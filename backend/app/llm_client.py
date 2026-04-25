"""
llm_client.py — Unified LLM wrapper for TalentRadar.

Supports two providers, selected via the LLM_PROVIDER env var:
  - "gemini"  (default) → Google Gemini 1.5 Flash, free tier
  - "groq"              → Groq API (Llama 3) via OpenAI-compatible API

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

class TelemetryFilter(logging.Filter):
    """Filter out noisy ChromaDB telemetry errors."""
    def filter(self, record):
        return "Failed to send telemetry event" not in record.getMessage()

# Attach filter to all root logger handlers to catch propagated logs
for handler in logging.root.handlers:
    handler.addFilter(TelemetryFilter())
# ── Configuration ─────────────────────────────────────────────────────────────
PROVIDER       = os.getenv("LLM_PROVIDER", "groq").lower()
GEMINI_MODEL   = "gemini-2.5-flash"
GROQ_MODELS    = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
GROQ_MODEL_IDX = 0
GROQ_BASE_URL  = "https://api.groq.com/openai/v1"

MAX_RETRIES    = 3
BASE_BACKOFF   = 1      # seconds — doubles each retry: 1 → 2 → 4
RATE_LIMIT_EXTRA_WAIT = 5   # extra seconds on top of backoff for 429s

# Global clients to avoid re-instantiation overhead
_genai_configured = False
_groq_client = None

def _get_groq_client():
    global _groq_client
    if _groq_client is None:
        from openai import AsyncOpenAI
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError("GROQ_API_KEY is not set. Add it to your .env file.")
        _groq_client = AsyncOpenAI(api_key=api_key, base_url=GROQ_BASE_URL)
    return _groq_client

def _configure_gemini():
    global _genai_configured
    if not _genai_configured:
        import google.generativeai as genai
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError("GEMINI_API_KEY is not set. Add it to your .env file.")
        genai.configure(api_key=api_key)
        _genai_configured = True

log.info(f"Initial Provider: {PROVIDER.upper()} | Primary Model: {GROQ_MODELS[0] if PROVIDER == 'groq' else GEMINI_MODEL}")


# ── Public: main entry point ──────────────────────────────────────────────────
async def call_llm(system_prompt: str, user_prompt: str) -> str:
    """
    Call the configured LLM with the given prompts (Asynchronous).

    Retries up to MAX_RETRIES times with exponential backoff.
    If using Groq and a rate limit is hit, it will automatically fall back
    to Gemini to prevent failure.
    """
    last_exc: Exception | None = None
    import asyncio
    global PROVIDER, GROQ_MODEL_IDX

    for attempt in range(MAX_RETRIES):
        try:
            if PROVIDER == "gemini":
                return await _call_gemini(system_prompt, user_prompt)
            else:
                # Try current Groq model
                model_name = GROQ_MODELS[GROQ_MODEL_IDX]
                return await _call_groq(system_prompt, user_prompt, model=model_name)

        except Exception as exc:
            last_exc = exc
            is_rate_limit = _is_rate_limit_error(exc)
            
            # TIERED FALLBACK LOGIC
            if is_rate_limit:
                # 1. Groq 70b -> Groq 8b
                if PROVIDER == "groq" and GROQ_MODEL_IDX == 0:
                    log.warning("Groq 70b limit hit. Falling back to Groq 8b (higher limits).")
                    GROQ_MODEL_IDX = 1
                    continue
                
                # 2. Groq 8b -> Gemini
                if PROVIDER == "groq" and GROQ_MODEL_IDX == 1:
                    log.warning("Groq 8b limit hit. Falling back to Gemini 2.5 Flash.")
                    PROVIDER = "gemini"
                    continue

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
                await asyncio.sleep(wait)

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
async def _call_gemini(system_prompt: str, user_prompt: str) -> str:
    """Call Google Gemini 1.5 Flash."""
    import google.generativeai as genai
    _configure_gemini()

    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=system_prompt,
    )

    response = await model.generate_content_async(user_prompt)
    return response.text.strip()


# ── Private: Groq ─────────────────────────────────────────────────────────────
async def _call_groq(system_prompt: str, user_prompt: str, model: str) -> str:
    """Call Groq via the OpenAI-compatible API (Asynchronous)."""
    client = _get_groq_client()

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        max_tokens=2048,  # Increased to prevent truncation of JSON/explanations
        temperature=0.1,  # Lower temperature for more stable JSON
    )
    return response.choices[0].message.content.strip()


# ── Private: rate-limit detection ─────────────────────────────────────────────
def _is_rate_limit_error(exc: Exception) -> bool:
    """
    Return True if the exception looks like a rate-limit / quota error.
    Covers Gemini (google.api_core.exceptions.ResourceExhausted),
    OpenAI / Groq (openai.RateLimitError), and generic HTTP 429 strings.
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
