FROM python:3.10-slim

ENV PYTHONUNBUFFERED True

ENV APP_HOME /app
WORKDIR $APP_HOME

COPY . .

# Actualiza pip y setuptools
RUN pip install -U pip
RUN pip install -U setuptools

# Instala las dependencias desde requirements.txt, asegurándote de que psycopg2 sea reemplazado por psycopg2-binary
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8090

# CMD que ejecuta el script principal
CMD ["python","-m", "src.main"]