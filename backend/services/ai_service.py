import os
import json
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
            
            # ✅ Build lead collection status
            lead_info = conversation.get("context", {})
            collected_fields = lead_info.get("collected_fields", [])
            
            # Check if lead info is collected
            lead_collected = self._is_lead_collected(conversation)
            
            # Build system prompt
            if phase == "booking" or self._is_booking_intent(message):
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
            
            # ✅ Build prompt with lead collection status
            prompt = f"""
            {system_prompt}
            
            ### Business Context from Knowledge Base:
            {rag_context if rag_context else "No specific context found. Use general knowledge."}
            
            ### Conversation History:
            {history}
            
            ### User Message:
            {message}
            
            ### Current Phase: {phase}
            ### Lead Collected: {lead_collected}
            ### Language: {language}
            
            ### Lead Collection Status:
            - Name collected: {'name' in collected_fields}
            - Phone collected: {'phone' in collected_fields}
            - Email collected: {'email' in collected_fields}
            - Service Interest collected: {'service_interest' in collected_fields}
            - Current lead data: {json.dumps(lead_info)}
            
            **IMPORTANT RULES:**
            1. Only ask for information you don't already have!
            2. If name is already collected, don't ask for it again.
            3. If phone is already collected, don't ask for it again.
            4. If both name and phone are collected, move to answering their question.
            5. Be natural and conversational - don't sound like a robot listing fields.
            
            Provide a response that:
            1. Answers the user's question using the context
            2. Adapts to the language ({language})
            3. If phase is lead_collection, collect name, phone, email naturally
            4. If booking intent, follow booking flow
            5. Be warm and conversational
            
            Return your response as JSON with the following structure:
            {{
                "reply": "Your response text",
                "intent": "booking|lead|general|calculation",
                "phase": "lead_collection|booking|general|human_handoff",
                "lead_collected": true/false,
                "lead_data": {{"name": "", "phone": "", "email": "", "service_interest": ""}},
                "booking_data": {{"service": "", "date": "", "time": "", "mode": ""}},
                "needs_human_handoff": true/false
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
                # Extract JSON from response
                response_text = response.strip()
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                result = json.loads(response_text)
            except json.JSONDecodeError:
                # Fallback: wrap in proper structure
                result = {
                    "reply": response,
                    "intent": "general",
                    "phase": phase,
                    "lead_collected": False,
                    "lead_data": {},
                    "booking_data": {},
                    "needs_human_handoff": False
                }
            
            # ✅ If lead data was extracted, mark as collected in result
            if result.get("lead_data"):
                for field in ["name", "phone", "email", "service_interest"]:
                    if result["lead_data"].get(field):
                        result["lead_collected"] = True
            
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
        return bool(
            "name" in collected_fields and 
            "phone" in collected_fields
        )
    
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
        for msg in messages[-10:]:  # Last 10 messages
            role = "User" if msg["role"] == "user" else "Assistant"
            history.append(f"{role}: {msg['content']}")
        
        return "\n".join(history)