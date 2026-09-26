from copy import deepcopy
from itertools import combinations
import random

import networkx as nx
import pytest

from app.analysis import _automorphism_state, _prepare_graph
from app.experiments import _inject_clones, _perturb, _read_config, run_experiments
from app.ingest import normalize_graph


def graph_data(graph):
    return {"name": "Эксперимент", "nodes": [{"id": str(n), "label": str(n)} for n in graph],
            "edges": [{"source": str(a), "target": str(b)} for a, b in graph.edges], "metadata": {}}


def small_config(**kwargs):
    return {"clone_count": 3, "retention": 1, "noise_levels": [0, .2], "repeats": 2, "seed": 713, **kwargs}


def without_time(value):
    if isinstance(value, dict):
        return {key: without_time(item) for key, item in value.items() if key != "elapsed_ms"}
    if isinstance(value, list):
        return [without_time(item) for item in value]
    return value


def test_reproducibility_including_input_order_independence():
    graph = graph_data(nx.path_graph(7))
    changed = deepcopy(graph)
    changed["nodes"].reverse()
    changed["edges"].reverse()
    first = run_experiments(graph, small_config())
    second = run_experiments(changed, small_config())
    assert without_time(first) == without_time(second)
    assert len(first["rows"]) == 2 * 2 * 3 * 2
    assert len(first["summary"]) == 2 * 3


def test_all_methods_share_graph_truth_population_and_fixed_threshold():
    result = run_experiments(graph_data(nx.path_graph(7)), small_config(threshold=.72))
    for noise in (0, .2):
        for repeat in (1, 2):
            for control in (True, False):
                rows = [row for row in result["rows"] if row["noise"] == noise and row["repeat"] == repeat and row["control"] == control]
                assert {row["method"] for row in rows} == {"neighbors", "symmetry", "combined"}
                assert len({row["graph_fingerprint"] for row in rows}) == 1
                assert len({row["actual_positive_pairs"] for row in rows}) == 1
                assert len({row["evaluated_pair_count"] for row in rows}) == 1
    assert result["config"]["threshold"] == .72


def test_exact_sequential_copy_retains_orbits_even_for_adjacent_origins():
    graph, nx_graph = _prepare_graph(graph_data(nx.complete_graph(4)))
    config = _read_config(small_config(clone_count=10, repeats=1, noise_levels=[0]))
    result, injected, positives = _inject_clones(graph, nx_graph, config, random.Random(5))
    orbits = _automorphism_state(injected)["orbit_by_node"]
    assert all(orbits[a] == orbits[b] for a, b in positives)
    for node in result["nodes"]:
        if "clone_of" in node:
            assert set(injected[node["id"]]) == set(injected[node["clone_of"]])
    normalize_graph(result)


def test_ground_truth_contains_clone_original_and_sibling_pairs_only():
    graph, nx_graph = _prepare_graph(graph_data(nx.path_graph(3)))
    config = _read_config(small_config(clone_count=8, repeats=1, noise_levels=[0]))
    result, injected, positives = _inject_clones(graph, nx_graph, config, random.Random(1))
    parent = {node["id"]: node["clone_of"] for node in result["nodes"] if "clone_of" in node}
    expected = set()
    for a, b in combinations(sorted(injected), 2):
        if parent.get(a) == b or parent.get(b) == a or (a in parent and b in parent and parent[a] == parent[b]):
            expected.add((a, b))
    assert positives == expected
    assert len(positives) > len(parent)
    assert all(not ({a, b} <= set(nx_graph)) for a, b in positives)
    assert all(node["truth"] == "unknown" for node in result["nodes"])


def test_control_false_positives_are_measured_but_not_in_main_average():
    result = run_experiments(graph_data(nx.cycle_graph(4)), small_config(noise_levels=[0], repeats=1))
    controls = [row for row in result["rows"] if row["control"]]
    assert all(row["actual_positive_pairs"] == 0 and row["tp"] == 0 and row["fn"] == 0 for row in controls)
    assert all(row["recall"] is None for row in controls)
    assert next(row for row in controls if row["method"] == "symmetry")["fp"] == 6
    for summary in result["summary"]:
        main = next(row for row in result["rows"] if not row["control"] and row["method"] == summary["method"])
        assert summary["precision"] == main["precision"]
        assert summary["fp"] == main["fp"]


def test_retention_zero_does_not_force_in_extra_structural_evidence():
    result = run_experiments(graph_data(nx.path_graph(5)), small_config(retention=0, noise_levels=[0], repeats=1))
    for row in result["rows"]:
        if not row["control"]:
            assert row["tp"] == 0
            assert row["recall"] == 0
    edges = result["example_graph"]["edges"]
    clones = {node["id"] for node in result["example_graph"]["nodes"] if "clone_of" in node}
    assert all(edge["source"] not in clones and edge["target"] not in clones for edge in edges)


def test_root_is_preserved_by_noise_and_not_used_as_clone_origin():
    nx_graph = nx.wheel_graph(7)
    graph, canonical = _prepare_graph(graph_data(nx_graph))
    config = _read_config(small_config(root="0", retention=.3, repeats=1, noise_levels=[1]))
    output, injected, positives = _inject_clones(graph, canonical, config, random.Random(8))
    assert all("0" not in pair for pair in positives)
    assert all(node.get("clone_of") != "0" for node in output["nodes"])
    changed, counts = _perturb(injected, 1, "0", random.Random(9))
    assert set(changed["0"]) == set(injected["0"])
    assert counts["deleted_edges"] > 0
    assert not nx.number_of_selfloops(changed)


def test_supplied_truth_and_clone_labels_do_not_leak_into_synthetic_evaluation():
    graph = graph_data(nx.path_graph(6))
    poisoned = deepcopy(graph)
    for index, node in enumerate(poisoned["nodes"]):
        node["truth"] = "bot" if index % 2 else "human"
    poisoned["nodes"][1]["clone_of"] = "0"
    first = run_experiments(graph, small_config(repeats=1))
    second = run_experiments(poisoned, small_config(repeats=1))
    assert without_time(first) == without_time(second)


def test_same_injection_is_used_across_noise_levels_and_order():
    graph = graph_data(nx.path_graph(8))
    first = run_experiments(graph, small_config(noise_levels=[0, .2], repeats=1))
    second = run_experiments(graph, small_config(noise_levels=[.2, 0], repeats=1))
    by_key = lambda result: {(r["noise"], r["method"], r["control"]): without_time(r) for r in result["rows"]}
    assert by_key(first) == by_key(second)


def test_maximum_length_origin_id_still_produces_valid_export():
    graph = {"name": "А" * 160, "nodes": [{"id": "x" * 128}, {"id": "y" * 128}],
             "edges": [{"source": "x" * 128, "target": "y" * 128}]}
    result = run_experiments(graph, small_config(noise_levels=[0], repeats=1))
    normalize_graph(result["example_graph"])


def test_capacity_is_rejected_without_silent_reduction():
    with pytest.raises(ValueError, match="2000"):
        run_experiments(graph_data(nx.path_graph(1999)), small_config())


@pytest.mark.parametrize("config", [{"retention": -1}, {"clone_count": 11}, {"noise_levels": []},
                                    {"noise_levels": [0, 0]}, {"noise_levels": [float("nan")]}, {"repeats": 6},
                                    {"seed": True}, {"threshold": 2}])
def test_invalid_experiment_options_are_rejected(config):
    with pytest.raises(ValueError):
        run_experiments(graph_data(nx.path_graph(4)), config)


def test_combined_experiment_uses_the_same_rule_as_interactive_analysis():
    from app.analysis import analyze_graph
    result = run_experiments(graph_data(nx.path_graph(6)), small_config(noise_levels=[0], repeats=1, threshold=.5))
    example = result["example_graph"]
    analyzed = analyze_graph(example, {"threshold": .5, "max_pairs": 1000})
    parents = {node["id"]: node["clone_of"] for node in example["nodes"] if "clone_of" in node}
    is_positive = lambda a, b: (parents.get(a) == b or parents.get(b) == a
                                or (a in parents and b in parents and parents[a] == parents[b]))
    tp = sum(is_positive(pair["source"], pair["target"]) for pair in analyzed["pairs"])
    row = next(row for row in result["rows"] if row["method"] == "combined" and not row["control"])
    assert row["tp"] == tp
    assert row["fp"] == len(analyzed["pairs"]) - tp
    assert row["candidate_count"] == analyzed["summary"]["candidate_count"]
