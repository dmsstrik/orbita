"""Structure and integrity checks for stored and exported artifacts."""

from __future__ import annotations

import json
import math

from .ingest import MAX_EDGES, MAX_NODES, normalize_graph

MAX_ARTIFACT_BYTES = 40 * 1024 * 1024
MAX_PAIRS = 20_000
METHODS = {"neighbors", "symmetry", "combined"}


def _error(path, message):
    raise ValueError(f"Некорректные сохранённые данные: {path} — {message}.")


def _object(value, path):
    if not isinstance(value, dict):
        _error(path, "ожидается объект")
    return value


def _array(value, path, maximum, minimum=0):
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        _error(path, f"ожидается список длиной от {minimum} до {maximum}")
    return value


def _string(value, path, maximum=4000, minimum=0):
    if not isinstance(value, str) or not minimum <= len(value) <= maximum:
        _error(path, f"ожидается строка длиной от {minimum} до {maximum}")
    return value


def _bool(value, path):
    if not isinstance(value, bool):
        _error(path, "ожидается true или false")
    return value


def _number(value, path, low=0, high=1, nullable=False):
    if value is None and nullable:
        return value
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not low <= value <= high or not math.isfinite(value):
        _error(path, f"ожидается конечное число от {low} до {high}")
    return value


def _integer(value, path, low=0, high=125_000):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        _error(path, f"ожидается целое число от {low} до {high}")
    return value


def _json_copy(value, path):
    _object(value, path)
    try:
        text = json.dumps(value, ensure_ascii=False, allow_nan=False)
        encoded = text.encode("utf-8")
        if len(encoded) > MAX_ARTIFACT_BYTES:
            _error(path, "размер превышает 12 МБ")
        return json.loads(text)
    except (TypeError, ValueError, OverflowError, RecursionError, UnicodeError):
        _error(path, "нужен объект JSON без неконечных чисел, размером не более 12 МБ")


def _strings(value, path, maximum=1000, item_maximum=4000):
    for index, item in enumerate(_array(value, path, maximum)):
        _string(item, f"{path}[{index}]", item_maximum)


def _reference(value, ids, path):
    _string(value, path, 128, 1)
    if value not in ids:
        _error(path, "ссылка на отсутствующую вершину")
    return value


def validate_options_artifact(data, ids=None):
    """Validate optional stored input options, retaining output annotations."""
    result = _json_copy(data, "options")
    if result.get("root") is not None:
        _string(result["root"], "options.root", 128, 1)
        if ids is not None:
            _reference(result["root"], ids, "options.root")
    if "radius" in result:
        _integer(result["radius"], "options.radius", 1, 3)
    if "threshold" in result:
        _number(result["threshold"], "options.threshold")
    if "exclude_root" in result:
        _bool(result["exclude_root"], "options.exclude_root")
    if "max_pairs" in result:
        _integer(result["max_pairs"], "options.max_pairs", 0, 1_998_000)
    if "layout_seed" in result:
        _integer(result["layout_seed"], "options.layout_seed", 0, 2**32 - 1)
    if "layout_method_actual" in result:
        _string(result["layout_method_actual"], "options.layout_method_actual", 100)
    if "conventions" in result:
        conventions = _object(result["conventions"], "options.conventions")
        if len(conventions) > 100:
            _error("options.conventions", "слишком много правил")
        for key, text in conventions.items():
            _string(key, "options.conventions.key", 100)
            _string(text, "options.conventions.value", 5000)
    return result


def _metrics(data, path, complete=True):
    for field in ("precision", "recall", "f1"):
        if complete or field in data:
            _number(data.get(field), f"{path}.{field}", nullable=True)
    for field in ("tp", "fp", "fn"):
        if complete or field in data:
            _integer(data.get(field), f"{path}.{field}")
    if "tn" in data:
        _integer(data["tn"], f"{path}.tn")


def validate_analysis_artifact(data: dict) -> dict:
    result = _json_copy(data, "analysis")
    graph = normalize_graph(_object(result.get("graph"), "analysis.graph"))
    result["graph"] = graph
    ids = {node["id"] for node in graph["nodes"]}
    options = validate_options_artifact(_object(result.get("options"), "analysis.options"), ids)
    result["options"] = options
    for node in graph["nodes"]:
        if "orbit" in node:
            _integer(node["orbit"], "graph.nodes.orbit", 0, MAX_NODES - 1)
        if "degree" in node:
            _integer(node["degree"], "graph.nodes.degree", 0, MAX_NODES - 1)
    summary = _object(result.get("summary"), "analysis.summary")
    for key, maximum in (("node_count", MAX_NODES), ("edge_count", MAX_EDGES),
                         ("component_count", MAX_NODES), ("orbit_count", MAX_NODES),
                         ("nontrivial_orbits", MAX_NODES), ("candidate_count", 1_998_000)):
        _integer(summary.get(key), f"analysis.summary.{key}", 0, maximum)
    _number(summary.get("density"), "analysis.summary.density")
    _number(summary.get("elapsed_ms"), "analysis.summary.elapsed_ms", high=86_400_000)
    _string(summary.get("group_order"), "analysis.summary.group_order", 256, 1)
    for field, maximum in (("returned_pair_count", MAX_PAIRS), ("isolated_count", MAX_NODES),
                           ("group_order_exponent", 10_000)):
        if field in summary:
            _integer(summary[field], f"analysis.summary.{field}", 0, maximum)
    if "group_order_exact" in summary:
        _bool(summary["group_order_exact"], "analysis.summary.group_order_exact")
    for field, maximum in (("average_degree", MAX_NODES - 1), ("group_order_mantissa", 1e308)):
        if field in summary:
            _number(summary[field], f"analysis.summary.{field}", high=maximum)
    if summary["node_count"] != len(ids) or summary["edge_count"] != len(graph["edges"]):
        _error("analysis.summary", "число вершин или рёбер не соответствует графу")
    orbits = _array(result.get("orbits"), "analysis.orbits", MAX_NODES, 1)
    partition, orbit_ids, orbit_nodes = set(), set(), {}
    for orbit in orbits:
        _object(orbit, "analysis.orbits.item")
        orbit_id = _integer(orbit.get("id"), "analysis.orbits.id", 0, MAX_NODES - 1)
        if orbit_id in orbit_ids:
            _error("analysis.orbits", "повторяется ID орбиты")
        orbit_ids.add(orbit_id)
        members = _array(orbit.get("nodes"), "analysis.orbits.nodes", MAX_NODES, 1)
        for node_id in members:
            _reference(node_id, ids, "analysis.orbits.nodes")
            if node_id in partition:
                _error("analysis.orbits", "вершина повторяется в разбиении")
            partition.add(node_id)
        if _integer(orbit.get("size"), "analysis.orbits.size", 1, MAX_NODES) != len(members):
            _error("analysis.orbits.size", "размер не соответствует списку вершин")
        orbit_nodes[orbit_id] = set(members)
    if partition != ids or summary["orbit_count"] != len(orbits):
        _error("analysis.orbits", "разбиение не соответствует графу или числу орбит")
    for node in graph["nodes"]:
        if "orbit" in node and node["id"] not in orbit_nodes.get(node["orbit"], set()):
            _error("graph.nodes.orbit", "вершина не принадлежит указанной орбите")
    pairs = _array(result.get("pairs"), "analysis.pairs", MAX_PAIRS)
    seen_pairs = set()
    for pair in pairs:
        _object(pair, "analysis.pairs.item")
        source = _reference(pair.get("source"), ids, "analysis.pairs.source")
        target = _reference(pair.get("target"), ids, "analysis.pairs.target")
        key = tuple(sorted((source, target)))
        if source == target or key in seen_pairs:
            _error("analysis.pairs", "пара повторяется или содержит одну и ту же вершину")
        seen_pairs.add(key)
        for metric in ("score", "jaccard"):
            _number(pair.get(metric), f"analysis.pairs.{metric}")
        same_orbit = _bool(pair.get("same_orbit"), "analysis.pairs.same_orbit")
        orbit_id = pair.get("orbit_id")
        if same_orbit:
            _integer(orbit_id, "analysis.pairs.orbit_id", 0, MAX_NODES - 1)
            if orbit_id not in orbit_nodes or not {source, target} <= orbit_nodes[orbit_id]:
                _error("analysis.pairs.orbit_id", "пара не принадлежит указанной орбите")
        elif orbit_id is not None:
            _error("analysis.pairs.orbit_id", "при разных орбитах ожидается null")
        neighbors = _array(pair.get("common_neighbors"), "analysis.pairs.common_neighbors", MAX_NODES)
        for node_id in neighbors:
            _reference(node_id, ids, "analysis.pairs.common_neighbors")
        if len(set(neighbors)) != len(neighbors):
            _error("analysis.pairs.common_neighbors", "повторяются ID соседей")
        _strings(pair.get("reasons"), "analysis.pairs.reasons", 50)
        if "orbit_evidence" in pair:
            _integer(pair["orbit_evidence"], "analysis.pairs.orbit_evidence", 0, 1)
        if pair.get("twin_type") not in (None, "false_twins", "true_twins"):
            _error("analysis.pairs.twin_type", "неизвестный вид двойников")
    if summary["candidate_count"] < len(pairs):
        _error("analysis.summary.candidate_count", "меньше числа выданных пар")
    _strings(result.get("warnings", []), "analysis.warnings")
    evaluation = result.get("evaluation")
    if evaluation is not None:
        _object(evaluation, "analysis.evaluation")
        _string(evaluation.get("note"), "analysis.evaluation.note", 5000)
        complete = _bool(evaluation.get("complete"), "analysis.evaluation.complete")
        _metrics(evaluation, "analysis.evaluation", complete=complete)
        for field in ("labeled_count", "eligible_count", "predicted_positive_count"):
            if field in evaluation:
                _integer(evaluation[field], f"analysis.evaluation.{field}", 0, MAX_NODES)
    return result


def validate_experiment_artifact(data: dict) -> dict:
    result = _json_copy(data, "experiments")
    config = _object(result.get("config"), "experiments.config")
    for key, minimum, maximum in (("clone_count", 1, 10), ("repeats", 1, 5), ("seed", 0, 2**32 - 1)):
        _integer(config.get(key), f"experiments.config.{key}", minimum, maximum)
    for key in ("retention", "threshold"):
        _number(config.get(key), f"experiments.config.{key}")
    _bool(config.get("exclude_root"), "experiments.config.exclude_root")
    if config.get("root") is not None:
        _string(config["root"], "experiments.config.root", 128, 1)
    for value in _array(config.get("noise_levels"), "experiments.config.noise_levels", 10, 1):
        _number(value, "experiments.config.noise_levels.item")
    if "conventions" in config:
        for key, value in _object(config["conventions"], "experiments.config.conventions").items():
            _string(key, "experiments.config.conventions.key", 100)
            _string(value, "experiments.config.conventions.value", 5000)
    for row in _array(result.get("rows"), "experiments.rows", 500, 1):
        _object(row, "experiments.rows.item")
        _bool(row.get("control"), "experiments.rows.control")
        _number(row.get("noise"), "experiments.rows.noise")
        _integer(row.get("repeat"), "experiments.rows.repeat", 1, 5)
        if not isinstance(row.get("method"), str) or row["method"] not in METHODS:
            _error("experiments.rows.method", "неизвестный метод")
        _metrics(row, "experiments.rows")
        _number(row.get("elapsed_ms"), "experiments.rows.elapsed_ms", high=86_400_000)
        for field, maximum in (("node_count", MAX_NODES), ("edge_count", MAX_EDGES),
                               ("candidate_count", 1_998_000), ("actual_positive_pairs", 1_998_000),
                               ("evaluated_pair_count", 1_998_000), ("deleted_edges", MAX_EDGES),
                               ("added_edges", MAX_EDGES), ("requested_each", MAX_EDGES)):
            if field in row:
                _integer(row[field], f"experiments.rows.{field}", 0, maximum)
        if "graph_fingerprint" in row:
            _string(row["graph_fingerprint"], "experiments.rows.graph_fingerprint", 128, 1)
    for row in _array(result.get("summary"), "experiments.summary", 100, 1):
        _object(row, "experiments.summary.item")
        _number(row.get("noise"), "experiments.summary.noise")
        if not isinstance(row.get("method"), str) or row["method"] not in METHODS:
            _error("experiments.summary.method", "неизвестный метод")
        for metric in ("precision", "recall", "f1"):
            _number(row.get(metric), f"experiments.summary.{metric}", nullable=True)
        for field in ("repeats", "precision_defined_repeats", "recall_defined_repeats", "f1_defined_repeats"):
            if field in row:
                _integer(row[field], f"experiments.summary.{field}", 0, 5)
        # Mean counts need not be integers.
        for metric in ("tp", "fp", "fn", "elapsed_ms"):
            if metric in row:
                _number(row[metric], f"experiments.summary.{metric}", high=86_400_000, nullable=True)
    _strings(result.get("warnings", []), "experiments.warnings")
    graph = normalize_graph(_object(result.get("example_graph"), "experiments.example_graph"))
    result["example_graph"] = graph
    if config.get("root") is not None:
        _reference(config["root"], {node["id"] for node in graph["nodes"]}, "experiments.config.root")
    return result
