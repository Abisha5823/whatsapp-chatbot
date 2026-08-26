import gspread
from google.oauth2.service_account import Credentials
from typing import Dict, Any
import logging
import json
from datetime import datetime
from core.config import settings
import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

class GoogleSheetsService:
    def __init__(self):
        self.client = None
        self.sheet = None
        self.lead_sheet = None
        self.booking_sheet = None
        self.initialize()



    
    
    def initialize(self):
        """Initialize Google Sheets connection"""
        try:
            credentials_json = settings.GOOGLE_SHEETS_CREDENTIALS
            
            if not credentials_json:
                logger.warning("Google Sheets credentials not configured")
                return
            
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive',
                'https://www.googleapis.com/auth/spreadsheets'
            ]
            
            # ✅ Check if it's a JSON string or file path
            creds = None
            if credentials_json.strip().startswith('{'):
                # It's a JSON string (from Render environment variable)
                try:
                    creds_dict = json.loads(credentials_json)
                    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
                    logger.info("✅ Loaded credentials from JSON string")
                except json.JSONDecodeError as e:
                    logger.error(f"❌ Failed to parse JSON credentials: {str(e)}")
                    return
            else:
                # It's a file path (local development)
                try:
                    creds = Credentials.from_service_account_file(credentials_json, scopes=scope)
                    logger.info("✅ Loaded credentials from file path")
                except Exception as e:
                    logger.error(f"❌ Failed to load credentials from file: {str(e)}")
                    return
            
            if not creds:
                logger.error("❌ No valid credentials found")
                return
            
            self.client = gspread.authorize(creds)
            
            if not settings.GOOGLE_SHEETS_SPREADSHEET_ID:
                logger.warning("Google Sheets Spreadsheet ID not configured")
                return
            
            spreadsheet = self.client.open_by_key(settings.GOOGLE_SHEETS_SPREADSHEET_ID)
            
            # ✅ Get or create Leads worksheet
            try:
                self.lead_sheet = spreadsheet.worksheet("Leads")
                logger.info("✅ Leads worksheet found")
            except gspread.exceptions.WorksheetNotFound:
                self.lead_sheet = spreadsheet.add_worksheet(
                    title="Leads", 
                    rows=1000, 
                    cols=10
                )
                # Add headers
                headers = ["created_at", "chat_id", "customer_name", "phone", "email", 
                          "service_interest", "source", "status", "business_type", "conversation_summary"]
                self.lead_sheet.append_row(headers)
                logger.info("✅ Leads worksheet created with headers")
            
            # ✅ Get or create Bookings worksheet
            try:
                self.booking_sheet = spreadsheet.worksheet("Bookings")
                logger.info("✅ Bookings worksheet found")
            except gspread.exceptions.WorksheetNotFound:
                self.booking_sheet = spreadsheet.add_worksheet(
                    title="Bookings", 
                    rows=1000, 
                    cols=12
                )
                # Add headers
                headers = ["created_at", "chat_id", "customer_name", "whatsapp_number", "email", "service_type", "reason", "preferred_date", "preferred_time", "mode", "language_preference", "booking_status", "business_id", "updated_at"]
                self.booking_sheet.append_row(headers)
                logger.info("✅ Bookings worksheet created with headers")
            
            logger.info("🎉 Google Sheets initialized successfully!")
                
        except Exception as e:
            logger.error(f"❌ Google Sheets init error: {str(e)}")
    
    async def append_lead(self, lead_data: Dict[str, Any]) -> bool:
        """Append lead to Google Sheets"""
        try:
            if not self.lead_sheet:
                logger.warning("⚠️ Lead sheet not available")
                return False
            
            # ✅ Ensure we have a created_at
            created_at = lead_data.get("created_at")
            if not created_at:
                created_at = datetime.now().isoformat()
            
            row = [
                created_at,
                lead_data.get("chat_id", ""),
                lead_data.get("name", ""),
                lead_data.get("phone", ""),
                lead_data.get("email", ""),
                lead_data.get("service_interest", ""),
                lead_data.get("source", "whatsapp"),
                lead_data.get("status", "new"),
                lead_data.get("business_type", ""),
                lead_data.get("conversation_summary", "")[:500]  # Truncate if needed
            ]
            
            self.lead_sheet.append_row(row)
            logger.info(f"✅ Lead appended to Google Sheets: {lead_data.get('name')}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Google Sheets append lead error: {str(e)}")
            return False
    
    async def append_booking(self, booking_data: Dict[str, Any]) -> bool:
        """Append booking to Google Sheets"""
        try:
            if not self.booking_sheet:
                logger.warning("⚠️ Booking sheet not available")
                return False
            
            # ✅ Ensure we have a created_at
            created_at = booking_data.get("created_at")
            if not created_at:
                created_at = datetime.now().isoformat()
            
            # ✅ Build row with email column (Column E)
            row = [
                created_at,                                          # Column A
                booking_data.get("chat_id", ""),                     # Column B
                booking_data.get("customer_name", ""),               # Column C
                booking_data.get("whatsapp_number", ""),             # Column D
                booking_data.get("email", ""),                       # ✅ Column E - EMAIL
                booking_data.get("service_type", ""),                # Column F
                booking_data.get("reason", ""),                      # Column G
                booking_data.get("preferred_date", ""),              # Column H
                booking_data.get("preferred_time", ""),              # Column I
                booking_data.get("mode", ""),                        # Column J
                booking_data.get("language_preference", "en"),       # Column K
                booking_data.get("booking_status", "pending"),       # Column L
                booking_data.get("business_id", ""),                 # Column M
                booking_data.get("updated_at", "")                   # Column N
            ]
            
            self.booking_sheet.append_row(row)
            logger.info(f"✅ Booking appended to Google Sheets: {booking_data.get('customer_name')} (Email: {booking_data.get('email')})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Google Sheets append booking error: {str(e)}")
            return False
    
    async def get_all_leads(self) -> list:
        """Get all leads from Google Sheets"""
        try:
            if not self.lead_sheet:
                return []
            
            records = self.lead_sheet.get_all_records()
            return records
            
        except Exception as e:
            logger.error(f"❌ Error fetching leads from sheets: {str(e)}")
            return []
    
    async def get_all_bookings(self) -> list:
        """Get all bookings from Google Sheets"""
        try:
            if not self.booking_sheet:
                return []
            
            records = self.booking_sheet.get_all_records()
            return records
            
        except Exception as e:
            logger.error(f"❌ Error fetching bookings from sheets: {str(e)}")
            return []
    
    async def clear_lead_sheet(self) -> bool:
        """Clear all data from lead sheet (keep headers)"""
        try:
            if not self.lead_sheet:
                return False
            
            # Get all values
            all_values = self.lead_sheet.get_all_values()
            if len(all_values) > 1:
                # Keep only headers (row 1)
                self.lead_sheet.clear()
                if all_values:
                    self.lead_sheet.append_row(all_values[0])
                logger.info("✅ Lead sheet cleared (headers preserved)")
            return True
        except Exception as e:
            logger.error(f"❌ Error clearing lead sheet: {str(e)}")
            return False