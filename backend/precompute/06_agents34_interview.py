"""
06_agents34_interview.py — Step 6: Run interview simulation for top-40.

Calls Agents 3+4 (conversation simulator) for each top-40 candidate.
Uses the LLM fallback carousel to handle rate limits.
Saves transcripts to artifacts/interviews/<candidate_id>.json.

Usage:
    cd backend
    python precompute/06_agents34_interview.py
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

from config import TOP_K_INTERVIEW, INTERVIEWS_DIR

logging.basicConfig(
    format="[06_interview] %(levelname)s %(message)s", level=logging.INFO
)
log = logging.getLogger(__name__)

_CONCURRENCY = 1   # simultaneous interview calls — rate-limit aware
_TURNS       = 6   # 6 turns per interview (spec requirement)


async def interview_candidate(
    semaphore: asyncio.Semaphore,
    candidate: dict,
    jd_schema: dict,
    out_dir: Path,
    full_candidates: dict,
    idx: int,
    total: int,
) -> None:
    """Run a single candidate's interview simulation."""
    cid  = candidate["candidate_id"]
    name = candidate.get("name", cid)

    # Check if already done (allows resume)
    out_path = out_dir / f"{cid}.json"
    if out_path.exists():
        log.info(f"[{idx}/{total}] Skip {name} — already interviewed.")
        return

    async with semaphore:
        log.info(f"[{idx}/{total}] Interviewing: {name} ({cid})")

        # Get full profile with private fields (interest_level, salary expectation etc.)
        full_profile = full_candidates.get(cid, candidate)

        try:
            from app.agents.conversation_sim import simulate_conversation
            transcript = await simulate_conversation(jd_schema, full_profile, turns=_TURNS)

            result = {
                "candidate_id": cid,
                "name":         name,
                "turns":        _TURNS,
                "transcript":   transcript,
            }
            with open(out_path, "w") as f:
                json.dump(result, f, indent=2)
            log.info(f"[{idx}/{total}] Saved interview for {name} → {out_path.name}")

        except Exception as exc:
            log.error(f"[{idx}/{total}] Interview failed for {name}: {exc}")
            # Save an empty transcript so downstream steps don't crash
            with open(out_path, "w") as f:
                json.dump({
                    "candidate_id": cid,
                    "name":         name,
                    "turns":        0,
                    "transcript":   [],
                    "error":        str(exc),
                }, f, indent=2)


async def main_async(
    scout_results_path: str,
    candidates_path: str,
    jd_schema_path: str,
    out_dir_str: str,
):
    # ── Load artifacts ───────────────────────────────────────────────────────
    with open(scout_results_path) as f:
        scout = json.load(f)
    with open(jd_schema_path) as f:
        jd_schema = json.load(f)

    top_candidates = scout["top_interview"]
    log.info(f"Loaded {len(top_candidates)} candidates for interview simulation.")

    # Load full candidate profiles for private data (interest_level, salary, etc.)
    from precompute.utils import load_candidates, normalize_candidate
    all_candidates = [normalize_candidate(c) for c in load_candidates(candidates_path)]
    cand_by_id = {c["candidate_id"]: c for c in all_candidates}

    out_dir = Path(out_dir_str)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Run interviews concurrently ───────────────────────────────────────────
    semaphore = asyncio.Semaphore(_CONCURRENCY)
    total     = len(top_candidates)
    start     = time.time()

    tasks = [
        interview_candidate(semaphore, cand, jd_schema, out_dir, cand_by_id, i + 1, total)
        for i, cand in enumerate(top_candidates)
    ]
    await asyncio.gather(*tasks)

    elapsed = time.time() - start
    completed = sum(1 for cand in top_candidates if (out_dir / f"{cand['candidate_id']}.json").exists())
    log.info(f"Interview simulation complete: {completed}/{total} candidates in {elapsed:.1f}s.")
    log.info("Step 6 complete. Next: python precompute/07_agent5_scorer.py")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scout-results", default="artifacts/scout_results.json")
    parser.add_argument("--candidates",    default="data/candidates.json")
    parser.add_argument("--jd-schema",     default="artifacts/jd_schema.json")
    parser.add_argument("--out-dir",       default="artifacts/interviews")
    args = parser.parse_args()
    asyncio.run(main_async(args.scout_results, args.candidates, args.jd_schema, args.out_dir))


if __name__ == "__main__":
    main()
