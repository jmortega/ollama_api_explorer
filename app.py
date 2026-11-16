"""Ollama API Explorer — interfaz Streamlit.

Permite probar los principales endpoints de la API de Ollama:
  Lectura:       /api/version, /api/tags, /api/ps, /v1/models, /api/show
  Uso:           /api/generate, /api/chat, /v1/chat/completions, /api/embed
  Modificación:  /api/pull, /api/copy, /api/create, /api/delete, /api/blobs/{digest}

El puerto es fijo (11434). La IP del servidor se introduce en la barra lateral
(por defecto localhost). Sin autenticación (uso en laboratorio).

Ejecutar:  streamlit run app.py
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import streamlit as st

from backends import DirectBackend, GatewayBackend
from ollama_client import OLLAMA_PORT, OllamaError, normalize_host

st.set_page_config(page_title="Ollama API Explorer", page_icon="🦙", layout="wide")


# --------------------------------------------------------------------- utils
def duration_s(nanos: Any) -> str:
    try:
        return f"{float(nanos) / 1e9:.2f} s"
    except Exception:
        return "—"


def show_error(exc: OllamaError):
    st.error(f"❌ {exc}")
    if exc.body:
        with st.expander("Detalle del error"):
            st.json(exc.body)


def get_backend():
    host = st.session_state.get("host", "localhost")
    mode = st.session_state.get("mode", "Directo a Ollama")
    if mode.startswith("Gateway"):
        return GatewayBackend(st.session_state.get("gateway", "http://localhost:8000"), host)
    return DirectBackend(host)


def _sh_quote(s: str) -> str:
    """Comilla simple segura para shell (maneja comillas embebidas)."""
    return "'" + s.replace("'", "'\\''") + "'"


def curl_cmd(method: str, path: str, body: Any = None, head: bool = False) -> str:
    """Construye el curl equivalente contra Ollama (puerto fijo 11434)."""
    host = normalize_host(st.session_state.get("host", "localhost"))
    url = f"http://{host}:{OLLAMA_PORT}{path}"
    if head:
        return f"curl -I {url}"
    if method == "GET":
        return f"curl {url}"
    parts = [f"curl -X {method} {url}", '-H "Content-Type: application/json"']
    if body is not None:
        parts.append("-d " + _sh_quote(json.dumps(body, ensure_ascii=False)))
    return " \\\n  ".join(parts)


def show_curl(method: str, path: str, body: Any = None, head: bool = False):
    """Desplegable con el comando curl equivalente a la llamada actual."""
    with st.expander("📋 Ver comando curl equivalente"):
        st.code(curl_cmd(method, path, body, head), language="bash")


@st.cache_data(show_spinner=False, ttl=30)
def cached_models(host: str, mode: str, gateway: str) -> list[str]:
    try:
        return get_backend().list_models()
    except OllamaError:
        return []


def model_selector(label: str, key: str, allow_text: bool = True) -> str:
    models = cached_models(st.session_state.get("host"), st.session_state.get("mode"),
                           st.session_state.get("gateway", ""))
    if models:
        return st.selectbox(label, models, key=key)
    st.caption("No se pudo obtener la lista de modelos; introdúcelo manualmente.")
    return st.text_input(label, value="llama3.2:3b", key=key + "_txt")


# ------------------------------------------------------------------- sidebar
with st.sidebar:
    st.title("🦙 Ollama API Explorer")
    st.caption("Laboratorio de endpoints — AI Security Academy")

    st.text_input("IP del servidor Ollama", value=st.session_state.get("host", "localhost"),
                  key="host", help="localhost o la IP donde escucha Ollama (p. ej. 192.168.18.17).")
    st.text_input("Puerto (fijo)", value=str(OLLAMA_PORT), disabled=True)

    st.radio("Modo de conexión", ["Directo a Ollama", "Gateway FastAPI"], key="mode",
             help="Directo: la app llama a Ollama. Gateway: la app llama al backend FastAPI, "
                  "que valida con Pydantic y ofrece Swagger en /docs.")
    if st.session_state.get("mode", "").startswith("Gateway"):
        st.text_input("URL del gateway FastAPI", value=st.session_state.get("gateway", "http://localhost:8000"),
                      key="gateway")

    if st.button("🔌 Probar conexión", use_container_width=True):
        try:
            data = get_backend().version()
            st.success(f"Conectado · Ollama {data.get('version', '?')}")
        except OllamaError as exc:
            show_error(exc)

    st.divider()
    b = get_backend()
    st.caption(f"Destino: `{b.base_url}` · modo **{b.kind}**")
    st.caption("Swagger del gateway: ejecuta `uvicorn api:app --port 8000` y abre "
               "[/docs](http://localhost:8000/docs).")


st.title("Consulta de endpoints de la API de Ollama")

tab_read, tab_use, tab_mod, tab_help = st.tabs(
    ["📖 Lectura", "⚙️ Uso del servicio", "🛠️ Modificación", "ℹ️ Ayuda / Swagger"]
)


# ============================================================== LECTURA
with tab_read:
    st.subheader("Lectura — inventario y metadatos")
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("/api/version", use_container_width=True):
        try:
            st.json(get_backend().version())
        except OllamaError as exc:
            show_error(exc)
    if c2.button("/api/tags", use_container_width=True):
        try:
            data = get_backend().tags()
            rows = [{
                "name": m.get("name"),
                "parámetros": m.get("details", {}).get("parameter_size"),
                "cuantización": m.get("details", {}).get("quantization_level"),
                "tamaño (GB)": round(m.get("size", 0) / 1e9, 2),
                "familia": m.get("details", {}).get("family"),
            } for m in data.get("models", [])]
            st.dataframe(rows, use_container_width=True)
            with st.expander("JSON completo"):
                st.json(data)
        except OllamaError as exc:
            show_error(exc)
    if c3.button("/api/ps (cargados)", use_container_width=True):
        try:
            data = get_backend().ps()
            modelos = data.get("models", [])
            if modelos:
                rows = [{
                    "name": m.get("name"),
                    "digest": m.get("digest"),
                    "parámetros": m.get("details", {}).get("parameter_size"),
                    "cuantización": m.get("details", {}).get("quantization_level"),
                    "tamaño (GB)": round(m.get("size", 0) / 1e9, 2),
                    "VRAM (GB)": round(m.get("size_vram", 0) / 1e9, 2),
                    "contexto": m.get("context_length"),
                    "expira": str(m.get("expires_at", ""))[:19].replace("T", " "),
                } for m in modelos]
                st.dataframe(rows, use_container_width=True)
            else:
                st.info("No hay modelos cargados en memoria.")
            with st.expander("JSON completo"):
                st.json(data)
        except OllamaError as exc:
            show_error(exc)
    if c4.button("/v1/models", use_container_width=True):
        try:
            data = get_backend().v1_models()
            rows = []
            for m in data.get("data", []):
                created = m.get("created")
                try:
                    fecha = datetime.fromtimestamp(created).strftime("%Y-%m-%d %H:%M") if created else ""
                except Exception:
                    fecha = str(created)
                rows.append({
                    "id": m.get("id"),
                    "object": m.get("object"),
                    "owned_by": m.get("owned_by"),
                    "created": fecha,
                })
            if rows:
                st.dataframe(rows, use_container_width=True)
            else:
                st.info("Sin modelos en la respuesta.")
            with st.expander("JSON completo"):
                st.json(data)
        except OllamaError as exc:
            show_error(exc)

    with st.expander("📋 Ver comandos curl (endpoints de lectura GET)"):
        for pth in ["/api/version", "/api/tags", "/api/ps", "/v1/models"]:
            st.code(curl_cmd("GET", pth), language="bash")

    st.divider()
    st.markdown("**/api/show** — metadatos detallados de un modelo")
    m = model_selector("Modelo", key="show_model")
    show_curl("POST", "/api/show", {"model": m})
    if st.button("Consultar metadatos", key="show_btn"):
        try:
            data = get_backend().show(m)
            cols = st.columns(2)
            with cols[0]:
                st.caption("details")
                st.json(data.get("details", {}))
            with cols[1]:
                st.caption("model_info")
                st.json(data.get("model_info", {}))
            with st.expander("Respuesta completa"):
                st.json(data)
        except OllamaError as exc:
            show_error(exc)


# ============================================================== USO
with tab_use:
    st.subheader("Uso del servicio — inferencia")
    sub = st.radio("Endpoint", ["/api/generate", "/api/chat", "/v1/chat/completions", "/api/embed"],
                   horizontal=True, key="use_sub")

    # ---- generate ----
    if sub == "/api/generate":
        model = model_selector("Modelo", key="gen_model")
        system = st.text_input("System prompt (opcional)", key="gen_system")
        prompt = st.text_area("Prompt", value="Explica brevemente qué es una auditoría de seguridad.",
                              height=140, key="gen_prompt")
        temp = st.slider("temperature", 0.0, 1.5, 0.7, 0.1, key="gen_temp")
        _gen_body = {"model": model, "prompt": prompt, "stream": False, "options": {"temperature": temp}}
        if system:
            _gen_body["system"] = system
        show_curl("POST", "/api/generate", _gen_body)
        if st.button("Generar", type="primary", key="gen_btn"):
            with st.spinner("Generando…"):
                try:
                    data = get_backend().generate(model, prompt, system=system or None,
                                                  options={"temperature": temp})
                    st.markdown("#### Respuesta")
                    st.write(data.get("response", ""))
                    cols = st.columns(3)
                    cols[0].metric("tokens generados", data.get("eval_count", "—"))
                    cols[1].metric("duración total", duration_s(data.get("total_duration")))
                    ec, ed = data.get("eval_count"), data.get("eval_duration")
                    tps = f"{ec / (ed / 1e9):.1f}" if ec and ed else "—"
                    cols[2].metric("tokens/s", tps)
                    with st.expander("JSON completo"):
                        st.json(data)
                except OllamaError as exc:
                    show_error(exc)

    # ---- chat ----
    elif sub == "/api/chat":
        model = model_selector("Modelo", key="chat_model")
        system = st.text_input("System prompt (opcional)", key="chat_system",
                               value="")
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []
        cc1, cc2 = st.columns([1, 5])
        if cc1.button("🗑️ Limpiar", key="chat_clear"):
            st.session_state.chat_history = []

        _chat_msgs = ([{"role": "system", "content": system}] if system else []) \
            + (st.session_state.chat_history or [{"role": "user", "content": "tu consulta"}])
        show_curl("POST", "/api/chat", {"model": model, "messages": _chat_msgs, "stream": False})

        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        user_msg = st.chat_input("Escribe tu consulta…")
        if user_msg:
            st.session_state.chat_history.append({"role": "user", "content": user_msg})
            with st.chat_message("user"):
                st.write(user_msg)
            messages = ([{"role": "system", "content": system}] if system else []) \
                + st.session_state.chat_history
            with st.chat_message("assistant"):
                with st.spinner("Pensando…"):
                    try:
                        data = get_backend().chat(model, messages)
                        answer = data.get("message", {}).get("content", "")
                        st.write(answer)
                        st.session_state.chat_history.append({"role": "assistant", "content": answer})
                    except OllamaError as exc:
                        show_error(exc)

    # ---- v1/chat/completions ----
    elif sub == "/v1/chat/completions":
        st.caption("Interfaz compatible con la API de OpenAI.")
        model = model_selector("Modelo", key="v1_model")
        prompt = st.text_area("Mensaje (role user)", value="¿Qué es un modelo de IA?", key="v1_prompt")
        show_curl("POST", "/v1/chat/completions",
                  {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False})
        if st.button("Enviar", type="primary", key="v1_btn"):
            with st.spinner("Generando…"):
                try:
                    data = get_backend().v1_chat(model, [{"role": "user", "content": prompt}])
                    choices = data.get("choices", [])
                    if choices:
                        st.markdown("#### Respuesta")
                        st.write(choices[0].get("message", {}).get("content", ""))
                    with st.expander("JSON completo"):
                        st.json(data)
                except OllamaError as exc:
                    show_error(exc)

    # ---- embed ----
    elif sub == "/api/embed":
        st.caption("Requiere un modelo de embeddings (p. ej. nomic-embed-text).")
        model = model_selector("Modelo de embeddings", key="emb_model")
        text = st.text_area("Texto a vectorizar", value="texto de ejemplo", key="emb_text")
        show_curl("POST", "/api/embed", {"model": model, "input": text})
        if st.button("Calcular embedding", type="primary", key="emb_btn"):
            try:
                data = get_backend().embed(model, text)
                embs = data.get("embeddings") or ([data.get("embedding")] if data.get("embedding") else [])
                if embs and embs[0]:
                    vec = embs[0]
                    st.success(f"Vector de dimensión {len(vec)}")
                    st.write("Primeros 10 valores:", [round(v, 5) for v in vec[:10]])
                else:
                    st.warning("El servidor no devolvió embeddings (¿modelo no es de embeddings?).")
                with st.expander("JSON (recortado)"):
                    st.json({k: (v if k not in ("embeddings", "embedding") else "…vector…")
                             for k, v in data.items()})
            except OllamaError as exc:
                show_error(exc)


# ============================================================== MODIFICACIÓN
with tab_mod:
    st.subheader("Modificación — gestión de modelos")
    st.warning("Estas operaciones cambian el estado del servidor Ollama.")
    sub = st.radio("Endpoint", ["/api/pull", "/api/copy", "/api/create", "/api/delete", "/api/blobs/{digest}"],
                   horizontal=True, key="mod_sub")

    if sub == "/api/pull":
        name = st.text_input("Modelo a descargar", value="tinyllama", key="pull_name")
        st.caption("La descarga puede tardar; stream desactivado (respuesta al finalizar).")
        show_curl("POST", "/api/pull", {"model": name, "stream": False})
        if st.button("Descargar (pull)", type="primary", key="pull_btn"):
            with st.spinner("Descargando…"):
                try:
                    st.json(get_backend().pull(name))
                except OllamaError as exc:
                    show_error(exc)

    elif sub == "/api/copy":
        src = model_selector("Origen", key="copy_src")
        dst = st.text_input("Destino", value="llama3.2:3b-copy", key="copy_dst")
        show_curl("POST", "/api/copy", {"source": src, "destination": dst})
        if st.button("Copiar", type="primary", key="copy_btn"):
            try:
                res = get_backend().copy(src, dst)
                st.success(f"Copia realizada (HTTP {res.get('status_code')}).")
                st.json(res)
            except OllamaError as exc:
                show_error(exc)

    elif sub == "/api/create":
        new = st.text_input("Nombre del nuevo modelo", value="mi-llama", key="cr_name")
        base = model_selector("Modelo base (from)", key="cr_from")
        system = st.text_area("System (opcional)", value="Responde siempre en español y sé conciso.",
                              key="cr_system")
        with st.expander("JSON avanzado (opcional, sobrescribe lo anterior)"):
            raw = st.text_area("Cuerpo JSON", value="", key="cr_raw",
                               placeholder='{"model": "mi-llama", "from": "llama3.2:3b", "system": "..."}')
        _cr_body = {"model": new, "from": base}
        if system.strip():
            _cr_body["system"] = system
        show_curl("POST", "/api/create", _cr_body)
        if st.button("Crear modelo", type="primary", key="cr_btn"):
            try:
                if raw.strip():
                    body = json.loads(raw)
                else:
                    body = {"model": new, "from": base}
                    if system.strip():
                        body["system"] = system
                res = get_backend().create(body)
                st.success("Petición enviada.")
                st.json(res)
            except json.JSONDecodeError as e:
                st.error(f"JSON inválido: {e}")
            except OllamaError as exc:
                show_error(exc)

    elif sub == "/api/delete":
        name = model_selector("Modelo a eliminar", key="del_name")
        confirm = st.checkbox(f"Confirmo que quiero eliminar «{name}»", key="del_confirm")
        show_curl("DELETE", "/api/delete", {"model": name})
        if st.button("Eliminar", type="primary", disabled=not confirm, key="del_btn"):
            try:
                res = get_backend().delete(name)
                st.success(f"Eliminado (HTTP {res.get('status_code')}).")
                st.json(res)
            except OllamaError as exc:
                show_error(exc)

    elif sub == "/api/blobs/{digest}":
        st.caption("Comprueba (HEAD) si un blob existe en el servidor.")
        digest = st.text_input("Digest", value="sha256:", key="blob_digest")
        show_curl("HEAD", f"/api/blobs/{digest}", head=True)
        if st.button("Comprobar blob", key="blob_btn"):
            try:
                res = get_backend().blob_exists(digest)
                code = res.get("status_code")
                if code == 200:
                    st.success("El blob existe (HTTP 200).")
                else:
                    st.warning(f"Respuesta HTTP {code}.")
                st.json(res)
            except OllamaError as exc:
                show_error(exc)


# ============================================================== AYUDA
with tab_help:
    st.subheader("Mapa de endpoints")
    st.markdown(
        """
| Categoría | Endpoint | Método | Descripción |
|---|---|---|---|
| **Lectura** | `/api/version` | GET | Versión del servicio |
| | `/api/tags` | GET | Inventario de modelos |
| | `/api/show` | POST | Metadatos detallados |
| | `/api/ps` | GET | Modelos cargados en memoria |
| | `/v1/models` | GET | Inventario vía API compatible |
| **Uso** | `/api/generate` | POST | Inferencia |
| | `/api/chat` | POST | Conversación |
| | `/v1/chat/completions` | POST | Inferencia vía API compatible OpenAI |
| | `/api/embed` | POST | Embeddings |
| **Modificación** | `/api/pull` | POST | Incorporar modelo |
| | `/api/copy` | POST | Crear otra referencia |
| | `/api/create` | POST | Crear modelo derivado |
| | `/api/delete` | DELETE | Eliminar modelo |
| | `/api/blobs/{digest}` | HEAD/GET | Comprobar existencia de un blob |
        """
    )
    st.divider()
    st.markdown("### Swagger (FastAPI)")
    st.markdown(
        "El proyecto incluye un **gateway FastAPI** con documentación Swagger automática. "
        "Arráncalo en paralelo:\n\n"
        "```bash\nuvicorn api:app --reload --port 8000\n```\n\n"
        "y abre **http://localhost:8000/docs** para probar cada endpoint con validación Pydantic. "
        "En cada operación puedes indicar la IP del servidor Ollama en el parámetro `host`."
    )
    st.info(f"Puerto de Ollama fijo: **{OLLAMA_PORT}**. Sin autenticación (uso en laboratorio).")
