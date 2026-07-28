import os
import re
import time
import json
import uuid as uuid_mod
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
    def _prepare_history_and_query(cls, db: Session, question: str, session_id: str = None, history_mode: bool = False):
        history_str = ""
        rewritten_question = question
        
        if history_mode and session_id:
            # Query last 5 Q&A pairs (turns)
            history_logs = db.query(ChatLog).filter(
                ChatLog.session_id == session_id
            ).order_by(ChatLog.created_at.desc()).limit(5).all()
            
            # Reverse to chronological order
            history_logs.reverse()
            
            if history_logs:
                # Format history
                history_str_list = []
                for log in history_logs:
                    ans = log.answer or ""
                    history_str_list.append(f"User: {log.question}\nAssistant: {ans}")
                history_str = "\n\n".join(history_str_list)
                
                # Rewrite question using LLM to make it a standalone search query
                rewrite_prompt = (
                    "Bạn là trợ lý ảo phụ trách viết lại câu hỏi tìm kiếm. "
                    "Dựa trên lịch sử hội thoại dưới đây và câu hỏi tiếp theo, hãy viết lại câu hỏi tiếp theo thành một câu hỏi độc lập, đầy đủ ngữ nghĩa để tìm kiếm trong cơ sở dữ liệu. "
                    "Chỉ trả về câu hỏi độc lập mới, KHÔNG trả lời câu hỏi và KHÔNG thêm bất kỳ giải thích nào khác.\n\n"
                    f"Lịch sử hội thoại:\n{history_str}\n\n"
                    f"Câu hỏi tiếp theo: {question}\n\n"
                    "Câu hỏi độc lập viết lại:"
                )
                try:
                    model = genai.GenerativeModel(model_name=settings.GEMINI_LLM_MODEL)
                    response = model.generate_content(rewrite_prompt)
                    rewritten_question = response.text.strip()
                    logger.info(f"Original question: '{question}' -> Rewritten for search: '{rewritten_question}'")
                except Exception as ex:
                    logger.error(f"Failed to rewrite question using history: {str(ex)}")
                    rewritten_question = question
                    
        return history_str, rewritten_question

    @classmethod
    def ask(cls, db: Session, question: str, session_id: str = None, history_mode: bool = False) -> Tuple[ChatLog, List[Dict[str, Any]]]:
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
        
        # 1. Prepare history and query rewrite
        history_str, query_for_retrieval = cls._prepare_history_and_query(db, question, session_id, history_mode)
        
        # 2. Retrieve hybrid chunks using rewritten question
        chunks, graph_relationships = RetrievalService.retrieve_hybrid(db, query_for_retrieval)
        
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
            if history_str:
                question_with_history = f"(Lịch sử hội thoại để tham khảo:\n{history_str})\n\nCâu hỏi hiện tại cần trả lời: {question}"
            else:
                question_with_history = question
            prompt = cls._prompt_template.replace("{context}", context_str).replace("{question}", question_with_history)
            
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
                snippet = chunk.content
                citations.append({
                    "source_id": f"S{idx+1}",
                    "document_id": str(chunk.document_id),
                    "file_name": chunk.document.original_file_name,
                    "page_number": chunk.page_number,
                    "page_start": getattr(chunk, "page_start", None) or chunk.page_number,
                    "page_end": getattr(chunk, "page_end", None) or chunk.page_number,
                    "heading": chunk.heading,
                    "heading_path": getattr(chunk, "heading_path", None),
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
                    snippet = chunk.content
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
        resolved_session_id = session_id or str(uuid_mod.uuid4())
        chat_log = ChatLog(
            session_id=resolved_session_id,
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

    @classmethod
    def ask_stream(cls, db: Session, question: str, session_id: str = None, history_mode: bool = False):
        """
        Streaming version of ask:
        Yields content chunks in SSE format first, then yields metadata at the end.
        """
        cls._configure()
        start_time = time.time()
        
        # 1. Prepare history and query rewrite
        history_str, query_for_retrieval = cls._prepare_history_and_query(db, question, session_id, history_mode)
        
        # 2. Retrieve hybrid chunks using rewritten question
        chunks, graph_relationships = RetrievalService.retrieve_hybrid(db, query_for_retrieval)
        
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
        
        # 3. Call Gemini LLM in stream mode (or Mock for benchmark)
        answer = ""
        if settings.MOCK_AI_SERVICES:
            mock_tokens = [
                "Theo tài liệu trích dẫn ",
                "[S1]",
                ", hệ thống GraphRAG đã xử lý thông tin từ cơ sở dữ liệu:\n\n",
                "1. Đây là câu trả lời thử nghiệm tải (Mock Performance Test).\n",
                "2. Quá trình Hybrid Vector Search (pgvector) & Graph Search (Neo4j) đã hoạt động chính xác."
            ]
            for token in mock_tokens:
                answer += token
                yield f"data: {json.dumps({'type': 'content', 'content': token}, ensure_ascii=False)}\n\n"
        else:
            try:
                model = genai.GenerativeModel(model_name=settings.GEMINI_LLM_MODEL)
                if history_str:
                    question_with_history = f"(Lịch sử hội thoại để tham khảo:\n{history_str})\n\nCâu hỏi hiện tại cần trả lời: {question}"
                else:
                    question_with_history = question
                prompt = cls._prompt_template.replace("{context}", context_str).replace("{question}", question_with_history)
                
                logger.info("Calling Gemini LLM for streaming Q&A...")
                response = model.generate_content(prompt, stream=True)
                
                for chunk in response:
                    chunk_text = chunk.text
                    answer += chunk_text
                    # Yield content chunk in SSE format
                    yield f"data: {json.dumps({'type': 'content', 'content': chunk_text}, ensure_ascii=False)}\n\n"
                    
            except Exception as e:
                logger.error(f"Gemini LLM streaming call failed: {str(e)}", exc_info=True)
                err_text = "Đã xảy ra lỗi khi gọi trợ lý AI. Vui lòng thử lại sau."
                answer = err_text
                yield f"data: {json.dumps({'type': 'content', 'content': err_text}, ensure_ascii=False)}\n\n"
            
        # Calculate latency
        latency_ms = int((time.time() - start_time) * 1000)
        
        # 4. Compile Citations
        citations = []
        cited_indices = re.findall(r"\[S(\d+)\]", answer)
        cited_nums = {int(idx) - 1 for idx in cited_indices if idx.isdigit()}
        
        for idx in sorted(cited_nums):
            if 0 <= idx < len(chunks):
                chunk = chunks[idx]
                snippet = chunk.content
                citations.append({
                    "source_id": f"S{idx+1}",
                    "document_id": str(chunk.document_id),
                    "file_name": chunk.document.original_file_name,
                    "page_number": chunk.page_number,
                    "page_start": getattr(chunk, "page_start", None) or chunk.page_number,
                    "page_end": getattr(chunk, "page_end", None) or chunk.page_number,
                    "heading": chunk.heading,
                    "heading_path": getattr(chunk, "heading_path", None),
                    "sheet_name": chunk.sheet_name,
                    "row_start": chunk.row_start,
                    "row_end": chunk.row_end,
                    "snippet": snippet
                })
                
        # 5. Record to PostgreSQL
        resolved_session_id = session_id or str(uuid_mod.uuid4())
        chat_log = ChatLog(
            session_id=resolved_session_id,
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
            logger.info(f"Chat log saved via stream with ID: {chat_log.id}")
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to save streaming chat log: {str(e)}")
            
        # 6. Yield metadata at the end of the stream
        yield f"data: {json.dumps({'type': 'metadata', 'chat_id': str(chat_log.id), 'session_id': resolved_session_id, 'citations': citations}, ensure_ascii=False)}\n\n"
