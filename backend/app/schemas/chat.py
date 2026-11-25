from typing import Literal, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: Optional[int] = None
    mode: Literal["personal", "support"] = "personal"
    customer_id: Optional[str] = Field(default=None, max_length=100)
    knowledge_base_id: Optional[int] = None


class RegenerateRequest(BaseModel):
    knowledge_base_id: Optional[int] = None


class ConversationRequest(BaseModel):
    mode: Literal["personal", "support"] = "personal"
    title: str = Field(default="New conversation", max_length=200)
    customer_id: Optional[str] = Field(default=None, max_length=100)


class ConversationUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    status: Optional[Literal["open", "archived"]] = None
    assigned_to_user_id: Optional[int] = None


class MemoryRequest(BaseModel):
    category: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=3000)
    scope: Literal["personal", "support"] = "personal"
    customer_id: Optional[str] = Field(default=None, max_length=100)
