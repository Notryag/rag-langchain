from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.models.user import UserRole


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)


class UserLogin(BaseModel):
    username_or_email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)


class UserRead(BaseModel):
    id: int
    username: str
    email: str
    role: UserRole = UserRole.USER

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead
