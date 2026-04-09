from pydantic import BaseModel, EmailStr
from app.models.user import UserRole


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    locale: str = "en"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str | None = None
    name: str
    role: UserRole
    locale: str
    autonomy_level: int | None = None
    created_by_id: int | None = None

    model_config = {"from_attributes": True}


class CreateChildRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    autonomy_level: int = 1  # 1=Supervised, 2=Semi, 3=Autonomous


class UpdateChildRequest(BaseModel):
    autonomy_level: int
