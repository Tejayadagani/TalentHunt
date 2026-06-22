"""
vector_store.py — ChromaDB initialisation and query helpers.

This module is the single point of contact for all vector DB operations.
It is imported by:
  - scripts/embed_candidates.py  (to write embeddings once)
  - app/agents/talent_scout.py   (to query at runtime)
"""

import os
# DISABLE CHROMADB TELEMETRY IMMEDIATELY
os.environ["ANONYMIZED_TELEMETRY"] = "False"

import chromadb
from chromadb.api import ClientAPI
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from typing import Any

# chromadb.Collection is the correct public type alias in 0.5.x.
# (chromadb.api.models.Collection.Collection was removed in 0.5).
Collection = chromadb.Collection

# ── Constants ─────────────────────────────────────────────────────────────────
COLLECTION_NAME = "candidates"
EMBEDDING_MODEL  = "all-MiniLM-L6-v2"      # ~80 MB, downloads once
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")

# Loaded once at import time so it is warm for every request.
# Type is EmbeddingFunction[Documents]; we call it with list[str] → list[list[float]].
print(f"[vector_store] Loading default ONNX embedding model '{EMBEDDING_MODEL}' …")
_embedding_fn: embedding_functions.EmbeddingFunction = embedding_functions.DefaultEmbeddingFunction()  # type: ignore[type-arg]
print("[vector_store] Embedding model ready.")


# ── ChromaDB client ────────────────────────────────────────────────────────────
def _get_client() -> ClientAPI:
    """Return a persistent ChromaDB client pointed at CHROMA_PERSIST_DIR."""
    return chromadb.PersistentClient(
        path=CHROMA_PERSIST_DIR,
        settings=Settings(anonymized_telemetry=False),
    )


def get_or_create_collection() -> Collection:
    """
    Return the 'candidates' collection (creates it if it doesn't exist yet).
    Uses cosine distance so similarity is intuitive (higher = more similar).
    """
    client = _get_client()
    collection: Collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},   # cosine distance: range 0–2
    )
    return collection


# ── Embedding helper ───────────────────────────────────────────────────────────
def embed_text(text: str) -> list[float]:
    """Embed a single string and return a plain Python list of floats.

    sentence-transformers 3.x returns np.float32 elements; ChromaDB 0.5
    requires plain Python float. We cast each element explicitly.
    """
    result = _embedding_fn([text])              # list[list[np.float32]]
    return [float(x) for x in result[0]]       # np.float32 → Python float


def _safe_list(value: Any) -> list[str]:
    """Convert a value that may be a list or comma-joined string back to a list."""
    if isinstance(value, list):
        return [str(v) for v in value if v]
    if isinstance(value, str):
        return [s for s in value.split(",") if s]
    return []


def build_candidate_text(candidate: dict) -> str:
    """
    Build the text representation of a candidate that will be embedded.
    Combines bio + skills so both semantic meaning and keywords are captured.
    """
    skills_str = " ".join(_safe_list(candidate.get("skills", [])))
    bio        = candidate.get("bio", "")
    title      = candidate.get("current_title", "")
    seniority  = candidate.get("seniority", "")
    domain     = " ".join(_safe_list(candidate.get("open_to_roles", [])))
    career     = candidate.get("career_history_text", "")
    return f"{title} {seniority} {bio} Career: {career} Skills: {skills_str} Roles: {domain}"


# ── Write helpers (used by embed_candidates.py) ────────────────────────────────
def upsert_candidate(collection: Collection, candidate: dict) -> None:
    """
    Embed and upsert a single candidate profile into the collection.
    Uses candidate['id'] as the document ID so re-running is idempotent.
    """
    text      = build_candidate_text(candidate)
    embedding = embed_text(text)

    # Store a minimal metadata snapshot alongside the vector so we can
    # reconstruct the candidate object directly from a query result.
    metadata = {
        "id":                  candidate["id"],
        "name":                candidate["name"],
        "current_title":       candidate.get("current_title", ""),
        "current_company":     candidate.get("current_company", ""),
        "seniority":           candidate.get("seniority", ""),
        "years_of_experience": candidate.get("years_of_experience", 0),
        "location":            candidate.get("location", ""),
        "remote_ok":           str(candidate.get("remote_ok", False)),
        "skills":              ",".join(_safe_list(candidate.get("skills", []))),
        "salary_expectation_inr": candidate.get("salary_expectation_inr", 0),
        "notice_period_days":  candidate.get("notice_period_days", 30),
        "interest_level":      candidate.get("interest_level", 3),   # private — not in output
        "open_to_roles":       ",".join(_safe_list(candidate.get("open_to_roles", []))),
        "email":               candidate.get("email", ""),
        "bio":                 candidate.get("bio", ""),
        "career_history_text": candidate.get("career_history_text", ""),
        "recruiter_response_rate": candidate.get("recruiter_response_rate", 1.0),
        "last_active_date":    candidate.get("last_active_date", "")
    }

    collection.upsert(
        ids=[candidate["id"]],
        embeddings=[embedding],
        documents=[text],
        metadatas=[metadata],
    )


def upsert_candidates_batch(collection: Collection, candidates: list[dict]) -> None:
    """Batch version of upsert_candidate to drastically improve ingestion speed."""
    if not candidates:
        return
        
    ids = []
    texts = []
    metadatas = []
    
    for candidate in candidates:
        text = build_candidate_text(candidate)
        
        metadata = {
            "id":                  candidate["id"],
            "name":                candidate["name"],
            "current_title":       candidate.get("current_title", ""),
            "current_company":     candidate.get("current_company", ""),
            "seniority":           candidate.get("seniority", ""),
            "years_of_experience": candidate.get("years_of_experience", 0),
            "location":            candidate.get("location", ""),
            "remote_ok":           str(candidate.get("remote_ok", False)),
            "skills":              ",".join(_safe_list(candidate.get("skills", []))),
            "salary_expectation_inr": candidate.get("salary_expectation_inr", 0),
            "notice_period_days":  candidate.get("notice_period_days", 30),
            "interest_level":      candidate.get("interest_level", 3),
            "open_to_roles":       ",".join(_safe_list(candidate.get("open_to_roles", []))),
            "email":               candidate.get("email", ""),
            "bio":                 candidate.get("bio", ""),
            "career_history_text": candidate.get("career_history_text", ""),
            "recruiter_response_rate": candidate.get("recruiter_response_rate", 1.0),
            "last_active_date":    candidate.get("last_active_date", "")
        }
        
        ids.append(candidate["id"])
        texts.append(text)
        metadatas.append(metadata)
        
    embeddings = _embedding_fn(texts)
    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas,
    )


# ── Read helpers (used by talent_scout.py) ─────────────────────────────────────
def query_candidates(query_text: str, top_k: int = 15) -> list[dict]:
    """
    Embed query_text and return the top_k most similar candidates.

    Each returned dict contains all metadata fields plus:
      - 'cosine_distance':    raw ChromaDB distance value  (0 = identical, 2 = opposite)
      - 'semantic_similarity': normalised 0–100 score      (higher = more similar)

    NOTE: ChromaDB cosine distance range is 0–2.
    Conversion: similarity = max(0, (1 - distance / 2) * 100)
    """
    collection = get_or_create_collection()

    if collection.count() == 0:
        raise RuntimeError(
            "ChromaDB collection is empty. "
            "Run `python scripts/embed_candidates.py` first."
        )

    query_embedding = embed_text(query_text)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, collection.count()),
        include=["metadatas", "distances", "documents"],
    )

    candidates: list[dict] = []

    # results["metadatas"] and results["distances"] are Optional[list[list[...]]]
    # Guard against None (empty collection edge-case).
    raw_metadatas = results.get("metadatas") or []
    raw_distances = results.get("distances") or []

    metadatas = list(raw_metadatas[0]) if raw_metadatas else [] # type: ignore
    distances = list(raw_distances[0]) if raw_distances else [] # type: ignore

    for meta, distance in zip(metadatas, distances):
        # ChromaDB 0.5.x can occasionally return a raw string for a metadata
        # entry if the document was stored without a metadata dict. Skip those.
        if not isinstance(meta, dict):
            print(f"[vector_store] Skipping non-dict metadata entry: {type(meta)}")
            continue

        # Reconstruct the candidate dict from stored metadata
        candidate: dict[str, Any] = dict(meta)

        def _safe_int(val: Any, default: int = 0) -> int:
            try:
                return int(float(str(val))) if val is not None else default
            except (ValueError, TypeError):
                return default

        # Convert comma-separated strings back to lists safely
        candidate["skills"]        = _safe_list(meta.get("skills"))
        candidate["open_to_roles"] = _safe_list(meta.get("open_to_roles"))
        candidate["remote_ok"]     = str(meta.get("remote_ok")).lower() == "true"
        candidate["years_of_experience"] = _safe_int(meta.get("years_of_experience"), 0)
        candidate["salary_expectation_inr"] = _safe_int(meta.get("salary_expectation_inr"), 0)
        candidate["notice_period_days"] = _safe_int(meta.get("notice_period_days"), 30)
        candidate["interest_level"] = _safe_int(meta.get("interest_level"), 3)
        candidate["career_history_text"] = str(meta.get("career_history_text", ""))
        candidate["last_active_date"] = str(meta.get("last_active_date", ""))
        
        # safely parse recruiter_response_rate as float
        try:
            candidate["recruiter_response_rate"] = float(meta.get("recruiter_response_rate", 1.0))
        except (ValueError, TypeError):
            candidate["recruiter_response_rate"] = 1.0

        # Attach distance / similarity
        candidate["cosine_distance"]    = round(distance, 4)
        candidate["semantic_similarity"] = round(max(0.0, (1 - distance / 2) * 100), 1)

        candidates.append(candidate)

    return candidates


def collection_count() -> int:
    """Return the number of documents currently in the collection."""
    return get_or_create_collection().count()
