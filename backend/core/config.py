from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # WhatsApp Cloud API
    WHATSAPP_ACCESS_TOKEN: str
    WHATSAPP_PHONE_NUMBER_ID: str
    WHATSAPP_BUSINESS_ID: Optional[str] = None
    VERIFY_TOKEN: str
    
    # AI Provider
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.0-flash-exp"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4-turbo"
    USE_GEMINI: bool = True
    
    # MongoDB
    MONGODB_URI: str
    MONGODB_DB_NAME: str = "whatsapp_chatbot"
    MONGODB_COLLECTION_CONVERSATIONS: str = "conversations"
    MONGODB_COLLECTION_LEADS: str = "leads"
    MONGODB_COLLECTION_BOOKINGS: str = "bookings"
    
    # Google Sheets
    GOOGLE_SHEETS_CREDENTIALS: Optional[str] = None
    GOOGLE_SHEETS_SPREADSHEET_ID: Optional[str] = None
    
    # Notifications
    OWNER_EMAIL: Optional[str] = None
    OWNER_PHONE: Optional[str] = None
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAIL_SENDER: Optional[str] = None
    
    # Business Configuration
    BUSINESS_NAME: str = "Solar Solutions"
    ASSISTANT_NAME: str = "Solar Assistant"
    BUSINESS_SCHEDULE: str = "Mon-Sat 9AM-6PM"
    
    # Services
    SERVICES: str = "Solar Installation, Battery Systems, Inverters, Maintenance"
    
    # General
    PORT: int = 8000
    DEBUG: bool = False
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()