from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional, List, Any

class CitationResponse(BaseModel):
    source_id: str
    document_id: UUID
    file_name: str
    page_number: Optional[int] = None
    heading: Optional[str] = None
    sheet_name: Optional[str] = None
    row_start: Optional[int] = None
    row_end: Optional[int] = None
    snippet: str

    model_config = ConfigDict(from_attributes=True)


class ChatRequest(BaseModel):
    question: str
    session_id: Optional[UUID] = None


class ChatResponse(BaseModel):
    chat_id: UUID
    session_id: UUID
    answer: str
    citations: List[CitationResponse]

    model_config = ConfigDict(from_attributes=True)


class ChatLogResponse(BaseModel):
    id: UUID
    session_id: UUID
    question: str
    answer: Optional[str] = None
    retrieved_chunk_ids: Optional[List[UUID]] = None
    graph_context: Optional[Any] = None
    citations: Optional[List[CitationResponse]] = None
    latency_ms: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
