#!/usr/bin/env python3
"""
validate_submission.py — Validate submission.csv against all hackathon spec requirements.

Usage:
    python validate_submission.py --csv ./submission.csv --candidates ./candidates.jsonl

Exits with code 0 if all checks pass, code 1 if any check fails.
"""

import argparse
import csv
import gzip
import json
import logging
import sys
from pathlib import Path
from collections import Counter

logging.basicConfig(
    format="[validate] %(levelname)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

TOP_K_FINAL        = 100
REQUIRED_COLUMNS   = ["candidate_id", "rank", "score", "reasoning"]
MAX_HONEYPOT_RATE  = 0.10


def main():
    parser = argparse.ArgumentParser(description="Validate submission.csv")
    parser.add_argument("--csv",        required=True, help="Path to submission CSV")
    parser.add_argument("--candidates", required=True, help="Path to candidates file")
    args = parser.parse_args()

    csv_path   = Path(args.csv)
    cand_path  = Path(args.candidates)

    if not csv_path.exists():
        log.error(f"CSV not found: {csv_path}")
        sys.exit(1)
    if not cand_path.exists():
        log.error(f"Candidates file not found: {cand_path}")
        sys.exit(1)

    # Load candidates
    valid_ids = _load_valid_ids(cand_path)
    log.info(f"Loaded {len(valid_ids)} valid candidate IDs")

    # Load CSV
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows   = list(reader)

    errors   = 0
    warnings = 0

    # ── 1.5 — Exactly 100 rows ────────────────────────────────────────────────
    if len(rows) == TOP_K_FINAL:
        log.info(f"✓ [1.5] Row count: {len(rows)}")
    else:
        log.error(f"✗ [1.5] Expected {TOP_K_FINAL} rows, got {len(rows)}")
        errors += 1

    # ── 1.9 — Correct column order ────────────────────────────────────────────
    actual_cols = list(rows[0].keys()) if rows else []
    if actual_cols == REQUIRED_COLUMNS:
        log.info(f"✓ [1.9] Columns: {REQUIRED_COLUMNS}")
    else:
        log.error(f"✗ [1.9] Column order wrong: {actual_cols}")
        log.error(f"         Expected: {REQUIRED_COLUMNS}")
        errors += 1

    # ── 1.6 — Ranks 1-100, no gaps, no duplicates ─────────────────────────────
    try:
        ranks = [int(r["rank"]) for r in rows]
        if sorted(ranks) == list(range(1, TOP_K_FINAL + 1)):
            log.info(f"✓ [1.6] Ranks 1–{TOP_K_FINAL}, no gaps, no duplicates")
        else:
            dups = [r for r, c in Counter(ranks).items() if c > 1]
            missing = [r for r in range(1, TOP_K_FINAL + 1) if r not in ranks]
            log.error(f"✗ [1.6] Rank sequence invalid. Duplicates: {dups[:5]}. Missing: {missing[:5]}")
            errors += 1
    except (ValueError, KeyError) as e:
        log.error(f"✗ [1.6] Rank parsing error: {e}")
        errors += 1

    # ── 1.8 — All candidate_ids valid ────────────────────────────────────────
    cand_ids = [r.get("candidate_id", "") for r in rows]
    invalid  = [cid for cid in cand_ids if cid not in valid_ids]
    dupes    = [cid for cid, cnt in Counter(cand_ids).items() if cnt > 1]
    if not invalid and not dupes:
        log.info(f"✓ [1.8] All candidate_ids valid and unique")
    else:
        if invalid:
            log.error(f"✗ [1.8] Invalid candidate_ids (not in input): {invalid[:5]}")
            errors += 1
        if dupes:
            log.error(f"✗ [1.8] Duplicate candidate_ids: {dupes[:5]}")
            errors += 1

    # ── 1.7 — Monotonically non-increasing scores ─────────────────────────────
    try:
        scores = [float(r["score"]) for r in rows]
        mono_errors = [(i+1, scores[i], scores[i+1])
                       for i in range(len(scores)-1) if scores[i] < scores[i+1]]
        if not mono_errors:
            log.info(f"✓ [1.7] Scores monotonically non-increasing")
        else:
            log.error(f"✗ [1.7] Monotonic violation at {len(mono_errors)} positions: {mono_errors[:3]}")
            errors += 1
    except (ValueError, KeyError) as e:
        log.error(f"✗ [1.7] Score parsing error: {e}")
        errors += 1

    # ── Score range sanity check ──────────────────────────────────────────────
    if scores:
        rank1_score   = scores[0]
        rank10_score  = scores[9] if len(scores) >= 10 else None
        rank50_score  = scores[49] if len(scores) >= 50 else None
        rank100_score = scores[99] if len(scores) >= 100 else None
        spread        = scores[0] - scores[-1]

        if rank1_score < 0.60:
            log.warning(f"⚠ [10.10] Rank-1 score {rank1_score:.4f} < 0.60 — top candidate appears weak")
            warnings += 1
        else:
            log.info(f"✓ [10.10] Rank-1 score: {rank1_score:.4f}")

        if rank100_score is not None and rank100_score > 0.70:
            log.warning(f"⚠ [10.10] Rank-100 score {rank100_score:.4f} > 0.70 — too many high scorers, no differentiation")
            warnings += 1

        if spread < 0.15:
            log.warning(f"⚠ [10.10] Score spread {spread:.4f} < 0.15 — insufficient differentiation")
            warnings += 1
        else:
            log.info(f"✓ [10.10] Score spread: {spread:.4f}")

    # ── Reasoning quality checks ──────────────────────────────────────────────
    empty_reasoning = [r["candidate_id"] for r in rows if not r.get("reasoning", "").strip()]
    if empty_reasoning:
        log.warning(f"⚠ [6.x] Empty reasoning for {len(empty_reasoning)} candidates: {empty_reasoning[:3]}")
        warnings += 1
    else:
        log.info(f"✓ [6.x] All reasoning entries non-empty")

    short_reasoning = [r["candidate_id"] for r in rows if len(r.get("reasoning", "")) < 50]
    if short_reasoning:
        log.warning(f"⚠ [6.1] Very short reasoning (< 50 chars) for {len(short_reasoning)} candidates")
        warnings += 1

    # ── Cross-signal consistency test ────────────────────────────────────────
    # Check top-10: scores should be meaningful (not all 0)
    top_10_scores = scores[:10]
    if all(s == 0.0 for s in top_10_scores):
        log.error(f"✗ [10.11] Top-10 candidates all have score 0.0 — scoring is broken!")
        errors += 1
    else:
        log.info(f"✓ [10.11] Top-10 scores: {[f'{s:.4f}' for s in top_10_scores[:5]]}...")

    # ── 2.8 — Honeypot rate check ────────────────────────────────────────────
    # We can't directly verify honeypot detection from CSV alone
    # but we can check if any score is exactly 0.0 (those would be honeypots)
    zero_scores = [r["candidate_id"] for r in rows if float(r.get("score", 1)) == 0.0]
    if zero_scores:
        hp_rate = len(zero_scores) / len(rows)
        if hp_rate > MAX_HONEYPOT_RATE:
            log.error(f"✗ [2.8] Honeypot rate {hp_rate:.1%} > {MAX_HONEYPOT_RATE:.0%} threshold!")
            errors += 1
        else:
            log.warning(f"⚠ [2.8] {len(zero_scores)} candidates with score=0.0 in top-100 ({hp_rate:.1%})")
    else:
        log.info(f"✓ [2.8] No zero-score candidates in top-100")

    # ── Final verdict ─────────────────────────────────────────────────────────
    log.info("\n" + "=" * 60)
    log.info(f"Errors:   {errors}")
    log.info(f"Warnings: {warnings}")
    log.info("=" * 60)

    if errors == 0:
        log.info("✓ ALL SUBMISSION CHECKS PASSED — ready to submit!")
        sys.exit(0)
    else:
        log.error(f"✗ {errors} CRITICAL ERROR(S) — fix before submitting!")
        sys.exit(1)


def _load_valid_ids(cand_path: Path) -> set[str]:
    ids = set()
    if cand_path.suffix == ".gz":
        opener = lambda: gzip.open(cand_path, "rt", encoding="utf-8")
    else:
        opener = lambda: open(cand_path, encoding="utf-8")

    with opener() as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                cid = obj.get("candidate_id") or obj.get("id") or f"cand_{i:07d}"
                ids.add(str(cid))
            except json.JSONDecodeError:
                pass
    return ids


if __name__ == "__main__":
    main()
