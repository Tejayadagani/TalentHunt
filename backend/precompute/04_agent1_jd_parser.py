"""
04_agent1_jd_parser.py — Step 4: Parse JD → structured JSON schema.

Calls Agent 1 (JD Parser) once for the whole pipeline.
Saves jd_schema.json and jd_embedding.npy.

Usage:
    cd backend
    python precompute/04_agent1_jd_parser.py --jd job_description.md
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from config import JD_SCHEMA_FILE, EMBEDDING_MODEL

logging.basicConfig(
    format="[04_jd_parser] %(levelname)s %(message)s", level=logging.INFO
)
log = logging.getLogger(__name__)


async def main_async(jd_path: str, out_schema: str, out_embedding: str):
    jd_text_path = Path(jd_path)
    if not jd_text_path.exists():
        log.error(f"JD file not found: {jd_path}")
        sys.exit(1)

    jd_text = jd_text_path.read_text(encoding="utf-8")
    log.info(f"Loaded JD ({len(jd_text)} chars): {jd_path}")

    # ── Agent 1: Parse JD ───────────────────────────────────────────────────
    from app.agents.jd_parser import parse_jd
    log.info("Running Agent 1: JD Parser...")
    jd_schema = await parse_jd(jd_text)
    log.info(f"Parsed: title='{jd_schema.get('title')}' | seniority={jd_schema.get('seniority')}")
    log.info(f"Required skills: {jd_schema.get('required_skills')}")

    # Save schema
    Path(out_schema).parent.mkdir(parents=True, exist_ok=True)
    with open(out_schema, "w") as f:
        json.dump(jd_schema, f, indent=2)
    log.info(f"Saved jd_schema → {out_schema}")

    # ── Embed JD ────────────────────────────────────────────────────────────
    from app.vector_store import build_candidate_text, embed_text
    # Use the same embedding approach as candidates for apples-to-apples comparison
    jd_embed_text = (
        f"{jd_schema.get('title','')} "
        f"{' '.join(jd_schema.get('required_skills',[]))} "
        f"{' '.join(jd_schema.get('nice_to_have_skills',[]))} "
        f"{jd_schema.get('domain','')}"
    ).strip()

    log.info(f"Embedding JD: '{jd_embed_text[:100]}...'")
    jd_emb = embed_text(jd_embed_text)
    jd_emb_arr = np.array(jd_emb, dtype=np.float32)

    # L2-normalize for cosine sim
    norm = np.linalg.norm(jd_emb_arr)
    if norm > 0:
        jd_emb_arr = jd_emb_arr / norm

    np.save(out_embedding, jd_emb_arr)
    log.info(f"Saved jd_embedding.npy → {out_embedding}")
    log.info("Step 4 complete. Next: python precompute/05_agent2_scout.py")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jd",            default="job_description.md")
    parser.add_argument("--out-schema",    default="artifacts/jd_schema.json")
    parser.add_argument("--out-embedding", default="artifacts/jd_embedding.npy")
    args = parser.parse_args()
    asyncio.run(main_async(args.jd, args.out_schema, args.out_embedding))


if __name__ == "__main__":
    main()
