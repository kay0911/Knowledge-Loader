import os
import re
import time
import json
import ssl
import urllib3
import requests
import uuid as uuid_mod

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
ssl._create_default_https_context = ssl._create_unverified_context

old_merge = requests.Session.merge_environment_settings
def custom_merge(self, url, proxies, stream, verify, cert):
    return old_merge(self, url, proxies, stream, False, cert)
requests.Session.merge_environment_settings = custom_merge

import google.generativeai as genai
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.logging import logger
from app.models.chat import ChatLog
from app.services.retrieval_service import RetrievalService
from app.services.cache_service import CacheService
from app.services.intent_router_service import IntentRouterService
from app.services.query_decomposer_service import QueryDecomposerService
from app.services.output_guardrail_service import OutputGuardrailService
from app.services.query_understanding_service import QueryUnderstandingService

class ChatService:
    _configured = False
    _prompt_template = ""
    _rewrite_prompt_template = ""

    @classmethod
    def _configure(cls):
        if not cls._configured:
            api_key = settings.GEMINI_API_KEY
            genai.configure(api_key=api_key, transport='rest')
            
            prompts_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "prompts"
            )

            # Load answer prompt template
            prompt_path = os.path.join(prompts_dir, "chat_answer.txt")
            try:
                with open(prompt_path, "r", encoding="utf-8") as f:
                    cls._prompt_template = f.read()
            except Exception as e:
                logger.error(f"Failed to load chat_answer.txt: {str(e)}")
                cls._prompt_template = (
                    "Answer strictly based on this context:\n{context}\n\nQuestion: {question}"
                )

            # Load rewrite prompt template
            rewrite_prompt_path = os.path.join(prompts_dir, "query_rewrite.txt")
            try:
                with open(rewrite_prompt_path, "r", encoding="utf-8") as f:
                    cls._rewrite_prompt_template = f.read()
            except Exception as e:
                logger.error(f"Failed to load query_rewrite.txt: {str(e)}")
                cls._rewrite_prompt_template = (
                    "Bạn là trợ lý ảo phụ trách viết lại câu hỏi tìm kiếm. "
                    "Dựa trên lịch sử hội thoại dưới đây và câu hỏi tiếp theo, hãy viết lại câu hỏi tiếp theo thành một câu hỏi độc lập, đầy đủ ngữ nghĩa để tìm kiếm trong cơ sở dữ liệu. "
                    "Chỉ trả về câu hỏi độc lập mới, KHÔNG trả lời câu hỏi và KHÔNG thêm bất kỳ giải thích nào khác.\n\n"
                    "Lịch sử hội thoại:\n{history}\n\n"
                    "Câu hỏi tiếp theo: {question}\n\n"
                    "Câu hỏi độc lập viết lại:"
                )

            cls._configured = True

    @classmethod
    def _prepare_history_and_query(cls, db: Session, question: str, session_id: str = None, history_mode: bool = False):
        cls._configure()
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
                rewrite_prompt = cls._rewrite_prompt_template.format(
                    history=history_str,
                    question=question
                )
                try:
                    rewritten_question = cls._generate_with_key_rotation(db, rewrite_prompt)
                    logger.info(f"Original question: '{question}' -> Rewritten for search: '{rewritten_question}'")
                except Exception as ex:
                    logger.error(f"Failed to rewrite question using history: {str(ex)}")
                    rewritten_question = question
                    
        return history_str, rewritten_question

    @classmethod
    def _generate_with_key_rotation(cls, db: Session, prompt: str) -> str:
        """
        Execute Gemini LLM generation with rotated API keys.
        """
        from app.services.key_rotation_service import KeyRotationService
        last_error = None

        for attempt in range(5):
            raw_key, key_obj = KeyRotationService.get_valid_api_key(db, provider="gemini")
            try:
                genai.configure(api_key=raw_key, transport='rest')
                model = genai.GenerativeModel(model_name=settings.GEMINI_LLM_MODEL)
                response = model.generate_content(prompt)
                ans = response.text.strip()
                if key_obj:
                    KeyRotationService.report_key_success(db, key_obj.id)
                return ans
            except Exception as e:
                last_error = e
                err_str = str(e)
                logger.warning(f"LLM Generation attempt {attempt + 1} with key '{KeyRotationService.mask_key(raw_key)}' failed: {err_str}")
                if key_obj:
                    KeyRotationService.report_key_error(db, key_obj.id, err_str)

        raise last_error

    @classmethod
    def ask(cls, db: Session, question: str, session_id: str = None, history_mode: bool = False) -> Tuple[ChatLog, List[Dict[str, Any]]]:
        """
        Main Q&A Pipeline:
        1. Fast Guardrail: Semantic Cache Check
        2. LLM Semantic Query Understanding Pass (Intent Router + Anti-Injection + Sub-query Decomposition)
        3. Parallel Retrieval Engine per Sub-query (Dense pgvector + Sparse BM25 + Neo4j Graph) & RRF Fusion
        4. Gemini LLM Q&A Generation
        5. Output Guardrail Sanitation & Citation Verification
        """
        cls._configure()
        start_time = time.time()

        # 1. Fast Guardrail: Semantic Cache Check
        cached_result = CacheService.get_semantic_cache(db, question)
        if cached_result:
            cached_ans, cached_cits = cached_result
            resolved_session_id = session_id or str(uuid_mod.uuid4())
            chat_log = ChatLog(
                session_id=resolved_session_id,
                question=question,
                answer=cached_ans,
                retrieved_chunk_ids=[],
                graph_context=[],
                citations=cached_cits,
                latency_ms=int((time.time() - start_time) * 1000)
            )
            db.add(chat_log)
            db.commit()
            db.refresh(chat_log)
            return chat_log, cached_cits

        # 2. LLM Semantic Query Understanding Pass
        analysis = QueryUnderstandingService.analyze_query(db, question)
        intent = analysis.get("intent", "DOMAIN_QUERY")
        is_injection = analysis.get("is_prompt_injection", False)
        direct_reply = analysis.get("direct_reply")
        sub_queries = analysis.get("sub_queries") or [question]

        if is_injection or intent != "DOMAIN_QUERY":
            reply = direct_reply or "Xin chào! Tôi là trợ lý ảo hỗ trợ tra cứu tri thức doanh nghiệp."
            resolved_session_id = session_id or str(uuid_mod.uuid4())
            chat_log = ChatLog(
                session_id=resolved_session_id,
                question=question,
                answer=reply,
                retrieved_chunk_ids=[],
                graph_context=[],
                citations=[],
                latency_ms=int((time.time() - start_time) * 1000)
            )
            db.add(chat_log)
            db.commit()
            db.refresh(chat_log)
            return chat_log, []
        
        # 3. Prepare history and query rewrite
        history_str, query_for_retrieval = cls._prepare_history_and_query(db, question, session_id, history_mode)
        
        # 4. Multi-query Parallel Retrieval Engine
        chunks = []
        graph_relationships = []
        seen_ids = set()

        logger.info(f"Executing Multi-Query Retrieval Engine across {len(sub_queries)} sub-query(ies)...")
        for idx, sub_q in enumerate(sub_queries, start=1):
            logger.info(f"  -> Sub-query [{idx}/{len(sub_queries)}]: '{sub_q}'")
            sub_chunks, sub_rels = RetrievalService.retrieve_hybrid(db, sub_q)
            for c in sub_chunks:
                if c.id not in seen_ids:
                    seen_ids.add(c.id)
                    chunks.append(c)
            graph_relationships.extend(sub_rels)
        
        logger.info(f"Multi-query Retrieval complete. Combined unique candidate chunks: {len(chunks)}")
        
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
            if history_str:
                question_with_history = f"(Lịch sử hội thoại để tham khảo:\n{history_str})\n\nCâu hỏi hiện tại cần trả lời: {question}"
            else:
                question_with_history = question
            prompt = cls._prompt_template.replace("{context}", context_str).replace("{question}", question_with_history)
            
            logger.info("Calling Gemini LLM for Q&A with key rotation...")
            answer = cls._generate_with_key_rotation(db, prompt)
            answer = cls._normalize_citation_tags(answer)
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

        # 5. Output Guardrail Sanitation & Citation Check
        answer = OutputGuardrailService.validate_and_sanitize(answer, citations)

        # 6. Record to PostgreSQL
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
        
        # 1. Fast Guardrail: Semantic Cache Check
        cached_result = CacheService.get_semantic_cache(db, question)
        if cached_result:
            cached_ans, cached_cits = cached_result
            resolved_session_id = session_id or str(uuid_mod.uuid4())
            chat_log = ChatLog(
                session_id=resolved_session_id,
                question=question,
                answer=cached_ans,
                retrieved_chunk_ids=[],
                graph_context=[],
                citations=cached_cits,
                latency_ms=25
            )
            try:
                db.add(chat_log)
                db.commit()
                db.refresh(chat_log)
            except Exception:
                db.rollback()

            yield f"data: {json.dumps({'type': 'content', 'content': cached_ans}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'metadata', 'chat_id': str(chat_log.id), 'session_id': resolved_session_id, 'citations': cached_cits}, ensure_ascii=False)}\n\n"
            return

        # 2. LLM Semantic Query Understanding Pass
        analysis = QueryUnderstandingService.analyze_query(db, question)
        intent = analysis.get("intent", "DOMAIN_QUERY")
        is_injection = analysis.get("is_prompt_injection", False)
        direct_reply = analysis.get("direct_reply")
        sub_queries = analysis.get("sub_queries") or [question]

        if is_injection or intent != "DOMAIN_QUERY":
            reply = direct_reply or "Xin chào! Tôi là trợ lý ảo hỗ trợ tra cứu tri thức doanh nghiệp."
            resolved_session_id = session_id or str(uuid_mod.uuid4())
            chat_log = ChatLog(
                session_id=resolved_session_id,
                question=question,
                answer=reply,
                retrieved_chunk_ids=[],
                graph_context=[],
                citations=[],
                latency_ms=int((time.time() - start_time) * 1000)
            )
            try:
                db.add(chat_log)
                db.commit()
                db.refresh(chat_log)
            except Exception:
                db.rollback()

            yield f"data: {json.dumps({'type': 'content', 'content': reply}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'metadata', 'chat_id': str(chat_log.id), 'session_id': resolved_session_id, 'citations': []}, ensure_ascii=False)}\n\n"
            return

        # 1. Prepare history and query rewrite
        history_str, query_for_retrieval = cls._prepare_history_and_query(db, question, session_id, history_mode)
        
        # 2. Query Decomposition & Parallel Retrieval Engine
        sub_queries = QueryDecomposerService.decompose_query(query_for_retrieval)
        chunks = []
        graph_relationships = []
        seen_ids = set()

        for sub_q in sub_queries:
            sub_chunks, sub_rels = RetrievalService.retrieve_hybrid(db, sub_q)
            for c in sub_chunks:
                if c.id not in seen_ids:
                    seen_ids.add(c.id)
                    chunks.append(c)
            graph_relationships.extend(sub_rels)
        
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
        normalized_answer = cls._normalize_citation_tags(answer)
        cited_indices = re.findall(r"\[S(\d+)\]", normalized_answer)
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

    @staticmethod
    def _normalize_citation_tags(text: str) -> str:
        """
        Converts grouped citations like [S1, S4] or [S1, S2, S3] or [S1; S2] into separate tags [S1][S4].
        Ensures frontend Markdown renderer can parse each source pill correctly.
        """
        if not text:
            return text

        def replacer(match):
            content = match.group(0)
            nums = re.findall(r"\d+", content)
            if nums:
                return "".join([f"[S{num}]" for num in nums])
            return content

        pattern = r"\[\s*S?\d+(?:\s*[\s,;&]\s*S?\d+)+\s*\]"
        return re.sub(pattern, replacer, text, flags=re.IGNORECASE)

    @staticmethod
    def _is_prompt_injection(question: str) -> bool:
        """
        Detects Prompt Injection and System Prompt Leakage attempts in user query.
        """
        if not question:
            return False
            
        patterns = [
            r"(bỏ qua|ignore|override)\s+(tất cả\s+|các\s+)?(chỉ thị|hướng dẫn|quy tắc hệ thống|prompt|system prompt|cấu hình hệ thống|lệnh hệ thống)",
            r"(bỏ qua|ignore|override)\s+system",
            r"(hiển thị|in ra|cho tôi biết|cho xem|tiết lộ|trả lời|show|print|reveal|tell me|display)\s+.*(system prompt|chỉ thị hệ thống|cấu hình prompt|prompt hiện tại|lệnh hệ thống)",
            r"you are now in (dan|jailbreak) mode",
            r"jailbreak"
        ]
        q_lower = question.lower()
        for p in patterns:
            if re.search(p, q_lower):
                return True
        return False
