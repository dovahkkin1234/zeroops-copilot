"""Tests for src/zeroops/memory/store.py — save contract, upsert, search, reset.

Uses:
- isolated_db fixture: each test gets its own temp SQLite file
- mock_embed_* fixtures: no sentence-transformer model loaded (offline)
"""

import numpy as np
import pytest
from unittest.mock import patch

from tests.conftest import NEAR_VEC, FAR_VEC


# ── helpers ───────────────────────────────────────────────────────────────────

def _inc(error_text="AttributeError: module 'auth' has no attribute 'validate_token'",
         confidence=0.75,
         resolution_status="resolved",
         **kwargs):
    return {
        "error_text": error_text,
        "confidence": confidence,
        "resolution_status": resolution_status,
        "root_cause": "incomplete_symbol_rename",
        "error_type": "AttributeError",
        **kwargs,
    }


# ── save contract ─────────────────────────────────────────────────────────────

def test_save_rejects_low_confidence(isolated_db, mock_embed_uniform):
    from zeroops.memory.store import save_incident
    with pytest.raises(ValueError, match="below threshold"):
        save_incident(_inc(confidence=0.49))


def test_save_rejects_confidence_zero(isolated_db, mock_embed_uniform):
    from zeroops.memory.store import save_incident
    with pytest.raises(ValueError, match="below threshold"):
        save_incident(_inc(confidence=0.0))


def test_save_rejects_uncertain_status(isolated_db, mock_embed_uniform):
    from zeroops.memory.store import save_incident
    with pytest.raises(ValueError, match="Uncertain"):
        save_incident(_inc(resolution_status="uncertain"))


def test_save_accepts_minimum_confidence(isolated_db, mock_embed_uniform):
    from zeroops.memory.store import save_incident
    incident_id = save_incident(_inc(confidence=0.5))
    assert isinstance(incident_id, int)
    assert incident_id >= 1


def test_save_accepts_resolved_status(isolated_db, mock_embed_uniform):
    from zeroops.memory.store import save_incident
    incident_id = save_incident(_inc(resolution_status="resolved"))
    assert incident_id >= 1


def test_save_accepts_known_pattern_status(isolated_db, mock_embed_uniform):
    from zeroops.memory.store import save_incident
    incident_id = save_incident(_inc(resolution_status="known_pattern"))
    assert incident_id >= 1


# ── upsert on duplicate signature ─────────────────────────────────────────────

def test_upsert_same_signature_keeps_one_row(isolated_db, mock_embed_uniform):
    """Saving the same error text twice must not create two rows."""
    from zeroops.memory import store as store_mod
    from zeroops.memory.store import save_incident

    error_text = "AttributeError: module 'auth' has no attribute 'validate_token'"
    id1 = save_incident(_inc(error_text=error_text, confidence=0.6))
    id2 = save_incident(_inc(error_text=error_text, confidence=0.9))

    # Both calls must return the same id
    assert id1 == id2

    # Only one row in the database
    conn = store_mod._get_conn()
    count = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
    assert count == 1


def test_upsert_updates_confidence(isolated_db, mock_embed_uniform):
    """Upsert should overwrite the confidence field."""
    from zeroops.memory import store as store_mod
    from zeroops.memory.store import save_incident

    error_text = "AttributeError: module 'auth' has no attribute 'validate_token'"
    save_incident(_inc(error_text=error_text, confidence=0.6))
    save_incident(_inc(error_text=error_text, confidence=0.95))

    conn = store_mod._get_conn()
    row = conn.execute("SELECT confidence FROM incidents").fetchone()
    assert row[0] == pytest.approx(0.95)


def test_different_signatures_create_separate_rows(isolated_db, mock_embed_uniform):
    """Two distinct errors must create two separate rows."""
    from zeroops.memory import store as store_mod
    from zeroops.memory.store import save_incident

    save_incident(_inc(error_text="AttributeError: module 'auth' has no attribute 'validate_token'"))
    save_incident(_inc(
        error_text="ImportError: cannot import name 'normalize_string' from 'utils'",
        error_type="ImportError",
    ))

    conn = store_mod._get_conn()
    count = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
    assert count == 2


# ── search_similar ────────────────────────────────────────────────────────────

def test_search_similar_empty_db_returns_empty(isolated_db, mock_embed_uniform):
    from zeroops.memory.store import search_similar
    results = search_similar(NEAR_VEC, k=3)
    assert results == []


def test_search_similar_ranks_near_duplicate_first(isolated_db, mock_embed_by_content):
    """Near-duplicate (same error type) should rank above unrelated incident."""
    from zeroops.memory.store import save_incident, search_similar

    # Save near-dup: embed() returns NEAR_VEC because text contains "AttributeError"
    save_incident(_inc(
        error_text="AttributeError: module 'auth' has no attribute 'validate_token'",
    ))
    # Save unrelated: embed() returns FAR_VEC
    save_incident(_inc(
        error_text="ImportError: cannot import name 'normalize_string' from 'utils'",
        error_type="ImportError",
    ))

    # Query with NEAR_VEC — near-dup has cosine_sim 1.0, far has 0.0
    results = search_similar(NEAR_VEC, k=2)
    assert len(results) == 2
    top_id, top_sim, top_row = results[0]
    assert top_sim == pytest.approx(1.0)
    assert top_row["error_type"] == "AttributeError"


def test_search_similar_respects_k(isolated_db, mock_embed_uniform):
    from zeroops.memory.store import save_incident, search_similar

    for i in range(5):
        save_incident(_inc(
            error_text=f"AttributeError: module 'mod{i}' has no attribute 'fn'",
        ))

    results = search_similar(NEAR_VEC, k=3)
    assert len(results) == 3


# ── reset_db ──────────────────────────────────────────────────────────────────

def test_reset_db_clears_incidents(isolated_db, mock_embed_uniform):
    from zeroops.memory import store as store_mod
    from zeroops.memory.store import reset_db, save_incident

    save_incident(_inc())
    conn = store_mod._get_conn()
    assert conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0] == 1

    reset_db()
    assert conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0] == 0


def test_reset_db_allows_new_inserts(isolated_db, mock_embed_uniform):
    from zeroops.memory.store import reset_db, save_incident

    save_incident(_inc())
    reset_db()
    new_id = save_incident(_inc())
    assert new_id >= 1


# ── get_by_id ─────────────────────────────────────────────────────────────────

def test_get_by_id_returns_incident(isolated_db, mock_embed_uniform):
    from zeroops.memory.store import get_by_id, save_incident

    inc_id = save_incident(_inc())
    row = get_by_id(inc_id)
    assert row is not None
    assert row["error_type"] == "AttributeError"


def test_get_by_id_missing_returns_none(isolated_db, mock_embed_uniform):
    from zeroops.memory.store import get_by_id
    assert get_by_id(99999) is None
