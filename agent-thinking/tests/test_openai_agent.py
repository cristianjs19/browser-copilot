"""
Tests for OpenAI agent functionality
"""

import asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from gpt_agent.domain import StreamingChunk
from gpt_agent.services.openai_agent import (
    Agent,
    AgentAction,
    AgentFlow,
    AgentStep,
    TokenUsageTracker,
)

from tests.conftest import async_generator_from_list


class TestTokenUsageTracker:
    """Test TokenUsageTracker functionality"""
    
    def test_token_usage_tracker_initialization(self):
        """Test TokenUsageTracker initialization"""
        tracker = TokenUsageTracker()
        
        assert tracker.prompt_tokens == 0
        assert tracker.completion_tokens == 0
        assert tracker.total_tokens == 0
    
    def test_update_from_response_with_usage(self):
        """Test updating token usage from OpenAI response"""
        tracker = TokenUsageTracker()
        
        # Mock response with usage data
        response = Mock()
        response.usage = Mock()
        response.usage.prompt_tokens = 10
        response.usage.completion_tokens = 15
        response.usage.total_tokens = 25
        
        tracker.update_from_response(response)
        
        assert tracker.prompt_tokens == 10
        assert tracker.completion_tokens == 15
        assert tracker.total_tokens == 25
    
    def test_update_from_response_without_usage(self):
        """Test updating token usage when response has no usage data"""
        tracker = TokenUsageTracker()
        
        # Mock response without usage data
        response = Mock()
        response.usage = None
        
        tracker.update_from_response(response)
        
        assert tracker.prompt_tokens == 0
        assert tracker.completion_tokens == 0
        assert tracker.total_tokens == 0
    
    def test_calculate_tokens_word_based(self):
        """Test token calculation using word-based estimation"""
        tracker = TokenUsageTracker()
        
        question = "What is the weather like today?"
        response = "The weather is sunny and warm with a temperature of 25 degrees."
        
        tokens = tracker.calculate_tokens(question, response)
        
        # Should be positive integer based on word count
        assert tokens > 0
        assert isinstance(tokens, int)
        
        # Should be roughly 75% of combined word count
        word_count = len(question.split()) + len(response.split())
        expected_tokens = max(1, int(word_count * 0.75))
        assert tokens == expected_tokens


class TestAgentFlow:
    """Test AgentFlow functionality"""
    
    def test_agent_flow_creation(self):
        """Test AgentFlow creation with steps"""
        step1 = AgentStep(action=AgentAction.GOTO, value="https://example.com")
        step2 = AgentStep(action=AgentAction.CLICK, selector="#button")
        
        flow = AgentFlow(steps=[step1, step2])
        
        assert len(flow.steps) == 2
        assert flow.steps[0].action == AgentAction.GOTO
        assert flow.steps[0].value == "https://example.com"
        assert flow.steps[1].action == AgentAction.CLICK
        assert flow.steps[1].selector == "#button"
    
    def test_agent_flow_message_helper(self):
        """Test AgentFlow.message static method"""
        flow = AgentFlow.message("Hello world")
        
        assert len(flow.steps) == 1
        assert flow.steps[0].action == AgentAction.MESSAGE
        assert flow.steps[0].value == "Hello world"


class TestAgent:
    """Test OpenAI Agent functionality"""
    
    @pytest.fixture
    def openai_agent(self, mock_session, mock_environment_variables):
        """Create Agent instance for testing"""
        with patch('gpt_agent.services.openai_agent.FileChatMessageHistory') as mock_file_history, \
             patch('gpt_agent.services.openai_agent.ConversationBufferMemory') as mock_memory, \
             patch('gpt_agent.services.openai_agent.ChatOpenAI') as mock_chat_openai, \
             patch('gpt_agent.services.openai_agent.OpenAIFunctionsAgent') as mock_agent_class, \
             patch('gpt_agent.services.openai_agent.AgentExecutor') as mock_executor, \
             patch('gpt_agent.services.openai_agent.get_session_path', return_value='/tmp/test'):
            
            # Setup memory mock
            mock_memory_instance = Mock()
            mock_memory_instance.memory_key = "chat_history"
            mock_memory_instance.chat_memory = Mock()
            mock_memory_instance.chat_memory.messages = []
            mock_memory_instance.chat_memory.add_user_message = Mock()
            mock_memory_instance.chat_memory.add_ai_message = Mock()
            mock_memory.return_value = mock_memory_instance
            
            # Setup other mocks
            mock_chat_openai.return_value = Mock()
            mock_agent_class.from_llm_and_tools.return_value = Mock()
            mock_executor.return_value = Mock()
            
            agent = Agent(mock_session)
            return agent
    
    def test_agent_initialization(self, openai_agent, mock_session):
        """Test Agent initialization"""
        assert openai_agent._session == mock_session
        assert openai_agent._memory is not None
        assert openai_agent._agent is not None
    
    def test_is_azure_detection(self):
        """Test Azure OpenAI detection"""
        # Test Azure URL
        assert Agent._is_azure("https://myresource.openai.azure.com") is True
        
        # Test regular OpenAI URL
        assert Agent._is_azure("https://api.openai.com") is False
        
        # Test None
        assert Agent._is_azure(None) is False
    
    def test_build_llm_openai(self, openai_agent):
        """Test building OpenAI LLM (non-Azure)"""
        with patch('gpt_agent.services.openai_agent.ChatOpenAI') as mock_chat_openai:
            mock_llm = Mock()
            mock_chat_openai.return_value = mock_llm
            
            llm = openai_agent._build_llm()
            
            mock_chat_openai.assert_called_once_with(
                model_name="gpt-4",
                temperature=0.7,
                verbose=True,
                streaming=True
            )
            assert llm == mock_llm
    
    def test_start_session(self, openai_agent):
        """Test session initialization"""
        openai_agent.start_session()
        
        # Verify that locale was added to memory
        openai_agent._memory.chat_memory.add_user_message.assert_called_once()
        call_args = openai_agent._memory.chat_memory.add_user_message.call_args
        assert "en-US" in call_args[0][0]
    
    def test_transcript_openai(self, openai_agent):
        """Test transcription with OpenAI"""
        with patch('gpt_agent.services.openai_agent.OpenAI') as mock_openai, \
             patch('builtins.open', mock_open_file := Mock()):
            mock_client = Mock()
            mock_openai.return_value = mock_client
            
            # Mock transcription response
            mock_response = Mock()
            mock_response.text = "Hello world"
            mock_client.audio.transcriptions.create.return_value = mock_response
            
            result = openai_agent.transcript("/path/to/audio.webm")
            
            assert result == "Hello world"
            mock_client.audio.transcriptions.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_ask_with_streaming_chunks_simple_response(self, openai_agent):
        """Test streaming response with simple text"""
        with patch('gpt_agent.services.openai_agent.AsyncIteratorCallbackHandler') as mock_callback_class:
            mock_callback = Mock()
            mock_callback_class.return_value = mock_callback
            
            # Mock the streaming tokens as an async generator
            async def mock_aiter():
                for token in ["Hello ", "world", "!"]:
                    yield token
            
            mock_callback.aiter.return_value = mock_aiter()
            
            # Mock the agent run
            openai_agent._agent.arun = AsyncMock(return_value="Hello world!")
            
            chunks = []
            async for chunk in openai_agent.ask_with_streaming_chunks("Test question"):
                chunks.append(chunk)
            
            # Should have content chunks and token chunk
            content_chunks = [c for c in chunks if c.type == "content"]
            token_chunks = [c for c in chunks if c.type == "tokens"]
            
            assert len(content_chunks) == 3  # "Hello ", "world", "!"
            assert len(token_chunks) == 1
            assert content_chunks[0].content == "Hello "
            assert content_chunks[1].content == "world"
            assert content_chunks[2].content == "!"
            assert token_chunks[0].tokens > 0
    
    @pytest.mark.asyncio
    async def test_ask_with_streaming_chunks_tool_response(self, openai_agent):
        """Test streaming response with tool output"""
        with patch('gpt_agent.services.openai_agent.AsyncIteratorCallbackHandler') as mock_callback_class, \
             patch('gpt_agent.services.openai_agent.AgentFlow.model_validate_json') as mock_validate:
            mock_callback = Mock()
            mock_callback_class.return_value = mock_callback
            
            # Mock the streaming tokens as an async generator
            async def mock_aiter():
                for token in ["Processing..."]:
                    yield token
            
            mock_callback.aiter.return_value = mock_aiter()
            
            # Mock tool response
            tool_response = '{"steps": [{"action": "message", "value": "Tool executed"}]}'
            openai_agent._agent.arun = AsyncMock(return_value=tool_response)
            mock_validate.return_value = Mock()  # Valid AgentFlow
            
            chunks = []
            async for chunk in openai_agent.ask_with_streaming_chunks("Use tool"):
                chunks.append(chunk)
            
            # Should have streaming content and tool output
            content_chunks = [c for c in chunks if c.type == "content"]
            
            assert len(content_chunks) >= 2  # Streamed content + tool output
            assert any(c.content == "Processing..." for c in content_chunks)
            assert any(tool_response in c.content for c in content_chunks)
    
    @pytest.mark.asyncio
    async def test_ask_with_streaming_chunks_error_handling(self, openai_agent):
        """Test error handling in streaming response"""
        with patch('gpt_agent.services.openai_agent.AsyncIteratorCallbackHandler') as mock_callback_class:
            mock_callback = Mock()
            mock_callback_class.return_value = mock_callback
            
            # Mock empty async generator
            async def mock_aiter():
                return
                yield  # Never reached
            
            mock_callback.aiter.return_value = mock_aiter()
            
            # Mock error in agent run
            openai_agent._agent.arun = AsyncMock(side_effect=Exception("Agent error"))
            
            chunks = []
            async for chunk in openai_agent.ask_with_streaming_chunks("Test question"):
                chunks.append(chunk)
            
            # Should have error chunk
            error_chunks = [c for c in chunks if c.type == "error"]
            assert len(error_chunks) == 1
            assert "Agent error" in error_chunks[0].error
    
    @pytest.mark.asyncio
    async def test_ask_legacy_method(self, openai_agent):
        """Test legacy ask method for backward compatibility"""
        with patch('gpt_agent.services.openai_agent.AsyncIteratorCallbackHandler') as mock_callback_class:
            mock_callback = Mock()
            mock_callback_class.return_value = mock_callback
            
            # Mock the streaming tokens as an async generator
            async def mock_aiter():
                for token in ["Hello ", "world"]:
                    yield token
            
            mock_callback.aiter.return_value = mock_aiter()
            
            # Mock the agent run
            openai_agent._agent.arun = AsyncMock(return_value="Hello world")
            
            tokens = []
            async for token in openai_agent.ask("Test question"):
                tokens.append(token)
            
            assert "Hello " in tokens
            assert "world" in tokens
    
    def test_build_agent_with_tools(self, openai_agent):
        """Test agent building with tools"""
        from gpt_agent.services.openai_agent import clock, contact_abstracta
        
        # The agent should be built with the provided tools
        assert openai_agent._agent is not None
        
        # Test the clock tool directly with proper input
        result = clock.invoke({})
        assert isinstance(result, str)
        assert len(result) > 0  # Should return current time string
    
    def test_contact_abstracta_tool(self):
        """Test the contact_abstracta tool"""
        from gpt_agent.services.openai_agent import contact_abstracta
        
        result = contact_abstracta.invoke({"full_name": "John Doe"})
        
        # Should return JSON string with steps
        assert isinstance(result, str)
        assert "steps" in result
        assert "John Doe" in result
        assert "abstracta.us" in result