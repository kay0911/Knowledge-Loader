from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.postgres import SessionLocal
from app.models.user import User
from app.schemas.user import UserLogin, Token, UserOut, ProfileUpdate, ContactAdminRequest
from app.core.security import verify_password, hash_password, create_access_token
from app.api.deps import get_current_user, get_db
from app.core.logging import logger

router = APIRouter()

@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticate user with username/email and password.
    Returns JWT access token.
    """
    q = payload.username.strip()
    user = db.query(User).filter(
        (User.username == q) | (User.email == q)
    ).first()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tên đăng nhập hoặc mật khẩu không chính xác."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản này đã bị khóa. Vui lòng liên hệ Admin."
        )

    access_token = create_access_token(data={"sub": str(user.id), "username": user.username, "role": user.role})
    logger.info(f"User '{user.username}' (Role: {user.role}) logged in successfully.")
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserOut.model_validate(user)
    )

@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    """
    Get profile information of currently authenticated user.
    """
    return current_user

@router.put("/profile", response_model=UserOut)
def update_profile(
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update profile details (full_name) or change password.
    """
    if payload.full_name is not None:
        current_user.full_name = payload.full_name.strip()

    if payload.new_password:
        if not payload.current_password or not verify_password(payload.current_password, current_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mật khẩu hiện tại không chính xác."
            )
        if len(payload.new_password) < 4:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mật khẩu mới phải có ít nhất 4 ký tự."
            )
        current_user.hashed_password = hash_password(payload.new_password)

    db.commit()
    db.refresh(current_user)
    logger.info(f"User '{current_user.username}' updated profile.")
    return current_user

@router.post("/contact-admin")
def contact_admin(payload: ContactAdminRequest):
    """
    Submit a request/contact message to Administrator for account creation.
    """
    logger.info(f"Account Registration Request from {payload.full_name} ({payload.email}): {payload.note}")
    return {
        "message": "Yêu cầu của bạn đã được gửi tới Quản trị viên. Chúng tôi sẽ liên hệ lại qua email trong thời gian sớm nhất!"
    }
