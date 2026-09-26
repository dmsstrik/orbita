"""API integration checks."""

import csv
import copy
import io
import json

import pytest
from fastapi.testclient import TestClient

from app.analysis import analyze_graph
from app.main import MAX_BODY, app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ORBITA_PROJECT_DIR", str(tmp_path / "projects"))
    with TestClient(app, raise_server_exceptions=False) as instance:
        yield instance


@pytest.fixture
def analysis():
    graph = {
        "name": 'Тест «графа», "кавычки" <img src=x onerror=alert(1)>',
        "nodes": [{"id": "r", "label": "Корень"},
                  {"id": "a", "label": 'Иван, "Петров" <script>alert(1)</script>'},
                  {"id": "b", "label": '=HYPERLINK("https://invalid","Метка")'},
                  {"id": "c", "label": "Сосед & коллега"}],
        "edges": [["r", "a"], ["r", "b"], ["r", "c"], ["a", "c"], ["b", "c"]],
    }
    return analyze_graph(graph, {"root": "r"})


def test_experiment_real_worker_export_and_reimport(client, analysis):
    response = client.post("/api/experiments", json={"graph": analysis["graph"], "config": {
        "root": "r", "repeats": 1, "noise_levels": [0, 0.15], "clone_count": 2, "retention": 1,
    }})
    assert response.status_code == 200, response.text
    experiment = response.json()
    assert len(experiment["rows"]) == 12
    assert len(experiment["summary"]) == 6
    for noise in (0, 0.15):
        for control in (False, True):
            rows = [r for r in experiment["rows"] if r["noise"] == noise and r["control"] is control]
            assert {row["method"] for row in rows} == {"neighbors", "symmetry", "combined"}
            assert len({row["graph_fingerprint"] for row in rows}) == 1
    csv_result = client.post("/api/export/experiments", json={"experiments": experiment})
    assert csv_result.status_code == 200
    csv_rows = list(csv.DictReader(io.StringIO(csv_result.text.lstrip("\ufeff"))))
    assert len(csv_rows) == 12
    assert {r["control"] for r in csv_rows} == {"True", "False"}
    report = client.post("/api/export/html", json={"analysis": analysis, "experiments": experiment})
    assert report.status_code == 200
    assert "Эксперименты" in report.text and "Контроль" in report.text
    exported = client.post("/api/export/json", json={"graph": experiment["example_graph"]})
    assert exported.status_code == 200, exported.text
    reimported = client.post("/api/import", json={"filename": "experiment.json", "content": exported.text})
    assert reimported.status_code == 200
    assert reimported.json()["edges"] == experiment["example_graph"]["edges"]
    saved = client.post("/api/projects", json={"name": "Граф и эксперимент", "graph": analysis["graph"],
                         "options": analysis["options"], "analysis": analysis, "experiments": experiment})
    assert saved.status_code == 200, saved.text
    restored = client.get("/api/projects/" + saved.json()["id"]).json()
    assert restored["experiments"]["rows"] == experiment["rows"]
    assert restored["analysis"]["options"]["conventions"] == analysis["options"]["conventions"]


def test_export_unicode_quotes_csv_formula_and_html_xss(client, analysis):
    report = client.post("/api/export/html", json={"analysis": analysis})
    assert report.status_code == 200
    assert '<script>' not in report.text and '<img src=x' not in report.text
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in report.text
    assert '&lt;img src=x onerror=alert(1)&gt;' in report.text
    assert 'Сосед &amp; коллега' in report.text
    assert report.headers["content-disposition"].endswith('"orbita-report.html"')
    exported = client.post("/api/export/csv", json={"analysis": analysis})
    assert exported.status_code == 200
    assert exported.text.startswith("\ufeff")
    rows = list(csv.DictReader(io.StringIO(exported.text.lstrip("\ufeff"))))
    assert rows[0]["source_label"] == 'Иван, "Петров" <script>alert(1)</script>'
    assert rows[0]["target_label"] == '\'=HYPERLINK("https://invalid","Метка")'


def test_actual_body_size_cannot_be_bypassed_with_small_content_length(client):
    content = b" " * (MAX_BODY + 1)
    response = client.post("/api/import", content=content,
                           headers={"Content-Type": "application/json", "Content-Length": "0"})
    assert response.status_code == 413
    assert "12 МБ" in response.json()["detail"]


def test_actual_body_size_checked_for_stream_without_length(client):
    def chunks():
        yield b" " * MAX_BODY
        yield b" "
    response = client.post("/api/import", content=chunks(), headers={"Content-Type": "application/json"})
    assert response.status_code == 413


def test_worker_validation_error_is_russian_json_and_next_job_works(client, analysis):
    response = client.post("/api/analyze", json={"graph": analysis["graph"], "options": {"root": "missing"}})
    assert response.status_code == 422
    assert "отсутствует" in response.json()["detail"]
    recovered = client.post("/api/analyze", json={"graph": analysis["graph"], "options": {"root": "r"}})
    assert recovered.status_code == 200


def test_worker_unexpected_exception_masks_internal_details(monkeypatch):
    from app import analysis as module
    from app.jobs import _worker

    def fail(*args):
        raise RuntimeError("secret-token /private/absolute/path")

    class Connection:
        result = None
        closed = False

        def send(self, value):
            self.result = value

        def close(self):
            self.closed = True

    monkeypatch.setattr(module, "analyze_graph", fail)
    connection = Connection()
    _worker(connection, "analyze", ({},))
    assert connection.result[0] is False
    assert "secret-token" not in connection.result[1] and "/private/" not in connection.result[1]
    assert connection.closed


def test_save_project_with_actual_analysis_options(client, analysis):
    response = client.post("/api/projects", json={"name": "Исследование", "graph": analysis["graph"],
                           "analysis": analysis, "options": analysis["options"]})
    assert response.status_code == 200, response.text
    project = client.get("/api/projects/" + response.json()["id"]).json()
    assert project["analysis"]["summary"] == analysis["summary"]
    assert project["options"]["root"] == "r"


@pytest.mark.parametrize("endpoint,payload", [
    ("/api/export/csv", {"analysis": {"pairs": [None]}}),
    ("/api/export/html", {"analysis": {"graph": {"nodes": [None]}}}),
    ("/api/export/experiments", {"experiments": {"rows": [None]}}),
])
def test_invalid_saved_artifact_export_is_rejected_as_json(client, endpoint, payload):
    response = client.post(endpoint, json=payload)
    assert response.status_code == 422, response.text
    assert isinstance(response.json()["detail"], str)


def test_one_corrupt_project_does_not_break_project_list(client, tmp_path, analysis):
    valid = client.post("/api/projects", json={"name": "Рабочий проект", "graph": analysis["graph"]})
    assert valid.status_code == 200
    directory = tmp_path / "projects"
    (directory / ("a" * 32 + ".json")).write_text(json.dumps({"name": "Поврежден", "updated_at": "now", "graph": []}))
    response = client.get("/api/projects")
    assert response.status_code == 200, response.text
    assert [p["id"] for p in response.json()["projects"]] == [valid.json()["id"]]


def test_project_load_rejects_wrong_schema(client, tmp_path):
    directory = tmp_path / "projects"
    directory.mkdir()
    identifier = "b" * 32
    (directory / (identifier + ".json")).write_text("[]")
    response = client.get("/api/projects/" + identifier)
    assert response.status_code == 422, response.text


def test_project_save_rejects_invalid_analysis_artifact(client, analysis):
    response = client.post("/api/projects", json={"name": "Повреждённый анализ", "graph": analysis["graph"],
                           "analysis": {"pairs": [None]}})
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("mutation", [
    lambda a: a["pairs"][0].update(source="missing"),
    lambda a: a["pairs"][0].update(score=1.5),
    lambda a: a["pairs"][0].update(jaccard=True),
    lambda a: a["pairs"][0].update(common_neighbors=["missing"]),
    lambda a: a["pairs"][0].update(reasons=[None]),
    lambda a: a["orbits"][0].update(nodes=["missing"]),
    lambda a: a["summary"].update(node_count=499),
    lambda a: a["options"].update(conventions={"score": ["wrong type"]}),
])
def test_invalid_nested_analysis_values_return_422(client, analysis, mutation):
    artifact = copy.deepcopy(analysis)
    mutation(artifact)
    response = client.post("/api/export/html", json={"analysis": artifact})
    assert response.status_code == 422, response.text


def test_nonfinite_analysis_values_rejected_without_serialization_failure(analysis):
    from app.validation import validate_analysis_artifact
    for value in (float("nan"), float("inf"), float("-inf")):
        artifact = copy.deepcopy(analysis)
        artifact["pairs"][0]["score"] = value
        with pytest.raises(ValueError, match="Некорректные"):
            validate_analysis_artifact(artifact)


def test_import_invalid_unicode_and_huge_visual_integer_return_russian_errors(client):
    malformed_graph = {"nodes": [{"id": "a", "x": 10**1000}]}
    response = client.post("/api/import", json={"content": json.dumps(malformed_graph), "filename": "graph.json"})
    assert response.status_code == 422 and "конечным числом" in response.json()["detail"]
    request_body = json.dumps({"content": chr(0xD800), "filename": "graph.csv"})
    response = client.post("/api/import", content=request_body, headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert "Проверьте" in response.json()["detail"] or "Unicode" in response.json()["detail"]
