"""
disqualifier.py — Disqualifier multiplier logic.

Applies score multipliers to candidates based on their background:
  - consulting_only  → ×0.25  (entire career at IT services firms)
  - wrong_domain     → ×0.40  (current title unrelated to tech/engineering)
  - honeypot         → ×0.00  (fabricated profile, already flagged)
  - ok               → ×1.00  (no disqualifier)

Public API
----------
  classify_candidate(candidate: dict) -> tuple[str, float]
    Returns (flag_label, multiplier)
    flag_label: "ok" | "consulting_only" | "wrong_domain" | "honeypot"
"""

import logging
import re

log = logging.getLogger(__name__)

try:
    from config import (
        CONSULTING_FIRMS,
        WRONG_DOMAIN_TITLES,
        DISQUALIFIER_MULTIPLIERS,
    )
except ImportError:
    CONSULTING_FIRMS = {
        "tcs", "infosys", "wipro", "accenture", "cognizant",
        "capgemini", "hcl", "tech mahindra", "mphasis", "hexaware",
        "ltimindtree", "lti", "mindtree",
    }
    WRONG_DOMAIN_TITLES = {
        "marketing manager", "hr manager", "accountant", "civil engineer",
        "mechanical engineer", "content writer", "graphic designer",
        "project manager", "customer support", "sales manager",
    }
    DISQUALIFIER_MULTIPLIERS = {
        "ok": 1.00, "consulting_only": 0.25, "wrong_domain": 0.40, "honeypot": 0.00,
        "pure_research": 0.30, "recent_llm_only": 0.45, "stopped_coding": 0.50
    }


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────
def classify_candidate(candidate: dict) -> tuple[str, float]:
    """
    Classify a candidate and return (flag, multiplier).

    Priority order (worst first):
      1. honeypot (if pre-flagged — caller must set candidate['honeypot']=True)
      2. wrong_domain (current title clearly outside tech)
      3. consulting_only (entire career in IT services)
      4. ok
    """
    # Honour pre-flagged honeypots
    if candidate.get("honeypot"):
        return "honeypot", DISQUALIFIER_MULTIPLIERS["honeypot"]

    # Wrong domain — check current title
    current_title = candidate.get("current_title", "").lower().strip()
    if _is_wrong_domain(current_title):
        flag = "wrong_domain"
        log.debug(f"[Disqualifier] {candidate.get('name')} → {flag} (title: '{current_title}')")
        return flag, DISQUALIFIER_MULTIPLIERS[flag]

    # Consulting-only — check entire career history
    if _is_consulting_only(candidate):
        flag = "consulting_only"
        log.debug(f"[Disqualifier] {candidate.get('name')} → {flag}")
        return flag, DISQUALIFIER_MULTIPLIERS[flag]

    # Pure Research
    is_research, _ = detect_pure_research(candidate)
    if is_research:
        flag = "pure_research"
        log.debug(f"[Disqualifier] {candidate.get('name')} → {flag}")
        return flag, DISQUALIFIER_MULTIPLIERS[flag]

    # Recent LLM Only
    is_llm_only, _ = detect_recent_langchain_only(candidate)
    if is_llm_only:
        flag = "recent_llm_only"
        log.debug(f"[Disqualifier] {candidate.get('name')} → {flag}")
        return flag, DISQUALIFIER_MULTIPLIERS[flag]

    # Stopped Coding
    is_stopped_coding, _ = detect_stopped_coding(candidate)
    if is_stopped_coding:
        flag = "stopped_coding"
        log.debug(f"[Disqualifier] {candidate.get('name')} → {flag}")
        return flag, DISQUALIFIER_MULTIPLIERS[flag]

    return "ok", DISQUALIFIER_MULTIPLIERS["ok"]

def detect_pure_research(candidate):
    """
    Returns (is_pure_research: bool, reason: str)
    Flags candidates whose ENTIRE career_history consists of research/
    academic titles with no evidence of production deployment language
    in any role description.
    """
    RESEARCH_TITLE_KEYWORDS = [
        "research scientist", "research fellow", "postdoc", "phd researcher",
        "research associate", "academic researcher", "research intern"
    ]
    PRODUCTION_EVIDENCE_KEYWORDS = [
        "deployed", "production", "shipped", "scale", "users", "live system",
        "launched", "rollout", "a/b test", "serving", "latency"
    ]

    titles = [role.get("title", "").lower() for role in candidate.get("career_history", [])]
    all_research = len(titles) > 0 and all(
        any(kw in t for kw in RESEARCH_TITLE_KEYWORDS) for t in titles
    )

    if not all_research:
        return False, ""

    descriptions = " ".join(
        role.get("description", "").lower() for role in candidate.get("career_history", [])
    )
    has_production_evidence = any(kw in descriptions for kw in PRODUCTION_EVIDENCE_KEYWORDS)

    if has_production_evidence:
        return False, ""  # research background but has shown production evidence — not disqualified

    return True, "entire career in research/academic roles with no production deployment evidence"

def detect_recent_langchain_only(candidate):
    """
    Returns (is_recent_stuffer: bool, reason: str)
    Flags candidates whose ONLY AI/ML-related experience is in roles
    lasting under 12 months, mentioning LangChain/OpenAI/prompt
    engineering, with no earlier ML/retrieval/embeddings experience.
    """
    RECENT_LLM_KEYWORDS = ["langchain", "openai api", "prompt engineering", "gpt wrapper", "llm app"]
    PRE_LLM_ML_KEYWORDS = [
        "embeddings", "retrieval", "ranking", "recommendation", "nlp",
        "machine learning", "deep learning", "bert", "transformer",
        "vector search", "search ranking", "information retrieval"
    ]

    history = candidate.get("career_history", [])
    ai_roles = [
        r for r in history
        if any(kw in r.get("description", "").lower() for kw in RECENT_LLM_KEYWORDS + PRE_LLM_ML_KEYWORDS)
    ]

    if not ai_roles:
        return False, ""  # no AI experience claimed at all — handled elsewhere, not this check

    recent_llm_only_roles = [
        r for r in ai_roles
        if r.get("duration_months", 999) < 12
        and any(kw in r.get("description", "").lower() for kw in RECENT_LLM_KEYWORDS)
    ]

    has_pre_llm_experience = any(
        any(kw in r.get("description", "").lower() for kw in PRE_LLM_ML_KEYWORDS)
        and r.get("duration_months", 0) >= 12
        for r in history
    )

    if recent_llm_only_roles and not has_pre_llm_experience and len(ai_roles) == len(recent_llm_only_roles):
        return True, "AI experience limited to recent (<12mo) LangChain/OpenAI work with no prior ML production background"

    return False, ""

def detect_stopped_coding(candidate):
    """
    Returns (has_stopped_coding: bool, reason: str)
    Flags candidates whose CURRENT role is architecture/management-titled
    AND has lasted 18+ months, with no recent hands-on coding evidence
    in the description.
    """
    NON_CODING_TITLE_KEYWORDS = [
        "architect", "tech lead", "engineering manager", "head of engineering",
        "director of engineering", "vp of engineering", "principal architect"
    ]
    HANDS_ON_EVIDENCE_KEYWORDS = [
        "wrote", "implemented", "coded", "built", "developed", "hands-on",
        "contributed code", "pull request", "shipped code", "personally built"
    ]

    history = candidate.get("career_history", [])
    current_role = next((r for r in history if r.get("is_current")), None)

    if not current_role:
        return False, ""

    title = current_role.get("title", "").lower()
    is_non_coding_title = any(kw in title for kw in NON_CODING_TITLE_KEYWORDS)
    tenure = current_role.get("duration_months", 0)

    if not (is_non_coding_title and tenure >= 18):
        return False, ""

    description = current_role.get("description", "").lower()
    has_hands_on_evidence = any(kw in description for kw in HANDS_ON_EVIDENCE_KEYWORDS)

    if has_hands_on_evidence:
        return False, ""  # title says architect, but description shows hands-on work — not disqualified

    return True, f"current role '{current_role.get('title')}' for {tenure} months with no hands-on coding evidence"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _is_wrong_domain(title: str) -> bool:
    """Return True if the title clearly indicates a non-tech role."""
    if not title:
        return False
    title_clean = title.lower().strip()
    # Exact match or prefix match against the set of known wrong-domain titles
    for bad in WRONG_DOMAIN_TITLES:
        if bad in title_clean:
            return True
    return False


def _is_consulting_only(candidate: dict) -> bool:
    """
    Return True if the candidate's ENTIRE career has been at consulting/IT-services firms.
    A single product-company role anywhere in their history clears them.
    """
    # Check career history (structured)
    careers = candidate.get("career_history", [])
    # ChromaDB stores lists as comma-joined strings — decode safely
    if isinstance(careers, str):
        import json
        try:
            careers = json.loads(careers)
        except Exception:
            careers = []   # unparseable — treat as no history

    if careers and isinstance(careers, list):
        for role in careers:
            if not isinstance(role, dict):
                continue  # skip non-dict entries
            company = role.get("company", "").lower().strip()
            if not _is_consulting_firm(company):
                return False   # found at least one non-consulting company
        return True  # all roles are consulting

    # Fallback: check current_company only
    current = candidate.get("current_company", "").lower().strip()
    if current and _is_consulting_firm(current):
        # Only flag if we have no other signal
        # Don't flag on current_company alone if no career_history — insufficient info
        return False

    return False


def _is_consulting_firm(company: str) -> bool:
    """Return True if the company name matches a known IT-services/consulting firm."""
    if not company:
        return False
    company_clean = company.lower().strip()
    # Remove common suffixes to improve matching
    company_clean = re.sub(r"\s*(ltd|limited|pvt|private|inc|llc|llp|technologies|tech|solutions|services|consulting|india)\.?\s*", "", company_clean).strip()
    return company_clean in CONSULTING_FIRMS or any(f in company_clean for f in CONSULTING_FIRMS)


# ─────────────────────────────────────────────────────────────────────────────
# Smoke test
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        # (candidate_dict, expected_flag)
        ({"name": "TCS Engineer", "current_title": "Software Engineer",
          "career_history": [
              {"company": "TCS"}, {"company": "Infosys"}, {"company": "Wipro"}
          ]}, "consulting_only"),
        ({"name": "Mixed Career", "current_title": "Senior Engineer",
          "career_history": [
              {"company": "TCS"}, {"company": "Razorpay"}
          ]}, "ok"),
        ({"name": "Marketing Person", "current_title": "Marketing Manager",
          "career_history": []}, "wrong_domain"),
        ({"name": "Product Engineer", "current_title": "Staff Engineer",
          "career_history": [{"company": "Zepto"}, {"company": "Cred"}]}, "ok"),
        ({"name": "Fake", "current_title": "Backend Engineer",
          "honeypot": True}, "honeypot"),
    ]

    print("=== Disqualifier Smoke Test ===\n")
    all_passed = True
    for cand, expected in tests:
        flag, mult = classify_candidate(cand)
        status = "✓" if flag == expected else "✗"
        if flag != expected:
            all_passed = False
        print(f"  {status} {cand['name']:<25} → {flag:<18} mult={mult}  (expected={expected})")

    print()
    if all_passed:
        print("✓ All disqualifier tests passed!")
    else:
        print("✗ Some tests failed!")
        import sys; sys.exit(1)
