from typing import List, Dict, Any
from app.core.logging import logger

class ChunkingService:
    @staticmethod
    def _recursive_split(
        text: str, 
        separators: List[str], 
        chunk_size: int, 
        overlap: int
    ) -> List[str]:
        text = text.strip()
        if not text:
            return []
            
        if len(text) <= chunk_size or not separators:
            return [text]
            
        separator = separators[0]
        next_separators = separators[1:]
        
        # Split text by current separator
        if separator == "":
            splits = list(text)
        else:
            splits = text.split(separator)
            
        final_chunks = []
        current_chunk = []
        current_len = 0
        
        for s in splits:
            # Reconstruct string with separator attached if applicable
            s_str = s if separator == "" else (s + separator if s != splits[-1] else s)
            s_len = len(s_str)
            
            if s_len > chunk_size:
                # If an individual split exceeds chunk_size, flush current buffer and recursively split
                if current_chunk:
                    final_chunks.append("".join(current_chunk).strip())
                    current_chunk = []
                    current_len = 0
                sub_splits = ChunkingService._recursive_split(s_str, next_separators, chunk_size, overlap)
                final_chunks.extend(sub_splits)
            elif current_len + s_len <= chunk_size:
                current_chunk.append(s_str)
                current_len += s_len
            else:
                # Current buffer full -> Flush to chunks
                if current_chunk:
                    chunk_text = "".join(current_chunk).strip()
                    final_chunks.append(chunk_text)
                    
                    # Create overlap buffer from trailing pieces
                    overlap_items = []
                    overlap_size = 0
                    for prev_s in reversed(current_chunk):
                        if overlap_size + len(prev_s) <= overlap:
                            overlap_items.insert(0, prev_s)
                            overlap_size += len(prev_s)
                        else:
                            break
                    current_chunk = overlap_items
                    current_len = overlap_size
                    
                current_chunk.append(s_str)
                current_len += s_len
                
        if current_chunk:
            final_chunks.append("".join(current_chunk).strip())
            
        return [c for c in final_chunks if c]

    @staticmethod
    def chunk_document(
        parsed_items: List[Dict[str, Any]], 
        chunk_size: int = 1000, 
        overlap: int = 200
    ) -> List[Dict[str, Any]]:
        logger.info(f"Executing Recursive Character Chunking with chunk_size={chunk_size}, overlap={overlap}")
        chunks = []
        chunk_order = 0
        separators = ["\n\n", "\n", ". ", " ", ""]
        
        for item in parsed_items:
            content = item["content"].strip()
            if not content:
                continue
                
            heading = item.get("heading")
            heading_prefix = f"[Bối cảnh: {heading}]\n" if heading and not content.startswith("#") else ""
            
            # For XLSX rows or small single entries, emit directly
            if len(content) <= chunk_size or item.get("sheet_name") is not None:
                chunk_order += 1
                final_text = f"{heading_prefix}{content}" if heading_prefix and not content.startswith("[Bối cảnh:") else content
                chunks.append({
                    "content": final_text,
                    "page_number": item.get("page_number"),
                    "heading": item.get("heading"),
                    "sheet_name": item.get("sheet_name"),
                    "row_start": item.get("row_start"),
                    "row_end": item.get("row_end"),
                    "chunk_order": chunk_order
                })
            else:
                # Use Recursive Character Text Splitting for long sections
                raw_sub_chunks = ChunkingService._recursive_split(content, separators, chunk_size, overlap)
                
                for idx, sub_c in enumerate(raw_sub_chunks):
                    chunk_order += 1
                    # Ensure sub-chunk has heading context prefix if not already present
                    if heading and not sub_c.startswith("#") and not sub_c.startswith("[Bối cảnh:"):
                        sub_text = f"[Bối cảnh: {heading}]\n{sub_c}"
                    else:
                        sub_text = sub_c
                        
                    chunks.append({
                        "content": sub_text,
                        "page_number": item.get("page_number"),
                        "heading": item.get("heading"),
                        "sheet_name": item.get("sheet_name"),
                        "row_start": item.get("row_start"),
                        "row_end": item.get("row_end"),
                        "chunk_order": chunk_order
                    })
                    
        logger.info(f"Recursive Chunking generated {chunk_order} clean structural chunks.")
        return chunks
