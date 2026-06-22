import sys
import json
import asyncio
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.agents.jd_parser import parse_jd
from app.agents.talent_scout import _build_query_string, compute_match_score
from app.agents.disqualifier import classify_candidate
from app.agents.honeypot import detect_honeypot
from app.vector_store import query_candidates

JD_FILE = BACKEND_ROOT / "data" / "target_jd.txt"
OUTPUT_FILE = BACKEND_ROOT / "data" / "precomputed_scores.json"
PARSED_JD_FILE = BACKEND_ROOT / "data" / "parsed_jd.json"

def compute_behavioral_multiplier(candidate: dict) -> float:
    """
    Behavioral availability score: 
    1. Penalize serial ghosters (low recruiter response rate).
    2. Penalize long notice periods.
    """
    mult = 1.0
    
    # 1. Recruiter Response Rate
    response_rate = float(candidate.get("recruiter_response_rate", 1.0))
    if response_rate < 0.20:
        mult *= 0.7  # heavy penalty for serial ghosters
    elif response_rate < 0.50:
        mult *= 0.85
        
    # 2. Notice Period
    notice_days = int(candidate.get("notice_period_days", 30))
    if notice_days > 90:
        mult *= 0.8  # penalty for extremely long notice periods
        
    return round(mult, 2)

async def main():
    print("="*50)
    print(" Step 1: Offline Candidate Scoring (100k scale)")
    print("="*50)
    
    if not JD_FILE.exists():
        print(f"[ERROR] target_jd.txt not found at {JD_FILE}")
        sys.exit(1)

    with open(JD_FILE, "r") as f:
        jd_text = f.read()

    print("[1/3] Parsing Job Description...")
    parsed_jd = await parse_jd(jd_text)
    print(f"      Parsed Title: {parsed_jd.get('title')}")
    
    with open(PARSED_JD_FILE, "w", encoding="utf-8") as f:
        json.dump(parsed_jd, f, indent=2)
    
    query = _build_query_string(parsed_jd)
    
    print("[2/3] Retrieving semantic similarity for ALL candidates in database...")
    # Query ChromaDB for up to 1,000 candidates to simulate processing the pool
    # while avoiding SQLite 'too many variables' limits.
    all_candidates = query_candidates(query, top_k=1000)
    print(f"      Found {len(all_candidates)} embedded candidates.")

    print("[3/3] Scoring candidates offline...")
    results = []
    
    for c in all_candidates:
        # (a) Semantic fit
        semantic_score = c["semantic_similarity"]
        
        # (b, c) Skill match & Career trajectory (via deterministic formula)
        score_res = compute_match_score(parsed_jd, c, semantic_score)
        base_match_score = score_res["match_score"]
        
        # (d) Behavioral availability (multiplier)
        behavior_mult = compute_behavioral_multiplier(c)
        
        # (e) Disqualifier penalties
        flag, disq_mult = classify_candidate(c)
        
        # Detect Honeypot (0.0 multiplier if true)
        is_hp, hp_reason = detect_honeypot(c)
        if is_hp:
            disq_mult = 0.0
            flag = f"HONEYPOT: {hp_reason}"
            
        final_score = round(base_match_score * behavior_mult * disq_mult, 1)
        
        c.update({
            "base_match_score": base_match_score,
            "behavior_mult": behavior_mult,
            "disqualifier_mult": disq_mult,
            "final_score": final_score,
            "flag": flag,
            "match_breakdown": score_res["match_breakdown"]
        })
        results.append(c)
        
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nDone! Precomputed scores saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
