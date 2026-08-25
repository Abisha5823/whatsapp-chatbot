# backend/api/webhook.py
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Dict, Any
import json
import logging
import re
from datetime import datetime

# ✅ FIX: Relative imports
from services.whatsapp_service import WhatsAppService
from services.ai_service import AIService
from services.lead_service import LeadService
from services.booking_service import BookingService
from services.conversation_service import ConversationService
from services.rag_service import RAGService
from services.voice_service import VoiceService
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
        
        if not msg_type and message.get("text"):
            msg_type = "text"
        
        if msg_type == "text":
            text = message.get("text", {}).get("body", "")
        elif msg_type == "voice":
            voice_service = VoiceService()
            text = await voice_service.transcribe_voice(message)
        elif msg_type == "interactive":
            text = message.get("interactive", {}).get("button_reply", {}).get("title", "")
        else:
            logger.warning(f"Unsupported message type: {msg_type}")
            return
        
        if not text:
            logger.warning("Empty message received")
            return
        
        conv_service = ConversationService()
        conversation = await conv_service.get_or_create(chat_id)
        
        from utils.helpers import detect_language
        language = detect_language(text)
        conversation["language"] = language
        
        context = conversation.get("context", {})
        if "collected_fields" not in context:
            context["collected_fields"] = []
        
        # ... (email, phone, name, date, time, mode extraction code here) ...
        
        conversation["context"] = context
        logger.info(f"📝 Current context for {chat_id}: {conversation.get('context', {})}")
        
        # Check for human handoff
        if any(keyword in text.lower() for keyword in ["agent", "human", "person", "speak", "talk to"]):
            await handle_human_handoff(chat_id, conversation)
            return
        
        # Process with AI
        ai_service = AIService()
        response = await ai_service.generate_response(
            message=text,
            conversation=conversation
        )
        
        # ... (lead data extraction code here) ...
        
        # ✅ SAVE LEAD ONLY ONCE - Check if lead already exists
        lead_service = LeadService()
        existing_lead = await lead_service.get_lead_by_chat_id(chat_id)
        
        # Check if we have enough data to save a lead
        has_lead_data = (
            response.get("lead_collected", False) or 
            len(context.get("collected_fields", [])) >= 2
        )
        
        if has_lead_data and not existing_lead:
            lead = await lead_service.save_lead(chat_id, conversation, response)
            if lead:
                await lead_service.sync_to_google_sheets(lead)
                from services.notification_service import send_lead_notification
                await send_lead_notification(lead)
                logger.info(f"✅ New lead saved and notified: {lead.name}")
        elif has_lead_data and existing_lead:
            # ✅ Update existing lead with new info instead of creating new one
            updated = await lead_service.update_lead(
                str(existing_lead["_id"]), 
                {
                    "name": context.get("name", existing_lead.get("name", "")),
                    "phone": context.get("phone", existing_lead.get("phone", "")),
                    "email": context.get("email", existing_lead.get("email", "")),
                    "service_interest": context.get("service_type", existing_lead.get("service_interest", ""))
                }
            )
            if updated:
                logger.info(f"🔄 Updated existing lead for {chat_id}")
        else:
            logger.info(f"⏭️ No lead data to save or already saved for {chat_id}")
        
        # Check for booking intent
        if "booking" in response.get("intent", "").lower():
            booking_service = BookingService()
            booking = await booking_service.create_from_conversation(
                chat_id, conversation, response
            )
            if booking:
                from services.notification_service import send_booking_notification
                await send_booking_notification(booking)
        
        # Send response via WhatsApp
        whatsapp = WhatsAppService()
        await whatsapp.send_message(chat_id, response["reply"])
        
        # Update conversation
        await conv_service.update(chat_id, {
            "messages": conversation.get("messages", []) + [
                {"role": "user", "content": text, "timestamp": datetime.utcnow().isoformat()},
                {"role": "assistant", "content": response["reply"], "timestamp": datetime.utcnow().isoformat()}
            ],
            "context": context,
            "phase": response.get("phase", "lead_collection"),
            "updated_at": datetime.utcnow().isoformat()
        })
        
        logger.info(f"💾 Updated context for {chat_id}: {context}")
        
    except Exception as e:
        logger.error(f"Message processing error: {str(e)}")
        try:
            whatsapp = WhatsAppService()
            await whatsapp.send_message(
                chat_id, 
                "Sorry, I'm having trouble processing your request. Please try again or contact our support."
            )
        except:
            pass
async def handle_human_handoff(chat_id: str, conversation: Dict):
    """Handle human handoff request"""
    whatsapp = WhatsAppService()
    
    await whatsapp.send_message(
        chat_id,
        "Sure! I'll connect you to our team. Please hold on while I find the best expert for you. 😊"
    )
    
    conv_service = ConversationService()
    await conv_service.update(chat_id, {
        "phase": "human_handoff",
        "handoff_requested_at": datetime.utcnow().isoformat()
    })
    
    from services.notification_service import send_handoff_notification
    await send_handoff_notification(chat_id, conversation)