"""P0-01 FIX tests: alembic auto-upgrade gate and dead variable removal."""


def test_has_migrations_flag_is_gone():
    """The misleading ``_HAS_MIGRATIONS = False`` constant must no
    longer be set in app.py — alembic is the source of truth now."""
    from pathlib import Path

    src = Path("backend/app.py").read_text(encoding="utf-8")
    assert "_HAS_MIGRATIONS" not in src
    # And the comment must point at alembic + startup_event.
    assert "alembic" in src
    assert "startup_event" in src


def test_startup_alembic_check_uses_command_upgrade():
    """The startup event must use ``alembic.command.upgrade`` for
    the auto-upgrade path, gated by CANDWAY_ALEMBIC_AUTO_UPGRADE."""
    from pathlib import Path

    src = Path("backend/startup.py").read_text(encoding="utf-8")
    assert "CANDWAY_ALEMBIC_AUTO_UPGRADE" in src
    assert "alembic_command.upgrade" in src or "command.upgrade" in src
    # Must raise in production if the env var is not set and
    # migrations are out of date.
    assert "settings.is_prod" in src


def test_dockerignore_excludes_secrets_and_tests():
    from pathlib import Path

    src = Path(".dockerignore").read_text(encoding="utf-8")
    for required in (".env", ".git", "__pycache__", "tests/", "*.sqlite"):
        assert required in src, f"{required} must be in .dockerignore"
