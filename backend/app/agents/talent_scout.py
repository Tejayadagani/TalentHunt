"""
talent_scout.py — Agent 2: Talent Scout.

Queries ChromaDB for semantically similar candidates, computes a structured
Match Score for each, and asks the LLM for a one-sentence match reason.

Public API
----------
  find_candidates(parsed_jd, top_k=10) -> list[dict]
  compute_match_score(jd, candidate, semantic_score) -> dict   (also exported for pipeline)

Each returned candidate dict contains every field from the original profile
plus the following additions:
  - match_score       : float 0–100
  - match_breakdown   : { skill_overlap, seniority_fit, semantic_similarity, location_fit }
  - match_reason      : str  (one-sentence LLM explanation)
  - cosine_distance   : float  (raw ChromaDB value, kept for debugging)
  - semantic_similarity: float 0–100
"""

import logging
import time

from app.llm_client import call_llm
from app.vector_store import query_candidates
from app.agents.jd_parser import jd_summary

log = logging.getLogger(__name__)

# ── Seniority ladder (matches candidate schema) ───────────────────────────────
SENIORITY_LADDER = ["intern", "junior", "mid", "senior", "lead", "principal"]

# ── Rate-limit guard: sleep between LLM calls ─────────────────────────────────
_LLM_INTER_CALL_SLEEP = 1.5   # seconds

# ── ChromaDB over-fetch multiplier ────────────────────────────────────────────
# We fetch more than top_k from ChromaDB so we have candidates to filter from
# before scoring. Spec says fetch 15 regardless of top_k.
_CHROMA_FETCH = 15


# ── Public: main entry point ──────────────────────────────────────────────────
def find_candidates(parsed_jd: dict, top_k: int = 10) -> list[dict]:
    """
    Find and score the top-K matching candidates for a parsed job description.

    Steps:
      1. Build a query string from the JD.
      2. Fetch top _CHROMA_FETCH candidates from ChromaDB by semantic similarity.
      3. Compute deterministic match sub-scores in Python (no LLM).
      4. Sort all fetched candidates by match_score, keep top_k.
      5. Call LLM once per candidate for a one-sentence match reason.

    Returns a list of candidate dicts sorted by match_score (descending),
    each augmented with match_score, match_breakdown, and match_reason.
    """
    log.info(f"[Agent 2] Scouting candidates for: '{parsed_jd.get('title')}'")

    # ── Step 1: Build query string ───────────────────────────────────────────
    query = _build_query_string(parsed_jd)
    log.info(f"[Agent 2] ChromaDB query: '{query[:100]}…'")

    # ── Step 2: Semantic search ──────────────────────────────────────────────
    raw_candidates = query_candidates(query, top_k=_CHROMA_FETCH)
    log.info(f"[Agent 2] Retrieved {len(raw_candidates)} candidates from ChromaDB")

    if not raw_candidates:
        log.warning("[Agent 2] No candidates found in ChromaDB. Run embed_candidates.py first.")
        return []

    # ── Step 3: Score each candidate deterministically ───────────────────────
    scored: list[dict] = []
    for candidate in raw_candidates:
        semantic_score = candidate["semantic_similarity"]   # already 0–100
        score_result   = compute_match_score(parsed_jd, candidate, semantic_score)
        candidate.update(score_result)
        scored.append(candidate)

    # ── Step 4: Sort and trim to top_k ───────────────────────────────────────
    scored.sort(key=lambda c: c["match_score"], reverse=True)
    top_candidates = scored[:top_k]

    log.info(
        f"[Agent 2] Top {len(top_candidates)} candidates by match_score: "
        + ", ".join(f"{c['name']}={c['match_score']}" for c in top_candidates)
    )

    # ── Step 5: LLM match reason (one sentence per candidate) ────────────────
    jd_sum = jd_summary(parsed_jd)
    for i, candidate in enumerate(top_candidates):
        log.info(
            f"[Agent 2] Getting match reason for candidate "
            f"{i + 1}/{len(top_candidates)}: {candidate['name']}"
        )
        candidate["match_reason"] = _get_match_reason(jd_sum, candidate)
        if i < len(top_candidates) - 1:
            time.sleep(_LLM_INTER_CALL_SLEEP)   # rate-limit guard

    log.info("[Agent 2] Talent scouting complete.")
    return top_candidates


# ── Public: scoring formula (exported for use in pipeline.py) ─────────────────
def compute_match_score(jd: dict, candidate: dict, semantic_score: float) -> dict:
    """
    Compute a structured Match Score using the exact formula from the spec.

    Match Score = skill_overlap × 0.40
               + seniority_fit × 0.20
               + semantic_similarity × 0.30
               + location_fit × 0.10

    All sub-scores are 0–100; result is 0–100.

    Returns:
        {
          "match_score":      float,
          "match_breakdown": {
              "skill_overlap":      float,
              "seniority_fit":      float,
              "semantic_similarity": float,
              "location_fit":       int (100 | 85 | 50 | 10)
          }
        }
    """
    # ── Skill overlap (×0.40) ────────────────────────────────────────────────
    required         = {s.lower() for s in jd.get("required_skills", [])}
    candidate_skills = {s.lower() for s in candidate.get("skills", [])}
    skill_overlap    = (
        len(required & candidate_skills) / max(len(required), 1)
    ) * 100

    # ── Seniority fit (×0.20) ────────────────────────────────────────────────
    jd_seniority   = (jd.get("seniority") or "mid").lower()
    cand_seniority = (candidate.get("seniority") or "mid").lower()

    jd_level   = SENIORITY_LADDER.index(jd_seniority)   if jd_seniority   in SENIORITY_LADDER else 2
    cand_level = SENIORITY_LADDER.index(cand_seniority) if cand_seniority in SENIORITY_LADDER else 2
    seniority_fit = max(0, 100 - abs(jd_level - cand_level) * 35)

    # ── Location fit (×0.10) ─────────────────────────────────────────────────
    jd_loc   = (jd.get("location")        or "").lower().strip()
    cand_loc = (candidate.get("location") or "").lower().strip()

    if jd_loc and jd_loc == cand_loc:
        location_fit = 100
    elif jd.get("remote_ok") and candidate.get("remote_ok"):
        location_fit = 85
    else:
        location_fit = 10

    # ── Combined match score ──────────────────────────────────────────────────
    match_score = (
        skill_overlap  * 0.40 +
        seniority_fit  * 0.20 +
        semantic_score * 0.30 +
        location_fit   * 0.10
    )

    return {
        "match_score": round(match_score, 1),
        "match_breakdown": {
            "skill_overlap":       round(skill_overlap, 1),
            "seniority_fit":       round(seniority_fit, 1),
            "semantic_similarity": round(semantic_score, 1),
            "location_fit":        location_fit,
        },
    }


# ── Private helpers ───────────────────────────────────────────────────────────
def _build_query_string(parsed_jd: dict) -> str:
    """
    Build the ChromaDB query string from the parsed JD.
    Spec: f"{title} {' '.join(required_skills)} {domain}"
    """
    title    = parsed_jd.get("title") or ""
    skills   = " ".join(parsed_jd.get("required_skills") or [])
    domain   = parsed_jd.get("domain") or ""
    nice     = " ".join(parsed_jd.get("nice_to_have_skills") or [])
    seniority = parsed_jd.get("seniority") or ""
    return f"{title} {seniority} {skills} {nice} {domain}".strip()


_MATCH_REASON_SYSTEM = (
    "You are a concise talent analyst. "
    "When given a job description summary and a candidate profile, "
    "you write exactly ONE sentence (max 30 words) explaining the match or mismatch. "
    "Mention the strongest matching skill and any notable gap. "
    "Return only the sentence — no labels, no JSON, no bullet points."
)

def _get_match_reason(jd_sum: str, candidate: dict) -> str:
    """Call the LLM for a one-sentence match/mismatch reason."""
    cand_summary = (
        f"{candidate['name']}: {candidate['current_title']} at {candidate['current_company']}. "
        f"Skills: {', '.join(candidate.get('skills', []))}. "
        f"Seniority: {candidate.get('seniority')} ({candidate.get('years_of_experience')} yrs). "
        f"Location: {candidate.get('location')} (remote_ok={candidate.get('remote_ok')})."
    )

    user_prompt = (
        f"Job description summary:\n{jd_sum}\n\n"
        f"Candidate profile:\n{cand_summary}\n\n"
        "Write exactly ONE sentence explaining why this candidate does or does not match."
    )

    try:
        reason = call_llm(_MATCH_REASON_SYSTEM, user_prompt)
        # Trim to a single sentence if the LLM goes over
        sentences = reason.replace("\n", " ").split(".")
        first = sentences[0].strip()
        return first + "." if first and not first.endswith(".") else first or reason
    except Exception as exc:
        log.warning(f"[Agent 2] match_reason LLM call failed: {exc}")
        return "Match reason unavailable."


# ── Quick demo (python -m app.agents.talent_scout) ────────────────────────────
if __name__ == "__main__":
    import json, sys

    # Simulate a parsed JD (as Agent 1 would produce)
    SAMPLE_JD = {
        "title": "Senior Backend Engineer",
        "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
        "nice_to_have_skills": ["Kubernetes", "Redis"],
        "seniority": "senior",
        "domain": "fintech",
        "location": "Bangalore",
        "remote_ok": True,
        "salary_range": {"min": 2000000, "max": 3500000, "currency": "INR"},
        "must_haves": ["5+ years experience"],
    }

    print("=== TalentRadar — Agent 2: Talent Scout demo ===\n")
    print(f"JD: {SAMPLE_JD['title']} | {SAMPLE_JD['domain']} | {SAMPLE_JD['location']}")
    print(f"Required skills: {SAMPLE_JD['required_skills']}\n")

    try:
        results = find_candidates(SAMPLE_JD, top_k=5)

        print(f"Top {len(results)} candidates:\n")
        for i, c in enumerate(results, 1):
            print(
                f"  {i}. {c['name']:<22} "
                f"match={c['match_score']:<6} "
                f"skill={c['match_breakdown']['skill_overlap']:<6} "
                f"seniority={c['match_breakdown']['seniority_fit']:<6} "
                f"semantic={c['match_breakdown']['semantic_similarity']:<6} "
                f"location={c['match_breakdown']['location_fit']}"
            )
            print(f"     Reason: {c.get('match_reason', 'N/A')}\n")

        print("✓ Agent 2 smoke test passed!")
    except Exception as e:
        print(f"\n✗ Failed: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)
