"""
FastAPI 入口：鉴权 + 会话 CRUD + 聊天
"""
import json
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

import agent
from database import get_db
from models import User, Session as DBSession, Message as DBMessage
from auth import hash_password, verify_password, create_access_token, get_current_user
from schemas import (
    RegisterRequest, LoginRequest, UserResponse, TokenResponse, ChatRequest,
    SessionCreateResponse, SessionItem, SessionRenameRequest, OkResponse,
    MessageItem, ChatResponse,
)

app = FastAPI(title="智能运维 Agent 平台")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- 工具：越权校验 ----------
def _get_user_session(db: Session, session_id: str, user: User) -> DBSession:
    """获取当前用户的会话，越权/不存在抛 403/404"""
    session = db.query(DBSession).filter(DBSession.id == session_id).first()
    if not session or session.is_deleted:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session.user_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问该会话")
    return session


# ---------- 鉴权 ----------
@app.post("/api/auth/register", response_model=UserResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if not req.username or not req.password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = User(username=req.username, password=hash_password(req.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserResponse(user_id=user.id, username=user.username)


@app.post("/api/auth/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_password(req.password, user.password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_access_token(user.id, user.username)
    return TokenResponse(
        token=token,
        user=UserResponse(user_id=user.id, username=user.username),
    )


@app.get("/api/auth/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    return UserResponse(user_id=user.id, username=user.username)


# ---------- 会话管理 ----------
@app.post("/api/sessions", response_model=SessionCreateResponse)
def create_session(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """FR-2.1 新建会话，默认标题"新对话" """
    session = DBSession(user_id=user.id, title="新对话")
    db.add(session)
    db.commit()
    db.refresh(session)
    return SessionCreateResponse(session_id=session.id, title=session.title)


@app.get("/api/sessions", response_model=list[SessionItem])
def list_sessions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """FR-2.2 当前用户全部未删除会话，按 updated_at 倒序"""
    rows = (
        db.query(DBSession)
        .filter(DBSession.user_id == user.id, DBSession.is_deleted == 0)
        .order_by(DBSession.updated_at.desc())
        .all()
    )
    return [
        SessionItem(
            id=r.id,
            title=r.title,
            updated_at=r.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        )
        for r in rows
    ]


@app.get("/api/sessions/{session_id}/messages", response_model=list[MessageItem])
def get_session_messages(
    session_id: str,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """FR-2.3 / FR-3.4 分页拉取会话历史消息"""
    _get_user_session(db, session_id, user)
    offset = (page - 1) * size
    rows = (
        db.query(DBMessage)
        .filter(DBMessage.session_id == session_id)
        .order_by(DBMessage.id.asc())
        .offset(offset)
        .limit(size)
        .all()
    )
    return [
        MessageItem(
            role=r.role,
            content=r.content,
            ts=r.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        )
        for r in rows
    ]


@app.patch("/api/sessions/{session_id}", response_model=OkResponse)
def rename_session(
    session_id: str,
    req: SessionRenameRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """FR-2.4 重命名会话"""
    session = _get_user_session(db, session_id, user)
    session.title = req.title
    db.commit()
    return OkResponse(ok=True)


@app.delete("/api/sessions/{session_id}", response_model=OkResponse)
def delete_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """FR-2.5 软删除会话"""
    session = _get_user_session(db, session_id, user)
    session.is_deleted = 1
    db.commit()
    return OkResponse(ok=True)


# ---------- 聊天 ----------
@app.post("/api/chat", response_model=ChatResponse)
def chat(
    req: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """FR-3 消息持久化 + Agent 编排"""
    session = _get_user_session(db, req.session_id, user)
    # 首条消息自动更新会话标题
    msg_count = db.query(DBMessage).filter(DBMessage.session_id == req.session_id).count()
    if msg_count == 0:
        session.title = req.message[:12]

    reply, intent, tools = agent.test_chat_openai(req.message, req.session_id, db)
    return ChatResponse(reply=reply, intent=intent, tools=tools)


@app.post("/api/chat/stream")
def chat_stream(
    req: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """FR-3 流式聊天：SSE 推送 meta/tool_call/tool_result/token/reset/done 事件"""
    session = _get_user_session(db, req.session_id, user)
    msg_count = db.query(DBMessage).filter(DBMessage.session_id == req.session_id).count()
    if msg_count == 0:
        session.title = req.message[:12]
        db.commit()

    def gen():
        try:
            for event, data in agent.test_chat_openai_stream(req.message, req.session_id, db):
                yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'detail': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
