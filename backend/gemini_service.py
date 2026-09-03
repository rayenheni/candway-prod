"""
Gemini AI Service - Fallback provider when Groq fails
Uses Google's Gemini API for question generation
SECURITY: Added sanitization for all user-controllable content
"""

import json
import logging
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)


class GeminiService:
    """
    Google Gemini API integration for interview question generation.
    Used as fallback when Groq API fails.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.model = "gemini-3.6-flash"

    async def generate_question(
        self,
        prompt: str,
    ) -> Dict[str, Any]:
        """
        Generate interview question using Gemini API from a pre-built prompt.

        Args:
            prompt: Pre-built prompt string (built by ai/prompts.py)

        Returns:
            Dict with question, options, correct_answer, etc.
        """

        # Call Gemini API
        try:
            url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"

            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.5,
                    "maxOutputTokens": 1000,
                    "responseMimeType": "application/json",
                },
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)

                if response.status_code != 200:
                    logger.error(
                        "Gemini API error",
                        extra={
                            "status_code": response.status_code,
                            "response_preview": response.text[:200],
                        },
                    )
                    raise Exception(f"Gemini API failed: {response.status_code}")

                result = response.json()

                # Extract generated text
                if "candidates" in result and len(result["candidates"]) > 0:
                    content = result["candidates"][0]["content"]["parts"][0]["text"]

                    # Parse JSON response
                    try:
                        question_data = json.loads(content)
                        logger.info("Gemini API: Question generated successfully")
                        return question_data
                    except json.JSONDecodeError as je:
                        logger.error(
                            "Gemini JSON parse error",
                            extra={"error": str(je), "raw_preview": content[:200]},
                        )
                        raise
                else:
                    raise Exception("Gemini returned empty response")

        except Exception as e:
            logger.error(
                "Gemini API exception",
                extra={"exception_type": type(e).__name__, "error": str(e)},
            )
            raise


# Global Gemini service instance
gemini_service = None


def init_gemini_service(api_key: str):
    """Initialize Gemini service with API key"""
    global gemini_service
    gemini_service = GeminiService(api_key)
    logger.info("Gemini AI Service initialized")


async def generate_question_with_gemini(
    prompt: str,
) -> Dict[str, Any]:
    """
    Generate question using Gemini API from a pre-built prompt.
    Wrapper function for easy integration.

    Args:
        prompt: Pre-built prompt string (built by ai/prompts.py)
    """
    if not gemini_service:
        raise Exception(
            "Gemini service not initialized. Call init_gemini_service() first."
        )

    return await gemini_service.generate_question(prompt=prompt)
