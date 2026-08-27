import re
import logging
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from app.core.logging import logger

def compute_cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = sum(a * a for a in vec1) ** 0.5
    norm2 = sum(b * b for b in vec2) ** 0.5
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return max(0.0, dot / (norm1 * norm2))

class TwoStageRetrievalService:
    @classmethod
    def stage_1_route_documents(
        cls,
        query: str,
        document_metadata_list: List[Dict[str, Any]],
        top_k_docs: int = 2,
        db: Optional[Session] = None,
        query_vec: Optional[List[float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Stage 1: Matches user query against Document Metadata Summaries using Hybrid Alpha-Blending Fusion:
        - 50% Vector Cosine Similarity (Query Vector vs Composite Summary Embedding)
        - 50% Rule-based Scoring (HyDE Questions + Keywords + Domain + Filename Title Boost)
        Returns top_k_docs candidate documents.
        """
        logger.info(f"--- STAGE 1: Hybrid Routing query '{query}' against {len(document_metadata_list)} documents ---")
        q_lower = query.lower()
        q_words = set(re.findall(r"\w+", q_lower))
        
        # 1. Reuse existing query_vec or generate if missing
        if query_vec is None and db:
            try:
                from app.services.embedding_service import EmbeddingService
                query_vec = EmbeddingService.get_embedding(query, db=db)
            except Exception as vec_err:
                logger.warning(f"Failed to generate query embedding for Stage 1 Summary Vector Search: {vec_err}")

        scored_docs = []
        for doc_meta in document_metadata_list:
            fn = doc_meta.get("filename", "")
            summary = doc_meta.get("document_summary", "").lower()
            domain = doc_meta.get("domain", "").lower()
            sub_domain = doc_meta.get("sub_domain", "").lower()
            keywords = [k.lower() for k in doc_meta.get("keywords", [])]
            entities = [e.lower() for e in doc_meta.get("primary_entities", [])]
            hyp_questions = [hq.lower() for hq in doc_meta.get("hypothetical_questions", [])]

            raw_rule_score = 0.0

            # 1. Hypothetical Question Overlap (HyDE Matching - Weight: 5.0)
            for hq in hyp_questions:
                hq_words = set(re.findall(r"\w+", hq))
                common = q_words.intersection(hq_words)
                if common:
                    overlap_ratio = len(common) / max(len(q_words), 1)
                    raw_rule_score += overlap_ratio * 5.0

            # 2. Keyword & Entity Overlap
            for kw in keywords + entities:
                if kw and kw in q_lower:
                    raw_rule_score += 3.0
                elif any(w in kw for w in q_words if len(w) > 3):
                    raw_rule_score += 1.5

            # 3. Domain / Sub-domain matching
            if domain and domain in q_lower:
                raw_rule_score += 2.0
            if sub_domain and sub_domain in q_lower:
                raw_rule_score += 2.0

            # 4. Summary Overlap
            summary_words = set(re.findall(r"\w+", summary))
            common_sum = q_words.intersection(summary_words)
            if common_sum:
                raw_rule_score += (len(common_sum) / max(len(q_words), 1)) * 2.0

            # 5. Direct Filename / Document Title Match Boost
            fn_clean = re.sub(r"[\._\-\d]+", " ", fn.lower())
            fn_tokens = [w for w in re.findall(r"\w+", fn_clean) if len(w) > 2 and w not in ["docx", "xlsx", "pdf"]]
            for ft in fn_tokens:
                if ft in q_lower:
                    raw_rule_score += 3.0

            # Vector Cosine Similarity Score
            summary_vec = doc_meta.get("summary_embedding")
            cos_sim = compute_cosine_similarity(query_vec, summary_vec) if (query_vec and summary_vec) else 0.0
            norm_vector_score = max(0.0, min(1.0, cos_sim))

            # Rule-based Normalization [0.0, 1.0]
            norm_rule_score = min(1.0, raw_rule_score / 10.0)

            # Alpha-Blending 50/50 Fusion: If vector is present, 50% Vector + 50% Rule; else 100% Rule
            if summary_vec and query_vec:
                final_score = (0.50 * norm_vector_score) + (0.50 * norm_rule_score)
            else:
                final_score = norm_rule_score

            scored_docs.append({
                "filename": fn,
                "score": final_score,
                "raw_rule_score": raw_rule_score,
                "cosine_sim": cos_sim,
                "domain": doc_meta.get("domain"),
                "document_summary": doc_meta.get("document_summary"),
                "hypothetical_questions": doc_meta.get("hypothetical_questions", []),
                "metadata": doc_meta
            })

        scored_docs.sort(key=lambda x: x["score"], reverse=True)
        
        # Adaptive Threshold Filtering: Keep candidate docs with significant positive scores
        max_score = scored_docs[0]["score"] if scored_docs else 0.0
        if max_score > 0:
            filtered = [d for d in scored_docs if d["score"] >= max(0.05, max_score * 0.3)]
            top_candidates = filtered[:top_k_docs]
        else:
            top_candidates = scored_docs[:top_k_docs]

        logger.info("Stage 1 Document Selection Results:")
        for idx, cand in enumerate(top_candidates, start=1):
            logger.info(f"  [{idx}] File: {cand['filename']} (FinalScore: {cand['score']:.3f} | CosSim: {cand['cosine_sim']:.3f} | RawRule: {cand['raw_rule_score']:.1f}) | Domain: {cand['domain']}")

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
