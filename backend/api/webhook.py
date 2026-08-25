# backend/api/webhook.py
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Dict, Any
import json
import logging
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
        
        # ✅ NEW: Log current context for debugging
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
        
        # ✅ NEW: Extract and save lead data from response
        # ✅ FIXED: Extract and save lead data from response with proper merging
        lead_data = response.get("lead_data", {})
        context = conversation.get("context", {})

    # Ensure collected_fields exists
        if "collected_fields" not in context:
            context["collected_fields"] = []

    # Save lead data to context (preserving existing data)
        if lead_data:
        # Update context with new lead data (don't overwrite existing)
            if lead_data.get("name"):
                context["name"] = lead_data["name"]
                if "name" not in context["collected_fields"]:
                    context["collected_fields"].append("name")
            if lead_data.get("phone"):
                context["phone"] = lead_data["phone"]
                if "phone" not in context["collected_fields"]:
                    context["collected_fields"].append("phone")
            if lead_data.get("email"):
                context["email"] = lead_data["email"]
                if "email" not in context["collected_fields"]:
                    context["collected_fields"].append("email")
            if lead_data.get("service_interest"):
                context["service_type"] = lead_data["service_interest"]
                if "service_interest" not in context["collected_fields"]:
                    context["collected_fields"].append("service_interest")

    # ✅ CRITICAL: Also check for lead data directly from AI response
    # Sometimes the AI puts lead data directly in the response
        if response.get("lead_collected") and not lead_data:
        # Try to extract from the reply text
            reply = response.get("reply", "")
        # Simple extraction for testing
            import re
            name_match = re.search(r"(?:name is |I am |I'm )(\w+)", reply.lower())
            if name_match and not context.get("name"):
                context["name"] = name_match.group(1).capitalize()
                if "name" not in context["collected_fields"]:
                    context["collected_fields"].append("name")

        logger.info(f"📝 Merged context for {chat_id}: {context}")
        
        # Check for booking intent
        if "booking" in response.get("intent", "").lower():
            booking_service = BookingService()
            booking = await booking_service.create_from_conversation(
                chat_id, conversation, response
            )
            if booking:
                # Notify owner
                from services.notification_service import send_booking_notification
                await send_booking_notification(booking)
        
        # Save lead if collected
        lead_service = LeadService()
        if response.get("lead_collected", False):
            lead = await lead_service.save_lead(chat_id, conversation, response)
            if lead:
                # Sync to Google Sheets
                await lead_service.sync_to_google_sheets(lead)
                # Notify owner
                from services.notification_service import send_lead_notification
                await send_lead_notification(lead)
        
        # Send response via WhatsApp
        whatsapp = WhatsAppService()
        await whatsapp.send_message(chat_id, response["reply"])
        
        # ✅ UPDATED: Update conversation with proper context
        await conv_service.update(chat_id, {
            "messages": conversation.get("messages", []) + [
                {"role": "user", "content": text, "timestamp": datetime.utcnow().isoformat()},
                {"role": "assistant", "content": response["reply"], "timestamp": datetime.utcnow().isoformat()}
            ],
            "context": context,  # ✅ Save updated context
            "phase": response.get("phase", "lead_collection"),
            "updated_at": datetime.utcnow().isoformat()
        })
        
        # ✅ NEW: Log what was saved
        logger.info(f"💾 Updated context for {chat_id}: {context}")
        
    except Exception as e:
        logger.error(f"Message processing error: {str(e)}")
        # Send fallback message
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
    from services.notification_service import send_handoff_notification
    await send_handoff_notification(chat_id, conversation)