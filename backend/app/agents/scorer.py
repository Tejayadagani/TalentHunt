"""
scorer.py — Agent 5: Scorer & Explainer.

Reads the full conversation transcript produced by Agents 3 & 4 and derives
an Interest Score from what the candidate *revealed* in conversation —
not from their private profile data.

Public API
----------
  async def score_conversation(transcript, parsed_jd, candidate) -> dict

Output schema
-------------
{
  "interest_score": int,          # 0–100, sum of all four breakdown dims
  "breakdown": {
    "enthusiasm":          int,   # 0–30
    "proactive_questions": int,   # 0–25
    "salary_alignment":    int,   # 0–25
    "availability":        int    # 0–20
  },
  "explanation": str              # 2–3 sentences for a recruiter
}

Privacy note
------------
  `interest_level` from the candidate profile is intentionally NOT passed
  to this agent — the scorer must infer interest purely from the transcript.
"""

import logging

from app.llm_client import call_llm, parse_json_response
from app.agents.jd_parser import jd_summary

log = logging.getLogger(__name__)

# ── Score dimension bounds (must sum to 100) ──────────────────────────────────
_MAX_ENTHUSIASM     = 30
_MAX_PROACTIVE      = 25
_MAX_SALARY         = 25
_MAX_AVAILABILITY   = 20
_MAX_INTEREST_SCORE = _MAX_ENTHUSIASM + _MAX_PROACTIVE + _MAX_SALARY + _MAX_AVAILABILITY  # 100


# ─────────────────────────────────────────────────────────────────────────────
# System prompt builder
# ─────────────────────────────────────────────────────────────────────────────
def _build_system_prompt(parsed_jd: dict, candidate_name: str) -> str:
    """Build the Agent 5 system prompt with JD salary context injected."""
    jd_sum = jd_summary(parsed_jd)

    salary_range = parsed_jd.get("salary_range")
    if salary_range:
        sal_min  = salary_range.get("min", 0)
        sal_max  = salary_range.get("max", 0)
        currency = salary_range.get("currency", "INR")
        salary_context = (
            f"The JD salary range is {currency} {sal_min:,}–{sal_max:,}. "
            f"Score salary_alignment based on how close the candidate's stated "
            f"expectation is to this range. Full marks if within range, "
            f"partial if slightly outside, 0 if far outside or not discussed."
        )
    else:
        salary_context = (
            "No salary range was specified in the JD. "
            "Award full salary_alignment marks (25) if the candidate mentioned "
            "a reasonable expectation, or 12 if they did not discuss salary at all."
        )

    return f"""You are an expert talent evaluator. Read the conversation transcript below between a recruiter and a candidate, then produce a structured Interest Score.

Job context: {jd_sum}
Candidate name: {candidate_name}

{salary_context}

Evaluate these four dimensions (each scored 0 to their maximum):

1. enthusiasm (max {_MAX_ENTHUSIASM}):
   - Positive tone, excitement, and genuine interest expressed throughout the call.
   - Did the candidate say they are actively looking for this type of role?
   - Were their responses engaged and enthusiastic vs flat and short?

2. proactive_questions (max {_MAX_PROACTIVE}):
   - Did the candidate ask thoughtful questions about the role, team, tech stack, or company?
   - Quality matters more than quantity — a single insightful question scores higher than two generic ones.
   - No questions at all = 0.

3. salary_alignment (max {_MAX_SALARY}):
   - Was the candidate's stated salary expectation within or close to the JD range?
   - If the candidate did not mention salary when asked = partial credit.
   - If salary was not discussed at all = award 12 (neutral).

4. availability (max {_MAX_AVAILABILITY}):
   - Did the candidate mention availability or a start date?
   - Notice period ≤ 30 days = full marks. 31–45 days = partial. > 45 days = low marks.
   - Mentioned another competing offer = deduct points.

Return ONLY valid JSON in this exact format — no markdown, no code fences, no extra keys:
{{
  "interest_score": <integer, sum of all four dimensions, 0-{_MAX_INTEREST_SCORE}>,
  "breakdown": {{
    "enthusiasm":          <integer 0-{_MAX_ENTHUSIASM}>,
    "proactive_questions": <integer 0-{_MAX_PROACTIVE}>,
    "salary_alignment":    <integer 0-{_MAX_SALARY}>,
    "availability":        <integer 0-{_MAX_AVAILABILITY}>
  }},
  "explanation": "<2–3 sentences written for a recruiter, mentioning key positive signals and any concerns>"
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
    Analyse a conversation transcript and return a structured Interest Score.

    Args:
        transcript:  list of {"role": str, "turn": int, "message": str} dicts
                     (output of conversation_sim.simulate_conversation)
        parsed_jd:   Structured JD dict from Agent 1.
        candidate:   Candidate profile dict.
                     NOTE: interest_level is intentionally NOT used here —
                     the score is derived only from what the transcript reveals.

    Returns:
        {
          "interest_score": int,
          "breakdown": {"enthusiasm": int, "proactive_questions": int,
                        "salary_alignment": int, "availability": int},
          "explanation": str
        }
    """
    candidate_name = candidate.get("name", "the candidate")
    log.info(f"[Agent 5] Scoring conversation for {candidate_name} …")

    if not transcript:
        log.warning(f"[Agent 5] Empty transcript for {candidate_name} — returning zero score.")
        return _zero_score("No conversation transcript was available to score.")

    # ── Format transcript for the LLM ────────────────────────────────────────
    transcript_text = _format_transcript(transcript)

    system_prompt = _build_system_prompt(parsed_jd, candidate_name)
    user_prompt   = (
        f"Here is the full conversation transcript:\n\n"
        f"{transcript_text}\n\n"
        f"Now evaluate the candidate's interest level using the four dimensions "
        f"and return the JSON score."
    )

    # ── Call LLM ─────────────────────────────────────────────────────────────
    raw_response = await call_llm(system_prompt, user_prompt)
    log.info(f"[Agent 5] Raw response received — parsing JSON …")

    # ── Parse and validate ────────────────────────────────────────────────────
    try:
        parsed = parse_json_response(raw_response)
        result = _validate_and_fix(parsed, candidate_name)
    except Exception as exc:
        log.error(f"[Agent 5] JSON parse error for {candidate_name}: {exc}")
        
        # HEAL: If it looks like truncation, try to close the JSON manually
        if "Expecting" in str(exc) or "Unterminated" in str(exc):
            log.warning("[Agent 5] Attempting to heal truncated JSON …")
            try:
                # Add closing quote if missing, then closing braces
                healed = raw_response.strip()
                if not healed.endswith('"}'):
                    if not healed.endswith('"'): healed += '"'
                    if not healed.endswith('}'): healed += '}'
                    if not healed.endswith('}'): healed += '}'
                parsed = parse_json_response(healed)
                result = _validate_and_fix(parsed, candidate_name)
            except Exception:
                result = _zero_score(f"Scoring failed due to a critical truncation error: {exc}")
        else:
            result = _zero_score(f"Scoring failed due to a parsing error: {exc}")

    log.info(
        f"[Agent 5] Scored {candidate_name}: "
        f"interest_score={result['interest_score']}  "
        f"breakdown={result['breakdown']}"
    )
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────
def _format_transcript(transcript: list[dict]) -> str:
    """
    Render the transcript as a clean dialogue string for the LLM.

    Example output:
        [Turn 1] RECRUITER: Hi, I'm Sarah …
        [Turn 1] CANDIDATE: Thanks for reaching out …
    """
    lines = []
    for entry in transcript:
        role    = entry.get("role", "unknown").upper()
        turn    = entry.get("turn", "?")
        message = entry.get("message", "").strip()
        lines.append(f"[Turn {turn}] {role}: {message}")
    return "\n\n".join(lines)


def _validate_and_fix(data: dict, candidate_name: str) -> dict:
    """
    Validate the LLM's JSON output and clamp scores within allowed bounds.
    Also recomputes interest_score from the breakdown to prevent hallucinated sums.
    """
    breakdown_raw = data.get("breakdown", {})

    enthusiasm     = _clamp(int(breakdown_raw.get("enthusiasm",          0)), 0, _MAX_ENTHUSIASM)
    proactive      = _clamp(int(breakdown_raw.get("proactive_questions", 0)), 0, _MAX_PROACTIVE)
    salary         = _clamp(int(breakdown_raw.get("salary_alignment",    0)), 0, _MAX_SALARY)
    availability   = _clamp(int(breakdown_raw.get("availability",        0)), 0, _MAX_AVAILABILITY)

    # Always recompute the total from parts — do not trust the LLM's sum
    interest_score = enthusiasm + proactive + salary + availability

    explanation = str(data.get("explanation", "")).strip()
    if not explanation:
        explanation = f"Interest score for {candidate_name} computed from transcript analysis."

    return {
        "interest_score": interest_score,
        "breakdown": {
            "enthusiasm":          enthusiasm,
            "proactive_questions": proactive,
            "salary_alignment":    salary,
            "availability":        availability,
        },
        "explanation": explanation,
    }


def _clamp(value: int, lo: int, hi: int) -> int:
    """Return value clamped to [lo, hi]."""
    return max(lo, min(hi, value))


def _zero_score(explanation: str) -> dict:
    """Return a safe zero-score result with an explanation."""
    return {
        "interest_score": 0,
        "breakdown": {
            "enthusiasm":          0,
            "proactive_questions": 0,
            "salary_alignment":    0,
            "availability":        0,
        },
        "explanation": explanation,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Quick demo  (python -m app.agents.scorer)
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json, sys

    # Simulate an enthusiastic transcript
    TRANSCRIPT_HIGH = [
        {"role": "recruiter", "turn": 1,
         "message": "Hi Arjun! Thanks for taking the time. Could you tell me a bit about your current role?"},
        {"role": "candidate", "turn": 1,
         "message": "Absolutely! I'm a senior backend engineer at Zepto, building payment APIs in FastAPI and PostgreSQL. "
                    "I've been there six years and I'm genuinely excited about fintech infrastructure challenges."},
        {"role": "recruiter", "turn": 2,
         "message": "That sounds great. What's drawing you to consider a new opportunity right now?"},
        {"role": "candidate", "turn": 2,
         "message": "I've been looking for exactly this kind of role — a senior backend position in fintech with a strong Python stack. "
                    "Could you tell me more about the team size and the deployment infrastructure? I'd love to know if you're on Kubernetes."},
        {"role": "recruiter", "turn": 3,
         "message": "We use a mix of ECS and Kubernetes on AWS. In terms of compensation, what are you looking for?"},
        {"role": "candidate", "turn": 3,
         "message": "I'm looking at around ₹28L per annum. I'm very flexible on other benefits though. "
                    "What does the engineering culture look like — how are on-call rotations handled?"},
        {"role": "recruiter", "turn": 4,
         "message": "On-call is light — roughly one week in six. When could you start if things move forward?"},
        {"role": "candidate", "turn": 4,
         "message": "My notice period is 30 days so I could start within a month. I'm keen to move quickly if the role is the right fit. "
                    "Is there a technical interview step I should prepare for?"},
        {"role": "recruiter", "turn": 5,
         "message": "Yes, a system design round and a take-home. Any other questions before I let you go?"},
        {"role": "candidate", "turn": 5,
         "message": "Just one — what does the growth path look like for someone joining at senior level? "
                    "Is there a staff engineer track?"},
        {"role": "recruiter", "turn": 6,
         "message": "Absolutely — we have a clear IC track up to staff and principal. Thanks so much Arjun, we'll be in touch within 3 days!"},
        {"role": "candidate", "turn": 6,
         "message": "Thank you Sarah, I really enjoyed this conversation. Looking forward to hearing from you!"},
    ]

    TRANSCRIPT_LOW = [
        {"role": "recruiter", "turn": 1,
         "message": "Hi! Thanks for speaking with us. Could you tell me about your current role?"},
        {"role": "candidate", "turn": 1,
         "message": "Sure. I'm at Flipkart. Principal engineer."},
        {"role": "recruiter", "turn": 2,
         "message": "Great. What's making you consider a new opportunity?"},
        {"role": "candidate", "turn": 2,
         "message": "I'm not really looking. I just took the call. I already have an offer from another company I'm considering."},
        {"role": "recruiter", "turn": 3,
         "message": "Understood. What compensation would it take for you to consider this?"},
        {"role": "candidate", "turn": 3,
         "message": "Significantly more than I make now. I'd need at least ₹1Cr. I don't think this role is at that level."},
        {"role": "recruiter", "turn": 4,
         "message": "When would you be available to start if things did work out?"},
        {"role": "candidate", "turn": 4,
         "message": "90 days minimum notice. Probably more."},
        {"role": "recruiter", "turn": 5,
         "message": "Any questions for me?"},
        {"role": "candidate", "turn": 5,
         "message": "Not really."},
        {"role": "recruiter", "turn": 6,
         "message": "Thanks for your time. We'll be in touch."},
        {"role": "candidate", "turn": 6,
         "message": "Sure. Bye."},
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

    SAMPLE_CANDIDATE = {"name": "Arjun Mehta", "salary_expectation_inr": 2800000}

    print("=== TalentRadar — Agent 5: Scorer demo ===\n")

    try:
        print("── Scoring HIGH-INTEREST transcript ──")
        high = score_conversation(TRANSCRIPT_HIGH, SAMPLE_JD, SAMPLE_CANDIDATE)
        print(json.dumps(high, indent=2))

        print("\n── Scoring LOW-INTEREST transcript ──")
        low = score_conversation(TRANSCRIPT_LOW, SAMPLE_JD, {"name": "Aisha Baig"})
        print(json.dumps(low, indent=2))

        assert high["interest_score"] > low["interest_score"], \
            f"Expected high > low but got {high['interest_score']} vs {low['interest_score']}"
        print(f"\n✓ High score ({high['interest_score']}) > Low score ({low['interest_score']}) — scorer is working correctly!")

    except Exception as e:
        print(f"\n✗ Failed: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)
