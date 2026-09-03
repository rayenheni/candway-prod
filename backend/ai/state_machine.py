from enum import Enum
from typing import Dict, Set


class InterviewState(str, Enum):
    NOT_STARTED = "not_started"  # Default state stored in DB; no interview active
    IDLE = "idle"  # Legacy alias kept for backward-compat reads
    INITIALIZING = "initializing"  # CV analyzed, pre-start settings being applied
    IN_PROGRESS = "in_progress"  # Chatting with the user
    PAUSED = "paused"  # Explicit pause or session timeout warning
    COMPLETED = "completed"  # 15 questions done or manual completion
    FAILED = "failed"  # Technical error or abandonment
    EVALUATING = "evaluating"  # Post-chat analysis running


# Accept either NOT_STARTED or legacy IDLE when reading DB rows
_LEGACY_STATE_ALIASES = {InterviewState.IDLE.value: InterviewState.NOT_STARTED}


def _canonical_state(value: str) -> str:
    return _LEGACY_STATE_ALIASES.get(value, value)


class InterviewStateMachine:
    """
    Strict state machine for managing AI Interview lifecycle.
    Prevents race conditions and invalid state jumps.
    """

    TRANSITIONS: Dict[InterviewState, Set[InterviewState]] = {
        InterviewState.NOT_STARTED: {
            InterviewState.INITIALIZING,
            InterviewState.IN_PROGRESS,
            InterviewState.COMPLETED,
            InterviewState.FAILED,
        },
        InterviewState.IDLE: {
            InterviewState.INITIALIZING,
            InterviewState.IN_PROGRESS,
            InterviewState.COMPLETED,
            InterviewState.FAILED,
        },
        InterviewState.INITIALIZING: {
            InterviewState.IN_PROGRESS,
            InterviewState.FAILED,
        },
        InterviewState.IN_PROGRESS: {
            InterviewState.PAUSED,
            InterviewState.EVALUATING,
            InterviewState.COMPLETED,  # session-timeout exit
            InterviewState.FAILED,
        },
        InterviewState.PAUSED: {InterviewState.IN_PROGRESS, InterviewState.FAILED},
        InterviewState.EVALUATING: {InterviewState.COMPLETED, InterviewState.FAILED},
        InterviewState.COMPLETED: {
            InterviewState.INITIALIZING
        },  # Allow restart only via re-init
        InterviewState.FAILED: {InterviewState.INITIALIZING},  # Allow retry
    }

    @classmethod
    def can_transition(
        cls, from_state: InterviewState, to_state: InterviewState
    ) -> bool:
        return to_state in cls.TRANSITIONS.get(from_state, set())

    @classmethod
    def from_db_value(cls, value: str) -> InterviewState:
        try:
            canonical = _canonical_state(value.lower())
            return InterviewState(canonical)
        except (ValueError, AttributeError):
            return InterviewState.NOT_STARTED

    @classmethod
    def validate_transition(cls, from_state: str, to_state: str):
        try:
            fs = InterviewState(_canonical_state(from_state))
            ts = InterviewState(_canonical_state(to_state))
        except ValueError as e:
            raise ValueError(f"Invalid state name: {e}")

        if not cls.can_transition(fs, ts):
            raise ValueError(f"Illegal transition from {from_state} to {to_state}")


def get_interview_strategy(skills: list, role_confidence: float) -> str:
    """
    STRICT 3-TIER PRIORITY:
    1. EXTRACTED_SKILLS (Any count > 0) -> skill-driven
    2. ROLE_CONFIDENCE (> 0.7)        -> role-driven
    3. FALLBACK                      -> general
    """
    if skills and len(skills) > 0:
        return "skill-driven"

    if role_confidence > 0.7:
        return "role-driven"

    return "general"


def initialize_engine_state(
    strategy: str,
    skills: list = None,
    initial_metrics: dict = None,
    max_turns: int = 15,
) -> dict:
    """
    Initializes the state object for the interview engine (v3.1 Hardened).
    Includes seeding for Talent Graph from CV metrics.
    """
    # Normalize skills to strings (defensive against legacy dict data)
    pool = []
    for s in skills or []:
        if isinstance(s, str):
            pool.append(s)
        elif isinstance(s, dict):
            name = s.get("name") or s.get("skill") or str(s)
            pool.append(name)
        elif s:
            pool.append(str(s))

    # Unified Skill Map (Dashboard Compatibility)
    default_metrics = {
        "Technical": 0,
        "Communication": 0,
        "Problem Solving": 0,
        "Adaptability": 0,
        "Confidence": 0,
        "Consistency": 0,
        "Soft Skills": 0,
    }
    live_metrics = initial_metrics if initial_metrics else default_metrics

    return {
        "turn": 0,
        "strategy": strategy,
        "focus_pool": pool,
        "verified_skills": [],
        "skill_scores": {s: [] for s in pool},  # {skill_name: [score1, score2]}
        "skill_depth": {s: 0 for s in pool},  # {skill_name: depth_level}
        "success_streak": {s: 0 for s in pool},  # {skill_name: consecutive_high_scores}
        "skill_attempts": {s: 0 for s in pool},  # {skill_name: total_probes}
        "live_skill_metrics": live_metrics,  # Live stats for Dashboard
        "history": [],  # [{q, a, focus, score, type}]
        "current_focus": None,
        "max_turns": max_turns,
        "early_exit": False,
        "terminated": False,
        "final_decision": None,
    }
