"""
07_agent5_scorer.py — Step 7: Score all interview transcripts with Agent 5.

Loads transcripts from artifacts/interviews/, runs Agent 5 scorer,
saves individual score JSON files to artifacts/scores/.

Usage:
    cd backend
    python precompute/07_agent5_scorer.py
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from config import INTERVIEWS_DIR, SCORES_DIR

logging.basicConfig(
    format="[07_scorer] %(levelname)s %(message)s", level=logging.INFO
)
log = logging.getLogger(__name__)

_CONCURRENCY = 1   # simultaneous scoring calls — sequential to avoid rate limits


async def score_one(
    semaphore: asyncio.Semaphore,
    interview_path: Path,
    jd_schema: dict,
    out_dir: Path,
    idx: int,
    total: int,
) -> None:
    """Run Agent 5 on a single transcript file."""
    cid      = interview_path.stem
    out_path = out_dir / f"{cid}.json"

    if out_path.exists():
        log.info(f"[{idx}/{total}] Skip {cid} — already scored.")
        return

    async with semaphore:
        with open(interview_path) as f:
            interview = json.load(f)

        transcript = interview.get("transcript", [])
        candidate  = {"name": interview.get("name", cid)}
        log.info(f"[{idx}/{total}] Scoring {interview.get('name', cid)} ({len(transcript)} messages)")

        try:
            from app.agents.scorer import score_conversation
            result = await score_conversation(transcript, jd_schema, candidate)
            result["candidate_id"] = cid
            result["name"]         = interview.get("name", cid)

            with open(out_path, "w") as f:
                json.dump(result, f, indent=2)
            log.info(f"[{idx}/{total}] Saved → {out_path.name}  interview_score={result['interview_score']:.4f}")

        except Exception as exc:
            log.error(f"[{idx}/{total}] Scoring failed for {cid}: {exc}")
            # Save neutral score so downstream doesn't break
            from app.agents.scorer import _neutral_score
            neutral = _neutral_score(f"Scoring failed: {exc}")
            neutral["candidate_id"] = cid
            neutral["name"]         = interview.get("name", cid)
            neutral["error"]        = str(exc)
            with open(out_path, "w") as f:
                json.dump(neutral, f, indent=2)


async def main_async(interviews_dir: str, jd_schema_path: str, out_dir_str: str):
    with open(jd_schema_path) as f:
        jd_schema = json.load(f)

    interviews_path = Path(interviews_dir)
    transcript_files = sorted(interviews_path.glob("*.json"))
    total = len(transcript_files)
    log.info(f"Found {total} interview transcripts to score.")

    if total == 0:
        log.warning("No transcripts found! Run 06_agents34_interview.py first.")
        return

    out_dir = Path(out_dir_str)
    out_dir.mkdir(parents=True, exist_ok=True)

    semaphore = asyncio.Semaphore(_CONCURRENCY)
    start     = time.time()

    tasks = [
        score_one(semaphore, fp, jd_schema, out_dir, i + 1, total)
        for i, fp in enumerate(transcript_files)
    ]
    await asyncio.gather(*tasks)

    elapsed   = time.time() - start
    completed = sum(1 for fp in transcript_files if (out_dir / fp.name).exists())
    log.info(f"Scoring complete: {completed}/{total} in {elapsed:.1f}s.")
    log.info("Step 7 complete. Next: python precompute/08_combine.py")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--interviews-dir", default="artifacts/interviews")
    parser.add_argument("--jd-schema",      default="artifacts/jd_schema.json")
    parser.add_argument("--out-dir",        default="artifacts/scores")
    args = parser.parse_args()
    asyncio.run(main_async(args.interviews_dir, args.jd_schema, args.out_dir))


if __name__ == "__main__":
    main()
