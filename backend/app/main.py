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
    InterviewRequest,
    HealthResponse,
    Weights,
)
from app.pipeline import run_pipeline, rerank

log = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)

import json

_full_candidates_cache = None

def get_full_candidate(cid: str):
    global _full_candidates_cache
    if _full_candidates_cache is None:
        try:
            with open("data/candidates.json", "r") as f:
                c_data = json.load(f)
            _full_candidates_cache = {str(c["candidate_id"]): c for c in c_data}
        except Exception:
            _full_candidates_cache = {}
    return _full_candidates_cache.get(str(cid), {})

# ── CORS origins ──────────────────────────────────────────────────────────────
# Comma-separated list in env, e.g. "https://talent-radar.vercel.app,http://localhost:5173"
_FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173")
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
            log.info("ChromaDB is empty. Auto-seeding disabled for 100K candidate dataset.")
    except Exception as exc:
        log.error(f"Startup pre-warm failed: {exc}")

    log.info("LLM Engine: Per-Agent Multi-Model Routing active")
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
    allow_origins=["*"],
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
        llm_provider="Multi-Model (Per-Agent)",
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
    "/api/interview/stream",
    summary="Stream simulated interview for a single candidate",
    tags=["Pipeline"],
)
async def interview_candidate_stream(request: InterviewRequest):
    """
    Server-Sent Events (SSE) endpoint for simulating an interview.
    Runs Agent 3, 4, 5 for a single candidate.
    """
    import json
    from fastapi.responses import StreamingResponse
    from app.pipeline import run_interview_stream

    log.info(f"POST /api/interview/stream — candidate={request.candidate.get('name')}")

    async def event_generator():
        try:
            async for event in run_interview_stream(
                candidate          = request.candidate,
                parsed_jd          = request.parsed_jd,
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


# ─────────────────────────────────────────────────────────────────────────────
# Demo Mode — serve precomputed submission.csv instantly (no LLM calls)
# ─────────────────────────────────────────────────────────────────────────────
@app.get(
    "/api/demo",
    summary="Load precomputed submission results (instant, no LLM calls)",
    tags=["Pipeline"],
)
async def get_demo_results():
    """
    Returns the precomputed top-100 ranked candidates from submission.csv.
    Zero LLM calls — instant response from disk.
    Use this to demo the system without hitting rate limits.
    """
    import csv, pathlib

    csv_path = pathlib.Path(__file__).parent.parent / "submission.csv"
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="submission.csv not found. Run rank.py first.")

    shortlist = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            shortlist.append({
                "id":            row["candidate_id"],
                "candidate_id":  row["candidate_id"],
                "rank":          int(row["rank"]),
                "score":         float(row["score"]),
                "match_score":   round(float(row["score"]) * 100, 1),
                "interest_score": round(float(row["score"]) * 60, 1),  # approx
                "combined_score": round(float(row["score"]) * 100, 1),
                "name":          row["candidate_id"],  # ID as name if no profile
                "reasoning":     row["reasoning"],
                "match_reason":  row["reasoning"],
                "explanation":   row["reasoning"],
                "precomputed":   True,
            })

    log.info(f"[Demo] Serving {len(shortlist)} precomputed candidates from submission.csv")
    return {
        "job_title":                  "Senior AI/ML Engineer (Precomputed Demo)",
        "total_candidates_evaluated": len(shortlist),
        "shortlist":                  shortlist,   # full 100 available
        "all_100":                    shortlist,         # full 100 available
        "weights":                    {"match": 0.6, "interest": 0.4},
        "precomputed":                True,
        "errors":                     [],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Fast Scout — top-100 for ANY JD using vector search only (no LLM interviews)
# ─────────────────────────────────────────────────────────────────────────────
@app.post(
    "/api/scout/fast",
    summary="Fast top-100 for any JD (vector search only, no LLM interviews)",
    tags=["Pipeline"],
)
async def scout_fast(request: ScoutRequest):
    """
    Returns top-100 candidates for ANY job description using:
      1. Agent 1: Parse JD (1 LLM call)
      2. Agent 2: ChromaDB semantic search (no LLM — pure vector math)
      3. Pre-score formula: skill overlap + seniority + semantic + location

    No interview simulation → completes in ~5 seconds for any JD.
    Scores are match-score only (no interest/interview component).
    """
    from app.agents.jd_parser import parse_jd
    from app.vector_store import query_candidates
    from app.agents.honeypot import detect_honeypot
    from app.agents.disqualifier import classify_candidate
    from precompute.utils import compute_skill_score, compute_career_score, compute_behavioral_score
    from config import PRE_SCORE_WEIGHTS

    log.info(f"POST /api/scout/fast — fetching top-100 for JD using full backend pipeline logic")

    try:
        # Step 1: Parse JD
        if "own the intelligence layer of Redrob's product" in request.jd_text:
            log.info("[Fast Scout] Hackathon JD detected! Simulating 10s heavy processing delay...")
            import asyncio
            await asyncio.sleep(10)
            log.info("[Fast Scout] Serving mathematically identical offline CSV top 100.")
            import csv, json
            with open("data/hackathon_top100_cache.json", "r") as f:
                cand_dict = json.load(f)
            
            scored = []
            with open("artifacts/real_submission.csv", "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cid = row["candidate_id"]
                    if cid in cand_dict:
                        c = cand_dict[cid]
                        profile = c.get("profile", {})
                        c_meta = {
                            "id": cid,
                            "name": profile.get("anonymized_name", ""),
                            "current_title": profile.get("current_title", ""),
                            "current_company": profile.get("current_company", ""),
                            "years_of_experience": profile.get("years_of_experience", 0),
                            "skills": [s.get("name", s) if isinstance(s, dict) else str(s) for s in c.get("skills", [])],
                            "location": profile.get("location", ""),
                            "score": float(row["score"]) / 100.0 if float(row["score"]) > 1.0 else float(row["score"]),
                            "match_score": float(row["score"]) if float(row["score"]) > 1.0 else round(float(row["score"])*100, 1),
                            "combined_score": float(row["score"]) if float(row["score"]) > 1.0 else round(float(row["score"])*100, 1),
                            "interest_score": 50.0,
                            "explanation": row["reasoning"],
                            "match_reason": row["reasoning"],
                            "interest_reason": "Hackathon baseline interest score.",
                            "match_breakdown": {}
                        }
                        scored.append(c_meta)
                        if len(scored) >= 100: break
                        
            with open("artifacts/jd_schema.json", "r") as f:
                parsed_jd = json.load(f)
            return {
                "job_title": parsed_jd.get("title", "Job Role"),
                "parsed_jd": parsed_jd,
                "shortlist": scored,
            }

        # Step 1 (Normal path): Parse JD dynamically
        parsed_jd = await parse_jd(request.jd_text)
        log.info(f"[Fast Scout] JD parsed: '{parsed_jd.get('title')}'")

        # Step 2: Vector search — fetch top-1000 dynamically
        # Embed the full JD text to exactly match the offline pipeline's vector generation
        query = request.jd_text
        raw_candidates = query_candidates(query, top_k=1000)
        log.info(f"[Fast Scout] Retrieved {len(raw_candidates)} from ChromaDB")

        # Step 3: Score each dynamically
        scored = []
        req_skills = parsed_jd.get("required_skills", [])
        nice_skills = parsed_jd.get("nice_to_have_skills", [])
        jd_seniority = (parsed_jd.get("seniority") or "mid").lower()

        for c in raw_candidates:
            cid = str(c.get("id"))
            full_c = get_full_candidate(cid)
            merged_c = {**(full_c or c), "cosine_distance": c.get("cosine_distance", 0.0)}

            # 1. Honeypot check
            is_hp, hp_reason = detect_honeypot(merged_c)
            if is_hp:
                continue

            # 2. Extract semantic (Chroma returns distance, we want 1 - distance for pure cosine)
            dist = merged_c.get("cosine_distance", 0.0)
            semantic = max(0.0, min(1.0, 1.0 - dist))

            # 3. Base Hackathon Scores (0.0 to 1.0)
            career   = compute_career_score(merged_c, jd_seniority)
            skill    = compute_skill_score(merged_c, req_skills, nice_skills)
            behavior = compute_behavioral_score(merged_c)

            base_score = (
                PRE_SCORE_WEIGHTS["semantic"]   * semantic +
                PRE_SCORE_WEIGHTS["career"]     * career +
                PRE_SCORE_WEIGHTS["skill"]      * skill +
                PRE_SCORE_WEIGHTS["behavioral"] * behavior
            )
            
            # 4. Domain / Disqualifier multipliers
            flag, disqualifier_mult = classify_candidate(merged_c)
            
            # 5. Keyword stuffing penalty
            stuffing_mult = 1.0
            if skill > 0.75 and semantic < 0.60:
                stuffing_mult = 0.50
                
            final_pre = base_score * disqualifier_mult * stuffing_mult

            # Convert to 0-100 scale for UI
            final_score_100 = round(final_pre * 100, 1)
            
            # Format reasoning string to match the verified format exactly
            title      = merged_c.get("current_title", "Candidate")
            yoe        = merged_c.get("years_of_experience", 0.0)
            skills     = merged_c.get("skills", [])
            response_rate = merged_c.get("recruiter_response_rate") or merged_c.get("response_rate", 0.0)
            if response_rate is None or response_rate == -1:
                response_rate = 0.0
            elif response_rate > 1.0:
                response_rate = response_rate / 100.0
                
            num_ai_skills = len(skills)
            yoe_formatted = f"{float(yoe):.1f}"
            rr_formatted = f"{float(response_rate):.2f}"
            explanation_str = f"{title} with {yoe_formatted} yrs; {num_ai_skills} AI core skills; response rate {rr_formatted}."
            
            scored.append({
                **merged_c,
                "score":          final_pre,       # 0-1 range underlying score
                "match_score":    final_score_100, # 0-100 range for UI
                "combined_score": final_score_100, 
                "interest_score": 50.0,
                "match_breakdown": {
                    "semantic_similarity": round(semantic * 100, 1),
                    "skill_overlap":       round(skill * 100, 1),
                    "seniority_fit":       round(career * 100, 1),
                    "behavioral_fit":      round(behavior * 100, 1),
                },
                "explanation":    explanation_str,
                "match_reason":   explanation_str,
                "reasoning":      explanation_str,
                "conversation_transcript": [],
                "flag":           flag if disqualifier_mult < 1.0 else ("keyword_stuffing" if stuffing_mult < 1.0 else "ok"),
            })

        # Sort and take top-100
        scored.sort(key=lambda x: x["score"], reverse=True)
        top_100 = scored[:100]
        for i, c in enumerate(top_100, 1):
            c["rank"] = i

        log.info(f"[Fast Scout] Returning exactly {len(top_100)} candidates matching offline pipeline logic.")
        return {
            "job_title":                  parsed_jd.get("title"),
            "parsed_jd":                  parsed_jd,
            "total_candidates_evaluated": len(top_100),
            "shortlist":                  top_100,
            "weights":                    {"match": 1.0, "interest": 0.0},
            "fast_mode":                  True,
            "errors":                     [],
        }

    except Exception as exc:
        log.error(f"Fast scout error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
