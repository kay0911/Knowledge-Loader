import os
import json
import re
import google.generativeai as genai
from typing import Dict, List, Tuple, Any
from app.core.config import settings
from app.core.logging import logger

class GraphExtractionService:
    _configured = False
    _prompt_template = ""

    @classmethod
    def _configure(cls):
        if not cls._configured:
            api_key = settings.GEMINI_API_KEY
            if not api_key or api_key == "YOUR_GEMINI_API_KEY_HERE":
                logger.warning("GEMINI_API_KEY is placeholder or empty in settings!")
            genai.configure(api_key=api_key, transport='rest')
            
            # Load prompt template
            prompt_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "prompts",
                "graph_extraction.txt"
            )
            try:
                with open(prompt_path, "r", encoding="utf-8") as f:
                    cls._prompt_template = f.read()
            except Exception as e:
                logger.error(f"Failed to load graph_extraction.txt: {str(e)}")
                # Fail-safe prompt fallback
                cls._prompt_template = "Extract entities and relationships from the text:\n{text}"
            
            cls._configured = True

    @classmethod
    def extract_graph(cls, chunk_content: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Call Gemini API to extract entities and relationships from chunk content.
        Returns a tuple of (entities, relationships).
        """
        cls._configure()
        if not chunk_content.strip():
            return [], []
            
        from app.services.key_rotation_service import KeyRotationService
        from app.db.postgres import SessionLocal
        
        db = SessionLocal()
        try:
            prompt = cls._prompt_template.replace("{text}", chunk_content)
            response_text = ""
            last_error = None

            for attempt in range(5):
                raw_key, key_obj = KeyRotationService.get_valid_api_key(db, provider="gemini")
                try:
                    genai.configure(api_key=raw_key, transport='rest')
                    model = genai.GenerativeModel(
                        model_name=settings.GEMINI_LLM_MODEL,
                        generation_config={"response_mime_type": "application/json"}
                    )
                    response = model.generate_content(prompt)
                    response_text = response.text.strip()
                    if key_obj:
                        KeyRotationService.report_key_success(db, key_obj.id)
                    break
                except Exception as e:
                    last_error = e
                    err_str = str(e)
                    logger.warning(f"Graph extraction attempt {attempt + 1} with key '{KeyRotationService.mask_key(raw_key)}' failed: {err_str}")
                    if key_obj:
                        KeyRotationService.report_key_error(db, key_obj.id, err_str)

            if not response_text:
                if last_error:
                    logger.error(f"Graph extraction failed after key retries: {str(last_error)}")
                return [], []
                
            # Parse JSON response
            extracted = json.loads(response_text)
            
            entities = extracted.get("entities", [])
            relationships = extracted.get("relationships", [])
            
            # Normalize entities and relationships
            normalized_entities = cls._normalize_entities(entities)
            normalized_relationships = cls._normalize_relationships(relationships)
            
            return normalized_entities, normalized_relationships
        except Exception as e:
            logger.error(f"Failed to extract graph from chunk content: {str(e)}", exc_info=True)
            # Fail silently in worker loop or let worker catch it? Let's return empty lists so worker can keep going
            return [], []
        finally:
            db.close()

    @staticmethod
    def _normalize_entities(entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        norm_entities = []
        for ent in entities:
            name = ent.get("name")
            ent_type = ent.get("type")
            if not name or not ent_type:
                continue
                
            # Trim and capitalize standard type
            name = name.strip()
            ent_type = ent_type.strip().capitalize()
            desc = ent.get("description", "").strip()
            conf = ent.get("confidence", 1.0)
            
            norm_entities.append({
                "name": name,
                "type": ent_type,
                "description": desc,
                "confidence": conf
            })
        return norm_entities

    @staticmethod
    def _normalize_relationships(relationships: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        norm_relationships = []
        for rel in relationships:
            src = rel.get("source")
            tgt = rel.get("target")
            relation = rel.get("relation")
            if not src or not tgt or not relation:
                continue
                
            src = src.strip()
            tgt = tgt.strip()
            
            # Convert relation to UPPER_SNAKE_CASE
            relation = relation.strip().upper().replace(" ", "_")
            relation = re.sub(r"[^A-Z0-9_]", "", relation)
            
            # Mapping synonyms to standard relation types
            synonym_map = {
                "APPLY_TO": "APPLIES_TO",
                "IS_APPLICABLE_TO": "APPLIES_TO",
                "APPLICABLE_TO": "APPLIES_TO",
                "BELONG_TO": "BELONGS_TO",
                "PART_OF": "BELONGS_TO",
                "DESCRIBE": "DESCRIBES",
                "MENTION": "MENTIONS",
            }
            relation = synonym_map.get(relation, relation)
            
            desc = rel.get("description", "").strip()
            conf = rel.get("confidence", 1.0)
            src_type = rel.get("source_type", "Entity").strip().capitalize()
            tgt_type = rel.get("target_type", "Entity").strip().capitalize()
            
            norm_relationships.append({
                "source": src,
                "source_type": src_type,
                "relation": relation,
                "target": tgt,
                "target_type": tgt_type,
                "description": desc,
                "confidence": conf
            })
        return norm_relationships
