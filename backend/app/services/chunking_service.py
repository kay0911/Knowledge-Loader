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

        chunks: List[Dict[str, Any]] = []
        prose_blocks: List[NormalizedBlock] = []

        for block in blocks:
            if block.block_type in ["table", "table_group"]:
                if prose_blocks:
                    chunks.extend(cls._chunk_prose_blocks(prose_blocks))
                    prose_blocks = []
                chunks.append({
                    "chunk_order": 0,
                    "heading": block.heading_path[-1] if block.heading_path else block.sheet_name,
                    "heading_path": list(block.heading_path),
                    "content": block.content,
                    "block_type": "table",
                    "sheet_name": block.sheet_name,
                    "has_table": True,
                    "requires_llm_summary": False,
                    "page_start": block.page_start,
                    "page_end": block.page_end
                })
            elif block.block_type == "image":
                if prose_blocks:
                    chunks.extend(cls._chunk_prose_blocks(prose_blocks))
                    prose_blocks = []
                chunks.append({
                    "chunk_order": 0,
                    "heading": block.heading_path[-1] if block.heading_path else None,
                    "heading_path": list(block.heading_path),
                    "content": block.content,
                    "block_type": "image",
                    "image_path": getattr(block, "image_path", None),
                    "has_image": True,
                    "requires_llm_summary": True,
                    "page_start": block.page_start,
                    "page_end": block.page_end
                })
            else:
                prose_blocks.append(block)

        # Flush remaining prose blocks
        if prose_blocks:
            chunks.extend(cls._chunk_prose_blocks(prose_blocks))

        # Post-merge pass: combine short adjacent chunks & tables up to MAX_CHARS (1500 chars / ~400 tokens)
        merged_chunks: List[Dict[str, Any]] = []
        for c in chunks:
            if not merged_chunks:
                merged_chunks.append(c)
                continue
            
            prev = merged_chunks[-1]
            prev_len = len(prev["content"])
            curr_len = len(c["content"])

            # Do NOT merge standalone image chunks into text/table chunks
            if prev.get("block_type") == "image" or c.get("block_type") == "image":
                merged_chunks.append(c)
                continue

            # Merge adjacent prose/text chunks if combined size fits in TARGET_CHARS (or if prev is below MIN_MERGE_CHARS up to MAX_CHARS)
            if (prev_len + curr_len <= cls.TARGET_CHARS) or (prev_len < cls.MIN_MERGE_CHARS and prev_len + curr_len <= cls.MAX_CHARS):
                prev["content"] = prev["content"] + "\n\n" + c["content"]
                if c.get("heading") and not prev.get("heading"):
                    prev["heading"] = c.get("heading")
                    prev["heading_path"] = c.get("heading_path")
                if c.get("has_table"):
                    prev["has_table"] = True
                if c.get("has_image"):
                    prev["has_image"] = True
                prev["requires_llm_summary"] = prev.get("has_image", False) or c.get("has_image", False)
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
        Recursive Chunker for Prose, Headings, Lists, and Code blocks.
        Performs Post-Merge to combine short adjacent blocks up to TARGET_CHARS budget.
        Anchors heading_path to the specific content section to prevent metadata misalignment.
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
            contains_image = "<img " in full_text
            b_type = "table" if contains_table else ("image" if contains_image else "text")
            req_summary = contains_table or contains_image

            # If full_text exceeds MAX_CHARS, split recursively
            if len(full_text) > cls.MAX_CHARS:
                sub_texts = cls._recursive_split_text(full_text, cls.MAX_CHARS, cls.OVERLAP_CHARS)
                for sub in sub_texts:
                    sub_table = "<table>" in sub or "<table " in sub or "| --- |" in sub or ("| " in sub and " |\n|" in sub)
                    sub_image = "<img " in sub
                    sub_type = "table" if sub_table else ("image" if sub_image else "text")
                    sub_req = sub_table or sub_image
                    chunks.append({
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
                    })
            else:
                chunks.append({
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
                })

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

            # Check if this block is a new heading or top-level item title
            is_new_section_title = block.block_type == "heading" or (item_pattern.search(text) and not any(p.startswith(text[:15]) for p in current_content_parts))

            # Flush preceding section ONLY when buffer has reached MIN_MERGE_CHARS (200 chars)!
            # Prevents creating micro-chunks for short consecutive headings!
            if is_new_section_title and current_content_parts and current_len >= cls.MIN_MERGE_CHARS:
                flush_chunk(is_section_boundary=True)

            if block.heading_path:
                current_heading_path = list(block.heading_path)

            if not active_chunk_heading_path:
                active_chunk_heading_path = list(current_heading_path)

            # Update page range tracking
            if block.page_start is not None:
                if current_page_start is None or block.page_start < current_page_start:
                    current_page_start = block.page_start
            if block.page_end is not None:
                if current_page_end is None or block.page_end > current_page_end:
                    current_page_end = block.page_end

            text_len = len(text)

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
        Table Chunker with Header Enrichment and Character Budget Packing for XLSX/CSV/Tables.
        """
        chunks: List[Dict[str, Any]] = []
        lines = [l.strip() for l in block.content.split("\n") if l.strip()]
        if not lines:
            return []

        sheet_prefix = f"Sheet: {block.sheet_name}\n" if block.sheet_name else ""
        header_text = sheet_prefix

        # Separate header lines vs record lines
        record_lines = lines

        current_records: List[str] = []
        current_len = len(header_text)
        row_start = block.row_start
        row_end = block.row_end

        def flush_table_chunk():
            nonlocal current_records, current_len
            if not current_records:
                return

            table_text = header_text + "\n".join(current_records)
            chunks.append({
                "block_type": "table",
                "has_table": True,
                "requires_llm_summary": True,
                "content": table_text,
                "heading": block.heading_path[-1] if block.heading_path else block.sheet_name,
                "heading_path": block.heading_path,
                "page_number": block.page_start,
                "page_start": block.page_start,
                "page_end": block.page_end,
                "sheet_name": block.sheet_name,
                "row_start": row_start,
                "row_end": row_end
            })

            current_records = []
            current_len = len(header_text)

        for line in record_lines:
            line_len = len(line) + 1
            if current_len + line_len <= cls.TARGET_CHARS:
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
