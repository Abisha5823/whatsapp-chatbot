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
            return {"chat_id": chat_id, "messages": [], "context": {"collected_fields": []}, "phase": "greeting"}
    
    async def update(self, chat_id: str, data: Dict) -> bool:
        """Update conversation - MERGE context instead of replacing"""
        try:
            collection = await get_collection(self.collection_name)
            
            # ✅ Get existing conversation to merge context
            existing = await collection.find_one({"chat_id": chat_id})
            
            # Set updated_at timestamp
            data["updated_at"] = datetime.utcnow().isoformat()
            
            # ✅ MERGE context (don't overwrite)
            if existing and "context" in data:
                existing_context = existing.get("context", {"collected_fields": []})
                new_context = data.get("context", {})
                
                # Ensure collected_fields exists
                if "collected_fields" not in existing_context:
                    existing_context["collected_fields"] = []
                if "collected_fields" not in new_context:
                    new_context["collected_fields"] = []
                
                # ✅ Merge: combine existing and new fields
                merged_context = {**existing_context, **new_context}
                
                # ✅ Merge collected_fields (deduplicate)
                existing_fields = set(existing_context.get("collected_fields", []))
                new_fields = set(new_context.get("collected_fields", []))
                merged_fields = list(existing_fields | new_fields)  # Union of both sets
                merged_context["collected_fields"] = merged_fields
                
                data["context"] = merged_context
                
                logger.info(f"🔄 Merged context for {chat_id}: {merged_context}")
            
            # ✅ Also merge messages (append, don't replace)
            if existing and "messages" in data:
                existing_messages = existing.get("messages", [])
                new_messages = data.get("messages", [])
                if new_messages:
                    # Append new messages to existing ones
                    data["messages"] = existing_messages + new_messages
            
            # Update the document
            result = await collection.update_one(
                {"chat_id": chat_id},
                {"$set": data}
            )
            
            logger.info(f"💾 Updated conversation for {chat_id}: {result.modified_count} field(s) modified")
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
        """Update conversation context - MERGE with existing"""
        try:
            collection = await get_collection(self.collection_name)
            
            # ✅ Get existing to merge
            existing = await collection.find_one({"chat_id": chat_id})
            if existing:
                existing_context = existing.get("context", {"collected_fields": []})
                
                # Merge context
                merged_context = {**existing_context, **context_data}
                
                # Merge collected_fields
                existing_fields = set(existing_context.get("collected_fields", []))
                new_fields = set(context_data.get("collected_fields", []))
                merged_fields = list(existing_fields | new_fields)
                merged_context["collected_fields"] = merged_fields
                
                result = await collection.update_one(
                    {"chat_id": chat_id},
                    {
                        "$set": {
                            "context": merged_context,
                            "updated_at": datetime.utcnow().isoformat()
                        }
                    }
                )
                logger.info(f"📝 Updated context for {chat_id}: {merged_context}")
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
    
    async def clear_context(self, chat_id: str) -> bool:
        """Clear conversation context (for testing)"""
        try:
            collection = await get_collection(self.collection_name)
            result = await collection.update_one(
                {"chat_id": chat_id},
                {
                    "$set": {
                        "context": {"collected_fields": []},
                        "updated_at": datetime.utcnow().isoformat()
                    }
                }
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error clearing context: {str(e)}")
            return False