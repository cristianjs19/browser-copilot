import logging
import os
import traceback
from typing import Annotated, AsyncGenerator, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from gpt_agent.auth import get_current_user
from gpt_agent.domain import (
    Question,
    Session,
    SessionBase,
    StreamingChunk,
    TranscriptionQuestion,
)
from gpt_agent.file_system_repos import (
    QuestionsRepository,
    SessionsRepository,
    TranscriptionsRepository,
)
from gpt_agent.services.gemini_agent import GeminiService
from gpt_agent.services.openai_agent import Agent

logging.basicConfig()
logger = logging.getLogger("gpt_agent")
logger.level = logging.DEBUG
logging.getLogger().level = logging.DEBUG

app = FastAPI()
assets_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'assets')
templates = Jinja2Templates(directory=assets_path)
sessions_repo = SessionsRepository()
questions_repo = QuestionsRepository()
transcriptions_repo = TranscriptionsRepository()


@app.get('/manifest.json')
async def get_manifest(request: Request) -> Response:
    return templates.TemplateResponse("manifest.json", {
        "request": request,
        "openid_url": os.getenv("MANIFEST_OPENID_URL", os.getenv("OPENID_URL")),
        "openid_client_id": os.getenv("OPENID_CLIENT_ID"),
        "openid_scope": os.getenv("OPENID_SCOPE"),
        "contact_email": os.getenv("CONTACT_EMAIL")
    }, media_type='application/json')


@app.get('/logo.png')
async def get_logo() -> FileResponse:
    return FileResponse(os.path.join(assets_path, 'logo.png'))


@app.post('/sessions', status_code=status.HTTP_201_CREATED)
async def create_session(req: SessionBase, user: Annotated[str, Depends(get_current_user)]) -> Session:
    ret = Session(**req.model_dump(), user=user)
    await sessions_repo.save_session(ret)
    # Initialize Gemini service for the new session
    gemini_service = GeminiService(ret)
    gemini_service.start_session()
    return ret


class QuestionRequest(BaseModel):
    question: Optional[str] = ""


@app.post('/sessions/{session_id}/questions')
async def answer_question(
        session_id: str, req: QuestionRequest, user: Annotated[str, Depends(get_current_user)]) -> StreamingResponse:
    session = await _find_session(session_id, user)
    # This copilot uses response streaming which allows users to start get a response as soon as
    # possible, which is particularly important when interacting with LLMs that support response
    # streaming and may take some time to end answering a given response.
    # Updated to use StreamingChunk format for consistency with Gemini endpoints
    chunk_generator = _openai_agent_response_stream(req, session)
    return StreamingResponse(_stream_response_chunks(chunk_generator), media_type="text/event-stream")


@app.post('/sessions/{session_id}/chat-gemini')
async def chat(
        session_id: str, req: QuestionRequest, user: Annotated[str, Depends(get_current_user)]) -> StreamingResponse:
    session = await _find_session(session_id, user)
    chunk_generator = _gemini_agent_response_stream(req, session, use_thinking=False)
    return StreamingResponse(_stream_response_chunks(chunk_generator), media_type="text/event-stream")


@app.post('/sessions/{session_id}/thinking-chat-gemini')
async def chat_thinking(
        session_id: str, req: QuestionRequest, user: Annotated[str, Depends(get_current_user)]) -> StreamingResponse:
    session = await _find_session(session_id, user)
    chunk_generator = _gemini_agent_response_stream(req, session, use_thinking=True)
    return StreamingResponse(_stream_response_chunks(chunk_generator), media_type="text/event-stream")


async def _find_session(session_id: str, user: str) -> Session:
    ret = await sessions_repo.find_session(session_id)
    if not ret or ret.user != user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f'session {session_id} not found')
    return ret


async def _create_response_stream(
    request: QuestionRequest,
    session: Session,
    response_generator_func
) -> AsyncGenerator[StreamingChunk, None]:
    """
    Common response stream handler that eliminates code duplication.
    Handles the common pattern: create service/agent -> generate response -> save to repository
    """
    try:
        complete_answer = ""
        
        # Generate response using the provided generator function
        async for chunk in response_generator_func(request.question):
            if chunk.type == "content" and chunk.content:
                complete_answer += chunk.content
            yield chunk
        
        # Save the question and answer to repository
        question = Question(question=request.question, answer=complete_answer, session=session)
        await questions_repo.save_question(question)
        
    except Exception as e:
        logger.error(f"Error in response stream: {str(e)}")
        yield StreamingChunk(type="error", error=str(e))


async def _openai_agent_response_stream(req: QuestionRequest, session: Session) -> AsyncGenerator[StreamingChunk, None]:
    """Generate streaming response using OpenAI agent with StreamingChunk format"""
    def create_openai_generator(question: str):
        agent = Agent(session)
        return agent.ask_with_streaming_chunks(question)
    
    async for chunk in _create_response_stream(req, session, create_openai_generator):
        yield chunk


async def _gemini_agent_response_stream(req: QuestionRequest, session: Session, use_thinking: bool) -> AsyncGenerator[StreamingChunk, None]:
    """Generate streaming response using Gemini service"""
    def create_gemini_generator(question: str):
        gemini_service = GeminiService(session)
        if use_thinking:
            return gemini_service.generate_thinking_response(question)
        else:
            return gemini_service.generate_standard_response(question)
    
    async for chunk in _create_response_stream(req, session, create_gemini_generator):
        yield chunk


async def _stream_response_chunks(
    chunk_generator: AsyncGenerator[StreamingChunk, None]
) -> AsyncGenerator[str, None]:
    """Convert StreamingChunk objects to Server-Sent Events format."""
    try:
        async for chunk in chunk_generator:
            yield f"data: {chunk.model_dump_json(exclude_none=True)}\n\n"
        end_chunk = StreamingChunk(type="end")
        yield f"data: {end_chunk.model_dump_json(exclude_none=True)}\n\n"
    except Exception as e:
        traceback.print_exception(e)
        error_chunk = StreamingChunk(type="error", error=str(e))
        yield f"data: {error_chunk.model_dump_json(exclude_none=True)}\n\n"


class TranscriptionRequest(BaseModel):
    file: Optional[str] = ""


class TranscriptionResponse(BaseModel):
    text: str


@app.post('/sessions/{session_id}/transcriptions')
async def answer_transcription(session_id: str, req: TranscriptionRequest, user: Annotated[str, Depends(get_current_user)]) -> TranscriptionResponse:
    session = await _find_session(session_id, user)
    ret = TranscriptionQuestion(base64=req.file, session=session)
    audio_file_path = await transcriptions_repo.save_audio(ret)
    text = Agent(session).transcript(audio_file_path)
    return TranscriptionResponse(text=text)
