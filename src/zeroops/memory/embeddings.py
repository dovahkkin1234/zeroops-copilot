"""Sentence-transformers wrapper for embedding and similarity.

Implemented in Phase 5.
"""

import numpy as np


def embed(text: str) -> np.ndarray:
    """Embed text using all-MiniLM-L6-v2. Lazy-loads model on first call."""
    raise NotImplementedError("Phase 5")


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    raise NotImplementedError("Phase 5")


def serialize(arr: np.ndarray) -> bytes:
    """Serialize numpy array to bytes for SQLite BLOB storage."""
    raise NotImplementedError("Phase 5")


def deserialize(blob: bytes) -> np.ndarray:
    """Deserialize bytes back to numpy array."""
    raise NotImplementedError("Phase 5")
