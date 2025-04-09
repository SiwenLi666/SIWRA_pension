import logging
import json
import os
import uuid
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path

from src.utils.config import BASE_DIR, CONVERSATION_CONTEXT

logger = logging.getLogger('conversation_manager')

class ConversationManager:
    """
    Manages conversation context and history for the Pension Advisor system.
    Allows for context-aware question answering and reference resolution.
    """
    
    def __init__(self):
        """Initialize the conversation manager."""
        self.conversations_dir = Path(BASE_DIR) / "data" / "conversations"
        self.conversations_dir.mkdir(parents=True, exist_ok=True)
        self.active_conversations: Dict[str, Dict] = {}
        
        # Load any existing conversation sessions
        self._load_active_conversations()
    
    def _load_active_conversations(self) -> None:
        """Load active conversations from disk."""
        if not CONVERSATION_CONTEXT:
            return
            
        try:
            for file_path in self.conversations_dir.glob("*.json"):
                if file_path.is_file():
                    with open(file_path, 'r', encoding='utf-8') as f:
                        conversation_data = json.load(f)
                        
                    # Only load conversations that were active in the last 24 hours
                    last_updated = datetime.fromisoformat(conversation_data.get('last_updated', '2000-01-01T00:00:00'))
                    now = datetime.now()
                    hours_since_update = (now - last_updated).total_seconds() / 3600
                    
                    if hours_since_update < 24:
                        conversation_id = file_path.stem
                        self.active_conversations[conversation_id] = conversation_data
                        logger.info(f"📚 Loaded active conversation: {conversation_id}")
        except Exception as e:
            logger.error(f"❌ Error loading active conversations: {e}")
    
    def create_conversation(self, user_id: Optional[str] = None) -> str:
        """
        Create a new conversation session.
        
        Args:
            user_id: Optional user identifier
            
        Returns:
            str: The conversation ID
        """
        if not CONVERSATION_CONTEXT:
            return "conversation_disabled"
            
        try:
            # Generate a unique conversation ID
            conversation_id = f"conv_{uuid.uuid4().hex[:8]}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Create the conversation data structure
            conversation_data = {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "messages": [],
                "metadata": {
                    "selected_agreement": None,
                    "topics_discussed": [],
                    "reference_entities": {}
                }
            }
            
            # Store in memory and on disk
            self.active_conversations[conversation_id] = conversation_data
            self._save_conversation(conversation_id)
            
            logger.info(f"🆕 Created new conversation: {conversation_id}")
            return conversation_id
            
        except Exception as e:
            logger.error(f"❌ Error creating conversation: {e}")
            return "error_creating_conversation"
    
    def add_message(self, conversation_id: str, message: str, role: str, 
                    metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Add a message to the conversation history.
        
        Args:
            conversation_id: The conversation ID
            message: The message text
            role: The role of the sender (user or assistant)
            metadata: Optional metadata about the message
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not CONVERSATION_CONTEXT:
            return False
            
        try:
            if conversation_id not in self.active_conversations:
                logger.warning(f"⚠️ Conversation not found: {conversation_id}")
                return False
                
            # Create the message object
            message_data = {
                "id": f"msg_{uuid.uuid4().hex[:8]}",
                "role": role,
                "content": message,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {}
            }
            
            # Add to the conversation
            self.active_conversations[conversation_id]["messages"].append(message_data)
            self.active_conversations[conversation_id]["last_updated"] = datetime.now().isoformat()
            
            # Update metadata if provided
            if metadata:
                if "selected_agreement" in metadata and metadata["selected_agreement"]:
                    self.active_conversations[conversation_id]["metadata"]["selected_agreement"] = metadata["selected_agreement"]
                
                if "topics" in metadata and metadata["topics"]:
                    for topic in metadata["topics"]:
                        if topic not in self.active_conversations[conversation_id]["metadata"]["topics_discussed"]:
                            self.active_conversations[conversation_id]["metadata"]["topics_discussed"].append(topic)
                
                if "entities" in metadata and metadata["entities"]:
                    for entity_name, entity_value in metadata["entities"].items():
                        self.active_conversations[conversation_id]["metadata"]["reference_entities"][entity_name] = entity_value
            
            # Save the updated conversation
            self._save_conversation(conversation_id)
            
            logger.info(f"💬 Added {role} message to conversation: {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error adding message to conversation: {e}")
            return False
    
    def get_conversation_history(self, conversation_id: str, 
                                 max_messages: Optional[int] = None) -> List[Dict]:
        """
        Get the conversation history.
        
        Args:
            conversation_id: The conversation ID
            max_messages: Optional maximum number of messages to retrieve
            
        Returns:
            List[Dict]: The conversation messages
        """
        if not CONVERSATION_CONTEXT:
            return []
            
        try:
            if conversation_id not in self.active_conversations:
                logger.warning(f"⚠️ Conversation not found: {conversation_id}")
                return []
                
            messages = self.active_conversations[conversation_id]["messages"]
            
            if max_messages is not None and max_messages > 0:
                messages = messages[-max_messages:]
                
            return messages
            
        except Exception as e:
            logger.error(f"❌ Error retrieving conversation history: {e}")
            return []
    
    def get_conversation_context(self, conversation_id: str, 
                                max_context_messages: int = 5) -> Tuple[str, Dict]:
        """
        Get the conversation context for context-aware question answering.
        
        Args:
            conversation_id: The conversation ID
            max_context_messages: Maximum number of previous messages to include in context
            
        Returns:
            Tuple[str, Dict]: The formatted context string and metadata
        """
        if not CONVERSATION_CONTEXT:
            return "", {}
            
        try:
            if conversation_id not in self.active_conversations:
                logger.warning(f"⚠️ Conversation not found: {conversation_id}")
                return "", {}
                
            # Get the most recent messages
            recent_messages = self.get_conversation_history(conversation_id, max_context_messages)
            
            # Format the context
            context_parts = []
            for msg in recent_messages:
                role_label = "User" if msg["role"] == "user" else "Assistant"
                context_parts.append(f"{role_label}: {msg['content']}")
            
            context_str = "\n\n".join(context_parts)
            
            # Get the metadata
            metadata = self.active_conversations[conversation_id]["metadata"]
            
            return context_str, metadata
            
        except Exception as e:
            logger.error(f"❌ Error retrieving conversation context: {e}")
            return "", {}
    
    def resolve_references(self, conversation_id: str, message: str) -> str:
        """
        Resolve references in the message based on conversation context.
        
        Args:
            conversation_id: The conversation ID
            message: The message text
            
        Returns:
            str: The message with references resolved
        """
        if not CONVERSATION_CONTEXT:
            return message
            
        try:
            if conversation_id not in self.active_conversations:
                logger.warning(f"⚠️ Conversation not found: {conversation_id}")
                return message
                
            # Get the conversation metadata
            metadata = self.active_conversations[conversation_id]["metadata"]
            
            # Get the recent messages
            recent_messages = self.get_conversation_history(conversation_id, 3)
            
            # Simple reference resolution for now - can be expanded later
            resolved_message = message
            
            # Replace "it" with the most recently mentioned entity if appropriate
            if any(ref in resolved_message.lower() for ref in ["it", "this", "that", "den", "det", "detta"]):
                if metadata["selected_agreement"]:
                    resolved_message = resolved_message.replace("it", metadata["selected_agreement"])
                    resolved_message = resolved_message.replace("this", metadata["selected_agreement"])
                    resolved_message = resolved_message.replace("that", metadata["selected_agreement"])
                    resolved_message = resolved_message.replace("den", metadata["selected_agreement"])
                    resolved_message = resolved_message.replace("det", metadata["selected_agreement"])
                    resolved_message = resolved_message.replace("detta", metadata["selected_agreement"])
            
            # Replace entity references
            for entity_name, entity_value in metadata["reference_entities"].items():
                if entity_name.lower() in resolved_message.lower():
                    resolved_message = resolved_message.replace(entity_name, entity_value)
            
            logger.info(f"🔄 Resolved references in message for conversation: {conversation_id}")
            return resolved_message
            
        except Exception as e:
            logger.error(f"❌ Error resolving references: {e}")
            return message
    
    def _save_conversation(self, conversation_id: str) -> bool:
        """
        Save the conversation to disk.
        
        Args:
            conversation_id: The conversation ID
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not CONVERSATION_CONTEXT:
            return False
            
        try:
            if conversation_id not in self.active_conversations:
                logger.warning(f"⚠️ Conversation not found: {conversation_id}")
                return False
                
            file_path = self.conversations_dir / f"{conversation_id}.json"
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.active_conversations[conversation_id], f, ensure_ascii=False, indent=2)
                
            return True
            
        except Exception as e:
            logger.error(f"❌ Error saving conversation: {e}")
            return False
    
    def delete_conversation(self, conversation_id: str) -> bool:
        """
        Delete a conversation.
        
        Args:
            conversation_id: The conversation ID
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not CONVERSATION_CONTEXT:
            return False
            
        try:
            if conversation_id not in self.active_conversations:
                logger.warning(f"⚠️ Conversation not found: {conversation_id}")
                return False
                
            # Remove from memory
            del self.active_conversations[conversation_id]
            
            # Remove from disk
            file_path = self.conversations_dir / f"{conversation_id}.json"
            if file_path.exists():
                os.remove(file_path)
                
            logger.info(f"🗑️ Deleted conversation: {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error deleting conversation: {e}")
            return False
    
    def get_active_conversations(self) -> List[Dict]:
        """
        Get a list of active conversations.
        
        Returns:
            List[Dict]: The active conversations
        """
        if not CONVERSATION_CONTEXT:
            return []
            
        try:
            return [
                {
                    "conversation_id": conv_id,
                    "user_id": conv_data.get("user_id"),
                    "created_at": conv_data.get("created_at"),
                    "last_updated": conv_data.get("last_updated"),
                    "message_count": len(conv_data.get("messages", [])),
                    "selected_agreement": conv_data.get("metadata", {}).get("selected_agreement"),
                    "topics_discussed": conv_data.get("metadata", {}).get("topics_discussed", [])
                }
                for conv_id, conv_data in self.active_conversations.items()
            ]
            
        except Exception as e:
            logger.error(f"❌ Error retrieving active conversations: {e}")
            return []
