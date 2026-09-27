#!/usr/bin/env python3
"""Build one large SNAP example from the ten bundled ego-Facebook graphs."""

from __future__ import annotations

from collections import defaultdict
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
TARGET = EXAMPLES / "facebook-large.json"


def global_id(value: object) -> str:
    text = str(value)
    if ":" not in text:
        raise ValueError(f"Ожидался ID с префиксом эго-сети: {text}")
    return text.split(":", 1)[1]


def build() -> dict:
    paths = sorted(EXAMPLES.glob("facebook-[0-9]*.json"), key=lambda path: int(path.stem.split("-")[1]))
    if len(paths) != 10:
        raise ValueError(f"Ожидалось 10 эго-сетей, найдено {len(paths)}.")

    edges: set[tuple[str, str]] = set()
    memberships: dict[str, list[str]] = defaultdict(list)
    egos: list[str] = []
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        ego = str(data["metadata"]["ego"])
        egos.append(ego)
        for node in data["nodes"]:
            identifier = global_id(node["id"])
            if ego not in memberships[identifier]:
                memberships[identifier].append(ego)
        for edge in data["edges"]:
            source, target = global_id(edge["source"]), global_id(edge["target"])
            edges.add(tuple(sorted((source, target))))

    degree: dict[str, int] = defaultdict(int)
    for source, target in edges:
        degree[source] += 1
        degree[target] += 1

    clusters: dict[str, list[str]] = {ego: [] for ego in egos}
    for identifier in sorted(memberships, key=lambda value: (int(value) if value.isdigit() else math.inf, value)):
        clusters[memberships[identifier][0]].append(identifier)

    positions: dict[str, tuple[float, float]] = {}
    for cluster_index, ego in enumerate(egos):
        cluster_angle = 2 * math.pi * cluster_index / len(egos) - math.pi / 2
        center_x, center_y = 3.1 * math.cos(cluster_angle), 2.35 * math.sin(cluster_angle)
        members = sorted(clusters[ego], key=lambda identifier: (-degree[identifier], identifier))
        if ego in members:
            members.remove(ego)
            positions[ego] = (center_x, center_y)
        for index, identifier in enumerate(members):
            angle = index * 2.399963229728653
            radius = .82 * math.sqrt((index + 1) / max(len(members), 1))
            positions[identifier] = (
                center_x + radius * math.cos(angle),
                center_y + radius * math.sin(angle),
            )

    nodes = [
        {
            "id": identifier,
            "label": f"Facebook {identifier}",
            "x": round(positions[identifier][0], 7),
            "y": round(positions[identifier][1], 7),
        }
        for identifier in sorted(positions, key=lambda value: (int(value) if value.isdigit() else math.inf, value))
    ]
    return {
        "name": "SNAP ego-Facebook · объединённый граф",
        "nodes": nodes,
        "edges": [{"source": source, "target": target} for source, target in sorted(edges)],
        "metadata": {
            "source": "snap_ego_facebook_union",
            "dataset": "SNAP ego-Facebook",
            "root": "1684",
            "recommended_radius": 2,
            "description": "Объединение десяти поставляемых эго-сетей по исходным глобальным ID.",
            "warnings": [
                "Обезличенный учебный набор SNAP ego-Facebook (McAuley & Leskovec, 2012); разметки ботов или клонов нет.",
                "Визуальная раскладка группирует вершины по первой эго-сети, в которой встретился ID; она не участвует в анализе.",
            ],
        },
    }


def main() -> None:
    graph = build()
    TARGET.write_text(json.dumps(graph, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{TARGET}: {len(graph['nodes'])} вершин, {len(graph['edges'])} рёбер")


if __name__ == "__main__":
    main()
