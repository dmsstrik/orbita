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

MAX_NODES = 2000
MAX_EDGES = 100_000
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
        "max_pairs": _bounded_integer(raw.get("max_pairs", 2000), "max_pairs", 0, MAX_NODES * (MAX_NODES - 1) // 2),
        "layout_seed": 42,
        "conventions": deepcopy(SCORING_CONVENTIONS),
    }


def _prepare_graph(graph: dict, root: str | None = None, radius: int | None = None) -> tuple[dict, nx.Graph]:
    """Normalize and sort once; radius=None fixes root without cutting the graph."""
    graph = normalize_graph(deepcopy(graph))
    if len(graph["nodes"]) > MAX_NODES or len(graph["edges"]) > MAX_EDGES:
        raise ValueError("Допускается не более 2000 вершин и 100000 рёбер без усечения.")
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


def _iter_pair_features(nx_graph: nx.Graph, state: dict, root: str | None, exclude_root: bool) -> Iterator[dict]:
    neighbors = _neighborhoods(nx_graph, root, exclude_root)
    full_neighbors = {node: set(nx_graph[node]) for node in nx_graph}
    orbit = state["orbit_by_node"]
    for source, target in combinations(sorted(node for node in nx_graph if node != root), 2):
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
        yield {"source": source, "target": target, "same_orbit": same_orbit,
               "orbit_id": orbit[source] if same_orbit else None,
               "common_neighbors": sorted(common), "jaccard": jaccard,
               "orbit_evidence": orbit_evidence, "score": (orbit_evidence + jaccard) / 2,
               "twin_type": twin_type}


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
    candidate_nodes: set[str] = set()
    heap: list[tuple] = []
    rank = {node: i for i, node in enumerate(sorted(nx_graph.nodes))}
    for pair in _iter_pair_features(nx_graph, state, root, options["exclude_root"]):
        if pair["score"] < options["threshold"] or not _has_evidence(pair):
            continue
        candidate_count += 1
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
    try:
        positions = nx.spring_layout(nx_graph, seed=options["layout_seed"], iterations=45, scale=1.0, method="force") if nx_graph else {}
        options["layout_method_actual"] = "spring"
    except ImportError:
        # Spring layout requires the scipy extra; fall back to circular.
        positions = nx.circular_layout(nx_graph)
        options["layout_method_actual"] = "circular"
        warnings.append("Для визуализации использована круговая раскладка: разреженная spring-раскладка недоступна.")
    for node in selected["nodes"]:
        identifier = node["id"]
        node.update(orbit=state["orbit_by_node"][identifier], degree=int(nx_graph.degree(identifier)),
                    x=float(positions[identifier][0]), y=float(positions[identifier][1]))
    count = nx_graph.number_of_nodes()
    edge_count = nx_graph.number_of_edges()
    spacing = 4.6 / max(count ** .5, 1) if count > 120 else None
    if spacing:
        try:
            positions = nx.spring_layout(nx_graph, seed=options["layout_seed"], iterations=90,
                                         k=spacing, scale=1.0, method="force")
            options["layout_method_actual"] = "spring-spaced"
            for node in selected["nodes"]:
                identifier = node["id"]
                node["x"] = float(positions[identifier][0])
                node["y"] = float(positions[identifier][1])
        except ImportError:
            spacing = None
    summary = {"node_count": count, "edge_count": edge_count, "density": nx.density(nx_graph),
               "component_count": nx.number_connected_components(nx_graph), "orbit_count": len(state["orbits"]),
               "nontrivial_orbits": sum(orbit["size"] > 1 for orbit in state["orbits"]),
               "group_order": state["group_order"], "group_order_exact": state["group_order_exact"],
               "group_order_mantissa": state["group_order_mantissa"], "group_order_exponent": state["group_order_exponent"],
               "candidate_count": candidate_count, "returned_pair_count": len(pairs),
               "average_degree": 2 * edge_count / count if count else 0,
               "isolated_count": nx.number_of_isolates(nx_graph), "elapsed_ms": (perf_counter() - started) * 1000}
    return {"graph": selected, "options": options, "summary": summary, "orbits": state["orbits"],
            "pairs": pairs, "warnings": list(dict.fromkeys(warnings)),
            "evaluation": _evaluate_supplied_labels(selected, root, candidate_nodes)}
