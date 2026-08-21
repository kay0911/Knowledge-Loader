from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID

class UserLogin(BaseModel):
    username: str = Field(..., description="Username or Email")
    password: str = Field(..., description="Password")

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[str] = None
    full_name: Optional[str] = None
    password: str = Field(..., min_length=4)
    role: str = Field("USER", description="USER, SUBADMIN, or ADMIN")

class UserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None

class UserOut(BaseModel):
    id: UUID
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

class ContactAdminRequest(BaseModel):
    full_name: str
    email: str
    phone: Optional[str] = None
    note: Optional[str] = None
