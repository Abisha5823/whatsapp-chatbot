from typing import Optional
from datetime import datetime
from pydantic import BaseModel

class Lead(BaseModel):
    chat_id: str
    name: str
    phone: str
    email: Optional[str] = None
    service_interest: Optional[str] = None
    source: str = "whatsapp"
    status: str = "new"  # new | contacted | converted | lost
    business_type: Optional[str] = None
    conversation_summary: Optional[str] = None
    created_at: str
    updated_at: str
    
    class Config:
        schema_extra = {
            "example": {
                "chat_id": "919876543210",
                "name": "Ramesh Kumar",
                "phone": "9876543210",
                "email": "ramesh@email.com",
                "service_interest": "Solar Installation",
                "source": "whatsapp",
                "status": "new",
                "business_type": "solar",
                "conversation_summary": "Interested in 5kW solar system",
                "created_at": "2026-08-20T10:35:00Z",
                "updated_at": "2026-08-20T10:35:00Z"
            }
        }

class LeadCreate(BaseModel):
    chat_id: str
    name: str
    phone: str
    email: Optional[str] = None
    service_interest: Optional[str] = None
    business_type: Optional[str] = None
    conversation_summary: Optional[str] = None