from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import logging
from bson import ObjectId

from core.database import get_collection
from models.booking import Booking, BookingCreate
from backend.services.google_sheets_service import GoogleSheetsService

logger = logging.getLogger(__name__)

class BookingService:
    def __init__(self):
        self.sheets_service = GoogleSheetsService()
    
    async def create_from_conversation(self, chat_id: str, conversation: Dict, response: Dict) -> Optional[Booking]:
        """Create booking from conversation"""
        try:
            booking_data = response.get("booking_data", {})
            context = conversation.get("context", {})
            
            # Check if booking already exists
            existing = await self.get_booking_by_chat_id(chat_id)
            if existing and existing["booking_status"] == "pending":
                return await self.update_booking(existing["_id"], booking_data)
            
            # Parse date and time
            preferred_date = booking_data.get("date", "")
            preferred_time = booking_data.get("time", "")
            
            if not preferred_date:
                preferred_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            
            # Create booking
            booking = Booking(
                chat_id=chat_id,
                customer_name=context.get("name", booking_data.get("name", "")),
                whatsapp_number=context.get("phone", booking_data.get("phone", "")),
                service_type=booking_data.get("service", context.get("service_type", "")),
                reason=booking_data.get("reason", ""),
                preferred_date=preferred_date,
                preferred_time=preferred_time or "10:00 AM",
                mode=booking_data.get("mode", "offline"),
                language_preference=conversation.get("language", "English"),
                booking_status="pending",
                business_id=context.get("business_id"),
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat()
            )
            
            # Save to MongoDB
            collection = await get_collection("bookings")
            result = await collection.insert_one(booking.dict())
            
            # Sync to Google Sheets
            if self.sheets_service.sheet:
                await self.sheets_service.append_booking(booking.dict())
            
            logger.info(f"Booking created: {booking.customer_name} ({chat_id})")
            return booking
            
        except Exception as e:
            logger.error(f"Error creating booking: {str(e)}")
            return None
    
    async def create_manual_booking(self, booking_data: BookingCreate) -> Optional[Booking]:
        """Create booking manually"""
        try:
            booking = Booking(
                chat_id=booking_data.chat_id,
                customer_name=booking_data.customer_name,
                whatsapp_number=booking_data.whatsapp_number,
                service_type=booking_data.service_type,
                reason=booking_data.reason,
                preferred_date=booking_data.preferred_date,
                preferred_time=booking_data.preferred_time,
                mode=booking_data.mode,
                language_preference=booking_data.language_preference,
                booking_status="pending",
                business_id=booking_data.business_id,
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat()
            )
            
            collection = await get_collection("bookings")
            await collection.insert_one(booking.dict())
            
            return booking
            
        except Exception as e:
            logger.error(f"Error creating manual booking: {str(e)}")
            return None
    
    async def get_booking_by_chat_id(self, chat_id: str) -> Optional[Dict]:
        """Get booking by chat ID"""
        try:
            collection = await get_collection("bookings")
            booking = await collection.find_one({"chat_id": chat_id})
            return booking
        except Exception as e:
            logger.error(f"Error fetching booking: {str(e)}")
            return None
    
    async def get_booking_by_id(self, booking_id: str) -> Optional[Dict]:
        """Get booking by ID"""
        try:
            collection = await get_collection("bookings")
            booking = await collection.find_one({"_id": ObjectId(booking_id)})
            return booking
        except Exception as e:
            logger.error(f"Error fetching booking: {str(e)}")
            return None
    
    async def get_all_bookings(self, skip: int = 0, limit: int = 100) -> List[Dict]:
        """Get all bookings with pagination"""
        try:
            collection = await get_collection("bookings")
            cursor = collection.find().skip(skip).limit(limit).sort("created_at", -1)
            bookings = await cursor.to_list(length=limit)
            return bookings
        except Exception as e:
            logger.error(f"Error fetching bookings: {str(e)}")
            return []
    
    async def update_booking(self, booking_id: str, data: Dict) -> Optional[Dict]:
        """Update booking"""
        try:
            collection = await get_collection("bookings")
            data["updated_at"] = datetime.utcnow().isoformat()
            result = await collection.update_one(
                {"_id": ObjectId(booking_id)},
                {"$set": data}
            )
            if result.modified_count > 0:
                return await self.get_booking_by_id(booking_id)
            return None
        except Exception as e:
            logger.error(f"Error updating booking: {str(e)}")
            return None
    
    async def update_status(self, booking_id: str, status: str) -> bool:
        """Update booking status"""
        try:
            collection = await get_collection("bookings")
            result = await collection.update_one(
                {"_id": ObjectId(booking_id)},
                {"$set": {"booking_status": status, "updated_at": datetime.utcnow().isoformat()}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating booking status: {str(e)}")
            return False
    
    async def confirm_booking(self, booking_id: str) -> bool:
        """Confirm a booking"""
        return await self.update_status(booking_id, "confirmed")
    
    async def complete_booking(self, booking_id: str) -> bool:
        """Complete a booking"""
        return await self.update_status(booking_id, "completed")
    
    async def cancel_booking(self, booking_id: str) -> bool:
        """Cancel a booking"""
        return await self.update_status(booking_id, "cancelled")
    
    async def get_available_slots(self, date: str) -> List[str]:
        """Get available time slots for a date"""
        # This is a sample implementation - would integrate with calendar in production
        available_slots = [
            "9:00 AM", "10:00 AM", "11:00 AM", 
            "2:00 PM", "3:00 PM", "4:00 PM", "5:00 PM"
        ]
        
        # Check existing bookings for this date
        collection = await get_collection("bookings")
        booked_slots = await collection.find(
            {"preferred_date": date, "booking_status": {"$in": ["pending", "confirmed"]}}
        ).to_list(length=None)
        
        booked_times = [b["preferred_time"] for b in booked_slots]
        available = [slot for slot in available_slots if slot not in booked_times]
        
        return available