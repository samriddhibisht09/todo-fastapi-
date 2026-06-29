from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator


class TodoCreate(BaseModel):
    task: str


class TodoUpdate(BaseModel):
    task: str
    completed: bool


class TodoRead(BaseModel):
    id: int
    user_id: int
    task: str
    completed: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserBase(BaseModel):
    email: EmailStr
    phone_number: str


class UserCreate(UserBase):
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Password must be 72 bytes or less")
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserRead(UserBase):
    id: int

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: Optional[str] = None