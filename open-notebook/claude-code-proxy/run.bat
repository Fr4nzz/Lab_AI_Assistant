@echo off
REM Start Claude Code Proxy Server (Windows)
REM This runs locally to use your authenticated Claude Code installation

echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Starting Claude Code Proxy on http://localhost:8080
echo.
echo Use this in Open Notebook:
echo   OPENAI_COMPATIBLE_BASE_URL_LLM=http://host.docker.internal:8080/v1
echo   OPENAI_COMPATIBLE_API_KEY_LLM=dummy-key
echo.

python server.py
