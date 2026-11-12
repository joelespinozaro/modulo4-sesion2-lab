FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

# Cloud Run inyecta PORT (ver src/utils/environment.py); en local, PORT=8000
# por defecto. docker run --name demo_mcp_server -p 8080:8080 -e PORT=8080 --env-file .env <image>
CMD ["python", "-m", "src.main"]
