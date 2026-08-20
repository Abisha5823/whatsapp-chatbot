# backend/api/routes.py
from fastapi import APIRouter, HTTPException, Query, Body
from typing import List, Optional
from datetime import datetime

# ✅ FIX: Relative imports
from models.lead import Lead, LeadCreate
from models.booking import Booking, BookingCreate
from services.lead_service import LeadService
from services.booking_service import BookingService
from services.conversation_service import ConversationService
from services.rag_service import RAGService

router = APIRouter(prefix="/api", tags=["API"])

@router.get("/leads", response_model=List[Lead])
async def get_all_leads(skip: int = 0, limit: int = 100):
    """Get all leads"""
    lead_service = LeadService()
    leads = await lead_service.get_all_leads(skip, limit)
    return leads

@router.get("/leads/{lead_id}")
async def get_lead(lead_id: str):
    """Get lead by ID"""
    lead_service = LeadService()
    lead = await lead_service.get_lead_by_id(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead

@router.get("/bookings", response_model=List[Booking])
async def get_all_bookings(skip: int = 0, limit: int = 100):
    """Get all bookings"""
    booking_service = BookingService()
    bookings = await booking_service.get_all_bookings(skip, limit)
    return bookings

@router.post("/bookings")
async def create_booking(booking: BookingCreate):
    """Create a new booking manually"""
    booking_service = BookingService()
    created = await booking_service.create_manual_booking(booking)
    return created

@router.get("/bookings/{booking_id}")
async def get_booking(booking_id: str):
    """Get booking by ID"""
    booking_service = BookingService()
    booking = await booking_service.get_booking_by_id(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking

@router.put("/bookings/{booking_id}/status")
async def update_booking_status(booking_id: str, status: str = Body(...)):
    """Update booking status"""
    booking_service = BookingService()
    updated = await booking_service.update_status(booking_id, status)
    if not updated:
        raise HTTPException(status_code=404, detail="Booking not found")
    return {"message": "Status updated successfully"}

@router.post("/rag/ingest")
async def ingest_pdf(file_path: str = Body(...)):
    """Ingest a new PDF into RAG system"""
    rag_service = RAGService()
    success = await rag_service.ingest_pdf(file_path)
    if success:
        return {"message": "PDF ingested successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to ingest PDF")

@router.get("/conversation/{chat_id}")
async def get_conversation(chat_id: str):
    """Get conversation history for a chat_id"""
    conv_service = ConversationService()
    conversation = await conv_service.get_conversation(chat_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation

@router.post("/handoff")
async def request_human_handoff(chat_id: str = Body(...)):
    """Request human handoff for a chat"""
    from api.webhook import handle_human_handoff
    conv_service = ConversationService()
    conversation = await conv_service.get_conversation(chat_id)
    if conversation:
        await handle_human_handoff(chat_id, conversation)
        return {"message": "Handoff requested successfully"}
    raise HTTPException(status_code=404, detail="Conversation not found")

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "whatsapp-chatbot",
        "timestamp": datetime.utcnow().isoformat()
    }

@router.post("/send-message")
async def send_proactive_message(chat_id: str = Body(...), message: str = Body(...)):
    """Send a proactive message to a user"""
    from services.whatsapp_service import WhatsAppService
    whatsapp = WhatsAppService()
    result = await whatsapp.send_message(chat_id, message)
    return {"message": "Message sent successfully", "result": result}