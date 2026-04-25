"""
models.py — Pydantic request/response schemas for the TalentRadar API.

All models used by FastAPI endpoints live here so they can be imported
by both main.py (for route declarations) and any test scripts.
"""

from pydantic import BaseModel, Field
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Request models
# ─────────────────────────────────────────────────────────────────────────────

class ScoutRequest(BaseModel):
    """Request body for POST /api/scout."""
    jd_text: str = Field(
        ...,
        min_length=50,
        description="Raw job description text. Must be at least 50 characters.",
        examples=[
            "We are hiring a Senior Backend Engineer for our fintech team in Bangalore. "
            "Required: Python, FastAPI, PostgreSQL, Docker. 5+ years experience. "
            "Hybrid role. Salary ₹20L–₹35L."
        ],
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=15,
        description="Number of candidates to evaluate end-to-end (1–15).",
    )
    match_weight: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Weight for Match Score in combined ranking (0.0–1.0). Interest weight = 1 − match_weight.",
    )
    conversation_turns: int = Field(
        default=6,
        ge=2,
        le=10,
        description="Number of recruiter↔candidate turns per simulation (2–10).",
    )


class RerankRequest(BaseModel):
    """Request body for POST /api/rerank — re-rank without LLM calls."""
    shortlist: list[dict] = Field(
        ...,
        description="The 'shortlist' list from a previous /api/scout response.",
    )
    match_weight: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="New match weight (0.0–1.0). Interest weight = 1 − match_weight.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Nested response sub-models
# ─────────────────────────────────────────────────────────────────────────────

class MatchBreakdown(BaseModel):
    """Sub-score breakdown for the Match Score (Agent 2)."""
    skill_overlap:       float = Field(description="0–100: % of required skills found in candidate's profile.")
    seniority_fit:       float = Field(description="0–100: seniority ladder delta score.")
    semantic_similarity: float = Field(description="0–100: ChromaDB cosine similarity, normalised.")
    location_fit:        int   = Field(description="100 (same city) | 85 (both remote) | 10 (mismatch).")


class InterestBreakdown(BaseModel):
    """Sub-score breakdown for the Interest Score (Agent 5)."""
    enthusiasm:          int = Field(description="0–30: positive tone and excitement in conversation.")
    proactive_questions: int = Field(description="0–25: thoughtful questions asked by the candidate.")
    salary_alignment:    int = Field(description="0–25: salary expectation vs JD range.")
    availability:        int = Field(description="0–20: notice period and start timeline mentioned.")


class ConversationMessage(BaseModel):
    """A single turn in the conversation transcript."""
    role:    str = Field(description="'recruiter' or 'candidate'.")
    turn:    int = Field(description="Turn number, 1-indexed.")
    message: str = Field(description="The message content.")


class CandidateResult(BaseModel):
    """A single candidate entry in the shortlist."""
    rank:                    int
    candidate_id:            str   = Field(alias="id")
    name:                    str
    current_title:           str
    current_company:         str
    seniority:               str
    years_of_experience:     int
    location:                str
    remote_ok:               bool
    skills:                  list[str]
    email:                   Optional[str] = None

    match_score:             float
    match_breakdown:         MatchBreakdown
    match_reason:            str

    interest_score:          int
    interest_breakdown:      InterestBreakdown

    combined_score:          float
    explanation:             str
    conversation_transcript: list[ConversationMessage]

    class Config:
        populate_by_name = True


class SalaryRange(BaseModel):
    min:      int
    max:      int
    currency: str


class ParsedJD(BaseModel):
    """Structured representation of the parsed job description."""
    title:               Optional[str]              = None
    required_skills:     list[str]                  = []
    nice_to_have_skills: list[str]                  = []
    seniority:           Optional[str]              = None
    domain:              Optional[str]              = None
    location:            Optional[str]              = None
    remote_ok:           bool                       = False
    salary_range:        Optional[SalaryRange]      = None
    must_haves:          list[str]                  = []


class Weights(BaseModel):
    match:    float
    interest: float


# ─────────────────────────────────────────────────────────────────────────────
# Top-level response models
# ─────────────────────────────────────────────────────────────────────────────

class ScoutResponse(BaseModel):
    """Response body for POST /api/scout."""
    job_title:                  Optional[str]
    parsed_jd:                  dict          # kept as dict for flexibility
    total_candidates_evaluated: int
    shortlist:                  list[dict]    # list of candidate result dicts
    weights:                    Weights
    errors:                     list[str]     = []


class RerankResponse(BaseModel):
    """Response body for POST /api/rerank."""
    shortlist: list[dict]
    weights:   Weights


class HealthResponse(BaseModel):
    """Response body for GET /api/health."""
    status:     str
    chromadb:   str
    llm_provider: str
    candidates_indexed: int
