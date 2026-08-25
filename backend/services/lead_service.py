from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
from bson import ObjectId

from core.database import get_collection
from models.lead import Lead, LeadCreate
from services.google_sheets_service import GoogleSheetsService

logger = logging.getLogger(__name__)

class LeadService:
    def __init__(self):
        self.sheets_service = GoogleSheetsService()
    
    async def save_lead(self, chat_id: str, conversation: Dict, response: Dict) -> Optional[Lead]:
    
        try:
            lead_data = response.get("lead_data", {})
            context = conversation.get("context", {})
            
            # ✅ Create lead with only lead-specific fields
            lead = Lead(
                chat_id=chat_id,
                name=context.get("name", lead_data.get("name", "")),
                phone=context.get("phone", lead_data.get("phone", "")),
                email=context.get("email", lead_data.get("email", "")),
                service_interest=context.get("service_type", lead_data.get("service_interest", "")),
                source="whatsapp",
                status="new",
                business_type=context.get("business_type", "general"),
                conversation_summary=response.get("conversation_summary", ""),
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat()
            )
            
            # ✅ Save to MongoDB
            collection = await get_collection("leads")
            result = await collection.insert_one(lead.dict())
            
            # ✅ Save to Google Sheets (only lead fields)
            try:
                self.sheets_service = GoogleSheetsService()
                sheet_result = await self.sheets_service.append_lead(lead.dict())
                if sheet_result:
                    logger.info(f"✅ Lead saved to Google Sheets: {lead.name}")
                else:
                    logger.warning(f"⚠️ Google Sheets save failed for lead: {lead.name}")
            except Exception as e:
                logger.error(f"❌ Google Sheets error: {str(e)}")
            
            logger.info(f"✅ Lead saved: {lead.name} ({chat_id})")
            return lead
        
        except Exception as e:
            logger.error(f"Error saving lead: {str(e)}")
            return None
        
    async def get_lead_by_chat_id(self, chat_id: str) -> Optional[Dict]:
        """Get lead by chat ID"""
        try:
            collection = await get_collection("leads")
            lead = await collection.find_one({"chat_id": chat_id})
            return lead
        except Exception as e:
            logger.error(f"Error fetching lead: {str(e)}")
            return None
    
    async def get_lead_by_id(self, lead_id: str) -> Optional[Dict]:
        """Get lead by ID"""
        try:
            collection = await get_collection("leads")
            lead = await collection.find_one({"_id": ObjectId(lead_id)})
            return lead
        except Exception as e:
            logger.error(f"Error fetching lead: {str(e)}")
            return None
    
    async def get_all_leads(self, skip: int = 0, limit: int = 100) -> List[Dict]:
        """Get all leads with pagination"""
        try:
            collection = await get_collection("leads")
            cursor = collection.find().skip(skip).limit(limit).sort("created_at", -1)
            leads = await cursor.to_list(length=limit)
            return leads
        except Exception as e:
            logger.error(f"Error fetching leads: {str(e)}")
            return []
    
    async def update_lead(self, lead_id: str, data: Dict) -> Optional[Dict]:
        """Update lead"""
        try:
            collection = await get_collection("leads")
            data["updated_at"] = datetime.utcnow().isoformat()
            result = await collection.update_one(
                {"_id": ObjectId(lead_id)},
                {"$set": data}
            )
            if result.modified_count > 0:
                return await self.get_lead_by_id(lead_id)
            return None
        except Exception as e:
            logger.error(f"Error updating lead: {str(e)}")
            return None
    
    async def update_lead_status(self, lead_id: str, status: str) -> bool:
        """Update lead status"""
        try:
            collection = await get_collection("leads")
            result = await collection.update_one(
                {"_id": ObjectId(lead_id)},
                {"$set": {"status": status, "updated_at": datetime.utcnow().isoformat()}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating lead status: {str(e)}")
            return False
    
    async def sync_to_google_sheets(self, lead: Dict) -> bool:
        """Sync lead to Google Sheets"""
        try:
            if self.sheets_service.sheet:
                await self.sheets_service.append_lead(lead)
                return True
            return False
        except Exception as e:
            logger.error(f"Error syncing to Google Sheets: {str(e)}")
            return False
    