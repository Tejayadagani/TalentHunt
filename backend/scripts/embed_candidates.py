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

from app.vector_store import get_or_create_collection, upsert_candidate, collection_count

CANDIDATES_FILE = BACKEND_ROOT / "data" / "candidates.json"


def main() -> None:
    print("=" * 60)
    print("  TalentRadar — Candidate Embedding Script")
    print("=" * 60)

    # ── Load candidates ──────────────────────────────────────────
    if not CANDIDATES_FILE.exists():
        print(f"[ERROR] candidates.json not found at: {CANDIDATES_FILE}")
        sys.exit(1)

    with open(CANDIDATES_FILE, encoding="utf-8") as f:
        candidates: list[dict] = json.load(f)

    print(f"\n[1/3] Loaded {len(candidates)} candidate profiles from candidates.json")

    # ── Get (or create) the ChromaDB collection ──────────────────
    collection = get_or_create_collection()
    print(f"[2/3] ChromaDB collection ready  (current count: {collection.count()})")

    # ── Embed and upsert each candidate ─────────────────────────
    print(f"\n[3/3] Embedding and upserting candidates …\n")

    success = 0
    errors  = 0

    for i, candidate in enumerate(candidates, start=1):
        cid   = candidate.get("id", f"unknown_{i}")
        name  = candidate.get("name", "Unknown")
        try:
            upsert_candidate(collection, candidate)
            print(f"  ✓  [{i:02d}/{len(candidates)}]  {cid}  —  {name}")
            success += 1
        except Exception as e:
            print(f"  ✗  [{i:02d}/{len(candidates)}]  {cid}  —  {name}  ERROR: {e}")
            errors += 1

        # Small pause so the console output is readable and rate limits
        # on any downstream resources (none here, but good habit) are respected.
        time.sleep(0.05)

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
