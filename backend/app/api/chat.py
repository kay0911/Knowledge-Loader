from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func
from uuid import UUID
from typing import List
from app.db.postgres import SessionLocal
from app.schemas.chat import ChatRequest, ChatResponse, ChatLogResponse
from app.models.chat import ChatLog
from app.models.user import User
from app.api.deps import get_current_user, get_db
from app.services.chat_service import ChatService
from app.core.logging import logger

router = APIRouter()

@router.post("/", response_model=ChatResponse, status_code=status.HTTP_200_OK)
def ask_question(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submit a question to the Hybrid Retrieval RAG Chatbot.
    Saved under the current_user's account.
    """
    if not payload.question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty"
        )
        
    session_id_str = str(payload.session_id) if payload.session_id else None
    chat_log, citations = ChatService.ask(
        db, payload.question, session_id=session_id_str, history_mode=payload.history_mode, user_id=str(current_user.id)
    )
    return ChatResponse(
        chat_id=chat_log.id,
        session_id=chat_log.session_id,
        answer=chat_log.answer,
        citations=citations
    )


@router.get("/", response_model=List[ChatLogResponse])
def get_chat_history(
    db: Session = Depends(get_db),
    limit: int = 50,
    current_user: User = Depends(get_current_user)
):
    """
    Get list of chat sessions belonging ONLY to current authenticated user.
    Returns the first message of each session, ordered by most recent activity.
    """
    first_id_subq = (
        db.query(
            ChatLog.session_id,
            sql_func.min(ChatLog.created_at).label("first_created"),
            sql_func.max(ChatLog.created_at).label("last_updated"),
        )
        .filter(ChatLog.session_id.isnot(None))
        .filter(ChatLog.user_id == current_user.id)
        .group_by(ChatLog.session_id)
        .subquery()
    )

    logs = (
        db.query(ChatLog)
        .join(first_id_subq, ChatLog.session_id == first_id_subq.c.session_id)
        .filter(ChatLog.created_at == first_id_subq.c.first_created)
        .order_by(first_id_subq.c.last_updated.desc())
        .limit(limit)
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
def get_session_messages(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all messages in a chat session belonging to current_user (or Admin).
    """
    query = db.query(ChatLog).filter(ChatLog.session_id == str(session_id))
    if current_user.role != "ADMIN":
        query = query.filter(ChatLog.user_id == current_user.id)

    logs = query.order_by(ChatLog.created_at.asc()).all()
    if not logs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found or access denied"
        )
    hydrate_chat_log_citations(db, logs)
    return logs


@router.get("/{chat_id}", response_model=ChatLogResponse)
def get_chat_detail(
    chat_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed logs for a single chat message.
    """
    query = db.query(ChatLog).filter(ChatLog.id == chat_id)
    if current_user.role != "ADMIN":
        query = query.filter(ChatLog.user_id == current_user.id)

    log = query.first()
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat log not found"
        )
    hydrate_chat_log_citations(db, [log])
    return log


@router.post("/stream")
def ask_question_stream(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submit a question and receive streaming cited answers via SSE.
    Saved under current_user's account.
    """
    if not payload.question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty"
        )
    
    session_id_str = str(payload.session_id) if payload.session_id else None
    return StreamingResponse(
        ChatService.ask_stream(
            db, payload.question, session_id=session_id_str, history_mode=payload.history_mode, user_id=str(current_user.id)
        ),
        media_type="text/event-stream"
    )


@router.delete("/session/{session_id}")
def delete_chat_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete all chat logs associated with a session ID belonging to current user (or Admin).
    """
    try:
        try:
            target_uuid = UUID(session_id)
        except (ValueError, AttributeError):
            target_uuid = None

        query = db.query(ChatLog)
        if target_uuid:
            query = query.filter((ChatLog.session_id == target_uuid) | (ChatLog.session_id == session_id))
        else:
            query = query.filter(ChatLog.session_id == session_id)

        if current_user.role != "ADMIN":
            query = query.filter(ChatLog.user_id == current_user.id)

        deleted_count = query.delete(synchronize_session=False)
        db.commit()
        logger.info(f"User '{current_user.username}' deleted {deleted_count} chat logs for session {session_id}")
        return {"message": "Session deleted successfully", "deleted_count": deleted_count}
    except Exception as e:
        logger.error(f"Failed to delete chat session {session_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete chat session: {str(e)}")
