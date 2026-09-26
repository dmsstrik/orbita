#!/usr/bin/env python3
"""End-to-end verification: injected synthetic clones are detected as candidates.

Injects clones with known provenance into real SNAP ego graphs, runs the
product analysis, and reports whether clone-source pairs appear in the
candidate table, at which rank, and how the supplied-labels evaluation scores
them. Perfect copies (retention=1.0) must be found at the default threshold;
partial copies (retention=0.8) are expected to need a lower threshold.
"""
from __future__ import annotations

import csv
import io
import random
import time
from pathlib import Path

from app.analysis import _prepare_graph, analyze_graph
from app.experiments import _inject_clones
from app.ingest import apply_labels, parse_graph

EGOS = ["3980", "0", "107"]
SWEEP = [0.65, 0.5, 0.4, 0.35, 0.3, 0.25]


def fmt(value):
    return "—" if value is None else f"{value:.3f}"


def load(ego: str):
    return parse_graph(Path(f"examples/facebook-{ego}.json").read_bytes(), f"facebook-{ego}.json")


def labels_csv(injected: dict) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "truth"])
    for node in injected["nodes"]:
        writer.writerow([node["id"], "bot" if node["id"].startswith("synthetic:") else "human"])
    return buffer.getvalue().encode()


def evaluate(ego: str, retention: float, thresholds: list[float], clone_count: int = 5) -> None:
    graph = load(ego)
    base, nx_graph = _prepare_graph(graph, None, None)
    config = {"root": None, "exclude_root": True, "clone_count": clone_count, "retention": retention}
    injected, inj_nx, _positives = _inject_clones(base, nx_graph, config, random.Random(42))
    mapping = {n["id"]: n["clone_of"] for n in injected["nodes"] if n.get("clone_of")}
    target_pairs = {tuple(sorted((c, s))) for c, s in mapping.items()}
    print(f"\n=== facebook-{ego}: {clone_count} клонов, retention={retention} ===")

    if retention < 1.0:
        jaccards = []
        for clone, source in mapping.items():
            a, b = set(inj_nx[clone]), set(inj_nx[source])
            union = len(a | b)
            jaccards.append(len(a & b) / union if union else 0.0)
        print(f"  Жаккар клон-источник по факту: " + ", ".join(f"{j:.2f}" for j in sorted(jaccards, reverse=True)))

    for threshold in thresholds:
        started = time.perf_counter()
        result = analyze_graph(injected, {"threshold": threshold, "max_pairs": 20000})
        elapsed = (time.perf_counter() - started) * 1000
        found: dict[tuple[str, str], tuple[float, int]] = {}
        for rank, pair in enumerate(result["pairs"], 1):
            key = tuple(sorted((pair["source"], pair["target"])))
            if key in target_pairs and key not in found:
                found[key] = (pair["score"], rank)
        status = "PASS" if len(found) == len(target_pairs) else ("частично" if found else "НЕТ")
        print(f"  порог {threshold:<5}: пар клон-источник {len(found)}/{len(target_pairs)} [{status}]; "
              f"кандидатов всего {result['summary']['candidate_count']}; {elapsed:.0f} мс")
        if threshold == thresholds[0]:
            for (clone, source), (score, rank) in sorted(found.items(), key=lambda item: item[1][1]):
                print(f"      {clone} → {source}: score={score:.3f}, ранг {rank}")

    labeled = apply_labels(injected, labels_csv(injected), "labels.csv")
    result = analyze_graph(labeled, {"threshold": thresholds[0], "max_pairs": 20000})
    evaluation = result.get("evaluation") or {}
    print(f"  разметка (клоны=bot) при пороге {thresholds[0]}: "
          f"P={fmt(evaluation.get('precision'))} R={fmt(evaluation.get('recall'))} F1={fmt(evaluation.get('f1'))} "
          f"TP={evaluation.get('tp')} FP={evaluation.get('fp')} FN={evaluation.get('fn')}")


def main() -> None:
    for ego in EGOS:
        evaluate(ego, 1.0, [0.65])
        evaluate(ego, 0.8, SWEEP)
    print("\nГотово.")


if __name__ == "__main__":
    main()
