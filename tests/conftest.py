"""Shared pytest fixtures."""

import numpy as np
import pytest
from unittest.mock import patch

# Two orthogonal unit vectors — cosine similarity of same=1.0, different=0.0
NEAR_VEC = np.zeros(384, dtype=np.float32)
NEAR_VEC[0] = 1.0

FAR_VEC = np.zeros(384, dtype=np.float32)
FAR_VEC[1] = 1.0


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    """Give each test its own SQLite database, resetting the store's globals."""
    import zeroops.memory.store as store_mod

    db_path = str(tmp_path / "test_incidents.db")

    # Close any open connection and point the store at the temp path
    if store_mod._conn is not None:
        store_mod._conn.close()
    monkeypatch.setattr(store_mod, "_conn", None)
    monkeypatch.setattr(store_mod, "_db_path", None)
    monkeypatch.setattr(store_mod.settings, "db_path", db_path)

    yield db_path

    # Teardown — close connection so the temp file can be removed on Windows
    if store_mod._conn is not None:
        store_mod._conn.close()
    store_mod._conn = None
    store_mod._db_path = None


@pytest.fixture()
def mock_embed_uniform():
    """Patch embed() to return NEAR_VEC for every call (no model load)."""
    with patch("zeroops.memory.store.embed", return_value=NEAR_VEC.copy()):
        yield


@pytest.fixture()
def mock_embed_by_content():
    """Patch embed() to return NEAR_VEC for 'AttributeError' texts, FAR_VEC otherwise."""
    def _side_effect(text: str) -> np.ndarray:
        return NEAR_VEC.copy() if "AttributeError" in text else FAR_VEC.copy()

    with patch("zeroops.memory.store.embed", side_effect=_side_effect):
        yield
