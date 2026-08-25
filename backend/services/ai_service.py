import os
import json
import re
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime
import google.generativeai as genai
from openai import AsyncOpenAI

from services.openrouter_service import OpenRouterService
from core.config import settings
from services.rag_service import RAGService
from prompts.system_prompt import get_system_prompt, get_booking_prompt, get_lead_collection_prompt
from utils.helpers import detect_language, format_response_for_language

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        self.rag_service = RAGService()
        self.use_gemini = settings.USE_GEMINI
        self.use_openrouter = settings.USE_OPENROUTER

        if self.use_openrouter:
            self.openrouter = OpenRouterService()
        elif self.use_gemini:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.gemini_model = genai.GenerativeModel(
                settings.GEMINI_MODEL,
                generation_config={
                    "temperature": 0.7,
                    "top_p": 0.95,
                    "top_k": 40,
                    "max_output_tokens": 2048,
                }
            )
        else:
            self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    
    async def generate_response(self, message: str, conversation: Dict) -> Dict[str, Any]:
        """Generate AI response with RAG context"""
        try:
            # Detect language
            language = detect_language(message)
            conversation["language"] = language
            
            # Get RAG context
            rag_context = await self.rag_service.query(message)
            
            # Determine phase
            phase = conversation.get("phase", "greeting")
            
            # ✅ Get context and collected fields
            context = conversation.get("context", {})
            collected_fields = context.get("collected_fields", [])
            
            # ✅ Extract email from message if present
            email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', message)
            if email_match and "email" not in collected_fields:
                context["email"] = email_match.group(0)
                collected_fields.append("email")
                logger.info(f"📧 Extracted email: {context['email']}")

            # ✅ Extract date/time from message
            date_keywords = ["tomorrow", "today", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            for keyword in date_keywords:
                if keyword in message.lower() and "preferred_date" not in collected_fields:
                    context["preferred_date"] = keyword
                    collected_fields.append("preferred_date")
                    break
            
            # ✅ Extract time from message (e.g., "10am", "10:00", "10")
            time_match = re.search(r'(\d{1,2})\s*(?:am|pm|:|o\'clock)', message.lower())
            if time_match and "preferred_time" not in collected_fields:
                time_str = time_match.group(0)
                context["preferred_time"] = time_str
                collected_fields.append("preferred_time")
                logger.info(f"🕐 Extracted time: {context['preferred_time']}")

            # ✅ Extract mode (online/offline)
            if "offline" in message.lower() and "mode" not in collected_fields:
                context["mode"] = "offline"
                collected_fields.append("mode")
            elif "online" in message.lower() and "mode" not in collected_fields:
                context["mode"] = "online"
                collected_fields.append("mode")

            # ✅ Update context with extracted data
            conversation["context"] = context
            
            # Check if lead info is collected (name + phone)
            lead_collected = "name" in collected_fields and "phone" in collected_fields
            
            # Build system prompt
            if "booking" in collected_fields or self._is_booking_intent(message):
                system_prompt = get_booking_prompt(settings.BUSINESS_NAME, settings.ASSISTANT_NAME)
                phase = "booking"
            elif not lead_collected:
                system_prompt = get_lead_collection_prompt(settings.BUSINESS_NAME, settings.ASSISTANT_NAME)
                phase = "lead_collection"
            else:
                system_prompt = get_system_prompt(
                    settings.BUSINESS_NAME,
                    settings.ASSISTANT_NAME,
                    settings.BUSINESS_SCHEDULE,
                    settings.SERVICES
                )
                phase = "general"
            
            # Build conversation history
            history = self._format_conversation_history(conversation.get("messages", []))
            
            # ✅ Build context summary for AI
            context_summary = self._build_context_summary(context, collected_fields)
            
            # ✅ Build prompt with full context
            prompt = f"""
            {system_prompt}
            
            ### Business Context from Knowledge Base:
            {rag_context if rag_context else "No specific context found. Use general knowledge."}
            
            ### Conversation History:
            {history}
            
            ### User Message:
            {message}
            
            ### Current Phase: {phase}
            ### Language: {language}
            
            ### ✅ WHAT I ALREADY KNOW ABOUT THIS USER:
            {context_summary}
            
            ### ✅ WHAT I HAVE ALREADY COLLECTED:
            {', '.join(collected_fields) if collected_fields else 'Nothing yet'}
            
            ### ✅ IMPORTANT RULES (STRICTLY FOLLOW):
            1. **NEVER ask for information I already have!**
            2. Look at "WHAT I ALREADY KNOW" above.
            3. If I already have name, phone, email, service_type - DO NOT ask again.
            4. If the user says "I already said that" - apologize and move on.
            5. Use the information I already have to answer their question.
            6. Only ask for ONE piece of NEW information at a time.
            7. If the user provides information I already have, acknowledge it and move forward.
            
            ### Instructions:
            1. Answer the user's question using the context
            2. Adapt to the language ({language})
            3. If booking intent, follow booking flow
            4. Be warm and conversational
            
            Return your response as JSON:
            {{
                "reply": "Your response text",
                "intent": "booking|lead|general|calculation",
                "phase": "lead_collection|booking|general|human_handoff",
                "lead_collected": {str(lead_collected).lower()},
                "lead_data": {{"name": "{context.get('name', '')}", "phone": "{context.get('phone', '')}", "email": "{context.get('email', '')}", "service_interest": "{context.get('service_type', '')}"}},
                "booking_data": {{"service": "", "date": "{context.get('preferred_date', '')}", "time": "{context.get('preferred_time', '')}", "mode": "{context.get('mode', '')}"}},
                "needs_human_handoff": false
            }}
            """
            
            # Generate response
            if self.use_openrouter:
                response = await self.openrouter.generate_response(prompt)
            elif self.use_gemini:
                response = await self._call_gemini(prompt)
            else:
                response = await self._call_openai(prompt)
            
            # Parse response
            try:
                response_text = response.strip()
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                result = json.loads(response_text)
            except json.JSONDecodeError:
                result = {
                    "reply": response,
                    "intent": "general",
                    "phase": phase,
                    "lead_collected": lead_collected,
                    "lead_data": {},
                    "booking_data": {},
                    "needs_human_handoff": False
                }
            
            # ✅ Ensure lead_data includes context values
            if not result.get("lead_data"):
                result["lead_data"] = {}
            if not result["lead_data"].get("name") and context.get("name"):
                result["lead_data"]["name"] = context["name"]
            if not result["lead_data"].get("phone") and context.get("phone"):
                result["lead_data"]["phone"] = context["phone"]
            if not result["lead_data"].get("email") and context.get("email"):
                result["lead_data"]["email"] = context["email"]
            if not result["lead_data"].get("service_interest") and context.get("service_type"):
                result["lead_data"]["service_interest"] = context["service_type"]
            
            # Format response for language
            result["reply"] = format_response_for_language(result["reply"], language)
            
            return result
            
        except Exception as e:
            logger.error(f"AI service error: {str(e)}")
            return {
                "reply": "Sorry, I'm having trouble processing your request. Please try again or contact our support team.",
                "intent": "error",
                "phase": "general",
                "lead_collected": False,
                "lead_data": {},
                "booking_data": {},
                "needs_human_handoff": True
            }
    
    def _build_context_summary(self, context: Dict, collected_fields: List[str]) -> str:
        """Build a human-readable summary of what we know about the user"""
        summary = []
        if "name" in collected_fields and context.get("name"):
            summary.append(f"✅ Name: {context['name']}")
        if "phone" in collected_fields and context.get("phone"):
            summary.append(f"✅ Phone: {context['phone']}")
        if "email" in collected_fields and context.get("email"):
            summary.append(f"✅ Email: {context['email']}")
        if "service_type" in collected_fields and context.get("service_type"):
            summary.append(f"✅ Service: {context['service_type']}")
        if "preferred_date" in collected_fields and context.get("preferred_date"):
            summary.append(f"✅ Date: {context['preferred_date']}")
        if "preferred_time" in collected_fields and context.get("preferred_time"):
            summary.append(f"✅ Time: {context['preferred_time']}")
        if "mode" in collected_fields and context.get("mode"):
            summary.append(f"✅ Mode: {context['mode']}")
        
        if not summary:
            return "Nothing collected yet."
        return "\n".join(summary)
    
    async def _call_gemini(self, prompt: str) -> str:
        """Call Gemini API"""
        try:
            response = await self.gemini_model.generate_content_async(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Gemini error: {str(e)}")
            raise
    
    async def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API"""
        try:
            response = await self.openai_client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant. Return responses in JSON format."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1500
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI error: {str(e)}")
            raise
    
    def _is_lead_collected(self, conversation: Dict) -> bool:
        """Check if lead info is collected"""
        context = conversation.get("context", {})
        collected_fields = context.get("collected_fields", [])
        return "name" in collected_fields and "phone" in collected_fields
    
    def _is_booking_intent(self, message: str) -> bool:
        """Check if message indicates booking intent"""
        booking_keywords = [
            "book", "appointment", "schedule", "slot", "reserve",
            "fixed", "appoint", "meeting", "consultation", "visit",
            "when available", "come", "go", "visit"
        ]
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in booking_keywords)
    
    def _format_conversation_history(self, messages: List[Dict]) -> str:
        """Format conversation history for prompt"""
        if not messages:
            return "No previous conversation."
        
        history = []
        for msg in messages[-10:]:
            role = "User" if msg["role"] == "user" else "Assistant"
            history.append(f"{role}: {msg['content']}")
        
        return "\n".join(history)