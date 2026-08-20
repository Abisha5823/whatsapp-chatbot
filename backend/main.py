import os
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

from api.webhook import router as webhook_router
from api.routes import router as api_router
from core.database import connect_to_mongo, close_mongo_connection
from core.config import settings
from services.rag_service import RAGService

app = FastAPI(
    title="WhatsApp AI Chatbot System",
    description="Production-level WhatsApp automation with RAG, lead generation, and booking",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "whatsapp-chatbot",
        "version": "1.0.0",
        "mongodb": "connected",
        "rag": "initialized" if RAGService().vectorstore else "not_initialized"
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "WhatsApp AI Chatbot System",
        "docs": "/docs",
        "webhook": "/webhook",
        "health": "/health"
    }

# Include routers
app.include_router(webhook_router)
app.include_router(api_router)

# Startup events
@app.on_event("startup")
async def startup_db_client():
    """Initialize services on startup"""
    try:
        # Connect to MongoDB
        await connect_to_mongo()
        logger.info("MongoDB connected")
        
        # Initialize RAG service
        rag_service = RAGService()
        await rag_service.initialize()
        logger.info("RAG service initialized")
        
        logger.info("Application started successfully!")
        
    except Exception as e:
        logger.error(f"Startup error: {str(e)}")
        # Don't fail the startup - let the app run with limited functionality

@app.on_event("shutdown")
async def shutdown_db_client():
    """Cleanup on shutdown"""
    try:
        await close_mongo_connection()
        logger.info("MongoDB connection closed")
    except Exception as e:
        logger.error(f"Shutdown error: {str(e)}")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=settings.DEBUG,
        log_level="info"
    )