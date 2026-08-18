import re
import logging
from typing import List, Dict, Any, Tuple
from app.core.logging import logger

class TwoStageRetrievalService:
    @classmethod
    def stage_1_route_documents(
        cls,
        query: str,
        document_metadata_list: List[Dict[str, Any]],
        top_k_docs: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Stage 1: Matches user query against Document Metadata Summaries.
        Scores candidate documents based on:
        - Hypothetical Questions matching (HyDE)
        - Keyword & Primary Entity matching
        - Document Summary & Domain relevance
        Returns top_k_docs candidate documents.
        """
        logger.info(f"--- STAGE 1: Routing query '{query}' against {len(document_metadata_list)} documents ---")
        q_lower = query.lower()
        q_words = set(re.findall(r"\w+", q_lower))
        
        scored_docs = []
        for doc_meta in document_metadata_list:
            fn = doc_meta.get("filename", "")
            summary = doc_meta.get("document_summary", "").lower()
            domain = doc_meta.get("domain", "").lower()
            sub_domain = doc_meta.get("sub_domain", "").lower()
            keywords = [k.lower() for k in doc_meta.get("keywords", [])]
            entities = [e.lower() for e in doc_meta.get("primary_entities", [])]
            hyp_questions = [hq.lower() for hq in doc_meta.get("hypothetical_questions", [])]

            score = 0.0

            # 1. Hypothetical Question Overlap (HyDE Matching - Highest Weight)
            for hq in hyp_questions:
                hq_words = set(re.findall(r"\w+", hq))
                common = q_words.intersection(hq_words)
                if common:
                    overlap_ratio = len(common) / max(len(q_words), 1)
                    score += overlap_ratio * 5.0

            # 2. Keyword & Entity Overlap
            for kw in keywords + entities:
                if kw and kw in q_lower:
                    score += 3.0
                elif any(w in kw for w in q_words if len(w) > 3):
                    score += 1.5

            # 3. Domain / Sub-domain matching
            if domain and domain in q_lower:
                score += 2.0
            if sub_domain and sub_domain in q_lower:
                score += 2.0

            # 4. Summary Overlap
            summary_words = set(re.findall(r"\w+", summary))
            common_sum = q_words.intersection(summary_words)
            if common_sum:
                score += (len(common_sum) / max(len(q_words), 1)) * 2.0

            # 5. Direct Filename / Document Title Match Boost
            fn_clean = re.sub(r"[\._\-\d]+", " ", fn.lower())
            fn_tokens = [w for w in re.findall(r"\w+", fn_clean) if len(w) > 2 and w not in ["docx", "xlsx", "pdf"]]
            for ft in fn_tokens:
                if ft in q_lower:
                    score += 3.0

            scored_docs.append({
                "filename": fn,
                "score": score,
                "domain": doc_meta.get("domain"),
                "document_summary": doc_meta.get("document_summary"),
                "hypothetical_questions": doc_meta.get("hypothetical_questions", []),
                "metadata": doc_meta
            })

        scored_docs.sort(key=lambda x: x["score"], reverse=True)
        
        # Adaptive Threshold Filtering: Keep candidate docs with significant positive scores
        max_score = scored_docs[0]["score"] if scored_docs else 0.0
        if max_score > 0:
            filtered = [d for d in scored_docs if d["score"] >= max(0.5, max_score * 0.3)]
            top_candidates = filtered[:top_k_docs]
        else:
            top_candidates = scored_docs[:top_k_docs]

        logger.info("Stage 1 Document Selection Results:")
        for idx, cand in enumerate(top_candidates, start=1):
            logger.info(f"  [{idx}] File: {cand['filename']} (Score: {cand['score']:.2f}) | Domain: {cand['domain']}")

        return top_candidates

    @classmethod
    def stage_2_retrieve_in_document_chunks(
        cls,
        query: str,
        selected_doc_filenames: List[str],
        all_document_chunks_map: Dict[str, List[Dict[str, Any]]],
        top_k_chunks: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Stage 2: Scopes chunk retrieval strictly to selected document(s) from Stage 1.
        Filters all_document_chunks_map by filename IN (selected_doc_filenames).
        Scores & ranks chunks in target documents.
        """
        logger.info(f"--- STAGE 2: Retrieving chunks scoped strictly to selected documents: {selected_doc_filenames} ---")
        q_lower = query.lower()
        q_words = set(re.findall(r"\w+", q_lower))

        candidate_chunks = []
        for fn in selected_doc_filenames:
            chunks = all_document_chunks_map.get(fn, [])
            for c in chunks:
                content = c.get("content", "").lower()
                heading = " ".join(c.get("heading_path", [])).lower() if isinstance(c.get("heading_path"), list) else str(c.get("heading_path", "")).lower()

                score = 0.0
                # Content word overlap
                c_words = set(re.findall(r"\w+", content))
                common = q_words.intersection(c_words)
                if common:
                    score += len(common) / max(len(q_words), 1) * 3.0

                # Heading match boost
                h_words = set(re.findall(r"\w+", heading))
                common_h = q_words.intersection(h_words)
                if common_h:
                    score += len(common_h) * 2.0

                # Table & Image contextual boost
                if c.get("has_table"):
                    score += 0.5
                if c.get("has_image"):
                    score += 0.5

                chunk_copy = dict(c)
                chunk_copy["stage_2_score"] = score
                candidate_chunks.append(chunk_copy)

        candidate_chunks.sort(key=lambda x: x["stage_2_score"], reverse=True)
        final_top_chunks = candidate_chunks[:top_k_chunks]

        logger.info(f"Stage 2 Final Chunk Selection returned {len(final_top_chunks)} chunks.")
        return final_top_chunks
