FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

# docker run --name agente_simple -p 8080:8080 --env-file .env <image>
CMD ["python", "-m", "src.main"]
