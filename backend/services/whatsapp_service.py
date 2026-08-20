import httpx
from typing import Dict, Any, Optional
import logging
from core.config import settings

logger = logging.getLogger(__name__)

class WhatsAppService:
    def __init__(self):
        self.base_url = "https://graph.facebook.com/v18.0"
        self.phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self.access_token = settings.WHATSAPP_ACCESS_TOKEN
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
    
    async def send_message(self, to: str, text: str) -> Dict[str, Any]:
        """Send a text message via WhatsApp Cloud API"""
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        
        # Ensure phone number format
        if not to.startswith("+"):
            to = f"+{to}"
        
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text[:4096]}  # WhatsApp text limit
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=payload
                )
                response.raise_for_status()
                logger.info(f"Message sent to {to}")
                return response.json()
                
        except httpx.HTTPStatusError as e:
            logger.error(f"WhatsApp API error: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}")
            raise
    
    async def send_interactive_message(self, to: str, header: str, body: str, buttons: list):
        """Send an interactive message with buttons"""
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        
        if not to.startswith("+"):
            to = f"+{to}"
        
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "header": {"type": "text", "text": header},
                "body": {"text": body},
                "action": {
                    "buttons": buttons
                }
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=payload
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error sending interactive message: {str(e)}")
            raise
    
    async def send_location(self, to: str, latitude: float, longitude: float, name: str = "", address: str = ""):
        """Send a location message"""
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        
        if not to.startswith("+"):
            to = f"+{to}"
        
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "location",
            "location": {
                "latitude": latitude,
                "longitude": longitude,
                "name": name,
                "address": address
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=payload
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error sending location: {str(e)}")
            raise
    
    async def send_template_message(self, to: str, template_name: str, components: Optional[Dict] = None):
        """Send a template message"""
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        
        if not to.startswith("+"):
            to = f"+{to}"
        
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": "en"}
            }
        }
        
        if components:
            payload["template"]["components"] = components
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=payload
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error sending template: {str(e)}")
            raise