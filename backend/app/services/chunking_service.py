from typing import List, Dict, Any
from app.core.logging import logger

class ChunkingService:
    @staticmethod
    def chunk_document(
        parsed_items: List[Dict[str, Any]], 
        chunk_size: int = 1000, 
        overlap: int = 200
    ) -> List[Dict[str, Any]]:
        logger.info(f"Chunking document with chunk_size={chunk_size}, overlap={overlap}")
        chunks = []
        chunk_order = 0
        
        for item in parsed_items:
            content = item["content"].strip()
            if not content:
                continue
            
            # If it's an XLSX row or a small piece of text, make it a single chunk
            if len(content) <= chunk_size or item["sheet_name"] is not None:
                chunk_order += 1
                chunks.append({
                    "content": content,
                    "page_number": item["page_number"],
                    "heading": item["heading"],
                    "sheet_name": item["sheet_name"],
                    "row_start": item["row_start"],
                    "row_end": item["row_end"],
                    "chunk_order": chunk_order
                })
            else:
                # PDF page or DOCX text too long -> Split by sentences
                sentences = []
                current_sentence = []
                for char in content:
                    current_sentence.append(char)
                    if char in ['.', '?', '!'] or char == '\n':
                        sent = "".join(current_sentence).strip()
                        if sent:
                            sentences.append(sent)
                        current_sentence = []
                if current_sentence:
                    sent = "".join(current_sentence).strip()
                    if sent:
                        sentences.append(sent)
                
                current_chunk = []
                current_length = 0
                
                for sent in sentences:
                    # If sentence itself is longer than chunk_size, split by characters
                    if len(sent) > chunk_size:
                        # Flush existing chunk
                        if current_chunk:
                            chunk_order += 1
                            chunks.append({
                                "content": " ".join(current_chunk),
                                "page_number": item["page_number"],
                                "heading": item["heading"],
                                "sheet_name": item["sheet_name"],
                                "row_start": item["row_start"],
                                "row_end": item["row_end"],
                                "chunk_order": chunk_order
                            })
                            current_chunk = []
                            current_length = 0
                        
                        # Sub-split long sentence
                        start = 0
                        while start < len(sent):
                            end = start + chunk_size
                            sub_sent = sent[start:end]
                            chunk_order += 1
                            chunks.append({
                                "content": sub_sent,
                                "page_number": item["page_number"],
                                "heading": item["heading"],
                                "sheet_name": item["sheet_name"],
                                "row_start": item["row_start"],
                                "row_end": item["row_end"],
                                "chunk_order": chunk_order
                            })
                            start += (chunk_size - overlap)
                        continue
                    
                    # Accumulate sentences
                    if current_length + len(sent) + 1 > chunk_size:
                        chunk_order += 1
                        chunks.append({
                            "content": " ".join(current_chunk),
                            "page_number": item["page_number"],
                            "heading": item["heading"],
                            "sheet_name": item["sheet_name"],
                            "row_start": item["row_start"],
                            "row_end": item["row_end"],
                            "chunk_order": chunk_order
                        })
                        
                        # Build overlap by pulling sentences from the end of current_chunk
                        overlap_chunk = []
                        overlap_len = 0
                        for prev_sent in reversed(current_chunk):
                            if overlap_len + len(prev_sent) + 1 <= overlap:
                                overlap_chunk.insert(0, prev_sent)
                                overlap_len += len(prev_sent) + 1
                            else:
                                break
                        current_chunk = overlap_chunk
                        current_length = overlap_len
                    
                    current_chunk.append(sent)
                    current_length += len(sent) + 1
                
                if current_chunk:
                    chunk_order += 1
                    chunks.append({
                        "content": " ".join(current_chunk),
                        "page_number": item["page_number"],
                        "heading": item["heading"],
                        "sheet_name": item["sheet_name"],
                        "row_start": item["row_start"],
                        "row_end": item["row_end"],
                        "chunk_order": chunk_order
                    })
        
        logger.info(f"Generated {chunk_order} chunks from document.")
        return chunks
