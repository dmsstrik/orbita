#!/usr/bin/env python3
"""Build a deterministic sparse social graph with exactly 10,000 vertices.

The base is a Holme–Kim scale-free graph. It receives ten exact false-twin
copies and eighty true-twin pairs with 1..8 shared external neighbours. The
result keeps exact ground truth while producing scores from 2/3 to 1 instead
of a list made only of perfect copies.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import random

import networkx as nx


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "examples" / "social-10000.json"
BASE_NODES = 9_830
CLONE_COUNT = 10
TRUE_TWIN_LEVELS = range(1, 9)
TRUE_TWIN_PAIRS_PER_LEVEL = 10
SEED = 42


def _independent_sources(graph: nx.Graph, count: int) -> list[str]:
    selected: list[str] = []
    for node in sorted(graph, key=lambda value: (graph.degree(value), value)):
        if all(not graph.has_edge(node, other) for other in selected):
            selected.append(node)
            if len(selected) == count:
                return selected
    raise RuntimeError("Не удалось выбрать независимые исходные вершины для клонов.")


def build() -> dict:
    generated = nx.powerlaw_cluster_graph(BASE_NODES, 3, .25, seed=SEED)
    graph = nx.relabel_nodes(generated, {node: f"u{node:05d}" for node in generated})
    sources = _independent_sources(graph, CLONE_COUNT)
    planted: dict[str, str] = {}
    for index, source in enumerate(sources, 1):
        clone = f"clone-{index:02d}"
        graph.add_node(clone)
        graph.add_edges_from((clone, neighbor) for neighbor in list(graph[source]))
        planted[clone] = source

    rng = random.Random(SEED + 10_000)
    anchor_pool = sorted(set(graph) - set(sources) - set(planted))
    planted_true_twins: list[dict] = []
    used_anchor_sets: set[tuple[str, ...]] = set()
    for common_count in TRUE_TWIN_LEVELS:
        for repeat in range(1, TRUE_TWIN_PAIRS_PER_LEVEL + 1):
            while True:
                anchors = tuple(sorted(rng.sample(anchor_pool, common_count)))
                if anchors not in used_anchor_sets:
                    used_anchor_sets.add(anchors)
                    break
            first = f"twin-d{common_count:02d}-p{repeat:02d}-a"
            second = f"twin-d{common_count:02d}-p{repeat:02d}-b"
            graph.add_edge(first, second)
            graph.add_edges_from((first, anchor) for anchor in anchors)
            graph.add_edges_from((second, anchor) for anchor in anchors)
            jaccard = common_count / (common_count + 2)
            planted_true_twins.append({
                "source": first,
                "target": second,
                "common_neighbor_count": common_count,
                "expected_jaccard": round(jaccard, 12),
                "expected_score": round((1 + jaccard) / 2, 12),
            })

    if len(graph) != 10_000:
        raise RuntimeError(f"Ожидалось 10000 вершин, получено {len(graph)}.")

    ranked = sorted(graph, key=lambda node: (-graph.degree(node), node))
    positions: dict[str, tuple[float, float]] = {}
    for index, node in enumerate(ranked):
        angle = index * 2.399963229728653 - math.pi / 2
        radius = .96 * math.sqrt((index + .5) / len(ranked))
        positions[node] = (radius * math.cos(angle), radius * math.sin(angle))
    # Put every planted clone close to its source while retaining distinct
    # coordinates. Coordinates affect the map only, never the analysis.
    for index, (clone, source) in enumerate(planted.items(), 1):
        x, y = positions[source]
        angle = index * 2.399963229728653
        positions[clone] = (x + .008 * math.cos(angle), y + .008 * math.sin(angle))
    for index, pair in enumerate(planted_true_twins):
        angle = 2 * math.pi * index / len(planted_true_twins) - math.pi / 2
        radius = .79 + .13 * ((index % TRUE_TWIN_PAIRS_PER_LEVEL) / (TRUE_TWIN_PAIRS_PER_LEVEL - 1))
        center_x, center_y = radius * math.cos(angle), radius * math.sin(angle)
        tangent_x, tangent_y = -.006 * math.sin(angle), .006 * math.cos(angle)
        positions[pair["source"]] = (center_x + tangent_x, center_y + tangent_y)
        positions[pair["target"]] = (center_x - tangent_x, center_y - tangent_y)

    true_twin_by_node = {
        node: pair for pair in planted_true_twins for node in (pair["source"], pair["target"])
    }

    nodes = []
    for node in sorted(graph):
        item = {
            "id": node,
            "label": f"Модельный аккаунт {node}",
            "x": round(positions[node][0], 7),
            "y": round(positions[node][1], 7),
        }
        if node in planted:
            item["label"] = f"Точная копия {planted[node]}"
            item["clone_of"] = planted[node]
        elif node in true_twin_by_node:
            pair = true_twin_by_node[node]
            side = "A" if node == pair["source"] else "B"
            item["label"] = f"Смежный двойник {side} · {pair['common_neighbor_count']} общих соседей"
        nodes.append(item)

    return {
        "name": "Модельная социальная сеть · 10 000 вершин",
        "nodes": nodes,
        "edges": [
            {"source": source, "target": target}
            for source, target in sorted(tuple(sorted(edge)) for edge in graph.edges)
        ],
        "metadata": {
            "source": "synthetic_powerlaw_cluster",
            "synthetic": True,
            "description": "Разреженный граф на 10 000 вершинах с 90 контрольными симметричными парами и оценками от 0,67 до 1,00.",
            "generator": {
                "model": "networkx.powerlaw_cluster_graph",
                "base_nodes": BASE_NODES,
                "m": 3,
                "triangle_probability": .25,
                "seed": SEED,
            },
            "planted_clones": planted,
            "planted_true_twins": planted_true_twins,
            "score_design": {
                "false_twin_pairs": len(planted),
                "true_twin_pairs": len(planted_true_twins),
                "true_twin_common_neighbor_levels": list(TRUE_TWIN_LEVELS),
                "formula": "true twins with d common external neighbours: J=d/(d+2), S=(1+J)/2",
            },
            "warnings": [
                "Синтетический пример предназначен для проверки масштаба и корректности алгоритма; он не описывает реальных пользователей.",
                "Контрольные пары специально включают несмежных и смежных двойников с разным числом общих соседей; поэтому оценки распределены, а не равны только 1.",
                "Координаты заданы генератором только для быстрой карты и не участвуют в вычислении сходства.",
            ],
        },
    }


def main() -> None:
    graph = build()
    TARGET.write_text(json.dumps(graph, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{TARGET}: {len(graph['nodes'])} вершин, {len(graph['edges'])} рёбер")


if __name__ == "__main__":
    main()
