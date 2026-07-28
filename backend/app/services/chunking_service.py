import re
from typing import List, Dict, Any, Optional
from app.schemas.normalized_block import NormalizedBlock
from app.core.logging import logger

class ChunkingService:
    # Character budget parameters as confirmed by user
    TARGET_CHARS = 1350   # 1,200 - 1,500 chars
    MAX_CHARS = 1900      # 1,800 - 2,000 chars
    OVERLAP_CHARS = 150   # 150 chars
    MIN_MERGE_CHARS = 400 # 400 - 500 chars

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
                # Flush accumulated prose blocks first
                if prose_blocks:
                    chunks.extend(cls._chunk_prose_blocks(prose_blocks))
                    prose_blocks = []
                # Chunk table block with TableChunker
                chunks.extend(cls._chunk_table_block(block))
            else:
                prose_blocks.append(block)

        # Flush remaining prose blocks
        if prose_blocks:
            chunks.extend(cls._chunk_prose_blocks(prose_blocks))

        # Re-assign sequential chunk order
        for idx, c in enumerate(chunks):
            c["chunk_order"] = idx + 1

        logger.info(f"Chunking complete. Produced {len(chunks)} chunks from {len(blocks)} normalized blocks.")
        return chunks

    @classmethod
    def _chunk_prose_blocks(cls, blocks: List[NormalizedBlock]) -> List[Dict[str, Any]]:
        """
        Recursive Chunker for Prose, Headings, Lists, and Code blocks.
        Performs Post-Merge to combine short adjacent blocks up to TARGET_CHARS budget.
        """
        chunks: List[Dict[str, Any]] = []
        
        current_content_parts: List[str] = []
        current_len = 0
        current_heading_path: List[str] = []
        current_page_start: Optional[int] = None
        current_page_end: Optional[int] = None

        def flush_chunk():
            nonlocal current_content_parts, current_len, current_heading_path, current_page_start, current_page_end
            if not current_content_parts:
                return

            full_text = "\n\n".join(current_content_parts).strip()
            if not full_text:
                return

            # If full_text exceeds MAX_CHARS, split recursively
            if len(full_text) > cls.MAX_CHARS:
                sub_texts = cls._recursive_split_text(full_text, cls.MAX_CHARS, cls.OVERLAP_CHARS)
                for sub in sub_texts:
                    chunks.append({
                        "content": sub,
                        "heading": current_heading_path[-1] if current_heading_path else None,
                        "heading_path": current_heading_path,
                        "page_number": current_page_start,
                        "page_start": current_page_start,
                        "page_end": current_page_end,
                        "sheet_name": None,
                        "row_start": None,
                        "row_end": None
                    })
            else:
                chunks.append({
                    "content": full_text,
                    "heading": current_heading_path[-1] if current_heading_path else None,
                    "heading_path": current_heading_path,
                    "page_number": current_page_start,
                    "page_start": current_page_start,
                    "page_end": current_page_end,
                    "sheet_name": None,
                    "row_start": None,
                    "row_end": None
                })

            # Overlap handling: retain trailing content up to OVERLAP_CHARS
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

        for block in blocks:
            text = block.content.strip()
            if not text:
                continue

            # Update page range tracking
            if block.page_start is not None:
                if current_page_start is None or block.page_start < current_page_start:
                    current_page_start = block.page_start
            if block.page_end is not None:
                if current_page_end is None or block.page_end > current_page_end:
                    current_page_end = block.page_end

            if block.heading_path:
                current_heading_path = block.heading_path

            text_len = len(text)

            if current_len + text_len <= cls.TARGET_CHARS:
                current_content_parts.append(text)
                current_len += text_len
            else:
                # If adding this block exceeds target, check if current buffer meets MIN_MERGE_CHARS
                if current_len >= cls.MIN_MERGE_CHARS:
                    flush_chunk()
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
