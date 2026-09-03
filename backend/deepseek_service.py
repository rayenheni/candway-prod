"""
DeepSeek AI Service - Secondary fallback provider
Uses DeepSeek API for question generation (fast & cost-effective)
SECURITY: Added sanitization for all user-controllable content
"""

import json
import logging
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)


class DeepSeekService:
    """
    DeepSeek API integration for interview question generation.
    Used as secondary fallback when Groq fails.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.deepseek.com/v1"
        self.model = "deepseek-chat"

    async def generate_question(
        self,
        prompt: str,
    ) -> Dict[str, Any]:
        """
        Generate interview question using DeepSeek API from a pre-built prompt.

        Args:
            prompt: Pre-built prompt string (built by ai/prompts.py)

        Returns:
            Dict with question, options, correct_answer, etc.
        """

        # Call DeepSeek API
        try:
            url = f"{self.base_url}/chat/completions"

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            # Build messages
            messages = [
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": "Generate the interview question based on the instructions above.",
                },
            ]

            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.5,
                "max_tokens": 1000,
                "response_format": {"type": "json_object"},
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=payload)

                if response.status_code != 200:
                    logger.error(
                        "DeepSeek API error",
                        extra={
                            "status_code": response.status_code,
                            "response_preview": response.text[:200],
                        },
                    )
                    raise Exception(f"DeepSeek API failed: {response.status_code}")

                result = response.json()

                # Extract generated text
                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0]["message"]["content"]

                    # Parse JSON response
                    try:
                        question_data = json.loads(content)
                        logger.info("DeepSeek API: Question generated successfully")
                        return question_data
                    except json.JSONDecodeError as je:
                        logger.error(
                            "DeepSeek JSON parse error",
                            extra={"error": str(je), "raw_preview": content[:200]},
                        )
                        raise
                else:
                    raise Exception("DeepSeek returned empty response")

        except Exception as e:
            logger.error(
                "DeepSeek API exception",
                extra={"exception_type": type(e).__name__, "error": str(e)},
            )
            raise


# Global DeepSeek service instance
deepseek_service = None


def init_deepseek_service(api_key: str):
    """Initialize DeepSeek service with API key"""
    global deepseek_service
    deepseek_service = DeepSeekService(api_key)
    logger.info("DeepSeek AI Service initialized")


async def generate_question_with_deepseek(
    prompt: str,
) -> Dict[str, Any]:
    """
    Generate question using DeepSeek API from a pre-built prompt.
    Wrapper function for easy integration.

    Args:
        prompt: Pre-built prompt string (built by ai/prompts.py)
    """
    if not deepseek_service:
        raise Exception(
            "DeepSeek service not initialized. Call init_deepseek_service() first."
        )

    return await deepseek_service.generate_question(prompt=prompt)
