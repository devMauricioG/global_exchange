#!/usr/bin/env bash
# Despliegue local reproducible con datos demo (SCRUM-124).
set -euo pipefail

COMPOSE=(docker compose)
MAX_ATTEMPTS="${HEALTHCHECK_ATTEMPTS:-30}"

wait_for_health() {
  local service="$1" attempt=1 container status
  container="$(${COMPOSE[@]} ps -q "$service")"
  until [ -n "$container" ] && status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container")" && [ "$status" = "healthy" -o "$status" = "running" ]; do
    if [ "$attempt" -ge "$MAX_ATTEMPTS" ]; then
      echo "El servicio $service no quedó saludable (estado: ${status:-no creado})." >&2
      ${COMPOSE[@]} logs --tail=100 "$service" >&2
      exit 1
    fi
    sleep 2
    attempt=$((attempt + 1))
    container="$(${COMPOSE[@]} ps -q "$service")"
  done
}

echo '==> Construyendo e iniciando servicios de desarrollo'
${COMPOSE[@]} up -d --build
wait_for_health db
wait_for_health mailpit
wait_for_health keycloak

echo '==> Aplicando migraciones y cargando datos demo'
${COMPOSE[@]} exec -T web python manage.py migrate --noinput
${COMPOSE[@]} exec -T web python manage.py seed_data

echo '==> Verificando aplicación y servicios'
${COMPOSE[@]} exec -T web python manage.py check
wait_for_health web
echo 'Despliegue de desarrollo completado: http://localhost:8000'
