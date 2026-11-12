#!/bin/bash
set -euo pipefail

# ==============================================================================
# CONFIGURACIÓN — Edita estas variables antes de ejecutar
# ==============================================================================

GCP_PROJECT="ID del proyecto"              # ID del proyecto en GCP
GCP_REGION="us-central1"                   # Región de Artifact Registry y Cloud Run
AR_REPOSITORY="Nombre del repositorio"     # Nombre del repositorio en Artifact Registry
IMAGE_NAME="03-mcp-server"                 # Nombre de la imagen
CLOUD_RUN_SERVICE="03-mcp-server-service"  # Nombre del servicio en Cloud Run
CLOUD_RUN_PORT=8080                        # Puerto que expone el contenedor
ENV_FILE="../.env"                         # Archivo de variables de entorno (directorio raíz del proyecto)
RUNTIME_SERVICE_ACCOUNT=""                 # Email de la SA de runtime (ver DEPLOYMENT.md). Vacío = usa la SA por defecto de Cloud Run.

# ==============================================================================
# PRIMERA VEZ: autenticar Docker con Artifact Registry
# Descomenta la siguiente línea si es la primera vez que usas este repositorio
# ==============================================================================
# gcloud auth configure-docker "${GCP_REGION}-docker.pkg.dev" --quiet

# ==============================================================================
# NO EDITAR DESDE AQUÍ
# ==============================================================================

# Tag único basado en fecha y hora: YYYYMMDD-HHmmss
IMAGE_TAG=$(date +"%Y%m%d-%H%M%S")
AR_HOSTNAME="${GCP_REGION}-docker.pkg.dev"
FULL_IMAGE="${AR_HOSTNAME}/${GCP_PROJECT}/${AR_REPOSITORY}/${IMAGE_NAME}:${IMAGE_TAG}"

echo "============================================================"
echo "  BUILD & DEPLOY — 03_mcp_server → Cloud Run"
echo "============================================================"
echo "  Proyecto  : ${GCP_PROJECT}"
echo "  Región    : ${GCP_REGION}"
echo "  Imagen    : ${FULL_IMAGE}"
echo "  Servicio  : ${CLOUD_RUN_SERVICE}"
echo "============================================================"

# 1. Configurar proyecto activo en gcloud
echo ""
echo "[1/4] Configurando proyecto GCP..."
gcloud config set project "${GCP_PROJECT}"

# 2. Construir imagen Docker
echo ""
echo "[2/4] Construyendo imagen Docker..."
docker build -t "${FULL_IMAGE}" ..

# 3. Subir imagen a Artifact Registry
echo ""
echo "[3/4] Subiendo imagen a Artifact Registry..."
docker push "${FULL_IMAGE}"

# 4. Leer .env y construir el argumento --set-env-vars para Cloud Run
echo ""
echo "[4/4] Desplegando en Cloud Run..."

if [ ! -f "${ENV_FILE}" ]; then
  echo "ERROR: No se encontró el archivo ${ENV_FILE}"
  exit 1
fi

ENV_VARS=$(grep -v '^\s*#' "${ENV_FILE}" | grep -v '^\s*$' | tr '\n' ',' | sed 's/,$//')

# --no-allow-unauthenticated: este servicio queda privado — solo 02_agent_api
# (con la SA compartida, roles/run.invoker sobre este servicio) puede
# invocarlo, autenticándose con un ID token de Google. Ver DEPLOYMENT.md.
DEPLOY_ARGS=(
  --image "${FULL_IMAGE}"
  --region "${GCP_REGION}"
  --platform managed
  --no-allow-unauthenticated
  --port "${CLOUD_RUN_PORT}"
)
if [ -n "${ENV_VARS}" ]; then
  DEPLOY_ARGS+=(--set-env-vars "${ENV_VARS}")
fi
if [ -n "${RUNTIME_SERVICE_ACCOUNT}" ]; then
  DEPLOY_ARGS+=(--service-account "${RUNTIME_SERVICE_ACCOUNT}")
fi

gcloud run deploy "${CLOUD_RUN_SERVICE}" "${DEPLOY_ARGS[@]}"

echo ""
echo "============================================================"
echo "  ✅ Despliegue completado exitosamente"
echo "  Imagen : ${FULL_IMAGE}"
echo "============================================================"
