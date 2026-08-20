from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Dict, Any
import json
import logging
from datetime import datetime

from backend.services.whatsapp_service import WhatsAppService
from backend.services.ai_service import AIService
from backend.services.lead_service import LeadService
from backend.services.booking_service import BookingService
from backend.services.conversation_service import ConversationService
from backend.services.rag_service import RAGService
from core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/webhook")
async def verify_webhook(request: Request):
    """WhatsApp webhook verification"""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    
    if mode and token:
        if mode == "subscribe" and token == settings.VERIFY_TOKEN:
            return JSONResponse(content=int(challenge))
        else:
            raise HTTPException(status_code=403, detail="Invalid verification token")
    
    raise HTTPException(status_code=400, detail="Missing parameters")

@router.post("/webhook")
async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle incoming WhatsApp messages"""
    try:
        body = await request.json()
        logger.info(f"Received webhook: {json.dumps(body)}")
        
        # Extract message data
        entry = body.get("entry", [])
        for e in entry:
            changes = e.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                messages = value.get("messages", [])
                
                for message in messages:
                    # Process each message in background
                    background_tasks.add_task(
                        process_message,
                        message,
                        value.get("metadata", {})
                    )
        
        return JSONResponse(content={"status": "ok"})
        
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})

async def process_message(message: Dict[str, Any], metadata: Dict[str, Any]):
    """Process incoming message asynchronously"""
    try:
        chat_id = message.get("from")
        msg_type = message.get("type")
        
        # Handle different message types
        if msg_type == "text":
            text = message.get("text", {}).get("body", "")
        elif msg_type == "voice":
            # Voice note - download and transcribe
            voice_service = VoiceService()
            text = await voice_service.transcribe_voice(message)
        elif msg_type == "interactive":
            # Interactive button/flow responses
            text = message.get("interactive", {}).get("button_reply", {}).get("title", "")
        else:
            logger.warning(f"Unsupported message type: {msg_type}")
            return
        
        if not text:
            return
        
        # Get or create conversation
        conv_service = ConversationService()
        conversation = await conv_service.get_or_create(chat_id)
        
        # Detect language
        from utils.helpers import detect_language
        language = detect_language(text)
        conversation["language"] = language
        
        # Check if user wants human handoff
        if any(keyword in text.lower() for keyword in ["agent", "human", "person", "speak", "talk to"]):
            await handle_human_handoff(chat_id, conversation)
            return
        
        # Process with AI
        ai_service = AIService()
        response = await ai_service.generate_response(
            message=text,
            conversation=conversation
        )
        
        # Check for booking intent
        if "booking" in response.get("intent", "").lower():
            booking_service = BookingService()
            booking = await booking_service.create_from_conversation(
                chat_id, conversation, response
            )
            if booking:
                # Notify owner
                from backend.services.notification_service import send_booking_notification
                await send_booking_notification(booking)
        
        # Save lead if collected
        lead_service = LeadService()
        if response.get("lead_collected", False):
            lead = await lead_service.save_lead(chat_id, conversation, response)
            if lead:
                # Sync to Google Sheets
                await lead_service.sync_to_google_sheets(lead)
                # Notify owner
                from backend.services.notification_service import send_lead_notification
                await send_lead_notification(lead)
        
        # Send response via WhatsApp
        whatsapp = WhatsAppService()
        await whatsapp.send_message(chat_id, response["reply"])
        
        # Update conversation
        await conv_service.update(chat_id, {
            "messages": conversation.get("messages", []) + [
                {"role": "user", "content": text, "timestamp": datetime.utcnow().isoformat()},
                {"role": "assistant", "content": response["reply"], "timestamp": datetime.utcnow().isoformat()}
            ],
            "context": conversation.get("context", {}),
            "phase": response.get("phase", "lead_collection"),
            "updated_at": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Message processing error: {str(e)}")
        # Send fallback message
        whatsapp = WhatsAppService()
        await whatsapp.send_message(
            chat_id, 
            "Sorry, I'm having trouble processing your request. Please try again or contact our support."
        )

async def handle_human_handoff(chat_id: str, conversation: Dict):
    """Handle human handoff request"""
    whatsapp = WhatsAppService()
    
    # Send acknowledgement
    await whatsapp.send_message(
        chat_id,
        "Sure! I'll connect you to our team. Please hold on while I find the best expert for you. 😊"
    )
    
    # Log handoff request
    conv_service = ConversationService()
    await conv_service.update(chat_id, {
        "phase": "human_handoff",
        "handoff_requested_at": datetime.utcnow().isoformat()
    })
    
    # Send notification to owner
    from backend.services.notification_service import send_handoff_notification
    await send_handoff_notification(chat_id, conversation)