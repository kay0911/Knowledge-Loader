import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.postgres import get_db
from app.models.llm_key import LLMKey
from app.schemas.llm_key import (
    LLMKeyCreate, LLMKeyUpdate, LLMKeyResponse, LLMKeyRotationStatus
)
from app.services.key_rotation_service import KeyRotationService

router = APIRouter(prefix="/keys", tags=["LLM API Key Rotation"])

def to_key_response(key_obj: LLMKey) -> LLMKeyResponse:
    return LLMKeyResponse(
        id=key_obj.id,
        provider=key_obj.provider,
        name=key_obj.name,
        masked_key=KeyRotationService.mask_key(key_obj.api_key),
        is_active=key_obj.is_active,
        status=key_obj.status,
        usage_count=key_obj.usage_count,
        error_count=key_obj.error_count,
        last_used_at=key_obj.last_used_at,
        last_error_at=key_obj.last_error_at,
        created_at=key_obj.created_at,
        updated_at=key_obj.updated_at
    )

@router.get("/", response_model=List[LLMKeyResponse])
def list_api_keys(provider: str = "gemini", db: Session = Depends(get_db)):
    """
    Danh sách các API Key trong pool xoay key (Masked bảo mật).
    """
    KeyRotationService.seed_default_key_if_empty(db, provider)
    keys = db.query(LLMKey).filter(LLMKey.provider == provider).order_by(LLMKey.created_at.asc()).all()
    return [to_key_response(k) for k in keys]

@router.post("/", response_model=LLMKeyResponse, status_code=status.HTTP_211_CREATED if hasattr(status, 'HTTP_211_CREATED') else 201)
def add_api_key(payload: LLMKeyCreate, db: Session = Depends(get_db)):
    """
    Thêm một LLM API Key mới vào pool xoay key.
    """
    clean_key = payload.api_key.strip()
    if not clean_key:
        raise HTTPException(status_code=400, detail="API Key không được để trống.")

    # Check duplicate
    existing = db.query(LLMKey).filter(LLMKey.api_key == clean_key).first()
    if existing:
        raise HTTPException(status_code=400, detail="API Key này đã tồn tại trong hệ thống.")

    new_key = LLMKey(
        provider=payload.provider.lower(),
        api_key=clean_key,
        name=payload.name or f"Key {payload.provider.upper()} ({KeyRotationService.mask_key(clean_key)})",
        is_active=payload.is_active,
        status="ACTIVE"
    )
    db.add(new_key)
    db.commit()
    db.refresh(new_key)
    return to_key_response(new_key)

@router.delete("/{key_id}")
def delete_api_key(key_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Xóa một API Key khỏi hệ thống.
    """
    key_obj = db.query(LLMKey).filter(LLMKey.id == key_id).first()
    if not key_obj:
        raise HTTPException(status_code=404, detail="Không tìm thấy API Key yêu cầu.")

    db.delete(key_obj)
    db.commit()
    return {"message": "Đã xóa API Key thành công.", "id": str(key_id)}

@router.patch("/{key_id}", response_model=LLMKeyResponse)
def update_api_key(key_id: uuid.UUID, payload: LLMKeyUpdate, db: Session = Depends(get_db)):
    """
    Cập nhật trạng thái (Bật/Tắt is_active, Đổi tên, Reset status) của API Key.
    """
    key_obj = db.query(LLMKey).filter(LLMKey.id == key_id).first()
    if not key_obj:
        raise HTTPException(status_code=404, detail="Không tìm thấy API Key yêu cầu.")

    if payload.name is not None:
        key_obj.name = payload.name
    if payload.is_active is not None:
        key_obj.is_active = payload.is_active
    if payload.status is not None:
        key_obj.status = payload.status
        if payload.status == "ACTIVE":
            key_obj.error_count = 0

    db.commit()
    db.refresh(key_obj)
    return to_key_response(key_obj)

@router.get("/status", response_model=LLMKeyRotationStatus)
def get_rotation_status(provider: str = "gemini", db: Session = Depends(get_db)):
    """
    Thống kê tổng quan trạng thái xoay key (Tổng số key, Active, Rate limited, Key hiện tại).
    """
    KeyRotationService.seed_default_key_if_empty(db, provider)
    keys = db.query(LLMKey).filter(LLMKey.provider == provider).all()
    
    total = len(keys)
    active = sum(1 for k in keys if k.is_active and k.status == "ACTIVE")
    exhausted = sum(1 for k in keys if k.status == "QUOTA_EXCEEDED")
    disabled = sum(1 for k in keys if not k.is_active or k.status in ("DISABLED", "INVALID"))

    raw_key, chosen_obj = KeyRotationService.get_valid_api_key(db, provider)

    return LLMKeyRotationStatus(
        total_keys=total,
        active_keys=active,
        exhausted_keys=exhausted,
        disabled_keys=disabled,
        current_key_id=chosen_obj.id if chosen_obj else None,
        current_masked_key=KeyRotationService.mask_key(raw_key) if raw_key else None
    )

@router.post("/reset-exhausted")
def reset_exhausted_keys(provider: str = "gemini", db: Session = Depends(get_db)):
    """
    Reset toàn bộ các key bị dính lỗi giới hạn Quota (429) quay về trạng thái ACTIVE.
    """
    count = KeyRotationService.reset_all_exhausted_keys(db, provider)
    return {"message": f"Đã reset thành công {count} API Key bị dính quota.", "reset_count": count}

@router.post("/rotate")
def trigger_key_rotation(provider: str = "gemini", db: Session = Depends(get_db)):
    """
    Thử nghiệm kích hoạt xoay sang API Key tiếp theo trong pool.
    """
    raw_key, key_obj = KeyRotationService.get_valid_api_key(db, provider)
    return {
        "message": "Đã xoay sang API Key tiếp theo trong pool",
        "key_id": str(key_obj.id) if key_obj else None,
        "name": key_obj.name if key_obj else "Env Key",
        "masked_key": KeyRotationService.mask_key(raw_key),
        "status": key_obj.status if key_obj else "ACTIVE"
    }
