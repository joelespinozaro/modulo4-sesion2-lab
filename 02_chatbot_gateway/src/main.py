import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from dotenv import load_dotenv
load_dotenv()
from src.routes.waha_router import router as waha_router

# Cargar variables de entorno del archivo .env

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Chatbot Gateway",
    description="API Gateway for processing chatbot questions",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(waha_router)

if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8090, reload=True)
