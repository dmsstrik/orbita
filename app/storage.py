"""Local atomic persistence for saved projects."""

from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .ingest import normalize_graph
from .validation import validate_analysis_artifact, validate_experiment_artifact, validate_options_artifact

DEFAULT_DIRECTORY = Path(__file__).resolve().parents[1] / "data" / "projects"
MAX_PROJECT_BYTES = 40 * 1024 * 1024


def project_directory() -> Path:
    return Path(os.environ.get("ORBITA_PROJECT_DIR", DEFAULT_DIRECTORY))


def _path(project_id: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{32}", project_id):
        raise ValueError("Некорректный идентификатор проекта.")
    return project_directory() / f"{project_id}.json"


def _validated_project(value, expected_id: str) -> dict:
    """Reject corrupt or inconsistent project files."""
    if not isinstance(value, dict):
        raise ValueError("Повреждён файл проекта: ожидается объект JSON.")
    payload = dict(value)
    if payload.get("id") != expected_id:
        raise ValueError("Повреждён файл проекта: идентификатор не соответствует имени файла.")
    if type(payload.get("version")) is not int or payload["version"] != 1:
        raise ValueError("Неподдерживаемая версия файла проекта.")
    name = payload.get("name")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 160 or any(ord(char) < 32 for char in name):
        raise ValueError("Повреждён файл проекта: некорректное название.")
    payload["name"] = name.strip()
    timestamp = payload.get("updated_at")
    try:
        if not isinstance(timestamp, str) or len(timestamp) > 100:
            raise ValueError
        parsed = datetime.fromisoformat(timestamp)
        if parsed.tzinfo is None:
            raise ValueError
        payload["updated_at"] = parsed.astimezone(timezone.utc).isoformat()
    except (ValueError, OverflowError):
        raise ValueError("Повреждён файл проекта: некорректная дата сохранения.") from None
    payload["graph"] = normalize_graph(payload.get("graph"))
    if payload.get("options") is not None:
        payload["options"] = validate_options_artifact(payload["options"], {n["id"] for n in payload["graph"]["nodes"]})
    if payload.get("analysis") is not None:
        payload["analysis"] = validate_analysis_artifact(payload["analysis"])
    if payload.get("experiments") is not None:
        payload["experiments"] = validate_experiment_artifact(payload["experiments"])
    return payload


def save_project(project: dict) -> dict:
    directory = project_directory()
    directory.mkdir(parents=True, exist_ok=True)
    project_id = uuid.uuid4().hex
    payload = dict(project)
    payload.update(id=project_id, updated_at=datetime.now(timezone.utc).isoformat(), version=1)
    payload = _validated_project(payload, project_id)
    try:
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise ValueError("Проект должен содержать только корректные конечные значения JSON.") from None
    if len(encoded) > MAX_PROJECT_BYTES:
        raise ValueError("Проект слишком большой. Сохраните граф без результатов экспериментов.")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=directory, prefix=".save-", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, _path(project_id))
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
    return {key: payload[key] for key in ("id", "name", "updated_at")}


def read_project(project_id: str) -> dict:
    path = _path(project_id)
    if not path.is_file() or path.is_symlink():
        raise FileNotFoundError("Проект не найден.")
    if path.stat().st_size > MAX_PROJECT_BYTES:
        raise ValueError("Файл проекта превышает допустимый размер.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError, RecursionError):
        raise ValueError("Повреждён файл проекта: не удалось прочитать JSON в UTF-8.") from None
    return _validated_project(payload, project_id)


def list_projects() -> list[dict]:
    directory = project_directory()
    if not directory.exists():
        return []
    projects = []
    for path in directory.glob("*.json"):
        try:
            project = read_project(path.stem)
            graph = project.get("graph", {})
            projects.append({"id": path.stem, "name": project["name"],
                             "updated_at": project["updated_at"],
                             "node_count": len(graph.get("nodes", [])),
                             "edge_count": len(graph.get("edges", []))})
        except (ValueError, OSError, KeyError, TypeError):
            continue
    return sorted(projects, key=lambda item: item["updated_at"], reverse=True)


def delete_project(project_id: str) -> None:
    path = _path(project_id)
    if not path.is_file() or path.is_symlink():
        raise FileNotFoundError("Проект не найден.")
    path.unlink()
