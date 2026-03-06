#!/usr/bin/env bash
# Production deploy: build, start stack, run DB migrations.
# Run from repo root: ./scripts/deploy-prod.sh

set -e
cd "$(dirname "$0")/.."

echo "==> Building and starting production stack..."
docker-compose up -d --build

echo "==> Waiting for API to be healthy..."
for i in {1..30}; do
  if docker-compose exec -T api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" 2>/dev/null; then
    echo "    API is up."
    break
  fi
  if [[ $i -eq 30 ]]; then
    echo "    Timeout waiting for API. Check: docker-compose logs api"
    exit 1
  fi
  sleep 2
done

echo "==> Running database migrations..."
docker-compose exec -T api alembic upgrade head

echo "==> Done. App is at http://localhost (port 80)."
echo "    Logs: docker-compose logs -f"
