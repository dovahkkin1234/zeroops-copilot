"""SQLite schema + CRUD operations for incident memory.

Memory save contract:
- Only save incidents where confidence >= 0.5
- Unresolved incidents (resolution_status == "uncertain") are NOT saved
- Embeddings are from normalized error signatures, not raw error_text
- Duplicate signatures upsert rather than create new rows
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

from ..config import settings
from .embeddings import (
    embed,
    normalize_error_signature,
    cosine_similarity,
    serialize,
    deserialize,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at          TEXT NOT NULL,
    error_text          TEXT NOT NULL,
    error_type          TEXT,
    error_signature     TEXT NOT NULL,
    root_cause          TEXT NOT NULL,
    root_cause_pattern  TEXT,
    affected_files      TEXT,
    fix_summary         TEXT,
    fix_diff            TEXT,
    embedding           BLOB,
    confidence          REAL,
    verified            INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_pattern ON incidents(root_cause_pattern);
CREATE INDEX IF NOT EXISTS idx_type ON incidents(error_type);
CREATE INDEX IF NOT EXISTS idx_signature ON incidents(error_signature);
"""

_db_path: Optional[str] = None
_conn: Optional[sqlite3.Connection] = None


def _get_conn() -> sqlite3.Connection:
    """Get or create the SQLite connection."""
    global _conn, _db_path
    target = settings.db_path
    if _conn is None or _db_path != target:
        _db_path = target
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(target)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(_SCHEMA)
    return _conn


def init_db(path: str | None = None) -> None:
    """Initialize the SQLite database with the incidents schema."""
    global _db_path, _conn
    if path:
        _db_path = path
        settings.db_path = path
    _conn = None  # force reconnect
    _get_conn()


def save_incident(incident: dict) -> int:
    """Persist a resolved incident to memory. Returns the new id.

    Memory save contract:
    - Only saves when confidence >= 0.5
    - Skips uncertain resolution_status
    - Upserts on duplicate error_signature
    """
    # Enforce save contract
    confidence = incident.get("confidence", 0.0)
    if confidence < 0.5:
        raise ValueError(f"Confidence {confidence} below threshold 0.5 — not saving")

    resolution = incident.get("resolution_status", "")
    if resolution == "uncertain":
        raise ValueError("Uncertain incidents are not saved to memory")

    conn = _get_conn()

    error_text = incident.get("error_text", "")
    signature = normalize_error_signature(error_text)
    embedding_vec = embed(signature)
    embedding_blob = serialize(embedding_vec)

    # Extract affected files from evidence
    affected_files = incident.get("affected_files", [])
    if isinstance(affected_files, list):
        affected_files = json.dumps(affected_files)

    # Check for existing incident with same signature (upsert)
    existing = conn.execute(
        "SELECT id FROM incidents WHERE error_signature = ?",
        (signature,)
    ).fetchone()

    now = datetime.now(timezone.utc).isoformat()

    if existing:
        # Update existing
        conn.execute("""
            UPDATE incidents SET
                error_text = ?, error_type = ?, root_cause = ?,
                root_cause_pattern = ?, affected_files = ?,
                fix_summary = ?, fix_diff = ?, embedding = ?,
                confidence = ?, verified = ?, created_at = ?
            WHERE id = ?
        """, (
            error_text,
            incident.get("error_type"),
            incident.get("root_cause", ""),
            incident.get("root_cause_pattern"),
            affected_files,
            incident.get("fix_summary"),
            incident.get("fix_diff"),
            embedding_blob,
            confidence,
            int(incident.get("verified", False)),
            now,
            existing["id"],
        ))
        conn.commit()
        return existing["id"]
    else:
        # Insert new
        cursor = conn.execute("""
            INSERT INTO incidents
                (created_at, error_text, error_type, error_signature,
                 root_cause, root_cause_pattern, affected_files,
                 fix_summary, fix_diff, embedding, confidence, verified)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            now,
            error_text,
            incident.get("error_type"),
            signature,
            incident.get("root_cause", ""),
            incident.get("root_cause_pattern"),
            affected_files,
            incident.get("fix_summary"),
            incident.get("fix_diff"),
            embedding_blob,
            confidence,
            int(incident.get("verified", False)),
        ))
        conn.commit()
        return cursor.lastrowid


def search_similar(query_embedding: np.ndarray, k: int = 3) -> list[tuple[int, float, dict]]:
    """Search for similar incidents by embedding cosine similarity.

    Returns list of (id, similarity_score, incident_dict) tuples,
    sorted by similarity descending.
    """
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM incidents WHERE embedding IS NOT NULL").fetchall()

    if not rows:
        return []

    scored = []
    for row in rows:
        row_dict = dict(row)
        stored_embedding = deserialize(row_dict["embedding"])
        sim = cosine_similarity(query_embedding, stored_embedding)
        scored.append((row_dict["id"], sim, row_dict))

    # Sort by similarity descending
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:k]


def search_by_text(query_text: str, k: int = 3) -> list[tuple[int, float, dict]]:
    """Convenience: embed query text then search."""
    signature = normalize_error_signature(query_text)
    query_vec = embed(signature)
    return search_similar(query_vec, k=k)


def get_by_id(id: int) -> dict | None:
    """Retrieve incident by id."""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM incidents WHERE id = ?", (id,)).fetchone()
    if row:
        return dict(row)
    return None


def reset_db() -> None:
    """Drop and recreate the incidents table. For testing only."""
    conn = _get_conn()
    conn.execute("DROP TABLE IF EXISTS incidents")
    conn.executescript(_SCHEMA)
    conn.commit()
