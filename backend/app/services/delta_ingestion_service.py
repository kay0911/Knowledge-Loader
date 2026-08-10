import hashlib
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from app.models.document import DocumentChunk
from app.core.logging import logger

class DeltaIngestionService:
    @staticmethod
    def compute_chunk_hash(content: str) -> str:
        """
        Computes SHA-256 hash for chunk content string.
        """
        if not content:
            return ""
        normalized_str = content.strip().encode("utf-8")
        return hashlib.sha256(normalized_str).hexdigest()

    @classmethod
    def filter_existing_chunks(cls, db: Session, parsed_chunks: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Compares parsed chunks against existing active chunk hashes in DB.
        Returns tuple of (reusable_existing_chunks, brand_new_delta_chunks).
        For reusable_existing_chunks: copies existing embedding to skip AI costs ($0 cost).
        """
        reusable_chunks = []
        brand_new_chunks = []

        for p_chunk in parsed_chunks:
            content = p_chunk.get("content", "")
            ch_hash = cls.compute_chunk_hash(content)
            p_chunk["chunk_hash"] = ch_hash

            # Check if this exact hash exists in DB as an active chunk
            existing_db_chunk = db.query(DocumentChunk).filter(
                DocumentChunk.chunk_hash == ch_hash,
                DocumentChunk.is_active == True,
                DocumentChunk.embedding.isnot(None)
            ).first()

            if existing_db_chunk:
                # Reuse existing embedding! Skip AI Embedding & Graph Extraction ($0 cost)
                p_chunk["embedding"] = existing_db_chunk.embedding
                p_chunk["reused_from_chunk_id"] = str(existing_db_chunk.id)
                reusable_chunks.append(p_chunk)
            else:
                brand_new_chunks.append(p_chunk)

        logger.info(f"Delta Processing Summary -> Total: {len(parsed_chunks)}, Reused ($0 cost): {len(reusable_chunks)}, Delta New: {len(brand_new_chunks)}")
        return reusable_chunks, brand_new_chunks
