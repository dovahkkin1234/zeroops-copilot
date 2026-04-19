"""SQLite schema + CRUD operations for incident memory.

Implemented in Phase 5.
"""


def init_db(path: str) -> None:
    """Initialize the SQLite database with the incidents schema."""
    raise NotImplementedError("Phase 5")


def save_incident(incident: dict) -> int:
    """Persist incident to SQLite. Returns id."""
    raise NotImplementedError("Phase 5")


def search_similar(query_embedding, k: int = 3) -> list[tuple[int, float, dict]]:
    """Search for similar incidents by embedding cosine similarity."""
    raise NotImplementedError("Phase 5")


def get_by_id(id: int) -> dict | None:
    """Retrieve incident by id."""
    raise NotImplementedError("Phase 5")
