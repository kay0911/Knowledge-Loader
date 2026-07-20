from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
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
    Runs retrieval, reranking, LLM generation, compiles citations, and returns answer.
    """
    if not payload.question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty"
        )
        
    chat_log, citations = ChatService.ask(db, payload.question)
    return ChatResponse(
        chat_id=chat_log.id,
        answer=chat_log.answer,
        citations=citations
    )


@router.get("/", response_model=List[ChatLogResponse])
def get_chat_history(db: Session = Depends(get_db), limit: int = 50):
    """
    Get list of past Q&A chat history logs.
    """
    logs = db.query(ChatLog).order_by(ChatLog.created_at.desc()).limit(limit).all()
    return logs


@router.get("/{chat_id}", response_model=ChatLogResponse)
def get_chat_detail(chat_id: UUID, db: Session = Depends(get_db)):
    """
    Get detailed logs for a single chat session.
    """
    log = db.query(ChatLog).filter(ChatLog.id == chat_id).first()
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat log not found"
        )
    return log
