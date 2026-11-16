#!/usr/bin/env bash
# Arranca el gateway FastAPI (Swagger en :8000/docs) y la interfaz Streamlit (:8501).
set -e
cd "$(dirname "$0")"

echo "Arrancando gateway FastAPI en http://localhost:8000/docs ..."
uvicorn api:app --port 8000 &
GATEWAY_PID=$!
trap "kill $GATEWAY_PID 2>/dev/null" EXIT

sleep 1
echo "Arrancando interfaz Streamlit en http://localhost:8501 ..."
streamlit run app.py
