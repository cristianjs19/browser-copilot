"""
Google Gemini API service
Handles AI model interactions, streaming responses, and token usage tracking
"""

import asyncio
import logging
import os
from typing import Any, AsyncGenerator, List, Optional

from google import genai
from google.genai import types
from langchain.memory import ConversationBufferMemory, FileChatMessageHistory
from langchain.schema import AIMessage, BaseMessage, HumanMessage
from pydantic import BaseModel, Field

from gpt_agent.domain import Session
from gpt_agent.file_system_repos import get_session_path

logger = logging.getLogger(__name__)

class StreamingChunk(BaseModel):
    """Streaming response chunk model"""
    type: str = Field(..., description="Chunk type: content, thought, tokens, end, error")
    content: Optional[str] = Field(default=None, description="Chunk content")
    tokens: Optional[int] = Field(default=None, description="Total token count")
    thoughts_tokens: Optional[int] = Field(default=None, description="Thinking tokens count")
    error: Optional[str] = Field(default=None, description="Error message")

class GeminiService:
    """
    Service for interacting with Google Gemini API
    """
    
    def __init__(self, session: Session):
        self._session = session
        
        # Initialize Gemini client
        self.client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        
        # Initialize conversation memory using existing FileChatMessageHistory
        message_history = FileChatMessageHistory(get_session_path(session.id) + "/chat_history.json")
        self._memory = ConversationBufferMemory(
            memory_key="chat_history", 
            chat_memory=message_history,
            return_messages=True
        )
        
        # Configuration settings
        self.flash_model = os.getenv("GEMINI_FLASH_MODEL", "gemini-2.5-flash")
        self.pro_model = os.getenv("GEMINI_PRO_MODEL", "gemini-2.5-pro")
        self.temperature = float(os.getenv("GEMINI_TEMPERATURE", "0.7"))
        self.top_p = float(os.getenv("GEMINI_TOP_P", "0.9"))
        self.top_k = int(os.getenv("GEMINI_TOP_K", "40"))
        self.max_output_tokens = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "4096"))
        self.chunk_delay = float(os.getenv("GEMINI_CHUNK_DELAY", "0.01"))
        
        logger.info(f"Initialized Gemini service for session {session.id}")

    def start_session(self):
        """Initialize session with locale information"""
        self._memory.chat_memory.add_user_message("this is my locale: " + self._session.locales[0])

    async def generate_standard_response(
        self,
        message: str
    ) -> AsyncGenerator[StreamingChunk, None]:
        """
        Generate standard AI response using Gemini Flash model
        
        Args:
            message: User message
            
        Yields:
            StreamingChunk objects with response content and token usage
        """
        logger.info(f"Starting standard response generation for session {self._session.id}")
        
        try:
            # Add user message to memory
            self._memory.chat_memory.add_user_message(message)
            
            # Get conversation history from memory
            conversation_history = self._get_conversation_history()
            
            # Build contents for Gemini API
            contents = self._build_gemini_contents(conversation_history)
            
            logger.debug(f"**Generated contents for Gemini: {contents}**")
            # Configure generation
            config = types.GenerateContentConfig(
                temperature=self.temperature,
                top_p=self.top_p,
                top_k=self.top_k,
                max_output_tokens=self.max_output_tokens
            )
            
            full_response = ""
            final_response = None
            
            # Generate streaming response using Flash model
            async for chunk in self._generate_content_stream_async(
                model=self.flash_model,
                contents=contents,
                config=config
            ):
                final_response = chunk
                
                for candidate in chunk.candidates:
                    if not candidate.content or not candidate.content.parts:
                        continue
                    
                    for part in candidate.content.parts:
                        if part.text:
                            response_text = part.text
                            full_response += response_text
                            
                            yield StreamingChunk(
                                type="content",
                                content=response_text
                            )
                            await asyncio.sleep(self.chunk_delay)
            
            # Add AI response to memory
            self._memory.chat_memory.add_ai_message(full_response)
            
            # Extract and yield token usage information
            total_tokens = self._extract_token_usage(
                final_response, message, full_response
            )
            
            yield StreamingChunk(
                type="tokens",
                tokens=total_tokens
            )
            
            logger.info(f"Completed standard response for session {self._session.id}. Response: {len(full_response)} chars")
                
        except Exception as e:
            logger.error(f"Error in standard response generation for session {self._session.id}: {str(e)}")
            yield StreamingChunk(
                type="error",
                error=str(e)
            )

    async def generate_thinking_response(
        self,
        message: str
    ) -> AsyncGenerator[StreamingChunk, None]:
        """
        Generate thinking mode AI response using Gemini Pro model
        
        Args:
            message: User message
                
        Yields:
            StreamingChunk objects with thoughts and response content
        """
        logger.info(f"Starting thinking mode response generation for session {self._session.id}")
        
        try:
            # Add user message to memory
            self._memory.chat_memory.add_user_message(message)
            
            # Get conversation history from memory
            conversation_history = self._get_conversation_history()
            
            # Build contents for Gemini API
            contents = self._build_gemini_contents(conversation_history)
            
            # Configure generation with thinking mode
            config = types.GenerateContentConfig(
                temperature=self.temperature,
                top_p=self.top_p,
                top_k=self.top_k,
                max_output_tokens=self.max_output_tokens,
                thinking_config=types.ThinkingConfig(
                    include_thoughts=True
                )
            )
            
            full_response = ""
            full_thoughts = ""
            final_response = None
            
            # Generate streaming response using Pro model
            async for chunk in self._generate_content_stream_async(
                model=self.pro_model,
                contents=contents,
                config=config
            ):
                final_response = chunk
                
                for candidate in chunk.candidates:
                    if not candidate.content or not candidate.content.parts:
                        continue
                    
                    for part in candidate.content.parts:
                        if not part.text:
                            continue
                        
                        # Check if this part contains thoughts
                        if hasattr(part, 'thought') and part.thought:
                            # This is a thought part
                            thought_text = part.text
                            full_thoughts += thought_text
                            
                            yield StreamingChunk(
                                type="thought",
                                content=thought_text
                            )
                            await asyncio.sleep(self.chunk_delay)
                        else:
                            # This is regular response content
                            response_text = part.text
                            full_response += response_text
                            
                            yield StreamingChunk(
                                type="content",
                                content=response_text
                            )
                            await asyncio.sleep(self.chunk_delay)
            
            # Add AI response to memory
            self._memory.chat_memory.add_ai_message(full_response)
            
            # Extract and yield token usage information
            total_tokens, thoughts_tokens = self._extract_thinking_token_usage(
                final_response, message, full_response, full_thoughts
            )
            
            yield StreamingChunk(
                type="tokens",
                tokens=total_tokens,
                thoughts_tokens=thoughts_tokens
            )
            
            logger.info(f"Completed thinking response for session {self._session.id}. Response: {len(full_response)} chars, Thoughts: {len(full_thoughts)} chars")
                
        except Exception as e:
            logger.error(f"Error in thinking response generation for session {self._session.id}: {str(e)}")
            yield StreamingChunk(
                type="error",
                error=str(e)
            )

    def _get_conversation_history(self) -> List[BaseMessage]:
        """Get conversation history from memory"""
        return self._memory.chat_memory.messages

    def _build_gemini_contents(self, conversation_history: List[BaseMessage]) -> List[dict]:
        """
        Build contents in Gemini API format from Langchain conversation history
        
        Args:
            conversation_history: List of BaseMessage objects from Langchain
            
        Returns:
            List of content dictionaries for Gemini API
        """
        contents = []
        
        # Convert conversation history to Gemini format
        for message in conversation_history:
            if isinstance(message, HumanMessage):
                contents.append({
                    "role": "user",
                    "parts": [{"text": message.content}]
                })
            elif isinstance(message, AIMessage):
                contents.append({
                    "role": "model",
                    "parts": [{"text": message.content}]
                })
        
        return contents

    async def _generate_content_stream_async(
        self,
        model: str,
        contents: List[dict],
        config: types.GenerateContentConfig
    ):
        """
        Async wrapper for the generate_content_stream method
        """
        def _sync_generate():
            return self.client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=config
            )
        
        generator = await asyncio.to_thread(_sync_generate)
        
        for chunk in generator:
            yield chunk

    def _extract_token_usage(self, response: Any, message: str, full_response: str) -> int:
        """
        Extract token usage from standard response
        
        Args:
            response: Gemini response object
            message: Original user message
            full_response: Complete AI response
            
        Returns:
            Total token count
        """
        try:
            if response and hasattr(response, 'usage_metadata'):
                total_tokens = response.usage_metadata.total_token_count
                logger.debug(f"Token usage from API: {total_tokens}")
                return total_tokens
            else:
                # Fallback estimation
                estimated_tokens = len(full_response.split()) + len(message.split())
                logger.warning(f"API token usage not available, estimated: {estimated_tokens}")
                return estimated_tokens
        except Exception as e:
            # Final fallback
            estimated_tokens = len(full_response.split()) + len(message.split())
            logger.error(f"Error extracting token usage, using estimation: {estimated_tokens}. Error: {e}")
            return estimated_tokens

    def _extract_thinking_token_usage(
        self, 
        response: Any, 
        message: str, 
        full_response: str, 
        full_thoughts: str
    ) -> tuple[int, int]:
        """
        Extract token usage from thinking mode response
        
        Args:
            response: Gemini response object
            message: Original user message
            full_response: Complete AI response
            full_thoughts: Complete thoughts
            
        Returns:
            Tuple of (total_tokens, thoughts_tokens)
        """
        try:
            if response and hasattr(response, 'usage_metadata'):
                total_tokens = response.usage_metadata.total_token_count
                thoughts_tokens = getattr(response.usage_metadata, 'thoughts_token_count', 0)
                logger.debug(f"Thinking token usage from API: total={total_tokens}, thoughts={thoughts_tokens}")
                return total_tokens, thoughts_tokens
            else:
                # Fallback estimation
                total_estimated = len(full_response.split()) + len(message.split()) + len(full_thoughts.split())
                thoughts_estimated = len(full_thoughts.split())
                logger.warning(f"API token usage not available, estimated: total={total_estimated}, thoughts={thoughts_estimated}")
                return total_estimated, thoughts_estimated
        except Exception as e:
            # Final fallback
            total_estimated = len(full_response.split()) + len(message.split()) + len(full_thoughts.split())
            thoughts_estimated = len(full_thoughts.split())
            logger.error(f"Error extracting thinking token usage, using estimation. Error: {e}")
            return total_estimated, thoughts_estimated