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
    chat_log, citations = ChatService.ask(
        db, payload.question, session_id=session_id_str, history_mode=payload.history_mode
    )
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


def hydrate_chat_log_citations(db: Session, logs: List[ChatLog]):
    """
    For old or existing chat logs, if citations contain truncated snippets (ending with '...'),
    look up original DocumentChunk records using retrieved_chunk_ids and restore full content.
    """
    if not logs:
        return
    
    all_chunk_ids = []
    for log in logs:
        if log.retrieved_chunk_ids and isinstance(log.retrieved_chunk_ids, list):
            all_chunk_ids.extend(log.retrieved_chunk_ids)
            
    if not all_chunk_ids:
        return
        
    from app.models.document import DocumentChunk
    import logging
    logger = logging.getLogger(__name__)
    try:
        chunks = db.query(DocumentChunk).filter(DocumentChunk.id.in_(all_chunk_ids)).all()
        chunk_map = {str(c.id): c.content for c in chunks}
    except Exception as e:
        logger.warning(f"Failed to fetch chunk map for citations: {e}")
        chunk_map = {}
        
    for log in logs:
        if not log.citations or not isinstance(log.citations, list):
            continue
            
        updated_citations = []
        for i, citation in enumerate(log.citations):
            cit = dict(citation)
            snippet = cit.get("snippet", "")
            if snippet.endswith("...") or len(snippet) <= 220:
                chunk_id = cit.get("chunk_id")
                full_content = None
                if chunk_id and chunk_id in chunk_map:
                    full_content = chunk_map[chunk_id]
                elif log.retrieved_chunk_ids and i < len(log.retrieved_chunk_ids):
                    cid = log.retrieved_chunk_ids[i]
                    if cid in chunk_map:
                        full_content = chunk_map[cid]
                
                if full_content:
                    cit["snippet"] = full_content
            updated_citations.append(cit)
        log.citations = updated_citations


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
    hydrate_chat_log_citations(db, logs)
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
    hydrate_chat_log_citations(db, [log])
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
        ChatService.ask_stream(db, payload.question, session_id=session_id_str, history_mode=payload.history_mode),
        media_type="text/event-stream"
    )


@router.delete("/session/{session_id}")
def delete_chat_session(session_id: UUID, db: Session = Depends(get_db)):
    """
    Delete all chat logs associated with a session ID.
    """
    deleted_count = db.query(ChatLog).filter(ChatLog.session_id == str(session_id)).delete(synchronize_session=False)
    db.commit()
    if deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found or already deleted"
        )
    return {"message": "Session deleted successfully", "deleted_count": deleted_count}

