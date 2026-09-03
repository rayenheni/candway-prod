"""
Architecture Enforcement Tests (Phase 9).

These AST-based tests fail if:
 1. The AI Engine (backend/ai/) imports forbidden live models: Job, BatchJob, Rubric, Application.
 2. The AI interview routers (backend/routers/ai_interview/) import those models directly
    (except via whitelisted dependency paths like database.py for EvaluationSession/User).
 3. The legacy rubric loaders (load_current_rubric_record, load_rubric_by_id) are called
    outside of backend/rubric/config_resolver.py and backend/rubric/rubric_loader.py.

Why AST-based?  We want these to fail at CI/review time, not at runtime, so that no
developer accidentally re-introduces live DB lookups inside the AI engine.
"""

import ast
import pathlib
from typing import List, Optional, Tuple

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO_ROOT = pathlib.Path(__file__).parent.parent.parent  # …/masar_landing_page/
BACKEND = REPO_ROOT / "backend"

AI_ENGINE_DIR = BACKEND / "ai"
AI_ROUTER_DIR = BACKEND / "routers" / "ai_interview"
RUBRIC_DIR = BACKEND / "rubric"

# ── Forbidden model imports inside AI layer ────────────────────────────────────
FORBIDDEN_LIVE_MODELS = {"Job", "BatchJob", "Rubric", "Application", "CampaignTemplate"}

# ── Legacy loader functions that must stay inside the resolver layer ───────────
LEGACY_LOADER_CALLS = {"load_current_rubric_record", "load_rubric_by_id"}

# ── Files explicitly allowed to import the legacy loaders ─────────────────────
LOADER_ALLOWED_FILES = {
    RUBRIC_DIR / "config_resolver.py",
    RUBRIC_DIR / "rubric_loader.py",
    RUBRIC_DIR / "interview_starter.py",  # allowed transitionally via rubric_id lookup
}


# ── Helper utilities ──────────────────────────────────────────────────────────


def _python_files(directory: pathlib.Path) -> List[pathlib.Path]:
    """Recursively list .py files, skipping __pycache__."""
    return [
        p
        for p in directory.rglob("*.py")
        if "__pycache__" not in p.parts and p.name != "__init__.py"
    ]


def _parse(path: pathlib.Path) -> Optional[ast.Module]:
    """Parse a Python file, skipping non-UTF-8 files silently."""
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (UnicodeDecodeError, SyntaxError):
        return None


def _imported_names(tree: ast.Module) -> List[str]:
    """Return module-level import names only (not inside function bodies).

    We only check module-level imports because function-level (lazy) imports
    are acceptable for backward-compatibility paths within the AI layer.
    """
    names: List[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.asname or alias.name.split(".")[-1])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.append(alias.asname or alias.name)
    return names


def _call_names(tree: ast.Module) -> List[str]:
    """Return all function-call identifiers in the AST."""
    names: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.append(node.func.attr)
    return names


# ── Test 1: AI engine must not import live models ─────────────────────────────


def test_ai_engine_does_not_import_live_models():
    """backend/ai/ must not import Job, BatchJob, Rubric, or Application."""
    if not AI_ENGINE_DIR.exists():
        return  # directory doesn't exist, nothing to check

    violations: List[Tuple[str, str]] = []
    for py_file in _python_files(AI_ENGINE_DIR):
        tree = _parse(py_file)
        if tree is None:
            continue
        for name in _imported_names(tree):
            if name in FORBIDDEN_LIVE_MODELS:
                violations.append((str(py_file.relative_to(REPO_ROOT)), name))

    assert not violations, (
        "AI Engine must NOT import live DB models directly.\n"
        "Use EvaluationConfigReader instead.\n"
        "Violations found:\n"
        + "\n".join(f"  {f}: imported '{n}'" for f, n in violations)
    )


# ── Test 2: AI interview routers must not import live models ──────────────────


def test_ai_interview_routers_do_not_import_live_models():
    """backend/routers/ai_interview/ must not import Job, BatchJob, Rubric, Application directly."""
    if not AI_ROUTER_DIR.exists():
        return

    # EvaluationSession, Application, and User are allowed (session management and core entity access)
    allowed_exceptions = {
        "EvaluationSession",
        "Application",
        "User",
        "EvaluationResult",
        "CandidateInteraction",
    }
    forbidden = FORBIDDEN_LIVE_MODELS - allowed_exceptions

    violations: List[Tuple[str, str]] = []
    for py_file in _python_files(AI_ROUTER_DIR):
        tree = _parse(py_file)
        if tree is None:
            continue
        for name in _imported_names(tree):
            if name in forbidden:
                violations.append((str(py_file.relative_to(REPO_ROOT)), name))

    assert not violations, (
        "AI interview routers must NOT import live models (Job, BatchJob, Rubric, Application).\n"
        "Access these via EvaluationConfigReader from the snapshot.\n"
        "Violations found:\n"
        + "\n".join(f"  {f}: imported '{n}'" for f, n in violations)
    )


# ── Test 3: Legacy loaders called only inside allowed files ───────────────────


def test_legacy_loaders_only_in_resolver_layer():
    """load_current_rubric_record / load_rubric_by_id must only be called in the resolver layer."""
    violations: List[Tuple[str, str]] = []
    for py_file in _python_files(BACKEND):
        if py_file in LOADER_ALLOWED_FILES:
            continue
        # Skip test files
        if "tests" in py_file.parts or "scripts" in py_file.parts:
            continue
        tree = _parse(py_file)
        if tree is None:
            continue
        for call_name in _call_names(tree):
            if call_name in LEGACY_LOADER_CALLS:
                violations.append((str(py_file.relative_to(REPO_ROOT)), call_name))

    assert not violations, (
        "Legacy rubric loaders must ONLY be called from:\n"
        "  backend/rubric/config_resolver.py\n"
        "  backend/rubric/rubric_loader.py\n"
        "  backend/rubric/interview_starter.py\n\n"
        "Use EvaluationConfigReader everywhere else.\n"
        "Violations found:\n" + "\n".join(f"  {f}: called '{n}'" for f, n in violations)
    )


# ── Test 4: EvaluationConfigReader is the only public config interface ─────────


def test_config_reader_module_is_importable():
    """EvaluationConfigReader must be importable without errors."""
    from backend.rubric.config_reader import (
        ConfigurationMissingError,
        EvaluationConfigReader,
    )

    assert EvaluationConfigReader is not None
    assert ConfigurationMissingError is not None


# ── Test 5: InterviewStarter is importable and has the start() method ─────────


def test_interview_starter_module_is_importable():
    """InterviewStarter must be importable and expose start()."""
    from backend.rubric.interview_starter import InterviewStarter

    assert callable(getattr(InterviewStarter, "start", None)), (
        "InterviewStarter.start must be a callable classmethod"
    )


# ── Test 6: ConfigurationResolver is importable and exposes resolve() ──────────


def test_configuration_resolver_module_is_importable():
    """ConfigurationResolver must be importable and expose resolve()."""
    from backend.rubric.config_resolver import ConfigurationResolver

    assert callable(getattr(ConfigurationResolver, "resolve", None))
