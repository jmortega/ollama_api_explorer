"""Modelos Pydantic para las peticiones a la API de Ollama."""
from __future__ import annotations

from typing import Any, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    # 'model' es un nombre de campo legítimo en la API de Ollama; desactivamos
    # el namespace protegido de Pydantic para evitar avisos.
    model_config = ConfigDict(protected_namespaces=())


class ChatMessage(_Base):
    role: str = Field(..., examples=["user"], description="system | user | assistant")
    content: str = Field(..., examples=["¿Qué es un modelo de IA?"])


# ---- Lectura ----
class ShowRequest(_Base):
    model: str = Field(..., examples=["llama3.2:3b"])


# ---- Uso del servicio ----
class GenerateRequest(_Base):
    model: str = Field(..., examples=["llama3.2:3b"])
    prompt: str = Field(..., examples=["Explica brevemente qué es una auditoría de seguridad."])
    stream: bool = False
    system: Optional[str] = Field(default=None, description="Prompt de sistema opcional.")
    options: Optional[dict[str, Any]] = Field(
        default=None, examples=[{"temperature": 0.7}], description="Opciones de inferencia de Ollama."
    )


class ChatRequest(_Base):
    model: str = Field(..., examples=["llama3.2:3b"])
    messages: list[ChatMessage]
    stream: bool = False
    options: Optional[dict[str, Any]] = None


class OpenAIChatRequest(_Base):
    """Cuerpo compatible con la API OpenAI (/v1/chat/completions)."""
    model: str = Field(..., examples=["llama3.2:3b"])
    messages: list[ChatMessage]
    stream: bool = False


class EmbedRequest(_Base):
    model: str = Field(..., examples=["nomic-embed-text"])
    input: Union[str, list[str]] = Field(..., examples=["texto a vectorizar"])


# ---- Modificación ----
class PullRequest(_Base):
    model: str = Field(..., examples=["tinyllama"])
    stream: bool = False


class CopyRequest(_Base):
    source: str = Field(..., examples=["llama3.2:3b"])
    destination: str = Field(..., examples=["llama3.2:3b-copy"])


class DeleteRequest(_Base):
    model: str = Field(..., examples=["tinyllama"])


class CreateRequest(_Base):
    # extra='allow' permite pasar cualquier campo adicional que admita la
    # versión de Ollama instalada (p. ej. 'adapters', 'quantize'...).
    model_config = ConfigDict(protected_namespaces=(), extra="allow", populate_by_name=True)
    model: str = Field(..., examples=["mi-llama"])
    from_: Optional[str] = Field(default=None, alias="from", examples=["llama3.2:3b"])
    system: Optional[str] = Field(default=None, examples=["Responde siempre en español."])
    template: Optional[str] = None
