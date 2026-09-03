import json
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.ai.engine import EVENTS_DIR, InterviewEngine
from backend.ai.state_machine import InterviewState, InterviewStateMachine
from backend.database import Application, Base, User
from backend.encryption import decrypt_text, is_encrypted

# Setup in-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    # Create a test user and application
    user = User(email="test@example.com", role="candidate")
    db.add(user)
    db.commit()

    app = Application(id=1, user_id=user.id, interview_state=InterviewState.IDLE.value)
    db.add(app)
    db.commit()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.mark.asyncio
async def test_state_machine_valid_transitions():
    assert (
        InterviewStateMachine.can_transition(
            InterviewState.IDLE, InterviewState.INITIALIZING
        )
        is True
    )
    assert (
        InterviewStateMachine.can_transition(
            InterviewState.IDLE, InterviewState.EVALUATING
        )
        is False
    )


@pytest.mark.asyncio
async def test_engine_transition(db):
    engine_inst = InterviewEngine(db)

    # Valid transition
    await engine_inst.transition_to(1, InterviewState.INITIALIZING, reason="Test Start")
    app = db.query(Application).filter(Application.id == 1).first()
    assert app.interview_state == InterviewState.INITIALIZING.value

    # Invalid transition: IDLE -> EVALUATING not allowed by state machine
    with pytest.raises(ValueError):
        await engine_inst.transition_to(1, InterviewState.EVALUATING)


@pytest.mark.asyncio
async def test_event_logging(db):
    engine_inst = InterviewEngine(db)
    app_id = 1

    # Clean up existing logs for app 1 if any
    log_path = os.path.join(EVENTS_DIR, f"app_{app_id}.events.jsonl")
    if os.path.exists(log_path):
        os.remove(log_path)

    await engine_inst.record_turn_start(app_id, 1, "Question 1")
    await engine_inst.record_answer(app_id, 1, "Answer 1")
    await engine_inst.record_evaluation(
        app_id, 1, {"current_score": 85, "answer_quality": "good"}
    )

    assert os.path.exists(log_path)

    with open(log_path, "r") as f:
        events = [json.loads(line) for line in f]

    assert len(events) == 3
    assert events[0]["event_type"] == "TURN_STARTED"
    assert events[1]["event_type"] == "ANSWER_RECEIVED"
    assert events[2]["event_type"] == "EVALUATION_COMPLETED"

    # Bug B-26: the event log writer now encrypts the ``data`` payload
    # so a leaked file is unreadable without the Fernet key. Tests
    # that need to read the payload must decrypt it explicitly.
    raw_data = events[2]["data"]
    if isinstance(raw_data, str) and is_encrypted(raw_data):
        raw_data = json.loads(decrypt_text(raw_data))
    assert raw_data["score"] == 85


if __name__ == "__main__":
    # Integration test for manual run
    pytest.main([__file__])
