"""
Tests for Gemini AI service functionality
"""

import asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from gpt_agent.domain import StreamingChunk
from gpt_agent.services.gemini_agent import GeminiService, TokenCalculator

from tests.conftest import (
    async_generator_from_list,
    mock_gemini_response,
    mock_gemini_thinking_response,
)


class TestTokenCalculator:
    """Test TokenCalculator functionality"""
    
    def test_extract_standard_tokens_with_api_response(self):
        """Test token extraction from standard API response"""
        calculator = TokenCalculator()
        response = mock_gemini_response("Hello world", token_count=25)
        
        tokens = calculator.extract_standard_tokens(response, "Test message", "Hello world")
        
        assert tokens == 25
    
    def test_extract_standard_tokens_fallback(self):
        """Test token extraction fallback when API doesn't provide usage"""
        calculator = TokenCalculator()
        response = Mock()
        response.usage_metadata = None
        
        tokens = calculator.extract_standard_tokens(response, "Test message", "Hello world")
        
        # Should estimate based on word count
        assert tokens > 0
        assert isinstance(tokens, int)
    
    def test_extract_thinking_tokens_with_api_response(self):
        """Test thinking token extraction from API response"""
        calculator = TokenCalculator()
        response = mock_gemini_thinking_response("Hello", "Let me think", token_count=30, thought_tokens=10)
        
        total_tokens, thoughts_tokens = calculator.extract_thinking_tokens(
            response, "Test message", "Hello", "Let me think"
        )
        
        assert total_tokens == 30
        assert thoughts_tokens == 10
    
    def test_extract_thinking_tokens_fallback(self):
        """Test thinking token extraction fallback"""
        calculator = TokenCalculator()
        response = Mock()
        response.usage_metadata = None
        
        total_tokens, thoughts_tokens = calculator.extract_thinking_tokens(
            response, "Test message", "Hello world", "Let me think about this"
        )
        
        assert total_tokens > 0
        assert thoughts_tokens > 0
        assert isinstance(total_tokens, int)
        assert isinstance(thoughts_tokens, int)
    
    def test_create_token_chunk_standard(self):
        """Test creating token chunk for standard response"""
        calculator = TokenCalculator()
        response = mock_gemini_response("Hello world", token_count=25)
        
        chunk = calculator.create_token_chunk(response, "Test", "Hello world", use_thinking=False)
        
        assert chunk.type == "tokens"
        assert chunk.tokens == 25
        assert chunk.thoughts_tokens is None
    
    def test_create_token_chunk_thinking(self):
        """Test creating token chunk for thinking response"""
        calculator = TokenCalculator()
        response = mock_gemini_thinking_response("Hello", "Let me think", token_count=30, thought_tokens=10)
        
        chunk = calculator.create_token_chunk(
            response, "Test", "Hello", use_thinking=True, full_thoughts="Let me think"
        )
        
        assert chunk.type == "tokens"
        assert chunk.tokens == 30
        assert chunk.thoughts_tokens == 10


class TestGeminiService:
    """Test GeminiService functionality"""
    
    @pytest.fixture
    def gemini_service(self, mock_session, mock_environment_variables):
        """Create GeminiService instance for testing"""
        with patch('gpt_agent.services.gemini_agent.genai.Client') as mock_genai, \
             patch('gpt_agent.services.gemini_agent.ConversationBufferMemory') as mock_memory, \
             patch('gpt_agent.services.gemini_agent.FileChatMessageHistory') as mock_file_history, \
             patch('gpt_agent.services.gemini_agent.get_session_path', return_value='/tmp/test'):
            
            # Setup mocks
            mock_client = Mock()
            mock_genai.return_value = mock_client
            
            # Create a proper mock memory instance
            mock_memory_instance = Mock()
            mock_memory_instance.memory_key = "chat_history"
            mock_memory_instance.chat_memory = Mock()
            mock_memory_instance.chat_memory.messages = []
            mock_memory_instance.chat_memory.add_user_message = Mock()
            mock_memory_instance.chat_memory.add_ai_message = Mock()
            mock_memory.return_value = mock_memory_instance
            
            # Create the service
            service = GeminiService(mock_session)
            
            # Set up additional mocks after creation
            service.client = mock_client
            service.client.models = Mock()
            service.client.models.generate_content_stream = Mock()
            
            return service
    
    def test_gemini_service_initialization(self, gemini_service, mock_session):
        """Test GeminiService initialization"""
        assert gemini_service._session == mock_session
        assert gemini_service._token_calculator is not None
        assert gemini_service.flash_model == "gemini-2.5-flash" or gemini_service.flash_model == "gemini-2.5-flash-lite-preview-06-17"
        assert gemini_service.pro_model == "gemini-2.5-pro"
        assert gemini_service.temperature == 0.7
    
    def test_start_session(self, gemini_service):
        """Test session initialization"""
        gemini_service.start_session()
        
        # Verify that locale was added to memory
        gemini_service._memory.chat_memory.add_user_message.assert_called_once()
        call_args = gemini_service._memory.chat_memory.add_user_message.call_args
        assert "en-US" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_generate_standard_response(self, gemini_service):
        """Test standard response generation"""
        # Mock the core response generation method
        expected_chunks = [
            StreamingChunk(type="content", content="Hello "),
            StreamingChunk(type="content", content="world!"),
            StreamingChunk(type="tokens", tokens=15)
        ]
        
        with patch.object(gemini_service, '_generate_response') as mock_generate:
            mock_generate.return_value = async_generator_from_list(expected_chunks)
            
            chunks = []
            async for chunk in gemini_service.generate_standard_response("Test message"):
                chunks.append(chunk)
            
            assert len(chunks) == 3
            assert chunks[0].type == "content"
            assert chunks[0].content == "Hello "
            assert chunks[2].type == "tokens"
            assert chunks[2].tokens == 15
            
            # Verify correct model was used
            mock_generate.assert_called_once_with(
                message="Test message",
                model=gemini_service.flash_model,
                use_thinking=False
            )
    
    @pytest.mark.asyncio
    async def test_generate_thinking_response(self, gemini_service):
        """Test thinking mode response generation"""
        expected_chunks = [
            StreamingChunk(type="thought", content="Let me think... "),
            StreamingChunk(type="content", content="Hello world!"),
            StreamingChunk(type="tokens", tokens=25, thoughts_tokens=10)
        ]
        
        with patch.object(gemini_service, '_generate_response') as mock_generate:
            mock_generate.return_value = async_generator_from_list(expected_chunks)
            
            chunks = []
            async for chunk in gemini_service.generate_thinking_response("Test message"):
                chunks.append(chunk)
            
            assert len(chunks) == 3
            assert chunks[0].type == "thought"
            assert chunks[0].content == "Let me think... "
            assert chunks[1].type == "content"
            assert chunks[2].type == "tokens"
            assert chunks[2].thoughts_tokens == 10
            
            # Verify correct model was used
            mock_generate.assert_called_once_with(
                message="Test message",
                model=gemini_service.pro_model,
                use_thinking=True
            )
    
    @pytest.mark.asyncio
    async def test_generate_response_standard_mode(self, gemini_service):
        """Test core response generation in standard mode"""
        mock_response = mock_gemini_response("Hello world!", token_count=20)
        
        with patch.object(gemini_service, '_generate_content_stream_async') as mock_stream:
            mock_stream.return_value = async_generator_from_list([mock_response])
            
            chunks = []
            async for chunk in gemini_service._generate_response("Test", "gemini-2.5-flash", False):
                chunks.append(chunk)
            
            # Should have content chunk and token chunk
            content_chunks = [c for c in chunks if c.type == "content"]
            token_chunks = [c for c in chunks if c.type == "tokens"]
            
            assert len(content_chunks) == 1
            assert len(token_chunks) == 1
            assert content_chunks[0].content == "Hello world!"
            assert token_chunks[0].tokens == 20
    
    @pytest.mark.asyncio
    async def test_generate_response_thinking_mode(self, gemini_service):
        """Test core response generation in thinking mode"""
        mock_response = mock_gemini_thinking_response("Hello!", "Let me think...", 30, 8)
        
        with patch.object(gemini_service, '_generate_content_stream_async') as mock_stream:
            mock_stream.return_value = async_generator_from_list([mock_response])
            
            chunks = []
            async for chunk in gemini_service._generate_response("Test", "gemini-2.5-pro", True):
                chunks.append(chunk)
            
            # Should have thought chunk, content chunk, and token chunk
            thought_chunks = [c for c in chunks if c.type == "thought"]
            content_chunks = [c for c in chunks if c.type == "content"]
            token_chunks = [c for c in chunks if c.type == "tokens"]
            
            assert len(thought_chunks) == 1
            assert len(content_chunks) == 1
            assert len(token_chunks) == 1
            assert thought_chunks[0].content == "Let me think..."
            assert content_chunks[0].content == "Hello!"
            assert token_chunks[0].tokens == 30
            assert token_chunks[0].thoughts_tokens == 8
    
    @pytest.mark.asyncio
    async def test_generate_response_error_handling(self, gemini_service):
        """Test error handling in response generation"""
        with patch.object(gemini_service, '_generate_content_stream_async') as mock_stream:
            mock_stream.side_effect = Exception("API Error")
            
            chunks = []
            async for chunk in gemini_service._generate_response("Test", "gemini-2.5-flash", False):
                chunks.append(chunk)
            
            # Should have error chunk
            error_chunks = [c for c in chunks if c.type == "error"]
            assert len(error_chunks) == 1
            assert "API Error" in error_chunks[0].error
    
    def test_get_conversation_history(self, gemini_service):
        """Test conversation history retrieval"""
        # Mock memory messages
        mock_messages = [Mock(), Mock()]
        gemini_service._memory.chat_memory.messages = mock_messages
        
        history = gemini_service._get_conversation_history()
        
        assert history == mock_messages
    
    def test_build_gemini_contents(self, gemini_service):
        """Test building Gemini API contents from conversation history"""
        from langchain.schema import AIMessage, HumanMessage
        
        conversation_history = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!"),
            HumanMessage(content="How are you?")
        ]
        
        contents = gemini_service._build_gemini_contents(conversation_history)
        
        assert len(contents) == 3
        assert contents[0]["role"] == "user"
        assert contents[0]["parts"][0]["text"] == "Hello"
        assert contents[1]["role"] == "model"
        assert contents[1]["parts"][0]["text"] == "Hi there!"
        assert contents[2]["role"] == "user"
        assert contents[2]["parts"][0]["text"] == "How are you?"
    
    @pytest.mark.asyncio
    async def test_generate_content_stream_async(self, gemini_service):
        """Test async wrapper for content generation"""
        mock_generator = [mock_gemini_response("Test", 10)]
        
        with patch.object(gemini_service.client.models, 'generate_content_stream') as mock_generate:
            mock_generate.return_value = mock_generator
            
            chunks = []
            async for chunk in gemini_service._generate_content_stream_async(
                "test-model", [], Mock()
            ):
                chunks.append(chunk)
            
            assert len(chunks) == 1
            assert chunks[0].candidates[0].content.parts[0].text == "Test"