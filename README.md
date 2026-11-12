# Módulo 4 · Sesión 2 · Laboratorio de Skills, Hooks y patrones production-grade

**AI Solution Architect · Datapath** · Joel Espinoza Rojas

En la Sesión 1 el asistente del instituto aprendió a razonar, usar tools y responder con RAG. Funcionaba en el notebook. En este laboratorio lo conectamos a WhatsApp, con alumnos reales, y le agregamos lo que hace falta para que no se rompa:

| Problema en producción | Pieza que lo resuelve | Parte |
|---|---|---|
| El system prompt crece y cada mensaje arrastra todas las reglas | **Skills** que se cargan solo cuando la pregunta las necesita | 2 |
| Nadie sabe qué pasó ni cuánto costó una conversación | **Hooks** de logging y presupuesto de tokens | 3 |
| El proveedor del modelo falla en hora punta | **Retry** con espera creciente | 3 |
| Un alumno intenta manipular al agente o pega datos personales | **Guardrails** en 8 capas, fail-close | 4 |
| Un cambio rompe algo y nadie se entera | **Test suite** con pytest | 4 |

## Guías

- `docs/guia-sesion2-skills-hooks.html`: los conceptos de la sesión con artefactos interactivos y el laboratorio paso a paso.
- `docs/guia-repo-modulo4-sesion2.html`: qué hay en este repo, su arquitectura y qué agrega cada rama.

Descárgalas y ábrelas en el navegador.

## Arquitectura

```
 Celular del alumno
        │  WhatsApp
        ▼
 ┌──────────────┐  webhook   ┌────────────────────┐  POST /api/chat  ┌──────────────────────────────┐
 │ WAHA  :3030  │ ─────────▶ │ Gateway  :8090     │ ───────────────▶ │ Agent API  :8080             │
 │ (Docker)     │ ◀───────── │ 02_chatbot_gateway │ ◀─────────────── │ 02_agent_api                 │
 └──────────────┘  sendText  └────────────────────┘    respuesta     │  guardrails → middlewares →  │
                                                                     │  skills → LLM → tools        │
                                                                     └──────┬───────────────┬───────┘
                                                                            │               │ stdio (parte 4)
                                                                     PostgreSQL       03_mcp_server
                                                                     (historial)      skills/*/SKILL.md
                                                                                      retrieve_documents → Qdrant
```

- **WAHA** expone un número de WhatsApp como API REST y avisa cada mensaje por webhook.
- **02_chatbot_gateway** traduce entre WhatsApp y el agente: marca leído, muestra «escribiendo…», llama al agente y envía la respuesta.
- **02_agent_api** es el agente (LangChain `create_agent`). Cada parte le suma una capa.
- **03_mcp_server** (desde la parte 4) publica las skills como archivos `SKILL.md` y la búsqueda en Qdrant como tool MCP.
- **01_data_setup** crea las tablas de PostgreSQL y carga los documentos del instituto en Qdrant. Si ya lo hiciste en la sesión de RAG, puedes saltarlo.

## Una rama por parte

Cada rama suma una capa a la anterior. Para ver qué cambió entre dos partes: `git diff parte-2-skills parte-3-hooks -- 02_agent_api`.

| Rama | Qué agrega | Qué observar |
|---|---|---|
| `main` | Parte 1: agente con RAG + WhatsApp (WAHA + gateway) | Un mensaje de ida y vuelta desde tu celular |
| `parte-2-skills` | `SkillMiddleware` y la tool `load_skill` | En el log, `load_skill` aparece solo cuando la pregunta lo necesita |
| `parte-3-hooks` | Middlewares de logging, `TokenBudget`, `SafetyGuard` y `Retry` | El orden de ida y vuelta en la consola, y el corte por presupuesto |
| `parte-4-guardrails` | 8 capas de guardrails, skills servidas por MCP, `pytest` | Qué capa bloquea cada ataque y `pytest tests/guardrails -q` |
| `parte-5-produccion` | Opcional: Model Armor, evaluación con RAGAS y despliegue en GCP | Ver `DEPLOYMENT.md` |

## Cómo empezar

Requisitos: Python 3.11+, Docker, una API key de OpenAI, PostgreSQL y Qdrant con datos (ver `01_data_setup`). Desde la parte 4 también una API key gratuita de [Groq](https://console.groq.com/keys).

```bash
git clone <url-de-este-repo>
cd <carpeta-del-repo>

# 1. WAHA
mkdir waha && cd waha
docker run --rm -v "$(pwd)":/app/env devlikeapro/waha init-waha /app/env
docker run -d --name mywaha -p 3030:3000 --env-file .env devlikeapro/waha
cd ..

# 2. Agent API (terminal 1)
cd 02_agent_api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # completa OPENAI_API_KEY, DATABASE_URL y QDRANT_*
python -m src.main          # :8080

# 3. Gateway (terminal 2)
cd 02_chatbot_gateway
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# crea .env con CHATBOT_API_URL, WAHA_API_URL y WAHA_API_KEY (ver el .env.example)
python -m src.main          # :8090
```

Luego, en `http://localhost:3030/dashboard`: inicia la sesión `default`, escanea el QR con un número de pruebas y registra el webhook `http://host.docker.internal:8090/waha/webhook` con el evento `message`. En Linux usa la IP local de tu máquina en lugar de `host.docker.internal`.

Para pasar a la siguiente parte: `git checkout parte-2-skills` y reinicia el Agent API. La guía del alumno tiene los pasos de cada parte con comandos para Linux, macOS y Windows.

## Seguridad

- Nunca subas un `.env`. Este repo los ignora en `.gitignore`.
- Usa un número de WhatsApp de pruebas, no tu número personal.
- Sin `GROQ_API_KEY`, las capas 7 y 8 bloquean todos los mensajes a propósito (fail-close).
