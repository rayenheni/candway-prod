import os

os.environ.setdefault(
    "DATABASE_URL",
    "sqlite:///file:test_scoring?mode=memory&cache=shared&uri=true",
)
os.environ.setdefault("TESTING", "true")
os.environ.setdefault("SECRET_KEY", "test_secret_key")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault(
    "CANDWAY_FIELD_ENCRYPTION_KEY",
    "bW5vdF9hX3JlYWxfa2V5X2Zvcl90ZXN0XzEyMzQ1Njc4OTAxMjM0NTY3ODkw",
)

from backend.scoring_service import CANONICAL_WEIGHTS


def canonical(cv, rubric, coverage, has_rubric):
    if has_rubric:
        return (
            cv * CANONICAL_WEIGHTS["cv"]
            + rubric * CANONICAL_WEIGHTS["rubric"]
            + coverage * CANONICAL_WEIGHTS["coverage"]
        )

    return cv * 0.75 + coverage * 0.25


def test_rubric_formula():
    assert canonical(80, 70, 90, True) == 77.5


def test_cv_only_formula():
    assert canonical(80, 0, 90, False) == 82.5


def test_zero_rubric_is_still_rubric():
    assert canonical(80, 0, 90, True) == 42.5
