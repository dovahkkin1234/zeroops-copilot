"""Memory tools: search_past_incidents, save_incident.

Thin wrappers around the memory store. These are the tool functions
that agent nodes call directly.
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


def save_incident(postmortem: dict) -> int:
    """Persist a resolved incident to memory. Returns the new id.

    Extracts relevant fields from the postmortem dict and passes to store.
    Enforces the memory save contract (confidence >= 0.5, not uncertain).
    """
    # Extract affected files from evidence if available
    affected_files = []
    if "hypothesis" in postmortem and postmortem["hypothesis"]:
        hyp = postmortem["hypothesis"]
        if "evidence" in hyp:
            for ev in hyp["evidence"]:
                ref = ev.get("reference", "")
                if ref and ev.get("source") == "file":
                    # Extract basename
                    affected_files.append(ref.split("/")[-1].split("\\")[-1])

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

    return _store_save(incident_data)
