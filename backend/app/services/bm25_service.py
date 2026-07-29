import re
from typing import List
from rank_bm25 import BM25Okapi
from sqlalchemy.orm import joinedload
from app.db.postgres import SessionLocal
from app.models.document import DocumentChunk, Document
from app.core.logging import logger

def tokenize(text: str) -> List[str]:
    """Simple unicode-aware tokenizer."""
    if not text:
        return []
    # \w matches any alphanumeric character, including Vietnamese accented characters
    return re.findall(r"\w+", text.lower())

class BM25Service:
    _index = None
    _chunks = []

    @classmethod
    def rebuild_index(cls):
        """
        Rebuild the BM25 index from scratch by fetching all active chunks
        of READY documents in PostgreSQL.
        """
        logger.info("Rebuilding BM25 index from PostgreSQL chunks...")
        db = SessionLocal()
        try:
            chunks = db.query(DocumentChunk).options(
                joinedload(DocumentChunk.document)
            ).join(
                Document, Document.id == DocumentChunk.document_id
            ).filter(
                DocumentChunk.is_active == True,
                Document.status == "READY",
                Document.is_enabled == True
            ).all()
            
            if not chunks:
                logger.info("No active chunks of READY documents found. BM25 index cleared.")
                cls._index = None
                cls._chunks = []
                return
                
            tokenized_corpus = [tokenize(chunk.content) for chunk in chunks]
            cls._index = BM25Okapi(tokenized_corpus)
            cls._chunks = chunks
            logger.info(f"BM25 index rebuilt successfully with {len(chunks)} chunks.")
        except Exception as e:
            logger.error(f"Error rebuilding BM25 index: {str(e)}", exc_info=True)
        finally:
            db.close()

    @classmethod
    def search(cls, query: str, top_k: int = 10) -> List[DocumentChunk]:
        """
        Perform BM25 search on active chunks.
        """
        if not cls._index or not cls._chunks:
            cls.rebuild_index()
            if not cls._index:
                return []
                
        tokenized_query = tokenize(query)
        if not tokenized_query:
            return []
            
        scores = cls._index.get_scores(tokenized_query)
        
        # Zip chunks and scores, sort by score descending
        ranked_results = sorted(
            zip(cls._chunks, scores),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Return chunks with positive score, fall back to top_k of overall if none are positive
        positive_results = [chunk for chunk, score in ranked_results if score > 0]
        if positive_results:
            return positive_results[:top_k]
            
        return [chunk for chunk, score in ranked_results[:top_k]]
