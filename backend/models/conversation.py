from typing import List, Dict, Optional, Any
from datetime import datetime
from pydantic import BaseModel

class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: str

class Context(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    service_type: Optional[str] = None
    collected_fields: List[str] = []

class Conversation(BaseModel):
    chat_id: str
    messages: List[Message] = []
    language: str = "en"
    context: Dict[str, Any] = {}
    phase: str = "greeting"  # greeting | lead_collection | booking | human_handoff
    handoff_requested_at: Optional[str] = None
    created_at: str
    updated_at: str
    
    class Config:
        schema_extra = {
            "example": {
                "chat_id": "919876543210",
                "messages": [
                    {
                        "role": "user",
                        "content": "I need solar installation",
                        "timestamp": "2026-08-20T10:30:00Z"
                    }
                ],
                "language": "ta",
                "context": {},
                "phase": "lead_collection",
                "created_at": "2026-08-20T10:30:00Z",
                "updated_at": "2026-08-20T10:30:00Z"
            }
        }