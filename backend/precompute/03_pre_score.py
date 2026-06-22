"""
03_pre_score.py — Step 3: Compute pre_interview_score for all candidates.

Formula:
  pre_score = (
    0.30 × semantic_score        # cosine similarity JD embed ↔ profile embed
  + 0.30 × skill_score           # required skills match
  + 0.20 × career_score          # product company, title fit, YOE 5-9, GitHub
  + 0.20 × behavioral_score      # open_to_work, last_active, notice, response_rate
  ) × disqualifier_multiplier

Also runs honeypot detection — honeypots get pre_score = 0.0.
Saves pre_scores.pkl: {candidate_id: {"pre_score": float, "flag": str, ...}}

Usage:
    cd backend
    python precompute/03_pre_score.py --jd-schema artifacts/jd_schema.json
"""

import argparse
import json
import logging
import pickle
import sys
import time
from pathlib import Path

import numpy as np
from tqdm import tqdm

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from config import (
    PRE_SCORE_WEIGHTS, CAREER_WEIGHTS, BEHAVIORAL_WEIGHTS,
    SENIORITY_LADDER, YOE_TARGET_MIN, YOE_TARGET_MAX,
    NOTICE_PERIOD, CONSULTING_FIRMS, GOOD_TITLES,
)
from app.agents.honeypot import detect_honeypot
from app.agents.disqualifier import classify_candidate

logging.basicConfig(
    format="[03_pre_score] %(levelname)s %(message)s", level=logging.INFO
)
log = logging.getLogger(__name__)


from precompute.utils import (
    compute_skill_score,
    compute_career_score,
    compute_behavioral_score,
)
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Compute pre-interview scores.")
    parser.add_argument("--candidates", default="data/candidates.json")
    parser.add_argument("--embeddings", default="artifacts/embeddings.npy")
    parser.add_argument("--candidate-ids", default="artifacts/candidate_ids.pkl")
    parser.add_argument("--jd-schema", default="artifacts/jd_schema.json")
    parser.add_argument("--jd-embedding", default="artifacts/jd_embedding.npy")
    parser.add_argument("--out", default="artifacts/pre_scores.pkl")
    args = parser.parse_args()

    # ── Load all artifacts ───────────────────────────────────────────────────
    log.info("Loading JD schema...")
    with open(args.jd_schema) as f:
        jd_schema = json.load(f)
    required_skills = jd_schema.get("required_skills", [])
    nice_to_have_skills = jd_schema.get("nice_to_have_skills", [])
    jd_seniority    = (jd_schema.get("seniority") or "mid").lower()
    log.info(f"JD: {jd_schema.get('title')} | seniority={jd_seniority} | required={required_skills} | nice_to_have={nice_to_have_skills}")

    log.info("Loading embeddings...")
    embeddings = np.load(args.embeddings)
    with open(args.candidate_ids, "rb") as f:
        candidate_ids = pickle.load(f)

    log.info("Loading JD embedding...")
    jd_emb = np.load(args.jd_embedding)

    # Semantic similarity: embeddings are L2-normalized → dot product = cosine similarity
    log.info("Computing semantic similarities...")
    similarities_array = embeddings @ jd_emb  # shape: (N,)

    # ── STAGE 1 RETRIEVAL: Top 1000 ──────────────────────────────────────────
    log.info("Retrieving top 1000 candidates by semantic similarity...")
    top_1000_idx = np.argsort(similarities_array)[-1000:][::-1]

    # ── Load full candidate profiles ─────────────────────────────────────────
    from precompute.utils import load_candidates, normalize_candidate
    log.info("Loading candidate profiles...")
    candidates = [normalize_candidate(c) for c in load_candidates(args.candidates)]
    cand_by_id = {c["candidate_id"]: c for c in candidates}
    log.info(f"Normalised {len(candidates):,} candidates.")

    # ── STAGE 2 SCORING: Top 1000 only ───────────────────────────────────────
    log.info("Scoring top 1000 candidates...")
    pre_scores: dict = {}
    start = time.time()

    for idx in tqdm(top_1000_idx, total=1000):
        cid = candidate_ids[idx]
        sim = similarities_array[idx]
        candidate = cand_by_id.get(cid, {})

        # Step 1 — honeypot check FIRST, early return
        is_honeypot, hp_reason = detect_honeypot(candidate)
        if is_honeypot:
            pre_scores[cid] = {
                "pre_score":       0.0,
                "flag":            "honeypot",
                "multiplier":      0.0,
                "honeypot_reason": hp_reason,
                "breakdown":       {"semantic": 0, "career": 0, "skill": 0, "behavioral": 0},
            }
            continue

        # Clamp similarity to [0, 1]
        semantic = max(0.0, min(1.0, float(sim)))

        # Step 2 — compute the four base scores
        career   = compute_career_score(candidate, jd_seniority)
        skill    = compute_skill_score(candidate, required_skills, nice_to_have_skills)
        behavior = compute_behavioral_score(candidate)

        base_score = (
            PRE_SCORE_WEIGHTS["semantic"]   * semantic +
            PRE_SCORE_WEIGHTS["career"]     * career +
            PRE_SCORE_WEIGHTS["skill"]      * skill +
            PRE_SCORE_WEIGHTS["behavioral"] * behavior
        )
        
        # Step 3 — domain/consulting disqualifier multiplier
        flag, disqualifier_mult = classify_candidate(candidate)
        
        # Step 4 — keyword stuffing penalty
        # Stuffing detection must not depend on seniority — a fabricated senior profile is more damaging to ranking
        # quality than a fabricated junior one, since it also inflates career_score.
        stuffing_mult = 1.0
        if skill > 0.75 and semantic < 0.60:
            stuffing_mult = 0.50
            
        final_pre = base_score * disqualifier_mult * stuffing_mult

        pre_scores[cid] = {
            "pre_score":  round(final_pre, 6),
            "flag":       flag if disqualifier_mult < 1.0 else ("keyword_stuffing" if stuffing_mult < 1.0 else "ok"),
            "multiplier": disqualifier_mult * stuffing_mult,
            "breakdown":  {
                "semantic":   round(semantic, 4),
                "career":     round(career, 4),
                "skill":      round(skill, 4),
                "behavioral": round(behavior, 4),
            },
        }

    elapsed = time.time() - start
    log.info(f"Scoring complete in {elapsed:.1f}s.")

    # ── Save ──────────────────────────────────────────────────────────────────
    with open(args.out, "wb") as f:
        pickle.dump(pre_scores, f, protocol=4)

    honeypot_count = sum(1 for v in pre_scores.values() if v["flag"] == "honeypot")
    consult_count  = sum(1 for v in pre_scores.values() if v["flag"] == "consulting_only")
    log.info(f"Saved pre_scores.pkl → {args.out}")
    log.info(f"  Total: {len(pre_scores):,}  Honeypots: {honeypot_count:,}  Consulting-only: {consult_count:,}")
    log.info("Step 3 complete. Next: python precompute/04_agent1_jd_parser.py")


if __name__ == "__main__":
    main()
