import httpx
import base64
import logging
from typing import Optional
from core.config import settings

logger = logging.getLogger(__name__)

class VoiceService:
    def __init__(self):
        self.media_url = "https://graph.facebook.com/v18.0"
        self.access_token = settings.WHATSAPP_ACCESS_TOKEN
    
    async def download_voice(self, media_id: str) -> bytes:
        """Download voice note from WhatsApp"""
        try:
            url = f"{self.media_url}/{media_id}"
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                return response.content
                
        except Exception as e:
            logger.error(f"Error downloading voice: {str(e)}")
            raise
    
    async def transcribe_voice(self, message: dict) -> str:
        """Transcribe voice note to text"""
        try:
            media_id = message.get("voice", {}).get("id")
            if not media_id:
                return ""
            
            # Download voice file
            audio_data = await self.download_voice(media_id)
            
            # Save temporarily
            temp_file = f"/tmp/voice_{media_id}.ogg"
            with open(temp_file, "wb") as f:
                f.write(audio_data)
            
            # Use Speech-to-Text service
            # Option 1: Use Gemini
            if settings.USE_GEMINI and settings.GEMINI_API_KEY:
                import google.generativeai as genai
                genai.configure(api_key=settings.GEMINI_API_KEY)
                
                # Upload audio file
                import pathlib
                audio_file = pathlib.Path(temp_file)
                sample = genai.upload_file(str(audio_file))
                
                model = genai.GenerativeModel("gemini-1.5-pro")
                response = model.generate_content([
                    "Transcribe this voice note accurately. Return only the transcribed text.",
                    sample
                ])
                
                import os
                os.remove(temp_file)
                return response.text
            
            # Option 2: Use OpenAI Whisper
            elif settings.OPENAI_API_KEY:
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                
                with open(temp_file, "rb") as audio:
                    transcript = await client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio,
                        response_format="text"
                    )
                
                import os
                os.remove(temp_file)
                return transcript
            
            else:
                logger.warning("No speech-to-text service configured")
                return ""
                
        except Exception as e:
            logger.error(f"Error transcribing voice: {str(e)}")
            return ""