import re
from typing import Tuple, Optional
from app.core.logging import logger

class IntentRouterService:
    CHITCHAT_PATTERNS = [
        r"^(xin\s+chào|chào\s+bạn|hello|hi|good\s+morning|good\s+afternoon|good\s+evening)\b",
        r"^(bạn\s+là\s+ai|bạn\s+tên\s+là\s+gì|who\s+are\s+you)\b",
        r"^(cảm\s+ơn|thank\s+you|thanks)\b",
        r"^(bạn\s+có\s+thể\s+làm\s+gì|giúp\s+gì\s+cho\s+tôi)\b"
    ]

    OUT_OF_DOMAIN_PATTERNS = [
        r"(thời\s+tiết|dự\s+báo\s+thời\s+tiết|nhiệt\s+độ\s+hôm\s+nay)",
        r"(công\s+thức\s+nấu|nấu\s+ăn|món\s+ngon|bún\s+chả|phở)",
        r"(kết\s+quả\s+bóng\s+đá|giải\s+ngoại\s+hạng|champion\s+league)",
        r"(xem\s+bói|tử\s+vi|chứng\s+khoán\s+hôm\s+nay|giá\s+vàng)"
    ]

    @classmethod
    def route_intent(cls, question: str) -> Tuple[str, Optional[str]]:
        """
        Routes the user intent into one of 3 categories:
        1. 'CHITCHAT' -> Direct LLM / Static Template
        2. 'OUT_OF_DOMAIN' -> Fallback Disclaimer
        3. 'DOMAIN_QUERY' -> Continue to RAG Pipeline
        Returns tuple (intent_type, response_text_if_any)
        """
        if not question:
            return "OUT_OF_DOMAIN", "Vui lòng nhập câu hỏi để tôi có thể hỗ trợ bạn."

        q_lower = question.strip().lower()

        # 1. Check Chitchat
        for p in cls.CHITCHAT_PATTERNS:
            if re.search(p, q_lower):
                logger.info(f"Intent Router matched CHITCHAT for query: '{question}'")
                reply = "Xin chào! Tôi là trợ lý ảo hỗ trợ tra cứu tri thức nội bộ. Bạn cần tìm hiểu thông tin hoặc quy định gì trong kho tài liệu doanh nghiệp hôm nay?"
                return "CHITCHAT", reply

        # 2. Check Out-of-Domain
        for p in cls.OUT_OF_DOMAIN_PATTERNS:
            if re.search(p, q_lower):
                logger.info(f"Intent Router matched OUT_OF_DOMAIN for query: '{question}'")
                reply = "Tôi là trợ lý tra cứu tri thức nội bộ doanh nghiệp. Câu hỏi này nằm ngoài phạm vi tài liệu và quy định nghiệp vụ được cung cấp."
                return "OUT_OF_DOMAIN", reply

        # 3. Domain Query
        return "DOMAIN_QUERY", None
