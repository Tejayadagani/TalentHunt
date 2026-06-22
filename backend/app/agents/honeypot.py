"""
honeypot.py — Honeypot candidate detection.

Detects fabricated/fake profiles using 5 structural integrity rules.
Honeypot candidates receive final_score=0.0 and never appear in top-100.

Public API
----------
  detect_honeypot(candidate: dict) -> tuple[bool, str]
    Returns (is_honeypot, reason_string)

Rules (from hackathon spec)
---------------------------
  1. Single company duration > YOE + 1.5 years
  2. Sum of all role durations > (YOE + 3) × 12 months
  3. proficiency="expert" AND duration_months=0 for any skill
  4. end_date < start_date for any career role
  5. 10+ expert skills with total duration < 12 months across all of them

NOTE: These rules operate on structured career/skill data.
      If the candidate profile only has a flat skills list (no career history),
      only Rule 3 and Rule 5 are applicable.
"""

import logging
import json
from datetime import datetime

log = logging.getLogger(__name__)

# Import from config with a safe fallback so this module works standalone too
try:
    from config import (
        HONEYPOT_DURATION_SLACK_YEARS,
        HONEYPOT_TOTAL_DURATION_SLACK,
        HONEYPOT_EXPERT_SKILL_COUNT,
        HONEYPOT_EXPERT_TOTAL_MONTHS,
    )
except ImportError:
    HONEYPOT_DURATION_SLACK_YEARS = 1.5
    HONEYPOT_TOTAL_DURATION_SLACK = 3
    HONEYPOT_EXPERT_SKILL_COUNT   = 10
    HONEYPOT_EXPERT_TOTAL_MONTHS  = 12


def _decode_list(value) -> list:
    """Safely decode a value that may be a list, JSON string, or plain string.

    ChromaDB stores nested structures (career_history, skills_detail) as
    JSON-serialized strings. This helper decodes them transparently.
    Returns an empty list if decoding fails or value is None.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
            return decoded if isinstance(decoded, list) else []
        except Exception:
            return []   # plain string, not JSON — not iterable as list
    return []



# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────
def detect_honeypot(candidate: dict) -> tuple[bool, str]:
    """
    Run all 5 honeypot detection rules on a candidate profile.

    Returns:
        (True, reason_string)  if honeypot detected
        (False, "")            if clean
    """
    cid  = candidate.get("id", "unknown")
    name = candidate.get("name", "Unknown")

    for rule_fn in [_rule1_single_company, _rule2_total_duration,
                    _rule3_expert_zero_duration, _rule4_date_reversal,
                    _rule5_expert_skill_flood]:
        flagged, reason = rule_fn(candidate)
        if flagged:
            log.warning(f"[Honeypot] {name} ({cid}) flagged: {reason}")
            return True, reason

    return False, ""


# ─────────────────────────────────────────────────────────────────────────────
# Rule implementations
# ─────────────────────────────────────────────────────────────────────────────
def _rule1_single_company(candidate: dict) -> tuple[bool, str]:
    """
    Rule 1: Duration at one company > total YOE + 1.5 years.
    Impossible unless tenure is fabricated.
    """
    yoe = _safe_int(candidate.get("years_of_experience", 0))
    max_single_months = (yoe + HONEYPOT_DURATION_SLACK_YEARS) * 12

    careers = _decode_list(candidate.get("career_history", []))
    for role in careers:
        if not isinstance(role, dict):
            continue
        duration = _role_duration_months(role)
        if duration > max_single_months:
            return True, (
                f"Rule 1: Single-company tenure {duration:.0f} months "
                f"exceeds YOE+{HONEYPOT_DURATION_SLACK_YEARS}yr limit "
                f"({max_single_months:.0f} months) at '{role.get('company', 'unknown')}'."
            )
    return False, ""


def _rule2_total_duration(candidate: dict) -> tuple[bool, str]:
    """
    Rule 2: Sum of all role durations > (YOE + 3) × 12 months.
    More years on CV than physically possible.
    """
    yoe = _safe_int(candidate.get("years_of_experience", 0))
    max_total_months = (yoe + HONEYPOT_TOTAL_DURATION_SLACK) * 12

    careers = _decode_list(candidate.get("career_history", []))
    if not careers:
        return False, ""

    total_months = sum(_role_duration_months(r) for r in careers if isinstance(r, dict))
    if total_months > max_total_months:
        return True, (
            f"Rule 2: Total career duration {total_months:.0f} months "
            f"exceeds (YOE+{HONEYPOT_TOTAL_DURATION_SLACK})×12 = {max_total_months:.0f} months."
        )
    return False, ""


def _rule3_expert_zero_duration(candidate: dict) -> tuple[bool, str]:
    """
    Rule 3: proficiency='expert' AND duration_months=0 for any skill.
    Cannot be expert in something you've never used.
    """
    skills = _decode_list(candidate.get("skills_detail") or candidate.get("skills") or [])
    for skill in skills:
        if not isinstance(skill, dict):
            continue
        if (str(skill.get("proficiency", "")).lower() == "expert"
                and skill.get("duration_months") == 0):
            return True, (
                f"Rule 3: Skill '{skill.get('name', 'unknown')}' "
                f"claims expert proficiency with 0 months duration."
            )
    return False, ""


def _rule4_date_reversal(candidate: dict) -> tuple[bool, str]:
    """
    Rule 4: end_date < start_date for any career role.
    Physically impossible — clear fabrication.
    """
    careers = _decode_list(candidate.get("career_history", []))
    for role in careers:
        if not isinstance(role, dict):
            continue
        start = _parse_date(role.get("start_date"))
        end   = _parse_date(role.get("end_date"))
        if start and end and end < start:
            return True, (
                f"Rule 4: Role at '{role.get('company', 'unknown')}' "
                f"has end_date ({role.get('end_date')}) "
                f"before start_date ({role.get('start_date')})."
            )
    return False, ""


def _rule5_expert_skill_flood(candidate: dict) -> tuple[bool, str]:
    """
    Rule 5: 10+ expert skills with total duration < 12 months across all of them.
    Cannot become expert in 10+ skills in under a year.
    """
    skills = _decode_list(candidate.get("skills_detail") or candidate.get("skills") or [])
    expert_skills = [
        s for s in skills
        if isinstance(s, dict) and str(s.get("proficiency", "")).lower() == "expert"
    ]

    if len(expert_skills) < HONEYPOT_EXPERT_SKILL_COUNT:
        return False, ""

    total_expert_months = sum(_safe_int(s.get("duration_months", 0)) for s in expert_skills)
    if total_expert_months < HONEYPOT_EXPERT_TOTAL_MONTHS:
        return True, (
            f"Rule 5: {len(expert_skills)} expert skills but only "
            f"{total_expert_months} total months of expert-level usage "
            f"(threshold: {HONEYPOT_EXPERT_TOTAL_MONTHS} months)."
        )
    return False, ""


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _role_duration_months(role: dict) -> float:
    """Calculate duration of a career role in months."""
    # If duration_months is explicitly provided, use it
    if "duration_months" in role:
        return float(role["duration_months"])

    start = _parse_date(role.get("start_date"))
    end   = _parse_date(role.get("end_date")) or datetime.now()

    if not start:
        return 0.0

    delta_months = (end.year - start.year) * 12 + (end.month - start.month)
    return max(0.0, float(delta_months))


def _parse_date(date_str) -> datetime | None:
    """Parse a date string in various common formats."""
    if not date_str or str(date_str).lower() in ("present", "current", "now", ""):
        return None
    for fmt in ("%Y-%m", "%Y-%m-%d", "%m/%Y", "%Y"):
        try:
            return datetime.strptime(str(date_str).strip(), fmt)
        except ValueError:
            continue
    return None


def _safe_int(val) -> int:
    """Safely convert to int, returning 0 on failure."""
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


# ─────────────────────────────────────────────────────────────────────────────
# Smoke test (python -m app.agents.honeypot)
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json

    # Clearly fake profile — fails Rule 1 and Rule 5
    HONEYPOT_CANDIDATE = {
        "id": "HONEYPOT_001",
        "name": "Fake Profile",
        "years_of_experience": 3,
        "career_history": [
            {"company": "TechCorp", "start_date": "2010-01", "end_date": "2023-12"},  # 168 months
        ],
        "skills_detail": [
            {"name": f"Skill_{i}", "proficiency": "expert", "duration_months": 0}
            for i in range(12)
        ],
    }

    # Clean profile
    CLEAN_CANDIDATE = {
        "id": "CLEAN_001",
        "name": "Real Engineer",
        "years_of_experience": 6,
        "career_history": [
            {"company": "Startup A", "start_date": "2018-06", "end_date": "2021-06"},  # 36 months
            {"company": "Scale-up B", "start_date": "2021-07", "end_date": "2024-06"},  # 36 months
        ],
        "skills_detail": [
            {"name": "Python", "proficiency": "expert", "duration_months": 48},
            {"name": "FastAPI", "proficiency": "advanced", "duration_months": 24},
        ],
    }

    print("=== Honeypot Detection Smoke Test ===\n")

    flagged, reason = detect_honeypot(HONEYPOT_CANDIDATE)
    print(f"Fake Profile: flagged={flagged}  reason='{reason}'")
    assert flagged, "Should have been flagged!"

    clean, _ = detect_honeypot(CLEAN_CANDIDATE)
    print(f"Real Engineer: flagged={clean}")
    assert not clean, "Should NOT have been flagged!"

    print("\n✓ Honeypot detection smoke test passed!")
