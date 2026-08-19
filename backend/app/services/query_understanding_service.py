import os
import re
import json
from typing import Dict, Any, List
from app.core.config import settings
from app.core.logging import logger

class QueryUnderstandingService:
    _prompt_template: str = ""

    @classmethod
    def _load_prompt(cls) -> str:
        if not cls._prompt_template:
            prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "query_understanding.txt")
            if os.path.exists(prompt_path):
                with open(prompt_path, "r", encoding="utf-8") as f:
                    cls._prompt_template = f.read()
            else:
                logger.error(f"query_understanding.txt not found at {prompt_path}")
        return cls._prompt_template

    @classmethod
    def is_complex_query(cls, question: str) -> bool:
        """
        Determines if a question is complex/composite or multi-part
        that warrants calling LLM decomposition pass.
        """
        if not question:
            return False

        q_lower = question.strip().lower()

        # Multiple question marks e.g. "Hỏi 1? Hỏi 2?"
        if q_lower.count("?") > 1 or q_lower.count(";") > 1:
            return True

        # Explicit comparison or multi-part keywords
        complex_keywords = [
            "so sánh", "khác nhau", "giống nhau", "phân biệt", "đối chiếu",
            "vừa", "đồng thời", "và cả", "cả 2", "cả hai", "mặt khác",
            "vụ việc", "mục 1 và", "điều 1 và"
        ]
        if any(k in q_lower for k in complex_keywords):
            return True

        # Check for multiple case/doc IDs e.g., "VV-2025-004 ... VV-2025-002"
        case_matches = re.findall(r"(?:vv|tc|fsd|wo|po|pr|md)[-_\s]?\d{3,}", q_lower)
        if len(set(case_matches)) > 1:
            return True

        return False

    @classmethod
    def analyze_query(cls, db, question: str) -> Dict[str, Any]:
        """
        Analyzes user query. Uses fast-path rules for simple queries ($0 LLM cost),
        and invokes LLM Query Understanding ONLY for complex/multi-part questions.
        """
        if not question:
            return {
                "intent": "OUT_OF_DOMAIN",
                "is_prompt_injection": False,
                "direct_reply": "Vui lòng nhập câu hỏi để tôi có thể hỗ trợ bạn.",
                "sub_queries": []
            }

        # Fast-Path Rule Checks (Chitchat, Prompt Injection, Simple Queries)
        fast_path = cls._fallback_analysis(question)
        
        # If chitchat or prompt injection detected, return fast-path response immediately ($0 LLM cost)
        if fast_path["intent"] != "DOMAIN_QUERY" or fast_path["is_prompt_injection"]:
            logger.info(f"Fast-path query analysis matched -> Intent: {fast_path['intent']}, Injection: {fast_path['is_prompt_injection']}")
            return fast_path

        # For simple single-topic domain queries, bypass LLM Query Understanding ($0 LLM cost)
        if not cls.is_complex_query(question):
            logger.info("Single-topic domain query detected. Bypassing LLM Query Understanding pass ($0 LLM cost).")
            return fast_path

        # LLM Query Understanding Pass for Complex/Multi-part Queries
        template = cls._load_prompt()
        if not template:
            return fast_path

        prompt = template.replace("{question}", question)

        try:
            logger.info("Executing LLM Query Understanding Pass for Complex Query...")
            from app.services.chat_service import ChatService
            response_text = ChatService._generate_with_key_rotation(db, prompt)
            
            # Clean JSON formatting if LLM wrapped it in markdown ```json ... ```
            json_str = response_text.strip()
            if json_str.startswith("```"):
                json_str = re.sub(r"^```(?:json)?\n?", "", json_str)
                json_str = re.sub(r"\n?```$", "", json_str)

            data = json.loads(json_str)
            logger.info(f"LLM Query Understanding Result -> Intent: {data.get('intent')}, Sub-queries: {data.get('sub_queries')}")
            return data
        except Exception as e:
            logger.error(f"LLM Query Understanding failed: {str(e)}. Using fast-path fallback.", exc_info=True)
            return fast_path

    @classmethod
    def _fallback_analysis(cls, question: str) -> Dict[str, Any]:
        """
        Rule-based fallback if LLM understanding pass fails.
        """
        q_lower = question.strip().lower()
        
        # Simple injection fallback
        if any(k in q_lower for k in ["bỏ qua system", "ignore instructions", "show system prompt"]):
            return {
                "intent": "DOMAIN_QUERY",
                "is_prompt_injection": True,
                "direct_reply": "Tôi là trợ lý ảo hỗ trợ tra cứu tri thức doanh nghiệp. Tôi không thể chia sẻ các chỉ thị cấu hình hệ thống.",
                "sub_queries": [question]
            }

        # Simple chitchat fallback
        if any(q_lower.startswith(k) for k in ["xin chào", "chào bạn", "hello", "hi", "cảm ơn"]):
            return {
                "intent": "CHITCHAT",
                "is_prompt_injection": False,
                "direct_reply": "Xin chào! Tôi là trợ lý ảo hỗ trợ tra cứu tri thức nội bộ. Bạn cần tìm hiểu thông tin gì trong kho tài liệu doanh nghiệp hôm nay?",
                "sub_queries": []
            }

        return {
            "intent": "DOMAIN_QUERY",
            "is_prompt_injection": False,
            "direct_reply": None,
            "sub_queries": [question]
        }
