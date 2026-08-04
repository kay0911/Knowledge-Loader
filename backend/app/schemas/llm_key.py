import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class LLMKeyBase(BaseModel):
    name: Optional[str] = Field(None, description="Tên gợi nhớ cho API Key")
    provider: str = Field("gemini", description="Nhà cung cấp AI (gemini, cohere, openai)")
    is_active: bool = Field(True, description="Trạng thái kích hoạt key")

class LLMKeyCreate(LLMKeyBase):
    api_key: str = Field(..., description="Giá trị API Key thực tế (ví dụ: AIzaSy...)")

class LLMKeyUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    status: Optional[str] = None

class LLMKeyResponse(BaseModel):
    id: uuid.UUID
    provider: str
    name: Optional[str] = None
    masked_key: str
    is_active: bool
    status: str
    usage_count: int
    error_count: int
    last_used_at: Optional[datetime] = None
    last_error_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class LLMKeyRotationStatus(BaseModel):
    total_keys: int
    active_keys: int
    exhausted_keys: int
    disabled_keys: int
    current_key_id: Optional[uuid.UUID] = None
    current_masked_key: Optional[str] = None
