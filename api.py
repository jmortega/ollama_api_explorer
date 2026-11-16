"""Gateway FastAPI sobre la API de Ollama.

Expone los mismos endpoints con validación Pydantic y documentación Swagger
automática en /docs (y ReDoc en /redoc). El host de Ollama se pasa como
parámetro de consulta `host` (por defecto 'localhost'); el puerto es fijo 11434.

Arranque:
    uvicorn api:app --reload --port 8000
    -> http://localhost:8000/docs
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from models import (
    ChatRequest,
    CopyRequest,
    CreateRequest,
    DeleteRequest,
    EmbedRequest,
    GenerateRequest,
    OpenAIChatRequest,
    PullRequest,
    ShowRequest,
)
from ollama_client import OLLAMA_PORT, OllamaClient, OllamaError

app = FastAPI(
    title="Ollama API Explorer — Gateway",
    description=(
        "Gateway de pruebas sobre la API de Ollama (puerto fijo "
        f"{OLLAMA_PORT}). Indica la IP del servidor en el parámetro `host` "
        "(por defecto `localhost`). Sin autenticación: uso en laboratorio."
    ),
    version="1.0.0",
    contact={"name": "TSS AI Security Academy"},
)

HostParam = Query("localhost", description="IP o hostname donde escucha Ollama (puerto fijo 11434).")


def _client(host: str) -> OllamaClient:
    return OllamaClient(host=host)


def _run(fn):
    try:
        return fn()
    except OllamaError as exc:
        raise HTTPException(status_code=exc.status or 502,
                            detail={"error": str(exc), "body": exc.body})


# ----------------------------------------------------------------- Lectura
@app.get("/version", tags=["Lectura"], summary="Versión del servicio")
def version(host: str = HostParam):
    return _run(lambda: _client(host).version())


@app.get("/tags", tags=["Lectura"], summary="Inventario de modelos (/api/tags)")
def tags(host: str = HostParam):
    return _run(lambda: _client(host).tags())


@app.get("/ps", tags=["Lectura"], summary="Modelos cargados en memoria (/api/ps)")
def ps(host: str = HostParam):
    return _run(lambda: _client(host).ps())


@app.get("/models", tags=["Lectura"], summary="Inventario vía API compatible (/v1/models)")
def v1_models(host: str = HostParam):
    return _run(lambda: _client(host).v1_models())


@app.post("/show", tags=["Lectura"], summary="Metadatos detallados (/api/show)")
def show(body: ShowRequest, host: str = HostParam):
    return _run(lambda: _client(host).show(body.model))


# -------------------------------------------------------------- Uso servicio
@app.post("/generate", tags=["Uso del servicio"], summary="Inferencia (/api/generate)")
def generate(body: GenerateRequest, host: str = HostParam):
    return _run(lambda: _client(host).generate(
        body.model, body.prompt, stream=False, system=body.system, options=body.options))


@app.post("/chat", tags=["Uso del servicio"], summary="Conversación (/api/chat)")
def chat(body: ChatRequest, host: str = HostParam):
    messages = [m.model_dump() for m in body.messages]
    return _run(lambda: _client(host).chat(body.model, messages, stream=False, options=body.options))


@app.post("/v1/chat/completions", tags=["Uso del servicio"],
          summary="Inferencia vía API compatible OpenAI")
def v1_chat_completions(body: OpenAIChatRequest, host: str = HostParam):
    messages = [m.model_dump() for m in body.messages]
    return _run(lambda: _client(host).v1_chat_completions(body.model, messages, stream=False))


@app.post("/embed", tags=["Uso del servicio"], summary="Embeddings (/api/embed)")
def embed(body: EmbedRequest, host: str = HostParam):
    return _run(lambda: _client(host).embed(body.model, body.input))


# -------------------------------------------------------------- Modificación
@app.post("/pull", tags=["Modificación"], summary="Incorporar modelo (/api/pull)")
def pull(body: PullRequest, host: str = HostParam):
    return _run(lambda: _client(host).pull(body.model, stream=False))


@app.post("/copy", tags=["Modificación"], summary="Crear otra referencia (/api/copy)")
def copy(body: CopyRequest, host: str = HostParam):
    return _run(lambda: _client(host).copy(body.source, body.destination))


@app.post("/create", tags=["Modificación"], summary="Crear modelo derivado (/api/create)")
def create(body: CreateRequest, host: str = HostParam):
    payload = body.model_dump(by_alias=True, exclude_none=True)
    return _run(lambda: _client(host).create(payload))


@app.delete("/delete", tags=["Modificación"], summary="Eliminar modelo (/api/delete)")
def delete(body: DeleteRequest, host: str = HostParam):
    return _run(lambda: _client(host).delete(body.model))


@app.get("/blobs/{digest}", tags=["Modificación"], summary="Comprobar existencia de un blob (HEAD)")
def blob_exists(digest: str, host: str = HostParam):
    return _run(lambda: _client(host).blob_exists(digest))


@app.get("/", include_in_schema=False)
def root():
    return {"app": "Ollama API Explorer Gateway", "docs": "/docs", "ollama_port": OLLAMA_PORT}
