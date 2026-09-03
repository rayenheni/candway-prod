import asyncio
import json
import time
import uuid
from typing import Any, Dict, Optional

from backend.config import get_settings
from backend.logger import logger
from backend.redis_manager import redis_manager

settings = get_settings()


class InterviewWorkerQueue:
    """
    Redis-backed worker queue for decoupling heavy LLM processing from HTTP threads.
    """

    def __init__(self):
        self._redis = None
        self.task_prefix = "interview_task:"
        self.result_prefix = "interview_result:"
        self.queue_name = "interview_queue"

    async def _get_redis(self):
        if self._redis is None:
            self._redis = await redis_manager.get_client()
        return self._redis

    async def enqueue_task(self, task_data: Dict[str, Any], timeout: int = 120) -> str:
        task_id = str(uuid.uuid4())
        payload = {"task_id": task_id, "data": task_data, "timestamp": time.time()}

        r = await self._get_redis()
        if r is None:
            logger.warning(
                "[WorkerQueue] Redis unavailable — falling back to in-process execution"
            )
            return await self._execute_inline(task_data, timeout)

        await r.set(f"{self.task_prefix}{task_id}", json.dumps(payload), ex=timeout * 2)
        await r.lpush(self.queue_name, task_id)

        logger.info(f"[WorkerQueue] Enqueued task {task_id}")
        return task_id

    async def _execute_inline(self, task_data: Dict[str, Any], timeout: int) -> str:
        task_id = f"inline_{uuid.uuid4().hex[:8]}"
        try:
            from backend.ai.llm import call_groq_cascade

            messages = task_data.get("messages", [])
            result = await asyncio.wait_for(
                call_groq_cascade(
                    messages=messages,
                    temperature=task_data.get("temperature", 0.1),
                    max_tokens=task_data.get("max_tokens", 1024),
                    json_mode=task_data.get("json_mode", True),
                    application_id=task_data.get("application_id"),
                    company_id=task_data.get("company_id"),
                ),
                timeout=timeout,
            )
            await self.complete_task(task_id, {"response": result})
        except Exception as e:
            logger.error(f"[WorkerQueue] Inline fallback failed: {e}")
            await self.complete_task(task_id, {"error": str(e)})
        return task_id

    async def wait_for_result(
        self, task_id: str, timeout: int = 120
    ) -> Optional[Dict[str, Any]]:
        start_time = time.time()
        result_key = f"{self.result_prefix}{task_id}"

        r = await self._get_redis()

        while time.time() - start_time < timeout:
            if r is None:
                return None
            result = await r.get(result_key)
            if result:
                await r.delete(result_key)
                await r.delete(f"{self.task_prefix}{task_id}")
                return json.loads(result)
            await asyncio.sleep(0.5)

        logger.error(f"[WorkerQueue] Timeout waiting for task {task_id}")
        return None

    async def get_next_task(self) -> Optional[Dict[str, Any]]:
        r = await self._get_redis()
        if r is None:
            return None
        result = await r.brpop(self.queue_name, timeout=5)
        if result:
            task_id = result[1]
            task_data_raw = await r.get(f"{self.task_prefix}{task_id}")
            if task_data_raw:
                return json.loads(task_data_raw)
        return None

    async def complete_task(self, task_id: str, result: Dict[str, Any]):
        r = await self._get_redis()
        if r is None:
            return
        result_key = f"{self.result_prefix}{task_id}"
        await r.set(result_key, json.dumps(result), ex=300)
        logger.info(f"[WorkerQueue] Completed task {task_id}")


# Singleton instance
interview_queue = InterviewWorkerQueue()
