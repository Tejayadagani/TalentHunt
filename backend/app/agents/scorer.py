"""
scorer.py — Agent 5: Technical Interview Scorer & Explainer.

Reads the full conversation transcript produced by Agents 3 & 4 and
evaluates the candidate's technical performance across 5 dimensions.

Public API
----------
  async def score_conversation(transcript, parsed_jd, candidate) -> dict

Output schema
-------------
{
  "interview_score": float,        # 0.0–1.0, weighted average of 5 dimensions
  "breakdown": {
    "technical_depth":    float,   # 0–10 (weight 0.30)
    "production_mindset": float,   # 0–10 (weight 0.25)
    "domain_relevance":   float,   # 0–10 (weight 0.20)
    "communication":      float,   # 0–10 (weight 0.15)
    "motivation_signal":  float    # 0–10 (weight 0.10)
  },
  "reasoning": str                 # 2-3 sentence recruiter-facing explanation
                                   # citing specific transcript evidence
}

Privacy note
------------
  `interest_level` from the candidate profile is intentionally NOT passed
  to this agent — the scorer must infer everything purely from the transcript.

Dimension definitions
---------------------
  technical_depth (×0.30):
    Does the candidate demonstrate genuine technical depth?
    Specific algorithms, architectures, trade-offs, numbers, constraints.

  production_mindset (×0.25):
    Does the candidate think about scale, reliability, monitoring, cost?
    Mentions of SLAs, oncall, incident response, performance tuning.

  domain_relevance (×0.20):
    Does their experience align with the JD domain (fintech/AI/SaaS)?
    Named companies, products, or standards relevant to the domain.

  communication_clarity (×0.15):
    Are explanations clear, structured, and concise?
    Avoids filler, explains reasoning, directly answers questions.

  motivation_signal (×0.10):
    Does the candidate show genuine interest in THIS role and company?
    Specific questions about the team, tech, growth — not generic.
"""

import logging

from app.llm_client import call_llm, parse_json_response, heal_json
from app.agents.jd_parser import jd_summary

log = logging.getLogger(__name__)

# ── Dimension weights (must sum to 1.0) ───────────────────────────────────────
DIMENSION_WEIGHTS = {
    "technical_depth":    0.30,
    "production_mindset": 0.25,
    "domain_relevance":   0.20,
    "communication":      0.15,
    "motivation_signal":  0.10,
}   # sum = 1.00

# Each dimension is scored 0–10 by the LLM, then normalized to 0–1 before fusion
_MAX_DIM_SCORE = 10


# ─────────────────────────────────────────────────────────────────────────────
# System prompt builder
# ─────────────────────────────────────────────────────────────────────────────
def _build_system_prompt(parsed_jd: dict, candidate_name: str) -> str:
    """Build the Agent 5 system prompt with JD context injected."""
    jd_sum    = jd_summary(parsed_jd)
    title     = parsed_jd.get("title", "the role")
    domain    = parsed_jd.get("domain", "tech")
    skills    = ", ".join(parsed_jd.get("required_skills", []))

    return f"""You are a senior technical interviewer evaluating a candidate for a {title} role.

Job context: {jd_sum}
Candidate name: {candidate_name}

Read the conversation transcript below and score the candidate on EXACTLY these 5 dimensions.
Score each dimension from 0 to 10 based ONLY on what is said in the transcript.

DIMENSIONS (score 0–10 each):

1. technical_depth (weight 30%):
   Does the candidate demonstrate genuine technical depth?
   HIGH score: specific algorithms, data structures, architectures, trade-offs, exact numbers,
   system constraints, performance characteristics.
   LOW score: vague answers ("I've worked with it"), buzzwords without substance.
   Required skills for this role: {skills}

2. production_mindset (weight 25%):
   Does the candidate think about production systems?
   HIGH score: mentions scale, reliability, monitoring, cost optimization, SLAs, incident response,
   CI/CD, testing, rollback strategies.
   LOW score: focuses only on feature development, no mention of operations or reliability.

3. domain_relevance (weight 20%):
   Does the candidate's experience align with the {domain} domain?
   HIGH score: names companies, products, standards, or regulations relevant to {domain}.
   LOW score: generic tech experience with no domain fit signals.

4. communication (weight 15%):
   Are explanations clear, structured, and concise?
   HIGH score: direct answers, clear structure, explains reasoning, no filler.
   LOW score: rambling, evasive, over-qualifies every statement.

5. motivation_signal (weight 10%):
   Does the candidate show genuine interest in THIS specific role?
   HIGH score: asks specific questions about the team's tech, roadmap, or challenges.
   LOW score: no questions, generic interest, mentions other competing offers.

SCORING RULES:
- Score ONLY based on the transcript — never assume knowledge not demonstrated.
- If a dimension is not testable from this transcript (e.g. no technical questions were asked),
  award 5/10 (neutral).
- Do NOT reward salary alignment or notice period availability — those are irrelevant here.

Return ONLY valid JSON in this EXACT format with no markdown, no extra keys:
{{
  "technical_depth":    <integer 0-10>,
  "production_mindset": <integer 0-10>,
  "domain_relevance":   <integer 0-10>,
  "communication":      <integer 0-10>,
  "motivation_signal":  <integer 0-10>,
  "reasoning": "<2-3 sentences for a recruiter. Cite specific things the candidate said.
   Mention at least 2 factual claims from the transcript. Acknowledge any concern if one exists.>"
}}"""


# ─────────────────────────────────────────────────────────────────────────────
# Public function
# ─────────────────────────────────────────────────────────────────────────────
async def score_conversation(
    transcript: list[dict],
    parsed_jd: dict,
    candidate: dict,
) -> dict:
    """
    Analyse a conversation transcript and return a structured Interview Score.

    Returns:
        {
          "interview_score": float,      # 0.0–1.0
          "breakdown": {
            "technical_depth": float,    # 0.0–1.0 (raw/10)
            "production_mindset": float,
            "domain_relevance": float,
            "communication": float,
            "motivation_signal": float,
          },
          "reasoning": str              # evidence-citing recruiter summary
        }
    """
    candidate_name = candidate.get("name", "the candidate")
    log.info(f"[Agent 5] Scoring conversation for {candidate_name} …")

    if not transcript:
        log.warning(f"[Agent 5] Empty transcript for {candidate_name} — returning neutral score.")
        return _neutral_score("No conversation transcript was available to evaluate.")

    # ── Format transcript for the LLM ────────────────────────────────────────
    transcript_text = _format_transcript(transcript)
    system_prompt   = _build_system_prompt(parsed_jd, candidate_name)
    user_prompt     = (
        f"Here is the full conversation transcript:\n\n"
        f"{transcript_text}\n\n"
        f"Now evaluate {candidate_name} on the 5 dimensions and return the JSON score."
    )

    # ── Call LLM ─────────────────────────────────────────────────────────────
    raw_response = await call_llm(system_prompt, user_prompt, agent_id=5)
    log.info(f"[Agent 5] Raw response received — parsing JSON …")

    # ── Parse and validate ────────────────────────────────────────────────────
    try:
        parsed = parse_json_response(raw_response)
    except Exception as e:
        log.warning(f"[Agent 5] JSON parse failed, attempting heal: {e}")
        try:
            parsed = heal_json(raw_response)
        except Exception as heal_err:
            log.error(f"[Agent 5] JSON healing failed for {candidate_name}: {heal_err}")
            return _neutral_score(f"Scoring failed due to JSON parse error for {candidate_name}.")

    result = _validate_and_normalize(parsed, candidate_name)

    log.info(
        f"[Agent 5] Scored {candidate_name}: "
        f"interview_score={result['interview_score']:.3f}  "
        f"breakdown={result['breakdown']}"
    )
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────
def _format_transcript(transcript: list[dict]) -> str:
    """Render the transcript as a clean dialogue string for the LLM."""
    lines = []
    for entry in transcript:
        role    = entry.get("role", "unknown").upper()
        turn    = entry.get("turn", "?")
        message = entry.get("message", "").strip()
        lines.append(f"[Turn {turn}] {role}: {message}")
    return "\n\n".join(lines)


def _validate_and_normalize(data: dict, candidate_name: str) -> dict:
    """
    Clamp each dimension to 0–10, compute weighted interview_score (0.0–1.0).
    Always recomputes from parts — never trusts a pre-computed sum.
    """
    def safe_int(v, default=5):
        try:
            return max(0, min(_MAX_DIM_SCORE, int(float(v))))
        except (TypeError, ValueError):
            return default

    td  = safe_int(data.get("technical_depth",    5))
    pm  = safe_int(data.get("production_mindset", 5))
    dr  = safe_int(data.get("domain_relevance",   5))
    cc  = safe_int(data.get("communication",      5))
    ms  = safe_int(data.get("motivation_signal",  5))

    # Weighted average; divide by 10 to normalize each dimension 0→1
    interview_score = (
        (td / 10) * DIMENSION_WEIGHTS["technical_depth"]    +
        (pm / 10) * DIMENSION_WEIGHTS["production_mindset"] +
        (dr / 10) * DIMENSION_WEIGHTS["domain_relevance"]   +
        (cc / 10) * DIMENSION_WEIGHTS["communication"]      +
        (ms / 10) * DIMENSION_WEIGHTS["motivation_signal"]
    )
    interview_score = max(0.0, min(1.0, interview_score))   # clamp to [0, 1]

    reasoning = str(data.get("reasoning", "")).strip()
    if not reasoning:
        reasoning = (
            f"{candidate_name} completed the interview. "
            f"Technical depth score: {td}/10. Production mindset: {pm}/10."
        )

    return {
        "interview_score": round(interview_score, 4),
        "breakdown": {
            "technical_depth":    round(td / 10, 2),
            "production_mindset": round(pm / 10, 2),
            "domain_relevance":   round(dr / 10, 2),
            "communication":      round(cc / 10, 2),
            "motivation_signal":  round(ms / 10, 2),
        },
        "reasoning": reasoning,
    }


def _neutral_score(reasoning: str) -> dict:
    """Return a neutral 5/10 score for all dimensions when transcript unavailable."""
    return {
        "interview_score": round(
            sum(DIMENSION_WEIGHTS.values()) * 0.5, 4
        ),   # 0.50
        "breakdown": {
            "technical_depth":    0.5,
            "production_mindset": 0.5,
            "domain_relevance":   0.5,
            "communication":      0.5,
            "motivation_signal":  0.5,
        },
        "reasoning": reasoning,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Quick demo  (python -m app.agents.scorer)
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json, sys, asyncio

    HIGH_TRANSCRIPT = [
        {"role": "recruiter", "turn": 1, "message": "Tell me about a system you built at scale."},
        {"role": "candidate", "turn": 1, "message":
            "At Zepto I designed a payment routing system handling 50K TPS using async FastAPI + PostgreSQL "
            "with read replicas. We had P99 < 80ms and zero downtime deploys via blue-green on ECS. "
            "I implemented circuit breakers using tenacity to handle Razorpay gateway timeouts."},
        {"role": "recruiter", "turn": 2, "message": "How did you handle reliability?"},
        {"role": "candidate", "turn": 2, "message":
            "We ran 3 replicas with Kubernetes liveness probes and PagerDuty alerting on p99 spikes. "
            "We also had a chaos engineering day monthly using Gremlin to test failure modes. "
            "SLA was 99.95% uptime — we hit it for 18 months straight."},
        {"role": "recruiter", "turn": 3, "message": "What draws you to fintech specifically?"},
        {"role": "candidate", "turn": 3, "message":
            "Fintech is where reliability really matters — a missed payment affects real people. "
            "I want to understand more about your compliance stack. Are you PCI-DSS Level 1? "
            "And what does your on-call rotation look like?"},
    ]

    SAMPLE_JD = {
        "title": "Senior Backend Engineer",
        "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
        "seniority": "senior",
        "domain": "fintech",
        "location": "Bangalore",
        "remote_ok": True,
        "salary_range": {"min": 2000000, "max": 3500000, "currency": "INR"},
    }

    print("=== SkillSync AI — Agent 5: Technical Scorer demo ===\n")

    try:
        result = asyncio.run(score_conversation(
            HIGH_TRANSCRIPT, SAMPLE_JD, {"name": "Arjun Mehta"}
        ))
        print(json.dumps(result, indent=2))

        assert 0.0 <= result["interview_score"] <= 1.0, "interview_score out of range!"
        assert len(result["breakdown"]) == 5, "Expected 5 breakdown dimensions!"
        assert all(k in result["breakdown"] for k in DIMENSION_WEIGHTS), "Missing dimension keys!"
        print(f"\n✓ interview_score={result['interview_score']}  reasoning='{result['reasoning'][:80]}...'")
        print("✓ All assertions passed!")

    except Exception as e:
        print(f"\n✗ Failed: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)
