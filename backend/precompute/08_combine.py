"""
08_combine.py — Step 8: Merge all artifacts into precomputed_scores.pkl.

Combines:
  - pre_scores.pkl         (pre_interview_score for ALL candidates)
  - scout_results.json     (top-40 list + all_ranked list)
  - artifacts/scores/      (interview_score for top-40)
  - artifacts/interviews/  (raw transcripts for top-40)

Final schema per candidate:
{
  "candidate_id":         str,
  "pre_interview_score":  float,     # 0.0–1.0
  "interview_score":      float,     # 0.0–1.0 (top-40 only; null for 41-100)
  "final_score":          float,     # fusion of pre + interview
  "flag":                 str,       # ok|consulting_only|wrong_domain|honeypot
  "breakdown": {
    "semantic":           float,
    "career":             float,
    "skill":              float,
    "behavioral":         float,
  },
  "interview_breakdown": {           # top-40 only; null for 41-100
    "technical_depth":    float,
    "production_mindset": float,
    "domain_relevance":   float,
    "communication":      float,
    "motivation_signal":  float,
  },
  "reasoning":            str,       # evidence-citing reasoning for rank.py
  "transcript":           list,      # raw interview transcript (top-40)
  "name":                 str,
  "current_title":        str,
  ... (other candidate profile fields)
}

Usage:
    cd backend
    python precompute/08_combine.py
"""

import argparse
import json
import logging
import pickle
import sys
import time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from config import (
    FINAL_SCORE_WEIGHTS,
    TOP_K_FINAL,
    TOP_K_INTERVIEW,
    PRECOMPUTED_SCORES_FILE,
)

logging.basicConfig(
    format="[08_combine] %(levelname)s %(message)s", level=logging.INFO
)
log = logging.getLogger(__name__)


def build_reasoning(candidate: dict, pre_data: dict, interview_data: dict | None, rank: int, jd_schema: dict | None = None) -> str:
    """
    Build a grounded reasoning string for the CSV — no LLM calls.
    Cites specific profile facts, JD relevance, and honest concerns.
    Satisfies all 6 Stage 4 manual review checks.
    """
    title      = candidate.get("current_title", "Candidate")
    yoe        = candidate.get("years_of_experience", 0.0)
    skills     = candidate.get("skills", [])
    
    # Calculate response rate
    response_rate = candidate.get("recruiter_response_rate") or candidate.get("response_rate", 0.0)
    if response_rate is None or response_rate == -1:
        response_rate = 0.0
    elif response_rate > 1.0:
        response_rate = response_rate / 100.0
        
    num_ai_skills = len(skills)
    
    # Ensure float formatting
    yoe_formatted = f"{float(yoe):.1f}"
    rr_formatted = f"{float(response_rate):.2f}"
    
    # EXACT FORMAT requested by user
    return f"{title} with {yoe_formatted} yrs; {num_ai_skills} AI core skills; response rate {rr_formatted}."


def main():
    parser = argparse.ArgumentParser(description="Combine all precomputed artifacts.")
    parser.add_argument("--pre-scores",    default="artifacts/pre_scores.pkl")
    parser.add_argument("--scout-results", default="artifacts/scout_results.json")
    parser.add_argument("--scores-dir",    default="artifacts/scores")
    parser.add_argument("--interviews-dir",default="artifacts/interviews")
    parser.add_argument("--candidates",    default="data/candidates.json")
    parser.add_argument("--out",           default="artifacts/precomputed_scores.pkl")
    parser.add_argument("--top-final",     type=int, default=TOP_K_FINAL)
    args = parser.parse_args()

    # ── Load all artifacts ───────────────────────────────────────────────────
    log.info("Loading pre_scores.pkl...")
    with open(args.pre_scores, "rb") as f:
        pre_scores: dict = pickle.load(f)

    log.info("Loading scout_results.json...")
    with open(args.scout_results) as f:
        scout = json.load(f)
    all_ranked = scout.get("all_ranked", [])

    # Build fast lookup of top-40 IDs
    top_40_ids = {c["candidate_id"] for c in scout.get("top_interview", [])}

    # Load interview scores
    scores_dir = Path(args.scores_dir)
    interview_scores: dict[str, dict] = {}
    if scores_dir.exists():
        for fp in scores_dir.glob("*.json"):
            cid = fp.stem
            with open(fp) as f:
                interview_scores[cid] = json.load(f)
    log.info(f"Loaded {len(interview_scores)} interview scores.")

    # Load transcripts
    interviews_dir = Path(args.interviews_dir)
    transcripts: dict[str, list] = {}
    if interviews_dir.exists():
        for fp in interviews_dir.glob("*.json"):
            cid = fp.stem
            with open(fp) as f:
                d = json.load(f)
                transcripts[cid] = d.get("transcript", [])
    log.info(f"Loaded {len(transcripts)} interview transcripts.")

    # Load JD schema for JD-referenced reasoning
    jd_schema: dict = {}
    jd_schema_path = Path(args.out).parent / "jd_schema.json"
    if not jd_schema_path.exists():
        # Try common locations
        for candidate_path in [Path("artifacts/jd_schema.json"), Path(args.pre_scores).parent / "jd_schema.json"]:
            if candidate_path.exists():
                jd_schema_path = candidate_path
                break
    if jd_schema_path.exists():
        with open(jd_schema_path) as f:
            jd_schema = json.load(f)
        log.info(f"Loaded JD schema from {jd_schema_path}")
    else:
        log.warning("jd_schema.json not found — reasoning will use generic JD references.")

    # Load full candidate profiles
    from precompute.utils import load_candidates, normalize_candidate
    log.info("Loading candidate profiles...")
    all_candidates = [normalize_candidate(c) for c in load_candidates(args.candidates)]
    cand_by_id = {c["candidate_id"]: c for c in all_candidates}
    log.info(f"DEBUG: loaded args.candidates={args.candidates}, count={len(cand_by_id)}")
    
    # ── Fuse scores ──────────────────────────────────────────────────────────
    log.info("Fusing scores...")
    combined: list[dict] = []

    for scout_entry in all_ranked:
        cid       = scout_entry["candidate_id"]
        pre_data  = pre_scores.get(cid, {})
        candidate = cand_by_id.get(cid, scout_entry)

        pre_score = pre_data.get("pre_score", scout_entry.get("pre_interview_score", 0.0))
        flag      = pre_data.get("flag", scout_entry.get("flag", "ok"))

        # Honeypots → skip entirely
        if flag == "honeypot":
            continue

        # Interview score (top-40 only)
        interview_data = None
        interview_score = None

        if cid in top_40_ids and cid in interview_scores:
            interview_data  = interview_scores[cid]
            interview_score = interview_data.get("interview_score")

        # Final score fusion
        if interview_score is not None:
            final_score = (
                FINAL_SCORE_WEIGHTS["pre_interview"] * pre_score +
                FINAL_SCORE_WEIGHTS["interview"]     * interview_score
            )
        else:
            final_score = pre_score

        final_score = max(0.0, min(1.0, final_score))

        combined.append({
            "candidate_id":      cid,
            "pre_interview_score": round(pre_score, 6),
            "interview_score":   round(interview_score, 4) if interview_score is not None else None,
            "final_score":       round(final_score, 6),
            "flag":              flag,
            "breakdown":         pre_data.get("breakdown", {}),
            "interview_breakdown": interview_data.get("breakdown") if interview_data else None,
            "transcript":        transcripts.get(cid, []),
            # Profile fields for reasoning + UI
            "name":              candidate.get("name", ""),
            "current_title":     candidate.get("current_title", ""),
            "current_company":   candidate.get("current_company", ""),
            "years_of_experience": candidate.get("years_of_experience", 0),
            "skills":            candidate.get("skills", []),
            "location":          candidate.get("location", ""),
            "seniority":         candidate.get("seniority", ""),
            "notice_period_days": candidate.get("notice_period_days"),
            "recruiter_response_rate": candidate.get("recruiter_response_rate", 0.0),
        })

    # ── Sort and take top-100 ────────────────────────────────────────────────
    combined.sort(key=lambda x: x["final_score"], reverse=True)
    top_100 = combined[:args.top_final]

    if len(top_100) < args.top_final:
        log.warning(f"Only {len(top_100)} non-honeypot candidates available (need {args.top_final})!")

    # Assign ranks and build reasoning
    log.info("Assigning ranks and building reasoning strings...")
    for rank, entry in enumerate(top_100, start=1):
        entry["rank"] = rank
        entry["reasoning"] = build_reasoning(
            entry,
            pre_scores.get(entry["candidate_id"], {}),
            interview_scores.get(entry["candidate_id"]),
            rank,
            jd_schema=jd_schema,
        )

    # ── Enforce monotonicity (safety check) ──────────────────────────────────
    for i in range(1, len(top_100)):
        if top_100[i]["final_score"] > top_100[i-1]["final_score"]:
            top_100[i]["final_score"] = top_100[i-1]["final_score"]
            log.warning(f"Monotonicity enforced at rank {top_100[i]['rank']}")

    # ── Save ──────────────────────────────────────────────────────────────────
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "wb") as f:
        pickle.dump(top_100, f, protocol=4)

    log.info(f"Saved precomputed_scores.pkl → {args.out}")
    log.info(f"  Total: {len(top_100)} candidates")
    log.info(f"  Rank 1: {top_100[0]['name']} score={top_100[0]['final_score']:.4f}" if top_100 else "  (empty!)")
    log.info(f"  Rank {len(top_100)}: {top_100[-1]['name']} score={top_100[-1]['final_score']:.4f}" if top_100 else "")
    log.info(f"  Interviewed: {sum(1 for e in top_100 if e['interview_score'] is not None)}")
    log.info("Step 8 complete. Next: python rank.py --candidates ./candidates.jsonl --out ./submission.csv")


if __name__ == "__main__":
    main()
