"""
llm_client.py — Unified LLM wrapper for TalentRadar.

Supports three-tier fallback:
  - Groq 70B (Primary)
  - Groq 8B (Secondary - high limits)
  - OpenRouter (Safety Net - generous free models)

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
GROQ_BASE_URL       = "https://api.groq.com/openai/v1"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Per-agent configuration: allows using optimal models for each agent type.
# We ensure every agent has ALL 5 OpenRouter models available as fallbacks,
# ordered by their specific preference, to maximize resilience.
AGENT_CONFIGS = {
    0: { # Default
        "groq": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
        "openrouter": [
            os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free"),
            "nousresearch/hermes-3-llama-3.1-405b:free",
            "mistralai/mistral-7b-instruct:free",
            "google/gemma-3-27b-it:free",
            "meta-llama/llama-3.2-3b-instruct:free"
        ]
    },
    1: { # JD Parser (fast & simple extraction)
        "groq": ["llama-3.1-8b-instant", "llama-3.3-70b-versatile"],
        "openrouter": [
            "meta-llama/llama-3.2-3b-instruct:free",
            "mistralai/mistral-7b-instruct:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "google/gemma-3-27b-it:free",
            "nousresearch/hermes-3-llama-3.1-405b:free"
        ]
    },
    2: { # Talent Scout (semantic search generation)
        "groq": ["llama-3.1-8b-instant", "llama-3.3-70b-versatile"],
        "openrouter": [
            "meta-llama/llama-3.2-3b-instruct:free",
            "google/gemma-3-27b-it:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "mistralai/mistral-7b-instruct:free",
            "nousresearch/hermes-3-llama-3.1-405b:free"
        ]
    },
    3: { # Recruiter AI (requires high nuance, HR persona)
        "groq": ["llama-3.3-70b-versatile"],
        "openrouter": [
            "nousresearch/hermes-3-llama-3.1-405b:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "google/gemma-3-27b-it:free",
            "mistralai/mistral-7b-instruct:free",
            "meta-llama/llama-3.2-3b-instruct:free"
        ]
    },
    4: { # Candidate AI (different persona from recruiter to prevent sameness)
        "groq": ["llama-3.3-70b-versatile"],
        "openrouter": [
            "meta-llama/llama-3.3-70b-instruct:free",
            "nousresearch/hermes-3-llama-3.1-405b:free",
            "mistralai/mistral-7b-instruct:free",
            "google/gemma-3-27b-it:free",
            "meta-llama/llama-3.2-3b-instruct:free"
        ]
    },
    5: { # Interest Scorer (requires high logical reasoning)
        "groq": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
        "openrouter": [
            "nousresearch/hermes-3-llama-3.1-405b:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "google/gemma-3-27b-it:free",
            "mistralai/mistral-7b-instruct:free",
            "meta-llama/llama-3.2-3b-instruct:free"
        ]
    }
}

# Track fallback state independently per agent to prevent cascaded failures
# Format: { agent_id: {"provider": "groq", "groq_idx": 0, "openrouter_idx": 0} }
_AGENT_STATES = {}

# Models that don't support a dedicated 'system' role — for these we merge
# the system prompt into the user message to avoid 400 INVALID_ARGUMENT errors.
_NO_SYSTEM_ROLE_MODELS = {"google/gemma-3-27b-it:free", "google/gemma-3-12b-it:free"}

MAX_RETRIES    = 6    # must be >= number of fallback tiers (Groq70B+Groq8B+3xOpenRouter)
BASE_BACKOFF   = 1
RATE_LIMIT_EXTRA_WAIT = 3

# Global clients
_groq_client = None
_openrouter_client = None

def _get_groq_client():
    global _groq_client
    if _groq_client is None:
        from openai import AsyncOpenAI
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError("GROQ_API_KEY is not set. Add it to your .env file.")
        _groq_client = AsyncOpenAI(api_key=api_key, base_url=GROQ_BASE_URL, max_retries=0)
    return _groq_client

def _get_openrouter_client():
    global _openrouter_client
    if _openrouter_client is None:
        from openai import AsyncOpenAI
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENROUTER_API_KEY is not set. Add it to your .env file.")
        _openrouter_client = AsyncOpenAI(
            api_key=api_key, 
            base_url=OPENROUTER_BASE_URL,
            default_headers={
                "HTTP-Referer": "https://talenthunt.vercel.app",
                "X-Title": "TalentRadar"
            },
            max_retries=0
        )
    return _openrouter_client

log.info("LLM Engine: Per-Agent Multi-Model Fallback initialized.")


# ── Public: main entry point ──────────────────────────────────────────────────
async def call_llm(system_prompt: str, user_prompt: str, agent_id: int = 0) -> str:
    """
    Call the configured LLM with tiered fallback logic specific to the agent's ID.
    If agent 1 hits a limit, it does not throttle agent 3.
    """
    last_exc: Exception | None = None
    import asyncio
    
    # Get or initialize state for this specific agent
    state = _AGENT_STATES.setdefault(agent_id, {"provider": "groq", "groq_idx": 0, "openrouter_idx": 0})
    config = AGENT_CONFIGS.get(agent_id, AGENT_CONFIGS[0])

    for attempt in range(MAX_RETRIES):
        try:
            if state["provider"] == "openrouter":
                model_name = config["openrouter"][state["openrouter_idx"]]
                return await _call_openrouter(system_prompt, user_prompt, model=model_name)
            else:
                model_name = config["groq"][state["groq_idx"]]
                return await _call_groq(system_prompt, user_prompt, model=model_name)

        except Exception as exc:
            last_exc = exc
            is_rate_limit    = _is_rate_limit_error(exc)
            is_unavailable   = _is_model_unavailable(exc)

            # ── Groq tier switches (only on rate-limit) ───────────────────────
            if is_rate_limit and state["provider"] == "groq":
                if state["groq_idx"] < len(config["groq"]) - 1:
                    log.warning(f"[Agent {agent_id}] Groq {config['groq'][state['groq_idx']]} limit hit. Switching to next Groq.")
                    state["groq_idx"] += 1
                    continue
                else:
                    log.warning(f"[Agent {agent_id}] Groq exhausted. Switching to OpenRouter.")
                    state["provider"] = "openrouter"
                    continue

            # ── OpenRouter model rotation (429 OR 404 — OUTSIDE rate-limit block)
            if state["provider"] == "openrouter" and (is_rate_limit or is_unavailable):
                if state["openrouter_idx"] < len(config["openrouter"]) - 1:
                    state["openrouter_idx"] += 1
                    next_model = config["openrouter"][state["openrouter_idx"]]
                    log.warning(f"[Agent {agent_id}] OpenRouter error ({exc.__class__.__name__}). Rotating to: {next_model}")
                    continue
                # All OpenRouter models exhausted
                # If it's a 404/400 (unrecoverable), waiting won't help. Break and fail fast.
                if is_unavailable:
                    log.error(f"[Agent {agent_id}] Models exhausted and hit unrecoverable error ({exc}). Failing fast.")
                    break

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


# ── Private: OpenRouter ───────────────────────────────────────────────────────
async def _call_openrouter(system_prompt: str, user_prompt: str, model: str) -> str:
    """Call OpenRouter with the provided model."""
    import asyncio
    client = _get_openrouter_client()
    # Small sleep to avoid hammering free-tier upstream concurrently
    await asyncio.sleep(0.5)

    # Some models (e.g. Gemma) don't support a system role — merge into user msg
    if model in _NO_SYSTEM_ROLE_MODELS:
        messages = [{"role": "user", "content": f"{system_prompt}\n\n{user_prompt}"}]
    else:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ]

    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


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
    Covers OpenAI / Groq / OpenRouter (openai.RateLimitError), and generic HTTP 429 strings.
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
        "402",
        "payment required",
        "spend limit",
    )
    return any(kw in exc_str for kw in rate_limit_keywords)


def _is_model_unavailable(exc: Exception) -> bool:
    """
    Return True if OpenRouter returned 404 'No endpoints found' — meaning
    this specific free model is currently offline/unavailable upstream.
    Should trigger rotation to the next model in the list.
    """
    exc_str = str(exc).lower()
    return ("404" in exc_str and "no endpoints found" in exc_str) or ("400" in exc_str)

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
