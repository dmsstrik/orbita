import csv
import io
import json

import pytest
from fastapi.testclient import TestClient

from app.analysis import analyze_graph
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ORBITA_PROJECT_DIR", str(tmp_path / "projects"))
    with TestClient(app) as instance:
        yield instance


@pytest.fixture
def graph():
    return {"name": "Проверка", "nodes": [{"id": n} for n in ["r", "a", "b", "c"]],
            "edges": [{"source": a, "target": b} for a, b in [("r", "a"), ("r", "b"), ("r", "c"), ("a", "c"), ("b", "c")]]}


def test_health_and_demos(client):
    assert client.get("/api/health").json()["status"] == "ok"
    demos = client.get("/api/demos").json()["demos"]
    assert len(demos) >= 3
    for demo in demos:
        result = client.get("/api/demos/" + demo["id"])
        assert result.status_code == 200
        assert result.json()["nodes"]


def test_import_and_real_worker_analysis(client, graph):
    result = client.post("/api/import", json={"content": json.dumps(graph), "filename": "example.json"})
    assert result.status_code == 200
    result = client.post("/api/analyze", json={"graph": result.json(), "options": {"root": "r"}})
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["summary"]["group_order"] == "2"
    assert {p["source"] for p in data["pairs"]} == {"a"}
    assert data["pairs"][0]["target"] == "b"


def test_vk_validation_errors_are_actionable(client):
    response = client.post("/api/vk", json={"user_id": "1", "max_friends": 999999})
    assert response.status_code == 422
    assert "max_friends" in response.text
    assert client.post("/api/import", json={"filename": "bad.csv", "content": ""}).status_code == 422


def test_boundaries(client, graph):
    assert client.post("/api/analyze", json={"graph": graph}, headers={"Origin": "https://outside.example"}).status_code == 403
    assert client.post("/api/import", content="{}", headers={"Content-Type": "text/plain"}).status_code == 415
    assert client.post("/api/import", content="{}", headers={"Content-Type": "application/json", "Content-Length": "999999999"}).status_code == 413
    assert client.get("/api/health", headers={"Host": "outside.example"}).status_code == 400


def test_project_round_trip_and_delete(client, graph):
    payload = {"name": "Мой граф", "graph": graph, "options": {"threshold": 0.7}}
    saved = client.post("/api/projects", json=payload)
    assert saved.status_code == 200, saved.text
    key = saved.json()["id"]
    listed = client.get("/api/projects").json()["projects"]
    assert listed[0]["id"] == key
    loaded = client.get(f"/api/projects/{key}").json()
    assert loaded["name"] == payload["name"]
    assert loaded["options"]["threshold"] == 0.7
    assert len(loaded["graph"]["nodes"]) == 4
    assert client.delete(f"/api/projects/{key}").status_code == 200
    assert client.get(f"/api/projects/{key}").status_code == 404
    assert client.get("/api/projects/not-a-uuid").status_code == 422


def test_exports_escape_labels_and_preserve_graph(client, graph):
    graph["nodes"][1]["label"] = '<script>alert("x")</script>'
    graph["nodes"][2]["label"] = "=HYPERLINK(1)"
    analysis = analyze_graph(graph, {"root": "r"})
    result = client.post("/api/export/html", json={"analysis": analysis})
    assert result.status_code == 200, result.text
    assert "<script>" not in result.text
    assert "&lt;script&gt;" in result.text
    assert "Индекс Жаккара" in result.text or "Жаккар" in result.text
    csv_result = client.post("/api/export/csv", json={"analysis": analysis})
    rows = list(csv.DictReader(io.StringIO(csv_result.text.lstrip("\ufeff"))))
    assert rows[0]["target_label"].startswith("'=HYPERLINK")
    assert rows[0]["source_label"] == graph["nodes"][1]["label"]
    exported = client.post("/api/export/json", json={"graph": graph})
    assert exported.status_code == 200
    assert exported.json()["nodes"][1]["label"] == graph["nodes"][1]["label"]


def test_experiment_request_bounds(client, graph):
    for config in [{"repeats": 1000}, {"noise_levels": [1.1]}, {"retention": -0.1}, {"clone_count": 100}]:
        response = client.post("/api/experiments", json={"graph": graph, "config": config})
        assert response.status_code == 422


def test_labels_not_used_to_change_score(client, graph):
    response = client.post("/api/labels", json={"graph": graph, "filename": "labels.csv", "content": "id,truth\na,bot\nb,human\n"})
    assert response.status_code == 200, response.text
    original = analyze_graph(graph, {"root": "r"})
    labeled = analyze_graph(response.json(), {"root": "r"})
    assert original["pairs"] == labeled["pairs"]
    assert labeled["evaluation"]["complete"] is False
