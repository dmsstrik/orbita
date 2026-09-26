from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import __version__, storage
from .ingest import apply_labels, demo_graph, list_demos, normalize_graph, parse_graph
from .jobs import JobBusy, JobTimeout, run_job

ROOT = Path(__file__).resolve().parents[1]
MAX_BODY = 40 * 1024 * 1024


def _load_env_file() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        key, _, value = line.strip().partition("=")
        if key == "VK_TOKEN" and value.strip() and not os.environ.get("VK_TOKEN"):
            os.environ["VK_TOKEN"] = value.strip()


_load_env_file()
VK_TOKEN = os.environ.get("VK_TOKEN", "")
app = FastAPI(title="Орбита", description="Локальная лаборатория социальных графов", version=__version__)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"])


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Options(StrictModel):
    root: str | None = Field(default=None, max_length=128)
    radius: int = Field(default=1, ge=1, le=3)
    threshold: float = Field(default=0.65, ge=0, le=1, allow_inf_nan=False)
    exclude_root: bool = True
    max_pairs: int = Field(default=2000, ge=1, le=20_000)


class ImportRequest(StrictModel):
    content: str = Field(max_length=20_000_000)
    filename: str = Field(default="graph.csv", max_length=255)
    name: str = Field(default="", max_length=160)


class LabelsRequest(ImportRequest):
    graph: dict[str, Any]


class AnalysisRequest(StrictModel):
    graph: dict[str, Any]
    options: Options = Field(default_factory=Options)


class ExperimentConfig(StrictModel):
    clone_count: int = Field(default=3, ge=1, le=10)
    retention: float = Field(default=0.8, ge=0, le=1, allow_inf_nan=False)
    noise_levels: list[float] = Field(default_factory=lambda: [0, 0.05, 0.15], min_length=1, max_length=6)
    repeats: int = Field(default=3, ge=1, le=5)
    seed: int = Field(default=42, ge=0, le=2**32 - 1)
    threshold: float = Field(default=0.65, ge=0, le=1, allow_inf_nan=False)
    root: str | None = Field(default=None, max_length=128)
    exclude_root: bool = True


class ExperimentRequest(StrictModel):
    graph: dict[str, Any]
    config: ExperimentConfig = Field(default_factory=ExperimentConfig)


class VKRequest(StrictModel):
    user_id: str = Field(min_length=1, max_length=128)
    max_friends: int = Field(default=80, ge=1, le=80)


class GraphRequest(StrictModel):
    graph: dict[str, Any]


class ExportRequest(StrictModel):
    analysis: dict[str, Any]
    experiments: dict[str, Any] | None = None

    @field_validator("analysis")
    @classmethod
    def check_analysis(cls, value):
        from .validation import validate_analysis_artifact
        return validate_analysis_artifact(value)

    @field_validator("experiments")
    @classmethod
    def check_experiments(cls, value):
        from .validation import validate_experiment_artifact
        return validate_experiment_artifact(value) if value is not None else None


class ExperimentExportRequest(StrictModel):
    experiments: dict[str, Any]

    @field_validator("experiments")
    @classmethod
    def check_experiments(cls, value):
        from .validation import validate_experiment_artifact
        return validate_experiment_artifact(value)


class ProjectRequest(StrictModel):
    name: str = Field(min_length=1, max_length=160)
    graph: dict[str, Any]
    options: dict[str, Any] | None = None
    analysis: dict[str, Any] | None = None
    experiments: dict[str, Any] | None = None

    @field_validator("analysis")
    @classmethod
    def check_analysis(cls, value):
        from .validation import validate_analysis_artifact
        return validate_analysis_artifact(value) if value is not None else None

    @field_validator("experiments")
    @classmethod
    def check_experiments(cls, value):
        from .validation import validate_experiment_artifact
        return validate_experiment_artifact(value) if value is not None else None

    @field_validator("options")
    @classmethod
    def check_options(cls, value):
        if value is None:
            return None
        return Options.model_validate({k: v for k, v in value.items() if k in Options.model_fields}).model_dump()


@app.middleware("http")
async def request_boundaries(request: Request, call_next):
    if request.method in {"POST", "PUT", "DELETE"}:
        origin = request.headers.get("origin")
        if origin:
            parsed = urlparse(origin)
            if parsed.scheme not in {"http", "https"} or parsed.netloc != request.headers.get("host"):
                return JSONResponse({"detail": "Запрос разрешён только из интерфейса этого приложения."}, status_code=403)
        if request.method != "DELETE" and "application/json" not in request.headers.get("content-type", ""):
            return JSONResponse({"detail": "Ожидается запрос в формате JSON."}, status_code=415)
        try:
            if int(request.headers.get("content-length", "0")) > MAX_BODY:
                return JSONResponse({"detail": "Размер запроса превышает 12 МБ."}, status_code=413)
        except ValueError:
            return JSONResponse({"detail": "Некорректный размер запроса."}, status_code=400)
        chunks = []
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > MAX_BODY:
                return JSONResponse({"detail": "Размер запроса превышает 12 МБ."}, status_code=413)
            chunks.append(chunk)
        request._body = b"".join(chunks)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(RequestValidationError)
async def invalid_request(_request: Request, exception: RequestValidationError):
    # Validation errors may echo the request body, including tokens.
    fields = ", ".join(".".join(str(x) for x in error["loc"][1:]) for error in exception.errors()[:5])
    return JSONResponse({"detail": f"Проверьте параметры запроса: {fields or 'некорректный JSON'}."}, status_code=422)


@app.exception_handler(ValueError)
async def invalid_data(_request: Request, exception: ValueError):
    return JSONResponse({"detail": str(exception)}, status_code=422)


@app.exception_handler(JobTimeout)
async def timed_out(_request: Request, exception: JobTimeout):
    return JSONResponse({"detail": str(exception)}, status_code=504)


@app.exception_handler(JobBusy)
async def job_busy(_request: Request, exception: JobBusy):
    return JSONResponse({"detail": str(exception)}, status_code=429)


@app.exception_handler(FileNotFoundError)
async def missing_file(_request: Request, exception: FileNotFoundError):
    return JSONResponse({"detail": "Проект не найден."}, status_code=404)


@app.get("/api/health")
def health():
    import pynauty
    return {"status": "ok", "version": __version__, "engine": "nauty / pynauty", "engine_version": pynauty.__version__}


@app.get("/api/demos")
def demos():
    return {"demos": list_demos()}


@app.get("/api/demos/{demo_id}")
def get_demo(demo_id: str):
    return demo_graph(demo_id)


@app.post("/api/import")
def import_graph(payload: ImportRequest):
    return parse_graph(payload.content, payload.filename, payload.name)


@app.post("/api/labels")
def import_labels(payload: LabelsRequest):
    return apply_labels(normalize_graph(payload.graph), payload.content, payload.filename)


@app.post("/api/analyze")
def analyze(payload: AnalysisRequest):
    return run_job("analyze", normalize_graph(payload.graph), payload.options.model_dump(), timeout=30)


@app.post("/api/experiments")
def experiments(payload: ExperimentRequest):
    config = payload.config.model_dump()
    if any(not 0 <= value <= 1 for value in config["noise_levels"]):
        raise ValueError("Доли шума должны быть числами от 0 до 1.")
    graph = normalize_graph(payload.graph)
    if len(graph["nodes"]) + config["clone_count"] > 2000:
        raise ValueError("После добавления клонов граф должен содержать не более 2000 вершин.")
    return run_job("experiments", graph, config, timeout=120)


@app.post("/api/vk")
def import_vk(payload: VKRequest):
    if not VK_TOKEN:
        raise HTTPException(status_code=503, detail="VK_TOKEN не задан: добавьте его в файл .env рядом с run.py или в переменные окружения.")
    return run_job("vk", payload.user_id, VK_TOKEN, payload.max_friends, timeout=150)


def download(content: str, filename: str, media_type: str):
    return Response(content, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.post("/api/export/json")
def export_graph(payload: GraphRequest):
    graph = normalize_graph(payload.graph)
    return download(json.dumps(graph, ensure_ascii=False, indent=2, allow_nan=False), "orbita-graph.json", "application/json")


@app.post("/api/export/csv")
def export_candidates(payload: ExportRequest):
    from .exports import candidates_csv
    return download(candidates_csv(payload.analysis), "orbita-candidates.csv", "text/csv")


@app.post("/api/export/html")
def export_report(payload: ExportRequest):
    from .exports import html_report
    return download(html_report(payload.analysis, payload.experiments), "orbita-report.html", "text/html")


@app.post("/api/export/experiments")
def export_experiments(payload: ExperimentExportRequest):
    from .exports import experiments_csv
    return download(experiments_csv(payload.experiments), "orbita-experiments.csv", "text/csv")


@app.get("/api/projects")
def projects():
    return {"projects": storage.list_projects()}


@app.post("/api/projects")
def create_project(payload: ProjectRequest):
    project = payload.model_dump()
    project["name"] = project["name"].strip()
    if not project["name"]:
        raise ValueError("Укажите название проекта.")
    project["graph"] = normalize_graph(project["graph"])
    if project["options"]:
        project["options"] = Options.model_validate(project["options"]).model_dump()
    return storage.save_project(project)


@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    return storage.read_project(project_id)


@app.delete("/api/projects/{project_id}")
def remove_project(project_id: str):
    storage.delete_project(project_id)
    return {"ok": True}


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/api/examples/{filename}")
def example_file(filename: str):
    if Path(filename).name != filename:
        raise HTTPException(status_code=404, detail="Пример не найден.")
    path = ROOT / "examples" / filename
    if not path.is_file() or path.suffix not in {".csv", ".json", ".txt"}:
        raise HTTPException(status_code=404, detail="Пример не найден.")
    return FileResponse(path, filename=path.name)


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
