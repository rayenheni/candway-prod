import asyncio
import os
import sys

# Add project root to path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from backend.ai.interview import generate_dynamic_interview_turn
from backend.ai.worker import interview_queue
from backend.logger import logger


async def worker_loop():
    logger.info("Interview Worker started. Listening for tasks...")
    while True:
        try:
            task = await interview_queue.get_next_task()
            if not task:
                continue

            task_id = task["task_id"]
            data = task["data"]

            logger.info(f"Processing task {task_id} for app {data.get('app_id')}")

            try:
                result = await generate_dynamic_interview_turn(
                    cv_context=data.get("cv_context"),
                    declared_role=data.get("declared_role"),
                    history=data.get("history"),
                    current_q_index=data.get("current_q_index"),
                    current_score=data.get("current_score"),
                    total_questions=data.get("total_questions"),
                    language=data.get("language"),
                    job_title=data.get("job_title"),
                    job_description=data.get("job_description"),
                    initial_skills=data.get("initial_skills"),
                    seniority_level=data.get("seniority_level"),
                    interview_instructions=data.get("interview_instructions"),
                    instruction_state=data.get("instruction_state"),
                )

                await interview_queue.complete_task(task_id, result)
            except Exception as e:
                logger.error(f"Worker Error for task {task_id}: {e}", exc_info=True)
                await interview_queue.complete_task(
                    task_id, {"error": str(e), "type": "error"}
                )

        except Exception as e:
            logger.error(f"Global Worker Loop Error: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(worker_loop())
