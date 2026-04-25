"""
conversation_sim.py — Agents 3 & 4: Dual-Agent Conversation Simulator.

Agent 3 (Recruiter) and Agent 4 (Candidate) take turns in a simulated
screening call. The recruiter does NOT know the candidate's private data
(salary expectation, notice period, interest level) — it must discover
these through conversation, just like a real recruiter would.

Public API
----------
  async def simulate_conversation(parsed_jd, candidate, turns=6) -> list[dict]

Returns a transcript:
  [
    {"role": "recruiter", "turn": 1, "message": "..."},
    {"role": "candidate", "turn": 1, "message": "..."},
    ...
  ]

Private data guard
------------------
  interest_level is used ONLY to configure Agent 4's personality.
  It is NEVER passed to Agent 3 or included in any output.
"""

import logging
import time

from app.llm_client import call_llm

log = logging.getLogger(__name__)

# ── Rate-limit guard ─────────────────────────────────────────────────────────
# Groq tier 1: 30 RPM. Each turn = 2 LLM calls.
# 6 turns × 2 calls = 12 calls per candidate. Sleep between turns.
_INTER_TURN_SLEEP = 2   # seconds between each full turn (recruiter + candidate)


# ─────────────────────────────────────────────────────────────────────────────
# Public function
# ─────────────────────────────────────────────────────────────────────────────
async def simulate_conversation(
    parsed_jd: dict,
    candidate: dict,
    turns: int = 6,
) -> list[dict]:
    """
    Simulate a {turns}-turn screening call between a recruiter and a candidate.

    Each turn consists of:
      1. Agent 3 (Recruiter) generates the next recruiter message.
      2. Agent 4 (Candidate) responds based on their profile.

    The full conversation history is passed as context on every call so both
    agents maintain coherence across turns.

    Args:
        parsed_jd:  Structured JD dict from Agent 1.
        candidate:  Candidate profile dict (including private interest_level).
        turns:      Number of back-and-forth exchanges (default 6 per spec).

    Returns:
        list of {"role": str, "turn": int, "message": str} dicts.
    """
    name = candidate.get("name", "the candidate")
    log.info(
        f"[Agent 3+4] Starting {turns}-turn simulation for {name} "
        f"(interest={candidate.get('interest_level')}/5)"
    )

    history: list[dict] = []

    import asyncio
    for turn in range(1, turns + 1):
        is_last_turn = (turn == turns)

        # ── Agent 3: Recruiter speaks ────────────────────────────────────────
        log.info(f"[Agent 3] Turn {turn}/{turns} — recruiter generating message …")
        recruiter_msg = await _call_recruiter(parsed_jd, history, turn, turns, is_last_turn)
        history.append({"role": "recruiter", "turn": turn, "message": recruiter_msg})

        # ── Agent 4: Candidate responds ───────────────────────────────────────
        log.info(f"[Agent 4] Turn {turn}/{turns} — candidate generating response …")
        candidate_msg = await _call_candidate(candidate, history, turn, turns, is_last_turn)
        history.append({"role": "candidate", "turn": turn, "message": candidate_msg})

        log.info(f"[Agent 3+4] Turn {turn} complete.")

        # Rate-limit guard — skip sleep after last turn
        if not is_last_turn:
            await asyncio.sleep(_INTER_TURN_SLEEP)

    log.info(f"[Agent 3+4] Simulation complete — {len(history)} messages total.")
    return history


# ─────────────────────────────────────────────────────────────────────────────
# Agent 3 — Recruiter
# ─────────────────────────────────────────────────────────────────────────────
def _recruiter_system_prompt(parsed_jd: dict, total_turns: int) -> str:
    title     = parsed_jd.get("title", "Software Engineer")
    domain    = parsed_jd.get("domain", "tech")
    location  = parsed_jd.get("location", "our office")
    remote    = "remote-friendly" if parsed_jd.get("remote_ok") else "on-site only"
    skills    = ", ".join(parsed_jd.get("required_skills", []))

    return f"""You are a friendly, professional recruiter conducting a screening call for a {title} role at a growing {domain} company.

Job context:
- Role: {title}
- Domain: {domain}
- Location: {location} ({remote})
- Skills needed: {skills}

Your goal over {total_turns} turns is to naturally cover:
  1. The candidate's current role and background
  2. Their interest in this specific opportunity
  3. Expected compensation (ask — do NOT reveal our range first)
  4. Availability / notice period
  5. Any questions the candidate has about the role or team

Rules:
- You do NOT know the candidate's salary expectations, notice period, or interest level upfront — discover these through conversation.
- Keep each message to 2–4 sentences. Be warm and human, not robotic.
- Never ask multiple questions in one message — one question per turn.
- Do NOT reveal the salary range unless the candidate asks directly.
- On the final turn, thank them warmly and explain next steps.
- Respond ONLY with your next message — no labels, no JSON."""


async def _call_recruiter(
    parsed_jd: dict,
    history: list[dict],
    turn: int,
    total_turns: int,
    is_last: bool,
) -> str:
    """Generate the recruiter's next message (Agent 3)."""
    system = _recruiter_system_prompt(parsed_jd, total_turns)

    if not history:
        # Opening turn — recruiter speaks first
        user_prompt = (
            f"This is turn 1 of {total_turns}. Open the call warmly, introduce yourself briefly, "
            f"and ask the candidate to tell you about their current role."
        )
    else:
        dialogue = _format_history(history)
        if is_last:
            instruction = (
                f"This is the final turn ({turn}/{total_turns}). "
                "Wrap up the call warmly: thank the candidate for their time, "
                "let them know you'll be in touch within a few days, and wish them well."
            )
        else:
            instruction = (
                f"This is turn {turn} of {total_turns}. "
                "Continue the conversation naturally. "
                "Pick up from where it left off and ask your next single question."
            )
        user_prompt = f"Conversation so far:\n{dialogue}\n\n{instruction}"

    try:
        return (await call_llm(system, user_prompt, agent_id=3)).strip()
    except Exception as exc:
        log.error(f"[Agent 3] LLM call failed on turn {turn}: {exc}")
        return "Thank you for your time. We'll be in touch soon."


# ─────────────────────────────────────────────────────────────────────────────
# Agent 4 — Candidate
# ─────────────────────────────────────────────────────────────────────────────
def _candidate_system_prompt(candidate: dict) -> str:
    name         = candidate.get("name", "the candidate")
    title        = candidate.get("current_title", "Software Engineer")
    company      = candidate.get("current_company", "my current employer")
    skills       = ", ".join(candidate.get("skills", []))
    seniority    = candidate.get("seniority", "mid")
    yoe          = candidate.get("years_of_experience", 0)
    location     = candidate.get("location", "")
    salary       = candidate.get("salary_expectation_inr", 0)
    notice       = candidate.get("notice_period_days", 30)
    interest     = candidate.get("interest_level", 3)   # PRIVATE — not in output

    # Interest-level behaviour instructions
    behaviour_map = {
        5: (
            "You are very excited about this opportunity. "
            "Ask 2–3 detailed questions about the team structure, tech stack, and growth path. "
            "Mention that you have been actively looking for exactly this kind of role."
        ),
        4: (
            "You are positive and genuinely engaged. "
            "Ask 1–2 thoughtful questions about the role or company. "
            "Express clear interest in moving forward."
        ),
        3: (
            "You are neutral and professional. "
            "Answer questions factually and completely. "
            "You are neither excited nor dismissive — you are evaluating your options."
        ),
        2: (
            "You are somewhat distracted and not actively looking. "
            "Mention that you are fairly happy at your current job. "
            "Give shorter answers and do not ask follow-up questions."
        ),
        1: (
            "You are politely disinterested. "
            "Mention that you are already in advanced stages with another offer. "
            "Keep answers brief and non-committal."
        ),
    }
    behaviour = behaviour_map.get(interest, behaviour_map[3])

    salary_inr_lakh = salary / 100000

    return f"""You are {name}, a software professional. Stay 100% consistent with your profile below at all times.

Your profile:
- Name: {name}
- Current role: {title} at {company}
- Skills: {skills}
- Seniority: {seniority} with {yoe} years of experience
- Location: {location}
- Salary expectation: ₹{salary_inr_lakh:.0f}L per annum ({salary:,} INR)
- Notice period: {notice} days
- Interest level: {interest}/5 (private — never say this number aloud)

Your personality for this call:
{behaviour}

Strict rules:
- Only reveal your salary expectation and notice period if the recruiter asks directly.
- Do NOT invent skills, experience, or qualifications you don't have.
- Keep each response to 2–4 sentences — sound like a real human in a phone call.
- Do NOT say things like "As an AI" or "As a language model".
- Respond ONLY with your next message — no labels, no JSON."""


async def _call_candidate(
    candidate: dict,
    history: list[dict],
    turn: int,
    total_turns: int,
    is_last: bool,
) -> str:
    """Generate the candidate's response (Agent 4)."""
    system   = _candidate_system_prompt(candidate)
    dialogue = _format_history(history)

    if is_last:
        instruction = (
            f"This is the final turn ({turn}/{total_turns}). "
            "Respond to the recruiter's closing remarks naturally and warmly."
        )
    else:
        instruction = (
            f"This is turn {turn} of {total_turns}. "
            "Respond to the recruiter's latest message naturally, "
            "staying completely in character."
        )

    user_prompt = f"Conversation so far:\n{dialogue}\n\n{instruction}"

    try:
        return (await call_llm(system, user_prompt, agent_id=4)).strip()
    except Exception as exc:
        log.error(f"[Agent 4] LLM call failed on turn {turn}: {exc}")
        return "Sorry, I seem to have lost the connection. Could we continue?"


# ─────────────────────────────────────────────────────────────────────────────
# Shared utility
# ─────────────────────────────────────────────────────────────────────────────
def _format_history(history: list[dict]) -> str:
    """
    Format the conversation history as a readable dialogue string.

    Example:
        Recruiter (turn 1): Hi, I'm Sarah from TalentCo. ...
        Candidate (turn 1): Thanks for reaching out! ...
    """
    lines = []
    for entry in history:
        role    = entry["role"].capitalize()
        turn    = entry.get("turn", "?")
        message = entry["message"]
        lines.append(f"{role} (turn {turn}): {message}")
    return "\n\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Quick demo  (python -m app.agents.conversation_sim)
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    SAMPLE_JD = {
        "title": "Senior Backend Engineer",
        "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
        "nice_to_have_skills": ["Kubernetes", "Redis"],
        "seniority": "senior",
        "domain": "fintech",
        "location": "Bangalore",
        "remote_ok": True,
        "salary_range": {"min": 2000000, "max": 3500000, "currency": "INR"},
    }

    SAMPLE_CANDIDATE = {
        "id": "cand_001",
        "name": "Arjun Mehta",
        "current_title": "Backend Engineer",
        "current_company": "Zepto",
        "seniority": "senior",
        "years_of_experience": 6,
        "location": "Bangalore",
        "remote_ok": True,
        "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "Redis", "AWS"],
        "bio": "Backend engineer with 6 years building high-throughput payment APIs.",
        "salary_expectation_inr": 2800000,
        "notice_period_days": 30,
        "interest_level": 4,
    }

    print("=== TalentRadar — Agent 3+4: Conversation Simulator demo ===\n")
    print(f"JD: {SAMPLE_JD['title']} | {SAMPLE_JD['domain']}")
    print(f"Candidate: {SAMPLE_CANDIDATE['name']} (interest={SAMPLE_CANDIDATE['interest_level']}/5)\n")
    print("─" * 70)

    try:
        transcript = simulate_conversation(SAMPLE_JD, SAMPLE_CANDIDATE, turns=6)
        print()
        for entry in transcript:
            role = entry["role"].upper()
            print(f"\n[{role} — Turn {entry['turn']}]")
            print(entry["message"])
        print("\n" + "─" * 70)
        print(f"\n✓ Simulation complete — {len(transcript)} messages generated.")
    except Exception as e:
        print(f"\n✗ Failed: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)
