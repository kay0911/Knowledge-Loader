import os
import re
import datetime
import uuid
import pypdf
import docx
import openpyxl
import zipfile
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

                            # Multi-Criteria Heading Promotion Engine (Font Size, ALL CAPS, Structural Heading Patterns)
                            heading_pattern = re.compile(
                                r"^(vụ việc:|mục\s+\d+|điều\s+\d+|chương\s+\d+|phần\s+\d+|báo cáo:|quy định:|quyết định:|hướng dẫn:|\d+\.|\d+\.\d+|[A-Z]\.|\b[I|V|X]+\.)\b",
                                re.IGNORECASE
                            )
                            is_all_caps = line_text.isupper() and 3 < len(line_text) < 120
                            is_title_pattern = bool(heading_pattern.search(line_text)) and len(line_text) < 120

                            if avg_size >= base_size * 1.35 or is_all_caps:
                                md_lines.append(f"# {line_text}")
                            elif avg_size >= base_size * 1.15 or is_bold or is_title_pattern:
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
        logger.info(f"Parsing DOCX file with Table & Image extraction: {file_path}")
        blocks: List[NormalizedBlock] = []
        try:
            doc = docx.Document(file_path)
            source_order = 0
            current_heading_path = ["Tổng quan"]

            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "storage", "extracted_images"))
            os.makedirs(base_dir, exist_ok=True)
            doc_basename = os.path.splitext(os.path.basename(file_path))[0]
            image_counter = 0

            # Iterate over elements in body sequentially (paragraphs and tables)
            for element in doc.element.body:
            # Handle Paragraph
                if element.tag.endswith('p'):
                    para = docx.text.paragraph.Paragraph(element, doc)
                    text = para.text.strip()
                    
                    # 1. Check for embedded images in this paragraph
                    para_img_tags = []
                    blips = element.xpath('.//a:blip')
                    for blip in blips:
                        embed_id = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                        if embed_id and embed_id in doc.part.rels:
                            rel_part = doc.part.rels[embed_id].target_part
                            if "image" in rel_part.content_type:
                                image_counter += 1
                                ext = rel_part.content_type.split("/")[-1]
                                if ext not in ["png", "jpeg", "jpg", "gif"]:
                                    ext = "png"
                                img_filename = f"{doc_basename}_img_{image_counter}.{ext}"
                                img_full_path = os.path.join(base_dir, img_filename)
                                
                                with open(img_full_path, "wb") as f:
                                    f.write(rel_part.blob)
                                
                                relative_img_path = f"storage/extracted_images/{img_filename}"
                                img_tag = f"<img src='{relative_img_path}' alt='Embedded Image {image_counter} in {doc_basename}' />"
                                para_img_tags.append(img_tag)
                                
                                # Also emit dedicated image block for VLM / LLM Summarization
                                source_order += 1
                                blocks.append(NormalizedBlock(
                                    block_id=str(uuid.uuid4()),
                                    source_type="docx",
                                    block_type="image",
                                    content=img_tag,
                                    image_path=img_full_path,
                                    requires_llm_summary=True,
                                    heading_path=list(current_heading_path),
                                    source_order=source_order
                                ))

                    # Insert inline image tags into text paragraph for contextual linkage
                    if para_img_tags:
                        img_combined_tag = "\n\n" + "\n\n".join(para_img_tags)
                        text = (text + img_combined_tag).strip() if text else img_combined_tag.strip()

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

                # Handle Table (Markdown Pipe Table format for token optimization)
                elif element.tag.endswith('tbl'):
                    table = docx.table.Table(element, doc)
                    table_rows = []
                    for row in table.rows:
                        row_vals = [cell.text.strip().replace('\n', ' ').replace('|', '\\|') for cell in row.cells]
                        if any(row_vals):
                            table_rows.append(row_vals)

                    if table_rows:
                        headers = table_rows[0]
                        data_rows = table_rows[1:]
                        
                        # Build Markdown Pipe header & divider
                        header_line = "| " + " | ".join(headers) + " |\n"
                        divider_line = "| " + " | ".join(["---"] * len(headers)) + " |\n"
                        header_md = header_line + divider_line

                        # Batch data rows into sub-tables (~15-20 rows or ~1000 chars per sub-table block)
                        curr_rows_md = []
                        curr_char_len = len(header_md)

                        for r_cols in data_rows:
                            row_line = "| " + " | ".join(r_cols) + " |\n"
                            row_len = len(row_line)

                            if curr_char_len + row_len >= 1000 or len(curr_rows_md) >= 20:
                                source_order += 1
                                sub_table_md = header_md + "".join(curr_rows_md)
                                blocks.append(NormalizedBlock(
                                    block_id=str(uuid.uuid4()),
                                    source_type="docx",
                                    block_type="table",
                                    content=sub_table_md.strip(),
                                    requires_llm_summary=True,
                                    heading_path=list(current_heading_path),
                                    source_order=source_order
                                ))
                                curr_rows_md = [row_line]
                                curr_char_len = len(header_md) + row_len
                            else:
                                curr_rows_md.append(row_line)
                                curr_char_len += row_len

                        # Flush remaining table rows batch
                        if curr_rows_md or not data_rows:
                            source_order += 1
                            sub_table_md = header_md + "".join(curr_rows_md)
                            blocks.append(NormalizedBlock(
                                block_id=str(uuid.uuid4()),
                                source_type="docx",
                                block_type="table",
                                content=sub_table_md.strip(),
                                requires_llm_summary=True,
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
        doc_basename = os.path.splitext(os.path.basename(file_path))[0]
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../storage/extracted_images"))
        os.makedirs(base_dir, exist_ok=True)
        source_order = 0

        # Step 1: Pre-map embedded images to exact Sheet & Row anchors using openpyxl drawings
        sheet_images_by_row: Dict[str, Dict[int, List[Dict[str, Any]]]] = {}
        try:
            wb_draw = openpyxl.load_workbook(file_path, data_only=True)
            for s_name in wb_draw.sheetnames:
                ws = wb_draw[s_name]
                images = getattr(ws, "_images", [])
                sheet_images_by_row[s_name] = {}
                for idx, img in enumerate(images, start=1):
                    anchor_cell = getattr(img.anchor, "_from", None)
                    r_idx = anchor_cell.row + 1 if anchor_cell else 1
                    ext = getattr(img, 'format', 'png').lower()
                    if ext not in ["png", "jpeg", "jpg", "gif"]:
                        ext = "png"
                    img_filename = f"{doc_basename}_{s_name}_img_{idx}.{ext}"
                    img_full_path = os.path.join(base_dir, img_filename)
                    try:
                        img_bytes = img._data()
                        with open(img_full_path, "wb") as f_img:
                            f_img.write(img_bytes)
                        rel_path = f"storage/extracted_images/{img_filename}"
                        if r_idx not in sheet_images_by_row[s_name]:
                            sheet_images_by_row[s_name][r_idx] = []
                        sheet_images_by_row[s_name][r_idx].append({
                            "rel_path": rel_path,
                            "full_path": img_full_path,
                            "alt": f"Embedded Image {idx} in Sheet {s_name}"
                        })
                    except Exception as e_save:
                        logger.warning(f"Could not save XLSX image: {e_save}")
        except Exception as draw_err:
            logger.warning(f"Fallback: openpyxl drawing inspection failed for {file_path}: {draw_err}")

        try:
            wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)

            for sheet_name in wb.sheetnames:
                sheet = wb[sheet_name]
                
                # Skip hidden sheets (sheets hidden by users in MS Excel UI)
                if hasattr(sheet, 'sheet_state') and sheet.sheet_state and sheet.sheet_state != 'visible':
                    logger.info(f"Skipping hidden sheet '{sheet_name}' in XLSX file: {file_path}")
                    continue

                curr_sheet_imgs = sheet_images_by_row.get(sheet_name, {})
                
                rows_list = list(sheet.iter_rows(values_only=True))
                if not rows_list:
                    continue

                headers = []
                best_header_row_idx = 0
                max_cols_count = 0
                
                # Scan top 15 rows to find the row with MAXIMUM populated non-empty columns (True Header)
                try:
                    for r_idx, r in enumerate(rows_list[:15]):
                        if not r:
                            continue
                        non_empty_cols = [i for i, c in enumerate(r) if c is not None and str(c).strip()]
                        if len(non_empty_cols) > max_cols_count:
                            max_cols_count = len(non_empty_cols)
                            best_header_row_idx = r_idx
                            last_col = max(non_empty_cols) + 1
                            max_col_idx = min(last_col, 35) # Cap at 35 columns max
                            headers = [str(r[i]).strip().replace('\n', ' ').replace('|', '\\|') if i < len(r) and r[i] is not None else f"Col{i+1}" for i in range(max_col_idx)]
                except Exception as h_err:
                    logger.warning(f"Error finding table header in sheet '{sheet_name}': {h_err}")
                    continue

                # Detect if this sheet is a Timeline / Action Plan sheet (>15 cols & 8+ date/week headers present)
                is_timeline_sheet = False
                month_headers = {}
                timeline_col_map = {}
                core_headers = []

                if max_cols_count >= 15:
                    # Scan row 3 for month group headers
                    current_month = ""
                    row3 = rows_list[2] if len(rows_list) > 2 else []
                    for idx_c, val_c in enumerate(row3):
                        if val_c is not None and str(val_c).strip():
                            val_str = str(val_c).strip()
                            if re.search(r'T\d{1,2}/\d{4}', val_str, re.IGNORECASE):
                                current_month = val_str
                        month_headers[idx_c] = current_month

                    # Scan header row for date/week columns
                    header_row_vals = rows_list[best_header_row_idx]
                    date_col_count = 0
                    for idx_c, val_c in enumerate(header_row_vals):
                        val_str = str(val_c).strip() if val_c is not None else ""
                        is_date_col = False
                        date_formatted = None

                        if isinstance(val_c, (datetime.datetime, datetime.date)):
                            is_date_col = True
                            date_formatted = val_c.strftime("%d/%m/%Y")
                        elif re.search(r'\d{4}-\d{2}-\d{2}', val_str) or re.search(r'\d{2}/\d{2}/\d{4}', val_str) or re.match(r'W\d{1,2}', val_str, re.IGNORECASE):
                            is_date_col = True
                            date_formatted = val_str.split(" ")[0]
                        elif idx_c >= 4 and re.match(r'^\d{1,2}$', val_str) and 1 <= int(val_str) <= 53:
                            is_date_col = True
                            date_formatted = f"Tuần {val_str}"

                        if is_date_col and idx_c >= 4:
                            date_col_count += 1
                            m_str = month_headers.get(idx_c, "")
                            timeline_col_map[idx_c] = {
                                "col_name": date_formatted or val_str or f"W{idx_c+1}",
                                "month": m_str
                            }
                        elif idx_c < 6:
                            core_headers.append((idx_c, val_str))

                    if date_col_count >= 8 and len(core_headers) >= 2:
                        is_timeline_sheet = True

                # ==================================================
                # MODE A: TIMELINE AGGREGATION MODE (For Task Plans)
                # ==================================================
                if is_timeline_sheet:
                    logger.info(f"Timeline Action Plan sheet detected in '{sheet_name}'. Activating Timeline Aggregation Engine.")
                    
                    # Dynamically map column positions from header row
                    col_map_idx = {}
                    header_row_tuple = rows_list[best_header_row_idx]
                    
                    # Find first populated column index in sample data rows
                    first_col_idx = 0
                    for r_sample in rows_list[best_header_row_idx+1:best_header_row_idx+10]:
                        if not r_sample:
                            continue
                        non_empty_indices = [i_c for i_c, v_c in enumerate(r_sample) if v_c is not None and str(v_c).strip()]
                        if non_empty_indices:
                            first_col_idx = min(non_empty_indices)
                            break

                    for c_idx, c_val in enumerate(header_row_tuple):
                        if c_val is None:
                            continue
                        c_lower = str(c_val).strip().lower()
                        if any(k in c_lower for k in ["stt", "no.", "no"]) and c_idx < 5 and "stt" not in col_map_idx:
                            col_map_idx["stt"] = c_idx
                        elif any(k in c_lower for k in ["hạng mục", "công việc", "task title", "task", "phase", "description", "title"]):
                            if "task_name" not in col_map_idx:
                                col_map_idx["task_name"] = c_idx
                        elif any(k in c_lower for k in ["pic", "owner", "task owner", "người làm", "phụ trách"]):
                            if "pic" not in col_map_idx:
                                col_map_idx["pic"] = c_idx
                        elif any(k in c_lower for k in ["ưu tiên", "priority"]):
                            if "priority" not in col_map_idx:
                                col_map_idx["priority"] = c_idx
                        elif any(k in c_lower for k in ["trạng thái", "status"]):
                            if "status" not in col_map_idx:
                                col_map_idx["status"] = c_idx
                        elif any(k in c_lower for k in ["tiến độ", "pct", "%", "complete"]):
                            if "progress" not in col_map_idx:
                                col_map_idx["progress"] = c_idx

                    # Smart fallback for STT & Task Name if not explicitly matched by header keywords
                    if "stt" not in col_map_idx:
                        col_map_idx["stt"] = first_col_idx

                    if "task_name" not in col_map_idx:
                        pic_idx = col_map_idx.get("pic", -1)
                        stt_idx = col_map_idx.get("stt", -1)
                        possible_task_cols = [c for c in range(first_col_idx, min(first_col_idx + 6, max_cols_count)) if c != pic_idx and c != stt_idx]
                        
                        col_total_vol = {}
                        for c_cand in possible_task_cols:
                            lens = [len(str(r[c_cand]).strip()) for r in rows_list[best_header_row_idx+1:best_header_row_idx+35] if c_cand < len(r) and r[c_cand] is not None and str(r[c_cand]).strip()]
                            col_total_vol[c_cand] = sum(lens)
                            
                        best_cand = max(col_total_vol.items(), key=lambda x: x[1])[0] if col_total_vol else first_col_idx + 1
                        col_map_idx["task_name"] = best_cand

                    # Default fallback indexes
                    idx_stt = col_map_idx["stt"]
                    idx_task = col_map_idx["task_name"]
                    idx_pic = col_map_idx.get("pic", None)
                    idx_prio = col_map_idx.get("priority", None)
                    idx_stat = col_map_idx.get("status", None)
                    idx_prog = col_map_idx.get("progress", None)

                    # Also inspect cell fills from openpyxl sheet object for colored Gantt bars
                    try:
                        ws_openpyxl = wb_draw[sheet_name]
                        ws_openpyxl_rows = list(ws_openpyxl.iter_rows())
                    except Exception:
                        ws_openpyxl_rows = []

                    timeline_records = []
                    raw_row_index = best_header_row_idx + 1

                    for row_i, row in enumerate(rows_list[best_header_row_idx + 1:], start=best_header_row_idx + 1):
                        raw_row_index += 1
                        if not row:
                            continue

                        stt = str(row[idx_stt]).strip() if idx_stt is not None and idx_stt < len(row) and row[idx_stt] is not None else ""
                        task_name = str(row[idx_task]).strip() if idx_task is not None and idx_task < len(row) and row[idx_task] is not None else ""
                        if not task_name and idx_task is not None and (idx_task + 1) < len(row) and row[idx_task + 1] is not None:
                            task_name = str(row[idx_task + 1]).strip()
                        pic = str(row[idx_pic]).strip() if idx_pic is not None and idx_pic < len(row) and row[idx_pic] is not None else "Unassigned"
                        priority = str(row[idx_prio]).strip() if idx_prio is not None and idx_prio < len(row) and row[idx_prio] is not None else "Normal"
                        status = str(row[idx_stat]).strip() if idx_stat is not None and idx_stat < len(row) and row[idx_stat] is not None else "Pending"
                        progress = str(row[idx_prog]).strip() if idx_prog is not None and idx_prog < len(row) and row[idx_prog] is not None else ""

                        if not task_name or task_name.lower() in ["stt", "no.", "task title", "hạng mục / công việc"]:
                            continue

                        if progress:
                            try:
                                p_val = float(progress)
                                progress_str = f"{int(p_val * 100)}%" if p_val <= 1.0 else f"{progress}%"
                            except ValueError:
                                progress_str = progress
                        else:
                            progress_str = "0%"

                        # Inspect cell values AND cell fill colors for active timeline markers
                        active_cols = []
                        cell_objects = ws_openpyxl_rows[row_i] if row_i < len(ws_openpyxl_rows) else []

                        for c_idx, t_info in timeline_col_map.items():
                            is_active = False
                            if c_idx < len(row) and row[c_idx] is not None and str(row[c_idx]).strip():
                                c_val = str(row[c_idx]).strip().lower()
                                if c_val in ["x", "1", "true", "yes", "done"] or len(c_val) > 0:
                                    is_active = True
                            
                            # Check cell fill color if value check didn't trigger
                            if not is_active and c_idx < len(cell_objects):
                                cell_obj = cell_objects[c_idx]
                                if cell_obj.fill and cell_obj.fill.start_color and cell_obj.fill.start_color.rgb:
                                    rgb = str(cell_obj.fill.start_color.rgb)
                                    # Ignore white, black, grey background fills
                                    if rgb not in ["00000000", "FFFFFFFF", "FFCCCCCC", "00FFFFFF"]:
                                        is_active = True

                            if is_active:
                                active_cols.append((c_idx, t_info))

                        if active_cols:
                            start_date = active_cols[0][1]["col_name"]
                            end_date = active_cols[-1][1]["col_name"]
                            start_month = active_cols[0][1]["month"]
                            end_month = active_cols[-1][1]["month"]

                            month_range_str = f"({start_month})" if start_month == end_month else f"({start_month} – {end_month})" if (start_month or end_month) else ""
                            timeline_summary = f"{start_date} – {end_date} {month_range_str}".strip() if start_date != end_date else f"{start_date} {month_range_str}".strip()
                        else:
                            timeline_summary = "Chưa xếp lịch"

                        rec_md = f"- **[{stt}] {task_name}**\n" \
                                 f"  • **PIC:** {pic} | **Ưu tiên:** {priority} | **Trạng thái:** {status} | **Tiến độ:** {progress_str}\n" \
                                 f"  • **Thời gian thực hiện:** {timeline_summary}"
                        timeline_records.append(rec_md)

                    # Group timeline task records into chunks
                    t_buffer = []
                    t_len = 0
                    for rec in timeline_records:
                        if t_len + len(rec) > 1150 and t_buffer:
                            source_order += 1
                            blocks.append(NormalizedBlock(
                                block_id=str(uuid.uuid4()),
                                source_type="xlsx",
                                block_type="paragraph",
                                content=f"### {sheet_name} (Kế hoạch hành động)\n\n" + "\n\n".join(t_buffer),
                                heading_path=[f"Sheet: {sheet_name}"],
                                source_order=source_order
                            ))
                            t_buffer = []
                            t_len = 0

                        t_buffer.append(rec)
                        t_len += len(rec)

                    if t_buffer:
                        source_order += 1
                        blocks.append(NormalizedBlock(
                            block_id=str(uuid.uuid4()),
                            source_type="xlsx",
                            block_type="paragraph",
                            content=f"### {sheet_name} (Kế hoạch hành động)\n\n" + "\n\n".join(t_buffer),
                            heading_path=[f"Sheet: {sheet_name}"],
                            source_order=source_order
                        ))
                    continue

                # ==================================================
                # MODE B: STANDARD MARKDOWN PIPE TABLE MODE
                # ==================================================
                header_line = "| " + " | ".join(headers) + " |\n"
                divider_line = "| " + " | ".join(["---"] * len(headers)) + " |\n"
                header_md = f"Sheet: {sheet_name}\n\n" + header_line + divider_line

                batch_rows = []
                batch_start_row = 1
                current_char_count = len(header_md)
                data_rows_count = 0     # Count POPULATED DATA ROWS ONLY
                total_sheet_chars = 0   # Total accumulated char length for this sheet
                sheet_blocks = []       # Temporary blocks list for this sheet
                is_large_sheet = False  # Flag for sheets > 200 rows OR > 20,000 chars
                raw_row_index = best_header_row_idx + 1

                for row in rows_list[best_header_row_idx + 1:]:
                    raw_row_index += 1

                    # Interleave Images anchored at this exact row sequentially!
                    if raw_row_index in curr_sheet_imgs:
                        for img_info in curr_sheet_imgs[raw_row_index]:
                            img_tag = f"<img src='{img_info['rel_path']}' alt='{img_info['alt']}' />"
                            source_order += 1
                            sheet_blocks.append(NormalizedBlock(
                                block_id=str(uuid.uuid4()),
                                source_type="xlsx",
                                block_type="image",
                                content=img_tag,
                                image_path=img_info['full_path'],
                                requires_llm_summary=True,
                                heading_path=[f"Sheet: {sheet_name}"],
                                source_order=source_order
                            ))

                    # Skip completely blank rows
                    if not any(c is not None and str(c).strip() for c in row[:len(headers)]):
                        continue

                    row_vals = [str(row[i]).strip().replace('\n', ' ').replace('|', '\\|') if i < len(row) and row[i] is not None else "" for i in range(len(headers))]
                    row_line = "| " + " | ".join(row_vals) + " |\n"
                    row_len = len(row_line)

                    data_rows_count += 1
                    total_sheet_chars += row_len

                    # Rule: If sheet exceeds 200 populated rows OR 20,000 total chars (Exhaustive Listing):
                    # Flag as large sheet and STOP streaming immediately!
                    if data_rows_count > 200 or total_sheet_chars > 20000:
                        logger.warning(f"Sheet '{sheet_name}' in {os.path.basename(file_path)} exceeds 200 rows / 20K chars (Exhaustive Listing). Filtering to keep 1ST SINGLE CHUNK ONLY.")
                        is_large_sheet = True
                        break

                    if current_char_count + row_len >= 1150 or len(batch_rows) >= 20:
                        source_order += 1
                        table_content = header_md + "".join(batch_rows)
                        sheet_blocks.append(NormalizedBlock(
                            block_id=str(uuid.uuid4()),
                            source_type="xlsx",
                            block_type="table",
                            content=table_content.strip(),
                            heading_path=[f"Sheet: {sheet_name}"],
                            sheet_name=sheet_name,
                            row_start=batch_start_row,
                            row_end=data_rows_count,
                            table_id=f"sheet_{sheet_name}",
                            requires_llm_summary=False,
                            source_order=source_order
                        ))
                        batch_rows = [row_line]
                        batch_start_row = data_rows_count
                        current_char_count = len(header_md) + row_len
                    else:
                        batch_rows.append(row_line)
                        current_char_count += row_len

                # Flush remaining batch if normal sheet
                if batch_rows and not is_large_sheet:
                    source_order += 1
                    table_content = header_md + "".join(batch_rows)
                    sheet_blocks.append(NormalizedBlock(
                        block_id=str(uuid.uuid4()),
                        source_type="xlsx",
                        block_type="table",
                        content=table_content.strip(),
                        heading_path=[f"Sheet: {sheet_name}"],
                        sheet_name=sheet_name,
                        row_start=batch_start_row,
                        row_end=data_rows_count,
                        table_id=f"sheet_{sheet_name}",
                        requires_llm_summary=False,
                        source_order=source_order
                    ))

                # IF LARGE SHEET (> 200 ROWS OR > 20,000 CHARS): KEEP ONLY THE FIRST CHUNK!
                if is_large_sheet:
                    if sheet_blocks:
                        blocks.append(sheet_blocks[0])
                    elif batch_rows:
                        source_order += 1
                        table_content = header_md + "".join(batch_rows)
                        blocks.append(NormalizedBlock(
                            block_id=str(uuid.uuid4()),
                            source_type="xlsx",
                            block_type="table",
                            content=table_content.strip(),
                            heading_path=[f"Sheet: {sheet_name}"],
                            sheet_name=sheet_name,
                            row_start=1,
                            row_end=len(batch_rows),
                            table_id=f"sheet_{sheet_name}",
                            requires_llm_summary=False,
                            source_order=source_order
                        ))
                else:
                    blocks.extend(sheet_blocks)

        except Exception as e:
            logger.error(f"Error parsing XLSX {file_path}: {str(e)}")
            raise e

        return blocks

    @classmethod
    def parse_pptx(cls, file_path: str) -> List[NormalizedBlock]:
        logger.info(f"Parsing PPTX file: {file_path}")
        blocks: List[NormalizedBlock] = []
        try:
            from pptx import Presentation
            prs = Presentation(file_path)
            source_order = 0

            for slide_idx, slide in enumerate(prs.slides):
                slide_num = slide_idx + 1
                slide_title = f"Slide {slide_num}"
                
                # Try to extract slide title shape
                if slide.shapes.title and slide.shapes.title.text:
                    slide_title = f"Slide {slide_num}: {slide.shapes.title.text.strip()}"

                slide_texts = []
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        for paragraph in shape.text_frame.paragraphs:
                            txt = paragraph.text.strip()
                            if txt and txt != slide.shapes.title.text.strip() if slide.shapes.title else True:
                                slide_texts.append(txt)

                if slide_texts:
                    source_order += 1
                    content = "\n".join(slide_texts)
                    blocks.append(NormalizedBlock(
                        block_id=str(uuid.uuid4()),
                        source_type="pptx",
                        block_type="paragraph",
                        content=f"{slide_title}\n\n{content}",
                        heading_path=[slide_title],
                        page_start=slide_num,
                        page_end=slide_num,
                        source_order=source_order
                    ))

        except Exception as e:
            logger.error(f"Error parsing PPTX {file_path}: {str(e)}")
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
        elif file_type in ["pptx", "ppt"]:
            return cls.parse_pptx(file_path)
        elif file_type in ["md", "markdown"]:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return cls.parse_markdown_content(content, source_type="md")
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
