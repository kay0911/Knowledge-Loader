from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserUpdate, UserOut
from app.core.security import hash_password
from app.api.deps import get_db, require_role
from app.core.logging import logger

router = APIRouter()

@router.get("/", response_model=List[UserOut])
def list_users(
    search: Optional[str] = None,
    role: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "SUBADMIN"]))
):
    """
    List all registered users (Restricted to ADMIN or SUBADMIN).
    Supports optional search by username/email/full_name and filtering by role.
    """
    query = db.query(User)

    if search and search.strip():
        s = f"%{search.strip()}%"
        query = query.filter(
            (User.username.ilike(s)) | (User.email.ilike(s)) | (User.full_name.ilike(s))
        )

    if role and role.strip():
        query = query.filter(User.role == role.strip().upper())

    users = query.order_by(User.created_at.desc()).all()
    return users

@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "SUBADMIN"]))
):
    """
    Create a new user, subadmin, or admin account (Restricted to ADMIN/SUBADMIN).
    Subadmins cannot create ADMIN accounts.
    """
    target_role = payload.role.strip().upper()
    if target_role not in ["ADMIN", "SUBADMIN", "USER"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vai trò (Role) không hợp lệ. Chỉ chấp nhận: ADMIN, SUBADMIN, USER."
        )

    # SUBADMIN safety check
    if current_user.role == "SUBADMIN" and target_role == "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Subadmin không có quyền tạo tài khoản ADMIN tối cao."
        )

    # Check username uniqueness
    existing_username = db.query(User).filter(User.username == payload.username.strip()).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tên đăng nhập '{payload.username}' đã tồn tại trên hệ thống."
        )

    # Check email uniqueness
    if payload.email and payload.email.strip():
        existing_email = db.query(User).filter(User.email == payload.email.strip()).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Email '{payload.email}' đã được đăng ký cho tài khoản khác."
            )

    new_user = User(
        username=payload.username.strip(),
        email=payload.email.strip() if payload.email else None,
        full_name=payload.full_name.strip() if payload.full_name else None,
        hashed_password=hash_password(payload.password),
        role=target_role,
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    logger.info(f"User '{new_user.username}' (Role: {new_user.role}) created by Admin '{current_user.username}'.")
    return new_user

@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "SUBADMIN"]))
):
    """
    Update details, role, status, or password of a target user.
    """
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tài khoản cần sửa không tồn tại."
        )

    # Subadmin permissions check
    if current_user.role == "SUBADMIN":
        if target_user.role == "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Subadmin không có quyền chỉnh sửa tài khoản ADMIN tối cao."
            )
        if payload.role and payload.role.upper() == "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Subadmin không có quyền thăng cấp tài khoản lên ADMIN."
            )

    if payload.full_name is not None:
        target_user.full_name = payload.full_name.strip()

    if payload.email is not None:
        email_str = payload.email.strip() if payload.email else None
        if email_str and email_str != target_user.email:
            existing = db.query(User).filter(User.email == email_str, User.id != user_id).first()
            if existing:
                raise HTTPException(status_code=400, detail="Email này đã được dùng cho tài khoản khác.")
        target_user.email = email_str

    if payload.role is not None:
        r_str = payload.role.strip().upper()
        if r_str in ["ADMIN", "SUBADMIN", "USER"]:
            target_user.role = r_str

    if payload.is_active is not None:
        # Prevent self-deactivation of current admin
        if str(target_user.id) == str(current_user.id) and not payload.is_active:
            raise HTTPException(status_code=400, detail="Bạn không thể tự khóa tài khoản của chính mình!")
        target_user.is_active = payload.is_active

    if payload.password and payload.password.strip():
        if len(payload.password.strip()) < 4:
            raise HTTPException(status_code=400, detail="Mật khẩu mới phải có ít nhất 4 ký tự.")
        target_user.hashed_password = hash_password(payload.password.strip())

    db.commit()
    db.refresh(target_user)
    logger.info(f"User '{target_user.username}' updated by Admin '{current_user.username}'.")
    return target_user

@router.delete("/{user_id}")
def delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"]))
):
    """
    Deactivate or delete a user account (Restricted to ADMIN).
    """
    if str(user_id) == str(current_user.id):
        raise HTTPException(status_code=400, detail="Bạn không thể tự xóa tài khoản của chính mình!")

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Tài khoản không tồn tại.")

    username = target_user.username
    db.delete(target_user)
    db.commit()
    logger.info(f"User '{username}' (ID: {user_id}) deleted by Admin '{current_user.username}'.")
    return {"message": f"Đã xóa tài khoản '{username}' thành công."}
