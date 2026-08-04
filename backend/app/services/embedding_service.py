import google.generativeai as genai
from typing import List, Optional
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.logging import logger
from app.db.postgres import SessionLocal
from app.services.key_rotation_service import KeyRotationService

class EmbeddingService:
    @classmethod
    def get_embedding(cls, text: str, db: Optional[Session] = None) -> List[float]:
        """
        Generate embedding for the text using rotated Gemini API keys.
        """
        if settings.MOCK_AI_SERVICES:
            import hashlib
            hash_val = int(hashlib.md5(text.encode('utf-8')).hexdigest(), 16)
            vec = [(float((hash_val >> (i % 32)) & 0xFF) / 255.0 - 0.5) for i in range(settings.GEMINI_EMBEDDING_DIMENSION)]
            return vec

        if not text.strip():
            return [0.0] * settings.GEMINI_EMBEDDING_DIMENSION

        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            model_name = settings.GEMINI_EMBEDDING_MODEL
            last_error = None

            # Attempt embedding with key rotation
            for attempt in range(5):
                raw_key, key_obj = KeyRotationService.get_valid_api_key(db, provider="gemini")
                try:
                    genai.configure(api_key=raw_key, transport='rest')
                    response = genai.embed_content(
                        model=model_name,
                        content=text,
                        task_type="retrieval_document",
                        output_dimensionality=settings.GEMINI_EMBEDDING_DIMENSION
                    )
                    
                    values = None
                    if isinstance(response, dict) and "embedding" in response:
                        val = response["embedding"]
                        values = val.get("values", val) if isinstance(val, dict) else val
                    elif hasattr(response, "embedding"):
                        emb = response.embedding
                        if isinstance(emb, dict):
                            values = emb.get("values", [])
                        elif hasattr(emb, "values"):
                            values = emb.values
                        elif isinstance(emb, list):
                            values = emb

                    if values and len(values) > 0:
                        if key_obj:
                            KeyRotationService.report_key_success(db, key_obj.id)
                        return list(values)

                except Exception as e:
                    last_error = e
                    err_str = str(e)
                    logger.warning(f"Embedding attempt {attempt + 1} with key '{KeyRotationService.mask_key(raw_key)}' failed: {err_str}")
                    if key_obj:
                        KeyRotationService.report_key_error(db, key_obj.id, err_str)

            logger.error(f"Error calling Gemini Embedding API: {str(last_error)}")
            raise last_error
        finally:
            if close_db:
                db.close()
