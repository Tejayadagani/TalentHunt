"""
jd_parser.py — Agent 1: Job Description Parser.

Takes raw JD text and extracts a clean, structured JSON object that all
downstream agents consume.

Public API
----------
  parse_jd(jd_text: str) -> dict

Output schema
-------------
{
  "title":              str | null,
  "required_skills":    list[str],
  "nice_to_have_skills": list[str],
  "seniority":          "intern"|"junior"|"mid"|"senior"|"lead"|"principal" | null,
  "domain":             str | null,
  "location":           str | null,
  "remote_ok":          bool,
  "salary_range":       { "min": int, "max": int, "currency": str } | null,
  "must_haves":         list[str]
}
"""

import logging
from app.llm_client import call_llm, parse_json_response

log = logging.getLogger(__name__)

# ── Valid seniority levels (matches candidate schema) ─────────────────────────
SENIORITY_LEVELS = {"intern", "junior", "mid", "senior", "lead", "principal"}

# ── System prompt ─────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """You are a structured data extractor for job descriptions.

Extract the following fields from the JD provided by the user:

- title: job title (string)
- required_skills: list of required technical skills (list of strings)
- nice_to_have_skills: list of optional/bonus skills (list of strings)
- seniority: one of [intern, junior, mid, senior, lead, principal]
- domain: industry/domain (string, e.g. "fintech", "edtech", "healthcare", "ecommerce")
- location: primary city (string or null)
- remote_ok: whether remote work is allowed (boolean)
- salary_range: { "min": <int>, "max": <int>, "currency": <str> } or null if not mentioned
- must_haves: list of non-negotiable requirements as stated in the JD (list of strings)

Rules:
- Only extract what is explicitly stated. Do not invent or infer.
- Return ONLY valid JSON. No markdown, no explanation, no code fences.
- If a field cannot be determined, set it to null.
- Normalise skill names consistently:
    "Postgres" or "postgres" → "PostgreSQL"
    "node" or "NodeJS"       → "Node.js"
    "mongo"                  → "MongoDB"
    "ES"                     → "Elasticsearch"
    "k8s"                    → "Kubernetes"
    "tf"                     → "Terraform"
    "js"                     → "JavaScript"
    "ts"                     → "TypeScript"
- Seniority inference guide (use the JD's wording, not just years):
    0–1 yr / trainee / graduate → "intern" or "junior"
    2–4 yr / engineer II        → "mid"
    5–8 yr / senior engineer    → "senior"
    8–12 yr / staff / EM        → "lead"
    12+ yr / principal / VP Eng → "principal"
- salary_range.currency should be the ISO 4217 code (e.g. "INR", "USD", "GBP").
  If currency is ambiguous (e.g. "₹" or "Rs"), use "INR".
"""


# ── Public function ───────────────────────────────────────────────────────────
def parse_jd(jd_text: str) -> dict:
    """
    Parse a raw job description string into a structured dict.

    Calls the LLM, strips any markdown fences from the response,
    parses JSON, validates/sanitises fields, and returns the result.

    Raises:
        ValueError: if jd_text is too short to be a real JD.
        json.JSONDecodeError: if the LLM returns non-parseable JSON after retries.
    """
    if len(jd_text.strip()) < 50:
        raise ValueError(
            "Job description is too short (< 50 chars). Please provide a full JD."
        )

    log.info("[Agent 1] Parsing job description …")

    raw_response = call_llm(
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=f"Extract the structured data from this job description:\n\n{jd_text}",
    )

    log.info("[Agent 1] Raw LLM response received — parsing JSON …")

    parsed = parse_json_response(raw_response)
    sanitised = _sanitise(parsed)

    log.info(
        f"[Agent 1] Done — title='{sanitised.get('title')}' "
        f"seniority={sanitised.get('seniority')} "
        f"required_skills={sanitised.get('required_skills')}"
    )
    return sanitised


# ── Internal: sanitise / set safe defaults ─────────────────────────────────────
def _sanitise(data: dict) -> dict:
    """
    Enforce types and safe defaults on the parsed JD object so downstream
    agents always receive a well-formed dict regardless of LLM output variation.
    """
    # String fields
    title    = data.get("title") or None
    domain   = data.get("domain") or None
    location = data.get("location") or None

    # Seniority — must be one of the allowed levels, else null
    seniority_raw = (data.get("seniority") or "").lower().strip()
    seniority = seniority_raw if seniority_raw in SENIORITY_LEVELS else None

    # List fields — always lists of stripped, non-empty strings
    required_skills      = _to_str_list(data.get("required_skills"))
    nice_to_have_skills  = _to_str_list(data.get("nice_to_have_skills"))
    must_haves           = _to_str_list(data.get("must_haves"))

    # Boolean: remote_ok
    remote_ok_raw = data.get("remote_ok")
    if isinstance(remote_ok_raw, bool):
        remote_ok = remote_ok_raw
    elif isinstance(remote_ok_raw, str):
        remote_ok = remote_ok_raw.lower() in ("true", "yes", "1")
    else:
        remote_ok = False

    # Salary range — must have min, max (ints) and currency (str), else null
    salary_range = _parse_salary(data.get("salary_range"))

    return {
        "title":               title,
        "required_skills":     required_skills,
        "nice_to_have_skills": nice_to_have_skills,
        "seniority":           seniority,
        "domain":              domain,
        "location":            location,
        "remote_ok":           remote_ok,
        "salary_range":        salary_range,
        "must_haves":          must_haves,
    }


def _to_str_list(value) -> list[str]:
    """Coerce a value to a clean list of non-empty strings."""
    if not value:
        return []
    if isinstance(value, str):
        # LLM occasionally returns a comma-separated string instead of a list
        return [s.strip() for s in value.split(",") if s.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _parse_salary(salary) -> dict | None:
    """Validate and return a salary_range dict, or None."""
    if not salary or not isinstance(salary, dict):
        return None
    try:
        s_min = int(salary.get("min") or 0)
        s_max = int(salary.get("max") or 0)
        currency = str(salary.get("currency") or "INR").strip().upper()
        if s_min <= 0 and s_max <= 0:
            return None
        return {"min": s_min, "max": s_max, "currency": currency}
    except (TypeError, ValueError):
        return None


# ── Build a human-readable JD summary (used by Agent 2 match-reason prompt) ───
def jd_summary(parsed_jd: dict) -> str:
    """Return a one-paragraph plain-English summary of a parsed JD dict."""
    title    = parsed_jd.get("title", "Unknown role")
    domain   = parsed_jd.get("domain", "")
    loc      = parsed_jd.get("location", "")
    remote   = "remote-friendly" if parsed_jd.get("remote_ok") else "on-site"
    seniority = parsed_jd.get("seniority", "")
    skills   = ", ".join(parsed_jd.get("required_skills", []))
    nice     = ", ".join(parsed_jd.get("nice_to_have_skills", []))
    salary   = parsed_jd.get("salary_range")
    sal_str  = ""
    if salary:
        sal_str = (
            f"Salary: {salary['currency']} {salary['min']:,}–{salary['max']:,}. "
        )
    return (
        f"{seniority.capitalize()} {title} in {domain} domain. "
        f"Location: {loc} ({remote}). "
        f"Required skills: {skills}. "
        f"Nice-to-have: {nice}. "
        f"{sal_str}"
    ).strip()


# ── Quick demo (python -m app.agents.jd_parser) ───────────────────────────────
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

    print("=== TalentRadar — Agent 1: JD Parser demo ===\n")
    print("Input JD:")
    print(SAMPLE_JD.strip())
    print("\nParsing …\n")

    try:
        result = parse_jd(SAMPLE_JD)
        print("Parsed output:")
        print(json.dumps(result, indent=2))
        print()
        print("JD Summary:")
        print(jd_summary(result))
        print("\n✓ Agent 1 smoke test passed!")
    except Exception as e:
        print(f"\n✗ Failed: {e}")
        sys.exit(1)
