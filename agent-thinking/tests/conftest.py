"""
Common test fixtures and utilities for the test suite
"""

import asyncio
import uuid
from typing import AsyncGenerator, List
from unittest.mock import AsyncMock, Mock, patch

import pytest
from gpt_agent.domain import Question, Session, SessionBase, StreamingChunk
from gpt_agent.services.gemini_agent import GeminiService
from gpt_agent.services.openai_agent import Agent


@pytest.fixture
def mock_session():
    """Create a mock session for testing"""
    return Session(
        id=uuid.uuid4(),
        user="test_user",
        locales=["en-US"]
    )


@pytest.fixture
def mock_session_base():
    """Create a mock session base for testing"""
    return SessionBase(locales=["en-US"])


@pytest.fixture
def mock_question(mock_session):
    """Create a mock question for testing"""
    return Question(
        id=uuid.uuid4(),
        session=mock_session,
        question="Test question",
        answer="Test answer"
    )


@pytest.fixture
def mock_streaming_chunks():
    """Create mock streaming chunks for testing"""
    return [
        StreamingChunk(type="content", content="Hello "),
        StreamingChunk(type="content", content="world!"),
        StreamingChunk(type="tokens", tokens=15),
        StreamingChunk(type="end")
    ]


@pytest.fixture
def mock_thinking_chunks():
    """Create mock thinking streaming chunks for testing"""
    return [
        StreamingChunk(type="thought", content="Let me think... "),
        StreamingChunk(type="content", content="Hello "),
        StreamingChunk(type="content", content="world!"),
        StreamingChunk(type="tokens", tokens=25, thoughts_tokens=10),
        StreamingChunk(type="end")
    ]


@pytest.fixture
def mock_gemini_service(mock_session):
    """Create a mock Gemini service"""
    with patch('gpt_agent.services.gemini_agent.genai.Client'):
        service = GeminiService(mock_session)
        return service


@pytest.fixture
def mock_openai_agent(mock_session):
    """Create a mock OpenAI agent"""
    with patch('gpt_agent.services.openai_agent.AzureChatOpenAI'), \
         patch('gpt_agent.services.openai_agent.ChatOpenAI'), \
         patch('gpt_agent.services.openai_agent.FileChatMessageHistory'):
        agent = Agent(mock_session)
        return agent


@pytest.fixture
def mock_repositories():
    """Mock all repositories"""
    with patch('gpt_agent.api.sessions_repo') as mock_sessions_repo, \
         patch('gpt_agent.api.questions_repo') as mock_questions_repo, \
         patch('gpt_agent.api.transcriptions_repo') as mock_transcriptions_repo:
        
        # Configure mock repositories
        mock_sessions_repo.save_session = AsyncMock()
        mock_sessions_repo.find_session = AsyncMock()
        mock_questions_repo.save_question = AsyncMock()
        mock_transcriptions_repo.save_audio = AsyncMock()
        
        yield {
            'sessions_repo': mock_sessions_repo,
            'questions_repo': mock_questions_repo,
            'transcriptions_repo': mock_transcriptions_repo
        }


@pytest.fixture
def mock_environment_variables():
    """Mock environment variables for testing"""
    env_vars = {
        'GOOGLE_API_KEY': 'test_gemini_key',
        'OPENAI_API_KEY': 'test_openai_key',
        'SYSTEM_PROMPT': 'You are a helpful assistant',
        'TEMPERATURE': '0.7',
        'MODEL_NAME': 'gpt-4',
        'GEMINI_FLASH_MODEL': 'gemini-2.5-flash',
        'GEMINI_PRO_MODEL': 'gemini-2.5-pro',
        'GEMINI_TEMPERATURE': '0.7',
        'GEMINI_TOP_P': '0.9',
        'GEMINI_TOP_K': '40',
        'GEMINI_MAX_OUTPUT_TOKENS': '4096',
        'GEMINI_CHUNK_DELAY': '0.01',
        'AGENT_MAX_ITERATIONS': '3'
    }
    
    with patch.dict('os.environ', env_vars):
        yield env_vars


async def async_generator_from_list(items: List) -> AsyncGenerator:
    """Helper to create async generator from list"""
    for item in items:
        yield item


def mock_gemini_response(content: str, token_count: int = 10):
    """Create a mock Gemini API response"""
    mock_response = Mock()
    mock_response.candidates = [Mock()]
    mock_response.candidates[0].content = Mock()
    mock_response.candidates[0].content.parts = [Mock()]
    mock_response.candidates[0].content.parts[0].text = content
    mock_response.candidates[0].content.parts[0].thought = False
    mock_response.usage_metadata = Mock()
    mock_response.usage_metadata.total_token_count = token_count
    return mock_response


def mock_gemini_thinking_response(content: str, thought: str, token_count: int = 20, thought_tokens: int = 8):
    """Create a mock Gemini thinking API response"""
    mock_response = Mock()
    mock_response.candidates = [Mock()]
    mock_response.candidates[0].content = Mock()
    mock_response.candidates[0].content.parts = [Mock(), Mock()]
    
    # Thought part
    mock_response.candidates[0].content.parts[0].text = thought
    mock_response.candidates[0].content.parts[0].thought = True
    
    # Content part  
    mock_response.candidates[0].content.parts[1].text = content
    mock_response.candidates[0].content.parts[1].thought = False
    
    mock_response.usage_metadata = Mock()
    mock_response.usage_metadata.total_token_count = token_count
    mock_response.usage_metadata.thoughts_token_count = thought_tokens
    return mock_response