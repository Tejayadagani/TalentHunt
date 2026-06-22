import sys
import json
import csv
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

INPUT_FILE = BACKEND_ROOT / "data" / "precomputed_scores.json"
PARSED_JD_FILE = BACKEND_ROOT / "data" / "parsed_jd.json"
OUTPUT_FILE = BACKEND_ROOT / "submission.csv"

def generate_deterministic_reason(parsed_jd: dict, candidate: dict) -> str:
    """
    Generate an honest, specific reasoning string using purely offline data.
    Cites exactly 2 specific facts (YOE, Title, Score) as required by Check 6.
    """
    yoe = candidate.get("years_of_experience", 0)
    title = candidate.get("current_title", "Unknown Role")
    semantic = candidate.get("match_breakdown", {}).get("semantic_similarity", 0)
    
    required_skills = {s.lower() for s in parsed_jd.get("required_skills", [])}
    cand_skills = {s.lower() for s in candidate.get("skills", [])}
    
    matched_skills = required_skills & cand_skills
    missing_skills = required_skills - cand_skills
    
    reason_parts = []
    
    # Fact 1: Exact YOE and Title
    reason_parts.append(f"Candidate holds {yoe} YOE as a '{title}'.")
    
    # Fact 2: Specific Signal Value (Semantic Score)
    reason_parts.append(f"Semantic match score is {semantic:.1f}/100.")
    
    # Fact 3 (Optional): Skills overlap
    if matched_skills:
        reason_parts.append(f"Demonstrates required skills: {', '.join(list(matched_skills)[:3])}.")
    if missing_skills:
        reason_parts.append(f"Missing some requirements like: {', '.join(list(missing_skills)[:2])}.")
        
    flag = candidate.get("flag", "ok")
    if flag != "ok":
        reason_parts.append(f"Flagged for: {flag}.")
    
    return " ".join(reason_parts)

def main():
    print("="*50)
    print(" Step 2: 100% Offline, API-Free Ranking (<5 mins)")
    print("="*50)
    
    if not INPUT_FILE.exists():
        print(f"[ERROR] {INPUT_FILE} not found! Run step1_precompute.py first.")
        sys.exit(1)
        
    if not PARSED_JD_FILE.exists():
        print(f"[ERROR] {PARSED_JD_FILE} not found! Run step1_precompute.py first.")
        sys.exit(1)
        
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        candidates = json.load(f)
        
    with open(PARSED_JD_FILE, "r", encoding="utf-8") as f:
        parsed_jd = json.load(f)
        
    print(f"[1/3] Loaded {len(candidates)} precomputed candidates.")
    
    # Sort descending by final score
    candidates.sort(key=lambda x: x["final_score"], reverse=True)
    
    top_100 = candidates[:100]
    print(f"      Selected top {len(top_100)} candidates.")
    
    # Strict assertions required by Hackathon judges (Check 1, 4)
    assert len(top_100) == 100, f"Expected exactly 100 candidates, but got {len(top_100)}"
    assert all(top_100[i]["final_score"] >= top_100[i+1]["final_score"] for i in range(len(top_100)-1)), "Scores are not monotonically non-increasing!"
    
    print("[2/3] Generating deterministic, honest reasoning (0 API calls)...")
    for c in top_100:
        c["reasoning"] = generate_deterministic_reason(parsed_jd, c)
            
    print(f"[3/3] Writing results to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "candidate_id", 
            "rank", 
            "score", 
            "reasoning"
        ])
        
        for rank, c in enumerate(top_100, start=1):
            cand_id = c.get("candidate_id", c.get("id", "Unknown"))
            writer.writerow([
                cand_id,
                rank,
                c["final_score"],
                c["reasoning"]
            ])
            
    print(f"\nDone! Submission ready at {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
