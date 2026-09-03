import json
import logging

import httpx
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.database import SystemConfig

logger = logging.getLogger("candway_app.ai_engine")


class AIEngine:
    """
    Unified AI Engine for Candway Platform.
    MVP: Groq-only. DeepSeek/Gemini removed.
    """

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.config = self._load_config()
        self.services = {}

    def _load_config(self):
        """Load AI configuration from DB, falling back to ENV"""
        config = {
            "provider": "groq",
            "api_keys": {
                "groq": self.settings.groq_api_key,
            },
        }

        try:
            db_provider = (
                self.db.query(SystemConfig).filter_by(key="ai_provider").first()
            )
            if db_provider and db_provider.value:
                config["provider"] = "groq"  # Always Groq in MVP

            db_key = self.db.query(SystemConfig).filter_by(key="groq_api_key").first()
            if db_key and db_key.value:
                config["api_keys"]["groq"] = db_key.value
        except Exception as e:
            logger.error(f"Failed to load AI config from DB: {e}")

        return config

    def _get_service(self, provider: str):
        """Get or initialize the requested service (Groq only)"""
        if provider in self.services:
            return self.services[provider]

        api_key = self.config["api_keys"].get(provider)
        if not api_key:
            raise ValueError(f"API Key for {provider} not configured")

        if provider == "groq":
            service = GroqWrapper(api_key)
        else:
            raise ValueError(f"Unknown provider: {provider} (MVP supports Groq only)")

        self.services[provider] = service
        return service

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful AI assistant.",
        provider: str = None,
    ) -> str:
        """Generate text response using Groq."""
        active_provider = provider or self.config["provider"]

        try:
            service = self._get_service(active_provider)
            return await service.generate_text(prompt, system_prompt)
        except Exception as e:
            logger.error(f"AI Generation failed with {active_provider}: {e}")
            return "Error: AI generation failed"

    async def generate_json(
        self, prompt: str, schema: dict = None, provider: str = None
    ) -> dict:
        """Generate structured JSON response using Groq."""
        active_provider = provider or self.config["provider"]
        try:
            service = self._get_service(active_provider)
            return await service.generate_json(prompt, schema)
        except Exception as e:
            logger.error(f"AI JSON Generation failed with {active_provider}: {e}")
            return {"error": "AI JSON generation failed"}


class GroqWrapper:
    def __init__(self, api_key):
        self.api_key = api_key
        self.url = "https://api.groq.com/openai/v1/chat/completions"
        self.model = "groq/compound"

    async def generate_text(self, prompt, system_prompt):
        async with httpx.AsyncClient() as client:
            res = await client.post(
                self.url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                },
                timeout=30.0,
            )
            if res.status_code != 200:
                raise Exception(f"Groq API Error: {res.text}")
            return res.json()["choices"][0]["message"]["content"]

    async def generate_json(self, prompt, schema=None):
        async with httpx.AsyncClient() as client:
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
            }
            res = await client.post(
                self.url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
                timeout=30.0,
            )
            if res.status_code != 200:
                raise Exception(f"Groq API Error: {res.text}")
            content = res.json()["choices"][0]["message"]["content"]
            return json.loads(content)
