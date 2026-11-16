"""Abstracción de backend para la interfaz: directo a Ollama o vía gateway FastAPI."""
from __future__ import annotations

from typing import Any, Union

import httpx

from ollama_client import OllamaClient, OllamaError


class DirectBackend:
    """Habla directamente con Ollama (puerto 11434)."""
    kind = "directo"

    def __init__(self, host: str):
        self.client = OllamaClient(host=host)
        self.base_url = self.client.base_url

    def version(self): return self.client.version()
    def tags(self): return self.client.tags()
    def ps(self): return self.client.ps()
    def v1_models(self): return self.client.v1_models()
    def show(self, model): return self.client.show(model)
    def list_models(self): return self.client.list_model_names()

    def generate(self, model, prompt, system=None, options=None):
        return self.client.generate(model, prompt, stream=False, system=system, options=options)

    def chat(self, model, messages, options=None):
        return self.client.chat(model, messages, stream=False, options=options)

    def v1_chat(self, model, messages):
        return self.client.v1_chat_completions(model, messages, stream=False)

    def embed(self, model, input_): return self.client.embed(model, input_)
    def pull(self, model): return self.client.pull(model, stream=False)
    def copy(self, source, destination): return self.client.copy(source, destination)
    def create(self, body): return self.client.create(body)
    def delete(self, model): return self.client.delete(model)
    def blob_exists(self, digest): return self.client.blob_exists(digest)


class GatewayBackend:
    """Habla con el gateway FastAPI, que a su vez habla con Ollama."""
    kind = "gateway"

    def __init__(self, gateway_url: str, host: str, timeout: float = 300.0):
        self.gateway = gateway_url.rstrip("/")
        self.host = host
        self.timeout = timeout
        self.base_url = self.gateway

    def _get(self, path, params=None):
        p = {"host": self.host}
        if params:
            p.update(params)
        try:
            r = httpx.get(f"{self.gateway}{path}", params=p, timeout=self.timeout)
        except httpx.RequestError as exc:
            raise OllamaError(f"No se pudo conectar con el gateway {self.gateway}: {exc}") from exc
        return self._parse(r)

    def _post(self, path, json):
        try:
            r = httpx.post(f"{self.gateway}{path}", params={"host": self.host}, json=json, timeout=self.timeout)
        except httpx.RequestError as exc:
            raise OllamaError(f"No se pudo conectar con el gateway {self.gateway}: {exc}") from exc
        return self._parse(r)

    def _delete(self, path, json):
        try:
            r = httpx.request("DELETE", f"{self.gateway}{path}", params={"host": self.host},
                              json=json, timeout=self.timeout)
        except httpx.RequestError as exc:
            raise OllamaError(f"No se pudo conectar con el gateway {self.gateway}: {exc}") from exc
        return self._parse(r)

    @staticmethod
    def _parse(r: httpx.Response) -> Any:
        try:
            data = r.json()
        except Exception:
            data = {"raw": r.text}
        if r.status_code >= 400:
            raise OllamaError(f"HTTP {r.status_code}", status=r.status_code, body=data)
        return data

    def version(self): return self._get("/version")
    def tags(self): return self._get("/tags")
    def ps(self): return self._get("/ps")
    def v1_models(self): return self._get("/models")
    def show(self, model): return self._post("/show", {"model": model})

    def list_models(self):
        try:
            return [m["name"] for m in self.tags().get("models", [])]
        except OllamaError:
            return []

    def generate(self, model, prompt, system=None, options=None):
        body = {"model": model, "prompt": prompt, "stream": False}
        if system:
            body["system"] = system
        if options:
            body["options"] = options
        return self._post("/generate", body)

    def chat(self, model, messages, options=None):
        body = {"model": model, "messages": messages, "stream": False}
        if options:
            body["options"] = options
        return self._post("/chat", body)

    def v1_chat(self, model, messages):
        return self._post("/v1/chat/completions", {"model": model, "messages": messages, "stream": False})

    def embed(self, model, input_): return self._post("/embed", {"model": model, "input": input_})
    def pull(self, model): return self._post("/pull", {"model": model, "stream": False})
    def copy(self, source, destination): return self._post("/copy", {"source": source, "destination": destination})
    def create(self, body): return self._post("/create", body)
    def delete(self, model): return self._delete("/delete", {"model": model})
    def blob_exists(self, digest): return self._get(f"/blobs/{digest}")
