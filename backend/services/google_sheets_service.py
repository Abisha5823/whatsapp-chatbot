import gspread
from google.oauth2.service_account import Credentials
from typing import Dict, Any
import logging
from core.config import settings

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
            if not settings.GOOGLE_SHEETS_CREDENTIALS:
                logger.warning("Google Sheets credentials not configured")
                return
            
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive',
                'https://www.googleapis.com/auth/spreadsheets'
            ]
            
            creds = Credentials.from_service_account_file(
                settings.GOOGLE_SHEETS_CREDENTIALS, 
                scopes=scope
            )
            self.client = gspread.authorize(creds)
            
            if settings.GOOGLE_SHEETS_SPREADSHEET_ID:
                spreadsheet = self.client.open_by_key(
                    settings.GOOGLE_SHEETS_SPREADSHEET_ID
                )
                
                # Get or create worksheets
                try:
                    self.lead_sheet = spreadsheet.worksheet("Leads")
                except gspread.exceptions.WorksheetNotFound:
                    self.lead_sheet = spreadsheet.add_worksheet(
                        title="Leads", 
                        rows=1000, 
                        cols=10
                    )
                    # Add headers
                    headers = ["Chat ID", "Name", "Phone", "Email", "Service Interest", 
                              "Source", "Status", "Business Type", "Created At", "Summary"]
                    self.lead_sheet.append_row(headers)
                
                try:
                    self.booking_sheet = spreadsheet.worksheet("Bookings")
                except gspread.exceptions.WorksheetNotFound:
                    self.booking_sheet = spreadsheet.add_worksheet(
                        title="Bookings", 
                        rows=1000, 
                        cols=12
                    )
                    # Add headers
                    headers = ["Chat ID", "Customer Name", "Phone", "Service", "Reason",
                              "Date", "Time", "Mode", "Language", "Status", "Created At", "Updated At"]
                    self.booking_sheet.append_row(headers)
                
                logger.info("Google Sheets initialized successfully")
                
        except Exception as e:
            logger.error(f"Google Sheets init error: {str(e)}")
    
    async def append_lead(self, lead_data: Dict[str, Any]) -> bool:
        """Append lead to Google Sheets"""
        try:
            if not self.lead_sheet:
                return False
            
            row = [
                lead_data.get("chat_id", ""),
                lead_data.get("name", ""),
                lead_data.get("phone", ""),
                lead_data.get("email", ""),
                lead_data.get("service_interest", ""),
                lead_data.get("source", "whatsapp"),
                lead_data.get("status", "new"),
                lead_data.get("business_type", ""),
                lead_data.get("created_at", ""),
                lead_data.get("conversation_summary", "")[:500]  # Truncate if needed
            ]
            
            self.lead_sheet.append_row(row)
            logger.info(f"Lead appended to Google Sheets: {lead_data.get('name')}")
            return True
            
        except Exception as e:
            logger.error(f"Google Sheets append lead error: {str(e)}")
            return False
    
    async def append_booking(self, booking_data: Dict[str, Any]) -> bool:
        """Append booking to Google Sheets"""
        try:
            if not self.booking_sheet:
                return False
            
            row = [
                booking_data.get("chat_id", ""),
                booking_data.get("customer_name", ""),
                booking_data.get("whatsapp_number", ""),
                booking_data.get("service_type", ""),
                booking_data.get("reason", ""),
                booking_data.get("preferred_date", ""),
                booking_data.get("preferred_time", ""),
                booking_data.get("mode", ""),
                booking_data.get("language_preference", ""),
                booking_data.get("booking_status", "pending"),
                booking_data.get("created_at", ""),
                booking_data.get("updated_at", "")
            ]
            
            self.booking_sheet.append_row(row)
            logger.info(f"Booking appended to Google Sheets: {booking_data.get('customer_name')}")
            return True
            
        except Exception as e:
            logger.error(f"Google Sheets append booking error: {str(e)}")
            return False
    
    async def get_all_leads(self) -> list:
        """Get all leads from Google Sheets"""
        try:
            if not self.lead_sheet:
                return []
            
            records = self.lead_sheet.get_all_records()
            return records
            
        except Exception as e:
            logger.error(f"Error fetching leads from sheets: {str(e)}")
            return []