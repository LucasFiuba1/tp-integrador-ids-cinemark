#!/usr/bin/env bash
# Instala las dependencias del proyecto y prepara la configuración local.
# Uso: bash init.sh            -> crea el entorno virtual e instala dependencias
#      bash init.sh --db       -> además crea la base y carga los datos iniciales
set -e

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Creando entorno virtual en .venv..."
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
echo "Instalando dependencias..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Se creó .env a partir de .env.example. Completá tus credenciales."
fi

if [ "$1" == "--db" ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
  echo "Creando la base ${DB_NAME} y cargando datos iniciales..."
  mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASSWORD" < src/backend/db/schema.sql
  mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASSWORD" < src/backend/db/seed.sql
fi

echo ""
echo "Listo. Para levantar las aplicaciones (en dos terminales):"
echo "  source .venv/bin/activate && flask --app src.backend.app run --port 5000 --debug"
echo "  source .venv/bin/activate && flask --app src.frontend.app run --port 5001 --debug"
