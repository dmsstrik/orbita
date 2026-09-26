import json
from pathlib import Path

import networkx as nx
import pytest

from app.ingest import apply_labels, demo_graph, list_demos, normalize_graph, parse_graph


def test_json_preserves_isolates_and_normalizes_edges():
    result = parse_graph(json.dumps({"nodes": [{"id": 1}, {"id": "2"}, {"id": "alone"}],
                                     "edges": [[1, "2"], {"source": "2", "target": 1}, [1, 1]]}), "sample.json")
    assert [n["id"] for n in result["nodes"]] == ["1", "2", "alone"]
    assert result["edges"] == [{"source": "1", "target": "2"}]
    assert len(result["metadata"]["warnings"]) == 2


@pytest.mark.parametrize("content", ["source,target\na,b\nb,c", "source;target\na;b\nb;c",
                                    "source\ttarget\na\tb\nb\tc", "a b\nb c",
                                    "a,b\nb,c", "\ufeffsource,target\na,b\nb,c",
                                    "target,source\nb,a\nc,b"])
def test_common_csv_formats(content):
    graph = parse_graph(content)
    assert len(graph["nodes"]) == 3
    assert len(graph["edges"]) == 2


def test_legacy_encoding():
    graph = parse_graph("source;target\nАнна;Борис".encode("cp1251"))
    assert graph["nodes"][0]["id"] == "Анна"
    assert any("Windows-1251" in w for w in graph["metadata"]["warnings"])


@pytest.mark.parametrize("data", [
    {"directed": True, "edges": [["a", "b"]]},
    {"nodes": [{"id": "a"}, {"id": "a"}]},
    {"nodes": ["a"], "edges": [["a", "missing"]]},
    {"nodes": [{"id": "a", "truth": "likely_bot"}]},
    {"nodes": [{"id": "a", "truth": []}]},
    {"nodes": [{"id": "a", "clone_of": "missing"}]},
    {"nodes": [{"id": "a", "clone_of": "a"}]},
    {"nodes": [{"id": "a", "clone_of": "b"}, {"id": "b", "clone_of": "a"}]},
    {"nodes": ["a"], "metadata": {"root": "absent"}},
    {"nodes": ["a"], "metadata": {"warnings": "message"}},
    {"nodes": ["a"], "metadata": {"value": float("nan")}},
    {"nodes": [{"id": True}]},
    {"nodes": [{"id": "x" * 129}]},
    {"nodes": [{"id": "a", "label": "x" * 161}]},
    {"nodes": [{"id": "a", "x": 10**1000}]},
    {"nodes": [{"id": "a", "orbit": 10**1000}]},
    {"nodes": [{"id": "a", "label": chr(0xD800)}]},
    {"name": chr(0xD800), "nodes": ["a"]},
    {"nodes": list(range(2001))},
    {"edges": [["a", "b"]] * 100_001},
    {"nodes": []},
])
def test_invalid_graphs_raise_readable_value_errors(data):
    with pytest.raises(ValueError) as caught:
        normalize_graph(data)
    assert any("А" <= c <= "я" for c in str(caught.value))


def test_limits_accept_boundary_nodes_and_empty_edges():
    assert len(normalize_graph({"nodes": list(range(500))})["nodes"]) == 500


@pytest.mark.parametrize("content", ["", "{wrong", "source,target\na,b,c", "source,weight\na,b", "source,target\na,", "[1,2]"])
def test_malformed_files(content):
    with pytest.raises(ValueError):
        parse_graph(content)


def test_invalid_unicode_content_is_readable_error():
    with pytest.raises(ValueError, match="Unicode"):
        parse_graph(chr(0xD800))


def test_labels_merge_explicit_entries_and_do_not_make_others_human():
    original = normalize_graph({"nodes": ["a", "b", "c"], "edges": [["a", "b"]]})
    result = apply_labels(original, "id,truth,clone_of\nb,bot,a\nc,unknown,")
    nodes = {n["id"]: n for n in result["nodes"]}
    assert "truth" not in nodes["a"]
    assert nodes["b"]["truth"] == "bot" and nodes["b"]["clone_of"] == "a"
    assert nodes["c"]["truth"] == "unknown"
    assert "truth" not in original["nodes"][1]


def test_clone_only_label_does_not_infer_bot_truth():
    graph = apply_labels(normalize_graph({"nodes": ["a", "b"]}), "id;clone_of\nb;a")
    assert graph["nodes"][1]["clone_of"] == "a"
    assert "truth" not in graph["nodes"][1]


@pytest.mark.parametrize("content", ["id,truth\nx,bot", "id,truth\na,bot\na,human", "id,truth\na,yes",
                                    "id,clone_of\na,missing", "id,truth\na,", "id,truth\n", "id,other\na,bot"])
def test_bad_labels_fail_without_mutating_graph(content):
    original = normalize_graph({"nodes": ["a", "b"]})
    before = json.dumps(original)
    with pytest.raises(ValueError):
        apply_labels(original, content)
    assert json.dumps(original) == before


def test_demo_ground_truth_and_topology_are_consistent():
    graph = demo_graph("social")
    g = nx.Graph((e["source"], e["target"]) for e in graph["edges"])
    assert len(graph["nodes"]) == 35
    assert graph["metadata"]["synthetic"] is True
    assert set(g["clone_a"]) == set(g["u04"])
    assert set(g["clone_b"]) == set(g["u18"])
    assert set(g["clone_partial"]) != set(g["u24"])
    assert "u29" in g["clone_partial"] and "u29" not in g["u24"]
    assert len([n for n in graph["nodes"] if n.get("truth") == "bot"]) == 3
    assert len(list_demos()) == 3
    graph["nodes"][0]["label"] = "mutated"
    assert demo_graph()["nodes"][0]["label"] != "mutated"


def test_frucht_is_asymmetric_despite_equal_degrees():
    graph = demo_graph("asymmetric")
    g = nx.Graph((e["source"], e["target"]) for e in graph["edges"])
    assert set(dict(g.degree()).values()) == {3}
    assert len(list(nx.algorithms.isomorphism.GraphMatcher(g, g).isomorphisms_iter())) == 1


def test_downloadable_examples_match_demo():
    folder = Path(__file__).resolve().parents[1] / "examples"
    graph = parse_graph((folder / "social.json").read_text(), "social.json")
    assert graph == demo_graph("social")
    labeled = apply_labels(graph, (folder / "labels.csv").read_text())
    assert labeled["nodes"] == graph["nodes"]
    csv_graph = parse_graph((folder / "social.csv").read_text())
    assert csv_graph["edges"] == graph["edges"]
    assert len(csv_graph["nodes"]) == 34
