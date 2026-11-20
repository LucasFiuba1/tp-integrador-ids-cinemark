# Imagen única para las dos apps Flask (API y sitio): docker-compose.yml elige cuál arrancar con `command`.
FROM python:3.12.12-slim

# tzdata: Python (datetime.now) y MySQL (NOW) tienen que estar en la misma zona horaria
# para comparar bien funciones futuras, reservas vencidas y plazos de cancelación.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=America/Argentina/Buenos_Aires \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Primero las dependencias: si solo cambia el código, Docker reutiliza esta capa.
COPY requirements.txt requirements-deploy.txt ./
RUN pip install --no-cache-dir -r requirements-deploy.txt

COPY src ./src
