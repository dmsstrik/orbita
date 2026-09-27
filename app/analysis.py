"""Exact automorphism orbits and structural pair scoring."""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import heapq
from itertools import combinations
import math
from time import perf_counter
from typing import Iterator

import networkx as nx
import pynauty

from .ingest import normalize_graph

MAX_NODES = 10_000
MAX_EDGES = 500_000
MAX_RETURNED_PAIRS = 20_000
MAX_DETAILED_PAIRS = 5_000_000
SPRING_LAYOUT_MAX_NODES = 2_000
SCORING_CONVENTIONS = {
    "target": "Структурное сходство пары аккаунтов.",
    "jaccard": "J(u,v)=|A(u)∩A(v)|/|A(u)∪A(v)|; A(v)=N(v) без корня при exclude_root=true. Пустое объединение даёт 0.",
    "orbit_evidence": "O(u,v)=1 для разных вершин одной нетривиальной точной орбиты с непустыми A; иначе 0.",
    "score": "S(u,v)=(O(u,v)+J(u,v))/2. Кандидат: S≥threshold и (O>0 или J>0). Корень не участвует в парах.",
    "threshold_effect": "При threshold>0.5 отсутствие точной общей орбиты исключает пару: J/2≤0.5.",
    "twins": "false_twins: N(u)=N(v), u и v несмежны; true_twins: N[u]=N[v], u и v смежны. Проверка на полном выбранном графе, отдельно от обычного Jaccard.",
    "symmetry_scope": "Точные автоморфизмы выбранного индуцированного графа; при указанном корне он фиксирован.",
    "truth": "truth и clone_of используются только для оценки, никогда для вычисления орбит или score.",
    "pair_limit": "max_pairs ограничивает только выдачу; счётчики и оценка используют все пары кандидатов.",
    "pair_screening": "Все допустимые пары покрываются точным предварительным правилом. До подробного расчёта отбрасываются только пары, которые математически не могут достичь выбранного порога.",
}


def _bounded_number(value, name: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: требуется число от {minimum} до {maximum}.")
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{name}: требуется число от {minimum} до {maximum}.")
    return float(value)


def _bounded_integer(value, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{name}: требуется целое число от {minimum} до {maximum}.")
    return value


def _read_options(options: dict | None) -> dict:
    if options is not None and not isinstance(options, dict):
        raise ValueError("Параметры анализа должны быть объектом.")
    raw = options or {}
    root = raw.get("root")
    if root is not None and not isinstance(root, str):
        raise ValueError("Корень графа должен быть строковым идентификатором или null.")
    excluded = raw.get("exclude_root", True)
    if not isinstance(excluded, bool):
        raise ValueError("exclude_root должен быть true или false.")
    return {
        "root": root,
        "radius": _bounded_integer(raw.get("radius", 1), "radius", 1, 3),
        "threshold": _bounded_number(raw.get("threshold", .65), "threshold", 0, 1),
        "exclude_root": excluded,
        "max_pairs": _bounded_integer(raw.get("max_pairs", 2000), "max_pairs", 0, MAX_RETURNED_PAIRS),
        "layout_seed": 42,
        "conventions": deepcopy(SCORING_CONVENTIONS),
    }


def _prepare_graph(graph: dict, root: str | None = None, radius: int | None = None) -> tuple[dict, nx.Graph]:
    """Normalize and sort once; radius=None fixes root without cutting the graph."""
    graph = normalize_graph(graph)
    graph["nodes"] = sorted(graph["nodes"], key=lambda node: node["id"])
    nx_graph = nx.Graph()
    nx_graph.add_nodes_from(node["id"] for node in graph["nodes"])
    nx_graph.add_edges_from((edge["source"], edge["target"]) for edge in graph["edges"])
    if root is not None and root not in nx_graph:
        raise ValueError(f"Корневая вершина «{root}» отсутствует в графе.")
    if root is not None and radius is not None:
        keep = set(nx.single_source_shortest_path_length(nx_graph, root, cutoff=radius))
        nx_graph = nx_graph.subgraph(keep).copy()
        graph["nodes"] = [node for node in graph["nodes"] if node["id"] in keep]
        metadata = graph.setdefault("metadata", {})
        metadata["analysis_scope"] = {"root": root, "radius": radius, "induced": True}
        metadata["root"] = root
        removed_clone_labels = 0
        for node in graph["nodes"]:
            if node.get("clone_of") is not None and node["clone_of"] not in keep:
                node.pop("clone_of")
                removed_clone_labels += 1
        if removed_clone_labels:
            metadata.setdefault("warnings", []).append(
                f"У {removed_clone_labels} вершин исходная clone_of ссылается за пределы выбранной окрестности; ссылка исключена из локальной выгрузки. Отсутствие ссылки не означает отрицательную метку.")
    if nx_graph.number_of_nodes() > MAX_NODES or nx_graph.number_of_edges() > MAX_EDGES:
        size = f"{nx_graph.number_of_nodes()} вершин и {nx_graph.number_of_edges()} рёбер"
        if root is None:
            raise ValueError(
                f"Полный граф содержит {size}. Для точного анализа выберите центр и радиус; "
                f"одна область анализа должна содержать не более {MAX_NODES} вершин и {MAX_EDGES} рёбер."
            )
        raise ValueError(
            f"Окрестность радиуса {radius} содержит {size}. Уменьшите радиус или выберите другой центр; "
            f"предел точного анализа — {MAX_NODES} вершин и {MAX_EDGES} рёбер."
        )
    graph["edges"] = [{"source": a, "target": b} for a, b in sorted(tuple(sorted(edge)) for edge in nx_graph.edges)]
    # Layout depends on insertion order, so rebuild the graph from sorted edges.
    canonical = nx.Graph()
    canonical.add_nodes_from(sorted(nx_graph.nodes))
    canonical.add_edges_from((edge["source"], edge["target"]) for edge in graph["edges"])
    return graph, canonical


def _automorphism_state(nx_graph: nx.Graph, root: str | None = None) -> dict:
    ids = sorted(nx_graph.nodes)
    if not ids:
        return {"orbits": [], "orbit_by_node": {}, "group_order": "1", "group_order_exact": True, "group_order_mantissa": 1.0, "group_order_exponent": 0}
    index = {identifier: i for i, identifier in enumerate(ids)}
    coloring = [{index[root]}] if root is not None else []
    graph = pynauty.Graph(
        number_of_vertices=len(ids), directed=False,
        adjacency_dict={index[node]: sorted(index[n] for n in nx_graph[node]) for node in ids},
        vertex_coloring=coloring,
    )
    _generators, mantissa, exponent, orbit_numbers, _count = pynauty.autgrp(graph)
    buckets: dict[int, list[str]] = defaultdict(list)
    for node, orbit in zip(ids, orbit_numbers):
        buckets[orbit].append(node)
    groups = sorted(buckets.values(), key=lambda nodes: nodes[0])
    orbits = [{"id": number, "nodes": nodes, "size": len(nodes)} for number, nodes in enumerate(groups)]
    orbit_by_node = {node: orbit["id"] for orbit in orbits for node in orbit["nodes"]}
    # nauty returns the group order as a double mantissa and decimal exponent.
    exact = exponent == 0 and mantissa <= 2 ** 53 and float(mantissa).is_integer()
    group_order = str(int(mantissa)) if exact else f"≈ {mantissa:.12g} × 10^{exponent}"
    return {"orbits": orbits, "orbit_by_node": orbit_by_node, "group_order": group_order,
            "group_order_exact": exact, "group_order_mantissa": float(mantissa), "group_order_exponent": int(exponent)}


def _neighborhoods(nx_graph: nx.Graph, root: str | None, exclude_root: bool) -> dict[str, set[str]]:
    return {node: set(nx_graph[node]) - ({root} if root is not None and exclude_root else set()) for node in nx_graph}


def _pair_features(source: str, target: str, neighbors: dict[str, set[str]],
                   full_neighbors: dict[str, set[str]], orbit: dict[str, int]) -> dict:
    a, b = neighbors[source], neighbors[target]
    common = a & b
    union_size = len(a) + len(b) - len(common)
    jaccard = len(common) / union_size if union_size else 0.0
    same_orbit = orbit[source] == orbit[target]
    orbit_evidence = int(same_orbit and bool(a) and bool(b))
    twin_type = None
    if target not in full_neighbors[source] and full_neighbors[source] == full_neighbors[target]:
        twin_type = "false_twins"
    elif target in full_neighbors[source] and (full_neighbors[source] | {source}) == (full_neighbors[target] | {target}):
        twin_type = "true_twins"
    return {"source": source, "target": target, "same_orbit": same_orbit,
            "orbit_id": orbit[source] if same_orbit else None,
            "common_neighbors": sorted(common), "jaccard": jaccard,
            "orbit_evidence": orbit_evidence, "score": (orbit_evidence + jaccard) / 2,
            "twin_type": twin_type}


def _iter_pair_features(nx_graph: nx.Graph, state: dict, root: str | None, exclude_root: bool) -> Iterator[dict]:
    """Reference iterator over every unordered eligible pair."""
    neighbors = _neighborhoods(nx_graph, root, exclude_root)
    full_neighbors = {node: set(nx_graph[node]) for node in nx_graph}
    orbit = state["orbit_by_node"]
    for source, target in combinations(sorted(node for node in nx_graph if node != root), 2):
        yield _pair_features(source, target, neighbors, full_neighbors, orbit)


def _relevant_pair_keys(nx_graph: nx.Graph, state: dict, root: str | None,
                        exclude_root: bool, threshold: float,
                        neighbors: dict[str, set[str]] | None = None) -> Iterator[tuple[str, str]]:
    """Yield exactly the pairs that can still pass the candidate rule.

    A pair outside a common non-trivial orbit has O=0. A pair without a
    shared effective neighbour has J=0. These two facts let sparse large
    graphs avoid a quadratic scan without changing a score or candidate.
    """
    eligible = sorted(node for node in nx_graph if node != root)
    neighbors = neighbors if neighbors is not None else _neighborhoods(nx_graph, root, exclude_root)
    orbit = state["orbit_by_node"]
    by_effective_neighbor: dict[str, list[str]] = defaultdict(list)
    for node in eligible:
        for neighbor in neighbors[node]:
            by_effective_neighbor[neighbor].append(node)

    def pair_count(size: int) -> int:
        return size * (size - 1) // 2

    if threshold > .5:
        upper_bound = 0
        for holders in by_effective_neighbor.values():
            counts: dict[int, int] = defaultdict(int)
            for node in holders:
                counts[orbit[node]] += 1
            upper_bound += sum(pair_count(size) for size in counts.values())
    else:
        orbit_counts: dict[int, int] = defaultdict(int)
        for node in eligible:
            if neighbors[node]:
                orbit_counts[orbit[node]] += 1
        upper_bound = sum(pair_count(size) for size in orbit_counts.values())
        upper_bound += sum(pair_count(len(holders)) for holders in by_effective_neighbor.values())
    if upper_bound > MAX_DETAILED_PAIRS:
        raise ValueError(
            f"Для выбранного порога верхняя оценка подробной проверки превышает {MAX_DETAILED_PAIRS} пар. "
            "Выберите центр и меньший радиус либо повысьте порог; скрытого усечения результатов нет."
        )

    seen: set[tuple[str, str]] = set()

    def remember(source: str, target: str) -> tuple[str, str] | None:
        key = (source, target) if source < target else (target, source)
        if key in seen:
            return None
        if len(seen) >= MAX_DETAILED_PAIRS:
            raise ValueError(
                f"Структура графа требует подробно проверить более {MAX_DETAILED_PAIRS} пар. "
                "Выберите центр и меньший радиус либо повысьте порог; скрытого усечения результатов нет."
            )
        seen.add(key)
        return key

    if threshold <= .5:
        # Every same-orbit pair with non-empty effective neighbourhoods can
        # reach the threshold even when J=0.
        by_orbit: dict[int, list[str]] = defaultdict(list)
        for node in eligible:
            if neighbors[node]:
                by_orbit[orbit[node]].append(node)
        for orbit_id in sorted(by_orbit):
            for source, target in combinations(sorted(by_orbit[orbit_id]), 2):
                key = remember(source, target)
                if key is not None:
                    yield key

    # A cross-orbit pair, and every pair at threshold > .5, needs J>0.
    # Generate such pairs through the shared effective neighbour itself.
    for common_neighbor in sorted(by_effective_neighbor):
        holders = sorted(by_effective_neighbor[common_neighbor])
        for source, target in combinations(holders, 2):
            if threshold > .5 and orbit[source] != orbit[target]:
                continue
            key = remember(source, target)
            if key is not None:
                yield key


def _iter_relevant_pair_features(nx_graph: nx.Graph, state: dict, root: str | None,
                                 exclude_root: bool, threshold: float,
                                 neighbors: dict[str, set[str]] | None = None) -> Iterator[dict]:
    neighbors = neighbors if neighbors is not None else _neighborhoods(nx_graph, root, exclude_root)
    full_neighbors = neighbors if root is None or not exclude_root else {
        node: set(nx_graph[node]) for node in nx_graph
    }
    orbit = state["orbit_by_node"]
    for source, target in _relevant_pair_keys(
            nx_graph, state, root, exclude_root, threshold, neighbors):
        yield _pair_features(source, target, neighbors, full_neighbors, orbit)


def _has_evidence(pair: dict) -> bool:
    return pair["orbit_evidence"] > 0 or pair["jaccard"] > 0


def _pair_reasons(pair: dict) -> list[str]:
    reasons = []
    if pair["orbit_evidence"]:
        reasons.append("Одна точная орбита при непустых сравниваемых окружениях.")
    if pair["twin_type"] == "false_twins":
        reasons.append("Структурные двойники: одинаковые открытые окрестности, вершины несмежны.")
    if pair["twin_type"] == "true_twins":
        reasons.append("Смежные двойники: одинаковые закрытые окрестности; обычный Jaccard открытых окрестностей может быть меньше 1.")
    if pair["common_neighbors"]:
        reasons.append(f"Общих соседей в сравниваемых окружениях: {len(pair['common_neighbors'])}.")
    return reasons


def _metrics(tp: int, fp: int, fn: int, tn: int | None = None) -> dict:
    result = {"tp": tp, "fp": fp, "fn": fn,
              "precision": tp / (tp + fp) if tp + fp else None,
              "recall": tp / (tp + fn) if tp + fn else None,
              "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None}
    if tn is not None:
        result["tn"] = tn
    return result


def _evaluate_supplied_labels(graph: dict, root: str | None, candidate_nodes: set[str]) -> dict | None:
    nodes = [node for node in graph["nodes"] if node["id"] != root]
    known = [node for node in nodes if node.get("truth") in {"bot", "human"}]
    if not known:
        return None
    if len(known) != len(nodes):
        return {"note": "Разметка неполна: метрики не рассчитаны. Неизвестные аккаунты не считаются людьми.",
            "complete": False, "labeled_count": len(known), "eligible_count": len(nodes), "unit": "node"}
    actual_bots = {node["id"] for node in nodes if node["truth"] == "bot"}
    actual_humans = {node["id"] for node in nodes if node["truth"] == "human"}
    return {"note": "Оценка по полной разметке bot/human на уровне вершин. Предсказано положительным: вершина входит хотя бы в одну пару кандидатов.",
            "complete": True, "unit": "node", "target": "supplied_bot_labels", "labeled_count": len(known),
            "eligible_count": len(nodes), "predicted_positive_count": len(candidate_nodes),
            **_metrics(len(candidate_nodes & actual_bots), len(candidate_nodes & actual_humans),
                       len(actual_bots - candidate_nodes), len(actual_humans - candidate_nodes))}


def analyze_graph(graph: dict, options: dict | None = None) -> dict:
    started = perf_counter()
    options = _read_options(options)
    selected, nx_graph = _prepare_graph(graph, options["root"], options["radius"] if options["root"] is not None else None)
    root = options["root"]
    state = _automorphism_state(nx_graph, root)
    warnings = list(selected.get("metadata", {}).get("warnings", []))
    if not state["group_order_exact"]:
        warnings.append("Орбиты вычислены точно; порядок группы показан приближённо (мантисса и степень десяти).")
    neighbors = _neighborhoods(nx_graph, root, options["exclude_root"])
    empty_count = sum(not neighbors[node] for node in nx_graph if node != root)
    if empty_count:
        warnings.append(f"У {empty_count} вершин пустые сравниваемые окрестности.")
    candidate_count = 0
    candidate_score_min: float | None = None
    candidate_score_max: float | None = None
    scored_pair_count = 0
    candidate_nodes: set[str] = set()
    heap: list[tuple] = []
    rank = {node: i for i, node in enumerate(sorted(nx_graph.nodes))}
    for pair in _iter_relevant_pair_features(
            nx_graph, state, root, options["exclude_root"], options["threshold"], neighbors):
        scored_pair_count += 1
        if pair["score"] < options["threshold"] or not _has_evidence(pair):
            continue
        candidate_count += 1
        candidate_score_min = pair["score"] if candidate_score_min is None else min(candidate_score_min, pair["score"])
        candidate_score_max = pair["score"] if candidate_score_max is None else max(candidate_score_max, pair["score"])
        candidate_nodes.update((pair["source"], pair["target"]))
        if not options["max_pairs"]:
            continue
        item = (pair["score"], -rank[pair["source"]], -rank[pair["target"]], pair)
        if len(heap) < options["max_pairs"]:
            heapq.heappush(heap, item)
        elif item[:3] > heap[0][:3]:
            heapq.heapreplace(heap, item)
    pairs = sorted((item[3] for item in heap), key=lambda p: (-p["score"], p["source"], p["target"]))
    for pair in pairs:
        pair["reasons"] = _pair_reasons(pair)
    if candidate_count > len(pairs):
        warnings.append(f"Показаны {len(pairs)} из {candidate_count} пар.")
    count = nx_graph.number_of_nodes()
    edge_count = nx_graph.number_of_edges()
    source_positions = {
        node["id"]: (float(node["x"]), float(node["y"]))
        for node in selected["nodes"] if "x" in node and "y" in node
    }
    if count > SPRING_LAYOUT_MAX_NODES and len(source_positions) == count:
        positions = source_positions
        options["layout_method_actual"] = "source"
    elif count > SPRING_LAYOUT_MAX_NODES:
        positions = nx.circular_layout(nx_graph)
        options["layout_method_actual"] = "circular-large"
        warnings.append("Для большой области использована линейная круговая раскладка; она влияет только на карту.")
    else:
        spacing = 4.6 / max(count ** .5, 1) if count > 120 else None
        try:
            positions = nx.spring_layout(
                nx_graph,
                seed=options["layout_seed"],
                iterations=70 if spacing else 45,
                k=spacing,
                scale=1.0,
                method="force",
            ) if nx_graph else {}
            options["layout_method_actual"] = "spring-spaced" if spacing else "spring"
        except ImportError:
            # Spring layout requires the scipy extra; fall back to circular.
            positions = nx.circular_layout(nx_graph)
            options["layout_method_actual"] = "circular"
            warnings.append("Для визуализации использована круговая раскладка: разреженная spring-раскладка недоступна.")
    for node in selected["nodes"]:
        identifier = node["id"]
        node.update(orbit=state["orbit_by_node"][identifier], degree=int(nx_graph.degree(identifier)),
                    x=float(positions[identifier][0]), y=float(positions[identifier][1]))
    eligible_count = count - int(root is not None)
    possible_pair_count = eligible_count * (eligible_count - 1) // 2
    summary = {"node_count": count, "eligible_node_count": eligible_count,
               "edge_count": edge_count, "density": nx.density(nx_graph),
               "component_count": nx.number_connected_components(nx_graph), "orbit_count": len(state["orbits"]),
               "nontrivial_orbits": sum(orbit["size"] > 1 for orbit in state["orbits"]),
               "group_order": state["group_order"], "group_order_exact": state["group_order_exact"],
               "group_order_mantissa": state["group_order_mantissa"], "group_order_exponent": state["group_order_exponent"],
               "possible_pair_count": possible_pair_count, "scored_pair_count": scored_pair_count,
               "candidate_count": candidate_count, "returned_pair_count": len(pairs),
               "candidate_score_min": candidate_score_min, "candidate_score_max": candidate_score_max,
               "average_degree": 2 * edge_count / count if count else 0,
               "isolated_count": nx.number_of_isolates(nx_graph), "elapsed_ms": (perf_counter() - started) * 1000}
    return {"graph": selected, "options": options, "summary": summary, "orbits": state["orbits"],
            "pairs": pairs, "warnings": list(dict.fromkeys(warnings)),
            "evaluation": _evaluate_supplied_labels(selected, root, candidate_nodes)}
