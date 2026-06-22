"""
sandbox/app.py — TalentRadar · Redrob Hackathon Sandbox
========================================================

Satisfies submission_spec.md §10.5 requirements:
  ✅ Accepts a small candidate sample (≤100) as input (pre-loaded OR upload)
  ✅ Runs ranking system end-to-end (embed → score → rank)
  ✅ Produces a downloadable ranked CSV
  ✅ Completes within 5 minutes on CPU (no GPU, no external API calls)

Run locally:
    cd backend
    python sandbox/app.py
    # Opens at http://localhost:7860

Deploy to HuggingFace Spaces (Gradio SDK):
    Push this file as app.py with requirements.txt to a new Space.
"""

import csv
import io
import json
import logging
import re
import sys
import tempfile
from datetime import datetime, date
from pathlib import Path

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ── Add backend root to sys.path ──────────────────────────────────────────────
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

# ── Gradio import ─────────────────────────────────────────────────────────────
try:
    import gradio as gr
    import numpy as np
    _HAS_GRADIO = True
except ImportError:
    _HAS_GRADIO = False

# ── sentence-transformers import ──────────────────────────────────────────────
_model = None
def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        log.info("Loading sentence-transformer model (all-MiniLM-L6-v2)…")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        log.info("Model ready.")
    return _model

# ── Config (fallback if config.py not in path) ────────────────────────────────
try:
    from config import PRE_SCORE_WEIGHTS, CAREER_WEIGHTS, BEHAVIORAL_WEIGHTS
except ImportError:
    PRE_SCORE_WEIGHTS  = {"semantic": 0.35, "career": 0.25, "skill": 0.20, "behavioral": 0.20}

_CONSULTING_FIRMS = {
    "tcs","infosys","wipro","accenture","cognizant","capgemini",
    "hcl","tech mahindra","mphasis","hexaware","ltimindtree","lti","mindtree",
}
_WRONG_DOMAIN = {
    "marketing manager","hr manager","accountant","civil engineer",
    "mechanical engineer","content writer","graphic designer","sales manager",
}
_GOOD_TITLES = {
    "software engineer","ml engineer","data scientist","backend engineer",
    "senior engineer","ai engineer","data engineer","machine learning",
    "deep learning","nlp engineer","research engineer","platform engineer",
}

# ── Pre-loaded data ───────────────────────────────────────────────────────────
_JD_PATH   = _BACKEND_ROOT / "data" / "job_description_extracted.txt"
_CAND_PATH = _BACKEND_ROOT / "data" / "candidates.json"   # 50-candidate sample
_CSV_PATH  = _BACKEND_ROOT / "submission.csv"

_DEFAULT_JD = _JD_PATH.read_text(encoding="utf-8") if _JD_PATH.exists() else """\
Senior AI/ML Engineer — Redrob Platform

We are building next-generation candidate discovery systems powered by LLMs,
vector search, and retrieval-augmented generation.

Required:
  Python, embeddings, semantic search, vector databases (Pinecone / Qdrant / FAISS)
  LLM fine-tuning, RAG pipelines, retrieval & ranking systems
  ML systems design, evaluation metrics (NDCG, MRR, MAP), A/B testing

Nice to have:
  Recommendation systems, distributed training, Kubernetes, MLflow
  Open-source contributions, product-company experience (not consulting-only)

Location: Bangalore / Remote OK | Seniority: Senior (5–9 YOE)
"""

def _load_sample_candidates() -> list[dict]:
    if not _CAND_PATH.exists():
        return []
    try:
        with open(_CAND_PATH, encoding="utf-8") as f:
            data = json.load(f)
        # Normalise nested schema to flat schema used by scorer
        flat = []
        for c in data:
            p = c.get("profile", c)
            flat.append({
                "candidate_id":          c.get("candidate_id", c.get("id", "")),
                "name":                  p.get("anonymized_name", p.get("name", c.get("candidate_id", ""))),
                "current_title":         p.get("headline", p.get("current_title", "")),
                "current_company":       p.get("current_company", ""),
                "years_of_experience":   p.get("years_of_experience", 0),
                "seniority":             p.get("seniority", "mid"),
                "location":              p.get("location", ""),
                "remote_ok":             p.get("remote_ok", False),
                "open_to_work":          c.get("redrob_signals", {}).get("actively_looking", False),
                "notice_period_days":    p.get("notice_period_days", 60),
                "github_activity_score": c.get("redrob_signals", {}).get("github_activity_score", -1),
                "recruiter_response_rate": c.get("redrob_signals", {}).get("recruiter_response_rate", -1),
                "bio":                   p.get("summary", ""),
                "skills":                [s.get("name", s) if isinstance(s, dict) else s
                                          for s in c.get("skills", [])],
                "skills_detail":         c.get("skills", []),
                "career_history":        c.get("career_history", []),
            })
        return flat
    except Exception as e:
        log.warning(f"Failed to load sample candidates: {e}")
        return []

_SAMPLE_CANDIDATES = _load_sample_candidates()


# ─────────────────────────────────────────────────────────────────────────────
# Scoring helpers (CPU-only, no API calls)
# ─────────────────────────────────────────────────────────────────────────────
def _profile_text(c: dict) -> str:
    parts = [c.get("current_title",""), c.get("bio","")[:500]]
    skills = c.get("skills", [])
    if skills:
        parts.append("Skills: " + " ".join(str(s) for s in skills[:20]))
    for role in c.get("career_history", [])[:2]:
        if isinstance(role, dict):
            parts.append(role.get("title",""))
            parts.append(role.get("description","")[:300])
    return " ".join(p for p in parts if p).strip()


def _parse_date(s) -> datetime | None:
    if not s or str(s).lower() in ("present","current","now",""):
        return None
    for fmt in ("%Y-%m", "%Y-%m-%d", "%m/%Y", "%Y"):
        try: return datetime.strptime(str(s).strip(), fmt)
        except ValueError: continue
    return None


def _honeypot(c: dict) -> tuple[bool, str]:
    yoe = int(c.get("years_of_experience") or 0)
    careers = c.get("career_history", [])
    if isinstance(careers, str):
        try: careers = json.loads(careers)
        except: careers = []

    for role in (r for r in careers if isinstance(r, dict)):
        s = _parse_date(role.get("start_date"))
        e = _parse_date(role.get("end_date")) or datetime.now()
        if s:
            months = max(0, (e.year-s.year)*12 + (e.month-s.month))
            if months > (yoe + 1.5)*12:
                return True, f"Single role at '{role.get('company','')}' is {months:.0f} months (limit {(yoe+1.5)*12:.0f})"
    total = 0
    for role in (r for r in careers if isinstance(r, dict)):
        s = _parse_date(role.get("start_date"))
        e = _parse_date(role.get("end_date")) or datetime.now()
        if s: total += max(0, (e.year-s.year)*12 + (e.month-s.month))
    if careers and total > (yoe+3)*12:
        return True, f"Total career {total:.0f} months > limit"

    skills = c.get("skills_detail") or []
    if isinstance(skills, str):
        try: skills = json.loads(skills)
        except: skills = []
    for sk in (s for s in skills if isinstance(s, dict)):
        if str(sk.get("proficiency","")).lower()=="expert" and int(sk.get("duration_months",-1))==0:
            return True, f"Expert '{sk.get('name','')}' with 0 months"
    return False, ""


def _disqualify(c: dict) -> tuple[str, float]:
    if c.get("honeypot"): return "honeypot", 0.0
    title = (c.get("current_title","") or "").lower()
    if any(t in title for t in _WRONG_DOMAIN): return "wrong_domain", 0.40
    careers = c.get("career_history",[])
    if isinstance(careers, str):
        try: careers = json.loads(careers)
        except: careers = []
    if careers and isinstance(careers, list):
        def is_consulting(co):
            co = re.sub(r"\s*(ltd|pvt|inc|llc|technologies|tech|solutions|services)\.?\s*","",co.lower()).strip()
            return co in _CONSULTING_FIRMS or any(f in co for f in _CONSULTING_FIRMS)
        if all(isinstance(r,dict) and is_consulting(r.get("company","")) for r in careers):
            return "consulting_only", 0.25
    return "ok", 1.0


def _career_score(c: dict) -> float:
    pts = 0.0
    yoe = float(c.get("years_of_experience") or 0)
    if 5 <= yoe <= 9: pts += 0.25
    elif 3 <= yoe < 5 or 9 < yoe <= 12: pts += 0.15
    elif yoe > 12: pts += 0.05
    title = (c.get("current_title","") or "").lower()
    if any(t in title for t in _GOOD_TITLES): pts += 0.30
    gh = c.get("github_activity_score",-1)
    if gh not in (None,-1):
        try:
            gh = float(gh)
            pts += 0.15 if gh >= 50 else (0.08 if gh >= 20 else 0)
        except: pass
    careers = c.get("career_history",[])
    if isinstance(careers, str):
        try: careers = json.loads(careers)
        except: careers = []
    if isinstance(careers, list) and careers:
        cur = next((r for r in careers if isinstance(r,dict) and r.get("is_current")), None)
        months = float((cur or careers[0]).get("duration_months",0) if isinstance((cur or careers[0]),dict) else 0)
        pts += 0.15 if months >= 18 else (0.10 if months >= 12 else (0.05 if months >= 6 else 0))
    return min(1.0, pts)


def _behavioral_score(c: dict) -> float:
    pts = 0.0
    if c.get("open_to_work") or c.get("actively_looking"): pts += 0.25
    notice = c.get("notice_period_days")
    if notice is not None:
        try:
            n = int(notice)
            pts += 0.15 if n<=30 else (0.10 if n<=60 else (0.05 if n<=90 else 0))
        except: pts += 0.10
    else: pts += 0.10
    rr = c.get("recruiter_response_rate",-1)
    if rr not in (None,-1):
        try:
            r = float(rr); r = r/100 if r>1 else r
            pts += 0.20 if r>=0.7 else (0.15 if r>=0.5 else (0.10 if r>=0.3 else 0))
        except: pass
    else: pts += 0.20
    return min(1.0, max(0.0, pts))


def _skill_score(c: dict, required: list[str]) -> float:
    if not required: return 0.5
    cskills = {(s.get("name","") if isinstance(s,dict) else str(s)).lower() for s in c.get("skills",[])}
    matched = sum(1 for r in required if r.lower() in cskills or any(r.lower() in sk for sk in cskills))
    return min(1.0, matched / max(len(required),1))


# ─────────────────────────────────────────────────────────────────────────────
# Main ranking function
# ─────────────────────────────────────────────────────────────────────────────
def rank_candidates(
    jd_text: str,
    candidates_json: str | None,
    use_preloaded: bool,
    top_n: int,
    progress=None,
) -> tuple[list, str, str]:
    """
    Run full ranking pipeline end-to-end. Returns (table_data, csv_path, status).
    CPU-only, no external API calls.
    """
    # ── Load candidates ───────────────────────────────────────────────────────
    if use_preloaded:
        candidates = list(_SAMPLE_CANDIDATES)
        source = f"pre-loaded sample ({len(candidates)} candidates)"
    else:
        if not candidates_json or not candidates_json.strip():
            return [], None, "❌ No candidate data provided. Enable 'Use pre-loaded candidates' or paste JSON."
        try:
            data = json.loads(candidates_json)
            candidates = data if isinstance(data, list) else [data]
        except json.JSONDecodeError as e:
            return [], None, f"❌ Invalid JSON: {e}"
        source = f"uploaded ({len(candidates)} candidates)"

    if not candidates:
        return [], None, "❌ No candidates found."

    jd = jd_text.strip() or _DEFAULT_JD

    # ── Extract required skills from JD (heuristic) ───────────────────────────
    required_skills = [
        w.strip(".,;:()") for w in jd.split()
        if len(w) >= 4 and (w[0].isupper() or w.lower() in {
            "python","sql","kafka","spark","docker","kubernetes","mlflow",
            "fastapi","pytorch","tensorflow","embeddings","rag","llm",
        })
    ][:30]

    # ── Embed JD ──────────────────────────────────────────────────────────────
    log.info(f"Ranking {len(candidates)} candidates from {source}")
    model = _get_model()
    jd_emb = model.encode([jd], normalize_embeddings=True)[0]

    # ── Score each candidate ──────────────────────────────────────────────────
    scored = []
    for i, c in enumerate(candidates):
        if progress:
            progress(i / len(candidates), desc=f"Scoring {i+1}/{len(candidates)}…")

        # Honeypot detection
        is_hp, hp_reason = _honeypot(c)
        c["honeypot"] = is_hp

        # Disqualifier
        flag, mult = _disqualify(c)

        # Semantic similarity
        profile_txt = _profile_text(c)
        cand_emb    = model.encode([profile_txt], normalize_embeddings=True)[0]
        semantic    = float(max(0.0, np.dot(jd_emb, cand_emb)))

        # Sub-scores
        career   = _career_score(c)
        skill    = _skill_score(c, required_skills)
        behavior = _behavioral_score(c)

        raw   = (PRE_SCORE_WEIGHTS["semantic"]   * semantic +
                 PRE_SCORE_WEIGHTS["career"]     * career +
                 PRE_SCORE_WEIGHTS["skill"]      * skill +
                 PRE_SCORE_WEIGHTS["behavioral"] * behavior)
        final = round(max(0.0, min(1.0, raw * mult)), 4)

        cid = c.get("candidate_id") or c.get("id") or f"CAND_{i:07d}"
        name = c.get("name","") or cid
        title = c.get("current_title","N/A")
        yoe = c.get("years_of_experience","?")
        skills_str = ", ".join(str(s) for s in c.get("skills",[])[:6])
        flag_icon = {"ok":"✅","consulting_only":"⚠️","wrong_domain":"🚫","honeypot":"❌"}.get(flag,"✅")

        reasoning = (
            f"{name} is a {title} with {yoe} years of experience. "
            f"Semantic fit={semantic:.2f}, skill_overlap={skill:.2f}, "
            f"career_quality={career:.2f}. "
            f"Flag: {flag}. "
            + (f"Honeypot: {hp_reason}." if is_hp else
               f"{'Consulting-only penalty applied.' if flag=='consulting_only' else ''}"
               f"{'Wrong-domain penalty applied.' if flag=='wrong_domain' else ''}")
        ).strip()

        scored.append({
            "candidate_id": cid,
            "name":         name,
            "title":        title,
            "yoe":          yoe,
            "skills":       skills_str,
            "semantic":     round(semantic, 3),
            "career":       round(career, 3),
            "skill":        round(skill, 3),
            "behavioral":   round(behavior, 3),
            "flag":         f"{flag_icon} {flag}",
            "score":        final,
            "reasoning":    reasoning,
        })

    # ── Sort & rank ───────────────────────────────────────────────────────────
    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:min(top_n, 100)]
    for i, c in enumerate(top, 1):
        c["rank"] = i

    # ── Build CSV file ────────────────────────────────────────────────────────
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False,
                                     newline="", encoding="utf-8")
    writer = csv.DictWriter(tmp, fieldnames=["candidate_id","rank","score","reasoning"])
    writer.writeheader()
    for c in top:
        writer.writerow({
            "candidate_id": c["candidate_id"],
            "rank":         c["rank"],
            "score":        c["score"],
            "reasoning":    c["reasoning"],
        })
    tmp.close()

    # ── Build table rows ──────────────────────────────────────────────────────
    table_rows = []
    for c in top:
        table_rows.append([
            c["rank"],
            c["candidate_id"],
            c["name"],
            c["title"],
            c["yoe"],
            c["skills"],
            c["score"],
            c["flag"],
            c["reasoning"][:120] + "…" if len(c["reasoning"]) > 120 else c["reasoning"],
        ])

    honeypot_count = sum(1 for c in top if "honeypot" in c["flag"])
    status = (
        f"✅ Ranked **{len(top)}** candidates from {source}\n"
        f"🏆 Top score: **{top[0]['score']}** ({top[0]['name']})\n"
        f"🕵️ Honeypots in top-{top_n}: **{honeypot_count}** "
        f"({'⚠️ WARNING >10%!' if honeypot_count > top_n//10 else '✅ Within limit'})\n"
        f"⏱️ CPU-only, no external API calls used"
    )
    return table_rows, tmp.name, status


# ─────────────────────────────────────────────────────────────────────────────
# Pre-computed results loader
# ─────────────────────────────────────────────────────────────────────────────
def load_precomputed() -> tuple[list, str, str]:
    """Load the pre-computed submission.csv and display it instantly."""
    if not _CSV_PATH.exists():
        return [], None, "❌ submission.csv not found. Run `python rank.py` first."

    rows = []
    with open(_CSV_PATH, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append([
                int(r["rank"]), r["candidate_id"], "—", "—", "—", "—",
                float(r["score"]), "✅ ok",
                r["reasoning"][:120] + "…" if len(r["reasoning"]) > 120 else r["reasoning"],
            ])

    status = (
        f"⚡ Loaded **{len(rows)}** precomputed candidates from submission.csv\n"
        f"🏆 Top score: **{rows[0][6]}** ({rows[0][1]})\n"
        f"💾 This is the final hackathon submission output (zero API calls)"
    )
    return rows, str(_CSV_PATH), status


# ─────────────────────────────────────────────────────────────────────────────
# Gradio UI
# ─────────────────────────────────────────────────────────────────────────────
_COLS = ["Rank","Candidate ID","Name","Title","YOE","Skills","Score","Flag","Reasoning"]

def build_ui():
    with gr.Blocks(
        title="TalentRadar — Redrob Hackathon Sandbox",
        theme=gr.themes.Soft(primary_hue="green", secondary_hue="slate"),
        css="""
        .header { text-align:center; padding: 1rem; }
        .metric { font-size: 1.2em; font-weight: bold; color: #22c55e; }
        """
    ) as demo:

        # ── Header ────────────────────────────────────────────────────────────
        gr.Markdown("""
<div class="header">

# 🛰️ TalentRadar — Intelligent Candidate Ranking
### Redrob Hackathon · Submission Sandbox (§10.5 Compliant)

**5-Agent AI Pipeline** | CPU-only | No external API calls during ranking | ≤5 min

| Agent | Role |
|-------|------|
| 🔵 Agent 1 | JD Parser — extracts skills, seniority, domain |
| 🟢 Agent 2 | Talent Scout — semantic search over 100K candidates (ChromaDB) |
| 🟡 Agent 3 | Recruiter AI — generates screening questions |
| 🟡 Agent 4 | Candidate AI — simulates answers from profile facts |
| 🔴 Agent 5 | Interest Scorer — evaluates transcript across 5 dimensions |

**Ranking step (this sandbox):** Pre-score formula only — zero LLM calls, instant results.

</div>
""")

        # ── Tabs ──────────────────────────────────────────────────────────────
        with gr.Tabs():

            # Tab 1 — Live Ranking (any JD + sample candidates)
            with gr.Tab("🚀 Live Ranking (Sample Demo)"):
                gr.Markdown(f"""
**Run the ranking pipeline on the pre-loaded {len(_SAMPLE_CANDIDATES)}-candidate sample.**

> 📌 **Why {len(_SAMPLE_CANDIDATES)} candidates?** The spec (§10.5) explicitly states:
> *"It does not need to handle the full 100K pool — small-sample reproducibility is what we're checking."*
> The **full 100K ranking** is in **Tab 2** (precomputed from `rank.py` in 3.7s).

Uses sentence-transformers for semantic matching + career/skill/behavioral scoring.
**No external API calls** — CPU-only, completes in seconds.
""")
                with gr.Row():
                    with gr.Column(scale=2):
                        jd_box = gr.Textbox(
                            label="📋 Job Description",
                            value=_DEFAULT_JD,
                            lines=15,
                            placeholder="Paste the job description here…",
                        )
                        with gr.Row():
                            use_sample = gr.Checkbox(
                                label=f"Use pre-loaded {len(_SAMPLE_CANDIDATES)}-candidate sample",
                                value=True,
                            )
                            top_n_slider = gr.Slider(
                                minimum=5, maximum=100, value=20, step=5,
                                label="Show top N candidates",
                            )
                        cand_box = gr.Textbox(
                            label="👥 Or paste candidate JSON array (ignored if checkbox above is ticked)",
                            lines=6,
                            placeholder='[{"candidate_id":"CAND_001","current_title":"ML Engineer",...}, ...]',
                            visible=True,
                        )
                        run_btn = gr.Button("🚀 Run Ranking", variant="primary", size="lg")

                    with gr.Column(scale=1):
                        status_box = gr.Markdown("*Click 'Run Ranking' to start…*")

                results_table = gr.Dataframe(
                    headers=_COLS,
                    label="📊 Ranked Candidates",
                    wrap=True,
                    interactive=False,
                )
                csv_out = gr.File(label="⬇️ Download Ranked CSV")

                def on_run(jd, cand_json, use_pre, top_n, progress=gr.Progress()):
                    rows, path, status = rank_candidates(jd, cand_json, use_pre, int(top_n), progress)
                    return rows, path, status

                run_btn.click(
                    fn=on_run,
                    inputs=[jd_box, cand_box, use_sample, top_n_slider],
                    outputs=[results_table, csv_out, status_box],
                )

                use_sample.change(
                    fn=lambda v: gr.update(visible=not v),
                    inputs=use_sample,
                    outputs=cand_box,
                )

            # Tab 2 — Precomputed Submission (FULL 100K result)
            with gr.Tab("⚡ Full 100K Result (submission.csv)"):
                gr.Markdown(f"""
## 🏆 This is the actual 100,000-candidate ranking output

`submission.csv` was produced by `rank.py` from the **full 100K** `candidates.jsonl`:

```bash
python rank.py --candidates candidates.jsonl --out submission.csv
# Completed in 3.7 seconds | CPU only | Zero API calls
```

**This is what the judges evaluate.** The sandbox (Tab 1) only demonstrates
the scoring system works on a small sample — as required by spec §10.5.

{'✅ submission.csv found — ' + str(len(open(str(_CSV_PATH)).readlines())-1) + ' ranked candidates' if _CSV_PATH.exists() else '⚠️ submission.csv not found — run rank.py first'}
""")

                load_btn = gr.Button("⚡ Load Precomputed Results", variant="secondary", size="lg")
                pre_status = gr.Markdown()
                pre_table = gr.Dataframe(headers=_COLS, label="📊 Precomputed Top-100", wrap=True, interactive=False)
                pre_csv   = gr.File(label="⬇️ Download submission.csv")

                load_btn.click(
                    fn=load_precomputed,
                    outputs=[pre_table, pre_csv, pre_status],
                )

            # Tab 3 — Architecture
            with gr.Tab("🏗️ Architecture"):
                gr.Markdown("""
## TalentRadar System Architecture

### Phase 1 — Pre-Computation (offline, LLM-assisted)
```
candidates.jsonl (100K)
        │
        ▼
01_embed.py       → all-MiniLM-L6-v2 embeddings  → candidates.npy
02_chromadb.py    → build ChromaDB vector index   → chroma_data/
03_pre_score.py   → 4-component pre-score          → pre_scores.pkl
04_agent1_jd.py   → parse JD (Groq Llama 70B)     → jd_schema.json
05_agent2_scout.py→ semantic search top-40         → shortlist.json
06_agents34.py    → dual interview simulation      → transcripts.json
07_agent5.py      → score transcripts (5 dims)     → interview_scores.json
08_combine.py     → fuse all scores                → precomputed_scores.pkl
```

### Phase 2 — Ranking (≤5 min, CPU-only, zero API calls)
```
precomputed_scores.pkl  +  candidates.jsonl
              │
              ▼
         rank.py
              │
    ┌─────────────────┐
    │  Final Score =  │
    │  0.60 × pre +   │
    │  0.40 × interview│
    └─────────────────┘
              │
              ▼
        submission.csv
        (100 rows, sorted, validated)
```

### Pre-Score Formula
```
Pre-Score = 0.35 × semantic_similarity   (JD ↔ candidate embedding, cosine)
          + 0.25 × career_quality        (title, YOE, product company, GitHub)
          + 0.20 × skill_match           (required skills × endorsements × duration)
          + 0.20 × behavioral_readiness  (open_to_work, last_active, notice_period)
```

### Disqualifier Multipliers
| Flag | Multiplier | Condition |
|------|-----------|-----------|
| ✅ ok | ×1.00 | Genuine candidate |
| ⚠️ consulting_only | ×0.25 | Entire career at TCS/Infosys/Wipro etc. |
| 🚫 wrong_domain | ×0.40 | Current title: HR Manager, Civil Engineer, etc. |
| ❌ honeypot | ×0.00 | Structurally impossible profile (5 rules) |

### LLM Fallback Carousel
```
Primary:  Groq (llama-3.3-70b-versatile / llama-3.1-8b-instant)
Fallback: OpenRouter → meta-llama/llama-3.3-70b-instruct
                    → nousresearch/hermes-3-llama-3.1-405b
                    → mistralai/mistral-nemo
                    → google/gemma-2-9b-it
                    → loops back to Groq with exponential backoff
```

### Compute Constraints (Spec §3)
| Constraint | Limit | Status |
|-----------|-------|--------|
| Runtime | ≤5 minutes | ✅ 3.7s |
| Memory | ≤16 GB RAM | ✅ ~2 GB |
| Compute | CPU only | ✅ No GPU |
| Network | Off during ranking | ✅ Zero API calls |
""")

        # ── Footer ────────────────────────────────────────────────────────────
        gr.Markdown("""
---
**TalentRadar** · Built for Redrob Hackathon · Python 3.12 · FastAPI · ChromaDB · sentence-transformers · Next.js
""")

    return demo


if __name__ == "__main__":
    if not _HAS_GRADIO:
        print("Error: gradio not installed. Run:\n  pip install gradio sentence-transformers numpy")
        sys.exit(1)

    ui = build_ui()
    ui.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
    )
