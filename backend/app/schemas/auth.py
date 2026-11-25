from typing import Literal, Optional

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=72)
    workspace_name: Optional[str] = Field(default=None, min_length=2, max_length=100)


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=72)


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=10, max_length=300)


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = Field(default=None, max_length=300)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10, max_length=300)
    new_password: str = Field(min_length=8, max_length=72)


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=10, max_length=300)


class UserProfileUpdateRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=8, max_length=72)


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)


class WorkspaceUpdateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)


class WorkspaceMemberAddRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    role: Literal["admin", "member"] = "member"
