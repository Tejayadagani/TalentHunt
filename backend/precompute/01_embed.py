"""
01_embed.py — Step 1: Embed all candidate profiles.

Loads candidates.jsonl.gz (or candidates.json), builds profile text,
embeds with sentence-transformers all-MiniLM-L6-v2,
saves embeddings.npy + candidate_ids.pkl to the artifacts directory.

Usage:
    cd backend
    python precompute/01_embed.py --candidates data/candidates.json

Runtime: ~15–20 min for 100K profiles on CPU. Much faster for small sets.
"""

import argparse
import logging
import pickle
import sys
import time
from pathlib import Path

import numpy as np
from tqdm import tqdm

# Allow running from backend/ directory
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from config import EMBEDDING_MODEL, EMBEDDINGS_FILE, CANDIDATE_IDS_FILE

logging.basicConfig(
    format="[01_embed] %(levelname)s %(message)s", level=logging.INFO
)
log = logging.getLogger(__name__)


from precompute.utils import build_profile_text, load_candidates, normalize_candidate

def main():
    parser = argparse.ArgumentParser(description="Embed candidate profiles.")
    parser.add_argument("--candidates", default="data/candidates.json",
                        help="Path to candidates file (.json/.jsonl/.jsonl.gz)")
    parser.add_argument("--batch-size", type=int, default=256,
                        help="Embedding batch size (default 256)")
    parser.add_argument("--out-dir", default="artifacts",
                        help="Output directory for artifacts")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(exist_ok=True)

    # ── Load candidates ──────────────────────────────────────────────────────
    log.info(f"Loading candidates from: {args.candidates}")
    candidates = load_candidates(args.candidates)
    log.info(f"Loaded {len(candidates):,} candidate profiles.")

    # ── Normalize nested schema → flat dict ────────────────────────────
    log.info("Normalising candidate schema...")
    candidates = [normalize_candidate(c) for c in candidates]

    # ── Build profile texts ──────────────────────────────────────────────────
    log.info("Building profile texts...")
    texts = [build_profile_text(c) for c in candidates]
    candidate_ids = [c["candidate_id"] for c in candidates]   # always correct after normalise

    # ── Load embedding model ─────────────────────────────────────────────────
    log.info(f"Loading embedding model: {EMBEDDING_MODEL}")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(EMBEDDING_MODEL)
    log.info("Model loaded.")

    # ── Embed in batches ─────────────────────────────────────────────────────
    log.info(f"Embedding {len(texts):,} profiles in batches of {args.batch_size}...")
    start = time.time()
    embeddings = model.encode(
        texts,
        batch_size=args.batch_size,
        show_progress_bar=True,
        normalize_embeddings=True,
    )
    elapsed = time.time() - start
    log.info(f"Embedding complete in {elapsed:.1f}s. Shape: {embeddings.shape}")

    # ── Save artifacts ───────────────────────────────────────────────────────
    emb_path = out_dir / "embeddings.npy"
    ids_path  = out_dir / "candidate_ids.pkl"

    np.save(emb_path, embeddings)
    with open(ids_path, "wb") as f:
        pickle.dump(candidate_ids, f)

    log.info(f"Saved embeddings → {emb_path}")
    log.info(f"Saved candidate_ids → {ids_path}")
    log.info("=" * 60)
    log.info("Step 1 complete. Next: python precompute/02_chromadb.py")


if __name__ == "__main__":
    main()
