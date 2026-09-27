from copy import deepcopy
import math

import networkx as nx
import pytest

from app.analysis import (_automorphism_state, _has_evidence, _iter_pair_features,
                          _prepare_graph, _relevant_pair_keys, analyze_graph)
from app.ingest import demo_graph, normalize_graph


def graph_data(graph):
    return {"name": "Проверка", "nodes": [{"id": str(n), "label": str(n)} for n in graph],
            "edges": [{"source": str(a), "target": str(b)} for a, b in graph.edges], "metadata": {}}


def pair_map(result):
    return {frozenset((pair["source"], pair["target"])): pair for pair in result["pairs"]}


def stable_scientific_result(result):
    summary = {key: value for key, value in result["summary"].items() if key != "elapsed_ms"}
    return {"summary": summary, "orbits": result["orbits"], "pairs": result["pairs"]}


def test_fixed_root_star_does_not_treat_empty_leaf_neighborhoods_as_evidence():
    graph = graph_data(nx.star_graph(4))
    result = analyze_graph(graph, {"root": "0", "threshold": 0})
    assert sorted(orbit["size"] for orbit in result["orbits"]) == [1, 4]
    assert result["summary"]["group_order"] == "24"
    assert result["pairs"] == []
    assert result["warnings"] == ["У 4 вершин пустые сравниваемые окрестности."]
    with_root = analyze_graph(graph, {"root": "0", "exclude_root": False})
    assert with_root["summary"]["candidate_count"] == 6
    assert all(pair["score"] == 1 for pair in with_root["pairs"])
    assert all("0" not in (p["source"], p["target"]) for p in with_root["pairs"])


def test_cycle_group_and_root_stabilizer_are_exact():
    graph = graph_data(nx.cycle_graph(5))
    unrooted = analyze_graph(graph)
    assert unrooted["summary"]["group_order"] == "10"
    assert [orbit["size"] for orbit in unrooted["orbits"]] == [5]
    rooted = analyze_graph(graph, {"root": "0", "radius": 3})
    assert rooted["summary"]["group_order"] == "2"
    assert sorted(orbit["size"] for orbit in rooted["orbits"]) == [1, 2, 2]


def test_asymmetric_frucht_graph_has_only_singleton_orbits():
    result = analyze_graph(graph_data(nx.frucht_graph()))
    assert result["summary"]["group_order"] == "1"
    assert result["summary"]["orbit_count"] == 12
    assert result["summary"]["nontrivial_orbits"] == 0
    assert result["pairs"] == []


def test_true_twins_use_ordinary_open_jaccard_not_silently_closed_sets():
    result = analyze_graph(graph_data(nx.complete_graph(3)))
    assert len(result["pairs"]) == 3
    for pair in result["pairs"]:
        assert pair["twin_type"] == "true_twins"
        assert pair["jaccard"] == pytest.approx(1 / 3)
        assert pair["score"] == pytest.approx(2 / 3)
        assert pair["same_orbit"]


def test_false_twins_and_isolates_are_distinguished_by_effective_evidence():
    graph = nx.cycle_graph(4)
    graph.add_nodes_from(["isolate-a", "isolate-b"])
    result = analyze_graph(graph_data(graph), {"threshold": 0})
    pairs = pair_map(result)
    assert pairs[frozenset(("0", "2"))]["twin_type"] == "false_twins"
    assert pairs[frozenset(("0", "2"))]["jaccard"] == 1
    assert not any("isolate-a" in pair for pair in pairs)
    assert not any("isolate-b" in pair for pair in pairs)


def test_ego_is_induced_and_returned_graph_remains_valid_after_label_projection():
    graph = graph_data(nx.path_graph(5))
    graph["metadata"]["root"] = "4"
    graph["nodes"][0]["clone_of"] = "4"
    result = analyze_graph(graph, {"root": "0", "radius": 2})
    assert {node["id"] for node in result["graph"]["nodes"]} == {"0", "1", "2"}
    assert result["summary"]["edge_count"] == 2
    assert result["graph"]["metadata"]["root"] == "0"
    assert "clone_of" not in result["graph"]["nodes"][0]
    assert any("clone_of" in warning for warning in result["warnings"])
    normalize_graph(result["graph"])
    assert graph["nodes"][0]["clone_of"] == "4"


def test_partial_labels_are_not_assumed_to_be_negatives():
    graph = graph_data(nx.complete_graph(4))
    graph["nodes"][0]["truth"] = "bot"
    evaluation = analyze_graph(graph)["evaluation"]
    assert evaluation["complete"] is False
    assert evaluation["labeled_count"] == 1
    assert "precision" not in evaluation
    assert "recall" not in evaluation


def test_pair_output_limit_does_not_change_evaluation_or_candidate_count():
    graph = graph_data(nx.complete_graph(4))
    for node in graph["nodes"]:
        node["truth"] = "bot" if node["id"] == "3" else "human"
    full = analyze_graph(graph, {"max_pairs": 100})
    short = analyze_graph(graph, {"max_pairs": 1})
    none = analyze_graph(graph, {"max_pairs": 0})
    assert full["summary"]["candidate_count"] == short["summary"]["candidate_count"] == 6
    assert len(short["pairs"]) == 1
    assert none["pairs"] == []
    assert full["evaluation"] == short["evaluation"] == none["evaluation"]
    assert short["evaluation"]["tp"] == 1
    assert short["evaluation"]["fp"] == 3
    assert short["evaluation"]["recall"] == 1
    assert short["pairs"] == full["pairs"][:1]


def test_id_order_and_edge_order_do_not_change_results_or_layout():
    graph = graph_data(nx.cycle_graph(6))
    shuffled = deepcopy(graph)
    shuffled["nodes"].reverse()
    shuffled["edges"] = [{"source": edge["target"], "target": edge["source"]} for edge in reversed(shuffled["edges"])]
    first, second = analyze_graph(graph), analyze_graph(shuffled)
    assert stable_scientific_result(first) == stable_scientific_result(second)
    assert first["graph"]["nodes"] == second["graph"]["nodes"]


def test_renaming_ids_preserves_orbits_and_pair_scores():
    graph = nx.cycle_graph(6)
    mapping = {node: f"x-{6 - node}" for node in graph}
    first = analyze_graph(graph_data(graph), {"threshold": .4})
    renamed = analyze_graph(graph_data(nx.relabel_nodes(graph, mapping)), {"threshold": .4})
    reverse = {value: str(key) for key, value in mapping.items()}
    original_pairs = {frozenset((p["source"], p["target"])): (p["score"], p["same_orbit"]) for p in first["pairs"]}
    renamed_pairs = {frozenset((reverse[p["source"]], reverse[p["target"]])): (p["score"], p["same_orbit"]) for p in renamed["pairs"]}
    assert original_pairs == renamed_pairs
    assert first["summary"]["group_order"] == renamed["summary"]["group_order"]


def test_ground_truth_and_display_labels_cannot_leak_into_scores():
    graph = graph_data(nx.cycle_graph(6))
    poisoned = deepcopy(graph)
    for index, node in enumerate(poisoned["nodes"]):
        node["label"] = "Бот" if index % 2 else "Человек"
        node["truth"] = "bot" if index % 2 else "human"
    poisoned["nodes"][1]["clone_of"] = "0"
    assert stable_scientific_result(analyze_graph(graph)) == stable_scientific_result(analyze_graph(poisoned))


def test_large_group_order_is_not_fabricated_as_exact_integer():
    result = analyze_graph(graph_data(nx.star_graph(25)), {"root": "0"})
    assert result["summary"]["group_order_exact"] is False
    assert result["summary"]["group_order"].startswith("≈")
    assert sorted(o["size"] for o in result["orbits"]) == [1, 25]


def test_singleton_has_finite_layout_and_no_pairs():
    graph = nx.empty_graph(1)
    result = analyze_graph(graph_data(graph))
    assert result["summary"]["group_order"] == "1"
    assert result["pairs"] == []
    assert all(math.isfinite(result["graph"]["nodes"][0][axis]) for axis in ("x", "y"))


@pytest.mark.parametrize("options", [{"threshold": float("nan")}, {"radius": 0}, {"radius": 1.1},
                                      {"root": "absent"}, {"exclude_root": "true"}, {"max_pairs": -1}])
def test_invalid_options_fail_clearly(options):
    with pytest.raises(ValueError):
        analyze_graph(graph_data(nx.path_graph(3)), options)


def test_500_nodes_layout_does_not_require_scipy_or_truncate():
    result = analyze_graph(graph_data(nx.path_graph(500)), {"max_pairs": 0})
    assert result["summary"]["node_count"] == 500
    assert len(result["graph"]["nodes"]) == 500
    assert all(math.isfinite(node[axis]) for node in result["graph"]["nodes"] for axis in ("x", "y"))


def test_large_source_requires_local_scope_but_analyzes_selected_neighborhood():
    graph = graph_data(nx.path_graph(10_001))
    with pytest.raises(ValueError, match="выберите центр"):
        analyze_graph(graph, {"max_pairs": 0})
    result = analyze_graph(graph, {"root": "0", "radius": 2, "max_pairs": 0})
    assert result["summary"]["node_count"] == 3
    assert {node["id"] for node in result["graph"]["nodes"]} == {"0", "1", "2"}


@pytest.mark.parametrize("threshold", [0, .3, .5, .65, 1])
def test_sparse_pair_screening_is_equivalent_to_exhaustive_pairs(threshold):
    graph = graph_data(nx.gnp_random_graph(14, .22, seed=17))
    _selected, nx_graph = _prepare_graph(graph)
    state = _automorphism_state(nx_graph)
    expected = [
        pair for pair in _iter_pair_features(nx_graph, state, None, True)
        if pair["score"] >= threshold and _has_evidence(pair)
    ]
    expected.sort(key=lambda pair: (-pair["score"], pair["source"], pair["target"]))
    actual = analyze_graph(graph, {"threshold": threshold, "max_pairs": 20_000})
    actual_core = [{key: value for key, value in pair.items() if key != "reasons"} for pair in actual["pairs"]]
    assert actual_core == expected
    assert actual["summary"]["candidate_count"] == len(expected)
    assert actual["summary"]["scored_pair_count"] <= actual["summary"]["possible_pair_count"]


def test_10000_vertex_example_is_analyzed_whole_and_finds_planted_twins():
    result = analyze_graph(demo_graph("social-10000"))
    summary = result["summary"]
    assert summary["node_count"] == summary["eligible_node_count"] == 10_000
    assert summary["edge_count"] == 30_311
    assert summary["possible_pair_count"] == 49_995_000
    assert summary["scored_pair_count"] == summary["candidate_count"] == 91
    assert summary["candidate_score_min"] == pytest.approx(2 / 3)
    assert summary["candidate_score_max"] == 1
    planted = result["graph"]["metadata"]["planted_clones"]
    planted_true = result["graph"]["metadata"]["planted_true_twins"]
    returned = {frozenset((pair["source"], pair["target"])) for pair in result["pairs"]}
    assert all(frozenset((clone, source)) in returned for clone, source in planted.items())
    assert all(frozenset((pair["source"], pair["target"])) in returned for pair in planted_true)
    assert sum(pair["twin_type"] == "false_twins" for pair in result["pairs"]) == 11
    assert sum(pair["twin_type"] == "true_twins" for pair in result["pairs"]) == 80
    assert len({round(pair["score"], 6) for pair in result["pairs"]}) == 9


def test_pair_explosion_returns_an_explicit_error_instead_of_truncating():
    graph = nx.relabel_nodes(nx.star_graph(3_200), str)
    state = {"orbit_by_node": {node: (0 if node == "0" else 1) for node in graph}}
    with pytest.raises(ValueError, match="скрытого усечения результатов нет"):
        next(_relevant_pair_keys(graph, state, None, True, .65))
