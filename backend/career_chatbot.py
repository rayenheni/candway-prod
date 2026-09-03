import json

from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.ai.llm import call_groq_cascade
from backend.database import Job
from backend.logger import logger

SYSTEM_PROMPT_TEMPLATE = """You are Candway AI, an intelligent recruitment assistant for {company_name}. Your goal is to help candidates find jobs, answer their questions, and collect their information for follow-up.

ABOUT THE COMPANY:
{company_description}

OPEN POSITIONS:
{open_jobs_summary}

FAQ:
{faq_text}

CAPABILITIES:
1. Answer questions about the company, culture, benefits, and hiring process
2. Provide details about specific open positions
3. Pre-screen candidates by collecting their name, email, phone, desired role, and experience level
4. Suggest matching jobs based on candidate's declared skills and interests
5. Capture candidate information for follow-up
6. Offer to schedule interviews with recruiters
7. Transfer to a human recruiter when the candidate requests it

CONVERSATION STAGES:
- greeting: Initial welcome, ask what they're looking for
- exploring: Candidate is browsing jobs or asking questions
- screening: Collecting candidate details (name, email, phone, role, experience)
- capturing: Getting contact info for follow-up
- scheduling: Offering to schedule an interview
- complete: Conversation wrapping up

RULES:
- Be friendly, professional, and concise
- Always respond in the language the candidate is using
- If the candidate asks about a specific job, provide details from the open positions
- When the candidate shows interest in applying, start collecting their information
- Extract structured data from conversations: name, email, phone, role interest, experience level
- If a candidate asks for something outside your scope, politely redirect to job-related topics
- Suggest 2-3 quick reply options at the end of your responses
- When you have collected name AND email AND role interest, suggest scheduling an interview
- If the candidate seems frustrated or asks for a human, offer to transfer them

Respond with a JSON object in this format:
{{
    "reply": "Your friendly response here",
    "intent": "job_search|company_info|apply_intent|schedule|general_qa|talk_to_human",
    "captured_info": {{
        "name": "extracted name or null",
        "email": "extracted email or null",
        "phone": "extracted phone or null",
        "role_interest": "extracted role or null",
        "experience_level": "extracted level or null"
    }},
    "suggested_quick_replies": ["Option 1", "Option 2", "Option 3"],
    "conversation_stage": "greeting|exploring|screening|capturing|scheduling|complete",
    "should_search_jobs": false,
    "job_search_query": "search terms if should_search_jobs is true",
    "should_save_lead": false,
    "should_schedule": false,
    "should_transfer": false
}}"""


class CareerChatbot:
    @staticmethod
    def get_system_prompt(
        company_name: str, company_description: str, open_jobs: list, faq: list
    ) -> str:
        jobs_summary = ""
        if open_jobs:
            for j in open_jobs[:10]:
                jobs_summary += f"- {j.get('title', 'N/A')} | {j.get('company', company_name)} | {j.get('location', 'Remote')} | Skills: {j.get('required_skills', 'N/A')}\n  {j.get('description', '')[:200]}...\n"

        faq_text = ""
        if faq:
            for item in faq:
                faq_text += (
                    f"Q: {item.get('question', '')}\nA: {item.get('answer', '')}\n\n"
                )

        return SYSTEM_PROMPT_TEMPLATE.format(
            company_name=company_name,
            company_description=company_description
            or "A modern company hiring top talent.",
            open_jobs_summary=jobs_summary or "No open positions at this time.",
            faq_text=faq_text or "No FAQ configured.",
        )

    @staticmethod
    async def detect_intent(message: str, history: list) -> str:
        messages = [
            {
                "role": "system",
                "content": "Classify the user's intent. Respond with exactly one word: job_search, company_info, apply_intent, schedule, talk_to_human, or general_qa",
            },
            {"role": "user", "content": message},
        ]
        try:
            result = await call_groq_cascade(
                messages, temperature=0.1, max_tokens=50, json_mode=False
            )
            if isinstance(result, str):
                result = result.strip().lower()
                valid = {
                    "job_search",
                    "company_info",
                    "apply_intent",
                    "schedule",
                    "talk_to_human",
                    "general_qa",
                }
                for v in valid:
                    if v in result:
                        return v
        except Exception as e:
            logger.error(f"Intent detection failed: {e}")
        return "general_qa"

    @staticmethod
    async def search_jobs(query: str, db: Session, limit: int = 5) -> list:
        try:
            q = f"%{query}%"
            jobs = (
                db.query(Job)
                .filter(
                    Job.is_active,
                    Job.deleted_at.is_(None),
                    or_(
                        Job.title.ilike(q),
                        Job.description.ilike(q),
                        Job.required_skills.ilike(q),
                        Job.company_name.ilike(q),
                    ),
                )
                .order_by(Job.created_at.desc())
                .limit(limit)
                .all()
            )

            return [
                {
                    "id": j.id,
                    "title": j.title,
                    "company": j.company_name,
                    "location": j.location or "Remote",
                    "type": j.type,
                    "salary_range": j.salary_range,
                    "description": j.description[:300] if j.description else "",
                    "required_skills": j.required_skills or "",
                }
                for j in jobs
            ]
        except Exception as e:
            logger.error(f"Job search failed: {e}")
            return []

    @staticmethod
    async def handle_message(
        message: str, conversation_history: list, context: dict, db: Session
    ) -> dict:
        try:
            trimmed_history = (
                conversation_history[-20:]
                if len(conversation_history) > 20
                else conversation_history
            )

            company_name = context.get("company_name", "Candway")
            company_desc = context.get(
                "company_description", "AI-Powered Recruitment Platform"
            )
            faq = context.get("faq", [])

            open_jobs = (
                db.query(Job)
                .filter(
                    Job.is_active,
                    Job.deleted_at.is_(None),
                )
                .order_by(Job.created_at.desc())
                .limit(20)
                .all()
            )

            open_jobs_data = [
                {
                    "title": j.title,
                    "company": j.company_name
                    or (j.company.name if j.company else "Unknown"),
                    "location": j.location or "Remote",
                    "required_skills": j.required_skills or "",
                    "description": j.description or "",
                }
                for j in open_jobs
            ]

            system_prompt = CareerChatbot.get_system_prompt(
                company_name, company_desc, open_jobs_data, faq
            )

            messages = [{"role": "system", "content": system_prompt}]

            for h in trimmed_history:
                if h.get("role") in ("user", "assistant"):
                    messages.append({"role": h["role"], "content": h["content"]})

            if context.get("page") == "job_details" and context.get("job_id"):
                job = db.query(Job).filter(Job.id == context["job_id"]).first()
                if job:
                    messages.append(
                        {
                            "role": "user",
                            "content": f"[Context: The user is viewing the job '{job.title}' at {job.company_name}. Description: {job.description[:300]}]",
                        }
                    )

            messages.append({"role": "user", "content": message})

            result = await call_groq_cascade(
                messages, temperature=0.3, max_tokens=1024, json_mode=True
            )

            if isinstance(result, dict) and "reply" in result:
                return result
            if isinstance(result, str):
                try:
                    parsed = json.loads(result)
                    if isinstance(parsed, dict) and "reply" in parsed:
                        return parsed
                except (json.JSONDecodeError, TypeError):
                    pass

            return {
                "reply": str(result)
                if result
                else "I'm here to help you find your next role! What kind of position are you looking for?",
                "intent": "general_qa",
                "captured_info": {},
                "suggested_quick_replies": [
                    "View open positions",
                    "Tell me about the company",
                    "I want to apply",
                ],
                "conversation_stage": "exploring",
                "should_search_jobs": False,
                "job_search_query": None,
                "should_save_lead": False,
                "should_schedule": False,
                "should_transfer": False,
            }

        except Exception as e:
            logger.error(f"Chatbot handle_message failed: {e}")
            return {
                "reply": "I'm sorry, I'm having a bit of trouble. Could you please try again?",
                "intent": "general_qa",
                "captured_info": {},
                "suggested_quick_replies": ["Show me jobs", "Talk to a recruiter"],
                "conversation_stage": "exploring",
            }

    @staticmethod
    def capture_candidate_info(message: str, existing_data: dict) -> dict:
        import re

        result = dict(existing_data or {})

        email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        email_match = re.search(email_pattern, message)
        if email_match and not result.get("email"):
            result["email"] = email_match.group()

        phone_pattern = (
            r"(?:\+?212|0|216|)?[-\s.]?\(?[0-9]{3}\)?[-\s.]?[0-9]{3}[-\s.]?[0-9]{4,6}"
        )
        phone_match = re.search(phone_pattern, message)
        if phone_match and not result.get("phone"):
            result["phone"] = phone_match.group().strip()

        name_patterns = [
            r"(?:my name is|I'm |i am |call me )([A-Za-z]+(?:\s+[A-Za-z]+)?)",
            r"name(?:'s| is) ([A-Za-z]+(?:\s+[A-Za-z]+)?)",
        ]
        for pat in name_patterns:
            m = re.search(pat, message, re.IGNORECASE)
            if m and not result.get("name"):
                result["name"] = m.group(1).strip()
                break

        role_keywords = [
            r"(?:looking for|interested in|applying for|want to be a|want to work as|role in|position as) ([A-Za-z\s]+?)(?:\.|,|!|$| role| position)",
            r"(?:software|frontend|backend|full.?stack|data|devops|ML|AI|machine learning|product|designer|engineer|developer|manager|analyst|scientist|architect)",
        ]
        for pat in role_keywords:
            m = re.search(pat, message, re.IGNORECASE)
            if m and not result.get("role_interest"):
                result["role_interest"] = (
                    m.group(1).strip() if m.lastindex else m.group(0).strip()
                )
                break

        exp_pattern = r"(?:experience|senior|junior|mid.level|entry.level|lead|principal) (?:level:?\s*)?(\w+)"
        exp_match = re.search(exp_pattern, message, re.IGNORECASE)
        if exp_match and not result.get("experience_level"):
            result["experience_level"] = exp_match.group(1)

        return result
