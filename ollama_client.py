"""Cliente HTTP ligero para la API de Ollama.

El puerto es fijo (11434). El host es configurable; por defecto 'localhost'.
No añade autenticación (tal y como se solicita para el laboratorio).
"""
from __future__ import annotations

from typing import Any, Optional, Union

import httpx

OLLAMA_PORT = 11434
DEFAULT_TIMEOUT = 300.0  # la inferencia / pull puede tardar


class OllamaError(Exception):
    def __init__(self, message: str, status: Optional[int] = None, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body


def normalize_host(host: Optional[str]) -> str:
    """Admite 'localhost', '192.168.1.10' o 'http://192.168.1.10' y devuelve el host limpio."""
    host = (host or "localhost").strip()
    host = host.replace("http://", "").replace("https://", "").strip("/")
    # si el usuario pega 'ip:puerto', nos quedamos con la ip
    if ":" in host:
        host = host.split(":", 1)[0]
    return host or "localhost"


class OllamaClient:
    def __init__(self, host: str = "localhost", port: int = OLLAMA_PORT, timeout: float = DEFAULT_TIMEOUT):
        self.host = normalize_host(host)
        self.port = port
        self.timeout = timeout
        self.base_url = f"http://{self.host}:{self.port}"

    # ------------------------------------------------------------------ core
    def _request(self, method: str, path: str, json: Any = None, expect_json: bool = True) -> Any:
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.request(method, url, json=json)
        except httpx.RequestError as exc:
            raise OllamaError(f"No se pudo conectar con {self.base_url}: {exc}") from exc

        if not expect_json:
            text = resp.text
            payload: Any
            try:
                payload = resp.json()
            except Exception:
                payload = text
            result = {
                "status_code": resp.status_code,
                "headers": dict(resp.headers),
                "body": payload,
            }
            if resp.status_code >= 400:
                raise OllamaError(f"HTTP {resp.status_code}", status=resp.status_code, body=result)
            return result

        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text}
        if resp.status_code >= 400:
            raise OllamaError(f"HTTP {resp.status_code}", status=resp.status_code, body=data)
        return data

    # --------------------------------------------------------------- Lectura
    def version(self) -> dict:
        return self._request("GET", "/api/version")

    def tags(self) -> dict:
        return self._request("GET", "/api/tags")

    def ps(self) -> dict:
        return self._request("GET", "/api/ps")

    def v1_models(self) -> dict:
        return self._request("GET", "/v1/models")

    def show(self, model: str) -> dict:
        return self._request("POST", "/api/show", json={"model": model})

    def list_model_names(self) -> list[str]:
        try:
            return [m["name"] for m in self.tags().get("models", [])]
        except OllamaError:
            return []

    # ----------------------------------------------------------- Uso servicio
    def generate(self, model: str, prompt: str, stream: bool = False,
                 system: Optional[str] = None, options: Optional[dict] = None) -> dict:
        body: dict[str, Any] = {"model": model, "prompt": prompt, "stream": stream}
        if system:
            body["system"] = system
        if options:
            body["options"] = options
        return self._request("POST", "/api/generate", json=body)

    def chat(self, model: str, messages: list[dict], stream: bool = False,
             options: Optional[dict] = None) -> dict:
        body: dict[str, Any] = {"model": model, "messages": messages, "stream": stream}
        if options:
            body["options"] = options
        return self._request("POST", "/api/chat", json=body)

    def v1_chat_completions(self, model: str, messages: list[dict], stream: bool = False) -> dict:
        return self._request("POST", "/v1/chat/completions",
                             json={"model": model, "messages": messages, "stream": stream})

    def embed(self, model: str, input_: Union[str, list[str]]) -> dict:
        return self._request("POST", "/api/embed", json={"model": model, "input": input_})

    # --------------------------------------------------------- Modificación
    def pull(self, model: str, stream: bool = False) -> dict:
        return self._request("POST", "/api/pull", json={"model": model, "stream": stream})

    def copy(self, source: str, destination: str) -> dict:
        return self._request("POST", "/api/copy",
                             json={"source": source, "destination": destination}, expect_json=False)

    def create(self, body: dict) -> dict:
        # la respuesta puede ser NDJSON (progreso); devolvemos texto crudo.
        return self._request("POST", "/api/create", json=body, expect_json=False)

    def delete(self, model: str) -> dict:
        return self._request("DELETE", "/api/delete", json={"model": model}, expect_json=False)

    def blob_exists(self, digest: str) -> dict:
        return self._request("HEAD", f"/api/blobs/{digest}", expect_json=False)
