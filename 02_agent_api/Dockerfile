FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Modelo spaCy usado por Presidio (Capa 5 del InputGuardrail) para NER en español.
RUN python -m spacy download es_core_news_sm

COPY . .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
# 03_mcp_server ya no va bundleado acá: es su propio servicio Cloud Run,
# 02_agent_api se conecta por HTTP (ver DEMO_MCP_SERVER_URL en
# src/utils/environment.py y DEPLOYMENT.md).

EXPOSE 8080

# docker run --name agente_simple -p 8080:8080 --env-file .env <image>
CMD ["python", "-m", "src.main"]
