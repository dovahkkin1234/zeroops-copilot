"""Tests for the graph-structured incident memory."""

import tempfile
import os
import pytest


@pytest.fixture()
def tmp_graph(tmp_path):
    """IncidentGraph backed by a temp db path."""
    from zeroops.memory.graph_store import IncidentGraph, reset_graph
    reset_graph(str(tmp_path / "test.db"))
    graph = IncidentGraph(str(tmp_path / "test.db"))
    yield graph
    reset_graph(str(tmp_path / "test.db"))


def _incident(id_: int, pattern: str = "incomplete_symbol_rename",
              files: list = None, error_type: str = "AttributeError"):
    return {
        "root_cause_pattern": pattern,
        "affected_files": files or ["middleware.py"],
        "error_type": error_type,
        "root_cause": f"Stale symbol reference in middleware (incident {id_})",
    }


class TestAddAndQuery:
    def test_add_incident_creates_nodes(self, tmp_graph):
        tmp_graph.add_incident(1, _incident(1))
        s = tmp_graph.stats()
        assert s["incidents"] == 1
        assert s["patterns"] >= 1
        assert s["files"] >= 1

    def test_query_by_file_returns_incident(self, tmp_graph):
        tmp_graph.add_incident(1, _incident(1, files=["auth.py"]))
        results = tmp_graph.query_by_file("auth.py")
        assert len(results) == 1
        assert results[0]["id"] == 1
        assert results[0]["match_type"] == "file"

    def test_query_by_file_unknown_returns_empty(self, tmp_graph):
        tmp_graph.add_incident(1, _incident(1))
        assert tmp_graph.query_by_file("does_not_exist.py") == []

    def test_query_by_pattern_returns_incident(self, tmp_graph):
        tmp_graph.add_incident(1, _incident(1, pattern="unchecked_none_return"))
        results = tmp_graph.query_by_pattern("unchecked_none_return")
        assert any(r["id"] == 1 for r in results)

    def test_query_by_pattern_no_cross_contamination(self, tmp_graph):
        tmp_graph.add_incident(1, _incident(1, pattern="incomplete_symbol_rename"))
        tmp_graph.add_incident(2, _incident(2, pattern="unchecked_none_return"))
        r1 = tmp_graph.query_by_pattern("incomplete_symbol_rename")
        r2 = tmp_graph.query_by_pattern("unchecked_none_return")
        assert all(r["id"] == 1 for r in r1)
        assert all(r["id"] == 2 for r in r2)

    def test_get_files_with_pattern(self, tmp_graph):
        tmp_graph.add_incident(1, _incident(1, files=["middleware.py", "db.py"]))
        files = tmp_graph.get_files_with_pattern("incomplete_symbol_rename")
        assert set(files) == {"middleware.py", "db.py"}

    def test_get_files_with_unknown_pattern_returns_empty(self, tmp_graph):
        tmp_graph.add_incident(1, _incident(1))
        assert tmp_graph.get_files_with_pattern("nonexistent_pattern") == []

    def test_query_by_error_type(self, tmp_graph):
        tmp_graph.add_incident(1, _incident(1, error_type="AttributeError"))
        tmp_graph.add_incident(2, _incident(2, error_type="ImportError"))
        attr_ids = tmp_graph.query_by_error_type("AttributeError")
        assert 1 in attr_ids
        assert 2 not in attr_ids


class TestPersistence:
    def test_graph_survives_reload(self, tmp_path):
        from zeroops.memory.graph_store import IncidentGraph
        db = str(tmp_path / "incidents.db")

        g1 = IncidentGraph(db)
        g1.add_incident(42, _incident(42, files=["handler.py"]))

        g2 = IncidentGraph(db)
        results = g2.query_by_file("handler.py")
        assert any(r["id"] == 42 for r in results)

    def test_graph_path_is_sibling_of_db(self, tmp_path):
        from zeroops.memory.graph_store import IncidentGraph
        db = str(tmp_path / "my.db")
        g = IncidentGraph(db)
        assert g._graph_path.suffix == ".json"
        assert g._graph_path.parent == tmp_path


class TestMultiIncident:
    def test_multiple_incidents_same_file(self, tmp_graph):
        tmp_graph.add_incident(1, _incident(1, files=["auth.py"]))
        tmp_graph.add_incident(2, _incident(2, files=["auth.py"]))
        results = tmp_graph.query_by_file("auth.py")
        ids = {r["id"] for r in results}
        assert {1, 2}.issubset(ids)

    def test_cross_pattern_file_isolation(self, tmp_graph):
        """Files from pattern A should not appear under pattern B."""
        tmp_graph.add_incident(1, _incident(1, pattern="p_a", files=["a.py"]))
        tmp_graph.add_incident(2, _incident(2, pattern="p_b", files=["b.py"]))
        assert "b.py" not in tmp_graph.get_files_with_pattern("p_a")
        assert "a.py" not in tmp_graph.get_files_with_pattern("p_b")


class TestGraphAugmentedSearch:
    def test_save_incident_updates_graph(self, tmp_path, monkeypatch):
        """save_incident in tools/memory.py must also call graph.add_incident."""
        import zeroops.memory.graph_store as gs
        import zeroops.memory.store as store

        db = str(tmp_path / "incidents.db")
        monkeypatch.setattr("zeroops.config.settings.db_path", db)
        gs.reset_graph(db)
        store._conn = None
        store._db_path = None

        from zeroops.tools.memory import save_incident
        postmortem = {
            "error_text": "AttributeError: module 'auth' has no attribute 'validate_token'",
            "triage": {"error_type": "AttributeError", "classification": "novel",
                       "match_confidence": 0.0, "suggested_tier": "L2",
                       "severity": "SEV3", "routing_reason": "novel"},
            "hypothesis": {
                "statement": "validate_token was renamed",
                "pattern": "incomplete_symbol_rename",
                "evidence": [{"source": "file", "reference": "middleware.py",
                               "observation": "import validate_token", "relevance": 0.9}],
                "confidence": 0.9,
            },
            "root_cause": "Symbol renamed but not all callers updated",
            "proposed_fix": "Update import in middleware.py",
            "proposed_diff": None,
            "confidence": 0.9,
            "resolution_status": "resolved",
        }

        inc_id = save_incident(postmortem)
        graph = gs.get_graph(db)
        files = graph.get_files_with_pattern("incomplete_symbol_rename")
        assert "middleware.py" in files
