import google.generativeai as genai
from typing import List
from app.core.config import settings
from app.core.logging import logger

class EmbeddingService:
    _configured = False

    @classmethod
    def _configure(cls):
        if not cls._configured:
            api_key = settings.GEMINI_API_KEY
            if not api_key or api_key == "YOUR_GEMINI_API_KEY_HERE":
                logger.warning("GEMINI_API_KEY is placeholder or empty in settings!")
            genai.configure(api_key=api_key)
            cls._configured = True

    @classmethod
    def get_embedding(cls, text: str) -> List[float]:
        """
        Generate embedding for the text using Gemini API.
        Default model: gemini-embedding-1
        """
        cls._configure()
        if not text.strip():
            # Return zero vector if text is empty
            return [0.0] * settings.GEMINI_EMBEDDING_DIMENSION
            
        try:
            model_name = settings.GEMINI_EMBEDDING_MODEL
            # Clean model name if models/ prefix is missing or extra
            if not model_name.startswith("models/"):
                # Usually embedding-001 is models/embedding-001, gemini-embedding-1 is models/gemini-embedding-1
                # But google-generativeai SDK accepts both raw names or prefixed names.
                # Let's pass it directly or with prefix models/
                # Let's use the settings directly
                pass
                
            response = genai.embed_content(
                model=model_name,
                content=text,
                task_type="retrieval_document",
                output_dimensionality=settings.GEMINI_EMBEDDING_DIMENSION
            )
            
            # Extract embedding values
            if isinstance(response, dict) and "embedding" in response:
                values = response["embedding"]
            elif hasattr(response, "embedding") and isinstance(response.embedding, dict) and "values" in response.embedding:
                values = response.embedding["values"]
            elif hasattr(response, "embedding") and isinstance(response.embedding, list):
                values = response.embedding
            elif hasattr(response, "embedding") and hasattr(response.embedding, "values"):
                values = response.embedding.values
            else:
                # Direct lookup if response has standard dictionary key or attribute
                try:
                    values = response["embedding"]["values"]
                except:
                    values = response.get("embedding", {}).get("values", [])
                    
            if not values:
                raise ValueError(f"Could not extract embedding values from response: {response}")
                
            # If dimension is different from expected, warn and return values
            if len(values) != settings.GEMINI_EMBEDDING_DIMENSION:
                logger.warning(f"Embedding dimension mismatch: expected {settings.GEMINI_EMBEDDING_DIMENSION}, got {len(values)}")
                
            return values
        except Exception as e:
            logger.error(f"Error calling Gemini Embedding API ({settings.GEMINI_EMBEDDING_MODEL}): {str(e)}")
            raise e
