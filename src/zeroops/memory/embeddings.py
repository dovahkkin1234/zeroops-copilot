"""Sentence-transformers wrapper for embedding and similarity.

Lazy singleton loader for all-MiniLM-L6-v2. Provides embed, similarity,
and serialization utilities for SQLite BLOB storage.
"""

import numpy as np
from ..config import settings

# Lazy singleton — model loads on first embed() call
_model = None


def _get_model():
    """Lazy-load the sentence-transformer model."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(settings.embed_model)
    return _model


def normalize_error_signature(error_text: str) -> str:
    """Strip volatile info from error text before embedding.

    Removes:
    - Specific line numbers (keeps filename)
    - Full file paths (keeps basenames)
    - Memory addresses (0x...)
    - Process IDs

    This ensures semantically identical errors produce similar embeddings.
    """
    import re

    text = error_text

    # Replace full paths with basenames
    text = re.sub(r'(?:File\s+["\'])([^"\']+)(["\'])',
                  lambda m: f'File "{m.group(1).split("/")[-1].split(chr(92))[-1]}"',
                  text)

    # Remove specific line numbers from "line N" patterns
    text = re.sub(r', line \d+', ', line N', text)

    # Remove memory addresses
    text = re.sub(r'0x[0-9a-fA-F]+', '0xADDR', text)

    # Remove process/thread IDs
    text = re.sub(r'pid=\d+', 'pid=N', text)

    return text.strip()


def embed(text: str) -> np.ndarray:
    """Embed text using the configured sentence-transformer model.
    Returns a 1-D float32 numpy array."""
    model = _get_model()
    return model.encode(text, convert_to_numpy=True).astype(np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def serialize(arr: np.ndarray) -> bytes:
    """Serialize numpy array to bytes for SQLite BLOB storage."""
    return arr.tobytes()


def deserialize(blob: bytes, dtype=np.float32) -> np.ndarray:
    """Deserialize bytes back to numpy array."""
    return np.frombuffer(blob, dtype=dtype)
