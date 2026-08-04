import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.postgres import Base

class LLMKey(Base):
    __tablename__ = "llm_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider = Column(String, nullable=False, default="gemini") # e.g. gemini, cohere, openai
    api_key = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=True) # Description e.g. "Key Backup 1"
    is_active = Column(Boolean, nullable=False, default=True)
    status = Column(String, nullable=False, default="ACTIVE") # ACTIVE, QUOTA_EXCEEDED, INVALID, DISABLED
    usage_count = Column(Integer, nullable=False, default=0)
    error_count = Column(Integer, nullable=False, default=0)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    last_error_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
