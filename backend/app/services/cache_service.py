import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, List, Dict, Any
from sqlalchemy.orm import Session
from app.models.chat import ChatLog
from app.core.logging import logger

def extract_numbers(text: str) -> set:
    if not text:
        return set()
    return set(re.findall(r"\b\d+\b", text))

def extract_code_entities(text: str) -> set:
    if not text:
        return set()
    return set(re.findall(r"\b[A-Z]+[0-9]+\b|\b[0-9]+[A-Z]+\b", text.upper()))

def compute_cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = sum(a * a for a in vec1) ** 0.5
    norm2 = sum(b * b for b in vec2) ** 0.5
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return max(0.0, dot / (norm1 * norm2))

class CacheService:
    @classmethod
    def get_semantic_cache(
        cls,
        db: Session,
        question: str,
        query_vector: Optional[List[float]] = None,
        similarity_threshold: float = 0.92
    ) -> Optional[Tuple[str, List[Dict[str, Any]]]]:
        """
        Hybrid Semantic Cache lookup:
        - 24-hour TTL window limit.
        - Strict Number & Year Match Guardrule (Preventing 2024 vs 2026 false positive hits).
        - Strict Entity Code Match Guardrule (Preventing P4 vs P5 or VF8 vs VF9 false positive hits).
        - Cosine Similarity >= similarity_threshold (0.92) or Exact String Match.
        """
        if not question or len(question.strip()) < 2:
            return None

        q_clean = question.strip().lower()
        q_numbers = extract_numbers(question)
        q_entities = extract_code_entities(question)

        try:
            cutoff_24h = datetime.now(timezone.utc) - timedelta(hours=24)

            cached_entries = db.query(ChatLog).filter(
                ChatLog.answer.isnot(None),
                ChatLog.answer != "",
                ChatLog.created_at >= cutoff_24h
            ).order_by(ChatLog.created_at.desc()).limit(100).all()

            for log in cached_entries:
                effective_q = (log.rewritten_question or log.question or "").strip().lower()
                
                # 1. First priority: Exact String Match
                if effective_q == q_clean:
                    logger.info(f"Semantic Cache EXACT STRING HIT (within 24h TTL) for query: '{question}'")
                    return log.answer, log.citations or []

                # 2. Hybrid Semantic Vector Match
                if query_vector and log.question_embedding is not None:
                    # Guard 1: Strict Number & Year Match
                    log_numbers = extract_numbers(effective_q)
                    if q_numbers != log_numbers:
                        # Numbers differ (e.g. 2024 != 2026 or Chương 1 != Chương 2) -> Skip!
                        continue

                    # Guard 2: Strict Entity Code Match
                    log_entities = extract_code_entities(effective_q)
                    if q_entities != log_entities:
                        # Code entities differ (e.g. P4 != P5 or VF8 != VF9) -> Skip!
                        continue

                    # Guard 3: Cosine Similarity >= 0.92
                    log_vec = list(log.question_embedding)
                    cos_sim = compute_cosine_similarity(query_vector, log_vec)

                    if cos_sim >= similarity_threshold:
                        logger.info(
                            f"Semantic Cache VECTOR HIT (CosSim: {cos_sim:.4f} >= {similarity_threshold}) "
                            f"for query: '{question}' matched cached: '{effective_q}'"
                        )
                        return log.answer, log.citations or []

        except Exception as e:
            logger.error(f"Semantic Cache check failed: {str(e)}")

        return None
