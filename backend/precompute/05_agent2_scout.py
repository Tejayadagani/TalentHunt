"""
05_agent2_scout.py — Step 5: Retrieve top-40 candidates from ChromaDB.

Uses the JD embedding to query ChromaDB for top-200 by semantic similarity,
then re-ranks by pre_interview_score and returns top-40.

Usage:
    cd backend
    python precompute/05_agent2_scout.py
"""

import argparse
import json
import logging
import pickle
import sys
from pathlib import Path

import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from config import TOP_K_INTERVIEW, TOP_K_CHROMA, CHROMA_COLLECTION, CHROMA_PERSIST_DIR

logging.basicConfig(
    format="[05_scout] %(levelname)s %(message)s", level=logging.INFO
)
log = logging.getLogger(__name__)

import os
os.environ["ANONYMIZED_TELEMETRY"] = "False"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jd-embedding",  default="artifacts/jd_embedding.npy")
    parser.add_argument("--pre-scores",    default="artifacts/pre_scores.pkl")
    parser.add_argument("--candidates",    default="data/candidates.json")
    parser.add_argument("--out",           default="artifacts/scout_results.json")
    parser.add_argument("--top-interview", type=int, default=TOP_K_INTERVIEW,
                        help=f"Candidates who get interviewed (default {TOP_K_INTERVIEW})")
    parser.add_argument("--chroma-fetch",  type=int, default=TOP_K_CHROMA,
                        help=f"Over-fetch from ChromaDB (default {TOP_K_CHROMA})")
    args = parser.parse_args()

    # ── Load artifacts ───────────────────────────────────────────────────────
    log.info("Loading JD embedding...")
    jd_emb = np.load(args.jd_embedding).tolist()

    log.info("Loading pre-interview scores...")
    with open(args.pre_scores, "rb") as f:
        pre_scores: dict = pickle.load(f)

    # ── Re-rank directly from pre_scores ─────────────────────────────────────
    log.info("Re-ranking directly by pre_interview_score...")
    
    # Sort all non-honeypots by pre_score
    valid_cids = [
        cid for cid, data in pre_scores.items() 
        if data.get("flag") != "honeypot"
    ]
    
    # Sort by pre_score descending
    valid_cids.sort(key=lambda cid: pre_scores[cid].get("pre_score", 0), reverse=True)
    
    # Take top fetch_n
    top_cids = set(valid_cids[:args.chroma_fetch])
    
    # Now we need to fetch the metadata for these top_cids
    log.info(f"Loading metadata for top {args.chroma_fetch} candidates from raw file...")
    from precompute.utils import load_candidates, normalize_candidate
    
    candidates_ranked = []
    
    for raw_cand in load_candidates(args.candidates):
        cid = raw_cand.get("candidate_id") or raw_cand.get("id", "")
        if cid in top_cids:
            c = normalize_candidate(raw_cand)
            pre_data = pre_scores[cid]
            pre_score = pre_data.get("pre_score", 0)
            flag = pre_data.get("flag", "ok")
            semantic_sim = pre_data.get("breakdown", {}).get("semantic", 0)
            
            candidates_ranked.append({
                "candidate_id":       cid,
                "semantic_similarity": round(semantic_sim, 4),
                "pre_interview_score": round(pre_score, 6),
                "flag":               flag,
                "name":               str(c.get("name") or ""),
                "current_title":      str(c.get("current_title") or ""),
                "current_company":    str(c.get("current_company") or ""),
                "seniority":          str(c.get("seniority") or "mid"),
                "years_of_experience": int(c.get("years_of_experience") or 0),
                "location":           str(c.get("location") or ""),
                "skills":             [s.get("name", "") if isinstance(s, dict) else str(s) for s in c.get("skills", [])],
            })

    # Sort by pre_interview_score, take top-N for interviews
    candidates_ranked.sort(key=lambda x: x["pre_interview_score"], reverse=True)
    top_interview  = candidates_ranked[:args.top_interview]
    all_ranked     = candidates_ranked   # full list for rank.py

    log.info(f"Top {len(top_interview)} selected for interview simulation.")
    if top_interview:
        log.info(f"  #1: {top_interview[0]['name']} | pre_score={top_interview[0]['pre_interview_score']:.4f}")
        log.info(f"  #2: {top_interview[1]['name'] if len(top_interview)>1 else 'N/A'}")

    # ── Save results ─────────────────────────────────────────────────────────
    out_data = {
        "top_interview": top_interview,
        "all_ranked":    all_ranked,
        "total_fetched": len(candidates_ranked),
    }
    with open(args.out, "w") as f:
        json.dump(out_data, f, indent=2)
    log.info(f"Saved scout_results.json → {args.out}")
    log.info("Step 5 complete. Next: python precompute/06_agents34_interview.py")


if __name__ == "__main__":
    main()
