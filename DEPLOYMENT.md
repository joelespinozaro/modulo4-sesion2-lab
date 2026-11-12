# Despliegue en GCP — 03_mcp_server + 02_agent_api + 01_agent-app + API Gateway + Model Armor

Guía paso a paso para desplegar los 3 componentes de este proyecto que sirven al usuario final, con el frontend hablando **solo** con un API Gateway de GCP (nunca directo a la API), `02_agent_api` hablando con `03_mcp_server` por HTTP autenticado con IAM (nunca como subproceso local), y GCP Model Armor como motor de content-safety.

```
                    ┌─────────────────────┐
  Usuario ────────► │  01_agent-app        │  (Next.js, Cloud Run)
                    │  (Identity Platform) │
                    └──────────┬───────────┘
                               │ HTTPS + Bearer <Identity Platform ID token>
                               ▼
                    ┌─────────────────────┐
                    │  GCP API Gateway     │  valida el JWT de Identity Platform
                    │  (openapi_gateway.yml)│ ANTES de reenviar la petición
                    └──────────┬───────────┘
                               │ solo el Gateway puede invocar
                               │ (Cloud Run --no-allow-unauthenticated)
                               ▼
                    ┌─────────────────────┐      ┌─────────────────────┐
                    │  02_agent_api         │◄────►│  GCP Model Armor    │
                    │  (FastAPI, Cloud Run) │      │  (sanitize_*)       │
                    └──────────┬───────────┘      └─────────────────────┘
                               │ HTTPS + Bearer <ID token de Google>
                               │ (misma SA, roles/run.invoker sobre este servicio)
                               ▼
                    ┌─────────────────────┐
                    │  03_mcp_server        │  (FastMCP streamable-http,
                    │  (Cloud Run, privado) │   Cloud Run --no-allow-unauthenticated)
                    └─────────────────────┘
```

**Por qué `02_agent_api` y `03_mcp_server` son dos Cloud Run separados, no uno bundleado**: `03_mcp_server` corre por transporte **streamable-http** (`mcp.run(transport="streamable-http")`, ver `03_mcp_server/src/main.py`) — un servicio HTTP normal. `02_agent_api` se conecta como cliente (`src/services/tools.py::load_demo_mcp_tools()`, vía `langchain_mcp_adapters.MultiServerMCPClient` con `transport: "streamable_http"`), autenticándose con un **ID token de Google** obtenido dinámicamente (`src/utils/gcp_auth.py::GoogleIDTokenAuth`, refrescado antes de expirar — un ID token dura ~1h y la conexión puede vivir más que eso). Como ambos servicios están en el mismo proyecto GCP, alcanza con IAM: la Service Account compartida (`$SERVICE_SA`) necesita `roles/run.invoker` sobre el Cloud Run de `03_mcp_server` — mismo patrón que ya usa Gateway→agent-api, un nivel más adentro.

**Orden de esta guía**: primero se habilita/crea TODO lo que no depende de que un Cloud Run ya exista (APIs, la Service Account única y sus permisos, el template de Model Armor). Después, `03_mcp_server` se despliega **antes** que `02_agent_api`, porque este último necesita su URL (`DEMO_MCP_SERVER_URL`) en el `.env` antes de desplegarse. La única excepción inevitable en el otorgamiento de permisos: `roles/run.invoker` sobre un Cloud Run específico solo puede otorgarse **después** de que ese Cloud Run exista (IAM no permite un rol sobre un recurso que no existe) — por eso aparece al final de las Fases 2 y 3, no antes.

---

## Prerrequisitos

Antes de ejecutar la guía necesitas:

- Un proyecto GCP con **facturación habilitada** y permisos para habilitar APIs, crear repositorios de Artifact Registry, Service Accounts, bindings IAM, servicios Cloud Run, recursos de API Gateway y templates de Model Armor.
- `gcloud` autenticado (`gcloud auth login`). La ruta recomendada es **Bash o Google Cloud Shell**, porque el render del OpenAPI usa `envsubst`. En Windows, los despliegues de los servicios también incluyen scripts `.ps1` y `.bat`, pero la creación de recursos de esta guía está expresada en Bash/Cloud Shell.
- **No hace falta Docker instalado ni corriendo**: las tres imágenes se construyen con `gcloud builds submit` (Cloud Build, en la nube) — más robusto que build+push local, porque no depende de que Docker Desktop esté corriendo y evita el clásico problema de construir una imagen `arm64`/`Windows` que después falla en Cloud Run (que exige `linux/amd64`). Cloud Build queda habilitado en la Fase 1.1.
- Identity Platform habilitado en el proyecto y al menos un proveedor de identidad configurado. La Fase 1 incluye la inicialización de Identity Platform; por claridad didáctica, la activación del proveedor y la creación del usuario de laboratorio se hacen desde Google Cloud Console.
- Los servicios externos y secretos indicados en `02_agent_api/.env.example` y `03_mcp_server/.env.example`: PostgreSQL, OpenAI y Groq para Agent API; OpenAI, Qdrant y SuperheroAPI para las herramientas MCP que los utilizan. Neon y LangSmith son opcionales. No reemplaces los ejemplos `sk-...`, `gsk_...` o `your-...` por valores ficticios en producción.

> Esta guía almacena API keys y credenciales en **Secret Manager**. Cloud Run recibe referencias a secretos, no sus valores como variables planas ni argumentos visibles.

> Ejecuta todos los bloques desde la **raíz del repositorio** `demo_rag_agent`, salvo cuando el propio bloque incluya un `cd`. Si cierras Cloud Shell, vuelve a ejecutar la Fase 0 para recuperar las variables de la sesión.

---

## 0. Variables (definir una sola vez, reusadas en todas las fases)

**Bash:**
```bash
export PROJECT_ID="tu-proyecto-gcp"
export REGION="us-central1"
export AR_REPOSITORY="repo"

# Principal que ejecuta los comandos y adjuntará SERVICE_SA a Cloud Run/API
# Gateway. Si gcloud usa una cuenta humana, este valor se obtiene así:
export DEPLOYER_ACCOUNT="$(gcloud config get-value account)"
export DEPLOYER_MEMBER="user:${DEPLOYER_ACCOUNT}"
# Si despliegas desde otra SA, usa en cambio:
# export DEPLOYER_MEMBER="serviceAccount:mi-deployer@${PROJECT_ID}.iam.gserviceaccount.com"

# Service Account única — identidad de runtime de 02_agent_api (llama a Model
# Armor y a 03_mcp_server) Y también la que usa el Gateway para invocar
# 02_agent_api (ver Fase 1.4)
export SERVICE_SA_NAME="agent-b-runtime"
export SERVICE_SA="${SERVICE_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# Model Armor
export MODEL_ARMOR_TEMPLATE_ID="agent-api-template"

# 03_mcp_server (Cloud Run)
export MCP_SERVER_SERVICE="mcp-server-service"

# 02_agent_api (Cloud Run)
export AGENT_API_SERVICE="agent-api-service"

# API Gateway
export GATEWAY_API_ID="agent-api-gw"
export GATEWAY_CONFIG_ID="agent-api-gw-config-v1"
export GATEWAY_ID="agent-api-gateway"

# Identity Platform. El frontend usa el SDK web de Firebase porque es el SDK
# cliente oficial compatible con Identity Platform; la autenticación y los
# usuarios pertenecen a Identity Platform de GCP.
export IDENTITY_PLATFORM_PROJECT_ID="${PROJECT_ID}"
export IDENTITY_PLATFORM_API_KEY="PEGA_AQUI_LA_API_KEY_WEB"
export IDENTITY_PLATFORM_AUTH_DOMAIN="${PROJECT_ID}.firebaseapp.com"

# 01_agent-app (Cloud Run)
export AGENT_APP_SERVICE="agent-app-service"
```

**PowerShell:**
```powershell
$PROJECT_ID = "tu-proyecto-gcp"
$REGION = "us-central1"
$AR_REPOSITORY = "repo"
$DEPLOYER_ACCOUNT = gcloud config get-value account
$DEPLOYER_MEMBER = "user:$DEPLOYER_ACCOUNT" # usa serviceAccount:... si corresponde
$SERVICE_SA_NAME = "agent-b-runtime"
$SERVICE_SA = "$SERVICE_SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
$MODEL_ARMOR_TEMPLATE_ID = "agent-api-template"
$MCP_SERVER_SERVICE = "mcp-server-service"
$AGENT_API_SERVICE = "agent-api-service"
$GATEWAY_API_ID = "agent-api-gw"
$GATEWAY_CONFIG_ID = "agent-api-gw-config-v1"
$GATEWAY_ID = "agent-api-gateway"
$IDENTITY_PLATFORM_PROJECT_ID = $PROJECT_ID
$IDENTITY_PLATFORM_API_KEY = "PEGA_AQUI_LA_API_KEY_WEB"
$IDENTITY_PLATFORM_AUTH_DOMAIN = "$PROJECT_ID.firebaseapp.com"
$AGENT_APP_SERVICE = "agent-app-service"
```

> Los nombres de Cloud Run deben comenzar con una letra. Los nombres de las carpetas (`01_`, `02_`, `03_`) no se pueden reutilizar literalmente como nombres de servicio.

---

## Fase 1 — Preparar servicios, Artifact Registry, IAM y Model Armor

Todo lo de esta fase es independiente de que exista ningún Cloud Run — se hace una sola vez, de entrada.

### 1.1. Seleccionar el proyecto y habilitar APIs

```bash
gcloud config set project "$PROJECT_ID"

gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  apigateway.googleapis.com \
  servicemanagement.googleapis.com \
  servicecontrol.googleapis.com \
  modelarmor.googleapis.com \
  iam.googleapis.com \
  identitytoolkit.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com

# Esperar a que la habilitación termine antes de crear los recursos siguientes.
gcloud services list --enabled --project="$PROJECT_ID"
```

Las tres imágenes de esta guía (`03_mcp_server`, `02_agent_api`, `01_agent-app`) se construyen con **Cloud Build** (`gcloud builds submit`, ver Fases 2.2, 3.2 y 5) en vez de `docker build` + `docker push` local — por eso `cloudbuild.googleapis.com` está en la lista. En proyectos nuevos, la Service Account por defecto de Cloud Build ya no recibe el rol `Editor` automáticamente, así que necesita permiso explícito para subir imágenes a Artifact Registry:

```bash
export PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"
```

> Si tu proyecto es de los que sí heredó el rol `Editor` en la SA de Cloud Build, este comando no rompe nada — solo agrega un rol que ya tenías cubierto.

### 1.2. Inicializar Identity Platform

Este bloque activa Identity Platform en el proyecto. Si ya estaba inicializado, una respuesta indicando que la configuración existe se puede ignorar.

```bash
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -H "X-Goog-User-Project: ${PROJECT_ID}" \
  -d '{}' \
  "https://identitytoolkit.googleapis.com/v2/projects/${PROJECT_ID}/identityPlatform:initializeAuth"
```

> Cada alumno despliega **su propio proyecto GCP** de punta a punta (su propio Identity Platform, su propio Gateway, sus propios Cloud Run) — no es un backend compartido entre alumnos. Por eso alcanza con **una sola cuenta de prueba** por despliegue: el frontend de `01_agent-app` solo tiene login (`signInWithEmailAndPassword`, ver `app/_lib/auth-context.tsx`), no un flujo de registro — así que esa cuenta hay que crearla a mano en este paso, dentro de tu propio proyecto.

Ahora realiza estos tres pasos en **Google Cloud Console → Identity Platform**:

1. En **Providers**, habilita Email/Password.
2. En **Users**, crea **una** cuenta de prueba (ej. `test@correo.com` con una password a elección) — es la única credencial con la que vas a loguearte en tu propio despliegue; no hace falta una por alumno porque cada uno tiene su propio proyecto.
3. En la configuración de la aplicación web, copia la **API key** y colócala en `IDENTITY_PLATFORM_API_KEY` de la Fase 0. Para el laboratorio se usa `IDENTITY_PLATFORM_AUTH_DOMAIN=${PROJECT_ID}.firebaseapp.com`.

> Aunque el paquete del frontend y sus variables se llaman `firebase`/`NEXT_PUBLIC_FIREBASE_*`, no se está usando Firebase Authentication como producto separado. Identity Platform utiliza ese SDK cliente y emite tokens con issuer `https://securetoken.google.com/$PROJECT_ID`, que API Gateway valida.

### 1.3. Crear el repositorio Docker

Artifact Registry no crea el repositorio automáticamente durante el primer build. En un proyecto nuevo hay que crearlo primero:

```bash
gcloud artifacts repositories create "$AR_REPOSITORY" \
  --project="$PROJECT_ID" \
  --repository-format=docker \
  --location="$REGION" \
  --description="Imágenes de demo_rag_agent"
```

Si el repositorio ya existe, omite el comando `repositories create` y conserva el mismo nombre y región en todos los scripts. No hace falta `gcloud auth configure-docker` — eso solo es necesario para hacer `docker push` desde tu Docker local, y esta guía construye y sube las imágenes con Cloud Build (Fases 2.2, 3.2 y 5), no con tu Docker.

### 1.4. Crear la Service Account única y darle los permisos que ya se pueden otorgar

Esta SA cumple tres roles: identidad de runtime de `02_agent_api` (para llamar a Model Armor y para autenticarse contra `03_mcp_server`), y la identidad que usa el **Gateway** para invocar `02_agent_api`. Todo lo que no depende de que un Cloud Run exista se le da acá:

```bash
gcloud iam service-accounts create "$SERVICE_SA_NAME" \
  --display-name="Runtime de 02_agent_api + backend-auth del Gateway"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SERVICE_SA}" \
  --role="roles/modelarmor.user"

# El principal que ejecuta gcloud necesita iam.serviceAccounts.actAs para
# adjuntar esta SA a los Cloud Run y al API config del Gateway.
gcloud iam service-accounts add-iam-policy-binding "$SERVICE_SA" \
  --project="$PROJECT_ID" \
  --member="$DEPLOYER_MEMBER" \
  --role="roles/iam.serviceAccountUser"

# El usuario que ejecuta el laboratorio crea y administra el template.
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="$DEPLOYER_MEMBER" \
  --role="roles/modelarmor.admin"
```

> `roles/run.invoker` (sobre `03_mcp_server` y sobre `02_agent_api`) se agrega en las Fases 2.3 y 3.3, apenas cada servicio exista — no se puede otorgar antes.

### 1.5. Crear el template de Model Armor

```bash
# Las operaciones sobre templates requieren el endpoint regional. Sin esta
# línea, el endpoint global puede devolver un 403 engañoso aunque IAM esté bien.
gcloud config set api_endpoint_overrides/modelarmor \
  "https://modelarmor.${REGION}.rep.googleapis.com/"

gcloud model-armor templates create "$MODEL_ARMOR_TEMPLATE_ID" \
  --project="$PROJECT_ID" \
  --location="$REGION" \
  --rai-settings-filters='[
    {"filterType": "HATE_SPEECH", "confidenceLevel": "MEDIUM_AND_ABOVE"},
    {"filterType": "HARASSMENT", "confidenceLevel": "MEDIUM_AND_ABOVE"},
    {"filterType": "SEXUALLY_EXPLICIT", "confidenceLevel": "MEDIUM_AND_ABOVE"},
    {"filterType": "DANGEROUS", "confidenceLevel": "MEDIUM_AND_ABOVE"}
  ]' \
  --basic-config-filter-enforcement=enabled \
  --pi-and-jailbreak-filter-settings-enforcement=enabled \
  --pi-and-jailbreak-filter-settings-confidence-level=HIGH \
  --malicious-uri-filter-settings-enforcement=enabled
```

Esto habilita: RAI (contenido dañino), prompt injection/jailbreak, URLs maliciosas, y SDP (datos sensibles) en modo **básico** — detecta y bloquea, pero **no enmascara** (no genera `deidentify_result`).

`02_agent_api/src/services/guardrails/layer_model_armor.py` ya sabe leer `deidentify_result` para enmascarar en vez de bloquear (igual criterio que la Capa 5 local de PII) — pero eso requiere el modo **avanzado** de SDP:

<details>
<summary>Opcional/avanzado — SDP con enmascarado real (Cloud DLP)</summary>

El modo básico de arriba solo detecta y bloquea. Para que el filtro `sdp` devuelva texto enmascarado en vez de bloquear, hay que:
1. Crear un **inspect template** y un **deidentify template** en Cloud DLP (Sensitive Data Protection) — fuera del alcance de esta guía, son recursos propios con su propia configuración de info-types y transformaciones.
2. Referenciarlos al crear el template de Model Armor con `--advanced-config-inspect-template=projects/$PROJECT_ID/locations/$REGION/inspectTemplates/TU_INSPECT_TEMPLATE` y `--advanced-config-deidentify-template=projects/$PROJECT_ID/locations/$REGION/deidentifyTemplates/TU_DEIDENTIFY_TEMPLATE`, en vez de `--basic-config-filter-enforcement=enabled`.

Sin esto, el filtro `sdp` en modo básico igual bloquea datos sensibles detectados (vía `_extract_deidentified_text` → sin `deidentify_result` disponible → cae a bloqueo) — solo no los deja pasar enmascarados.
</details>

Con esto termina la Fase 1: ya están habilitadas las APIs, existe el repositorio Docker, y tenemos la SA, sus permisos de Model Armor y el template.

---

## Fase 2 — Desplegar 03_mcp_server

Va primero porque `02_agent_api` necesita su URL antes de poder desplegarse.

### 2.1. Completar tu `.env` de `03_mcp_server`

Crea el archivo a partir del ejemplo y reemplaza los valores marcados:

```bash
cp 03_mcp_server/.env.example 03_mcp_server/.env
nano 03_mcp_server/.env
```

Completa Qdrant, SuperheroAPI y OpenAI para embeddings de `retrieve_documents`. No necesita ninguna variable nueva para el transporte HTTP — Cloud Run inyecta `PORT` automáticamente (`src/utils/environment.py::MCP_SERVER_PORT`). Guarda con `Ctrl+O`, Enter y sal de `nano` con `Ctrl+X`.

### 2.2. Build + deploy

```bash
export IMAGE_TAG="$(date +'%Y%m%d-%H%M%S')"
export MCP_SERVER_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPOSITORY}/03-mcp-server:${IMAGE_TAG}"

gcloud builds submit 03_mcp_server \
  --project="$PROJECT_ID" \
  --tag="$MCP_SERVER_IMAGE"

export MCP_ENV_VARS="$(grep -vE '^\s*(#|$)' 03_mcp_server/.env | paste -sd, -)"

gcloud run deploy "$MCP_SERVER_SERVICE" \
  --project="$PROJECT_ID" \
  --image="$MCP_SERVER_IMAGE" \
  --region="$REGION" \
  --platform=managed \
  --no-allow-unauthenticated \
  --service-account="$SERVICE_SA" \
  --port=8080 \
  --cpu=2 \
  --memory=4Gi \
  --set-env-vars="$MCP_ENV_VARS"
```

Despliega con `--no-allow-unauthenticated` — nadie fuera de `02_agent_api` (con la SA + `run.invoker` del siguiente paso) puede invocarlo.

### 2.3. Obtener su URL y darle a la SA permiso sobre este Cloud Run

```bash
export MCP_SERVER_URL=$(gcloud run services describe "$MCP_SERVER_SERVICE" \
  --region="$REGION" --format="value(status.url)")
echo "$MCP_SERVER_URL"

gcloud run services add-iam-policy-binding "$MCP_SERVER_SERVICE" \
  --region="$REGION" \
  --member="serviceAccount:${SERVICE_SA}" \
  --role="roles/run.invoker"
```

La URL completa que usará `02_agent_api` es `${MCP_SERVER_URL}/mcp` (endpoint streamable-http de FastMCP, **sin** barra final — ver nota debajo).

> **`03_mcp_server/requirements.txt` fija `mcp[cli]>=1.13.0,<2` a propósito** (no uses `mcp[cli]==1.8.0`, una versión vieja que no propaga `structuredContent` correctamente hacia `langchain-mcp-adapters` en `02_agent_api` — con ella, `retrieve_documents` y tools como `get_pokemon` responden bien pero el campo `sources` de `/api/chat` queda vacío o con el JSON crudo en `content`). Tampoco subas a `mcp[cli]>=2`: es un major con breaking changes (`FastMCP` se renombró a `MCPServer`) que ni siquiera arranca contra este código.
>
> **Por qué la URL va sin barra final con esta versión** (al revés de lo que podrías esperar): el endpoint registrado por FastMCP es `/mcp` (sin slash). Pedir `/mcp/` (con slash) devuelve un `307` cuyo header `Location` usa `http://` en vez de `https://` — y ese downgrade de esquema hace que `httpx` (usado por el cliente MCP) **descarte el header `Authorization` al seguir la redirección**, por diseño de seguridad estándar (tratar el cambio de esquema como cambio de origen). El resultado es una segunda petición sin token, que Cloud Run rechaza con `403 Forbidden` — un error que parece de IAM/permisos pero es en realidad de la barra final. Pedir `/mcp` directo evita el redirect por completo.

---

## Fase 3 — Desplegar 02_agent_api

### 3.1. Completar tu `.env` de `02_agent_api`

```bash
cp 02_agent_api/.env.example 02_agent_api/.env
nano 02_agent_api/.env
```

Completa primero OpenAI, PostgreSQL y Groq. Luego reemplaza las variables de integración por estos valores reales:

```
GUARDRAIL_ENGINE=model_armor
MODEL_ARMOR_PROJECT_ID=<tu PROJECT_ID>
MODEL_ARMOR_LOCATION=<tu REGION>
MODEL_ARMOR_TEMPLATE_ID=<el que creaste en la Fase 1.5>
DEMO_MCP_SERVER_URL=<$MCP_SERVER_URL de la Fase 2.3>/mcp
```

Por ejemplo, si el comando anterior mostró `https://mcp-server-service-abc-uc.a.run.app`, escribe `DEMO_MCP_SERVER_URL=https://mcp-server-service-abc-uc.a.run.app/mcp`. **Sin barra final** — ver la nota de la Fase 2.3 sobre por qué la barra final rompe la autenticación con la versión de `mcp` que usa este proyecto. Guarda el archivo y vuelve al directorio raíz del repositorio antes de ejecutar el siguiente bloque.
`GOOGLE_APPLICATION_CREDENTIALS` debe quedar **vacío** — en Cloud Run la SA de la Fase 1.4 reemplaza esa credencial local, tanto para Model Armor como para obtener el ID token hacia `03_mcp_server`.

### 3.2. Build + deploy

Las 5 credenciales sensibles (OpenAI, base de datos, Neon, Groq, LangSmith) no viajan como texto plano en la configuración de Cloud Run — el bucle de abajo las sube una sola vez a **Secret Manager** y el deploy solo referencia un puntero (`agent-openai-api-key:latest`), nunca el valor. Por qué usar secretos en vez de variables de entorno directas:

- **El valor no queda expuesto.** `gcloud run services describe` muestra el nombre del secreto y su versión, nunca el contenido — a diferencia de una env var normal, legible por cualquiera con acceso de lectura al servicio.
- **Acceso mínimo, uno por uno.** El bucle otorga `secretAccessor` secreto por secreto a la Service Account, no un rol amplio sobre todo Secret Manager del proyecto.
- **Versionado, no sobrescritura.** Cada `versions add` crea una versión inmutable. `:latest` apunta a la más reciente, pero podés fijar un número y hacer rollback si una key se rota mal.
- **Queda auditado.** Cada acceso a un secreto se registra en Cloud Audit Logs — una env var normal no deja ese rastro de quién la leyó ni cuándo.

> **¿Por qué no simplemente `--set-env-vars`?** Funcionaría, pero el valor quedaría en texto plano dentro de la revisión de Cloud Run, visible para cualquiera con permiso de lectura sobre el servicio (`run.services.get`), sin necesitar acceso a Secret Manager. Con secretos, ese mismo lector solo ve el *nombre* del secreto; para leer el valor necesita además `secretAccessor` sobre ese secreto puntual.

> **Validación real del laboratorio:** este contenedor carga spaCy, guardrails, LangChain y clientes MCP durante el arranque — con `--memory=1Gi` el arranque es inestable (varias revisiones fallaron por esto durante la validación de esta guía). Usa `--cpu=4 --memory=4Gi`, que es lo que quedó probado y estable de punta a punta. Si Cloud Run informa que no escuchó `PORT=8080`, no aumentes el timeout del Gateway a ciegas: revisa primero los logs de la revisión (`gcloud run services logs read`, ver Verificación) — o, si tienes Docker instalado localmente, prueba la misma imagen con `docker run` (opcional, no lo necesitas para el resto de la guía). Las integraciones opcionales Neon MCP y LangSmith pueden omitirse del runtime sin quitar `DATABASE_URL` ni el MCP privado principal, pero si las incluyes revisa que **las 5** queden en `--set-secrets` — omitir una silenciosamente la deja sin conectar, sin ningún error visible.

```bash
export IMAGE_TAG="$(date +'%Y%m%d-%H%M%S')"
export AGENT_API_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPOSITORY}/02-agent-api:${IMAGE_TAG}"

gcloud builds submit 02_agent_api \
  --project="$PROJECT_ID" \
  --tag="$AGENT_API_IMAGE"

# Crea los secretos una vez, agrega la versión real desde .env y concede a la
# SA acceso solo a cada secreto (no a todos los secretos del proyecto).
for SPEC in \
  OPENAI_API_KEY:agent-openai-api-key \
  DATABASE_URL:agent-database-url \
  NEON_API_KEY:agent-neon-api-key \
  GROQ_API_KEY:agent-groq-api-key \
  LANGSMITH_API_KEY:agent-langsmith-api-key; do
  KEY="${SPEC%%:*}"
  SECRET_ID="${SPEC#*:}"
  gcloud secrets describe "$SECRET_ID" --project="$PROJECT_ID" >/dev/null 2>&1 || \
    gcloud secrets create "$SECRET_ID" --project="$PROJECT_ID" --replication-policy=automatic
  VALUE="$(grep -m1 "^${KEY}=" 02_agent_api/.env | cut -d= -f2-)"
  printf %s "$VALUE" | gcloud secrets versions add "$SECRET_ID" \
    --project="$PROJECT_ID" --data-file=-
  unset VALUE
  gcloud secrets add-iam-policy-binding "$SECRET_ID" \
    --project="$PROJECT_ID" \
    --member="serviceAccount:${SERVICE_SA}" \
    --role="roles/secretmanager.secretAccessor"
done

# Solo configuración no sensible. También se omite la ruta local de ADC.
grep -vE '^\s*(#|$|OPENAI_API_KEY=|DATABASE_URL=|NEON_API_KEY=|GROQ_API_KEY=|LANGSMITH_API_KEY=|GOOGLE_APPLICATION_CREDENTIALS=)' \
  02_agent_api/.env > .agent-cloudrun.env

gcloud run deploy "$AGENT_API_SERVICE" \
  --project="$PROJECT_ID" \
  --image="$AGENT_API_IMAGE" \
  --region="$REGION" \
  --platform=managed \
  --no-allow-unauthenticated \
  --service-account="$SERVICE_SA" \
  --port=8080 \
  --cpu=4 \
  --memory=4Gi \
  --timeout=300 \
  --env-vars-file=.agent-cloudrun.env \
  --set-secrets='OPENAI_API_KEY=agent-openai-api-key:latest,DATABASE_URL=agent-database-url:latest,NEON_API_KEY=agent-neon-api-key:latest,GROQ_API_KEY=agent-groq-api-key:latest,LANGSMITH_API_KEY=agent-langsmith-api-key:latest'

rm .agent-cloudrun.env
```

Despliega con `--no-allow-unauthenticated` y `--service-account "$RUNTIME_SERVICE_ACCOUNT"` — el Cloud Run queda cerrado, solo el Gateway podrá invocarlo.

### 3.3. Ahora sí: darle a la SA permiso sobre este Cloud Run específico

```bash
gcloud run services add-iam-policy-binding "$AGENT_API_SERVICE" \
  --region="$REGION" \
  --member="serviceAccount:${SERVICE_SA}" \
  --role="roles/run.invoker"
```

---

## Fase 4 — Crear el API Gateway

Google API Gateway es un proxy administrado: recibe la request pública, valida el JWT contra Identity Platform y, solo si es válida, la reenvía a `02_agent_api` con una identidad de servicio distinta. Nada de esto vive en el código de FastAPI — es configuración declarada en `openapi_gateway.yml`, no lógica que tengas que mantener vos.

Qué pasa en cada request:

1. **El navegador** manda `Authorization: Bearer <ID token de Identity Platform>`, obtenido al loguearse con la cuenta de prueba de la Fase 1.2.
2. **El Gateway** valida firma, expiración y `audience` del token contra el `securitySchemes.identity_platform` del OpenAPI — si falla, corta acá mismo con `401` y `02_agent_api` ni se entera de que existió la request.
3. Si el token es válido, el Gateway **cambia de identidad**: pide un ID token de Google para la Service Account (`--backend-auth-service-account`, ver 4.3) y lo adjunta en lugar del token del usuario.
4. **`02_agent_api`** recibe la request ya autenticada como llamada de servicio a servicio, verificada por IAM de Cloud Run (`--no-allow-unauthenticated`) — nunca ve ni confía en el token original del usuario final.

Por qué vale la pena este salto extra en vez de exponer `02_agent_api` directo:

- **Reduce lo que queda expuesto.** `02_agent_api` se despliega privado; nadie puede llamarlo directo aunque adivine la URL. La única puerta pública del backend es el Gateway.
- **Traduce la identidad.** El usuario llega con su propio token; el Gateway lo cambia por un token de servicio al reenviar, así el backend nunca maneja credenciales de usuarios finales.
- **El contrato vive en un YAML.** Rutas, `deadline` y quién firma la auth están en `openapi_gateway.yml` — versionable (`GATEWAY_CONFIG_ID`) sin tocar ni redeployar el código de FastAPI.
- **Corta temprano lo inválido.** Un JWT ausente o vencido se rechaza en el Gateway antes de despertar un cold start de Cloud Run — el backend privado no gasta cómputo en tráfico no autenticado.

> **¿Qué pasa si el JWT es inválido o venció?** El Gateway responde `401 Unauthorized` directamente — la request nunca llega a Cloud Run. Hay que volver a loguear al usuario para obtener un token nuevo; no es un bug de `02_agent_api` aunque el error aparezca al llamar a la URL del Gateway.

### 4.1. Obtener la URL del Cloud Run recién desplegado

```bash
export CLOUD_RUN_URL=$(gcloud run services describe "$AGENT_API_SERVICE" \
  --region="$REGION" --format="value(status.url)")
echo "$CLOUD_RUN_URL"
```

### 4.2. Renderizar `openapi_gateway.yml` (plantilla parametrizada)

`02_agent_api/openapi_gateway.yml` usa `${CLOUD_RUN_URL}`, `${GATEWAY_HOST}` y `${IDENTITY_PLATFORM_PROJECT_ID}` — Google API Gateway sube el YAML tal cual (no soporta variables en runtime), así que hay que resolverlas antes con `envsubst`. `GATEWAY_HOST` recién se conoce después de crear el gateway (paso 4.3) — para esta primera subida usa un placeholder cualquiera (el `servers.url` es informativo, no afecta el ruteo real):

La plantilla configura `deadline: 120.0` para el backend. Es necesario porque la primera petición puede inicializar el agente, la conexión MCP y los guardrails; con el límite predeterminado la prueba real puede terminar en `504 upstream request timeout`.

> **No corras `envsubst` sin lista de variables.** Sin argumentos, `envsubst` sustituye *cualquier* `$VAR` o `${VAR}` del archivo — incluido `$ref`, que OpenAPI usa por todo el spec para las referencias de schema. Como no existe una variable de entorno `ref`, `envsubst` reemplaza cada `$ref` por texto vacío y rompe **todos** los `$ref` del archivo — un YAML que sigue pareciendo válido pero con las referencias vacías. Por eso el comando de abajo le pasa la lista explícita de las 3 variables reales y valida el resultado antes de seguir. Si en algún momento agregas una variable nueva a `openapi_gateway.yml`, agrégala también a esta lista — si no, `envsubst` la deja tal cual (literal en el YAML) y la verificación de abajo lo va a detectar.

```bash
export GATEWAY_HOST="placeholder.gateway.dev"

cd 02_agent_api

envsubst '${CLOUD_RUN_URL} ${GATEWAY_HOST} ${IDENTITY_PLATFORM_PROJECT_ID}' \
  < openapi_gateway.yml > openapi_gateway.rendered.yml

# Verificación: falla temprano si quedó algo sin resolver o roto
if grep -qE '\$\{' openapi_gateway.rendered.yml; then
  echo "ERROR: quedaron variables \${...} sin sustituir en openapi_gateway.rendered.yml" >&2
  grep -n '\${' openapi_gateway.rendered.yml >&2
  exit 1
fi
if grep -qE '^\s*: "' openapi_gateway.rendered.yml; then
  echo "ERROR: quedó un \$ref roto en openapi_gateway.rendered.yml (revisa la lista de envsubst)" >&2
  exit 1
fi

cd ..
```

### 4.3. Crear API, config y gateway

```bash
gcloud api-gateway apis create "$GATEWAY_API_ID" --project="$PROJECT_ID"

gcloud api-gateway api-configs create "$GATEWAY_CONFIG_ID" \
  --api="$GATEWAY_API_ID" \
  --openapi-spec=02_agent_api/openapi_gateway.rendered.yml \
  --project="$PROJECT_ID" \
  --backend-auth-service-account="$SERVICE_SA"

gcloud api-gateway gateways create "$GATEWAY_ID" \
  --api="$GATEWAY_API_ID" \
  --api-config="$GATEWAY_CONFIG_ID" \
  --location="$REGION" \
  --project="$PROJECT_ID"

export GATEWAY_HOST=$(gcloud api-gateway gateways describe "$GATEWAY_ID" \
  --location="$REGION" --format="value(defaultHostname)")
echo "Gateway listo en: https://$GATEWAY_HOST"
```

Si quieres que `servers.url` del YAML refleje el host real (no el placeholder), vuelve a correr el `envsubst` del paso 4.2 con el `$GATEWAY_HOST` real — no es obligatorio, es solo documentación dentro del propio spec.

**Actualizar el config más adelante** (nuevo deploy de `02_agent_api`, o cambios en `openapi_gateway.yml`): crea un nuevo `GATEWAY_CONFIG_ID` (ej. `agent-api-gw-config-v2`) con `api-configs create` y luego apunta el gateway existente a esa config con `gcloud api-gateway gateways update "$GATEWAY_ID" --api="$GATEWAY_API_ID" --api-config=NUEVO_CONFIG_ID --location="$REGION"` — los configs son inmutables, no se editan in-place.

---

## Fase 5 — Desplegar 01_agent-app (frontend)

Recién acá se despliega el frontend — ya tenemos `$GATEWAY_HOST`, la única variable que le faltaba. Las variables `NEXT_PUBLIC_*` se hornean en build-time (ver comentario en `01_agent-app/Dockerfile`).

Este build necesita 4 `--build-arg`, y `gcloud builds submit --tag` (el atajo que usan las Fases 2.2 y 3.2) no soporta pasarlos. Por eso `01_agent-app/cloudbuild.yaml` describe el mismo `docker build` explícitamente, y los 4 valores se inyectan vía `--substitutions` al momento de invocarlo:

```bash
export IMAGE_TAG=$(date +"%Y%m%d-%H%M%S")
export AGENT_APP_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPOSITORY}/01-agent-app:${IMAGE_TAG}"

gcloud builds submit 01_agent-app \
  --project="$PROJECT_ID" \
  --config=01_agent-app/cloudbuild.yaml \
  --substitutions=_GATEWAY_HOST="$GATEWAY_HOST",_FIREBASE_API_KEY="$IDENTITY_PLATFORM_API_KEY",_FIREBASE_AUTH_DOMAIN="$IDENTITY_PLATFORM_AUTH_DOMAIN",_FIREBASE_PROJECT_ID="$IDENTITY_PLATFORM_PROJECT_ID",_IMAGE="$AGENT_APP_IMAGE"

gcloud run deploy "$AGENT_APP_SERVICE" \
  --image "$AGENT_APP_IMAGE" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --port 3000 \
  --cpu 2 \
  --memory 2Gi
```

> Las sustituciones van separadas por comas y sin espacios alrededor del `=` — si algún valor llegara a contener una coma (no debería, para una API key o un host), rómpelo en un `cloudbuild.yaml` con variables de entorno en vez de `--substitutions`.

`01_agent-app` sí queda público (`--allow-unauthenticated`) — es la app que ve el usuario final; la protección real está en que `02_agent_api` solo acepta al Gateway (y `03_mcp_server` solo acepta a `02_agent_api`), y el Gateway solo reenvía peticiones con un JWT válido de Identity Platform.

---

## Verificación

**1. Confirmar que el Gateway responde y valida auth:**
```bash
# Sin token: debe dar 401
curl -i "https://${GATEWAY_HOST}/api/errors"

# Con token de Identity Platform (reemplaza <ID_TOKEN>, obtenido al iniciar sesión)
curl -i "https://${GATEWAY_HOST}/api/errors" -H "Authorization: Bearer <ID_TOKEN>"
```

**2. Confirmar que Cloud Run rechaza acceso directo** (debe fallar con 403, ya no acepta llamadas sin la identidad del Gateway):
```bash
curl -i "${CLOUD_RUN_URL}/api/errors"
```

**3. Confirmar que Model Armor está activo (no en fallback local)**: revisa los logs de `02_agent_api` en Cloud Logging — al arrancar debe aparecer el pipeline con `ModelArmorMiddleware` y **no** el warning `"No se pudo inicializar ModelArmorMiddleware"` ni `"falta MODEL_ARMOR_PROJECT_ID/MODEL_ARMOR_TEMPLATE_ID"` (ver `guardrails/__init__.py`). Si aparece, revisa que la SA (Fase 1.4) tenga `roles/modelarmor.user`.

**Si Cloud Run falla antes de escuchar el puerto**, identifica la revisión y lee sus logs antes de crear otra:

```bash
gcloud run revisions list --service="$AGENT_API_SERVICE" --region="$REGION"
gcloud run services logs read "$AGENT_API_SERVICE" --region="$REGION" --limit=100
```

Un `504 upstream request timeout` en Gateway junto con un `503` y `failed the readiness check` en Cloud Run indica un cold start fallido del contenedor, no un error de autenticación del Gateway.

**4. Confirmar que 02_agent_api conectó a 03_mcp_server por HTTP**: en los logs, buscar `"Demo MCP server conectado"` (log de `main.py`). Si en cambio aparece `"Error conectando al demo MCP server"`:
   - Revisa que `DEMO_MCP_SERVER_URL` termine en `/mcp` (sin barra final — ver Fase 2.3) y apunte a la URL real de la Fase 2.3.
   - Si el error menciona 401/403: la causa más común es la barra final en `DEMO_MCP_SERVER_URL` (Fase 2.3 explica por qué revienta la autenticación). Si ya la sacaste y sigue, revisa que la SA tenga `roles/run.invoker` sobre `$MCP_SERVER_SERVICE`, o que `GoogleIDTokenAuth` haya podido obtener el ID token (revisa que la Cloud Run de `02_agent_api` tenga `--service-account "$SERVICE_SA"` asignado, Fase 3.2) — busca el warning `"No se pudo obtener ID token de Google"` en los logs (`src/utils/gcp_auth.py`).
   - Si la conexión queda establecida pero el campo `sources` de `/api/chat` llega vacío para preguntas que usaron `retrieve_documents`: confirma que `03_mcp_server/requirements.txt` tenga `mcp[cli]>=1.13.0,<2` (no la versión `==1.8.0`, que no propaga `structuredContent`).

**5. Probar el flujo completo por `curl`, sin depender del navegador**: obtén un ID token real iniciando sesión con el usuario de prueba (Fase 1.2) contra la REST API de Identity Platform, y úsalo contra el Gateway. Esto ejercita la cadena completa (Gateway → `02_agent_api` → guardrails → `03_mcp_server`) exactamente igual que lo haría el frontend:

```bash
export ID_TOKEN=$(curl -s -X POST \
  "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=${IDENTITY_PLATFORM_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"email":"<email del usuario de prueba>","password":"<su password>","returnSecureToken":true}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['idToken'])")

curl -i -X POST "https://${GATEWAY_HOST}/api/chat" \
  -H "Authorization: Bearer ${ID_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"question":"What is the capital of Chile?","user":"smoke-test"}'
```

Debe responder `200` con un `answer` real (la primera llamada puede tardar hasta el `deadline: 120.0` del Gateway si el contenedor estaba en cold start). Si el `curl` con caracteres acentuados/UTF-8 en `question` devuelve `400 There was an error parsing the body`, es un problema de encoding del shell al armar el JSON (usa `--data-binary @archivo.json` con el payload guardado en un archivo), no un error del servicio.

**6. Probar el flujo completo desde el navegador**: abrir la URL de `$AGENT_APP_SERVICE`, iniciar sesión con el usuario de Identity Platform, mandar un mensaje y confirmar que llega respuesta (en Network del navegador la request debe ir a `https://$GATEWAY_HOST/api/chat`, no al Cloud Run directo).

---

## Limpieza — eliminar todo lo desplegado

Para volver a ejecutar el laboratorio desde cero (o simplemente para no seguir pagando por los recursos), esto borra todo lo que creó esta guía, en el orden correcto de dependencias. Ejecuta este bloque desde la misma terminal donde definiste las variables de la Fase 0 (si la cerraste, vuelve a exportarlas primero).

```bash
# 1. API Gateway: primero el gateway, luego todos sus api-configs, al final la API.
gcloud api-gateway gateways delete "$GATEWAY_ID" \
  --location="$REGION" --project="$PROJECT_ID" --quiet

for CFG in $(gcloud api-gateway api-configs list --api="$GATEWAY_API_ID" \
  --project="$PROJECT_ID" --format="value(name.basename())"); do
  gcloud api-gateway api-configs delete "$CFG" \
    --api="$GATEWAY_API_ID" --project="$PROJECT_ID" --quiet
done

gcloud api-gateway apis delete "$GATEWAY_API_ID" --project="$PROJECT_ID" --quiet

# 2. Los 3 Cloud Run.
gcloud run services delete "$AGENT_APP_SERVICE" --region="$REGION" --project="$PROJECT_ID" --quiet
gcloud run services delete "$AGENT_API_SERVICE" --region="$REGION" --project="$PROJECT_ID" --quiet
gcloud run services delete "$MCP_SERVER_SERVICE" --region="$REGION" --project="$PROJECT_ID" --quiet

# 3. Los 5 secretos de Secret Manager (Fase 3.2).
for SECRET_ID in agent-openai-api-key agent-database-url agent-neon-api-key \
  agent-groq-api-key agent-langsmith-api-key; do
  gcloud secrets delete "$SECRET_ID" --project="$PROJECT_ID" --quiet
done

# 4. El template de Model Armor (requiere el mismo endpoint regional de la Fase 1.5).
gcloud config set api_endpoint_overrides/modelarmor \
  "https://modelarmor.${REGION}.rep.googleapis.com/"
gcloud model-armor templates delete "$MODEL_ARMOR_TEMPLATE_ID" \
  --project="$PROJECT_ID" --location="$REGION" --quiet

# 5. Los bindings IAM a nivel de proyecto (Fases 1.1 y 1.4) — no se borran
# solos al eliminar la SA, quedarían como entradas huérfanas "deleted:...".
export PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
gcloud projects remove-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/artifactregistry.writer" --quiet
gcloud projects remove-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SERVICE_SA}" \
  --role="roles/modelarmor.user" --quiet
gcloud projects remove-iam-policy-binding "$PROJECT_ID" \
  --member="$DEPLOYER_MEMBER" \
  --role="roles/modelarmor.admin" --quiet

# 6. La Service Account (esto también elimina el binding run.invoker que tenía
# sobre cada Cloud Run y el iam.serviceAccountUser que tenía el deployer sobre ella).
gcloud iam service-accounts delete "$SERVICE_SA" --project="$PROJECT_ID" --quiet

# 7. El repositorio de Artifact Registry, con todas las imágenes que subiste.
gcloud artifacts repositories delete "$AR_REPOSITORY" \
  --project="$PROJECT_ID" --location="$REGION" --quiet

# 8. Artefacto local generado por la Fase 4.2 (no es un recurso de GCP).
rm -f 02_agent_api/openapi_gateway.rendered.yml
```

> **Identity Platform no se elimina con `gcloud`** (no hay un comando de "desinicializar" el proyecto para este producto). Si quieres borrar solo la cuenta de prueba de la Fase 1.2, hazlo desde **Google Cloud Console → Identity Platform → Users**. Dejar Identity Platform habilitado sin usuarios no genera costo.

> Los archivos `02_agent_api/.env` y `03_mcp_server/.env` (con tus API keys) **no se tocan** — son locales y los reutilizas tal cual la próxima vez que despliegues, salvo que cambies de proyecto GCP (en ese caso, `MODEL_ARMOR_PROJECT_ID` y `DEMO_MCP_SERVER_URL` van a cambiar).
