# backend/api/webhook.py
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Dict, Any
import json
import logging
import re
from datetime import datetime

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
        
        entry = body.get("entry", [])
        for e in entry:
            changes = e.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                messages = value.get("messages", [])
                
                for message in messages:
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
        
        # ✅ EXTRACT ALL DATA FROM USER MESSAGE
        
        # Extract Name (multiple patterns)
        name_patterns = [
            r"(?:my name is |i am |i'm |name is |this is )([A-Za-z\s]+)",
            r"^([A-Za-z\s]{2,20})$"  # Just a name
        ]
        for pattern in name_patterns:
            name_match = re.search(pattern, text, re.IGNORECASE)
            if name_match and "name" not in context["collected_fields"]:
                name = name_match.group(1).strip().title()
                if len(name) > 1 and len(name) < 30:
                    context["name"] = name
                    context["collected_fields"].append("name")
                    logger.info(f"👤 Extracted name: {context['name']}")
                    break
        
        # Extract Phone
        phone_match = re.search(r'(\+?91)?[6-9]\d{9}', text)
        if phone_match and "phone" not in context["collected_fields"]:
            phone = phone_match.group(0)
            if not phone.startswith('+'):
                phone = '+91' + phone if len(phone) == 10 else phone
            context["phone"] = phone
            context["collected_fields"].append("phone")
            logger.info(f"📱 Extracted phone: {context['phone']}")
        
        # Extract Email
        email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
        if email_match and "email" not in context["collected_fields"]:
            context["email"] = email_match.group(0).lower()
            context["collected_fields"].append("email")
            logger.info(f"📧 Extracted email: {context['email']}")
        
        # Extract Date (YYYY-MM-DD)
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', text)
        if date_match and "preferred_date" not in context["collected_fields"]:
            context["preferred_date"] = date_match.group(0)
            context["collected_fields"].append("preferred_date")
            logger.info(f"📅 Extracted date: {context['preferred_date']}")
        
        # Extract Date (DD/MM/YYYY)
        date_match2 = re.search(r'(\d{2}/\d{2}/\d{4})', text)
        if date_match2 and "preferred_date" not in context["collected_fields"]:
            context["preferred_date"] = date_match2.group(0)
            context["collected_fields"].append("preferred_date")
            logger.info(f"📅 Extracted date: {context['preferred_date']}")
        
        # Extract Time (HH:MM AM/PM)
        time_match = re.search(r'(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))', text)
        if time_match and "preferred_time" not in context["collected_fields"]:
            context["preferred_time"] = time_match.group(0)
            context["collected_fields"].append("preferred_time")
            logger.info(f"🕐 Extracted time: {context['preferred_time']}")
        
        # Extract Time (e.g., "9am")
        time_match2 = re.search(r'(\d{1,2})\s*(?:AM|PM|am|pm)', text)
        if time_match2 and "preferred_time" not in context["collected_fields"]:
            time_str = time_match2.group(0)
            if ':' not in time_str:
                if 'AM' in time_str:
                    time_str = time_str.replace('AM', ':00 AM')
                elif 'PM' in time_str:
                    time_str = time_str.replace('PM', ':00 PM')
            context["preferred_time"] = time_str
            context["collected_fields"].append("preferred_time")
            logger.info(f"🕐 Extracted time: {context['preferred_time']}")
        
        # Extract Mode
        if "offline" in text.lower() and "mode" not in context["collected_fields"]:
            context["mode"] = "offline"
            context["collected_fields"].append("mode")
            logger.info(f"📍 Extracted mode: offline")
        elif "online" in text.lower() and "mode" not in context["collected_fields"]:
            context["mode"] = "online"
            context["collected_fields"].append("mode")
            logger.info(f"📍 Extracted mode: online")
        
        # ✅ Check if user confirmed booking
        is_confirmation = any(word in text.lower() for word in ["yes", "confirm", "ok", "sure", "confirm pannalama", "go ahead"])
        
        # ✅ Update conversation
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
        
        # ✅ Check if booking is confirmed
        booking_confirmed = is_confirmation and "preferred_date" in context.get("collected_fields", [])
        
        if booking_confirmed:
            logger.info(f"✅ Booking confirmed by user for {chat_id}")
            
            # Create booking
            booking_service = BookingService()
            booking_data = {
                "chat_id": chat_id,
                "customer_name": context.get("name", "Unknown"),
                "whatsapp_number": context.get("phone", ""),
                "service_type": context.get("service_type", "solar installation"),
                "reason": context.get("reason", ""),
                "preferred_date": context.get("preferred_date", ""),
                "preferred_time": context.get("preferred_time", ""),
                "mode": context.get("mode", "offline"),
                "language_preference": language,
                "booking_status": "confirmed"
            }
            
            booking = await booking_service.create_manual_booking(booking_data)
            if booking:
                # Send email notification
                from services.notification_service import send_booking_notification
                await send_booking_notification(booking)
                logger.info(f"✅ Booking notification sent for {context.get('name')}")
        
        # Save lead ONLY ONCE
        lead_service = LeadService()
        existing_lead = await lead_service.get_lead_by_chat_id(chat_id)
        has_lead_data = (
            "name" in context.get("collected_fields", []) and 
            "phone" in context.get("collected_fields", [])
        )
        
        if has_lead_data and not existing_lead:
            lead = await lead_service.save_lead(chat_id, conversation, response)
            if lead:
                await lead_service.sync_to_google_sheets(lead)
                from services.notification_service import send_lead_notification
                await send_lead_notification(lead)
                logger.info(f"✅ New lead saved: {lead.name}")
        
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