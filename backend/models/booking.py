from typing import Optional
from datetime import datetime
from pydantic import BaseModel

class Booking(BaseModel):
    chat_id: str
    customer_name: str
    whatsapp_number: str
    service_type: str
    reason: Optional[str] = None
    preferred_date: str
    preferred_time: str
    mode: str  # online | offline
    language_preference: str = "English"
    booking_status: str = "pending"  # pending | confirmed | completed | cancelled
    business_id: Optional[str] = None
    created_at: str
    updated_at: str
    
    class Config:
        schema_extra = {
            "example": {
                "chat_id": "919876543210",
                "customer_name": "Ramesh Kumar",
                "whatsapp_number": "9876543210",
                "service_type": "Solar Installation",
                "reason": "Residential 5kW system",
                "preferred_date": "2026-08-25",
                "preferred_time": "10:00 AM",
                "mode": "offline",
                "language_preference": "Tamil",
                "booking_status": "confirmed",
                "business_id": "solar_business_001",
                "created_at": "2026-08-20T10:40:00Z",
                "updated_at": "2026-08-20T10:40:00Z"
            }
        }

class BookingCreate(BaseModel):
    chat_id: str
    customer_name: str
    whatsapp_number: str
    service_type: str
    reason: Optional[str] = None
    preferred_date: str
    preferred_time: str
    mode: str
    language_preference: str = "English"
    business_id: Optional[str] = None