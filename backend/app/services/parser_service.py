import os
import re
import uuid
import pypdf
import docx
import openpyxl
from typing import List, Dict, Any, Optional
from app.schemas.normalized_block import NormalizedBlock
from app.core.logging import logger

class ParserService:
    @staticmethod
    def parse_pdf(file_path: str) -> List[NormalizedBlock]:
        logger.info(f"Parsing PDF file (Page-aware): {file_path}")
        blocks: List[NormalizedBlock] = []
        try:
            reader = pypdf.PdfReader(file_path)
            source_order = 0
            current_heading_path = []

            for page_idx, page in enumerate(reader.pages):
                page_num = page_idx + 1
                text = page.extract_text() or ""
                lines = [line.strip() for line in text.split("\n") if line.strip()]
                
                if not lines:
                    continue

                page_content_paragraphs = []
                for line in lines:
                    # Detect simple heading lines (e.g., Starts with Chapter, Section, 1., #)
                    if re.match(r"^(Chương|Mục|\d+\.|\#+)\s+", line, re.IGNORECASE) and len(line) < 100:
                        if page_content_paragraphs:
                            source_order += 1
                            blocks.append(NormalizedBlock(
                                block_id=str(uuid.uuid4()),
                                source_type="pdf",
                                block_type="paragraph",
                                content="\n".join(page_content_paragraphs),
                                heading_path=list(current_heading_path),
                                page_start=page_num,
                                page_end=page_num,
                                source_order=source_order
                            ))
                            page_content_paragraphs = []
                        
                        heading_clean = re.sub(r"^\#+\s*", "", line).strip()
                        current_heading_path = [heading_clean]
                        source_order += 1
                        blocks.append(NormalizedBlock(
                            block_id=str(uuid.uuid4()),
                            source_type="pdf",
                            block_type="heading",
                            content=heading_clean,
                            heading_path=list(current_heading_path),
                            page_start=page_num,
                            page_end=page_num,
                            source_order=source_order
                        ))
                    else:
                        page_content_paragraphs.append(line)

                if page_content_paragraphs:
                    source_order += 1
                    blocks.append(NormalizedBlock(
                        block_id=str(uuid.uuid4()),
                        source_type="pdf",
                        block_type="paragraph",
                        content="\n".join(page_content_paragraphs),
                        heading_path=list(current_heading_path),
                        page_start=page_num,
                        page_end=page_num,
                        source_order=source_order
                    ))

        except Exception as e:
            logger.error(f"Error parsing PDF {file_path}: {str(e)}")
            raise e

        return blocks

    @staticmethod
    def parse_docx(file_path: str) -> List[NormalizedBlock]:
        logger.info(f"Parsing DOCX file: {file_path}")
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
                    # Calculate depth
                    if "heading 1" in style_name:
                        current_heading_path = [heading_text]
                    elif "heading 2" in style_name and len(current_heading_path) >= 1:
                        current_heading_path = [current_heading_path[0], heading_text]
                    else:
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
                elif style_name.startswith("list"):
                    source_order += 1
                    blocks.append(NormalizedBlock(
                        block_id=str(uuid.uuid4()),
                        source_type="docx",
                        block_type="list",
                        content=text,
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

            # Also parse tables in DOCX
            for table_idx, table in enumerate(doc.tables):
                table_rows = []
                for row in table.rows:
                    cells = [cell.text.strip() for cell in row.cells]
                    if any(cells):
                        table_rows.append(" | ".join(cells))
                
                if table_rows:
                    source_order += 1
                    table_content = "\n".join(table_rows)
                    blocks.append(NormalizedBlock(
                        block_id=str(uuid.uuid4()),
                        source_type="docx",
                        block_type="table",
                        content=table_content,
                        heading_path=list(current_heading_path),
                        table_id=f"table_{table_idx + 1}",
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
                
                # Identify headers from row 1
                headers = []
                for col in range(1, sheet.max_column + 1):
                    val = sheet.cell(row=1, column=col).value
                    headers.append(str(val).strip() if val is not None else f"Col{col}")
                
                # Read row records
                header_line = " | ".join(headers)
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
                    # Format as structured logical record
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
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
