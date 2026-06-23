#!/usr/bin/env python3
"""
rank.py — SkillSync AI Hackathon Submission Script.

Loads precomputed_scores.pkl and generates submission.csv.
Zero network calls. Zero GPU. Runs in < 5 minutes on CPU.

Usage (exact hackathon command):
    python rank.py --candidates ./candidates.jsonl --out ./submission.csv

Output CSV format:
    candidate_id, rank, score, reasoning
    (exactly 100 rows, ranks 1-100, scores monotonically non-increasing)

Design decisions:
  1. All heavy computation (embedding, LLM calls, scoring) is done in
     the precompute pipeline (01_embed.py → 08_combine.py).
     rank.py is deliberately thin: load → sort → validate → write.

  2. The precomputed_scores.pkl is the single source of truth.
     If it's missing, rank.py falls back to a simplified CPU-only
     scoring from the candidate file (no LLM, no internet).

  3. Reasoning strings are pre-built in 08_combine.py and cached in
     the pickle file — rank.py never makes LLM calls.
"""

import argparse
import csv
import gzip
import json
import logging
import pickle
import sys
import time
from pathlib import Path
from datetime import datetime, date

logging.basicConfig(
    format="[rank.py] %(levelname)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ── Config (replicated here so rank.py is self-contained) ─────────────────────
TOP_K_FINAL        = 100
SUBMISSION_COLUMNS = ["candidate_id", "rank", "score", "reasoning"]
PRECOMPUTED_FILE   = Path(__file__).parent / "backend" / "artifacts" / "precomputed_scores.pkl"

# Consulting firm list for fallback scoring
_CONSULTING_FIRMS = {
    "tcs", "infosys", "wipro", "accenture", "cognizant",
    "capgemini", "hcl", "tech mahindra", "mphasis", "hexaware",
    "ltimindtree", "lti", "mindtree", "birlasoft", "syntel",
}
_WRONG_DOMAIN_TITLES = {
    "marketing manager", "hr manager", "accountant",
    "civil engineer", "mechanical engineer", "content writer",
    "graphic designer", "sales manager", "teacher", "doctor",
}


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="SkillSync AI — Generate submission.csv")
    parser.add_argument("--candidates", required=True,
                        help="Path to candidates.jsonl or candidates.json(.gz)")
    parser.add_argument("--out",        required=True,
                        help="Output path for submission.csv")
    parser.add_argument("--precomputed", default=str(PRECOMPUTED_FILE),
                        help="Path to precomputed_scores.pkl (default: backend/artifacts/precomputed_scores.pkl)")
    args = parser.parse_args()

    wall_start = time.time()

    # ── Validate candidates file exists ───────────────────────────────────────
    cand_path = Path(args.candidates)
    if not cand_path.exists():
        log.error(f"Candidates file not found: {args.candidates}")
        sys.exit(1)

    # ── Load precomputed scores (primary path) ─────────────────────────────────
    pkl_path = Path(args.precomputed)
    if pkl_path.exists():
        log.info(f"Loading precomputed scores from: {pkl_path}")
        ranked = _load_precomputed(pkl_path, args.candidates)
    else:
        log.warning(f"Precomputed scores not found at {pkl_path}.")
        log.warning("Running fallback CPU-only scoring (no LLM, no internet)...")
        ranked = _fallback_score(args.candidates)

    # ── Validate we have enough candidates ────────────────────────────────────
    if len(ranked) < TOP_K_FINAL:
        log.warning(f"Only {len(ranked)} candidates available (need {TOP_K_FINAL}).")
        if len(ranked) == 0:
            log.error("No candidates! Aborting.")
            sys.exit(1)

    # ── Take top-100 ──────────────────────────────────────────────────────────
    top_100 = ranked[:TOP_K_FINAL]

    # ── Enforce monotonic scores (safety check) ───────────────────────────────
    _enforce_monotonic(top_100)

    # ── Validate candidate_ids exist in the input file ────────────────────────
    valid_ids = _load_valid_ids(args.candidates)
    invalid   = [r for r in top_100 if r["candidate_id"] not in valid_ids]
    if invalid:
        log.error(f"INVALID candidate IDs (not in candidates file): {[r['candidate_id'] for r in invalid]}")
        sys.exit(1)

    # ── Write CSV ─────────────────────────────────────────────────────────────
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(top_100, out_path)

    # ── Final validation ──────────────────────────────────────────────────────
    _validate_output(out_path, valid_ids)

    elapsed = time.time() - wall_start
    log.info(f"rank.py completed in {elapsed:.1f}s.")

    if elapsed > 300:
        log.warning(f"Exceeded 5-minute limit ({elapsed:.0f}s)! Precompute pipeline may need optimisation.")
    else:
        log.info(f"✓ Within 5-minute limit.")

    log.info(f"Submission CSV: {out_path.resolve()}")


# ─────────────────────────────────────────────────────────────────────────────
# Load precomputed scores
# ─────────────────────────────────────────────────────────────────────────────
def _load_precomputed(pkl_path: Path, candidates_path: str) -> list[dict]:
    """Load pre-ranked candidates from pickle. Validates candidate_ids."""
    with open(pkl_path, "rb") as f:
        data = pickle.load(f)

    # data is a list of dicts (sorted by final_score descending from 08_combine.py)
    if not isinstance(data, list):
        log.error(f"Unexpected precomputed_scores.pkl format: {type(data)}")
        sys.exit(1)

    log.info(f"Loaded {len(data)} pre-ranked candidates from pickle.")

    # Re-sort by final_score descending (defensive, should already be sorted)
    data.sort(key=lambda x: x.get("final_score", 0.0), reverse=True)

    # Convert to submission row format
    rows = []
    for rank, entry in enumerate(data, start=1):
        cid     = entry.get("candidate_id", "")
        score   = entry.get("final_score", 0.0)
        reason  = entry.get("reasoning", _default_reasoning(entry, rank))

        if not cid:
            log.warning(f"Entry at rank {rank} has no candidate_id — skipping.")
            continue

        rows.append({
            "candidate_id": str(cid),
            "rank":         rank,
            "score":        round(float(score), 4),
            "reasoning":    str(reason).strip(),
        })

    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Fallback CPU-only scoring (no LLM, no internet)
# ─────────────────────────────────────────────────────────────────────────────
def _fallback_score(candidates_path: str) -> list[dict]:
    """
    Simplified scoring when precomputed_scores.pkl is missing.
    CPU-only, no internet, no GPU.
    """
    log.info("Fallback scoring: loading candidates...")
    raw_candidates = _load_candidates(candidates_path)
    # CRITICAL: normalize the nested schema before accessing any profile fields
    from pathlib import Path as _Path
    sys.path.insert(0, str(_Path(__file__).resolve().parent / "backend"))
    try:
        from precompute.utils import normalize_candidate
        candidates = [normalize_candidate(c) for c in raw_candidates]
    except ImportError:
        # If precompute not available, do basic extraction inline
        def normalize_candidate(r):
            p = r.get("profile", {})
            s = r.get("redrob_signals", {})
            return {"candidate_id": r.get("candidate_id", ""), "name": p.get("anonymized_name",""),
                    "current_title": p.get("current_title",""), "current_company": p.get("current_company",""),
                    "years_of_experience": p.get("years_of_experience",0),
                    "open_to_work": s.get("open_to_work_flag",False),
                    "notice_period_days": s.get("notice_period_days",60),
                    "skills": r.get("skills",[]), "career_history": r.get("career_history",[]),
                    **{k: v for k, v in r.items() if k not in ("profile","redrob_signals")}}
        candidates = [normalize_candidate(c) for c in raw_candidates]
    log.info(f"Loaded and normalised {len(candidates)} candidates for fallback scoring.")

    scored = []
    for c in candidates:
        cid   = c.get("candidate_id", "")   # always correct after normalise
        title = (c.get("current_title") or "").lower()
        yoe   = int(c.get("years_of_experience") or 0)

        # Disqualifier detection
        flag       = "ok"
        multiplier = 1.00
        if any(t in title for t in _WRONG_DOMAIN_TITLES):
            flag, multiplier = "wrong_domain", 0.40
        elif _is_consulting_only(c):
            flag, multiplier = "consulting_only", 0.25

        # Simple score components
        yoe_score = 1.0 if 5 <= yoe <= 9 else (0.5 if 3 <= yoe <= 12 else 0.2)
        otw_score = 1.0 if c.get("open_to_work") or c.get("actively_looking") else 0.3

        notice = int(c.get("notice_period_days") or 60)
        notice_score = 1.0 if notice <= 30 else (0.7 if notice <= 60 else 0.3)

        raw = 0.50 * yoe_score + 0.30 * otw_score + 0.20 * notice_score
        score = max(0.0, min(1.0, raw * multiplier))

        reason = _default_reasoning(dict(
            name=c.get("name",""), current_title=c.get("current_title",""),
            years_of_experience=yoe, skills=c.get("skills",[]), flag=flag,
        ), 0)

        scored.append({"candidate_id": str(cid), "score": round(score, 4),
                        "reasoning": reason, "flag": flag})

    scored.sort(key=lambda x: x["score"], reverse=True)
    for rank, entry in enumerate(scored, start=1):
        entry["rank"] = rank

    return scored


def _is_consulting_only(candidate: dict) -> bool:
    careers = candidate.get("career_history", [])
    if careers:
        for role in careers:
            company = (role.get("company") or "").lower()
            if not any(f in company for f in _CONSULTING_FIRMS):
                return False
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────
def _load_candidates(path: str) -> list[dict]:
    """Load candidates from JSON/JSONL/JSONL.GZ."""
    p = Path(path)
    if p.suffix == ".gz":
        with gzip.open(p, "rt", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    elif p.suffix == ".jsonl":
        with open(p, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    else:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else [data]


def _load_valid_ids(candidates_path: str) -> set[str]:
    """Return a set of all candidate_ids in the input file."""
    candidates = _load_candidates(candidates_path)
    ids = set()
    for c in candidates:
        # Real dataset uses "candidate_id" at top level
        cid = c.get("candidate_id") or c.get("id", "")
        if cid:
            ids.add(str(cid))
    log.info(f"Loaded {len(ids)} valid candidate IDs from input file.")
    return ids


def _enforce_monotonic(rows: list[dict]) -> None:
    """Clamp scores so they are monotonically non-increasing."""
    for i in range(1, len(rows)):
        if rows[i]["score"] > rows[i-1]["score"]:
            rows[i]["score"] = rows[i-1]["score"]


def _default_reasoning(entry: dict, rank: int) -> str:
    """Generate a minimal reasoning string when none is available."""
    name  = entry.get("name", entry.get("candidate_id", "Candidate"))
    title = entry.get("current_title", "professional")
    yoe   = entry.get("years_of_experience", 0)
    flag  = entry.get("flag", "ok")
    skills = entry.get("skills", [])
    skill_names = [s.get("name", "") if isinstance(s, dict) else str(s) for s in skills]
    skill_str = ", ".join(skill_names[:3]) if skill_names else "technical skills"

    reason = (
        f"{name} is a {title} with {yoe} years of experience, "
        f"demonstrating proficiency in {skill_str}."
    )
    if flag == "consulting_only":
        reason += " Note: entire career in IT services (0.25× multiplier applied)."
    elif flag == "wrong_domain":
        reason += " Note: current role outside target technical domain (0.40× multiplier applied)."
    if rank and rank <= 10:
        reason += f" Ranked #{rank} — recommended for priority technical screening."
    return reason


def _write_csv(rows: list[dict], out_path: Path) -> None:
    """Write submission CSV with exactly the required columns in order."""
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SUBMISSION_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    log.info(f"Wrote {len(rows)} rows to {out_path}")


def _validate_output(out_path: Path, valid_ids: set[str]) -> None:
    """Run all submission spec checks on the output CSV."""
    errors = 0

    with open(out_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows   = list(reader)

    # 1.5 — Exactly 100 rows
    if len(rows) != TOP_K_FINAL:
        log.error(f"✗ Expected {TOP_K_FINAL} rows, got {len(rows)}")
        errors += 1
    else:
        log.info(f"✓ Row count: {len(rows)}")

    # 1.9 — Correct column order
    actual_cols = list(rows[0].keys()) if rows else []
    if actual_cols != SUBMISSION_COLUMNS:
        log.error(f"✗ Column mismatch: {actual_cols} ≠ {SUBMISSION_COLUMNS}")
        errors += 1
    else:
        log.info(f"✓ Column order: {SUBMISSION_COLUMNS}")

    # 1.6 — Ranks 1-100, no gaps, no duplicates
    ranks = [int(r["rank"]) for r in rows]
    if sorted(ranks) != list(range(1, TOP_K_FINAL + 1)):
        log.error(f"✗ Rank sequence invalid: min={min(ranks)} max={max(ranks)} unique={len(set(ranks))}")
        errors += 1
    else:
        log.info(f"✓ Ranks: 1–{TOP_K_FINAL}, no gaps, no duplicates")

    # 1.8 — All candidate_ids in input
    ids = [r["candidate_id"] for r in rows]
    invalid = [cid for cid in ids if cid not in valid_ids]
    if invalid:
        log.error(f"✗ Invalid candidate_ids: {invalid[:5]}")
        errors += 1
    else:
        log.info(f"✓ All candidate_ids valid")

    # 1.7 — Monotonically non-increasing scores
    scores = [float(r["score"]) for r in rows]
    mono_errors = [(i+1, scores[i], scores[i+1]) for i in range(len(scores)-1)
                   if scores[i] < scores[i+1]]
    if mono_errors:
        log.error(f"✗ Score not monotonic at {len(mono_errors)} positions: {mono_errors[:3]}")
        errors += 1
    else:
        log.info(f"✓ Scores monotonically non-increasing")

    # Reasoning non-empty
    empty_reasoning = [r["candidate_id"] for r in rows if not r.get("reasoning", "").strip()]
    if empty_reasoning:
        log.warning(f"⚠ Empty reasoning for {len(empty_reasoning)} candidates")
    else:
        log.info(f"✓ All reasoning entries non-empty")

    # Summary
    log.info(f"\n{'='*60}")
    if errors == 0:
        log.info("✓ ALL SUBMISSION CHECKS PASSED")
    else:
        log.error(f"✗ {errors} SUBMISSION CHECK(S) FAILED")
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()
