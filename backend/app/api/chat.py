from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func
from uuid import UUID
from typing import List
from app.db.postgres import SessionLocal
from app.schemas.chat import ChatRequest, ChatResponse, ChatLogResponse
from app.models.chat import ChatLog
from app.services.chat_service import ChatService

router = APIRouter()

# Dependency to get db session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/", response_model=ChatResponse, status_code=status.HTTP_200_OK)
def ask_question(payload: ChatRequest, db: Session = Depends(get_db)):
    """
    Submit a question to the Hybrid Retrieval RAG Chatbot.
    """
    if not payload.question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty"
        )
        
    session_id_str = str(payload.session_id) if payload.session_id else None
    chat_log, citations = ChatService.ask(db, payload.question, session_id=session_id_str)
    return ChatResponse(
        chat_id=chat_log.id,
        session_id=chat_log.session_id,
        answer=chat_log.answer,
        citations=citations
    )


@router.get("/", response_model=List[ChatLogResponse])
def get_chat_history(db: Session = Depends(get_db), limit: int = 50):
    """
    Get list of chat sessions (one entry per session, showing the first question).
    Returns the first message of each session, ordered by most recent activity.
    """
    # Subquery: get the earliest chat_log id per session
    first_id_subq = (
        db.query(
            ChatLog.session_id,
            sql_func.min(ChatLog.created_at).label("first_created"),
        )
        .filter(ChatLog.session_id.isnot(None))
        .group_by(ChatLog.session_id)
        .order_by(sql_func.max(ChatLog.created_at).desc())
        .limit(limit)
        .subquery()
    )

    logs = (
        db.query(ChatLog)
        .join(first_id_subq, ChatLog.session_id == first_id_subq.c.session_id)
        .filter(ChatLog.created_at == first_id_subq.c.first_created)
        .order_by(ChatLog.created_at.desc())
        .all()
    )
    return logs


@router.get("/session/{session_id}", response_model=List[ChatLogResponse])
def get_session_messages(session_id: UUID, db: Session = Depends(get_db)):
    """
    Get all messages in a chat session, ordered chronologically.
    """
    logs = (
        db.query(ChatLog)
        .filter(ChatLog.session_id == str(session_id))
        .order_by(ChatLog.created_at.asc())
        .all()
    )
    if not logs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    return logs


@router.get("/{chat_id}", response_model=ChatLogResponse)
def get_chat_detail(chat_id: UUID, db: Session = Depends(get_db)):
    """
    Get detailed logs for a single chat message.
    """
    log = db.query(ChatLog).filter(ChatLog.id == chat_id).first()
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat log not found"
        )
    return log


@router.post("/stream")
def ask_question_stream(payload: ChatRequest, db: Session = Depends(get_db)):
    """
    Submit a question and receive streaming cited answers via SSE.
    """
    if not payload.question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty"
        )
    
    session_id_str = str(payload.session_id) if payload.session_id else None
    return StreamingResponse(
        ChatService.ask_stream(db, payload.question, session_id=session_id_str),
        media_type="text/event-stream"
    )

