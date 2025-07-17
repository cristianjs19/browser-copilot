"""
Tests for FastAPI endpoints and helper functions
"""

import json
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from gpt_agent.api import (
    QuestionRequest,
    TranscriptionRequest,
    _create_response_stream,
    _find_session,
    _stream_response_chunks,
    app,
    get_current_user,
)
from gpt_agent.domain import Session, SessionBase, StreamingChunk

from tests.conftest import async_generator_from_list


class TestAPIEndpoints:
    """Test FastAPI endpoints"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_user(self):
        """Mock authenticated user"""
        return "test_user"
    
    def test_get_manifest(self, client):
        """Test manifest endpoint"""
        with patch.dict('os.environ', {
            'MANIFEST_OPENID_URL': 'https://auth.example.com',
            'OPENID_CLIENT_ID': 'test_client',
            'OPENID_SCOPE': 'openid profile',
            'CONTACT_EMAIL': 'test@example.com'
        }):
            response = client.get('/manifest.json')

            assert response.status_code == 200
            # Corrected assertion: Expect 'application/json' as seen in curl output
            assert response.headers['content-type'] == 'application/json'
    
    def test_get_logo(self, client):
        """Test logo endpoint"""
        # Removed the patch as TestClient can handle FileResponse directly.
        # This prevents the RecursionError.
        response = client.get('/logo.png')

        assert response.status_code == 200
        assert response.headers['content-type'] == 'image/png'
        # Optional: You can also check if the content matches the actual logo file
        # import os
        # from gpt_agent.api import assets_path # Assuming assets_path is accessible or can be mocked
        # with open(os.path.join(assets_path, 'logo.png'), 'rb') as f:
        #     expected_content = f.read()
        # assert response.content == expected_content
    
    @pytest.mark.asyncio
    async def test_create_session(self, client, mock_session_base, mock_repositories):
        """Test session creation endpoint"""
        # Patch repositories and GeminiService as before, as these are global objects
        # and not FastAPI dependencies.
        with patch('gpt_agent.api.sessions_repo', new=mock_repositories['sessions_repo']), \
             patch('gpt_agent.api.GeminiService') as mock_gemini_service:
            
            mock_service = Mock()
            mock_service.start_session = Mock()
            mock_gemini_service.return_value = mock_service
            
            # Override the get_current_user dependency for this test
            app.dependency_overrides[get_current_user] = lambda: "test_user"
            
            try:
                response = client.post('/sessions', json=mock_session_base.model_dump())
                
                assert response.status_code == 201
                response_data = response.json()
                assert response_data['user'] == "test_user"
                assert 'id' in response_data
                assert response_data['locales'] == ["en-US"]
                mock_repositories['sessions_repo'].save_session.assert_called_once()
                mock_gemini_service.assert_called_once()
                mock_service.start_session.assert_called_once()
            finally:
                # Clean up the dependency override after the test
                app.dependency_overrides = {}
    
    @pytest.mark.asyncio
    async def test_answer_question_openai(self, client, mock_session, mock_repositories):
        """Test OpenAI question answering endpoint"""
        with patch('gpt_agent.api.get_current_user', return_value="test_user"), \
             patch('gpt_agent.api._find_session', return_value=mock_session), \
             patch('gpt_agent.api._openai_agent_response_stream') as mock_stream:
            
            # Mock streaming response
            mock_chunks = [
                StreamingChunk(type="content", content="Hello"),
                StreamingChunk(type="tokens", tokens=10)
            ]
            mock_stream.return_value = async_generator_from_list(mock_chunks)
            
            response = client.post(
                f'/sessions/{mock_session.id}/questions',
                json={"question": "Test question"}
            )
            
            assert response.status_code == 200
            assert response.headers['content-type'] == 'text/event-stream; charset=utf-8'
            
            # Verify the stream was called
            mock_stream.assert_called_once()
            call_args = mock_stream.call_args[0]
            assert call_args[0].question == "Test question"
            assert call_args[1] == mock_session
    
    @pytest.mark.asyncio
    async def test_chat_gemini_standard(self, client, mock_session, mock_repositories):
        """Test Gemini standard chat endpoint"""
        with patch('gpt_agent.api.get_current_user', return_value="test_user"), \
             patch('gpt_agent.api._find_session', return_value=mock_session), \
             patch('gpt_agent.api._gemini_agent_response_stream') as mock_stream:
            
            # Mock streaming response
            mock_chunks = [
                StreamingChunk(type="content", content="Hello from Gemini"),
                StreamingChunk(type="tokens", tokens=15)
            ]
            mock_stream.return_value = async_generator_from_list(mock_chunks)
            
            response = client.post(
                f'/sessions/{mock_session.id}/chat-gemini',
                json={"question": "Test question"}
            )
            
            assert response.status_code == 200
            assert response.headers['content-type'] == 'text/event-stream; charset=utf-8'
            
            # Verify the stream was called with correct parameters
            mock_stream.assert_called_once()
            call_args = mock_stream.call_args
            assert call_args[0][0].question == "Test question"
            assert call_args[0][1] == mock_session
            assert call_args[1]['use_thinking'] is False
    
    @pytest.mark.asyncio
    async def test_chat_gemini_thinking(self, client, mock_session, mock_repositories):
        """Test Gemini thinking chat endpoint"""
        with patch('gpt_agent.api.get_current_user', return_value="test_user"), \
             patch('gpt_agent.api._find_session', return_value=mock_session), \
             patch('gpt_agent.api._gemini_agent_response_stream') as mock_stream:
            
            # Mock streaming response with thinking
            mock_chunks = [
                StreamingChunk(type="thought", content="Let me think..."),
                StreamingChunk(type="content", content="Here's my answer"),
                StreamingChunk(type="tokens", tokens=25, thoughts_tokens=10)
            ]
            mock_stream.return_value = async_generator_from_list(mock_chunks)
            
            response = client.post(
                f'/sessions/{mock_session.id}/thinking-chat-gemini',
                json={"question": "Complex question"}
            )
            
            assert response.status_code == 200
            assert response.headers['content-type'] == 'text/event-stream; charset=utf-8'
            
            # Verify the stream was called with thinking enabled
            mock_stream.assert_called_once()
            call_args = mock_stream.call_args
            assert call_args[0][0].question == "Complex question"
            assert call_args[0][1] == mock_session
            assert call_args[1]['use_thinking'] is True
    
    @pytest.mark.asyncio
    async def test_answer_transcription(self, client, mock_session, mock_repositories):
        """Test transcription endpoint"""
        with patch('gpt_agent.api.get_current_user', return_value="test_user"), \
             patch('gpt_agent.api._find_session', return_value=mock_session), \
             patch('gpt_agent.api.Agent') as mock_agent_class:
            
            mock_agent = Mock()
            mock_agent.transcript.return_value = "Hello world"
            mock_agent_class.return_value = mock_agent
            
            mock_repositories['transcriptions_repo'].save_audio.return_value = "/path/to/audio.webm"
            
            response = client.post(
                f'/sessions/{mock_session.id}/transcriptions',
                json={"file": "base64_audio_data"}
            )
            
            assert response.status_code == 200
            response_data = response.json()
            assert response_data['text'] == "Hello world"
            
            # Verify transcription was processed
            mock_repositories['transcriptions_repo'].save_audio.assert_called_once()
            mock_agent.transcript.assert_called_once_with("/path/to/audio.webm")
    
    @pytest.mark.asyncio
    async def test_session_not_found(self, client, mock_repositories):
        """Test session not found error"""
        with patch('gpt_agent.api.get_current_user', return_value="test_user"), \
             patch('gpt_agent.api._find_session', side_effect=HTTPException(status_code=404)):
            
            response = client.post(
                '/sessions/nonexistent-id/questions',
                json={"question": "Test question"}
            )
            
            assert response.status_code == 404


class TestHelperFunctions:
    """Test API helper functions"""
    
    @pytest.mark.asyncio
    async def test_find_session_success(self, mock_session, mock_repositories):
        """Test successful session finding"""
        mock_repositories['sessions_repo'].find_session.return_value = mock_session
        
        result = await _find_session(str(mock_session.id), mock_session.user)
        
        assert result == mock_session
        mock_repositories['sessions_repo'].find_session.assert_called_once_with(str(mock_session.id))
    
    @pytest.mark.asyncio
    async def test_find_session_not_found(self, mock_session, mock_repositories):
        """Test session not found"""
        mock_repositories['sessions_repo'].find_session.return_value = None
        
        with pytest.raises(HTTPException) as exc_info:
            await _find_session(str(mock_session.id), "test_user")
        
        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_find_session_wrong_user(self, mock_session, mock_repositories):
        """Test session access by wrong user"""
        mock_repositories['sessions_repo'].find_session.return_value = mock_session
        
        with pytest.raises(HTTPException) as exc_info:
            await _find_session(str(mock_session.id), "wrong_user")
        
        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_create_response_stream_success(self, mock_session, mock_repositories):
        """Test successful response stream creation"""
        async def mock_generator(question):
            yield StreamingChunk(type="content", content="Hello ")
            yield StreamingChunk(type="content", content="world!")
        
        request = QuestionRequest(question="Test question")
        
        chunks = []
        async for chunk in _create_response_stream(request, mock_session, mock_generator):
            chunks.append(chunk)
        
        # Should have content chunks
        content_chunks = [c for c in chunks if c.type == "content"]
        assert len(content_chunks) == 2
        assert content_chunks[0].content == "Hello "
        assert content_chunks[1].content == "world!"
        
        # Should save question to repository
        mock_repositories['questions_repo'].save_question.assert_called_once()
        saved_question = mock_repositories['questions_repo'].save_question.call_args[0][0]
        assert saved_question.question == "Test question"
        assert saved_question.answer == "Hello world!"
    
    @pytest.mark.asyncio
    async def test_create_response_stream_error(self, mock_session, mock_repositories):
        """Test error handling in response stream"""
        async def mock_generator(question):
            raise Exception("Generator error")
            yield # This line makes it an async generator, but is never reached
        
        request = QuestionRequest(question="Test question")
        
        chunks = []
        async for chunk in _create_response_stream(request, mock_session, mock_generator):
            chunks.append(chunk)
        
        # Should have error chunk
        error_chunks = [c for c in chunks if c.type == "error"]
        assert len(error_chunks) == 1
        assert "Generator error" in error_chunks[0].error
    
    @pytest.mark.asyncio
    async def test_stream_response_chunks_success(self):
        """Test successful response chunk streaming"""
        mock_chunks = [
            StreamingChunk(type="content", content="Hello"),
            StreamingChunk(type="tokens", tokens=10)
        ]
        
        results = []
        async for sse_data in _stream_response_chunks(async_generator_from_list(mock_chunks)):
            results.append(sse_data)
        
        # Should have SSE format with data prefix
        assert len(results) == 3  # 2 chunks + end chunk
        assert all(line.startswith("data: ") for line in results)
        assert all(line.endswith("\n\n") for line in results)
        
        # Parse first chunk
        first_chunk_data = results[0].replace("data: ", "").strip()
        first_chunk = json.loads(first_chunk_data)
        assert first_chunk['type'] == 'content'
        assert first_chunk['content'] == 'Hello'
        
        # Parse end chunk
        end_chunk_data = results[-1].replace("data: ", "").strip()
        end_chunk = json.loads(end_chunk_data)
        assert end_chunk['type'] == 'end'
    
    @pytest.mark.asyncio
    async def test_stream_response_chunks_error(self):
        """Test error handling in response chunk streaming"""
        async def error_generator():
            yield StreamingChunk(type="content", content="Hello")
            raise Exception("Stream error")
        
        results = []
        async for sse_data in _stream_response_chunks(error_generator()):
            results.append(sse_data)
        
        # Should have content chunk and error chunk
        assert len(results) == 2
        
        # Parse error chunk
        error_chunk_data = results[-1].replace("data: ", "").strip()
        error_chunk = json.loads(error_chunk_data)
        assert error_chunk['type'] == 'error'
        assert "Stream error" in error_chunk['error']


class TestRequestModels:
    """Test request/response models"""
    
    def test_question_request_model(self):
        """Test QuestionRequest model"""
        request = QuestionRequest(question="Test question")
        assert request.question == "Test question"
        
        # Test with empty question
        empty_request = QuestionRequest()
        assert empty_request.question == ""
    
    def test_transcription_request_model(self):
        """Test TranscriptionRequest model"""
        request = TranscriptionRequest(file="base64_data")
        assert request.file == "base64_data"
        
        # Test with empty file
        empty_request = TranscriptionRequest()
        assert empty_request.file == ""


class TestIntegrationScenarios:
    """Test integration scenarios"""
    
    @pytest.mark.asyncio
    async def test_openai_response_stream_integration(self, mock_session, mock_repositories):
        """Test OpenAI response stream integration"""
        from gpt_agent.api import _openai_agent_response_stream
        
        with patch('gpt_agent.api.Agent') as mock_agent_class:
            mock_agent = Mock()
            mock_agent_class.return_value = mock_agent
            
            # Mock streaming response
            mock_chunks = [
                StreamingChunk(type="content", content="OpenAI response"),
                StreamingChunk(type="tokens", tokens=20)
            ]
            mock_agent.ask_with_streaming_chunks.return_value = async_generator_from_list(mock_chunks)
            
            request = QuestionRequest(question="Test OpenAI")
            
            chunks = []
            async for chunk in _openai_agent_response_stream(request, mock_session):
                chunks.append(chunk)
            
            # Should have content and token chunks
            content_chunks = [c for c in chunks if c.type == "content"]
            token_chunks = [c for c in chunks if c.type == "tokens"]
            
            assert len(content_chunks) == 1
            assert len(token_chunks) == 1
            assert content_chunks[0].content == "OpenAI response"
            assert token_chunks[0].tokens == 20
            
            # Should save question
            mock_repositories['questions_repo'].save_question.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_gemini_response_stream_integration(self, mock_session, mock_repositories):
        """Test Gemini response stream integration"""
        from gpt_agent.api import _gemini_agent_response_stream
        
        with patch('gpt_agent.api.GeminiService') as mock_service_class:
            mock_service = Mock()
            mock_service_class.return_value = mock_service
            
            # Mock standard response
            mock_chunks = [
                StreamingChunk(type="content", content="Gemini response"),
                StreamingChunk(type="tokens", tokens=18)
            ]
            mock_service.generate_standard_response.return_value = async_generator_from_list(mock_chunks)
            
            request = QuestionRequest(question="Test Gemini")
            
            chunks = []
            async for chunk in _gemini_agent_response_stream(request, mock_session, use_thinking=False):
                chunks.append(chunk)
            
            # Should have content and token chunks
            content_chunks = [c for c in chunks if c.type == "content"]
            token_chunks = [c for c in chunks if c.type == "tokens"]
            
            assert len(content_chunks) == 1
            assert len(token_chunks) == 1
            assert content_chunks[0].content == "Gemini response"
            assert token_chunks[0].tokens == 18
            
            # Should call standard response method
            mock_service.generate_standard_response.assert_called_once_with("Test Gemini")
            
            # Should save question
            mock_repositories['questions_repo'].save_question.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_gemini_thinking_response_stream_integration(self, mock_session, mock_repositories):
        """Test Gemini thinking response stream integration"""
        from gpt_agent.api import _gemini_agent_response_stream
        
        with patch('gpt_agent.api.GeminiService') as mock_service_class:
            mock_service = Mock()
            mock_service_class.return_value = mock_service
            
            # Mock thinking response
            mock_chunks = [
                StreamingChunk(type="thought", content="Thinking..."),
                StreamingChunk(type="content", content="Gemini thinking response"),
                StreamingChunk(type="tokens", tokens=30, thoughts_tokens=12)
            ]
            mock_service.generate_thinking_response.return_value = async_generator_from_list(mock_chunks)
            
            request = QuestionRequest(question="Complex question")
            
            chunks = []
            async for chunk in _gemini_agent_response_stream(request, mock_session, use_thinking=True):
                chunks.append(chunk)
            
            # Should have thought, content, and token chunks
            thought_chunks = [c for c in chunks if c.type == "thought"]
            content_chunks = [c for c in chunks if c.type == "content"]
            token_chunks = [c for c in chunks if c.type == "tokens"]
            
            assert len(thought_chunks) == 1
            assert len(content_chunks) == 1
            assert len(token_chunks) == 1
            assert thought_chunks[0].content == "Thinking..."
            assert content_chunks[0].content == "Gemini thinking response"
            assert token_chunks[0].tokens == 30
            assert token_chunks[0].thoughts_tokens == 12
            
            # Should call thinking response method
            mock_service.generate_thinking_response.assert_called_once_with("Complex question")
            
            # Should save question
            mock_repositories['questions_repo'].save_question.assert_called_once()