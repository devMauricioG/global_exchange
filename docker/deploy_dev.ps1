# Despliegue local reproducible con datos demo (SCRUM-124).
[CmdletBinding()]
param(
    [int]$HealthcheckAttempts = 30
)

$ErrorActionPreference = 'Stop'

function Wait-ServiceHealth([string]$Service) {
    for ($attempt = 1; $attempt -le $HealthcheckAttempts; $attempt++) {
        $container = (docker compose ps -q $Service).Trim()
        if ($container) {
            $status = (docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' $container).Trim()
            if ($status -in @('healthy', 'running')) { return }
        }
        Start-Sleep -Seconds 2
    }
    docker compose logs --tail 100 $Service
    throw "El servicio $Service no quedó saludable."
}

Write-Host '==> Construyendo e iniciando servicios de desarrollo'
docker compose up -d --build
Wait-ServiceHealth 'db'
Wait-ServiceHealth 'mailpit'
Wait-ServiceHealth 'keycloak'

Write-Host '==> Aplicando migraciones y cargando datos demo'
docker compose exec -T web python manage.py migrate --noinput
docker compose exec -T web python manage.py seed_data

Write-Host '==> Verificando aplicación y servicios'
docker compose exec -T web python manage.py check
Wait-ServiceHealth 'web'
Write-Host 'Despliegue de desarrollo completado: http://localhost:8000'
