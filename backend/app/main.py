"""
main.py — TalentRadar FastAPI application.

Endpoints
---------
  POST /api/scout    Run the full 5-agent pipeline for a job description.
  POST /api/rerank   Re-rank an existing shortlist with new weights (no LLM calls).
  GET  /api/health   Liveness + readiness check.

Startup
-------
  On startup the embedding model and ChromaDB client are pre-warmed so the
  first /api/scout request is not delayed by model loading.

CORS
----
  Configured to allow all origins in development.
  Set ALLOWED_ORIGINS env var to restrict to specific domains in production
  (e.g. your Vercel frontend URL).
"""

import logging
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.models import (
    ScoutRequest, ScoutResponse,
    RerankRequest, RerankResponse,
    HealthResponse,
    Weights,
)
from app.pipeline import run_pipeline, rerank
from app.llm_client import PROVIDER

log = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)

# ── CORS origins ──────────────────────────────────────────────────────────────
# Comma-separated list in env, e.g. "https://talent-radar.vercel.app,http://localhost:5173"
_FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
ALLOWED_ORIGINS = [o.strip() for o in _FRONTEND_URL.split(",")]


# ─────────────────────────────────────────────────────────────────────────────
# Lifespan: pre-warm expensive singletons at startup
# ─────────────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-warm the embedding model and ChromaDB connection on startup."""
    log.info("=" * 60)
    log.info("TalentRadar API — starting up …")

    try:
        # Pre-warm embedding model (downloads ~80 MB on first run, then cached)
        from app.vector_store import _embedding_fn, collection_count
        count = collection_count()
        log.info(f"ChromaDB ready — {count} candidates indexed.")

        if count == 0:
            log.warning("ChromaDB is empty! Ensure the build step embedded the candidates.")
    except Exception as exc:
        log.error(f"Startup pre-warm failed: {exc}")

    log.info(f"LLM provider: {PROVIDER.upper()}")
    log.info("TalentRadar API ready.")
    log.info("=" * 60)

    yield  # Application runs here

    log.info("TalentRadar API — shutting down.")


# ─────────────────────────────────────────────────────────────────────────────
# App factory
# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="TalentRadar API",
    description=(
        "AI-powered talent scouting and engagement agent. "
        "Takes a raw Job Description and returns a ranked shortlist of candidates "
        "scored on Match Score (skills/seniority) and Interest Score (conversation analysis)."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Global exception handler
# ─────────────────────────────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error(f"Unhandled exception on {request.method} {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.get(
    "/api/health",
    response_model=HealthResponse,
    summary="Health check",
    tags=["System"],
)
async def health_check():
    """
    Liveness and readiness probe.

    Returns the LLM provider in use and the number of candidates currently
    indexed in ChromaDB. A `candidates_indexed` value of 0 means
    `embed_candidates.py` has not been run yet.
    """
    try:
        from app.vector_store import collection_count
        count = collection_count()
        db_status = "ok"
    except Exception as exc:
        count = -1
        db_status = f"error: {exc}"

    return HealthResponse(
        status="ok",
        chromadb=db_status,
        llm_provider=PROVIDER,
        candidates_indexed=count,
    )


@app.post(
    "/api/scout",
    response_model=ScoutResponse,
    summary="Scout and rank candidates for a job description",
    tags=["Pipeline"],
)
async def scout_candidates(request: ScoutRequest):
    """
    Run the full TalentRadar pipeline:

    1. **Agent 1** — Parse the raw JD into structured JSON.
    2. **Agent 2** — Semantic search over ChromaDB → top-K candidates + Match Scores.
    3. **Agents 3+4** — Simulate a screening conversation per candidate.
    4. **Agent 5** — Score each transcript → Interest Score + explanation.
    5. **Pipeline** — Combine scores, sort, rank.

    ⚠️ This endpoint makes ~14 LLM calls per candidate (6-turn conversation).
    With `top_k=5` expect ~2-5 minutes.
    """
    import asyncio

    log.info(
        f"POST /api/scout — top_k={request.top_k} "
        f"match_weight={request.match_weight} "
        f"turns={request.conversation_turns}"
    )
    log.info(f"JD preview: {request.jd_text[:120].strip()} …")

    try:
        # run_pipeline is now async and parallelized.
        result = await run_pipeline(
            jd_text            = request.jd_text,
            top_k              = request.top_k,
            match_weight       = request.match_weight,
            conversation_turns = request.conversation_turns,
        )
        return result

    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        log.error(f"Pipeline error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post(
    "/api/scout/stream",
    summary="Stream scout and rank candidates",
    tags=["Pipeline"],
)
async def scout_candidates_stream(request: ScoutRequest):
    """
    Server-Sent Events (SSE) endpoint for the TalentRadar pipeline.
    Yields real-time events as candidates are processed.
    """
    import json
    from fastapi.responses import StreamingResponse
    from app.pipeline import run_pipeline_stream

    log.info(f"POST /api/scout/stream — top_k={request.top_k}")

    async def event_generator():
        try:
            async for event in run_pipeline_stream(
                jd_text            = request.jd_text,
                top_k              = request.top_k,
                match_weight       = request.match_weight,
                conversation_turns = request.conversation_turns,
            ):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:
            log.error(f"Stream error: {exc}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post(
    "/api/rerank",
    response_model=RerankResponse,
    summary="Re-rank an existing shortlist with new weights",
    tags=["Pipeline"],
)
async def rerank_shortlist(request: RerankRequest):
    """
    Re-rank an existing shortlist using new match/interest weights.

    **No LLM calls** — this is pure Python arithmetic on the cached scores.
    Called by the frontend weight sliders for live re-ranking without
    triggering a new pipeline run.

    Returns the same shortlist with updated `combined_score` and `rank` fields.
    """
    if not request.shortlist:
        raise HTTPException(status_code=422, detail="shortlist must not be empty.")

    log.info(
        f"POST /api/rerank — {len(request.shortlist)} candidates, "
        f"match_weight={request.match_weight}"
    )

    try:
        reranked = rerank(request.shortlist, request.match_weight)
        return RerankResponse(
            shortlist=reranked,
            weights=Weights(
                match=round(request.match_weight, 2),
                interest=round(1.0 - request.match_weight, 2),
            ),
        )
    except Exception as exc:
        log.error(f"Rerank error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
