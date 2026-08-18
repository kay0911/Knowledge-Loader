import os
import json
import logging
import re
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger

try:
    import google.generativeai as genai
except ImportError:
    genai = None

class DocumentSummaryService:
    @classmethod
    def generate_document_metadata(
        cls,
        filename: str,
        chunks: List[Dict[str, Any]],
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Generates Document Metadata Summary using Option 2 (Single-Stage Direct One-Shot Prompting).
        Packs 100% of document chunks into a single context prompt for Gemini / LLM.
        Returns structured JSON adhering to DocumentMetadataSchema.
        """
        logger.info(f"Generating Document Metadata Summary (Option 2 One-Shot Context) for {filename} across {len(chunks)} chunks...")
        
        # Combine all chunk content into 1 full document context
        doc_text_parts = []
        for idx, chunk in enumerate(chunks, start=1):
            heading_path = chunk.get("heading_path", [])
            heading = " > ".join(heading_path) if isinstance(heading_path, list) else str(heading_path)
            content = chunk.get("content", "").strip()
            doc_text_parts.append(f"--- CHUNK {idx} (Heading: {heading}) ---\n{content}")

        full_doc_context = "\n\n".join(doc_text_parts)

        prompt = f"""Bạn là Chuyên gia Đánh giá và Phân loại Tài liệu Doanh nghiệp cho Hệ thống RAG.
Hãy đọc TOÀN BỘ nội dung các Chunks của tài liệu dưới đây và trích xuất ra một bản Metadata tổng hợp tài liệu dạng JSON CHUẨN XÁC NGUYÊN BẢN.

TÊN FILE TÀI LIỆU: {filename}

NỘI DUNG TOÀN BỘ CHUNKS CỦA TÀI LIỆU:
{full_doc_context}

---
YÊU CẦU ĐẦU RA JSON (Chỉ trả về JSON thuần hợp lệ, không bọc trong ```json hay bất kỳ văn bản nào khác):

{{
  "filename": "{filename}",
  "document_summary": "<Tóm tắt ngắn gọn 2-3 câu bức tranh tổng quan của toàn bộ tài liệu>",
  "domain": "<Lĩnh vực chính: DATA_ENGINEERING | AFTER_SALES | SUPPLY_CHAIN | QUALITY_ENG | FINANCE | IT_SECURITY | GA_MANUFACTURING>",
  "sub_domain": "<Phân khúc cụ thể, ví dụ: FABRIC_ONELAKE / WARRANTY / PFEP / PAM / BOM / GA_CONSUMPTION>",
  "doc_type": "<Loại tài liệu: USER_GUIDE | TECHNICAL_SPEC | BUSINESS_REPORT | TRAINING_MANUAL | DECISION_PROPOSAL | TIMELINE_PLAN>",
  "target_audience": ["<Danh sách đối tượng sử dụng, ví dụ: DATA_ANALYST, DEALER_PIC, ENGINEER>"],
  "primary_entities": ["<Các thực thể, báo cáo, sản phẩm chính xuất hiện trong file>"],
  "system_dependencies": ["<Các hệ thống liên quan: SAP, PowerBI, Fabric, Azure, TeamCenter, IDS, eSync>"],
  "keywords": ["<5-10 từ khóa cốt lõi, từ viết tắt chuyên ngành: PFEP, FRS, SOH, GIT, Min Max...>"],
  "applicable_scope": {{
    "region": ["<Khu vực: VN, US, CA, EU, GLOBAL>"],
    "timeframe": "<Thời gian áp dụng, ví dụ: 2024-2026>"
  }},
  "hypothetical_questions": [
    "<Câu hỏi mẫu 1 người dùng thường sẽ hỏi tài liệu này>",
    "<Câu hỏi mẫu 2 người dùng thường sẽ hỏi tài liệu này>",
    "<Câu hỏi mẫu 3 người dùng thường sẽ hỏi tài liệu này>",
    "<Câu hỏi mẫu 4 người dùng thường sẽ hỏi tài liệu này>",
    "<Câu hỏi mẫu 5 người dùng thường sẽ hỏi tài liệu này>"
  ]
}}
"""

        ans_json = None
        if db:
            from app.services.key_rotation_service import KeyRotationService
            for attempt in range(5):
                raw_key, key_obj = KeyRotationService.get_valid_api_key(db, provider="gemini")
                try:
                    if genai:
                        genai.configure(api_key=raw_key, transport='rest')
                        model = genai.GenerativeModel(model_name=getattr(settings, "GEMINI_LLM_MODEL", "gemini-3.5-flash-lite"))
                        response = model.generate_content(prompt)
                        ans_json = response.text.strip()
                    if key_obj:
                        KeyRotationService.report_key_success(db, key_obj.id)
                    break
                except Exception as e:
                    err_str = str(e)
                    logger.warning(f"Metadata LLM generation attempt {attempt+1} failed: {err_str}")
                    if key_obj:
                        KeyRotationService.report_key_error(db, key_obj.id, err_str)
        else:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                try:
                    from app.services.key_rotation_service import KeyRotationService
                    api_key = KeyRotationService._get_fallback_api_key("gemini")
                except Exception:
                    api_key = None
            if api_key and genai:
                try:
                    genai.configure(api_key=api_key, transport='rest')
                    model = genai.GenerativeModel(model_name=getattr(settings, "GEMINI_LLM_MODEL", "gemini-3.5-flash-lite"))
                    response = model.generate_content(prompt)
                    ans_json = response.text.strip()
                except Exception as e:
                    logger.warning(f"Fallback Gemini metadata extraction failed: {e}")

        if not ans_json:
            logger.warning(f"Could not get LLM response for document metadata {filename}, falling back to rule-based fallback metadata.")
            return cls._build_fallback_metadata(filename, chunks)

        # Sanitize JSON output
        try:
            clean_json_str = re.sub(r"^```json\s*", "", ans_json, flags=re.IGNORECASE)
            clean_json_str = re.sub(r"```$", "", clean_json_str).strip()
            parsed_metadata = json.loads(clean_json_str)
            logger.info(f"Successfully generated Document Metadata for {filename}! Domain: {parsed_metadata.get('domain')}, Questions: {len(parsed_metadata.get('hypothetical_questions', []))}")
            return parsed_metadata
        except Exception as parse_err:
            logger.error(f"Failed to parse LLM JSON output for document metadata {filename}: {parse_err}. Output: {ans_json[:200]}")
            return cls._build_fallback_metadata(filename, chunks)

    @classmethod
    def _build_fallback_metadata(cls, filename: str, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        fn_lower = filename.lower()
        domain = "GENERAL"
        if "ga" in fn_lower or "tieu hao" in fn_lower:
            domain = "GA_MANUFACTURING"
        elif "freight" in fn_lower or "timeline" in fn_lower or "scm" in fn_lower:
            domain = "SUPPLY_CHAIN"
        elif "indicator" in fn_lower or "glidepath" in fn_lower or "warranty" in fn_lower:
            domain = "QUALITY_ENG"
        elif "khhd" in fn_lower or "data team" in fn_lower:
            domain = "DATA_ENGINEERING"

        keywords = list(set(re.findall(r"\b[A-Z0-9]{3,}\b", filename)))
        return {
            "filename": filename,
            "document_summary": f"Tài liệu {filename} chứa thông tin quy trình và dữ liệu chuyên ngành.",
            "domain": domain,
            "sub_domain": "GENERAL",
            "doc_type": "USER_GUIDE" if ".docx" in fn_lower else ("BUSINESS_REPORT" if ".xlsx" in fn_lower else "DOCUMENT"),
            "target_audience": ["STAFF"],
            "primary_entities": [filename],
            "system_dependencies": [],
            "keywords": keywords or ["VinFast", "Report"],
            "applicable_scope": {"region": ["VN"], "timeframe": "2024-2026"},
            "hypothetical_questions": [
                f"Nội dung chính của tài liệu {filename} là gì?",
                f"Tài liệu {filename} quy định quy trình nào?"
            ]
        }
