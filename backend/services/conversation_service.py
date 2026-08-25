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
        self.MAX_MESSAGES = 50  # ✅ Limit to 50 messages
    
    async def get_or_create(self, chat_id: str) -> Dict[str, Any]:
        """Get existing conversation or create new one"""
        try:
            collection = await get_collection(self.collection_name)
            conversation = await collection.find_one({"chat_id": chat_id})
            
            if conversation:
                # ✅ Trim messages if too many
                if len(conversation.get("messages", [])) > self.MAX_MESSAGES:
                    conversation["messages"] = conversation["messages"][-self.MAX_MESSAGES:]
                    await collection.update_one(
                        {"chat_id": chat_id},
                        {"$set": {"messages": conversation["messages"]}}
                    )
                return conversation
            
            new_conversation = {
                "chat_id": chat_id,
                "messages": [],
                "language": "en",
                "context": {"collected_fields": []},
                "phase": "greeting",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            await collection.insert_one(new_conversation)
            return new_conversation
            
        except Exception as e:
            logger.error(f"Error getting/creating conversation: {str(e)}")
            return {"chat_id": chat_id, "messages": [], "context": {"collected_fields": []}, "phase": "greeting"}
    
    async def update(self, chat_id: str, data: Dict) -> bool:
        """Update conversation with size limit"""
        try:
            collection = await get_collection(self.collection_name)
            existing = await collection.find_one({"chat_id": chat_id})
            
            if not existing:
                logger.warning(f"Conversation {chat_id} not found")
                return False
            
            data["updated_at"] = datetime.utcnow().isoformat()
            
            # ✅ Merge context
            if "context" in data:
                existing_context = existing.get("context", {"collected_fields": []})
                new_context = data.get("context", {})
                
                if "collected_fields" not in existing_context:
                    existing_context["collected_fields"] = []
                if "collected_fields" not in new_context:
                    new_context["collected_fields"] = []
                
                merged_context = {**existing_context, **new_context}
                
                existing_fields = set(existing_context.get("collected_fields", []))
                new_fields = set(new_context.get("collected_fields", []))
                merged_fields = list(existing_fields | new_fields)
                merged_context["collected_fields"] = merged_fields
                
                data["context"] = merged_context
            
            # ✅ Limit messages
            if "messages" in data:
                existing_messages = existing.get("messages", [])
                new_messages = data.get("messages", [])
                if new_messages:
                    combined = existing_messages + new_messages
                    data["messages"] = combined[-self.MAX_MESSAGES:]
                    logger.info(f"📝 Messages limited to last {self.MAX_MESSAGES} (total: {len(combined)})")
            else:
                # ✅ Even if messages not in update, ensure existing is limited
                if len(existing.get("messages", [])) > self.MAX_MESSAGES:
                    data["messages"] = existing["messages"][-self.MAX_MESSAGES:]
            
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
        """Add a message with size limit"""
        try:
            collection = await get_collection(self.collection_name)
            message = {
                "role": role,
                "content": content,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # ✅ Push and then limit
            result = await collection.update_one(
                {"chat_id": chat_id},
                {
                    "$push": {"messages": message},
                    "$set": {"updated_at": datetime.utcnow().isoformat()}
                }
            )
            
            # ✅ Limit messages after adding
            conversation = await collection.find_one({"chat_id": chat_id})
            if conversation and len(conversation.get("messages", [])) > self.MAX_MESSAGES:
                conversation["messages"] = conversation["messages"][-self.MAX_MESSAGES:]
                await collection.update_one(
                    {"chat_id": chat_id},
                    {"$set": {"messages": conversation["messages"]}}
                )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error adding message: {str(e)}")
            return False
    
    async def update_context(self, chat_id: str, context_data: Dict) -> bool:
        """Update conversation context"""
        try:
            collection = await get_collection(self.collection_name)
            existing = await collection.find_one({"chat_id": chat_id})
            if existing:
                existing_context = existing.get("context", {"collected_fields": []})
                merged_context = {**existing_context, **context_data}
                
                existing_fields = set(existing_context.get("collected_fields", []))
                new_fields = set(context_data.get("collected_fields", []))
                merged_context["collected_fields"] = list(existing_fields | new_fields)
                
                result = await collection.update_one(
                    {"chat_id": chat_id},
                    {"$set": {"context": merged_context, "updated_at": datetime.utcnow().isoformat()}}
                )
                return result.modified_count > 0
            return False
        except Exception as e:
            logger.error(f"Error updating context: {str(e)}")
            return False
    
    async def update_phase(self, chat_id: str, phase: str) -> bool:
        """Update conversation phase"""
        try:
            collection = await get_collection(self.collection_name)
            result = await collection.update_one(
                {"chat_id": chat_id},
                {"$set": {"phase": phase, "updated_at": datetime.utcnow().isoformat()}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating phase: {str(e)}")
            return False
    
    async def clear_conversation(self, chat_id: str) -> bool:
        """Clear all messages for a chat"""
        try:
            collection = await get_collection(self.collection_name)
            result = await collection.update_one(
                {"chat_id": chat_id},
                {"$set": {"messages": [], "updated_at": datetime.utcnow().isoformat()}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error clearing conversation: {str(e)}")
            return False