# Chatbot Gateway

Este proyecto implementa un **API Gateway** que actúa como middleware entre WhatsApp (a través de WAHA - WhatsApp HTTP API) y un servicio de chatbot basado en LangChain. El gateway procesa webhooks de WhatsApp, reenvía mensajes al chatbot y devuelve las respuestas automáticamente.

## Características

- **API Gateway**: Middleware entre WhatsApp y servicios de chatbot
- **Integración WAHA**: Compatible con WhatsApp HTTP API (WAHA)
- **Procesamiento de Webhooks**: Recibe y procesa eventos de WhatsApp automáticamente
- **Reenvío de Mensajes**: Transforma y reenvía mensajes al servicio de chatbot
- **Respuestas Automáticas**: Envía las respuestas del chatbot de vuelta a WhatsApp
- **Manejo de Errores**: Gestión robusta de errores con mensajes de usuario amigables
- **API REST**: Arquitectura basada en FastAPI con documentación automática
- **Mapeo de Datos**: Transformación automática entre formatos de WAHA y chatbot

## Instalación
    
1. Instalar dependencias:
```bash
pip install -r requirements.txt
```

2. Crear archivo `.env` en la raíz del proyecto:
```bash
# Crear el archivo .env
touch .env
```

3. Configurar variables de entorno en el archivo `.env`:
```env
# Variables de entorno para el Chatbot Gateway

# URL del servicio de chatbot (donde está corriendo el chatbot LangChain)
CHATBOT_API_URL=http://localhost:8080

# URL de la API de WAHA (WhatsApp HTTP API)
WAHA_API_URL=http://localhost:3000
```

**⚠️ Importante**: 
- Asegúrate de que el servicio de chatbot esté corriendo en la URL especificada
- Configura WAHA correctamente y actualiza la URL según tu configuración

## Uso

### Ejecutar el gateway
```bash
python -m src.main
```

El gateway estará disponible en: http://localhost:8090

### Documentación de la API
Visita: http://localhost:8090/docs para ver la documentación interactiva de Swagger.

## Arquitectura

El `chatbot_gateway` funciona como un puente entre WhatsApp y tu servicio de chatbot:

```
WhatsApp → WAHA → Chatbot Gateway → Servicio Chatbot
                      ↓
WhatsApp ← WAHA ← Chatbot Gateway ← Respuesta Chatbot
```

### Flujo de Procesamiento

1. **Webhook de WAHA**: Recibe mensajes de WhatsApp vía webhook
2. **Mapeo de Datos**: Transforma el formato de WAHA al formato del chatbot
3. **Llamada al Chatbot**: Envía la pregunta al servicio de chatbot
4. **Procesamiento de Respuesta**: Recibe y valida la respuesta del chatbot
5. **Envío a WhatsApp**: Reenvía la respuesta a WhatsApp vía WAHA

### Endpoints principales

#### 1. Webhook de WAHA
```http
POST /waha/webhook
Content-Type: application/json

{
    "event": "message",
    "session": "default",
    "payload": {
        "id": "msg_id",
        "timestamp": 1234567890,
        "from": "5491234567890@c.us",
        "fromMe": false,
        "to": "5491234567891@c.us",
        "body": "Hola, ¿cómo estás?",
        "hasMedia": false,
        "ack": 1,
        "vCards": [],
        "_data": {}
    }
}
```

**Respuesta exitosa:**
```json
{
    "status": "success",
    "message": "Message processed and sent successfully",
    "chatbot_response": {
        "status": "success",
        "response": "¡Hola! Estoy muy bien, gracias por preguntar. ¿En qué puedo ayudarte hoy?",
        "user": "5491234567890@c.us"
    },
    "send_response": {
        "success": true
    }
}
```

## Configuración de WAHA

Para que el gateway funcione correctamente, necesitas configurar WAHA para enviar webhooks:

### 1. Configurar Webhook en WAHA
```bash
curl -X POST "http://localhost:3000/api/webhook" \
     -H "Content-Type: application/json" \
     -d '{
       "url": "http://localhost:8090/waha/webhook",
       "events": ["message"]
     }'
```

### 2. Verificar Estado del Webhook
```bash
curl -X GET "http://localhost:3000/api/webhook"
```

## Servicios Requeridos

Para que el `chatbot_gateway` funcione correctamente, necesitas tener corriendo:

1. **Servicio de Chatbot**: El chatbot LangChain debe estar corriendo en `CHATBOT_API_URL`
2. **WAHA**: WhatsApp HTTP API debe estar corriendo en `WAHA_API_URL`
3. **WhatsApp**: Una sesión de WhatsApp activa en WAHA

### Verificar Servicios
```bash
# Verificar chatbot
curl http://localhost:8080/health

# Verificar WAHA
curl http://localhost:3000/api/sessions

# Verificar gateway
curl http://localhost:8090/docs
```

## Manejo de Errores

El gateway incluye manejo robusto de errores:

- **Errores de conexión**: Mensajes amigables al usuario cuando hay problemas de red
- **Errores del chatbot**: Validación de respuestas del servicio de chatbot
- **Errores de WAHA**: Manejo de fallos en el envío de mensajes a WhatsApp
- **Logging**: Registro detallado de errores para debugging

## Componentes del Código

### Estructura del Proyecto
```
src/
├── main.py                 # Aplicación FastAPI principal
├── routes/
│   └── waha_router.py      # Endpoints del webhook y lógica de procesamiento
├── entities/
│   └── chatbot_entities.py # Modelos de datos Pydantic
└── mapper/
    └── waha_mapper.py      # Transformación de datos entre formatos
```

### Funciones Principales

- **`send_waha_message()`**: Envía mensajes a WhatsApp vía WAHA
- **`handle_error_response()`**: Maneja errores y envía mensajes de error al usuario
- **`map_to_chatbot_payload()`**: Transforma datos de WAHA al formato del chatbot
- **`map_to_send_text_payload()`**: Transforma respuestas para envío vía WAHA 