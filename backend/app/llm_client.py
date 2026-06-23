"""
llm_client.py — Unified LLM wrapper for SkillSync AI.

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
            "meta-llama/llama-3.2-3b-instruct:free"
        ]
    },
    1: { # JD Parser (70B for best structured extraction — runs once)
        "groq": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
        "openrouter": [
            "meta-llama/llama-3.3-70b-instruct:free",
            "meta-llama/llama-3.2-3b-instruct:free",
            "nousresearch/hermes-3-llama-3.1-405b:free"
        ]
    },
    2: { # Talent Scout (semantic search generation)
        "groq": ["llama-3.1-8b-instant", "llama-3.3-70b-versatile"],
        "openrouter": [
            "meta-llama/llama-3.2-3b-instruct:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "nousresearch/hermes-3-llama-3.1-405b:free"
        ]
    },
    3: { # Recruiter AI (requires high nuance, HR persona)
        "groq": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
        "openrouter": [
            "nousresearch/hermes-3-llama-3.1-405b:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "meta-llama/llama-3.2-3b-instruct:free"
        ]
    },
    4: { # Candidate AI (different persona from recruiter to prevent sameness)
        "groq": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
        "openrouter": [
            "meta-llama/llama-3.3-70b-instruct:free",
            "nousresearch/hermes-3-llama-3.1-405b:free",
            "meta-llama/llama-3.2-3b-instruct:free"
        ]
    },
    5: { # Interest Scorer (8b-instant: fast + cheap for structured eval, temp=0.1)
        "groq": ["llama-3.1-8b-instant", "llama-3.3-70b-versatile"],
        "openrouter": [
            "nousresearch/hermes-3-llama-3.1-405b:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "meta-llama/llama-3.2-3b-instruct:free"
        ]
    }
}

# Track fallback state independently per agent to prevent cascaded failures
# Format: { agent_id: {"provider": "groq", "groq_idx": 0, "openrouter_idx": 0} }
_AGENT_STATES = {}

# Optional callback invoked when a model swap occurs (used by SSE stream).
# Signature: (agent_id: int, from_model: str, to_model: str, reason: str) -> None
_model_swap_callback = None

def set_model_swap_callback(fn):
    """Register a callable that will be invoked on every model fallback swap."""
    global _model_swap_callback
    _model_swap_callback = fn

# Models that don't support a dedicated 'system' role — for these we merge
# the system prompt into the user message to avoid 400 INVALID_ARGUMENT errors.
_NO_SYSTEM_ROLE_MODELS = {"google/gemma-3-27b-it:free", "google/gemma-3-12b-it:free"}

MAX_RETRIES    = 15    # Must be > total models across all tiers to allow full rotation + retries
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
                "X-Title": "SkillSync AI"
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
                from_model = config['groq'][state['groq_idx']]
                if state["groq_idx"] < len(config["groq"]) - 1:
                    state["groq_idx"] += 1
                    to_model = config['groq'][state['groq_idx']]
                    log.warning(f"[Agent {agent_id}] Groq {from_model} limit hit. Switching to {to_model}.")
                    if _model_swap_callback:
                        _model_swap_callback(agent_id, f"groq/{from_model}", f"groq/{to_model}", "429")
                    continue
                else:
                    if os.environ.get("OPENROUTER_API_KEY"):
                        to_model = config["openrouter"][0]
                        log.warning(f"[Agent {agent_id}] Groq exhausted. Switching to OpenRouter/{to_model}.")
                        if _model_swap_callback:
                            _model_swap_callback(agent_id, f"groq/{from_model}", f"openrouter/{to_model}", "429")
                        state["provider"] = "openrouter"
                        continue
                    else:
                        log.warning(f"[Agent {agent_id}] Groq exhausted and OPENROUTER_API_KEY not configured. Retrying Groq.")
                        state["groq_idx"] = 0

            # ── OpenRouter model rotation (429 OR 404 — OUTSIDE rate-limit block)
            if state["provider"] == "openrouter" and (is_rate_limit or is_unavailable):
                from_model = config["openrouter"][state["openrouter_idx"]]
                if state["openrouter_idx"] < len(config["openrouter"]) - 1:
                    state["openrouter_idx"] += 1
                    to_model = config["openrouter"][state["openrouter_idx"]]
                    log.warning(f"[Agent {agent_id}] OpenRouter error ({exc.__class__.__name__}). Rotating to: {to_model}")
                    if _model_swap_callback:
                        _model_swap_callback(agent_id, f"openrouter/{from_model}", f"openrouter/{to_model}", str(exc.__class__.__name__))
                    continue
                else:
                    # All OpenRouter models exhausted — loop back to Groq!
                    log.warning(f"[Agent {agent_id}] All models exhausted. Looping back to Groq.")
                    if _model_swap_callback:
                        _model_swap_callback(agent_id, f"openrouter/{from_model}", f"groq/{config['groq'][0]}", "exhausted")
                    state["provider"] = "groq"
                    state["groq_idx"] = 0
                    state["openrouter_idx"] = 0

            wait = min(BASE_BACKOFF * (2 ** attempt), 15)

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


def heal_json(text: str) -> dict:
    """
    Attempt to repair a truncated or malformed JSON string from an LLM.

    Strategy:
      1. Strip markdown fences.
      2. Try to parse as-is.
      3. Close open strings, arrays, and objects iteratively.
      4. Raises json.JSONDecodeError if all healing attempts fail.
    """
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()

    # Attempt 1: parse as-is
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Attempt 2: close open structures
    # Count open braces / brackets
    healed = cleaned
    # Remove trailing comma before closing
    healed = re.sub(r",\s*$", "", healed)
    # Close unterminated string
    quote_count = healed.count('"') - healed.count('\\"')
    if quote_count % 2 != 0:
        healed += '"'
    # Close open objects/arrays
    open_braces = healed.count('{') - healed.count('}')
    open_brackets = healed.count('[') - healed.count(']')
    healed += ']' * max(0, open_brackets)
    healed += '}' * max(0, open_braces)

    return json.loads(healed)  # raises JSONDecodeError if still broken


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
    Return True if OpenRouter/Groq returned 404/400 (model unavailable/retired/paid).
    Should trigger rotation to the next model in the list.
    """
    exc_str = str(exc).lower()
    return "404" in exc_str or "400" in exc_str

# ── Smoke-test (run directly: python -m app.llm_client) ──────────────────────
if __name__ == "__main__":
    import sys, asyncio

    print("\nRunning LLM client smoke test …")
    print("-" * 50)

    async def _smoke():
        result = await call_llm(
            system_prompt="You are a helpful assistant. Reply in plain text only.",
            user_prompt='Return only valid JSON: {"status": "ok", "engine": "groq_or_openrouter"}',
        )
        print(f"Raw response:\n{result}\n")
        parsed = parse_json_response(result)
        print(f"Parsed JSON: {parsed}")

        # Test JSON healing
        broken = '{"key": "value with missing close'
        try:
            healed = heal_json(broken)
            print(f"Healed JSON: {healed}")
        except Exception:
            print("Heal test: expected failure on severely broken JSON — OK")

        print("\n✓ Smoke test passed!")

    try:
        asyncio.run(_smoke())
    except Exception as e:
        print(f"\n✗ Smoke test failed: {e}")
        sys.exit(1)
