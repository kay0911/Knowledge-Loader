import threading
from datetime import datetime
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from app.models.llm_key import LLMKey
from app.core.config import settings
from app.core.logging import logger

class KeyRotationService:
    _lock = threading.Lock()
    _current_index = {}

    @classmethod
    def mask_key(cls, key: str) -> str:
        """Utility to mask API Key for security (e.g. AIzaSyB...fg8)"""
        if not key:
            return ""
        if len(key) <= 10:
            return key[:3] + "..." + key[-3:]
        return key[:7] + "..." + key[-4:]

    @classmethod
    def seed_default_key_if_empty(cls, db: Session, provider: str = "gemini"):
        """Auto-seed default API Key from environment settings if DB pool is empty"""
        existing_count = db.query(LLMKey).filter(LLMKey.provider == provider).count()
        if existing_count == 0:
            env_key = settings.GEMINI_API_KEY if provider == "gemini" else getattr(settings, f"{provider.upper()}_API_KEY", "")
            if env_key and env_key != "YOUR_GEMINI_API_KEY_HERE" and "your_" not in env_key.lower():
                try:
                    default_key = LLMKey(
                        provider=provider,
                        api_key=env_key,
                        name=f"Primary Default Key ({provider.upper()})",
                        is_active=True,
                        status="ACTIVE"
                    )
                    db.add(default_key)
                    db.commit()
                    logger.info(f"Seeded default {provider} API key from environment settings.")
                except Exception as e:
                    db.rollback()
                    logger.warning(f"Could not seed default API key: {str(e)}")

    @classmethod
    def auto_recover_cooldown_keys(cls, db: Session, provider: str = "gemini", cooldown_seconds: int = 60):
        """Auto-recover keys from QUOTA_EXCEEDED state back to ACTIVE after cooldown period (60s)"""
        try:
            from datetime import timedelta
            threshold_time = datetime.utcnow() - timedelta(seconds=cooldown_seconds)
            recovered = db.query(LLMKey).filter(
                LLMKey.provider == provider,
                LLMKey.status == "QUOTA_EXCEEDED",
                LLMKey.last_error_at <= threshold_time
            ).update({"status": "ACTIVE", "error_count": 0}, synchronize_session=False)
            if recovered > 0:
                db.commit()
                logger.info(f"Auto-recovered {recovered} {provider} API key(s) from QUOTA_EXCEEDED cooldown.")
        except Exception as e:
            db.rollback()
            logger.warning(f"Failed to auto-recover cooldown keys: {e}")

    @classmethod
    def get_valid_api_key(cls, db: Session, provider: str = "gemini") -> Tuple[str, Optional[LLMKey]]:
        """
        Get the next available active API key using Round-Robin strategy.
        Returns tuple of (raw_api_key_str, llm_key_db_object).
        """
        with cls._lock:
            cls.seed_default_key_if_empty(db, provider)
            # Auto recover keys that completed 60-second rate limit cooldown
            cls.auto_recover_cooldown_keys(db, provider, cooldown_seconds=60)
            
            # Fetch all active keys for provider
            active_keys = db.query(LLMKey).filter(
                LLMKey.provider == provider,
                LLMKey.is_active == True,
                LLMKey.status == "ACTIVE"
            ).order_by(LLMKey.created_at.asc()).all()

            # If no ACTIVE keys found, check if any QUOTA_EXCEEDED keys can be fallback reset
            if not active_keys:
                fallback_keys = db.query(LLMKey).filter(
                    LLMKey.provider == provider,
                    LLMKey.is_active == True
                ).order_by(LLMKey.last_used_at.asc().nullsfirst()).all()
                
                if fallback_keys:
                    logger.warning(f"No fully ACTIVE keys available for {provider}. Resetting fallback key...")
                    chosen = fallback_keys[0]
                    chosen.status = "ACTIVE"
                    chosen.error_count = 0
                    db.commit()
                    return chosen.api_key, chosen
                
                # If still no key, fallback to env setting
                env_key = settings.GEMINI_API_KEY if provider == "gemini" else ""
                return env_key, None

            # Round Robin selection
            idx = cls._current_index.get(provider, 0) % len(active_keys)
            chosen_key = active_keys[idx]
            cls._current_index[provider] = (idx + 1) % len(active_keys)

            return chosen_key.api_key, chosen_key

    @classmethod
    def report_key_success(cls, db: Session, key_id):
        """Update usage stats when an API call succeeds with key_id"""
        if not key_id:
            return
        try:
            db.query(LLMKey).filter(LLMKey.id == key_id).update({
                "usage_count": LLMKey.usage_count + 1,
                "error_count": 0,
                "status": "ACTIVE",
                "last_used_at": func.now()
            })
            db.commit()
        except Exception as e:
            db.rollback()
            logger.warning(f"Failed to report key success for {key_id}: {e}")

    @classmethod
    def report_key_error(cls, db: Session, key_id, error_msg: str, is_quota_exceeded: bool = False):
        """Handle key errors (429 rate limit or invalid credentials)"""
        if not key_id:
            return
        try:
            key_obj = db.query(LLMKey).filter(LLMKey.id == key_id).first()
            if not key_obj:
                return
            
            key_obj.error_count += 1
            key_obj.last_error_at = datetime.utcnow()

            if is_quota_exceeded or "429" in error_msg or "quota" in error_msg.lower() or "resource_exhausted" in error_msg.lower():
                key_obj.status = "QUOTA_EXCEEDED"
                logger.warning(f"API Key '{key_obj.name or cls.mask_key(key_obj.api_key)}' hit rate limit 429. Marked as QUOTA_EXCEEDED.")
            elif "401" in error_msg or "403" in error_msg or "invalid" in error_msg.lower():
                key_obj.status = "INVALID"
                logger.error(f"API Key '{key_obj.name or cls.mask_key(key_obj.api_key)}' returned invalid auth error. Marked as INVALID.")
            elif key_obj.error_count >= 3:
                key_obj.status = "TEMPORARY_ERROR"
                logger.warning(f"API Key '{key_obj.name or cls.mask_key(key_obj.api_key)}' failed {key_obj.error_count} times consecutive.")

            db.commit()
        except Exception as e:
            db.rollback()
            logger.warning(f"Failed to report key error: {e}")

    @classmethod
    def reset_all_exhausted_keys(cls, db: Session, provider: str = "gemini") -> int:
        """Reset QUOTA_EXCEEDED keys back to ACTIVE state"""
        try:
            updated = db.query(LLMKey).filter(
                LLMKey.provider == provider,
                LLMKey.status == "QUOTA_EXCEEDED"
            ).update({"status": "ACTIVE", "error_count": 0})
            db.commit()
            return updated
        except Exception as e:
            db.rollback()
            logger.error(f"Reset exhausted keys error: {e}")
            return 0
