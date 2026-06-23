"""
config.py — SkillSync AI Central Configuration.

All weights, thresholds, model names, consulting firm lists,
disqualifier title lists, and scoring constants live here.
Nothing is hardcoded anywhere else.

Usage:
    from config import (
        SCORING_WEIGHTS, DISQUALIFIER_MULTIPLIERS,
        CONSULTING_FIRMS, WRONG_DOMAIN_TITLES,
        GROQ_MODELS, OPENROUTER_MODELS,
        TOP_K_INTERVIEW, TOP_K_FINAL,
    )
"""

# ── Hackathon output constraints ───────────────────────────────────────────────
TOP_K_FINAL     = 100       # rows in submission.csv
TOP_K_INTERVIEW = 40        # candidates who get interview simulation
TOP_K_CHROMA    = 200       # over-fetch from ChromaDB before re-ranking

# Max honeypot rate in top-100 before Stage 3 disqualification
HONEYPOT_MAX_RATE = 0.10    # 10%

# ── Embedding model ────────────────────────────────────────────────────────────
EMBEDDING_MODEL  = "all-MiniLM-L6-v2"   # ~80 MB, 384-dim, CPU-friendly
EMBEDDING_DIM    = 384

# ── LLM models ─────────────────────────────────────────────────────────────────
# Agent-specific model preferences (indexed by agent_id 1–5)
GROQ_MODELS = {
    "primary":   "llama-3.3-70b-versatile",
    "secondary": "llama-3.1-8b-instant",
}

OPENROUTER_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",      # primary fallback
    "nousresearch/hermes-3-llama-3.1-405b:free",   # hermes-3-70b equivalent
    "mistralai/mistral-nemo:free",                  # mistral-nemo (spec)
    "google/gemma-2-9b-it:free",                    # gemma-2-9b (spec)
    "meta-llama/llama-3.2-3b-instruct:free",       # final fallback
]

# ── Pre-interview scoring weights ──────────────────────────────────────────────
# pre_score = semantic × 0.30 + skill × 0.30 + career × 0.20 + behavioral × 0.20
PRE_SCORE_WEIGHTS = {
    "semantic":   0.30,   # cosine similarity JD embed ↔ profile embed
    "skill":      0.30,   # required skills weighted by assessments
    "career":     0.20,   # product company, title fit, YOE 5-9, GitHub
    "behavioral": 0.20,   # open_to_work, last_active, response_rate, notice
}
assert abs(sum(PRE_SCORE_WEIGHTS.values()) - 1.0) < 1e-6, (
    f"Scoring weights must sum to 1.0, got {sum(PRE_SCORE_WEIGHTS.values())}"
)

# ── Final score fusion ─────────────────────────────────────────────────────────
# For top-40 (interviewed): final = pre × 0.60 + interview × 0.40
# For rank 41-100 (not interviewed): final = pre_score
FINAL_SCORE_WEIGHTS = {
    "pre_interview": 0.60,
    "interview":     0.40,
}

# ── Match score (real-time pipeline, Agent 2) ──────────────────────────────────
MATCH_SCORE_WEIGHTS = {
    "skill_overlap":      0.40,
    "seniority_fit":      0.20,
    "semantic_similarity": 0.30,
    "location_fit":       0.10,
}

# ── Agent 5 interview score dimensions ──────────────────────────────────────
# Each dimension scored 0-10 by LLM, then normalized to 0.0-1.0
# Weights must sum to 1.00
INTERVIEW_SCORE_DIMS = {
    "technical_depth":    0.30,   # specific algorithms, architectures, trade-offs
    "production_mindset": 0.25,   # scale, reliability, monitoring, SLAs, oncall
    "domain_relevance":   0.20,   # alignment with JD domain (fintech/AI/SaaS)
    "communication":      0.15,   # clarity, structure, conciseness
    "motivation_signal":  0.10,   # genuine interest in THIS specific role
}   # sum = 1.00

# Legacy alias (kept for backward compatibility)
INTEREST_SCORE_DIMS = INTERVIEW_SCORE_DIMS

# ── Seniority ladder ──────────────────────────────────────────────────────────
SENIORITY_LADDER = ["intern", "junior", "mid", "senior", "lead", "principal"]

# ── Location fit scores ────────────────────────────────────────────────────────
LOCATION_FIT = {
    "same_city":    100,
    "both_remote":   85,
    "mismatch":      10,
}

# ── Honeypot detection thresholds ─────────────────────────────────────────────
HONEYPOT_DURATION_SLACK_YEARS  = 1.5   # single company duration > YOE + 1.5 → honeypot
HONEYPOT_TOTAL_DURATION_SLACK  = 3     # sum of all durations > (YOE + 3) × 12 months
HONEYPOT_EXPERT_SKILL_COUNT    = 10    # ≥ 10 expert skills with < 12 months total → honeypot
HONEYPOT_EXPERT_TOTAL_MONTHS   = 12    # threshold for above rule

# ── Disqualifier multipliers ───────────────────────────────────────────────────
DISQUALIFIER_MULTIPLIERS = {
    "ok":               1.00,
    "consulting_only":  0.25,
    "wrong_domain":     0.40,
    "honeypot":         0.00,
}

# ── Consulting / IT services firms (entire career here → consulting_only) ──────
CONSULTING_FIRMS = {
    "tcs", "tata consultancy", "infosys", "wipro", "accenture",
    "cognizant", "capgemini", "hcl", "hcl technologies", "tech mahindra",
    "mphasis", "hexaware", "ltimindtree", "lti", "mindtree",
    "niit technologies", "mastech", "kpit", "cyient", "persistent",
    "zensar", "mphasis", "birlasoft", "syntel", "igate",
}

# ── Wrong domain titles (current_title → wrong_domain multiplier) ─────────────
WRONG_DOMAIN_TITLES = {
    "marketing manager", "marketing executive", "brand manager",
    "hr manager", "human resources manager", "hr executive",
    "accountant", "chartered accountant", "finance manager",
    "civil engineer", "structural engineer", "mechanical engineer",
    "electrical engineer", "chemical engineer", "industrial engineer",
    "content writer", "copywriter", "content creator",
    "graphic designer", "ui designer", "ux designer", "visual designer",
    "project manager", "program manager",
    "customer support", "customer service", "customer success manager",
    "sales manager", "sales executive", "business development manager",
    "supply chain manager", "logistics manager", "procurement manager",
    "teacher", "professor", "lecturer",
    "doctor", "nurse", "pharmacist",
}

# (NOTICE_PERIOD defined below near BEHAVIORAL_WEIGHTS where it is used)

# ── YOE target range for this hackathon's JD ──────────────────────────────────
YOE_TARGET_MIN = 5
YOE_TARGET_MAX = 9

# ── Behavioral scoring weights ────────────────────────────────────────────────
# Sub-components of behavioral_score (weighted sum = behavioral_score 0-1)
# Must sum to 1.00 (but we allow fractional components)
BEHAVIORAL_WEIGHTS = {
    "open_to_work":              0.25,   # actively looking (+0.25)
    "last_active":               0.25,   # ≤7d=0.25, ≤30d=0.20, ≤90d=0.12, ≤180d=0.05
    "response_rate":             0.20,   # recruiter response rate
    "notice_period":             0.15,   # shorter = better
    "interview_completion_rate": 0.10,   # shows hiring seriousness
    "verified_signals":          0.05,   # email+phone+linkedin / 3
}   # sum = 1.00

# ── Notice period scoring thresholds (days) ─────────────────────────────────
# Used inside behavioral_score calculation
NOTICE_PERIOD = {
    "ideal_max":   30,   # ≤ 30 days → full notice score
    "ok_max":      60,   # 31–60 days → partial
    "long":        90,   # 61–90 days → low
}

# ── Career scoring — Good titles (ML/AI/Data Engineering focus) ──────────────
GOOD_TITLES = {
    # ML/AI
    "machine learning", "ml engineer", "ai engineer", "deep learning",
    "data scientist", "research engineer", "nlp engineer", "computer vision",
    "applied scientist", "research scientist",
    # Data Engineering
    "data engineer", "analytics engineer", "platform engineer",
    # Backend / Platform (also relevant)
    "backend engineer", "software engineer", "software developer",
    "senior engineer", "staff engineer", "principal engineer",
    "fullstack engineer", "systems engineer",
    # Leadership
    "tech lead", "engineering manager", "vp engineering", "cto",
}

# Good industries for career_score (industry match signal)
GOOD_INDUSTRIES = {
    "fintech", "financial technology", "payments", "lending",
    "saas", "software", "ai", "artificial intelligence",
    "edtech", "healthtech", "deep tech", "machine learning",
    "data analytics", "cloud", "cybersecurity",
}

# ── Career scoring weights ────────────────────────────────────────────────────
CAREER_WEIGHTS = {
    "product_company": 0.40,   # worked at product company (not consulting)
    "title_seniority": 0.30,   # title matches JD seniority
    "yoe_fit":         0.20,   # YOE in target range
    "github_signals":  0.10,   # has GitHub / open source activity
}

# ── ChromaDB ──────────────────────────────────────────────────────────────────
CHROMA_COLLECTION  = "candidates"
CHROMA_PERSIST_DIR = "./chroma_data"

# ── Precompute artifact paths ─────────────────────────────────────────────────
PRECOMPUTED_SCORES_FILE = "./artifacts/precomputed_scores.pkl"
EMBEDDINGS_FILE         = "./artifacts/embeddings.npy"
CANDIDATE_IDS_FILE      = "./artifacts/candidate_ids.pkl"
JD_SCHEMA_FILE          = "./artifacts/jd_schema.json"
SCOUT_RESULTS_FILE      = "./artifacts/scout_results.json"
INTERVIEWS_DIR          = "./artifacts/interviews"
SCORES_DIR              = "./artifacts/scores"

# ── Submission CSV columns (in exact order required by hackathon spec) ─────────
SUBMISSION_COLUMNS = ["candidate_id", "rank", "score", "reasoning"]
