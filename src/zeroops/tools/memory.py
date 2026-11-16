"""Memory tools: search_past_incidents, save_incident.

Thin wrappers around the memory store and graph store. These are the
tool functions that agent nodes call directly.
"""

from ..memory.store import (
    save_incident as _store_save,
    search_by_text,
    get_by_id,
)


def search_past_incidents(query_text: str, k: int = 3) -> list[dict]:
    """Embed the query, search SQLite, return top-k with similarity scores.

    Returns list of dicts with keys: id, similarity, error_type,
    root_cause, root_cause_pattern, fix_summary.
    """
    results = search_by_text(query_text, k=k)

    formatted = []
    for incident_id, similarity, row in results:
        formatted.append({
            "id": incident_id,
            "similarity": round(similarity, 4),
            "error_type": row.get("error_type"),
            "root_cause": row.get("root_cause"),
            "root_cause_pattern": row.get("root_cause_pattern"),
            "fix_summary": row.get("fix_summary"),
            "confidence": row.get("confidence"),
        })

    return formatted


def search_past_incidents_with_graph(
    query_text: str,
    file_hint: str = "",
    error_type_hint: str = "",
    k: int = 3,
) -> list[dict]:
    """Embedding search augmented with graph traversal.

    Retrieves embedding-similar incidents (flat) and merges with structurally
    related incidents found via the graph (same file or same error_type).
    Graph hits are labelled with match_type='file' or 'error_type' and
    de-duplicated against the embedding results.

    Returns the same schema as search_past_incidents, with an extra
    'graph_match' key on graph-only hits.
    """
    # Flat embedding results
    flat = search_past_incidents(query_text, k=k)
    seen_ids = {r["id"] for r in flat}

    # Graph augmentation
    graph_hits: list[dict] = []
    try:
        from ..memory.graph_store import get_graph
        graph = get_graph()

        if file_hint:
            for gh in graph.query_by_file(file_hint, k=k):
                if gh["id"] not in seen_ids:
                    graph_hits.append({
                        "id": gh["id"],
                        "similarity": 0.0,  # no embedding score for graph hits
                        "error_type": gh.get("error_type"),
                        "root_cause": gh.get("root_cause"),
                        "root_cause_pattern": None,
                        "fix_summary": None,
                        "confidence": None,
                        "graph_match": f"same_file:{file_hint}",
                    })
                    seen_ids.add(gh["id"])

        if error_type_hint:
            for inc_id in graph.query_by_error_type(error_type_hint, k=k):
                if inc_id not in seen_ids:
                    row = get_by_id(inc_id)
                    if row:
                        graph_hits.append({
                            "id": inc_id,
                            "similarity": 0.0,
                            "error_type": row.get("error_type"),
                            "root_cause": row.get("root_cause"),
                            "root_cause_pattern": row.get("root_cause_pattern"),
                            "fix_summary": row.get("fix_summary"),
                            "confidence": row.get("confidence"),
                            "graph_match": f"same_error_type:{error_type_hint}",
                        })
                        seen_ids.add(inc_id)

    except Exception:
        pass  # graph unavailable — degrade to flat embedding only

    # Merge: flat (sorted by similarity) + graph-only hits after
    combined = flat + graph_hits
    return combined[:k + 2]  # allow slightly more context when graph adds hits


def save_incident(postmortem: dict) -> int:
    """Persist a resolved incident to memory. Returns the new id.

    Extracts relevant fields from the postmortem dict and passes to store.
    Enforces the memory save contract (confidence >= 0.5, not uncertain).
    Also updates the graph store with the incident's relationships.
    """
    # Extract affected files from evidence if available
    affected_files = []
    if "hypothesis" in postmortem and postmortem["hypothesis"]:
        hyp = postmortem["hypothesis"]
        if "evidence" in hyp:
            for ev in hyp["evidence"]:
                ref = ev.get("reference", "")
                if ref and ev.get("source") == "file":
                    # Strip path separators and any :line suffix
                    basename = ref.split("/")[-1].split("\\")[-1]
                    basename = basename.split(":")[0]
                    if basename:
                        affected_files.append(basename)

    incident_data = {
        "error_text": postmortem.get("error_text", ""),
        "error_type": postmortem.get("triage", {}).get("error_type", ""),
        "root_cause": postmortem.get("root_cause", ""),
        "root_cause_pattern": postmortem.get("hypothesis", {}).get("pattern") if postmortem.get("hypothesis") else None,
        "affected_files": affected_files,
        "fix_summary": postmortem.get("proposed_fix", ""),
        "fix_diff": postmortem.get("proposed_diff"),
        "confidence": postmortem.get("confidence", 0.0),
        "resolution_status": postmortem.get("resolution_status", "resolved"),
    }

    incident_id = _store_save(incident_data)

    # Update graph store (best-effort — never fail a save due to graph errors)
    try:
        from ..memory.graph_store import get_graph
        get_graph().add_incident(incident_id, incident_data)
    except Exception:
        pass

    return incident_id
