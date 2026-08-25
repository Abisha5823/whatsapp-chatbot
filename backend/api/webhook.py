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
        
        # ✅ If type is missing but text exists, assume it's a text message
        if not msg_type and message.get("text"):
            msg_type = "text"
        
        # Handle different message types
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
        
        # Get or create conversation
        conv_service = ConversationService()
        conversation = await conv_service.get_or_create(chat_id)
        
        # Detect language
        from utils.helpers import detect_language
        language = detect_language(text)
        conversation["language"] = language
        
        # ✅ Get context and ensure collected_fields exists
        context = conversation.get("context", {})
        if "collected_fields" not in context:
            context["collected_fields"] = []
        
        # ✅ ✅ ✅ EXTRACT EMAIL FROM MESSAGE
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        email_match = re.search(email_pattern, text)
        if email_match and "email" not in context["collected_fields"]:
            context["email"] = email_match.group(0).lower()
            context["collected_fields"].append("email")
            logger.info(f"📧 Extracted email: {context['email']}")
        
        # ✅ ✅ ✅ EXTRACT PHONE NUMBER FROM MESSAGE
        phone_pattern = r'(\+?91)?[6-9]\d{9}'
        phone_match = re.search(phone_pattern, text)
        if phone_match and "phone" not in context["collected_fields"]:
            phone = phone_match.group(0)
            if not phone.startswith('+'):
                phone = '+91' + phone if len(phone) == 10 else phone
            context["phone"] = phone
            context["collected_fields"].append("phone")
            logger.info(f"📱 Extracted phone: {context['phone']}")
        
        # ✅ ✅ ✅ EXTRACT NAME (simple version)
        name_patterns = [
            r"(?:my name is |i am |i'm |name is |this is )([A-Za-z\s]+)",
            r"^([A-Za-z\s]+)$"  # If message is just a name
        ]
        for pattern in name_patterns:
            name_match = re.search(pattern, text.lower())
            if name_match and "name" not in context["collected_fields"]:
                name = name_match.group(1).strip().title()
                if len(name) > 1 and len(name) < 30:  # Reasonable name length
                    context["name"] = name
                    context["collected_fields"].append("name")
                    logger.info(f"👤 Extracted name: {context['name']}")
                    break
        
        # ✅ ✅ ✅ EXTRACT DATE
        date_keywords = ["tomorrow", "today", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for keyword in date_keywords:
            if keyword in text.lower() and "preferred_date" not in context["collected_fields"]:
                context["preferred_date"] = keyword
                context["collected_fields"].append("preferred_date")
                logger.info(f"📅 Extracted date: {context['preferred_date']}")
                break
        
        # ✅ ✅ ✅ EXTRACT TIME
        time_pattern = r'(\d{1,2})\s*(?:am|pm|:|o\'clock|\s*to\s*)'
        time_match = re.search(time_pattern, text.lower())
        if time_match and "preferred_time" not in context["collected_fields"]:
            time_str = time_match.group(0)
            # Clean up time format
            time_str = time_str.replace('o clock', '').strip()
            context["preferred_time"] = time_str
            context["collected_fields"].append("preferred_time")
            logger.info(f"🕐 Extracted time: {context['preferred_time']}")
        
        # ✅ ✅ ✅ EXTRACT MODE (online/offline)
        if "offline" in text.lower() and "mode" not in context["collected_fields"]:
            context["mode"] = "offline"
            context["collected_fields"].append("mode")
            logger.info(f"📍 Extracted mode: offline")
        elif "online" in text.lower() and "mode" not in context["collected_fields"]:
            context["mode"] = "online"
            context["collected_fields"].append("mode")
            logger.info(f"📍 Extracted mode: online")
        
        # ✅ Save extracted data back to conversation
        conversation["context"] = context
        
        # ✅ Log current context for debugging
        logger.info(f"📝 Current context for {chat_id}: {conversation.get('context', {})}")
        
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
        
        # ✅ Extract lead data from response
        lead_data = response.get("lead_data", {})
        
        # ✅ Save lead data to context (preserving existing data)
        if lead_data:
            if lead_data.get("name") and "name" not in context["collected_fields"]:
                context["name"] = lead_data["name"]
                context["collected_fields"].append("name")
            if lead_data.get("phone") and "phone" not in context["collected_fields"]:
                context["phone"] = lead_data["phone"]
                context["collected_fields"].append("phone")
            if lead_data.get("email") and "email" not in context["collected_fields"]:
                context["email"] = lead_data["email"]
                context["collected_fields"].append("email")
            if lead_data.get("service_interest") and "service_interest" not in context["collected_fields"]:
                context["service_type"] = lead_data["service_interest"]
                context["collected_fields"].append("service_interest")
        
        # ✅ If AI says lead is collected but we don't have data, try to extract from reply
        if response.get("lead_collected") and not lead_data:
            reply = response.get("reply", "")
            # Try to extract email from reply (user might have said it)
            email_match = re.search(email_pattern, reply)
            if email_match and "email" not in context["collected_fields"]:
                context["email"] = email_match.group(0).lower()
                context["collected_fields"].append("email")
                logger.info(f"📧 Extracted email from reply: {context['email']}")
        
        logger.info(f"📝 Merged context for {chat_id}: {context}")
        
        # Check for booking intent
        if "booking" in response.get("intent", "").lower():
            booking_service = BookingService()
            booking = await booking_service.create_from_conversation(
                chat_id, conversation, response
            )
            if booking:
                from services.notification_service import send_booking_notification
                await send_booking_notification(booking)
        
        # Save lead if collected
        lead_service = LeadService()
        if response.get("lead_collected", False) or len(context.get("collected_fields", [])) >= 2:
            lead = await lead_service.save_lead(chat_id, conversation, response)
            if lead:
                await lead_service.sync_to_google_sheets(lead)
                from services.notification_service import send_lead_notification
                await send_lead_notification(lead)
        
        # Send response via WhatsApp
        whatsapp = WhatsAppService()
        await whatsapp.send_message(chat_id, response["reply"])
        
        # ✅ Update conversation with proper context
        await conv_service.update(chat_id, {
            "messages": conversation.get("messages", []) + [
                {"role": "user", "content": text, "timestamp": datetime.utcnow().isoformat()},
                {"role": "assistant", "content": response["reply"], "timestamp": datetime.utcnow().isoformat()}
            ],
            "context": context,
            "phase": response.get("phase", "lead_collection"),
            "updated_at": datetime.utcnow().isoformat()
        })
        
        # ✅ Log what was saved
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