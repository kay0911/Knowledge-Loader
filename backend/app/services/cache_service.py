from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, List, Dict, Any
from sqlalchemy.orm import Session
from app.models.chat import ChatLog
from app.core.logging import logger

class CacheService:
    @classmethod
    def get_semantic_cache(cls, db: Session, question: str) -> Optional[Tuple[str, List[Dict[str, Any]]]]:
        """
        Queries past Q&A history within the last 24 hours for exact or high-similarity matching questions.
        Returns cached (answer, citations) tuple if a cache hit occurs, or None if cache miss.
        """
        if not question or len(question.strip()) < 2:
            return None

        q_clean = question.strip().lower()
        try:
            # Enforce 24-hour TTL limit for Cache Hits
            cutoff_24h = datetime.now(timezone.utc) - timedelta(hours=24)

            cached_entry = db.query(ChatLog).filter(
                ChatLog.answer.isnot(None),
                ChatLog.answer != "",
                ChatLog.created_at >= cutoff_24h
            ).order_by(ChatLog.created_at.desc()).limit(100).all()

            for log in cached_entry:
                if log.question and log.question.strip().lower() == q_clean:
                    logger.info(f"Semantic Cache HIT (within 24h TTL) for query: '{question}'")
                    return log.answer, log.citations or []
        except Exception as e:
            logger.error(f"Semantic Cache check failed: {str(e)}")

        return None
