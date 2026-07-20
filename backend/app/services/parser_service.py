import os
import pypdf
import docx
import openpyxl
from typing import List, Dict, Any
from app.core.logging import logger

class ParserService:
    @staticmethod
    def parse_pdf(file_path: str) -> List[Dict[str, Any]]:
        logger.info(f"Parsing PDF file: {file_path}")
        results = []
        try:
            reader = pypdf.PdfReader(file_path)
            for page_idx, page in enumerate(reader.pages):
                text = page.extract_text()
                if not text:
                    text = ""
                # Basic cleaning
                lines = [line.strip() for line in text.split("\n")]
                # Filter out empty lines
                cleaned_text = "\n".join([line for line in lines if line])
                results.append({
                    "page_number": page_idx + 1,
                    "heading": None,
                    "sheet_name": None,
                    "row_start": None,
                    "row_end": None,
                    "content": cleaned_text
                })
        except Exception as e:
            logger.error(f"Error parsing PDF {file_path}: {str(e)}")
            raise e
        return results

    @staticmethod
    def parse_docx(file_path: str) -> List[Dict[str, Any]]:
        logger.info(f"Parsing DOCX file: {file_path}")
        results = []
        try:
            doc = docx.Document(file_path)
            current_heading = "Introduction"
            
            # Simple parsing: group paragraphs under headings
            # To keep chunking working nicely, we emit paragraph contents and tag them with current_heading
            for para in doc.paragraphs:
                text = para.text.strip()
                if not text:
                    continue
                
                # Check style name for Heading
                if para.style.name.startswith("Heading") or para.style.name.startswith("heading"):
                    current_heading = text
                    # We can also emit the heading itself
                    results.append({
                        "page_number": None,
                        "heading": current_heading,
                        "sheet_name": None,
                        "row_start": None,
                        "row_end": None,
                        "content": f"# {text}"
                    })
                else:
                    results.append({
                        "page_number": None,
                        "heading": current_heading,
                        "sheet_name": None,
                        "row_start": None,
                        "row_end": None,
                        "content": text
                    })
        except Exception as e:
            logger.error(f"Error parsing DOCX {file_path}: {str(e)}")
            raise e
        return results

    @staticmethod
    def parse_xlsx(file_path: str) -> List[Dict[str, Any]]:
        logger.info(f"Parsing XLSX file: {file_path}")
        results = []
        try:
            wb = openpyxl.load_workbook(file_path, data_only=True)
            for sheet_name in wb.sheetnames:
                sheet = wb[sheet_name]
                
                # Identify headers from row 1
                headers = []
                for col in range(1, sheet.max_column + 1):
                    val = sheet.cell(row=1, column=col).value
                    headers.append(str(val).strip() if val is not None else f"Column{col}")
                
                # Read rows
                for r in range(2, sheet.max_row + 1):
                    row_vals = []
                    has_data = False
                    for col in range(1, sheet.max_column + 1):
                        val = sheet.cell(row=r, column=col).value
                        if val is not None:
                            has_data = True
                        row_vals.append(val)
                    
                    if not has_data:
                        continue
                    
                    # Convert row data into structured text format
                    row_content_lines = [
                        f"Sheet: {sheet_name}",
                        f"Row: {r}"
                    ]
                    for head, val in zip(headers, row_vals):
                        if val is not None:
                            row_content_lines.append(f"{head}: {val}")
                    
                    row_content = "\n".join(row_content_lines)
                    results.append({
                        "page_number": None,
                        "heading": None,
                        "sheet_name": sheet_name,
                        "row_start": r,
                        "row_end": r,
                        "content": row_content
                    })
        except Exception as e:
            logger.error(f"Error parsing XLSX {file_path}: {str(e)}")
            raise e
        return results

    @classmethod
    def parse(cls, file_path: str, file_type: str) -> List[Dict[str, Any]]:
        file_type = file_type.lower().strip(".")
        if file_type == "pdf":
            return cls.parse_pdf(file_path)
        elif file_type in ["docx", "doc"]:
            return cls.parse_docx(file_path)
        elif file_type in ["xlsx", "xls"]:
            return cls.parse_xlsx(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
