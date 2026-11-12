#Requires -Version 5.1
<#
.SYNOPSIS
    Construye, sube y despliega la imagen Docker de 02_agent_api en GCP Cloud Run.

.DESCRIPTION
    1. Configura el proyecto GCP activo.
    2. Construye la imagen Docker con un tag basado en fecha/hora.
    3. Sube la imagen a Artifact Registry.
    4. Lee el archivo .env y despliega el servicio en Cloud Run.

    Nota: se excluye GOOGLE_APPLICATION_CREDENTIALS del .env al desplegar —
    es una ruta local a un JSON de credenciales que no existe dentro del
    contenedor. En Cloud Run, Model Armor debe autenticarse con la cuenta de
    servicio adjunta al servicio (--service-account más abajo), no con esta
    variable.

.EXAMPLE
    .\build-deploy.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ==============================================================================
# CONFIGURACIÓN — Edita estas variables antes de ejecutar
# ==============================================================================

$GCP_PROJECT        = "ID del proyecto"            # ID del proyecto en GCP
$GCP_REGION         = "us-central1"                # Región de Artifact Registry y Cloud Run
$AR_REPOSITORY      = "Nombre del repositorio"     # Nombre del repositorio en Artifact Registry
$IMAGE_NAME         = "02-agent-api"               # Nombre de la imagen
$CLOUD_RUN_SERVICE  = "02-agent-api-service"       # Nombre del servicio en Cloud Run
$CLOUD_RUN_PORT     = 8080                         # Puerto que expone el contenedor
$ENV_FILE           = "../.env"                    # Archivo de variables de entorno (directorio raíz del proyecto)
$RUNTIME_SERVICE_ACCOUNT = ""                       # Email de la SA de runtime (ver DEPLOYMENT.md, Fase 1). Vacío = usa la SA por defecto de Cloud Run.

# ==============================================================================
# PRIMERA VEZ: autenticar Docker con Artifact Registry
# Descomenta la siguiente línea si es la primera vez que usas este repositorio
# ==============================================================================
# gcloud auth configure-docker "$GCP_REGION-docker.pkg.dev" --quiet

# ==============================================================================
# NO EDITAR DESDE AQUÍ
# ==============================================================================

# Tag único basado en fecha y hora: YYYYMMDD-HHmmss
$IMAGE_TAG   = (Get-Date -Format "yyyyMMdd-HHmmss")
$AR_HOSTNAME = "$GCP_REGION-docker.pkg.dev"
$FULL_IMAGE  = "$AR_HOSTNAME/$GCP_PROJECT/$AR_REPOSITORY/${IMAGE_NAME}:$IMAGE_TAG"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  BUILD & DEPLOY — 02_agent_api -> Cloud Run" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Proyecto  : $GCP_PROJECT"
Write-Host "  Region    : $GCP_REGION"
Write-Host "  Imagen    : $FULL_IMAGE"
Write-Host "  Servicio  : $CLOUD_RUN_SERVICE"
Write-Host "============================================================" -ForegroundColor Cyan

# ── 1. Configurar proyecto activo en gcloud ──────────────────────────────────
Write-Host ""
Write-Host "[1/4] Configurando proyecto GCP..." -ForegroundColor Yellow
gcloud config set project $GCP_PROJECT
if ($LASTEXITCODE -ne 0) { throw "ERROR: gcloud config set project falló." }

# ── 2. Construir imagen Docker ───────────────────────────────────────────────
Write-Host ""
Write-Host "[2/4] Construyendo imagen Docker..." -ForegroundColor Yellow
docker build -t $FULL_IMAGE ..
if ($LASTEXITCODE -ne 0) { throw "ERROR: docker build falló." }

# ── 3. Subir imagen a Artifact Registry ──────────────────────────────────────
Write-Host ""
Write-Host "[3/4] Subiendo imagen a Artifact Registry..." -ForegroundColor Yellow
docker push $FULL_IMAGE
if ($LASTEXITCODE -ne 0) { throw "ERROR: docker push falló." }

# ── 4. Leer .env y desplegar en Cloud Run ────────────────────────────────────
Write-Host ""
Write-Host "[4/4] Desplegando en Cloud Run..." -ForegroundColor Yellow

if (-not (Test-Path $ENV_FILE)) {
    throw "ERROR: No se encontró el archivo '$ENV_FILE'."
}

# Lee el .env, ignora comentarios (#), líneas vacías y GOOGLE_APPLICATION_CREDENTIALS
# (ver nota al inicio del script) — construye KEY=VALUE,...
$envVars = Get-Content $ENV_FILE |
    Where-Object { $_ -notmatch '^\s*#' -and $_ -notmatch '^\s*$' -and $_ -notmatch '^GOOGLE_APPLICATION_CREDENTIALS=' } |
    ForEach-Object { $_.Trim() }

if ($envVars.Count -eq 0) {
    throw "ERROR: El archivo '$ENV_FILE' no contiene variables válidas."
}

$envVarsString = $envVars -join ","

# --no-allow-unauthenticated: este servicio queda SOLO detrás del API Gateway
# (ver DEPLOYMENT.md) — nadie debe poder invocar el Cloud Run directo,
# saltándose la validación de Firebase del Gateway. Si todavía no armaste el
# Gateway y necesitas probar contra Cloud Run directo, usa
# --allow-unauthenticated temporalmente.
$deployArgs = @(
    "--image", $FULL_IMAGE,
    "--region", $GCP_REGION,
    "--platform", "managed",
    "--no-allow-unauthenticated",
    "--port", $CLOUD_RUN_PORT,
    "--set-env-vars", $envVarsString
)
if ($RUNTIME_SERVICE_ACCOUNT) {
    $deployArgs += @("--service-account", $RUNTIME_SERVICE_ACCOUNT)
}

gcloud run deploy $CLOUD_RUN_SERVICE @deployArgs

if ($LASTEXITCODE -ne 0) { throw "ERROR: gcloud run deploy falló." }

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  Despliegue completado exitosamente" -ForegroundColor Green
Write-Host "  Imagen : $FULL_IMAGE" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
