"""
02_chromadb.py — Step 2: Build ChromaDB collection with pre-score metadata.

Loads embeddings.npy + candidate_ids.pkl + full candidate profiles,
then builds a ChromaDB collection with metadata including an initial
pre_interview_score placeholder (updated by step 3).

Usage:
    cd backend
    python precompute/02_chromadb.py
"""

import argparse
import logging
import pickle
import sys
from pathlib import Path

import numpy as np
from tqdm import tqdm

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from config import CHROMA_COLLECTION, CHROMA_PERSIST_DIR

logging.basicConfig(
    format="[02_chromadb] %(levelname)s %(message)s", level=logging.INFO
)
log = logging.getLogger(__name__)

import os
os.environ["ANONYMIZED_TELEMETRY"] = "False"


def main():
    parser = argparse.ArgumentParser(description="Build ChromaDB collection.")
    parser.add_argument("--candidates",    default="data/candidates.json")
    parser.add_argument("--embeddings",    default="artifacts/embeddings.npy")
    parser.add_argument("--candidate-ids", default="artifacts/candidate_ids.pkl")
    parser.add_argument("--batch-size",    type=int, default=500)
    args = parser.parse_args()

    # ── Load artifacts ───────────────────────────────────────────────────────
    log.info("Loading embeddings and candidate IDs...")
    embeddings    = np.load(args.embeddings)
    with open(args.candidate_ids, "rb") as f:
        candidate_ids = pickle.load(f)

    from precompute.utils import load_candidates, normalize_candidate
    log.info("Loading candidate profiles...")
    candidates = [normalize_candidate(c) for c in load_candidates(args.candidates)]
    cand_by_id = {c["candidate_id"]: c for c in candidates}

    # ── Init ChromaDB ────────────────────────────────────────────────────────
    import chromadb
    from chromadb.config import Settings

    log.info(f"Initialising ChromaDB at: {CHROMA_PERSIST_DIR}")
    client = chromadb.PersistentClient(
        path=CHROMA_PERSIST_DIR,
        settings=Settings(anonymized_telemetry=False),
    )

    # Delete and recreate for a clean build
    try:
        client.delete_collection(CHROMA_COLLECTION)
        log.info(f"Deleted existing '{CHROMA_COLLECTION}' collection.")
    except Exception:
        pass

    collection = client.create_collection(
        name=CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )
    log.info(f"Created fresh collection: '{CHROMA_COLLECTION}'")

    # ── Upsert in batches ────────────────────────────────────────────────────
    log.info(f"Upserting {len(candidate_ids):,} candidates in batches of {args.batch_size}...")
    total = len(candidate_ids)

    for batch_start in tqdm(range(0, total, args.batch_size)):
        batch_ids   = candidate_ids[batch_start : batch_start + args.batch_size]
        batch_embs  = embeddings[batch_start : batch_start + args.batch_size]

        batch_metas = []
        batch_docs  = []

        for cid, emb in zip(batch_ids, batch_embs):
            c = cand_by_id.get(cid, {})

            # Skills in dataset are [{name, proficiency, endorsements, duration_months}]
            skills_str = ",".join(
                s.get("name", "") if isinstance(s, dict) else str(s)
                for s in c.get("skills", [])
            )

            meta = {
                "candidate_id":        str(cid),
                "name":                str(c.get("name") or ""),
                "current_title":       str(c.get("current_title") or ""),
                "current_company":     str(c.get("current_company") or ""),
                "seniority":           str(c.get("seniority") or "mid"),
                "years_of_experience": float(c.get("years_of_experience") or 0),
                "location":            str(c.get("location") or ""),
                "skills":              skills_str,
                "notice_period_days":  int(c.get("notice_period_days") or 60),
                "open_to_work":        str(bool(c.get("open_to_work"))),
                "pre_interview_score": 0.0,   # placeholder, updated by step 3
                "flag":                "ok",  # placeholder, updated by step 3
            }
            batch_metas.append(meta)
            headline = c.get("headline") or c.get("current_title") or ""
            doc = f"{headline} {c.get('summary','')[:300]} Skills: {skills_str}"
            batch_docs.append(doc[:1000])   # ChromaDB 1KB doc limit

        collection.upsert(
            ids=[str(cid) for cid in batch_ids],
            embeddings=batch_embs.tolist(),
            metadatas=batch_metas,
            documents=batch_docs,
        )

    log.info(f"ChromaDB build complete. Total documents: {collection.count():,}")
    log.info("Step 2 complete. Next: python precompute/03_pre_score.py")


if __name__ == "__main__":
    main()
