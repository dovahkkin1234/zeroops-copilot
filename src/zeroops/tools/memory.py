"""Memory tools: search_past_incidents, save_incident.

Implemented in Phase 4.
"""


def search_past_incidents(query_text: str, k: int = 3) -> list[dict]:
    """Embed the query, search SQLite, return top-k with similarity scores."""
    raise NotImplementedError("Phase 4")


def save_incident(postmortem: dict) -> int:
    """Persist a resolved incident to memory. Returns the new id."""
    raise NotImplementedError("Phase 4")
