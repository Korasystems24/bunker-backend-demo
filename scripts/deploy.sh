#!/usr/bin/env bash
# Запускается на сервере (из GitHub Action или вручную из клона).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "Нет $ROOT/.env — скопируйте .env.example и заполните секреты." >&2
  exit 1
fi

echo "[deploy] docker compose up --build"
docker compose up -d --build

echo "[deploy] жду /readyz"
ok=0
for _ in $(seq 1 40); do
  if docker compose exec -T api python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/readyz', timeout=2)" \
    2>/dev/null; then
    ok=1
    break
  fi
  sleep 3
done
if [[ "$ok" -ne 1 ]]; then
  echo "[deploy] api не ответил на /readyz" >&2
  docker compose logs --tail=80 api
  exit 1
fi

echo "[deploy] справочник бункеров"
docker compose exec -T api python scripts/seed_catalog.py

curl -fsS http://127.0.0.1:8000/readyz
echo
echo "[deploy] готово"
