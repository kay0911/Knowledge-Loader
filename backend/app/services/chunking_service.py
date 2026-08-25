import re
from typing import List, Dict, Any, Optional
from app.schemas.normalized_block import NormalizedBlock
from app.core.logging import logger

class ChunkingService:
    # Character budget parameters corresponding to ~300 Token target & ~400 Token max ceiling
    # (Ratio: 1 token ≈ 3.8 chars in mixed Vietnamese/English text)
    TARGET_CHARS = 1150   # ~300 tokens target
    MAX_CHARS = 1500      # ~400 tokens max ceiling
    OVERLAP_CHARS = 120   # ~30 tokens overlap
    MIN_MERGE_CHARS = 300 # ~80 tokens minimum merge threshold

    @classmethod
    def chunk_normalized_blocks(cls, blocks: List[NormalizedBlock]) -> List[Dict[str, Any]]:
        """
        Main entrypoint: Accepts a list of NormalizedBlock objects and returns chunk dictionaries
        ready for PostgreSQL DocumentChunk insertion.
        """
        if not blocks:
            return []

        prose_buffer: List[NormalizedBlock] = []
        raw_chunks: List[Dict[str, Any]] = []

        for block in blocks:
            if block.block_type == "table":
                if prose_buffer:
                    raw_chunks.extend(cls._chunk_prose_blocks(prose_buffer))
                    prose_buffer = []
                raw_chunks.extend(cls._chunk_table_block(block))
            else:
                prose_buffer.append(block)

        if prose_buffer:
            raw_chunks.extend(cls._chunk_prose_blocks(prose_buffer))

        chunks = raw_chunks

        # Post-merge pass: combine short adjacent prose/image chunks up to MAX_CHARS (1500 chars / ~400 tokens) & max 3 images
        merged_chunks: List[Dict[str, Any]] = []
        for c in chunks:
            if not merged_chunks:
                merged_chunks.append(c)
                continue
            
            prev = merged_chunks[-1]
            prev_len = len(prev["content"])
            curr_len = len(c["content"])

            # Extract image paths in prev and c
            prev_imgs = prev.get("image_path", [])
            if isinstance(prev_imgs, str):
                prev_imgs = [prev_imgs]
            curr_imgs = c.get("image_path", [])
            if isinstance(curr_imgs, str):
                curr_imgs = [curr_imgs]
            
            combined_imgs = list(dict.fromkeys([img for img in (prev_imgs or []) + (curr_imgs or []) if img]))

            # Merge adjacent chunks (text, table, image) if combined size fits in TARGET_CHARS and max 3 images cap
            if len(combined_imgs) <= 3 and ((prev_len + curr_len <= cls.TARGET_CHARS) or (prev_len < cls.MIN_MERGE_CHARS and prev_len + curr_len <= cls.MAX_CHARS)):
                prev["content"] = prev["content"] + "\n\n" + c["content"]
                if c.get("heading") and not prev.get("heading"):
                    prev["heading"] = c.get("heading")
                    prev["heading_path"] = c.get("heading_path")
                if c.get("has_table"):
                    prev["has_table"] = True
                if combined_imgs:
                    prev["has_image"] = True
                    prev["image_path"] = combined_imgs
                    prev["block_type"] = "image"
                prev["requires_llm_summary"] = prev.get("has_image", False) or prev.get("has_table", False)
                if c.get("page_end"):
                    prev["page_end"] = c.get("page_end")
                continue

            merged_chunks.append(c)

        # Re-assign sequential chunk order and compute character & estimated token counts
        for idx, c in enumerate(merged_chunks):
            c["chunk_order"] = idx + 1
            content_str = c.get("content", "")
            c["char_count"] = len(content_str)
            c["estimated_tokens"] = round(len(content_str) / 3.8)

        logger.info(f"Chunking complete. Produced {len(merged_chunks)} chunks from {len(blocks)} normalized blocks.")
        return merged_chunks

    @classmethod
    def _chunk_prose_blocks(cls, blocks: List[NormalizedBlock]) -> List[Dict[str, Any]]:
        """
        Recursive Chunker for Prose, Headings, Lists, Code, and Inline Images.
        Streams text and inline <img /> tags continuously into unified chunks (max 3 images per chunk).
        """
        chunks: List[Dict[str, Any]] = []
        
        current_content_parts: List[str] = []
        current_len = 0
        current_heading_path: List[str] = []
        active_chunk_heading_path: List[str] = []
        current_page_start: Optional[int] = None
        current_page_end: Optional[int] = None

        def flush_chunk(is_section_boundary: bool = False):
            nonlocal current_content_parts, current_len, active_chunk_heading_path, current_heading_path, current_page_start, current_page_end
            if not current_content_parts:
                return

            full_text = "\n\n".join(current_content_parts).strip()
            # Clean out decorative divider lines (e.g. ---, ***, --------...)
            full_text = re.sub(r"(\n[\s\-\*_]{3,}\n|\n[\s\-\*_]{3,}$|^[\s\-\*_]{3,}\n)", "\n", full_text).strip()
            if not full_text:
                return

            # Use active_chunk_heading_path (anchored to the content in this chunk)
            effective_heading_path = list(active_chunk_heading_path) if active_chunk_heading_path else list(current_heading_path)
            heading_title = effective_heading_path[-1] if effective_heading_path else None

            contains_table = "<table>" in full_text or "<table " in full_text or "| --- |" in full_text or ("| " in full_text and " |\n|" in full_text)
            
            # Extract image paths embedded in <img src='...' />
            img_matches = re.findall(r"<img\s+src=['\"]([^'\"]+)['\"]", full_text)
            image_paths = list(dict.fromkeys(img_matches))
            contains_image = len(image_paths) > 0

            b_type = "table" if contains_table else ("image" if contains_image else "text")
            req_summary = contains_table or contains_image

            chunk_dict = {
                "block_type": b_type,
                "has_table": contains_table,
                "has_image": contains_image,
                "requires_llm_summary": req_summary,
                "content": full_text,
                "heading": heading_title,
                "heading_path": effective_heading_path,
                "page_number": current_page_start,
                "page_start": current_page_start,
                "page_end": current_page_end,
                "sheet_name": None,
                "row_start": None,
                "row_end": None
            }
            if contains_image:
                chunk_dict["image_path"] = image_paths

            # If full_text exceeds MAX_CHARS, split recursively
            if len(full_text) > cls.MAX_CHARS:
                sub_texts = cls._recursive_split_text(full_text, cls.MAX_CHARS, cls.OVERLAP_CHARS)
                for sub in sub_texts:
                    sub_table = "<table>" in sub or "<table " in sub or "| --- |" in sub or ("| " in sub and " |\n|" in sub)
                    sub_img_matches = re.findall(r"<img\s+src=['\"]([^'\"]+)['\"]", sub)
                    sub_image_paths = list(dict.fromkeys(sub_img_matches))
                    sub_image = len(sub_image_paths) > 0
                    sub_type = "table" if sub_table else ("image" if sub_image else "text")
                    sub_req = sub_table or sub_image

                    sub_chunk = {
                        "block_type": sub_type,
                        "has_table": sub_table,
                        "has_image": sub_image,
                        "requires_llm_summary": sub_req,
                        "content": sub,
                        "heading": heading_title,
                        "heading_path": effective_heading_path,
                        "page_number": current_page_start,
                        "page_start": current_page_start,
                        "page_end": current_page_end,
                        "sheet_name": None,
                        "row_start": None,
                        "row_end": None
                    }
                    if sub_image:
                        sub_chunk["image_path"] = sub_image_paths
                    chunks.append(sub_chunk)
            else:
                chunks.append(chunk_dict)

            # Overlap handling: If section boundary, DO NOT overlap bleeding from previous section!
            if is_section_boundary:
                current_content_parts = []
                current_len = 0
                active_chunk_heading_path = []
                current_page_start = None
                current_page_end = None
            else:
                overlap_parts = []
                overlap_size = 0
                for part in reversed(current_content_parts):
                    if overlap_size + len(part) <= cls.OVERLAP_CHARS:
                        overlap_parts.insert(0, part)
                        overlap_size += len(part)
                    else:
                        break

                current_content_parts = overlap_parts
                current_len = sum(len(p) for p in current_content_parts)
                if not current_content_parts:
                    active_chunk_heading_path = []
                    current_page_start = None
                    current_page_end = None

        item_pattern = re.compile(r"^(vụ việc:|mục\s+\d+|điều\s+\d+|chương\s+\d+|phần\s+\d+)\b", re.IGNORECASE)

        for block in blocks:
            text = block.content.strip()
            if not text:
                continue

            # Check image count in current buffer + candidate block
            block_imgs = re.findall(r"<img\s+src=['\"]([^'\"]+)['\"]", text)
            curr_imgs = re.findall(r"<img\s+src=['\"]([^'\"]+)['\"]", "".join(current_content_parts))
            total_img_count = len(list(dict.fromkeys(curr_imgs + block_imgs)))

            is_new_section_title = block.block_type == "heading" or (item_pattern.search(text) and not any(p.startswith(text[:15]) for p in current_content_parts))

            if is_new_section_title and current_len >= cls.MIN_MERGE_CHARS:
                flush_chunk(is_section_boundary=True)

            if block.heading_path:
                current_heading_path = list(block.heading_path)
                if not active_chunk_heading_path:
                    active_chunk_heading_path = list(block.heading_path)

            if block.page_start is not None:
                if current_page_start is None:
                    current_page_start = block.page_start
            text_len = len(text)

            # Flush if adding this block exceeds 3 images cap OR TARGET_CHARS
            if (total_img_count > 3 and len(curr_imgs) > 0) or (current_len + text_len > cls.TARGET_CHARS):
                if current_len >= cls.MIN_MERGE_CHARS or total_img_count > 3:
                    flush_chunk(is_section_boundary=False)
                    if not active_chunk_heading_path and block.heading_path:
                        active_chunk_heading_path = list(block.heading_path)

            if current_len + text_len <= cls.TARGET_CHARS:
                current_content_parts.append(text)
                current_len += text_len
            else:
                # If adding this block exceeds target, check if current buffer meets MIN_MERGE_CHARS
                if current_len >= cls.MIN_MERGE_CHARS:
                    flush_chunk()
                    active_chunk_heading_path = list(current_heading_path)
                    current_content_parts.append(text)
                    current_len = sum(len(p) for p in current_content_parts)
                    if block.page_start is not None:
                        current_page_start = block.page_start
                    if block.page_end is not None:
                        current_page_end = block.page_end
                else:
                    # Still small, append up to MAX_CHARS
                    if current_len + text_len <= cls.MAX_CHARS:
                        current_content_parts.append(text)
                        current_len += text_len
                    else:
                        flush_chunk()
                        active_chunk_heading_path = list(current_heading_path)
                        current_content_parts.append(text)
                        current_len = len(text)
                        if block.page_start is not None:
                            current_page_start = block.page_start
                        if block.page_end is not None:
                            current_page_end = block.page_end

        if current_content_parts:
            flush_chunk()

        return chunks

    @classmethod
    def _chunk_table_block(cls, block: NormalizedBlock) -> List[Dict[str, Any]]:
        """
        Table Chunker with Header Enrichment and Character Budget Packing for Markdown/XLSX/CSV Tables.
        Preserves Table Header (| col1 | col2 |... and | --- | --- |) at the top of EVERY split table chunk!
        """
        chunks: List[Dict[str, Any]] = []
        raw_content = block.content.strip()
        lines = [l.strip() for l in raw_content.split("\n") if l.strip()]
        if not lines:
            return []

        sheet_prefix = f"Sheet: {block.sheet_name}\n" if block.sheet_name else ""

        # Detect Markdown Table Header (First 1-2 lines matching | ... |)
        header_lines: List[str] = []
        data_lines: List[str] = []

        if lines[0].startswith("|") and len(lines) > 1 and "|-" in lines[1].replace(" ", ""):
            header_lines = [lines[0], lines[1]]
            data_lines = lines[2:]
        elif lines[0].startswith("#") and len(lines) > 2 and lines[1].startswith("|") and "|-" in lines[2].replace(" ", ""):
            header_lines = [lines[0], lines[1], lines[2]]
            data_lines = lines[3:]
        else:
            data_lines = lines

        header_prefix = sheet_prefix + ("\n".join(header_lines) + "\n" if header_lines else "")
        header_len = len(header_prefix)

        current_records: List[str] = []
        current_len = header_len

        def flush_table_chunk():
            nonlocal current_records, current_len
            if not current_records:
                return

            table_text = (header_prefix + "\n".join(current_records)).strip()
            heading_val = block.heading_path[-1] if block.heading_path else (block.sheet_name or "Bảng dữ liệu")

            chunks.append({
                "block_type": "table",
                "has_table": True,
                "has_image": False,
                "requires_llm_summary": True,
                "content": table_text,
                "heading": heading_val,
                "heading_path": block.heading_path or [],
                "page_number": block.page_start,
                "page_start": block.page_start,
                "page_end": block.page_end,
                "sheet_name": block.sheet_name,
                "row_start": block.row_start,
                "row_end": block.row_end
            })

            current_records = []
            current_len = header_len

        for line in data_lines:
            line_len = len(line) + 1
            is_notice_line = line.startswith("*(Lưu ý:") or line.startswith("*(Notice:")
            if is_notice_line or current_len + line_len <= cls.TARGET_CHARS:
                current_records.append(line)
                current_len += line_len
            elif current_len + line_len <= cls.MAX_CHARS:
                current_records.append(line)
                current_len += line_len
                flush_table_chunk()
            else:
                flush_table_chunk()
                current_records.append(line)
                current_len += line_len

        if current_records:
            flush_table_chunk()

        return chunks

    @classmethod
    def _recursive_split_text(cls, text: str, max_chars: int, overlap: int) -> List[str]:
        """
        Helper to recursively split long text using natural separators:
        Heading -> Paragraph -> Line -> Sentence -> Word -> Char.
        """
        text = text.strip()
        if not text or len(text) <= max_chars:
            return [text] if text else []

        separators = ["\n\n", "\n", ". ", "; ", ", ", " "]
        
        for sep in separators:
            splits = text.split(sep)
            if len(splits) > 1:
                sub_chunks = []
                current_buf = []
                current_len = 0
                
                for piece in splits:
                    piece_str = piece + sep if piece != splits[-1] else piece
                    p_len = len(piece_str)
                    
                    if current_len + p_len <= max_chars:
                        current_buf.append(piece_str)
                        current_len += p_len
                    else:
                        if current_buf:
                            sub_chunks.append("".join(current_buf).strip())
                        current_buf = [piece_str]
                        current_len = p_len
                        
                if current_buf:
                    sub_chunks.append("".join(current_buf).strip())
                    
                if sub_chunks:
                    return sub_chunks

        # Hard character slicing fallback
        results = []
        for i in range(0, len(text), max_chars - overlap):
            results.append(text[i:i + max_chars])
        return results
