"""
vector_store.py — ChromaDB initialisation and query helpers.

This module is the single point of contact for all vector DB operations.
It is imported by:
  - scripts/embed_candidates.py  (to write embeddings once)
  - app/agents/talent_scout.py   (to query at runtime)
"""

import os
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

# ── Constants ─────────────────────────────────────────────────────────────────
COLLECTION_NAME = "candidates"
EMBEDDING_MODEL  = "all-MiniLM-L6-v2"      # ~80 MB, downloads once
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")

# Loaded once at import time so it is warm for every request.
print(f"[vector_store] Loading default ONNX embedding model '{EMBEDDING_MODEL}' …")
_embedding_fn = embedding_functions.DefaultEmbeddingFunction()
print("[vector_store] Embedding model ready.")


# ── ChromaDB client ────────────────────────────────────────────────────────────
def _get_client() -> chromadb.PersistentClient:
    """Return a persistent ChromaDB client pointed at CHROMA_PERSIST_DIR."""
    return chromadb.PersistentClient(
        path=CHROMA_PERSIST_DIR,
        settings=Settings(anonymized_telemetry=False),
    )


def get_or_create_collection() -> chromadb.Collection:
    """
    Return the 'candidates' collection (creates it if it doesn't exist yet).
    Uses cosine distance so similarity is intuitive (higher = more similar).
    """
    client = _get_client()
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},   # cosine distance: range 0–2
    )
    return collection


# ── Embedding helper ───────────────────────────────────────────────────────────
def embed_text(text: str) -> list[float]:
    """Embed a single string and return a plain Python list of floats."""
    return _embedding_fn([text])[0]


def build_candidate_text(candidate: dict) -> str:
    """
    Build the text representation of a candidate that will be embedded.
    Combines bio + skills so both semantic meaning and keywords are captured.
    """
    skills_str = " ".join(candidate.get("skills", []))
    bio        = candidate.get("bio", "")
    title      = candidate.get("current_title", "")
    seniority  = candidate.get("seniority", "")
    domain     = " ".join(candidate.get("open_to_roles", []))
    return f"{title} {seniority} {bio} Skills: {skills_str} Roles: {domain}"


# ── Write helpers (used by embed_candidates.py) ────────────────────────────────
def upsert_candidate(collection: chromadb.Collection, candidate: dict) -> None:
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
        "skills":              ",".join(candidate.get("skills", [])),
        "salary_expectation_inr": candidate.get("salary_expectation_inr", 0),
        "notice_period_days":  candidate.get("notice_period_days", 30),
        "interest_level":      candidate.get("interest_level", 3),   # private — not in output
        "open_to_roles":       ",".join(candidate.get("open_to_roles", [])),
        "email":               candidate.get("email", ""),
        "bio":                 candidate.get("bio", ""),
    }

    collection.upsert(
        ids=[candidate["id"]],
        embeddings=[embedding],
        documents=[text],
        metadatas=[metadata],
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
    metadatas  = results["metadatas"][0]
    distances  = results["distances"][0]

    for meta, distance in zip(metadatas, distances):
        # Reconstruct the candidate dict from stored metadata
        candidate = dict(meta)

        # Convert comma-separated strings back to lists
        candidate["skills"]        = [s for s in meta["skills"].split(",") if s]
        candidate["open_to_roles"] = [r for r in meta["open_to_roles"].split(",") if r]
        candidate["remote_ok"]     = meta["remote_ok"] == "True"
        candidate["years_of_experience"] = int(meta["years_of_experience"])
        candidate["salary_expectation_inr"] = int(meta["salary_expectation_inr"])
        candidate["notice_period_days"] = int(meta["notice_period_days"])
        candidate["interest_level"] = int(meta["interest_level"])

        # Attach distance / similarity
        candidate["cosine_distance"]    = round(distance, 4)
        candidate["semantic_similarity"] = round(max(0.0, (1 - distance / 2) * 100), 1)

        candidates.append(candidate)

    return candidates


def collection_count() -> int:
    """Return the number of documents currently in the collection."""
    return get_or_create_collection().count()
