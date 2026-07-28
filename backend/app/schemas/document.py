from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional, List

class DocumentChunkResponse(BaseModel):
    id: UUID
    document_id: UUID
    document_version_id: UUID
    content: str
    page_number: Optional[int] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    heading: Optional[str] = None
    heading_path: Optional[List[str]] = None
    sheet_name: Optional[str] = None
    row_start: Optional[int] = None
    row_end: Optional[int] = None
    chunk_order: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentVersionResponse(BaseModel):
    id: UUID
    document_id: UUID
    version_number: int
    file_hash: str
    parser_version: Optional[str] = None
    chunking_version: Optional[str] = None
    embedding_model: Optional[str] = None
    extraction_prompt_version: Optional[str] = None
    is_active: bool
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentResponse(BaseModel):
    id: UUID
    file_name: str
    original_file_name: str
    file_path: str
    file_type: str
    file_hash: str
    status: str
    is_enabled: bool = True
    routing_result: Optional[str] = None
    active_version_id: Optional[UUID] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentDetailResponse(DocumentResponse):
    versions: List[DocumentVersionResponse] = []
    chunks_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class ProcessingJobResponse(BaseModel):
    id: UUID
    document_id: UUID
    document_version_id: Optional[UUID] = None
    job_type: str
    status: str
    retry_count: int
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
