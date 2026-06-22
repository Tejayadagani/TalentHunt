"""
embed_candidates.py — One-time script to embed all candidate profiles into ChromaDB.

Run this ONCE after:
  1. Installing requirements.txt
  2. Having backend/data/candidates.json in place

Usage:
    cd backend
    python scripts/embed_candidates.py

Re-running is safe — upsert is idempotent (same candidate ID = overwrite).
"""

import json
import sys
import time
from pathlib import Path

# Allow running from either the `backend/` dir or the project root
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.vector_store import get_or_create_collection, upsert_candidates_batch, collection_count

CANDIDATES_FILE = Path("/Users/bhargavchowdaryyadagani/Downloads/India_runs_data_and_ai_challenge/candidates.jsonl")
if not CANDIDATES_FILE.exists():
    CANDIDATES_FILE = BACKEND_ROOT / "data" / "candidates.jsonl"


def main() -> None:
    print("=" * 60)
    print("  TalentRadar — Candidate Embedding Script (Batch Mode)")
    print("=" * 60)

    # ── Get (or create) the ChromaDB collection ──────────────────
    collection = get_or_create_collection()
    print(f"[2/3] ChromaDB collection ready  (current count: {collection.count()})")

    # ── Embed and upsert each candidate line by line ─────────────────────────
    print(f"\n[3/3] Embedding and upserting candidates …\n")

    success = 0
    errors  = 0
    batch = []
    BATCH_SIZE = 1000

    with open(CANDIDATES_FILE, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            
            try:
                raw_cand = json.loads(line)
                cid   = raw_cand.get("candidate_id", raw_cand.get("id", f"unknown_{i}"))
                
                profile = raw_cand.get("profile", {})
                skills_list = [s.get("name") for s in raw_cand.get("skills", []) if isinstance(s, dict)]
                
                # Build a comprehensive career narrative
                career_history = raw_cand.get("career_history", [])
                career_narrative = ""
                for role in career_history:
                    title = role.get("title", "")
                    company = role.get("company", "")
                    duration = role.get("duration_months", 0)
                    desc = role.get("description", "")
                    career_narrative += f"{title} at {company} ({duration} mos): {desc}. "
                
                signals = raw_cand.get("redrob_signals", {})
                
                # Create a flattened dictionary for the vector store
                candidate = {
                    "id": cid,
                    "name": profile.get("anonymized_name", "Unknown"),
                    "current_title": profile.get("current_title", ""),
                    "current_company": profile.get("current_company", ""),
                    "seniority": profile.get("seniority", "mid"),
                    "years_of_experience": profile.get("years_of_experience", 0),
                    "location": profile.get("location", ""),
                    "remote_ok": str(signals.get("preferred_work_mode", "")) == "remote",
                    "skills": skills_list,
                    "salary_expectation_inr": signals.get("expected_salary_range_inr_lpa", {}).get("min", 0) * 100000, 
                    "notice_period_days": signals.get("notice_period_days", 30),
                    "interest_level": 3,
                    "open_to_roles": [],
                    "email": "",
                    "bio": profile.get("summary", ""),
                    "career_history_text": career_narrative.strip(),
                    "recruiter_response_rate": signals.get("recruiter_response_rate", 1.0),
                    "last_active_date": signals.get("last_active_date", "")
                }
                
                batch.append(candidate)
                
                if len(batch) >= BATCH_SIZE:
                    upsert_candidates_batch(collection, batch)
                    success += len(batch)
                    print(f"  ✓  [{i:06d}]  Upserted batch of {len(batch)} ...")
                    batch = []
            
            except Exception as e:
                print(f"  ✗  [{i:06d}]  ERROR: {e}")
                errors += 1
        
        # Upsert any remaining candidates in the final batch
        if batch:
            try:
                upsert_candidates_batch(collection, batch)
                success += len(batch)
                print(f"  ✓  [final]  Upserted final batch of {len(batch)} ...")
            except Exception as e:
                print(f"  ✗  [final]  ERROR on final batch: {e}")
                errors += len(batch)

    # ── Summary ──────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"  Done!  ✓ {success} embedded   ✗ {errors} failed")
    print(f"  Total documents in ChromaDB: {collection_count()}")
    print("=" * 60)

    if errors:
        sys.exit(1)

    # ── Quick sanity-check query ─────────────────────────────────
    print("\n[Sanity check] Running a test query: 'Senior Python backend FastAPI fintech Bangalore' …\n")

    from app.vector_store import query_candidates
    results = query_candidates("Senior Python backend FastAPI fintech Bangalore", top_k=3)

    print(f"  Top 3 results:")
    for rank, c in enumerate(results, start=1):
        print(
            f"  {rank}. {c['name']:<22}  "
            f"seniority={c['seniority']:<12}  "
            f"semantic_similarity={c['semantic_similarity']:.1f}  "
            f"skills={c['skills'][:3]}"
        )
    print()


if __name__ == "__main__":
    main()
