"""Headless command-line runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .exports import candidates_csv, experiments_csv, html_report
from .ingest import apply_labels, parse_graph
from .jobs import run_job


def _json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Пакетный структурный анализ графов — Орбита")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, description in [("analyze", "Анализ и HTML/CSV-отчёт"), ("experiment", "Воспроизводимый модельный эксперимент")]:
        command = commands.add_parser(name, help=description)
        command.add_argument("graph", type=Path)
        command.add_argument("--out", type=Path, default=Path("output") / name)
        command.add_argument("--root", default=None)
        command.add_argument("--threshold", type=float, default=0.65)
        command.add_argument("--include-root-neighbors", action="store_true", help="Учитывать ego как общего соседа")
        if name == "analyze":
            command.add_argument("--radius", type=int, default=1)
            command.add_argument("--labels", type=Path)
        else:
            command.add_argument("--clones", type=int, default=3)
            command.add_argument("--retention", type=float, default=0.8)
            command.add_argument("--noise", type=float, nargs="+", default=[0, 0.05, 0.15])
            command.add_argument("--repeats", type=int, default=3)
            command.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    try:
        graph = parse_graph(args.graph.read_bytes(), args.graph.name)
        options = {"root": args.root, "threshold": args.threshold, "exclude_root": not args.include_root_neighbors}
        if args.command == "analyze":
            if args.labels:
                graph = apply_labels(graph, args.labels.read_bytes(), args.labels.name)
            options["radius"] = args.radius
            result = run_job("analyze", graph, options, timeout=30)
            args.out.mkdir(parents=True, exist_ok=True)
            _json(args.out / "source-graph.json", graph)
            _json(args.out / "subgraph.json", result["graph"])
            _json(args.out / "analysis.json", result)
            (args.out / "candidates.csv").write_text(candidates_csv(result), encoding="utf-8")
            (args.out / "report.html").write_text(html_report(result), encoding="utf-8")
            print(f"Вершин: {result['summary']['node_count']}; орбит: {result['summary']['orbit_count']}; пар кандидатов: {result['summary']['candidate_count']}")
        else:
            options.update(clone_count=args.clones, retention=args.retention, noise_levels=args.noise, repeats=args.repeats, seed=args.seed)
            result = run_job("experiments", graph, options, timeout=120)
            args.out.mkdir(parents=True, exist_ok=True)
            _json(args.out / "source-graph.json", graph)
            _json(args.out / "experiments.json", result)
            _json(args.out / "example-graph.json", result["example_graph"])
            (args.out / "experiments.csv").write_text(experiments_csv(result), encoding="utf-8")
            print(f"Результатов: {len(result['rows'])}; seed: {result['config']['seed']}")
        print(f"Сохранено в {args.out.resolve()}")
    except (ValueError, OSError, TimeoutError, RuntimeError) as error:
        parser.exit(1, f"Ошибка: {error}\n")


if __name__ == "__main__":
    main()
