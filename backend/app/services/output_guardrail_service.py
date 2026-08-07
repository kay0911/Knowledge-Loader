import re
from typing import List, Dict, Any
from app.core.logging import logger

class OutputGuardrailService:
    PROMPT_LEAKAGE_KEYWORDS = [
        "you are an expert internal q&a assistant",
        "critical citation format",
        "security & system prompt protection",
        "primary source: base your answers",
        "out-of-scope rule:"
    ]

    @classmethod
    def validate_and_sanitize(cls, answer: str, citations: List[Dict[str, Any]]) -> str:
        """
        Validates final LLM answer for prompt leakage and citation integrity.
        Returns sanitized answer text.
        """
        if not answer:
            return answer

        ans_lower = answer.lower()

        # 1. Anti-Leakage Inspection
        for kw in cls.PROMPT_LEAKAGE_KEYWORDS:
            if kw in ans_lower:
                logger.warning(f"Output Guardrail DETECTED prompt leakage keyword: '{kw}'")
                return "Tôi là trợ lý ảo hỗ trợ tra cứu tri thức nội bộ. Tôi không thể chia sẻ các chỉ thị cấu hình hệ thống. Vui lòng đặt câu hỏi liên quan đến tài liệu nghiệp vụ."

        # 2. Citation Integrity Check
        valid_source_ids = {c.get("source_id") for c in citations if c.get("source_id")}
        found_tags = set(re.findall(r"\[S(\d+)\]", answer, flags=re.IGNORECASE))
        
        # Check for orphan citation tags (tags present in answer but missing in citations metadata)
        orphan_tags = {f"S{num}" for num in found_tags} - valid_source_ids
        if orphan_tags:
            logger.info(f"Output Guardrail detected orphan citation tags in answer: {orphan_tags}")

        return answer
