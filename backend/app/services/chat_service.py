import os
import re
import time
import google.generativeai as genai
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.logging import logger
from app.models.chat import ChatLog
from app.services.retrieval_service import RetrievalService

class ChatService:
    _configured = False
    _prompt_template = ""

    @classmethod
    def _configure(cls):
        if not cls._configured:
            api_key = settings.GEMINI_API_KEY
            genai.configure(api_key=api_key)
            
            # Load prompt template
            prompt_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "prompts",
                "chat_answer.txt"
            )
            try:
                with open(prompt_path, "r", encoding="utf-8") as f:
                    cls._prompt_template = f.read()
            except Exception as e:
                logger.error(f"Failed to load chat_answer.txt: {str(e)}")
                cls._prompt_template = (
                    "Answer strictly based on this context:\n{context}\n\nQuestion: {question}"
                )
            cls._configured = True

    @classmethod
    def ask(cls, db: Session, question: str) -> Tuple[ChatLog, List[Dict[str, Any]]]:
        """
        Run the Q&A pipeline:
        1. Run hybrid retrieval to get top relevant context chunks.
        2. Format prompt context with Source IDs (e.g. S1, S2...).
        3. Call Gemini LLM to generate cited response.
        4. Compile citation details based on referenced source codes.
        5. Log interaction details to the Postgres database.
        """
        cls._configure()
        start_time = time.time()
        
        # 1. Retrieve hybrid chunks
        chunks, graph_relationships = RetrievalService.retrieve_hybrid(db, question)
        
        # 2. Format Context
        context_blocks = []
        for i, chunk in enumerate(chunks):
            source_id = f"S{i+1}"
            meta = f"Source ID: {source_id}\nTên file: {chunk.document.original_file_name}"
            if chunk.page_number:
                meta += f", Trang: {chunk.page_number}"
            if chunk.heading:
                meta += f", Heading: {chunk.heading}"
            if chunk.sheet_name:
                meta += f", Sheet: {chunk.sheet_name} (Dòng {chunk.row_start}-{chunk.row_end})"
            
            block = f"{meta}\nNội dung: {chunk.content}"
            context_blocks.append(block)
            
        context_str = "\n---\n".join(context_blocks)
        
        # 3. Call Gemini LLM
        answer = ""
        try:
            model = genai.GenerativeModel(model_name=settings.GEMINI_LLM_MODEL)
            prompt = cls._prompt_template.replace("{context}", context_str).replace("{question}", question)
            
            logger.info("Calling Gemini LLM for Q&A...")
            response = model.generate_content(prompt)
            answer = response.text.strip()
        except Exception as e:
            logger.error(f"Gemini LLM call failed: {str(e)}", exc_info=True)
            answer = "Đã xảy ra lỗi khi gọi trợ lý AI. Vui lòng thử lại sau."
            
        # Calculate latency
        latency_ms = int((time.time() - start_time) * 1000)
        
        # 4. Compile Citations
        citations = []
        # Find which source IDs (e.g., [S1], [S2]) were actually used in the answer
        cited_indices = re.findall(r"\[S(\d+)\]", answer)
        cited_nums = {int(idx) - 1 for idx in cited_indices if idx.isdigit()}
        
        # Build citation records
        for idx in sorted(cited_nums):
            if 0 <= idx < len(chunks):
                chunk = chunks[idx]
                snippet = chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content
                citations.append({
                    "source_id": f"S{idx+1}",
                    "document_id": str(chunk.document_id),
                    "file_name": chunk.document.original_file_name,
                    "page_number": chunk.page_number,
                    "heading": chunk.heading,
                    "sheet_name": chunk.sheet_name,
                    "row_start": chunk.row_start,
                    "row_end": chunk.row_end,
                    "snippet": snippet
                })
                
        # Fallback: if no citations found in text but we had chunks, list top 3 chunks as reference
        if not citations and chunks:
            # Check if answer contains refusal message
            is_refusal = "chưa tìm thấy đủ thông tin" in answer or "lỗi" in answer.lower()
            if not is_refusal:
                # Add top 3 chunks as general references
                for i in range(min(3, len(chunks))):
                    chunk = chunks[i]
                    snippet = chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content
                    citations.append({
                        "source_id": f"S{i+1}",
                        "document_id": str(chunk.document_id),
                        "file_name": chunk.document.original_file_name,
                        "page_number": chunk.page_number,
                        "heading": chunk.heading,
                        "sheet_name": chunk.sheet_name,
                        "row_start": chunk.row_start,
                        "row_end": chunk.row_end,
                        "snippet": snippet
                    })

        # 5. Record to PostgreSQL
        chat_log = ChatLog(
            question=question,
            answer=answer,
            retrieved_chunk_ids=[str(c.id) for c in chunks],
            graph_context=graph_relationships,
            citations=citations,
            latency_ms=latency_ms
        )
        
        try:
            db.add(chat_log)
            db.commit()
            db.refresh(chat_log)
            logger.info(f"Chat log saved with ID: {chat_log.id}")
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to save chat log: {str(e)}")
            
        return chat_log, citations
