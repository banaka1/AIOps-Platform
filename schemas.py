"""
Pydantic 请求/响应模型
"""
from pydantic import BaseModel, Field


# ---- 鉴权 ----
class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class UserResponse(BaseModel):
    user_id: int
    username: str


class TokenResponse(BaseModel):
    token: str
    user: UserResponse


# ---- 聊天 ----
class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=64)
    message: str = Field(..., min_length=1, max_length=2000)


# ---- 会话 ----
class SessionCreateResponse(BaseModel):
    session_id: str
    title: str


class SessionItem(BaseModel):
    id: str
    title: str
    updated_at: str


class SessionRenameRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=128)


class OkResponse(BaseModel):
    ok: bool


class MessageItem(BaseModel):
    role: str
    content: str
    ts: str


class ToolCallInfo(BaseModel):
    name: str
    args: dict
    result: str
    ms: int


class ChatResponse(BaseModel):
    reply: str
    intent: str = "chat"
    tools: list[ToolCallInfo] = []
