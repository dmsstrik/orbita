"""Convert SNAP ego-Facebook archives to Orbita graph JSON.

Source: McAuley & Leskovec, SNAP ego-Facebook (https://snap.stanford.edu/data/ego-Facebook.html).
The <ego>.edges file lists links between the friends of the ego account; the
<ego>.circles file lists friend-list groupings. Both are imported: the ego node
is added, edges are de-duplicated as an undirected simple graph, and circles are
stored in metadata as reference information. IDs are prefixed with the network
number so that graphs from different egos never collide.

Usage: python tools/snap_convert.py [PATH ...] [--out DIR]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def convert(edges_path: Path, circles_path: Path | None, out_dir: Path) -> Path:
    ego = edges_path.stem
    edges: set[tuple[str, str]] = set()
    ids: set[str] = set()

    def node_id(raw: str) -> str:
        return f"fb{ego}:{raw}"

    for line in edges_path.read_text().splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        a, b = node_id(parts[0]), node_id(parts[1])
        ids.update((a, b))
        edges.add(tuple(sorted((a, b))))

    for friend in sorted(ids):
        edges.add(tuple(sorted((node_id(ego), friend))))
    all_ids = {node_id(ego), *ids}

    circles: dict[str, list[str]] = {}
    if circles_path is not None and circles_path.is_file():
        for line in circles_path.read_text().splitlines():
            parts = line.split("\t")
            if len(parts) >= 1:
                circles[parts[0]] = [node_id(x) for x in parts[1:] if x]

    graph = {
        "name": f"SNAP ego-Facebook {ego}",
        "nodes": [{"id": node_id(ego), "label": f"Аккаунт {ego} (центр)"}]
                 + [{"id": x, "label": x.replace(":", "·")} for x in sorted(all_ids - {node_id(ego)})],
        "edges": [{"source": a, "target": b} for a, b in sorted(edges)],
        "metadata": {
            "source": "snap_ego_facebook",
            "dataset": "SNAP ego-Facebook",
            "ego": ego,
            "circles": circles,
            "warnings": [
                "Обезличенные связи Facebook (SNAP ego-Facebook, McAuley & Leskovec, 2012). Разметка кругов не является разметкой ботов или клонов.",
                "Связи соответствуют снимку набора данных; текущая доступность профилей не проверяется.",
            ],
        },
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"facebook-{ego}.json"
    target.write_text(json.dumps(graph, ensure_ascii=False, indent=1), encoding="utf-8")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert SNAP ego-Facebook files to Orbita JSON")
    parser.add_argument("paths", nargs="*", help="Path to <ego>.edges or to the unpacked facebook directory")
    parser.add_argument("--out", type=Path, default=Path("examples"), help="Output directory (default: examples/)")
    args = parser.parse_args()
    paths = [Path(p) for p in args.paths] or [Path("facebook")]
    written = []
    for path in paths:
        if path.is_dir():
            files = sorted(path.glob("*.edges"))
        elif path.suffix == ".edges":
            files = [path]
        else:
            raise SystemExit(f"Не найден .edges файл: {path}")
        for edges_path in files:
            circles_path = edges_path.with_suffix(".circles")
            target = convert(edges_path, circles_path, args.out)
            written.append(target)
            print(f"{target} ({edges_path.stem})")
    if not written:
        raise SystemExit("Нет файлов для конвертации.")


if __name__ == "__main__":
    main()
