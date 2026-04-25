"""
llm_client.py — Unified LLM wrapper for TalentRadar.

Supports two providers, selected via the LLM_PROVIDER env var:
  - "gemini"  (default) → Google Gemini 1.5 Flash, free tier
  - "grok"              → xAI Grok-3-mini via OpenAI-compatible API

Public API
----------
  call_llm(system_prompt, user_prompt)  → str
  parse_json_response(text)             → dict  (strips markdown fences)

Retry policy
------------
  3 attempts with exponential backoff: 1 s, 2 s, 4 s.
  Rate-limit errors (HTTP 429 / RESOURCE_EXHAUSTED) add an extra 5-second wait.
"""

import json
import os
import re
import time
import logging
from dotenv import load_dotenv

load_dotenv()

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="[llm_client] %(levelname)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
PROVIDER       = os.getenv("LLM_PROVIDER", "gemini").lower()
GEMINI_MODEL   = "gemini-1.5-flash"
GROK_MODEL     = "grok-3-mini"
GROK_BASE_URL  = "https://api.x.ai/v1"

MAX_RETRIES    = 3
BASE_BACKOFF   = 1      # seconds — doubles each retry: 1 → 2 → 4
RATE_LIMIT_EXTRA_WAIT = 5   # extra seconds on top of backoff for 429s

# Validate provider at import time so failures are caught early
if PROVIDER not in ("gemini", "grok"):
    raise ValueError(
        f"Invalid LLM_PROVIDER='{PROVIDER}'. Must be 'gemini' or 'grok'."
    )

log.info(f"Provider: {PROVIDER.upper()}  |  model: {GEMINI_MODEL if PROVIDER == 'gemini' else GROK_MODEL}")


# ── Public: main entry point ──────────────────────────────────────────────────
def call_llm(system_prompt: str, user_prompt: str) -> str:
    """
    Call the configured LLM with the given prompts.

    Retries up to MAX_RETRIES times with exponential backoff.
    Rate-limit errors trigger an additional RATE_LIMIT_EXTRA_WAIT-second pause.

    Returns the raw text response (stripped of leading/trailing whitespace).
    Raises the last exception if all retries are exhausted.
    """
    last_exc: Exception | None = None

    for attempt in range(MAX_RETRIES):
        try:
            if PROVIDER == "gemini":
                return _call_gemini(system_prompt, user_prompt)
            else:
                return _call_grok(system_prompt, user_prompt)

        except Exception as exc:
            last_exc = exc
            is_rate_limit = _is_rate_limit_error(exc)
            wait = BASE_BACKOFF * (2 ** attempt)

            if is_rate_limit:
                wait += RATE_LIMIT_EXTRA_WAIT
                log.warning(
                    f"Rate limit hit (attempt {attempt + 1}/{MAX_RETRIES}). "
                    f"Waiting {wait}s before retry …"
                )
            else:
                log.warning(
                    f"LLM error on attempt {attempt + 1}/{MAX_RETRIES}: {exc}. "
                    f"Waiting {wait}s before retry …"
                )

            if attempt < MAX_RETRIES - 1:
                time.sleep(wait)

    log.error(f"All {MAX_RETRIES} LLM attempts failed. Last error: {last_exc}")
    raise last_exc  # type: ignore[misc]


# ── Public: JSON parsing helper ───────────────────────────────────────────────
def parse_json_response(text: str) -> dict:
    """
    Parse a JSON string from an LLM response.

    LLMs frequently wrap JSON in markdown code fences like:
        ```json
        { ... }
        ```
    This function strips those fences before parsing so callers don't
    need to handle this inconsistency.

    Raises json.JSONDecodeError if the cleaned text is not valid JSON.
    """
    # Remove ```json ... ``` or ``` ... ``` fences
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip()
    # Also strip stray backticks or trailing commas before the closing brace
    cleaned = cleaned.rstrip("`").strip()
    return json.loads(cleaned)


# ── Private: Gemini ───────────────────────────────────────────────────────────
def _call_gemini(system_prompt: str, user_prompt: str) -> str:
    """Call Google Gemini 1.5 Flash."""
    import google.generativeai as genai

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY is not set. Add it to your .env file."
        )

    genai.configure(api_key=api_key)

    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=system_prompt,
    )

    response = model.generate_content(user_prompt)
    return response.text.strip()


# ── Private: Grok ─────────────────────────────────────────────────────────────
def _call_grok(system_prompt: str, user_prompt: str) -> str:
    """Call xAI Grok via the OpenAI-compatible API."""
    from openai import OpenAI

    api_key = os.environ.get("GROK_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GROK_API_KEY is not set. Add it to your .env file."
        )

    client = OpenAI(api_key=api_key, base_url=GROK_BASE_URL)

    response = client.chat.completions.create(
        model=GROK_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
    )
    return response.choices[0].message.content.strip()


# ── Private: rate-limit detection ─────────────────────────────────────────────
def _is_rate_limit_error(exc: Exception) -> bool:
    """
    Return True if the exception looks like a rate-limit / quota error.
    Covers Gemini (google.api_core.exceptions.ResourceExhausted),
    OpenAI / Grok (openai.RateLimitError), and generic HTTP 429 strings.
    """
    exc_str = str(exc).lower()
    rate_limit_keywords = (
        "429",
        "rate limit",
        "ratelimit",
        "resource_exhausted",
        "resourceexhausted",
        "quota",
        "too many requests",
    )
    return any(kw in exc_str for kw in rate_limit_keywords)


# ── Smoke-test (run directly: python -m app.llm_client) ──────────────────────
if __name__ == "__main__":
    import sys

    print(f"\nRunning smoke test with provider: {PROVIDER.upper()}")
    print("-" * 50)

    try:
        result = call_llm(
            system_prompt="You are a helpful assistant. Reply in plain text only.",
            user_prompt='Say exactly: {"status": "ok", "provider": "<provider>"} '
                        f'but replace <provider> with {PROVIDER}. Return only JSON.',
        )
        print(f"Raw response:\n{result}\n")

        parsed = parse_json_response(result)
        print(f"Parsed JSON: {parsed}")
        print("\n✓ Smoke test passed!")
    except Exception as e:
        print(f"\n✗ Smoke test failed: {e}")
        sys.exit(1)
