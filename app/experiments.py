"""Reproducible experiments with synthetic clone injection."""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import hashlib
from itertools import combinations
import json
import random
from statistics import mean
from time import perf_counter

import networkx as nx

from .analysis import (
    MAX_EDGES, MAX_NODES, _automorphism_state, _bounded_integer,
    _bounded_number, _metrics, _neighborhoods, _prepare_graph,
)

METHODS = ("neighbors", "symmetry", "combined")
EXPERIMENT_CONVENTIONS = {
    "target": "Положительны только пары внедрённый клон–его исходная вершина и клоны одного источника. Остальные пары отрицательны только для этой синтетической задачи, а не как реальные люди или боты.",
    "neighbors": "Обычный Jaccard открытых окрестностей J; кандидат при J≥threshold и J>0.",
    "symmetry": "O=1 для одной точной орбиты и двух непустых эффективных окрестностей; кандидат при O≥threshold и O>0.",
    "combined": "S=(O+J)/2; кандидат при S≥threshold и (O>0 или J>0).",
    "threshold_effect": "При threshold>0.5 combined требует точной общей орбиты, поскольку J/2≤0.5. Поэтому neighbors может обнаруживать частичные дубликаты, пропущенные combined.",
    "root": "Используется весь переданный граф без обрезания по радиусу; root фиксирован и исключён из пар. exclude_root удаляет его из сравниваемых окружений.",
    "injection": "Источники выбираются из исходных вершин с непустой эффективной окрестностью. Каждый новый клон независимо сохраняет соседей текущего источника с вероятностью retention; связь с ego, если она есть, сохраняется всегда. При retention=1 последовательное копирование сохраняет точные структурные дубликаты.",
    "noise": "Удаляются k=round(noise*m) случайных рёбер и добавляются до k случайных исходных нерёбер, где m — число рёбер, не инцидентных фиксированному корню. Инцидентные корню связи не меняются; число добавлений ограничено числом доступных нерёбер.",
    "comparison": "Три метода получают один и тот же изменённый граф, одну совокупность пар и один заранее заданный threshold. Разметка не участвует в алгоритмах. Порог не подбирается по результатам.",
    "controls": "Для каждой noise/repeat обрабатывается отдельный контроль без внедрения, с тем же правилом шума. Все его пары отрицательны для восстановления внедрений; FP не означает число реальных ботов. Контроль исключён из основных средних.",
    "timing": "elapsed_ms включает подготовку окрестностей и проход соответствующего метода; для symmetry/combined также время общего точного вычисления орбит (без повторного запуска nauty). Генерация и визуализация не включены.",
    "undefined_metrics": "precision=null при отсутствии предсказаний, recall=null при отсутствии положительных пар; f1=null при отсутствии и положительных, и предсказанных пар.",
    "replicates": "Внедрения при одном repeat одинаковы для всех noise; повторы независимы. Средние — описательные средние по заданным повторам, без утверждения статистической значимости.",
}


def _read_config(config: dict | None) -> dict:
    if config is not None and not isinstance(config, dict):
        raise ValueError("Параметры эксперимента должны быть объектом.")
    raw = config or {}
    root = raw.get("root")
    if root is not None and not isinstance(root, str):
        raise ValueError("Корень эксперимента должен быть строковым идентификатором или null.")
    excluded = raw.get("exclude_root", True)
    if not isinstance(excluded, bool):
        raise ValueError("exclude_root должен быть true или false.")
    noise = raw.get("noise_levels", [0, .05, .15])
    if not isinstance(noise, list) or not 1 <= len(noise) <= 10:
        raise ValueError("noise_levels: укажите от 1 до 10 уровней шума.")
    levels = [_bounded_number(level, "noise", 0, 1) for level in noise]
    if len(set(levels)) != len(levels):
        raise ValueError("Уровни шума не должны повторяться.")
    return {
        "clone_count": _bounded_integer(raw.get("clone_count", 3), "clone_count", 1, 10),
        "retention": _bounded_number(raw.get("retention", .8), "retention", 0, 1),
        "noise_levels": levels,
        "repeats": _bounded_integer(raw.get("repeats", 3), "repeats", 1, 5),
        "seed": _bounded_integer(raw.get("seed", 42), "seed", 0, 2 ** 32 - 1),
        "threshold": _bounded_number(raw.get("threshold", .65), "threshold", 0, 1),
        "root": root, "exclude_root": excluded,
        "conventions": deepcopy(EXPERIMENT_CONVENTIONS),
    }


def _seed(base: int, *parts) -> int:
    encoded = json.dumps([base, *parts], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return int.from_bytes(hashlib.sha256(encoded).digest()[:16], "big")


def _serialize_graph(graph: dict, nx_graph: nx.Graph) -> dict:
    output = deepcopy(graph)
    output["nodes"] = sorted(output["nodes"], key=lambda node: node["id"])
    output["edges"] = [{"source": a, "target": b} for a, b in sorted(tuple(sorted(edge)) for edge in nx_graph.edges)]
    return output


def _inject_clones(graph: dict, nx_graph: nx.Graph, config: dict, rng: random.Random) -> tuple[dict, nx.Graph, set[tuple[str, str]]]:
    if len(nx_graph) + config["clone_count"] > MAX_NODES:
        raise ValueError("Для внедрения клонов не хватает места: после добавления должно остаться не более 2000 вершин.")
    result = deepcopy(graph)
    for node in result["nodes"]:
        node["truth"] = "unknown"
        for key in ("clone_of", "orbit", "degree", "x", "y"):
            node.pop(key, None)
    generated = nx_graph.copy()
    effective = _neighborhoods(nx_graph, config["root"], config["exclude_root"])
    origins = sorted(node for node in nx_graph if node != config["root"] and effective[node])
    if not origins:
        raise ValueError("Нет исходных вершин с непустым сравниваемым окружением для внедрения. Выберите другой граф или настройки корня.")
    families: dict[str, list[str]] = defaultdict(list)
    for index in range(config["clone_count"]):
        origin = rng.choice(origins)
        identifier = f"synthetic:clone:{index + 1}"
        collision = 0
        while identifier in generated:
            collision += 1
            identifier = f"synthetic:clone:{index + 1}:{collision}"
        # Sources may be adjacent, so copy the current neighborhood of the graph.
        copied = [neighbor for neighbor in sorted(generated[origin])
                  if neighbor == config["root"] or rng.random() < config["retention"]]
        generated.add_node(identifier)
        generated.add_edges_from((identifier, neighbor) for neighbor in copied)
        if generated.number_of_edges() > MAX_EDGES:
            raise ValueError("Внедрение превышает ограничение 20000 рёбер; уменьшите граф или число клонов.")
        result["nodes"].append({"id": identifier, "label": f"Синтетический клон {index + 1} ← {origin}"[:160],
                                "truth": "unknown", "clone_of": origin})
        families[origin].append(identifier)
    positives = {tuple(sorted(pair)) for origin, clones in families.items() for pair in combinations([origin, *clones], 2)}
    result["name"] = f"{graph.get('name', 'Граф')[:125]} — синтетическое внедрение"
    result.setdefault("metadata", {}).update({"source": "synthetic_experiment", "synthetic_target": "injection_provenance_pairs",
                                              "injected_clone_count": config["clone_count"]})
    return _serialize_graph(result, generated), generated, positives


def _perturb(nx_graph: nx.Graph, noise: float, root: str | None, rng: random.Random) -> tuple[nx.Graph, dict]:
    graph = nx_graph.copy()
    existing = sorted(tuple(sorted(edge)) for edge in graph.edges if root not in edge)
    budget = round(noise * len(existing))
    if not budget:
        return graph, {"deleted_edges": 0, "added_edges": 0, "requested_each": budget}
    absent = [(a, b) for a, b in combinations(sorted(node for node in graph if node != root), 2) if not graph.has_edge(a, b)]
    deleted = rng.sample(existing, budget)
    added = rng.sample(absent, min(budget, len(absent)))
    graph.remove_edges_from(deleted)
    graph.add_edges_from(added)
    return graph, {"deleted_edges": len(deleted), "added_edges": len(added), "requested_each": budget}


def _fingerprint(nx_graph: nx.Graph) -> str:
    representation = {"nodes": sorted(nx_graph), "edges": sorted(tuple(sorted(edge)) for edge in nx_graph.edges)}
    return hashlib.sha256(json.dumps(representation, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()[:20]


def _evaluate_methods(nx_graph: nx.Graph, positives: set[tuple[str, str]], config: dict) -> list[dict]:
    started = perf_counter()
    neighbors = _neighborhoods(nx_graph, config["root"], config["exclude_root"])
    eligible = sorted(node for node in nx_graph if node != config["root"])
    neighbors_ms = (perf_counter() - started) * 1000
    started = perf_counter()
    state = _automorphism_state(nx_graph, config["root"])
    orbits_ms = (perf_counter() - started) * 1000
    orbit = state["orbit_by_node"]
    pair_count = len(eligible) * (len(eligible) - 1) // 2
    fingerprint = _fingerprint(nx_graph)
    results = []
    for method in METHODS:
        started = perf_counter()
        tp = fp = 0
        for a, b in combinations(eligible, 2):
            if not neighbors[a] or not neighbors[b]:
                continue
            evidence = int(orbit[a] == orbit[b]) if method != "neighbors" else 0
            jaccard = 0.0
            if method != "symmetry":
                intersection = len(neighbors[a] & neighbors[b])
                union_size = len(neighbors[a]) + len(neighbors[b]) - intersection
                jaccard = intersection / union_size if union_size else 0.0
            score = jaccard if method == "neighbors" else evidence if method == "symmetry" else (evidence + jaccard) / 2
            if score >= config["threshold"] and (evidence > 0 or jaccard > 0):
                if (a, b) in positives:
                    tp += 1
                else:
                    fp += 1
        elapsed_ms = (perf_counter() - started) * 1000 + neighbors_ms + (orbits_ms if method != "neighbors" else 0)
        fn = len(positives) - tp
        results.append({"method": method, **_metrics(tp, fp, fn, pair_count - len(positives) - fp),
                        "elapsed_ms": elapsed_ms, "candidate_count": tp + fp, "actual_positive_pairs": len(positives),
                        "evaluated_pair_count": pair_count, "graph_fingerprint": fingerprint,
                        "node_count": len(nx_graph), "edge_count": nx_graph.number_of_edges()})
    return results


def run_experiments(graph: dict, config: dict | None = None) -> dict:
    config = _read_config(config)
    base, nx_graph = _prepare_graph(graph, config["root"], radius=None)
    warnings = list(base.get("metadata", {}).get("warnings", []))
    if config["root"] is not None:
        warnings.append("Корень фиксирован; связи с корнем сохраняются при внедрении и не изменяются шумом.")
    rows = []
    example_graph = None
    for repeat in range(1, config["repeats"] + 1):
        injection_seed = _seed(config["seed"], "injection", repeat)
        injected, injected_nx, positives = _inject_clones(base, nx_graph, config, random.Random(injection_seed))
        for noise in config["noise_levels"]:
            noise_seed = _seed(config["seed"], "noise", repeat, float(noise).hex())
            perturbed, changes = _perturb(injected_nx, noise, config["root"], random.Random(noise_seed))
            for row in _evaluate_methods(perturbed, positives, config):
                rows.append({"noise": noise, "repeat": repeat, "control": False, **changes, **row})
            if example_graph is None:
                example_graph = _serialize_graph(injected, perturbed)
                example_graph.setdefault("metadata", {})["experiment"] = {"seed": config["seed"], "repeat": repeat,
                    "noise": noise, "retention": config["retention"], "threshold": config["threshold"],
                    "positive_pair_count": len(positives), **changes}
            control, control_changes = _perturb(nx_graph, noise, config["root"], random.Random(noise_seed))
            for row in _evaluate_methods(control, set(), config):
                rows.append({"noise": noise, "repeat": repeat, "control": True, **control_changes, **row})
    summary = []
    for noise in config["noise_levels"]:
        for method in METHODS:
            measurements = [row for row in rows if not row["control"] and row["noise"] == noise and row["method"] == method]
            record = {"noise": noise, "method": method, "repeats": len(measurements)}
            for metric in ("precision", "recall", "f1", "elapsed_ms", "tp", "fp", "fn"):
                values = [row[metric] for row in measurements if row[metric] is not None]
                record[metric] = mean(values) if values else None
                if metric in {"precision", "recall", "f1"}:
                    record[f"{metric}_defined_repeats"] = len(values)
            summary.append(record)
    return {"rows": rows, "summary": summary, "config": config, "warnings": list(dict.fromkeys(warnings)), "example_graph": example_graph}
