from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
from bson import ObjectId

from core.database import get_collection
from models.conversation import Conversation, Message

logger = logging.getLogger(__name__)

class ConversationService:
    def __init__(self):
        self.collection_name = "conversations"
    
    async def get_or_create(self, chat_id: str) -> Dict[str, Any]:
        """Get existing conversation or create new one"""
        try:
            collection = await get_collection(self.collection_name)
            conversation = await collection.find_one({"chat_id": chat_id})
            
            if conversation:
                return conversation
            
            # Create new conversation
            new_conversation = {
                "chat_id": chat_id,
                "messages": [],
                "language": "en",
                "context": {
                    "collected_fields": []
                },
                "phase": "greeting",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            await collection.insert_one(new_conversation)
            return new_conversation
            
        except Exception as e:
            logger.error(f"Error getting/creating conversation: {str(e)}")
            return {"chat_id": chat_id, "messages": [], "context": {}, "phase": "greeting"}
    
    async def update(self, chat_id: str, data: Dict) -> bool:
        """Update conversation"""
        try:
            collection = await get_collection(self.collection_name)
            data["updated_at"] = datetime.utcnow().isoformat()
            
            result = await collection.update_one(
                {"chat_id": chat_id},
                {"$set": data}
            )
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error updating conversation: {str(e)}")
            return False
    
    async def get_conversation(self, chat_id: str) -> Optional[Dict]:
        """Get conversation by chat ID"""
        try:
            collection = await get_collection(self.collection_name)
            conversation = await collection.find_one({"chat_id": chat_id})
            return conversation
            
        except Exception as e:
            logger.error(f"Error fetching conversation: {str(e)}")
            return None
    
    async def add_message(self, chat_id: str, role: str, content: str) -> bool:
        """Add a message to conversation"""
        try:
            collection = await get_collection(self.collection_name)
            message = {
                "role": role,
                "content": content,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            result = await collection.update_one(
                {"chat_id": chat_id},
                {
                    "$push": {"messages": message},
                    "$set": {"updated_at": datetime.utcnow().isoformat()}
                }
            )
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error adding message: {str(e)}")
            return False
    
    async def update_context(self, chat_id: str, context_data: Dict) -> bool:
        """Update conversation context"""
        try:
            collection = await get_collection(self.collection_name)
            result = await collection.update_one(
                {"chat_id": chat_id},
                {
                    "$set": {
                        "context": context_data,
                        "updated_at": datetime.utcnow().isoformat()
                    }
                }
            )
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error updating context: {str(e)}")
            return False
    
    async def update_phase(self, chat_id: str, phase: str) -> bool:
        """Update conversation phase"""
        try:
            collection = await get_collection(self.collection_name)
            result = await collection.update_one(
                {"chat_id": chat_id},
                {
                    "$set": {
                        "phase": phase,
                        "updated_at": datetime.utcnow().isoformat()
                    }
                }
            )
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error updating phase: {str(e)}")
            return False