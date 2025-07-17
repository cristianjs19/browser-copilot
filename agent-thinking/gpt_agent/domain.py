import uuid
from typing import List, Optional

from pydantic import BaseModel, Field


class StreamingChunk(BaseModel):
    """Streaming response chunk model - core domain object for all streaming responses"""
    type: str = Field(..., description="Chunk type: content, thought, tokens, end, error")
    content: Optional[str] = Field(default=None, description="Chunk content")
    tokens: Optional[int] = Field(default=None, description="Total token count")
    thoughts_tokens: Optional[int] = Field(default=None, description="Thinking tokens count")
    error: Optional[str] = Field(default=None, description="Error message")


class SessionBase(BaseModel):
    locales: List[str]


class Session(SessionBase):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    user: str


class Question(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    session: Session = Field(exclude=True)
    question: str
    answer: str

class TranscriptionQuestion(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    session: Session = Field(exclude=True)
    base64: str
