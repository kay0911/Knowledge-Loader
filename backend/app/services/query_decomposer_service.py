import re
from typing import List
from app.core.logging import logger

class QueryDecomposerService:
    @classmethod
    def decompose_query(cls, question: str) -> List[str]:
        """
        Decomposes complex multi-part queries (e.g., comparison or multi-topic questions)
        into distinct, context-rich sub-queries for parallel retrieval.
        """
        if not question:
            return []

        q_clean = question.strip()
        q_lower = q_clean.lower()

        # Check for comparison or multi-clause patterns
        is_comparison = any(k in q_lower for k in ["so sánh", "khác nhau", "đối chiếu", "phân biệt", "đồng thời"])
        
        if is_comparison and " và " in q_lower:
            parts = re.split(r"\bvà\b", q_clean, flags=re.IGNORECASE)
            if len(parts) >= 2:
                p1 = parts[0].strip()
                p2 = parts[1].strip().rstrip(".?")

                # Extract topic context from p1 (e.g. "vụ", "bảo hành", "xe", "chính sách")
                topic_prefix = ""
                topic_match = re.search(r"(vụ|chính sách|quy định|bảo hành|dòng xe|sản phẩm|thiết bị)\s+", p1, flags=re.IGNORECASE)
                if topic_match:
                    topic_prefix = topic_match.group(0)

                sub1 = p1
                sub2 = f"{topic_prefix}{p2}" if topic_prefix and not p2.lower().startswith(topic_prefix.lower().strip()) else p2
                
                sub_queries = [sub1, sub2]
                logger.info(f"Query Decomposer split '{question}' into sub-queries: {sub_queries}")
                return sub_queries

        return [q_clean]
