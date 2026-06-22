"""
precompute/utils.py — Shared utility functions used across all precompute steps.

These functions are extracted here so they can be imported normally by:
  - Other precompute scripts
  - sandbox/app.py
  - rank.py (fallback path)

without hitting the Python restriction that prohibits importing files
whose names begin with a digit (01_embed.py, 03_pre_score.py, etc.).

IMPORTANT — Dataset schema
--------------------------
The real candidates.json uses a NESTED schema:
  candidate["profile"]["current_title"]
  candidate["redrob_signals"]["open_to_work_flag"]
  candidate["candidate_id"]          (not "id")

All scoring code expects a FLAT dict. Call normalize_candidate() once
at the point of loading, then pass the flat dict everywhere.
"""

import gzip
import json
import logging
from datetime import datetime, date
from pathlib import Path

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Candidate I/O
# ─────────────────────────────────────────────────────────────────────────────
def load_candidates(path: str) -> list[dict]:
    """Load candidates from .json, .jsonl, or .jsonl.gz file."""
    p = Path(path)
    if not p.exists():
        log.error(f"Candidates file not found: {path}")
        return []

    if p.suffix == ".gz":
        with gzip.open(p, "rt", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    elif p.suffix == ".jsonl":
        with open(p, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    else:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else [data]


def normalize_candidate(raw: dict) -> dict:
    """
    Flatten the real candidates.json nested schema into a flat dict
    that all scoring functions expect.

    Real schema:                          Flat key produced:
      raw["candidate_id"]             →   "id" + "candidate_id"
      raw["profile"]["current_title"] →   "current_title"
      raw["redrob_signals"]["..."]    →   direct flat key
      raw["skills"][i]["name"]        →   kept as-is (already flat list)

    Call this ONCE after loading, pass the result to every scoring function.
    If the candidate is already flat (e.g., from a precomputed artifact),
    it is returned unchanged.
    """
    # If already flat (no "profile" sub-key), assume already normalized
    if "profile" not in raw and "redrob_signals" not in raw:
        return raw

    profile  = raw.get("profile", {})
    signals  = raw.get("redrob_signals", {})

    return {
        # ── Identity ────────────────────────────────────────────────────────
        "id":                        raw.get("candidate_id", raw.get("id", "")),
        "candidate_id":              raw.get("candidate_id", raw.get("id", "")),

        # ── Profile fields ──────────────────────────────────────────────────
        "name":                      profile.get("anonymized_name", ""),
        "headline":                  profile.get("headline", ""),
        "summary":                   profile.get("summary", ""),
        "location":                  profile.get("location", ""),
        "country":                   profile.get("country", ""),
        "years_of_experience":       profile.get("years_of_experience", 0),
        "current_title":             profile.get("current_title", ""),
        "current_company":           profile.get("current_company", ""),
        "current_company_size":      profile.get("current_company_size", ""),
        "current_industry":          profile.get("current_industry", ""),
        # No "seniority" in dataset — derive from YOE
        "seniority":                 _derive_seniority(profile.get("years_of_experience", 0)),

        # ── Redrob signals (behavioral) ─────────────────────────────────────
        "open_to_work":              signals.get("open_to_work_flag", False),
        "last_active_date":          signals.get("last_active_date", ""),
        "notice_period_days":        signals.get("notice_period_days", 60),
        "recruiter_response_rate":   signals.get("recruiter_response_rate", -1),
        "interview_completion_rate": signals.get("interview_completion_rate", -1),
        "offer_acceptance_rate":     signals.get("offer_acceptance_rate", -1),
        "github_activity_score":     signals.get("github_activity_score", -1),
        "skill_assessment_scores":   signals.get("skill_assessment_scores", {}),
        "profile_completeness_score":signals.get("profile_completeness_score", 0),
        "connection_count":          signals.get("connection_count", 0),
        "endorsements_received":     signals.get("endorsements_received", 0),
        "preferred_work_mode":       signals.get("preferred_work_mode", ""),
        "willing_to_relocate":       signals.get("willing_to_relocate", False),

        # Verified signals — combine 3 booleans into the dict format our
        # behavioral scorer expects
        "verified_signals": {
            "email":    signals.get("verified_email", False),
            "phone":    signals.get("verified_phone", False),
            "linkedin": signals.get("linkedin_connected", False),
        },

        # ── Pass-through arrays (already top-level in the dataset) ──────────
        "skills":         raw.get("skills", []),
        "skills_detail":  raw.get("skills", []) or raw.get("skills_detail", []),
        "career_history": raw.get("career_history", []),
        "education":      raw.get("education", []),
        "certifications": raw.get("certifications", []),
        "languages":      raw.get("languages", []),
    }


def _derive_seniority(yoe: float) -> str:
    """Derive a seniority label from years_of_experience (dataset has no seniority field)."""
    yoe = float(yoe or 0)
    if yoe < 1:    return "intern"
    if yoe < 3:    return "junior"
    if yoe < 6:    return "mid"
    if yoe < 10:   return "senior"
    if yoe < 15:   return "lead"
    return "principal"


# ─────────────────────────────────────────────────────────────────────────────
# Profile text builder (used for embedding)
# ─────────────────────────────────────────────────────────────────────────────
def build_profile_text(candidate: dict) -> str:
    """
    Build the text representation of a candidate for embedding.

    Includes (in priority order):
      headline / current_title → summary / bio →
      top-3 career descriptions (capped 400 chars each) →
      top-25 skill names → certification names → open_to_roles
    """
    parts = []

    # Headline / title
    headline = candidate.get("current_title") or candidate.get("headline") or ""
    if headline:
        parts.append(headline)

    # Summary / bio
    summary = candidate.get("bio") or candidate.get("summary") or ""
    if summary:
        parts.append(summary[:800])

    # Career role titles + descriptions (top 3, capped at 400 chars each)
    for role in candidate.get("career_history", [])[:3]:
        if role_title := role.get("title", ""):
            parts.append(role_title)
        if desc := role.get("description", ""):
            parts.append(desc[:400])

    # Skills (top 25 names)
    seen_skills = set()
    skill_names = []
    for s in candidate.get("skills", []) + candidate.get("skills_detail", []):
        name = (s.get("name", "") if isinstance(s, dict) else str(s)).strip()
        if name and name.lower() not in seen_skills:
            seen_skills.add(name.lower())
            skill_names.append(name)
    skill_names = skill_names[:25]
    if skill_names:
        parts.append("Skills: " + " ".join(skill_names))

    # Certification names
    certs = candidate.get("certifications", [])
    cert_names = [c.get("name", c) if isinstance(c, dict) else str(c) for c in certs]
    if cert_names:
        parts.append("Certifications: " + " ".join(cert_names[:10]))

    # Open-to roles
    open_roles = candidate.get("open_to_roles", [])
    if open_roles:
        parts.append("Open to: " + " ".join(open_roles[:10]))

    text = " ".join(p for p in parts if p).strip()
    return text or f"Candidate {candidate.get('id', '')}"


# ─────────────────────────────────────────────────────────────────────────────
# Scoring sub-functions (imported by sandbox/app.py and 03_pre_score.py)
# ─────────────────────────────────────────────────────────────────────────────
def compute_skill_score(candidate: dict, required_skills: list[str], nice_to_have_skills: list[str] = None) -> float:
    """
    Skill overlap score (0–1).

    Calculates:
      skill_score = (req_component × 0.70) + (nth_component × 0.30)
    
    Checks platform assessment scores, duration, endorsements, and proficiency
    multipliers for required and nice-to-have skills. Also scans career history
    descriptions for plain-language mentions.
    """
    if not required_skills and not nice_to_have_skills:
        return 0.5

    # Extract candidate skills
    cand_skills = candidate.get("skills", []) or candidate.get("skills_detail", [])
    
    # Get descriptions text for fallback matching
    desc_text = " ".join(
        (r.get("description", "") or "") for r in candidate.get("career_history", [])
    ).lower()
    
    # Assessment scores from redrob_signals
    assessment_scores = candidate.get("skill_assessment_scores", {})
    if not isinstance(assessment_scores, dict):
        # Handle cases where it is nested inside redrob_signals
        signals = candidate.get("redrob_signals", {})
        if isinstance(signals, dict):
            assessment_scores = signals.get("skill_assessment_scores", {})
    if not isinstance(assessment_scores, dict):
        assessment_scores = {}
        
    def get_skill_match_weight(skill_name: str) -> float:
        s_low = skill_name.lower().strip()
        best_w = 0.0
        
        # 1. Search in candidate skills
        for cs in cand_skills:
            cs_name = (cs.get("name", "") if isinstance(cs, dict) else str(cs)).lower().strip()
            if not cs_name:
                continue
            
            # Case-insensitive substring matching
            if s_low == cs_name or s_low in cs_name or cs_name in s_low:
                w = 1.0
                
                # Platform assessment score bonus
                orig_name = cs.get("name", "") if isinstance(cs, dict) else str(cs)
                score = assessment_scores.get(orig_name, 0)
                if score >= 75:
                    w += 0.50
                elif score >= 50:
                    w += 0.25
                
                # Duration bonus
                dur = int(cs.get("duration_months") or 0) if isinstance(cs, dict) else 0
                if dur >= 36:
                    w += 0.30
                elif dur >= 12:
                    w += 0.15
                
                # Endorsements bonus
                ends = int(cs.get("endorsements") or 0) if isinstance(cs, dict) else 0
                if ends >= 20:
                    w += 0.20
                elif ends >= 5:
                    w += 0.10
                
                # Proficiency multiplier
                prof = str(cs.get("proficiency", "advanced") if isinstance(cs, dict) else "advanced").lower().strip()
                m = 1.0
                if "beginner" in prof:
                    m = 0.50
                elif "intermediate" in prof:
                    m = 0.80
                elif "advanced" in prof:
                    m = 1.00
                elif "expert" in prof:
                    m = 1.20
                
                w = w * m
                if w > best_w:
                    best_w = w
        
        # 2. Fallback to career description scan
        if best_w == 0.0:
            if s_low in desc_text:
                best_w = 0.50
                
        # 3. Operational evidence bonus
        if best_w > 0.0:
            OPERATIONAL_EVIDENCE_KEYWORDS = [
                "production", "deployed", "scale", "drift", "regression", "latency",
                "index refresh", "a/b test", "monitoring", "incident", "rollback"
            ]
            if any(kw in desc_text for kw in OPERATIONAL_EVIDENCE_KEYWORDS):
                best_w *= 1.15
                
        return best_w

    # Calculate req_component
    if required_skills:
        req_weights = [get_skill_match_weight(s) for s in required_skills]
        req_component = min(sum(req_weights) / len(required_skills), 1.0)
    else:
        req_component = 1.0

    # Calculate nth_component
    if nice_to_have_skills:
        nth_matches = sum(1.0 for s in nice_to_have_skills if get_skill_match_weight(s) > 0.0)
        nth_component = min(nth_matches / len(nice_to_have_skills), 1.0)
    else:
        nth_component = 1.0

    # Overall skill_score
    score = (req_component * 0.70) + (nth_component * 0.30)
    return min(1.0, max(0.0, score))


def compute_career_score(candidate: dict, jd_seniority: str) -> float:
    """
    Career quality signal (0–1, capped at 1.0).

    Components (must sum to max 1.0):
      YOE fit (0.25):         5–9 years (+0.25), 3–5 or 9–12 (+0.15), >12 (+0.05), else 0
      Title match (0.30):     title in GOOD_TITLES list (+0.30)
      Industry match (0.15):  software/AI/fintech/saas/data (+0.15)
      Role tenure (0.15):     current role ≥ 18 months (+0.15), ≥ 12 months (+0.10), ≥ 6 months (+0.05)
      GitHub activity (0.15): github_activity_score ≥ 50 (+0.15), ≥ 20 (+0.08), -1 handled gracefully (0 points)
    """
    try:
        from config import GOOD_TITLES
    except ImportError:
        GOOD_TITLES = {"software engineer", "ml engineer", "data scientist", "backend engineer",
                       "ai engineer", "data engineer", "senior engineer"}

    points = 0.0

    # 1. YOE fit (0.25)
    yoe = float(candidate.get("years_of_experience") or 0.0)
    if 5.0 <= yoe <= 9.0:
        points += 0.25
    elif (3.0 <= yoe < 5.0) or (9.0 < yoe <= 12.0):
        points += 0.15
    elif yoe > 12.0:
        points += 0.05

    # 2. Title match (0.30)
    title = (candidate.get("current_title") or "").lower().strip()
    title_match = any(gt in title for gt in GOOD_TITLES)
    if title_match:
        points += 0.30

    # 3. Industry match (0.15)
    industry = (candidate.get("current_industry") or "").lower().strip()
    industry_clean = industry.replace("/", " ").replace("-", " ").replace(",", " ")
    industry_words = {w.strip(".,()/-") for w in industry_clean.split()}
    industry_match = (
        any(t in industry for t in ("software", "fintech", "saas", "data")) or
        "ai" in industry_words or
        "artificial intelligence" in industry
    )
    if industry_match:
        points += 0.15

    # 4. Role tenure (0.15)
    careers = candidate.get("career_history", [])
    tenure_months = 0.0
    for role in careers:
        if role.get("is_current"):
            tenure_months = float(role.get("duration_months") or 0.0)
            break
    if tenure_months == 0.0 and careers:
        tenure_months = float(careers[0].get("duration_months") or 0.0)
    
    if tenure_months >= 18.0:
        points += 0.15
    elif tenure_months >= 12.0:
        points += 0.10
    elif tenure_months >= 6.0:
        points += 0.05

    # 5. GitHub signals (0.15)
    gh_raw = candidate.get("github_activity_score")
    if gh_raw is not None and gh_raw != -1:
        try:
            gh_val = float(gh_raw)
            if gh_val >= 50.0:
                points += 0.15
            elif gh_val >= 20.0:
                points += 0.08
        except (TypeError, ValueError):
            pass

    # 6. Soft penalty for CV/Speech/Robotics without NLP/IR
    CV_SPEECH_ROBOTICS_KEYWORDS = [
        "computer vision", "object detection", "image segmentation",
        "speech recognition", "audio processing", "robotics", "slam",
        "autonomous navigation", "lidar"
    ]
    NLP_IR_KEYWORDS = [
        "nlp", "natural language", "retrieval", "ranking", "embeddings",
        "search", "information retrieval", "recommendation"
    ]

    cand_skills = candidate.get("skills", []) or candidate.get("skills_detail", [])
    skill_names = [s.get("name", "") if isinstance(s, dict) else str(s) for s in cand_skills]
    
    desc_text = " ".join(
        (r.get("description", "") or "") for r in candidate.get("career_history", [])
    ).lower()

    all_skill_and_desc_text = (" ".join(skill_names) + " " + desc_text).lower()

    has_cv_speech_robotics = any(kw in all_skill_and_desc_text for kw in CV_SPEECH_ROBOTICS_KEYWORDS)
    has_nlp_ir = any(kw in all_skill_and_desc_text for kw in NLP_IR_KEYWORDS)

    if has_cv_speech_robotics and not has_nlp_ir:
        points *= 0.70  # moderate reduction, not a hard disqualifier

    return min(1.0, max(0.0, points))


def compute_behavioral_score(candidate: dict) -> float:
    """
    Behavioral readiness signal (0–1, capped at 1.0).

    Components:
      open_to_work_flag (0.25):         true (+0.25)
      last_active_date recency (0.25):  ≤ 7 days (+0.25), ≤ 30 days (+0.20), ≤ 90 days (+0.12), ≤ 180 days (+0.05)
      recruiter_response_rate (0.20):   ≥ 0.70 (+0.20), ≥ 0.50 (+0.15), ≥ 0.30 (+0.10)
      notice_period_days (0.15):        ≤ 30 days (+0.15), ≤ 60 days (+0.10), ≤ 90 days (+0.05)
      interview_completion_rate (0.10): × rate (0.0–1.0)
      verified signals (0.05):          × (email+phone+linkedin) / 3
    """
    points = 0.0

    # 1. open_to_work_flag (0.25)
    otw = bool(candidate.get("open_to_work") or candidate.get("actively_looking"))
    if otw:
        points += 0.25

    # 2. last_active_date recency (0.25)
    la_days = candidate.get("days_since_last_active")
    if la_days is None:
        la_str = candidate.get("last_active_date")
        if la_str:
            for fmt in ("%Y-%m-%d", "%Y-%m", "%d/%m/%Y"):
                try:
                    la_date = datetime.strptime(str(la_str).strip(), fmt).date()
                    la_days = (date.today() - la_date).days
                    break
                except ValueError:
                    continue
    if la_days is not None:
        try:
            la_days = float(la_days)
            if la_days <= 7.0:
                points += 0.25
            elif la_days <= 30.0:
                points += 0.20
            elif la_days <= 90.0:
                points += 0.12
            elif la_days <= 180.0:
                points += 0.05
        except (TypeError, ValueError):
            pass
    else:
        points += 0.20  # Neutral default

    # 3. recruiter_response_rate (0.20)
    rr_raw = candidate.get("recruiter_response_rate") or candidate.get("response_rate")
    if rr_raw is not None and rr_raw != -1:
        try:
            rr = float(rr_raw)
            rr = rr / 100.0 if rr > 1.0 else rr
            if rr >= 0.70:
                points += 0.20
            elif rr >= 0.50:
                points += 0.15
            elif rr >= 0.30:
                points += 0.10
        except (TypeError, ValueError):
            pass

    # 4. notice_period_days (0.15)
    notice = candidate.get("notice_period_days")
    if notice is not None:
        try:
            n_days = int(notice)
            if n_days <= 30:
                points += 0.15
            elif n_days <= 60:
                points += 0.10
            elif n_days <= 90:
                points += 0.05
        except (TypeError, ValueError):
            pass
    else:
        points += 0.10  # Neutral default

    # 5. interview_completion_rate (0.10)
    icr = candidate.get("interview_completion_rate", -1)
    if icr is None or icr == -1:
        icr_score = 0.50
    else:
        try:
            icr_score = max(0.0, min(1.0, float(icr)))
        except (TypeError, ValueError):
            icr_score = 0.50
    points += 0.10 * icr_score

    # 6. verified signals (0.05)
    verified = candidate.get("verified_signals", {})
    if isinstance(verified, dict):
        email = float(bool(verified.get("email")))
        phone = float(bool(verified.get("phone")))
        linkedin = float(bool(verified.get("linkedin")))
    else:
        email = float(bool(candidate.get("verified_email")))
        phone = float(bool(candidate.get("verified_phone")))
        linkedin = float(bool(candidate.get("linkedin_connected")))
    verified_score = (email + phone + linkedin) / 3.0
    points += 0.05 * verified_score

    return min(1.0, max(0.0, points))
