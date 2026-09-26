"""Graph import, validation and bundled demo graphs."""

from __future__ import annotations

import copy
import csv
import io
import json
import math
import re
from pathlib import Path

MAX_NODES = 2000
MAX_EDGES = 100_000
MAX_CONTENT_BYTES = 20_000_000
TRUTHS = {"bot", "human", "unknown"}


def _text(value, field: str, maximum: int, *, empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field}: требуется текст.")
    value = value.strip()
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise ValueError(f"{field}: текст содержит некорректные символы Unicode.") from None
    if (not value and not empty) or len(value) > maximum:
        raise ValueError(f"{field}: длина должна быть от {0 if empty else 1} до {maximum} символов.")
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError(f"{field}: управляющие символы недопустимы.")
    return value


def _identifier(value, field: str = "ID вершины") -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError(f"{field}: требуется строка или целое число.")
    return _text(str(value), field, 128)


def _content_text(content: str | bytes) -> tuple[str, list[str]]:
    warnings = []
    if isinstance(content, bytes):
        if len(content) > MAX_CONTENT_BYTES:
            raise ValueError("Файл слишком большой: максимум 20 МБ.")
        try:
            content = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                content = content.decode("cp1251")
                warnings.append("Файл прочитан в кодировке Windows-1251; для обмена рекомендуется UTF-8.")
            except UnicodeDecodeError as exc:
                raise ValueError("Не удалось прочитать текст: используйте UTF-8 или Windows-1251.") from exc
    elif not isinstance(content, str):
        raise ValueError("Содержимое файла должно быть текстом.")
    try:
        encoded_length = len(content.encode("utf-8"))
    except UnicodeError:
        raise ValueError("Файл содержит некорректные символы Unicode. Сохраните его в UTF-8.") from None
    if encoded_length > MAX_CONTENT_BYTES:
        raise ValueError("Файл слишком большой: максимум 20 МБ.")
    content = content.lstrip("\ufeff")
    if "\x00" in content:
        raise ValueError("Обнаружен нулевой байт. Загрузите текстовый CSV или JSON.")
    if not content.strip():
        raise ValueError("Файл пуст.")
    return content, warnings


def _metadata(value, ids: set[str]) -> dict:
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ValueError("metadata должен быть объектом JSON.")
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
        if len(encoded.encode("utf-8")) > 100_000:
            raise ValueError("Слишком большой раздел metadata: максимум 100 КБ.")
        result = json.loads(encoded)
    except (TypeError, OverflowError, RecursionError) as exc:
        raise ValueError("metadata должен содержать только значения JSON.") from exc
    except ValueError as exc:
        if str(exc).startswith("Слишком большой"):
            raise
        raise ValueError("metadata должен содержать только конечные JSON-значения.") from exc
    warnings = result.get("warnings", [])
    if not isinstance(warnings, list) or len(warnings) > 500:
        raise ValueError("metadata.warnings должен быть списком до 500 предупреждений.")
    result["warnings"] = [_text(w, "Предупреждение", 2000) for w in warnings]
    if result.get("root") is not None:
        result["root"] = _identifier(result["root"], "metadata.root")
        if result["root"] not in ids:
            raise ValueError("metadata.root ссылается на отсутствующую вершину.")
    if "missing_nodes" in result:
        if not isinstance(result["missing_nodes"], list) or len(result["missing_nodes"]) > MAX_NODES:
            raise ValueError("metadata.missing_nodes должен быть списком ID.")
        result["missing_nodes"] = [_identifier(x) for x in result["missing_nodes"]]
    return result


def normalize_graph(data: dict) -> dict:
    """Return a new simple graph without modifying the input."""
    if not isinstance(data, dict):
        raise ValueError("Граф должен быть объектом JSON с полями nodes и edges.")
    if data.get("directed", False) is not False:
        raise ValueError("Поддерживаются только неориентированные графы: directed должен быть false.")
    raw_nodes = data.get("nodes")
    raw_edges = data.get("edges", [])
    if not isinstance(raw_edges, list):
        raise ValueError("edges должен быть списком рёбер.")
    if len(raw_edges) > MAX_EDGES:
        raise ValueError(f"Слишком много рёбер: максимум {MAX_EDGES} записей.")
    if raw_nodes is not None and not isinstance(raw_nodes, list):
        raise ValueError("nodes должен быть списком вершин.")
    nodes: dict[str, dict] = {}
    for raw in raw_nodes or []:
        raw = raw if isinstance(raw, dict) else {"id": raw}
        if "id" not in raw:
            raise ValueError("У каждой вершины должен быть id.")
        node_id = _identifier(raw["id"])
        if node_id in nodes:
            raise ValueError(f"ID вершины повторяется: {node_id}.")
        node = {"id": node_id, "label": _text(raw.get("label", node_id), "Название вершины", 160)}
        if "truth" in raw:
            if not isinstance(raw["truth"], str) or raw["truth"] not in TRUTHS:
                raise ValueError(f"Вершина {node_id}: truth должен быть bot, human или unknown.")
            node["truth"] = raw["truth"]
        if raw.get("clone_of") not in (None, ""):
            node["clone_of"] = _identifier(raw["clone_of"], "clone_of")
        for key in ("x", "y", "orbit", "degree"):
            if key in raw:
                val = raw[key]
                try:
                    finite = not isinstance(val, bool) and isinstance(val, (int, float)) and math.isfinite(val)
                except (ValueError, OverflowError):
                    finite = False
                if not finite:
                    raise ValueError(f"Поле {key} должно быть конечным числом.")
                node[key] = val
        nodes[node_id] = node
        if len(nodes) > MAX_NODES:
            raise ValueError(f"Слишком много вершин: максимум {MAX_NODES}.")
    seen, edges = set(), []
    loops = duplicates = 0
    for index, raw in enumerate(raw_edges, 1):
        if isinstance(raw, dict) and "source" in raw and "target" in raw:
            source, target = raw["source"], raw["target"]
        elif isinstance(raw, (list, tuple)) and len(raw) == 2:
            source, target = raw
        else:
            raise ValueError(f"Ребро {index}: нужны source и target или пара [ID, ID].")
        source, target = _identifier(source), _identifier(target)
        for node_id in (source, target):
            if node_id not in nodes:
                if raw_nodes is not None:
                    raise ValueError(f"Ребро {index} ссылается на отсутствующую вершину {node_id}.")
                nodes[node_id] = {"id": node_id, "label": node_id}
        if len(nodes) > MAX_NODES:
            raise ValueError(f"Слишком много вершин: максимум {MAX_NODES}.")
        if source == target:
            loops += 1
            continue
        key = tuple(sorted((source, target)))
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        edges.append({"source": key[0], "target": key[1]})
    if not nodes:
        raise ValueError("В графе нет вершин. Для изолятов добавьте nodes в JSON.")
    for node in nodes.values():
        target = node.get("clone_of")
        if target is not None and (target not in nodes or target == node["id"]):
            raise ValueError(f"Вершина {node['id']}: clone_of должен указывать на другую существующую вершину.")
        chain = {node["id"]}
        while target is not None:
            if target in chain:
                raise ValueError("В разметке clone_of обнаружен цикл.")
            chain.add(target)
            if target not in nodes:
                raise ValueError(f"clone_of ссылается на отсутствующую вершину {target}.")
            target = nodes[target].get("clone_of")
    metadata = _metadata(data.get("metadata", {}), set(nodes))
    if loops:
        metadata["warnings"].append(f"Удалены петли: {loops}. Анализ использует простой граф.")
    if duplicates:
        metadata["warnings"].append(f"Удалены повторные рёбра: {duplicates} (направление записи не учитывается).")
    return {"name": _text(data.get("name") or "Импортированный граф", "Название графа", 160),
            "nodes": list(nodes.values()), "edges": edges, "metadata": metadata}


def _rows(content: str) -> list[list[str]]:
    # Accept spreadsheet delimiters and plain two-column edge lists.
    lines = [line for line in content.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if not lines:
        raise ValueError("Файл не содержит строк с данными.")
    sample = "\n".join(lines[:30])
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
    except csv.Error:
        delimiter = next((d for d in (",", ";", "\t") if d in lines[0]), None)
    if delimiter is None:
        return [re.split(r"\s+", line.strip()) for line in lines]
    try:
        return [[cell.strip() for cell in row] for row in csv.reader(io.StringIO("\n".join(lines)), delimiter=delimiter, strict=True)]
    except csv.Error as exc:
        raise ValueError("Ошибка CSV: проверьте кавычки и разделители.") from exc


def parse_graph(content: str | bytes, filename: str = "graph.csv", name: str = "") -> dict:
    content, warnings = _content_text(content)
    if filename.lower().endswith(".json") or content.lstrip().startswith(("{", "[")):
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, RecursionError) as exc:
            raise ValueError("Ошибка JSON: проверьте синтаксис файла.") from exc
        if isinstance(data, dict) and name:
            data["name"] = name
        graph = normalize_graph(data)
    else:
        rows = _rows(content)
        header = [cell.lower() for cell in rows[0]]
        if "source" in header or "target" in header:
            if len(header) != 2 or set(header) != {"source", "target"}:
                raise ValueError("Заголовок графа CSV должен содержать ровно source,target.")
            source_index, target_index = header.index("source"), header.index("target")
            rows = rows[1:]
        else:
            source_index, target_index = 0, 1
        edges = []
        for i, row in enumerate(rows, 1):
            if len(row) != 2:
                raise ValueError(f"Строка данных {i}: нужны ровно два ID вершин.")
            edges.append([row[source_index], row[target_index]])
        graph = normalize_graph({"name": name or Path(filename).stem or "Импортированный граф", "edges": edges})
        graph["metadata"]["warnings"].append("CSV содержит только рёбра: изолированные вершины можно передать через JSON nodes.")
    graph["metadata"].setdefault("source", "import")
    graph["metadata"]["warnings"].extend(warnings)
    return graph


def apply_labels(graph: dict, content: str | bytes, filename: str = "labels.csv") -> dict:
    """Merge explicit labels only; unlisted nodes retain unknown/missing truth."""
    result = normalize_graph(graph)
    content, warnings = _content_text(content)
    rows = _rows(content)
    header = [item.lower() for item in rows[0]]
    if (len(set(header)) != len(header) or "id" not in header or
            not ({"truth", "clone_of"} & set(header)) or set(header) - {"id", "truth", "clone_of"}):
        raise ValueError("Разметка CSV: нужен заголовок id,truth или id,clone_of (допустимы все три поля).")
    nodes = {node["id"]: node for node in result["nodes"]}
    seen = set()
    if len(rows) == 1:
        raise ValueError("Файл разметки не содержит данных.")
    for i, row in enumerate(rows[1:], 2):
        if len(row) != len(header):
            raise ValueError(f"Разметка, строка {i}: число столбцов не совпадает с заголовком.")
        values = dict(zip(header, row))
        node_id = _identifier(values["id"])
        if node_id not in nodes:
            raise ValueError(f"Разметка: вершина {node_id} отсутствует в графе.")
        if node_id in seen:
            raise ValueError(f"Разметка: ID {node_id} повторяется.")
        seen.add(node_id)
        if values.get("truth"):
            truth = values["truth"].lower()
            if truth not in TRUTHS:
                raise ValueError(f"Разметка {node_id}: truth должен быть bot, human или unknown.")
            nodes[node_id]["truth"] = truth
        if values.get("clone_of"):
            nodes[node_id]["clone_of"] = _identifier(values["clone_of"], "clone_of")
        if not values.get("truth") and not values.get("clone_of"):
            raise ValueError(f"Разметка {node_id}: укажите truth или clone_of.")
    result["metadata"]["warnings"].extend(warnings)
    result["metadata"]["label_source"] = "user"
    return normalize_graph(result)


DEMO_CATALOG = [
    {"id": "social", "name": "Локальная социальная сеть", "description": "35 модельных аккаунтов, три сообщества, два точных и один частичный клон; известная разметка."},
    {"id": "star", "name": "Звезда", "description": "Центр и 12 структурно эквивалентных листьев."},
    {"id": "asymmetric", "name": "Асимметричный граф Фрухта", "description": "12 вершин одной степени и только тождественный автоморфизм; степень не определяет орбиту."},
]


def list_demos() -> list[dict]:
    return copy.deepcopy(DEMO_CATALOG)


def demo_graph(demo_id: str = "social") -> dict:
    import networkx as nx

    if demo_id not in {item["id"] for item in DEMO_CATALOG}:
        raise ValueError("Неизвестный пример. Доступны social, star и asymmetric.")
    item = next(item for item in DEMO_CATALOG if item["id"] == demo_id)
    metadata = {"source": "synthetic", "synthetic": True, "demo_id": demo_id,
                "description": item["description"]}
    if demo_id == "social":
        g = nx.Graph()
        g.add_node("ego", label="Центральный аккаунт", truth="human")
        for n in range(1, 31):
            node_id = f"u{n:02}"
            g.add_node(node_id, label=f"Участник {n:02}", truth="human")
            g.add_edge("ego", node_id)
        for base in (0, 10, 20):
            ids = [f"u{base+n:02}" for n in range(1, 11)]
            g.add_edges_from((ids[n], ids[(n+1) % 10]) for n in range(10))
            g.add_edges_from((ids[a], ids[b]) for a, b in ((0, 2), (0, 4), (0, 6), (1, 4), (2, 5), (3, 7), (4, 8), (6, 9)))
        g.add_edges_from([("u01", "u11"), ("u11", "u21"), ("u02", "u23"), ("u07", "u15"), ("u16", "u28")])
        for clone, original in (("clone_a", "u04"), ("clone_b", "u18")):
            neighbors = list(g.neighbors(original))
            g.add_node(clone, label=f"Модельный клон {original}", truth="bot", clone_of=original)
            g.add_edges_from((clone, neighbor) for neighbor in neighbors)
        partial_neighbors = sorted(g.neighbors("u24"))
        g.add_node("clone_partial", label="Частичный клон u24", truth="bot", clone_of="u24")
        g.add_edges_from(("clone_partial", neighbor) for neighbor in partial_neighbors if neighbor != "u23")
        g.add_edge("clone_partial", "u29")
        g.add_node("isolated", label="Изолированный участник", truth="human")
        metadata["root"] = "ego"
        metadata["planted_clones"] = {"clone_a": "u04", "clone_b": "u18", "clone_partial": "u24"}
    else:
        g = nx.star_graph(12) if demo_id == "star" else nx.frucht_graph()
        g = nx.relabel_nodes(g, {n: str(n) for n in g.nodes})
        for node_id in g:
            g.nodes[node_id].update(label=("Центр" if node_id == "0" and demo_id == "star" else f"Вершина {node_id}"), truth="human")
        if demo_id == "star":
            metadata["root"] = "0"
    return normalize_graph({"name": item["name"], "nodes": [{"id": n, **attrs} for n, attrs in g.nodes(data=True)],
                            "edges": list(g.edges), "metadata": metadata})
