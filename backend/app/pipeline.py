"""
pipeline.py — TalentRadar Pipeline Orchestrator.

Chains all 5 agents in sequence:
  Agent 1  → parse_jd()              : JD text → structured JSON
  Agent 2  → find_candidates()       : JD JSON → top-K candidates + Match Scores
  Agents 3+4 → simulate_conversation(): per candidate → 6-turn transcript
  Agent 5  → score_conversation()    : transcript → Interest Score + explanation
  Pipeline → rank + combine scores   : produce final ranked shortlist

Public API
----------
  run_pipeline(jd_text, top_k=5, match_weight=0.6) -> dict
  compute_combined_score(match_score, interest_score, match_weight=0.6) -> float

Rate limiting
-------------
  Gemini free tier: 15 req/min, 1500 req/day.
  Per candidate: ~1 (match reason) + 12 (conversation) + 1 (scoring) = ~14 LLM calls.
  Pipeline sleeps INTER_CANDIDATE_SLEEP seconds between candidates.
  With top_k=5 and 14 calls/candidate: ~70 calls total — within daily limit.

Privacy
-------
  'interest_level' is stripped from all output dicts before returning.
"""

import logging
import time
from typing import Optional

from app.agents.jd_parser        import parse_jd
from app.agents.talent_scout     import find_candidates
from app.agents.conversation_sim import simulate_conversation
from app.agents.scorer           import score_conversation

log = logging.getLogger(__name__)

# ── Rate-limit guard between candidates ───────────────────────────────────────
# Conversation sim already sleeps 2s/turn internally.
# This additional pause separates back-to-back candidate pipelines.
INTER_CANDIDATE_SLEEP = 3   # seconds

# Fields from the candidate profile that must never appear in the API response
_PRIVATE_FIELDS = {"interest_level"}


# ─────────────────────────────────────────────────────────────────────────────
# Combined score formula (spec §SCORING FORMULAS)
# ─────────────────────────────────────────────────────────────────────────────
def compute_combined_score(
    match_score: float,
    interest_score: float,
    match_weight: float = 0.6,
) -> float:
    """
    Combine Match Score and Interest Score into a single ranking number.

    Combined Score = (match_score × match_weight)
                   + (interest_score × (1 − match_weight))

    Default weights: Match 60% / Interest 40% (recruiter-adjustable via sliders).

    Args:
        match_score:    0–100, from Agent 2 (talent_scout).
        interest_score: 0–100, from Agent 5 (scorer).
        match_weight:   0.0–1.0, defaults to 0.6 per spec.

    Returns:
        Float rounded to 1 decimal place.
    """
    match_weight    = max(0.0, min(1.0, match_weight))  # clamp to [0, 1]
    interest_weight = 1.0 - match_weight
    return round(match_score * match_weight + interest_score * interest_weight, 1)


# ─────────────────────────────────────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────────────────────────────────────
def run_pipeline(
    jd_text: str,
    top_k: int = 5,
    match_weight: float = 0.6,
    conversation_turns: int = 6,
) -> dict:
    """
    Run the full TalentRadar pipeline for a given job description.

    Args:
        jd_text:           Raw job description text (min 50 chars).
        top_k:             Number of candidates to evaluate end-to-end (default 5).
        match_weight:      Weight for Match Score in combined ranking (default 0.6).
        conversation_turns: Number of recruiter↔candidate turns (default 6).

    Returns:
        {
          "job_title":                  str,
          "parsed_jd":                  dict,
          "total_candidates_evaluated": int,
          "shortlist": [
            {
              "rank":                   int,
              "candidate_id":           str,
              "name":                   str,
              "current_title":          str,
              "current_company":        str,
              "seniority":              str,
              "years_of_experience":    int,
              "location":               str,
              "remote_ok":              bool,
              "skills":                 list[str],
              "match_score":            float,
              "match_breakdown":        dict,
              "match_reason":           str,
              "interest_score":         int,
              "interest_breakdown":     dict,
              "combined_score":         float,
              "explanation":            str,
              "conversation_transcript": list[dict]
            },
            ...
          ],
          "weights": { "match": float, "interest": float },
          "errors":  list[str]    # per-candidate errors, empty if all succeeded
        }

    Raises:
        ValueError: if jd_text is too short.
        Exception:  if Agent 1 (JD parsing) fails — pipeline cannot continue.
    """
    pipeline_start = time.time()
    errors: list[str] = []

    # ── Step 1: Parse the JD (Agent 1) ───────────────────────────────────────
    log.info("=" * 60)
    log.info("[Pipeline] Step 1/3 — Parsing job description …")
    parsed_jd = parse_jd(jd_text)   # raises ValueError if JD is too short
    log.info(
        f"[Pipeline] JD parsed: title='{parsed_jd.get('title')}' "
        f"seniority={parsed_jd.get('seniority')} "
        f"required_skills={parsed_jd.get('required_skills')}"
    )

    # ── Step 2: Find candidates (Agent 2) ─────────────────────────────────────
    log.info(f"[Pipeline] Step 2/3 — Scouting top {top_k} candidates …")
    candidates = find_candidates(parsed_jd, top_k=top_k)

    if not candidates:
        log.warning("[Pipeline] No candidates found. Returning empty shortlist.")
        return _empty_result(parsed_jd, match_weight)

    log.info(f"[Pipeline] {len(candidates)} candidates retrieved from ChromaDB.")

    # ── Steps 3+4+5: Per-candidate conversation + scoring ────────────────────
    log.info(f"[Pipeline] Step 3/3 — Running conversation + scoring for each candidate …")
    results: list[dict] = []

    for idx, candidate in enumerate(candidates, start=1):
        name = candidate.get("name", f"Candidate {idx}")
        log.info(f"[Pipeline] ── Candidate {idx}/{len(candidates)}: {name} ──")

        try:
            # Agent 3 + 4: Conversation simulation
            log.info(f"[Pipeline] Simulating conversation for {name} …")
            transcript = simulate_conversation(
                parsed_jd, candidate, turns=conversation_turns
            )

            # Agent 5: Score the transcript
            log.info(f"[Pipeline] Scoring conversation for {name} …")
            score_result = score_conversation(transcript, parsed_jd, candidate)

            # Combine scores
            combined = compute_combined_score(
                match_score    = candidate["match_score"],
                interest_score = score_result["interest_score"],
                match_weight   = match_weight,
            )

            # Build result dict — strip private fields
            result = {
                **_public_candidate(candidate),
                "interest_score":          score_result["interest_score"],
                "interest_breakdown":      score_result["breakdown"],
                "combined_score":          combined,
                "explanation":             score_result["explanation"],
                "conversation_transcript": transcript,
            }
            results.append(result)

            log.info(
                f"[Pipeline] {name} → match={candidate['match_score']} "
                f"interest={score_result['interest_score']} combined={combined}"
            )

        except Exception as exc:
            # Don't let one candidate failure abort the whole pipeline
            log.error(f"[Pipeline] Error processing {name}: {exc}", exc_info=True)
            errors.append(f"{name}: {exc}")

        # Rate-limit guard between candidates (skip after last one)
        if idx < len(candidates):
            log.info(f"[Pipeline] Sleeping {INTER_CANDIDATE_SLEEP}s before next candidate …")
            time.sleep(INTER_CANDIDATE_SLEEP)

    # ── Sort by combined score and assign ranks ────────────────────────────────
    results.sort(key=lambda x: x["combined_score"], reverse=True)
    for rank, result in enumerate(results, start=1):
        result["rank"] = rank

    elapsed = round(time.time() - pipeline_start, 1)
    log.info(
        f"[Pipeline] Complete — {len(results)}/{len(candidates)} candidates scored "
        f"in {elapsed}s.  Errors: {len(errors)}"
    )
    log.info("=" * 60)

    return {
        "job_title":                  parsed_jd.get("title"),
        "parsed_jd":                  parsed_jd,
        "total_candidates_evaluated": len(candidates),
        "shortlist":                  results,
        "weights": {
            "match":    round(match_weight, 2),
            "interest": round(1.0 - match_weight, 2),
        },
        "errors": errors,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────
def _public_candidate(candidate: dict) -> dict:
    """
    Return a copy of the candidate dict with all private fields removed.
    Ensures interest_level (and any future private fields) never leak into output.
    """
    return {k: v for k, v in candidate.items() if k not in _PRIVATE_FIELDS}


def _empty_result(parsed_jd: dict, match_weight: float) -> dict:
    """Return a well-formed empty result when no candidates are found."""
    return {
        "job_title":                  parsed_jd.get("title"),
        "parsed_jd":                  parsed_jd,
        "total_candidates_evaluated": 0,
        "shortlist":                  [],
        "weights": {
            "match":    round(match_weight, 2),
            "interest": round(1.0 - match_weight, 2),
        },
        "errors": ["No candidates found in ChromaDB. Run embed_candidates.py first."],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Re-ranking helper (called by the frontend slider — no LLM calls)
# ─────────────────────────────────────────────────────────────────────────────
def rerank(shortlist: list[dict], match_weight: float) -> list[dict]:
    """
    Re-rank an existing shortlist using new match/interest weights.
    Called by the frontend slider — pure Python, zero LLM calls.

    Args:
        shortlist:    The 'shortlist' list from a previous run_pipeline() result.
        match_weight: New weight for match_score (0.0–1.0).

    Returns:
        A new list with updated combined_score and rank, sorted descending.
    """
    updated = []
    for item in shortlist:
        new_combined = compute_combined_score(
            match_score    = item["match_score"],
            interest_score = item["interest_score"],
            match_weight   = match_weight,
        )
        updated.append({**item, "combined_score": new_combined})

    updated.sort(key=lambda x: x["combined_score"], reverse=True)
    for rank, item in enumerate(updated, start=1):
        item["rank"] = rank

    return updated


# ─────────────────────────────────────────────────────────────────────────────
# Quick demo  (python -m app.pipeline)
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json, sys

    SAMPLE_JD = """
    We are hiring a Senior Backend Engineer to join our payments infrastructure
    team in Bangalore. The ideal candidate has 5+ years of experience with Python,
    PostgreSQL, and Docker. Experience with FastAPI or Django is required.
    Kubernetes is a plus. This is a hybrid role — 3 days in office, 2 days remote.
    Compensation: ₹20L–₹35L per annum depending on experience.
    We need someone who can start within 45 days.
    Must have: experience with financial APIs, strong SQL skills.
    """

    print("=== TalentRadar — Full Pipeline demo (top_k=2 for speed) ===\n")

    try:
        result = run_pipeline(SAMPLE_JD, top_k=2, conversation_turns=4)

        print(f"\nJob Title : {result['job_title']}")
        print(f"Candidates: {result['total_candidates_evaluated']}")
        print(f"Weights   : match={result['weights']['match']}  interest={result['weights']['interest']}")
        if result["errors"]:
            print(f"Errors    : {result['errors']}")

        print("\n── Shortlist ──")
        for c in result["shortlist"]:
            print(
                f"\n  #{c['rank']} {c['name']:<22} "
                f"combined={c['combined_score']:<6} "
                f"match={c['match_score']:<6} "
                f"interest={c['interest_score']}"
            )
            print(f"      Explanation: {c['explanation'][:120]}")

        # Verify interest_level is stripped
        for c in result["shortlist"]:
            assert "interest_level" not in c, "PRIVACY VIOLATION: interest_level in output!"
        print("\n✓ Privacy check passed — interest_level not in any output candidate.")

        # Test re-ranking
        print("\n── Re-rank with match_weight=0.3 (interest-heavy) ──")
        reranked = rerank(result["shortlist"], match_weight=0.3)
        for c in reranked:
            print(f"  #{c['rank']} {c['name']:<22} combined={c['combined_score']}")

        print("\n✓ Pipeline demo complete!")

    except Exception as e:
        print(f"\n✗ Failed: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)
