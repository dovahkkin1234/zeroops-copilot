"""Graph-structured incident memory using networkx.

Augments flat embedding retrieval with structural traversal:
incident <-> file <-> pattern <-> commit.

Enables multi-hop queries that cosine similarity alone cannot answer:
- "which incidents previously affected this file?"
- "which files have we seen with this pattern before?"

Persists to {db_path}.graph.json beside the SQLite file.
"""

import json
from pathlib import Path
from typing import Optional

import networkx as nx


# Node types (stored as the 'type' node attribute)
# - 'incident'  node id = "incident:{sqlite_id}"
# - 'file'      node id = "file:{basename}"
# - 'pattern'   node id = "pattern:{name}"
# - 'commit'    node id = "commit:{hash[:8]}"


class IncidentGraph:
    def __init__(self, db_path: str):
        self._graph_path = Path(db_path).with_suffix(".graph.json")
        self.g: nx.DiGraph = nx.DiGraph()
        self._load()

    # ── Write ─────────────────────────────────────────────────────────────────

    def add_incident(self, incident_id: int, incident_dict: dict) -> None:
        """Add an incident and all its relationships to the graph."""
        inode = f"incident:{incident_id}"

        self.g.add_node(
            inode,
            type="incident",
            error_type=incident_dict.get("error_type", ""),
            root_cause=incident_dict.get("root_cause", "")[:120],
        )

        pattern = incident_dict.get("root_cause_pattern")
        if pattern:
            pnode = f"pattern:{pattern}"
            self.g.add_node(pnode, type="pattern", name=pattern)
            self.g.add_edge(inode, pnode, rel="has_pattern")

        affected = incident_dict.get("affected_files", [])
        if isinstance(affected, str):
            try:
                affected = json.loads(affected)
            except Exception:
                affected = []

        for fname in affected:
            fnode = f"file:{fname}"
            self.g.add_node(fnode, type="file", basename=fname)
            self.g.add_edge(inode, fnode, rel="affects")
            # pattern → file cross-link enables "files with this pattern" query
            if pattern:
                pnode = f"pattern:{pattern}"
                self.g.add_edge(pnode, fnode, rel="found_in")

        self._save()

    # ── Read ──────────────────────────────────────────────────────────────────

    def query_by_file(self, basename: str, k: int = 3) -> list[dict]:
        """Find incidents that previously affected this file (1-hop)."""
        fnode = f"file:{basename}"
        if fnode not in self.g:
            return []
        results = []
        for node in self.g.predecessors(fnode):
            ndata = self.g.nodes[node]
            if ndata.get("type") == "incident":
                inc_id = int(node.split(":", 1)[1])
                results.append({
                    "id": inc_id,
                    "match_type": "file",
                    "matched_on": basename,
                    "error_type": ndata.get("error_type", ""),
                    "root_cause": ndata.get("root_cause", ""),
                })
        return results[:k]

    def query_by_pattern(self, pattern: str, k: int = 3) -> list[dict]:
        """Find incidents with the same root cause pattern (1-hop)."""
        pnode = f"pattern:{pattern}"
        if pnode not in self.g:
            return []
        results = []
        for node in self.g.predecessors(pnode):
            ndata = self.g.nodes[node]
            if ndata.get("type") == "incident":
                inc_id = int(node.split(":", 1)[1])
                results.append({
                    "id": inc_id,
                    "match_type": "pattern",
                    "matched_on": pattern,
                    "error_type": ndata.get("error_type", ""),
                    "root_cause": ndata.get("root_cause", ""),
                })
        return results[:k]

    def query_by_error_type(self, error_type: str, k: int = 5) -> list[int]:
        """Return incident IDs with the given error_type."""
        ids = []
        for node, data in self.g.nodes(data=True):
            if data.get("type") == "incident" and data.get("error_type") == error_type:
                try:
                    ids.append(int(node.split(":", 1)[1]))
                except (ValueError, IndexError):
                    pass
        return ids[:k]

    def get_files_with_pattern(self, pattern: str) -> list[str]:
        """Return file basenames previously seen with this pattern.

        Used by Problem Manager to seed grep candidates from known-vulnerable
        files, complementing the LLM's pattern-based reasoning.
        """
        pnode = f"pattern:{pattern}"
        if pnode not in self.g:
            return []
        files = []
        for node in self.g.successors(pnode):
            ndata = self.g.nodes[node]
            if ndata.get("type") == "file":
                files.append(ndata["basename"])
        return files

    def stats(self) -> dict:
        return {
            "nodes": self.g.number_of_nodes(),
            "edges": self.g.number_of_edges(),
            "incidents": sum(1 for _, d in self.g.nodes(data=True) if d.get("type") == "incident"),
            "patterns": sum(1 for _, d in self.g.nodes(data=True) if d.get("type") == "pattern"),
            "files": sum(1 for _, d in self.g.nodes(data=True) if d.get("type") == "file"),
        }

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load(self) -> None:
        if self._graph_path.exists():
            try:
                data = json.loads(self._graph_path.read_text(encoding="utf-8"))
                # Determine which key name was used (networkx 2.x="links", 3.x="edges")
                edges_key = "links" if "links" in data else "edges"
                self.g = nx.node_link_graph(data, directed=True, multigraph=False,
                                            edges=edges_key)
            except Exception:
                self.g = nx.DiGraph()

    def _save(self) -> None:
        self._graph_path.parent.mkdir(parents=True, exist_ok=True)
        # Use networkx default (no edges= kwarg) for forward compatibility
        data = nx.node_link_data(self.g)
        self._graph_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# Module-level singleton
_instance: Optional[IncidentGraph] = None


def get_graph(db_path: Optional[str] = None) -> IncidentGraph:
    global _instance
    from ..config import settings
    path = db_path or settings.db_path
    target_path = str(Path(path).with_suffix(".graph.json"))
    if _instance is None or str(_instance._graph_path) != target_path:
        _instance = IncidentGraph(path)
    return _instance


def reset_graph(db_path: Optional[str] = None) -> None:
    global _instance
    from ..config import settings
    path = db_path or settings.db_path
    graph_path = Path(path).with_suffix(".graph.json")
    try:
        graph_path.unlink(missing_ok=True)
    except Exception:
        pass
    _instance = None
