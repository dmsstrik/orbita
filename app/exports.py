"""CSV and standalone HTML export helpers."""

from __future__ import annotations

import csv
import html
import io
import json
import math
from datetime import datetime, timezone

from . import __version__

COLORS = ["#087f8c", "#e66c37", "#647acb", "#b977a3", "#629b58", "#b69432", "#37729a", "#926b52"]
METHODS = {"neighbors": "Сходство соседей", "symmetry": "Симметрия", "combined": "Сочетание признаков"}


def _cell(value):
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        value = json.dumps(value, ensure_ascii=False)
    value = str(value)
    # Spreadsheet programs interpret these prefixes as formulas, even in CSV.
    if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
        value = "'" + value
    return value


def _csv(headers: list[str], rows):
    stream = io.StringIO(newline="")
    stream.write("\ufeff")
    writer = csv.writer(stream, lineterminator="\r\n")
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_cell(value) for value in row])
    return stream.getvalue()


def candidates_csv(analysis: dict) -> str:
    pairs = analysis.get("pairs", [])
    if not isinstance(pairs, list):
        raise ValueError("В результате анализа отсутствует список пар.")
    labels = {str(node["id"]): node.get("label", node["id"]) for node in analysis.get("graph", {}).get("nodes", [])}
    fields = ["source", "source_label", "target", "target_label", "score", "same_orbit", "jaccard", "common_neighbors_count", "common_neighbors", "twin_type", "reasons"]
    rows = ([p.get("source"), labels.get(str(p.get("source")), ""), p.get("target"), labels.get(str(p.get("target")), ""),
             p.get("score"), p.get("same_orbit"), p.get("jaccard"), len(p.get("common_neighbors", [])),
             p.get("common_neighbors", []), p.get("twin_type"), p.get("reasons", [])] for p in pairs)
    return _csv(fields, rows)


def experiments_csv(experiments: dict) -> str:
    rows = experiments.get("rows", [])
    if not isinstance(rows, list):
        raise ValueError("В эксперименте отсутствует список результатов.")
    fields = ["control", "noise", "repeat", "method", "precision", "recall", "f1", "tp", "fp", "fn", "elapsed_ms"]
    return _csv(fields, ([row.get(field, False if field == "control" else None) for field in fields] for row in rows))


def _e(value):
    return html.escape(str(value), quote=True)


def _num(value, digits=3):
    if value is None:
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if not math.isfinite(number):
        return "—"
    return f"{number:.{digits}f}".rstrip("0").rstrip(".") if digits else f"{number:.0f}"


def _safe_float(value, default=0.0):
    try:
        value = float(value)
        return min(1.2, max(-1.2, value)) if math.isfinite(value) else default
    except (ValueError, TypeError):
        return default


def _graph_svg(graph: dict, root: str | None) -> str:
    nodes = graph.get("nodes", [])[:2000]
    positions = {}
    for index, node in enumerate(nodes):
        angle = 2 * math.pi * index / max(1, len(nodes))
        x = _safe_float(node.get("x", math.cos(angle)))
        y = _safe_float(node.get("y", math.sin(angle)))
        positions[str(node["id"])] = (440 + 340 * x, 270 + 205 * y)
    parts = ['<svg viewBox="0 0 880 540" role="img" aria-label="Граф с раскраской орбит"><rect width="880" height="540" fill="#f6f5f0" rx="14"/>']
    for edge in graph.get("edges", [])[:100_000]:
        a, b = positions.get(str(edge.get("source"))), positions.get(str(edge.get("target")))
        if a and b:
            parts.append(f'<line x1="{a[0]:.2f}" y1="{a[1]:.2f}" x2="{b[0]:.2f}" y2="{b[1]:.2f}" stroke="#c7cfce" stroke-width="1"/>')
    for node in nodes:
        x, y = positions[str(node["id"])]
        try:
            color = COLORS[int(node.get("orbit", 0)) % len(COLORS)]
        except (ValueError, TypeError):
            color = COLORS[0]
        is_root = node["id"] == root
        parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{8 if is_root else 5}" fill="{color}" stroke="{ "#182c30" if is_root else "white"}" stroke-width="2"><title>{_e(node.get("label", node["id"]))}</title></circle>')
        if len(nodes) <= 55 or is_root:
            parts.append(f'<text x="{x + 9:.2f}" y="{y + 4:.2f}" font-size="11" fill="#32484b">{_e(str(node.get("label", node["id"]))[:30])}</text>')
    parts.append("</svg>")
    return "".join(parts)


def html_report(analysis: dict, experiments: dict | None = None) -> str:
    graph = analysis.get("graph", {})
    summary = analysis.get("summary", {})
    options = analysis.get("options", {})
    if not isinstance(graph, dict) or not isinstance(summary, dict) or not graph.get("nodes"):
        raise ValueError("Сначала выполните анализ непустого графа.")
    pairs = analysis.get("pairs", [])
    labels = {node["id"]: node.get("label", node["id"]) for node in graph["nodes"]}
    title = _e(graph.get("name", "Социальный граф"))
    date = datetime.now(timezone.utc).strftime("%d.%m.%Y · %H:%M UTC")
    cards = [("Вершины", summary.get("node_count")), ("Связи", summary.get("edge_count")),
             ("Орбиты", summary.get("orbit_count")), ("Пары кандидатов", summary.get("candidate_count")),
             ("Порядок группы", summary.get("group_order")), ("Время, мс", _num(summary.get("elapsed_ms"), 1))]
    card_html = "".join(f'<div class="card"><span>{_e(label)}</span><strong>{_e(value)}</strong></div>' for label, value in cards)
    warning_html = "".join(f"<li>{_e(warning)}</li>" for warning in analysis.get("warnings", []))
    table_rows = "".join(
        f'<tr><td>{_e(labels.get(p.get("source"), p.get("source")))}</td><td>{_e(labels.get(p.get("target"), p.get("target")))}</td>'
        f'<td>{_num(p.get("score"))}</td><td>{"Да" if p.get("same_orbit") else "Нет"}</td><td>{_num(p.get("jaccard"))}</td>'
        f'<td>{len(p.get("common_neighbors", []))}</td><td>{_e(" ".join(p.get("reasons", [])))}</td></tr>' for p in pairs)
    orbit_rows = "".join(f'<tr><td>{_e(orbit.get("id"))}</td><td>{_e(orbit.get("size"))}</td><td>{_e(", ".join(labels.get(n, n) for n in orbit.get("nodes", [])))}</td></tr>' for orbit in analysis.get("orbits", []))
    conventions = options.get("conventions", {})
    method_html = "".join(f"<li>{_e(value)}</li>" for value in conventions.values()) if isinstance(conventions, dict) else ""
    evaluation = analysis.get("evaluation")
    evaluation_html = "<p>Разметка bot/human не предоставлена; оценка не выполнена.</p>"
    if evaluation:
        evaluation_html = f'<p>{_e(evaluation.get("note", ""))}</p>'
        if evaluation.get("complete"):
            evaluation_html += '<table><thead><tr><th>Precision</th><th>Recall</th><th>F1</th><th>TP</th><th>FP</th><th>FN</th></tr></thead><tbody><tr>'
            evaluation_html += "".join(f'<td>{_num(evaluation.get(key))}</td>' for key in ["precision", "recall", "f1", "tp", "fp", "fn"]) + "</tr></tbody></table>"
    experiment_html = ""
    if experiments:
        exp_rows = "".join(f'<tr><td>{"Контроль" if row.get("control") else _num(row.get("noise"))}</td><td>{_e(row.get("repeat", ""))}</td><td>{_e(METHODS.get(row.get("method"), row.get("method")))}</td><td>{_num(row.get("precision"))}</td><td>{_num(row.get("recall"))}</td><td>{_num(row.get("f1"))}</td><td>{_num(row.get("fp"), 0)}</td></tr>' for row in experiments.get("rows", []))
        exp_warnings = "".join(f"<li>{_e(w)}</li>" for w in experiments.get("warnings", []))
        experiment_html = f'<section><h2>Эксперименты</h2><ul>{exp_warnings}</ul><pre>{_e(json.dumps(experiments.get("config", {}), ensure_ascii=False, indent=2))}</pre><table><thead><tr><th>Шум</th><th>Повтор</th><th>Метод</th><th>Precision</th><th>Recall</th><th>F1</th><th>FP</th></tr></thead><tbody>{exp_rows}</tbody></table></section>'
    graph_preview_note = "Цвет обозначает орбиту; при большом числе орбит цвета повторяются. Центральная вершина выделена обводкой."
    if len(graph["nodes"]) > 2000:
        graph_preview_note += f" Карта отчёта показывает первые 2000 из {len(graph['nodes'])} вершин; сводка, орбиты и таблица рассчитаны по всей области."
    coverage_html = ""
    if summary.get("possible_pair_count") is not None:
        coverage_html = (
            f" Охвачено возможных пар: {_e(summary['possible_pair_count'])}; "
            f"подробно рассчитано после точного предварительного правила: {_e(summary.get('scored_pair_count', '—'))}."
        )
    if summary.get("candidate_score_min") is not None:
        coverage_html += (
            f" Диапазон итоговой оценки кандидатов: {_num(summary['candidate_score_min'], 2)}–"
            f"{_num(summary['candidate_score_max'], 2)}."
        )
    return f'''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Орбита — {title}</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#f6f5f0;color:#193338;font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}main{{max-width:1100px;margin:40px auto;padding:42px;background:white;border-radius:22px}}header{{border-bottom:2px solid #e66c37;padding-bottom:28px}}.brand{{font-weight:800;letter-spacing:.2em;color:#087f8c}}h1{{font-size:34px;line-height:1.2;margin:16px 0}}h2{{font-size:22px;margin:0 0 16px}}h3{{font-size:17px}}.muted{{color:#667a7d}}.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:28px 0}}.card{{padding:16px;background:#f6f5f0;border-radius:12px}}.card span{{display:block;color:#667a7d;font-size:12px}}.card strong{{font-size:25px;word-break:break-word}}section{{margin-top:36px}}table{{width:100%;border-collapse:collapse;font-size:12px}}th,td{{text-align:left;vertical-align:top;border-bottom:1px solid #dee6e4;padding:9px;overflow-wrap:anywhere}}th{{background:#eef3f1}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#f6f5f0;padding:18px;font-size:12px;border-radius:10px}}svg{{width:100%;height:auto}}.note{{border-left:3px solid #e66c37;padding:12px 18px;background:#fff5ec}}li{{margin:8px 0}}footer{{margin-top:40px;border-top:1px solid #dee6e4;padding-top:20px;font-size:12px;color:#667a7d}}@media print{{body{{background:white}}main{{margin:0;padding:0;max-width:none}}section{{break-inside:auto}}tr,.card{{break-inside:avoid}}thead{{display:table-header-group}}}}@media(max-width:650px){{main{{margin:0;padding:20px}}.cards{{grid-template-columns:repeat(2,1fr)}}}}
</style></head><body><main><header><div class="brand">ОРБИТА / ИССЛЕДОВАНИЕ</div><h1>{title}</h1><div class="muted">Отчёт по структурному анализу · {date} · версия {__version__}</div></header>
<div class="cards">{card_html}</div>
<section><h2>Граф и орбиты</h2>{_graph_svg(graph, options.get('root'))}<p class="muted">{_e(graph_preview_note)}</p><table><thead><tr><th>Орбита</th><th>Размер</th><th>Вершины</th></tr></thead><tbody>{orbit_rows}</tbody></table></section>
<section><h2>Пары кандидатов</h2><p>В таблице: {len(pairs)}; всего по правилу: {_e(summary.get('candidate_count', len(pairs)))}.{coverage_html} Ограничение выдачи не меняет число найденных пар и метрики.</p><table><thead><tr><th>Аккаунт A</th><th>Аккаунт B</th><th>Оценка</th><th>Одна орбита</th><th>Жаккар</th><th>Общие соседи</th><th>Причины</th></tr></thead><tbody>{table_rows or '<tr><td colspan="7">Нет пар, удовлетворяющих выбранному правилу.</td></tr>'}</tbody></table></section>
<section><h2>Оценка по разметке</h2>{evaluation_html}</section>
<section><h2>Методика</h2><ul>{method_html}</ul><h3>Замечания к данным</h3><ul>{warning_html}</ul><h3>Параметры</h3><pre>{_e(json.dumps(options, ensure_ascii=False, indent=2))}</pre><h3>Происхождение данных</h3><pre>{_e(json.dumps(graph.get('metadata', {}), ensure_ascii=False, indent=2))}</pre></section>
{experiment_html}<footer>Орбита · локальная лаборатория социальных графов. Отчёт автономен и не загружает внешние ресурсы. Для воспроизведения сохраните также исходный JSON-граф и параметры.</footer></main></body></html>'''
