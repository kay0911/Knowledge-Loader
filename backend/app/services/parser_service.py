import os
import re
import uuid
import pypdf
import docx
import openpyxl
from typing import List, Dict, Any, Optional
from app.schemas.normalized_block import NormalizedBlock
from app.core.logging import logger

try:
    from markitdown import MarkItDown
    markitdown_available = True
    markitdown_instance = MarkItDown()
except ImportError:
    markitdown_available = False
    markitdown_instance = None
    logger.warning("markitdown package not found, falling back to direct parsing.")

class ParserService:
    @staticmethod
    def parse_markdown_content(
        md_text: str, 
        source_type: str, 
        page_start: Optional[int] = None, 
        page_end: Optional[int] = None,
        initial_order: int = 0
    ) -> List[NormalizedBlock]:
        """
        Parses standardized Markdown text into structured NormalizedBlock list.
        Tracks heading hierarchy (heading_path), code blocks, tables, and lists.
        """
        blocks: List[NormalizedBlock] = []
        lines = md_text.split("\n")
        
        current_heading_path: List[str] = []
        source_order = initial_order
        
        buf_type = "paragraph"
        buf_lines: List[str] = []
        in_code_block = False
        code_block_lines: List[str] = []

        def flush_buffer():
            nonlocal source_order, buf_lines, buf_type
            if not buf_lines:
                return
            
            content = "\n".join(buf_lines).strip()
            if content:
                source_order += 1
                blocks.append(NormalizedBlock(
                    block_id=str(uuid.uuid4()),
                    source_type=source_type,
                    block_type=buf_type,
                    content=content,
                    heading_path=list(current_heading_path),
                    page_start=page_start,
                    page_end=page_end,
                    source_order=source_order
                ))
            buf_lines = []
            buf_type = "paragraph"

        for line in lines:
            trimmed = line.strip()

            # Filter out decorative horizontal rules (e.g. ---, ***, ___, --------...)
            if re.match(r"^[\s\-\*_]{3,}$", trimmed):
                flush_buffer()
                continue

            # Handle Code Blocks ```
            if trimmed.startswith("```"):
                if in_code_block:
                    code_block_lines.append(trimmed)
                    source_order += 1
                    blocks.append(NormalizedBlock(
                        block_id=str(uuid.uuid4()),
                        source_type=source_type,
                        block_type="code",
                        content="\n".join(code_block_lines),
                        heading_path=list(current_heading_path),
                        page_start=page_start,
                        page_end=page_end,
                        source_order=source_order
                    ))
                    code_block_lines = []
                    in_code_block = False
                else:
                    flush_buffer()
                    in_code_block = True
                    code_block_lines = [trimmed]
                continue

            if in_code_block:
                code_block_lines.append(line)
                continue

            # Handle Headings (# Heading)
            heading_match = re.match(r"^(#{1,6})\s+(.*)$", trimmed)
            if heading_match:
                flush_buffer()
                level = len(heading_match.group(1))
                h_text = heading_match.group(2).strip()

                if level == 1:
                    current_heading_path = [h_text]
                elif level == 2:
                    current_heading_path = [current_heading_path[0], h_text] if len(current_heading_path) >= 1 else [h_text]
                else:
                    current_heading_path = current_heading_path[:level-1] + [h_text]

                source_order += 1
                blocks.append(NormalizedBlock(
                    block_id=str(uuid.uuid4()),
                    source_type=source_type,
                    block_type="heading",
                    content=h_text,
                    heading_path=list(current_heading_path),
                    page_start=page_start,
                    page_end=page_end,
                    source_order=source_order
                ))
                continue

            # Handle Markdown Tables (| col | col |)
            if trimmed.startswith("|") and trimmed.endswith("|"):
                if buf_type != "table":
                    flush_buffer()
                    buf_type = "table"
                buf_lines.append(trimmed)
                continue
            elif buf_type == "table":
                flush_buffer()

            # Handle Lists (- item, * item, 1. item)
            if re.match(r"^(\*|-|\+|\d+\.)\s+", trimmed):
                if buf_type != "list":
                    flush_buffer()
                    buf_type = "list"
                buf_lines.append(trimmed)
                continue
            elif buf_type == "list" and trimmed == "":
                flush_buffer()

            # Empty lines flush buffer
            if not trimmed:
                flush_buffer()
                continue

            # Paragraph lines
            if buf_type not in ["paragraph", "list"]:
                flush_buffer()
                buf_type = "paragraph"
            buf_lines.append(line)

        flush_buffer()
        return blocks

    @classmethod
    def parse_pdf(cls, file_path: str) -> List[NormalizedBlock]:
        logger.info(f"Parsing PDF file with Layout Font-Size Parser: {file_path}")
        try:
            import pdfplumber
            from collections import Counter

            font_sizes = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    words = page.extract_words(extra_attrs=['fontname', 'size'])
                    for w in words:
                        font_sizes.append(round(w['size'], 1))

                if font_sizes:
                    base_size = Counter(font_sizes).most_common(1)[0][0]
                    md_lines = []

                    for page_idx, page in enumerate(pdf.pages):
                        page_num = page_idx + 1
                        words = page.extract_words(extra_attrs=['fontname', 'size'])
                        lines_dict = {}
                        for w in words:
                            top = round(w['top'], 1)
                            matching_top = None
                            for k in lines_dict:
                                if abs(k - top) <= 3:
                                    matching_top = k
                                    break
                            if matching_top is None:
                                matching_top = top
                                lines_dict[matching_top] = []
                            lines_dict[matching_top].append(w)

                        for top in sorted(lines_dict.keys()):
                            line_words = sorted(lines_dict[top], key=lambda x: x['x0'])
                            line_text = ' '.join([w['text'] for w in line_words]).strip()
                            if not line_text:
                                continue

                            avg_size = sum(w['size'] for w in line_words) / len(line_words)
                            is_bold = any('bold' in w['fontname'].lower() or 'heavy' in w['fontname'].lower() for w in line_words)

                            # Auto-convert font sizes & bold lines to Markdown Headings # and ##
                            if avg_size >= base_size * 1.4:
                                md_lines.append(f"# {line_text}")
                            elif avg_size >= base_size * 1.15 or (is_bold and len(line_text) < 100):
                                md_lines.append(f"## {line_text}")
                            else:
                                md_lines.append(line_text)

                    full_md_text = "\n\n".join(md_lines)
                    return cls.parse_markdown_content(md_text=full_md_text, source_type="pdf")

        except Exception as err:
            logger.warning(f"pdfplumber layout parsing failed for {file_path}, falling back to pypdf: {str(err)}")

        # Fallback to pypdf
        blocks: List[NormalizedBlock] = []
        try:
            reader = pypdf.PdfReader(file_path)
            order_counter = 0

            for page_idx, page in enumerate(reader.pages):
                page_num = page_idx + 1
                text = page.extract_text() or ""
                if not text.strip():
                    continue

                page_blocks = cls.parse_markdown_content(
                    md_text=text,
                    source_type="pdf",
                    page_start=page_num,
                    page_end=page_num,
                    initial_order=order_counter
                )
                order_counter += len(page_blocks)
                blocks.extend(page_blocks)

        except Exception as e:
            logger.error(f"Error parsing PDF {file_path}: {str(e)}")
            raise e

        return blocks

    @classmethod
    def parse_docx(cls, file_path: str) -> List[NormalizedBlock]:
        logger.info(f"Parsing DOCX file with MarkItDown: {file_path}")
        try:
            if markitdown_available and markitdown_instance:
                result = markitdown_instance.convert(file_path)
                md_text = result.text_content
                return cls.parse_markdown_content(md_text=md_text, source_type="docx")
        except Exception as err:
            logger.warning(f"MarkItDown conversion failed for {file_path}, falling back to python-docx: {str(err)}")

        # Fallback to python-docx parsing
        blocks: List[NormalizedBlock] = []
        try:
            doc = docx.Document(file_path)
            source_order = 0
            current_heading_path = ["Tổng quan"]

            for para in doc.paragraphs:
                text = para.text.strip()
                if not text:
                    continue

                style_name = para.style.name.lower() if para.style else ""
                
                if "heading" in style_name or text.startswith("#"):
                    heading_text = re.sub(r"^\#+\s*", "", text).strip()
                    current_heading_path = [heading_text]
                    source_order += 1
                    blocks.append(NormalizedBlock(
                        block_id=str(uuid.uuid4()),
                        source_type="docx",
                        block_type="heading",
                        content=heading_text,
                        heading_path=list(current_heading_path),
                        source_order=source_order
                    ))
                else:
                    source_order += 1
                    blocks.append(NormalizedBlock(
                        block_id=str(uuid.uuid4()),
                        source_type="docx",
                        block_type="paragraph",
                        content=text,
                        heading_path=list(current_heading_path),
                        source_order=source_order
                    ))
        except Exception as e:
            logger.error(f"Error parsing DOCX {file_path}: {str(e)}")
            raise e

        return blocks

    @staticmethod
    def parse_xlsx(file_path: str) -> List[NormalizedBlock]:
        logger.info(f"Parsing XLSX file: {file_path}")
        blocks: List[NormalizedBlock] = []
        try:
            wb = openpyxl.load_workbook(file_path, data_only=True)
            source_order = 0

            for sheet_name in wb.sheetnames:
                sheet = wb[sheet_name]
                
                headers = []
                for col in range(1, sheet.max_column + 1):
                    val = sheet.cell(row=1, column=col).value
                    headers.append(str(val).strip() if val is not None else f"Col{col}")
                
                for r in range(2, sheet.max_row + 1):
                    row_vals = []
                    has_data = False
                    for col in range(1, sheet.max_column + 1):
                        val = sheet.cell(row=r, column=col).value
                        if val is not None:
                            has_data = True
                        row_vals.append(str(val).strip() if val is not None else "")
                    
                    if not has_data:
                        continue
                    
                    source_order += 1
                    record_lines = [f"Row {r}: " + " | ".join([f"{h}: {v}" for h, v in zip(headers, row_vals) if v])]
                    
                    blocks.append(NormalizedBlock(
                        block_id=str(uuid.uuid4()),
                        source_type="xlsx",
                        block_type="table",
                        content="\n".join(record_lines),
                        heading_path=[f"Sheet: {sheet_name}"],
                        sheet_name=sheet_name,
                        row_start=r,
                        row_end=r,
                        table_id=f"sheet_{sheet_name}",
                        source_order=source_order
                    ))

        except Exception as e:
            logger.error(f"Error parsing XLSX {file_path}: {str(e)}")
            raise e

        return blocks

    @classmethod
    def parse(cls, file_path: str, file_type: str) -> List[NormalizedBlock]:
        file_type = file_type.lower().strip(".")
        if file_type == "pdf":
            return cls.parse_pdf(file_path)
        elif file_type in ["docx", "doc"]:
            return cls.parse_docx(file_path)
        elif file_type in ["xlsx", "xls", "csv"]:
            return cls.parse_xlsx(file_path)
        elif file_type in ["md", "markdown"]:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return cls.parse_markdown_content(content, source_type="md")
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
