import httpx
from typing import List, Dict, Any
from app.core.config import settings
from app.core.logging import logger
from app.models.document import DocumentChunk

class RerankService:
    @classmethod
    def rerank(cls, query: str, chunks: List[DocumentChunk], top_n: int = None) -> List[DocumentChunk]:
        """
        Rank chunks using Cohere Rerank API based on query relevance.
        Falls back to original order if API call fails or COHERE_API_KEY is missing.
        """
        if not chunks:
            return []
            
        limit = top_n or settings.RERANK_TOP_K

        api_key = settings.COHERE_API_KEY
        if not api_key or api_key == "your_cohere_api_key_here":
            logger.warning("COHERE_API_KEY is not configured. Skipping Cohere Rerank and returning original order.")
            return chunks[:limit]
            
        # Extract text content from each chunk
        documents_text = [chunk.content for chunk in chunks]
        
        url = "https://api.cohere.com/v2/rerank"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "accept": "application/json"
        }
        
        payload = {
            "model": settings.COHERE_RERANK_MODEL,
            "query": query,
            "documents": documents_text,
            "top_n": limit
        }
        
        try:
            logger.info(f"Sending {len(chunks)} documents to Cohere Rerank API (top_n={limit})...")
            response = httpx.post(url, headers=headers, json=payload, timeout=10.0, verify=False)
            
            if response.status_code != 200:
                logger.error(f"Cohere API returned error status {response.status_code}: {response.text}")
                return chunks[:limit]
                
            data = response.json()
            results = data.get("results", [])
            
            # Map results to original chunks by index
            ranked_chunks = []
            for item in results:
                idx = item.get("index")
                if idx is not None and 0 <= idx < len(chunks):
                    # We can store the relevance score on the chunk temporarily or log it
                    score = item.get("relevance_score", 0.0)
                    logger.debug(f"Chunk index {idx} ranked with score {score}")
                    ranked_chunks.append(chunks[idx])
                    
            logger.info(f"Successfully reranked and selected top {len(ranked_chunks)} chunks.")
            return ranked_chunks
            
        except Exception as e:
            logger.error(f"Failed to call Cohere Rerank API: {str(e)}", exc_info=True)
            # Safe fallback
            return chunks[:settings.RERANK_TOP_K]
