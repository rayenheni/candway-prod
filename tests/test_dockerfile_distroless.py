"""P1-12: Production Dockerfile must use a distroless base image.

What this file locks
--------------------
1. The runtime image is `gcr.io/distroless/...` (no shell, no apt)
2. The build is multi-stage (a builder stage compiles C extensions,
   a runtime stage carries only the artefacts)
3. The runtime runs as the built-in `nonroot` user (uid 65532)
4. The `uploads/` directory is pre-created in the builder and
   copied into the runtime, so the app can write to it without
   needing a shell `mkdir` in the runtime
5. The CMD uses gunicorn + uvicorn workers and binds to 0.0.0.0
6. The `python:3.11-slim` and `debian:*` bases are NOT used in
   the runtime stage (they were the previous P1-12 violation)
7. The .dockerignore still excludes tests, secrets, dev artefacts

What this file does NOT cover
-----------------------------
* Actually building the image (no docker daemon in CI for unit tests)
* Image size (would require a registry to measure)
* Runtime CVE count (would require `trivy scan` or similar)
"""

from __future__ import annotations

import pathlib
import re

import pytest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
_DOCKERFILE = _REPO_ROOT / "Dockerfile"
_DOCKERIGNORE = _REPO_ROOT / ".dockerignore"


# ----------------------------- Dockerfile ---------------------------------

def _read_dockerfile() -> str:
    return _DOCKERFILE.read_text(encoding="utf-8")


def test_dockerfile_exists():
    assert _DOCKERFILE.exists(), "Dockerfile is missing"


def test_dockerfile_uses_distroless_runtime():
    """The runtime stage must be a distroless base."""
    src = _read_dockerfile()
    # Find the LAST `FROM` (the runtime stage in a multi-stage build)
    from_lines = [ln for ln in src.splitlines() if ln.strip().startswith("FROM ")]
    assert from_lines, "Dockerfile has no FROM instruction"
    last_from = from_lines[-1]
    assert "distroless" in last_from, (
        f"Final FROM is not distroless: {last_from!r}\n"
        "P1-12 requires the runtime image to be gcr.io/distroless/*"
    )


def test_dockerfile_is_multistage():
    """At least two `FROM` lines: a builder and a runtime."""
    src = _read_dockerfile()
    from_lines = [
        ln for ln in src.splitlines() if ln.strip().startswith("FROM ")
    ]
    assert len(from_lines) >= 2, (
        f"Expected multi-stage build, got {len(from_lines)} FROM lines:\n"
        + "\n".join(from_lines)
    )


def test_dockerfile_does_not_use_slim_or_debian_in_runtime():
    """The runtime image must NOT be python:slim, debian:*, or
    ubuntu:* - those are the bases the audit flagged.
    """
    src = _read_dockerfile()
    from_lines = [ln for ln in src.splitlines() if ln.strip().startswith("FROM ")]
    runtime_from = from_lines[-1]
    forbidden_substrings = [
        "python:3.11-slim",
        "python:3.12-slim",
        "debian:",
        "ubuntu:",
        "alpine",
    ]
    for bad in forbidden_substrings:
        assert bad not in runtime_from, (
            f"Runtime FROM contains {bad!r}: {runtime_from!r}\n"
            "Distroless is the only acceptable runtime base for P1-12."
        )


def test_dockerfile_copies_python_from_builder():
    """The runtime must NOT install pip packages; the Python +
    site-packages must come from the builder via COPY --from=.
    """
    src = _read_dockerfile()
    assert "COPY --from=builder /usr/local /usr/local" in src, (
        "Runtime must copy /usr/local from the builder stage.\n"
        "This is how we get a Python interpreter into a distroless base."
    )


def test_dockerfile_does_not_run_pip_in_runtime():
    """Pip is not in distroless - any `RUN pip install` in the
    runtime stage is a build error.
    """
    src = _read_dockerfile()
    from_lines = [ln for ln in src.splitlines() if ln.strip().startswith("FROM ")]
    # Split on FROM ... AS ... markers
    stages = re.split(r"^FROM .*?(?=^FROM |\Z)", src, flags=re.MULTILINE | re.DOTALL)
    # The LAST non-empty stage is the runtime
    runtime = [s for s in stages if s.strip()][-1]
    # distroless has no pip, so any "pip install" in the runtime
    # would fail at build time. Catch it.
    assert "pip install" not in runtime, (
        "Runtime stage contains `pip install` - distroless has no pip."
    )


def test_dockerfile_runs_as_nonroot():
    """The distroless `nonroot` variant is mandatory - it ships
    with uid 65532 baked in. We do NOT need (and MUST NOT add)
    a `USER appuser` or `useradd` line.
    """
    src = _read_dockerfile()
    from_lines = [ln for ln in src.splitlines() if ln.strip().startswith("FROM ")]
    runtime_from = from_lines[-1]
    assert "nonroot" in runtime_from, (
        f"Runtime FROM does not use the `nonroot` variant: {runtime_from!r}"
    )
    # If we add a USER line later, the distroless `nonroot`
    # variant still wins because the image's USER is baked in.
    # But we should not duplicate it.
    # Allow: the runtime might still set a different USER explicitly,
    # in which case we want it to be 65532. For now, do not allow
    # `useradd` in the runtime (no shell, no adduser, no apt).
    assert "useradd" not in src, (
        "Do not call `useradd` - distroless `nonroot` provides the user."
    )


def test_dockerfile_uses_gunicorn_uvicorn_in_cmd():
    """The CMD must be gunicorn with the uvicorn worker class,
    calling `backend.app:create_app()`.
    """
    src = _read_dockerfile()
    # The CMD block can be in either JSON exec form or shell form.
    # We require exec form (no shell in distroless).
    assert "CMD [" in src, "CMD must be in JSON exec form (no shell in distroless)"
    assert "uvicorn.workers.UvicornWorker" in src
    assert "backend.app:create_app()" in src
    # Must NOT be shell form (`CMD gunicorn ...` without brackets)
    # because distroless has no shell to interpret it.
    shell_cmd = re.search(r"^CMD\s+(?!\[)", src, flags=re.MULTILINE)
    assert not shell_cmd, (
        "CMD appears to be in shell form - use JSON exec form for distroless."
    )


def test_dockerfile_binds_to_all_interfaces_on_8000():
    src = _read_dockerfile()
    assert "--bind" in src
    assert "0.0.0.0" in src
    # 8000 is the canonical candway port
    assert "8000" in src
    # Must not bind to localhost only (would be unreachable in container)
    assert "--bind 127.0.0.1" not in src


def test_dockerfile_creates_uploads_dir_for_nonroot():
    """The distroless runtime has no mkdir. The uploads dir must
    be pre-created in the builder and copied over.
    """
    src = _read_dockerfile()
    # The builder must create the uploads dir
    assert "mkdir -p /build/staging/backend/uploads" in src, (
        "Builder stage must pre-create the uploads directory so the "
        "runtime can COPY it (distroless has no mkdir)."
    )
    # The runtime must COPY it
    assert "/app/backend/uploads/" in src, (
        "Runtime stage must COPY the uploads directory into /app/backend/uploads/"
    )


def test_dockerfile_exposes_8000():
    src = _read_dockerfile()
    assert "EXPOSE 8000" in src, "Dockerfile must EXPOSE 8000"


def test_dockerfile_sets_python_env_vars():
    src = _read_dockerfile()
    assert "PYTHONDONTWRITEBYTECODE=1" in src
    assert "PYTHONUNBUFFERED=1" in src
    assert "PYTHONPATH=/app" in src


def test_dockerfile_builder_compiles_wheels_with_gcc():
    """The builder needs gcc + libpq-dev to compile C extensions
    (cryptography, bcrypt, numpy, scipy, greenlet).
    """
    src = _read_dockerfile()
    assert "FROM python:3.11-slim AS builder" in src
    assert "gcc" in src
    assert "pip install" in src


# ----------------------------- .dockerignore ---------------------------------


def test_dockerignore_excludes_tests():
    """Tests must not bloat the production image."""
    src = _DOCKERIGNORE.read_text(encoding="utf-8")
    assert "tests/" in src
    assert "backend/tests/" in src


def test_dockerignore_excludes_secrets():
    src = _DOCKERIGNORE.read_text(encoding="utf-8")
    assert ".env" in src
    # Must not exclude the example env (CI / onboarding needs it)
    assert "!.env.example" in src


def test_dockerignore_excludes_python_cache():
    src = _DOCKERIGNORE.read_text(encoding="utf-8")
    for pat in ("__pycache__/", "*.py[cod]", ".pytest_cache/", ".venv/"):
        assert pat in src, f"Missing dockerignore pattern: {pat}"


def test_dockerignore_excludes_dev_scripts():
    src = _DOCKERIGNORE.read_text(encoding="utf-8")
    for pat in ("scripts/dev/", "scripts/probe_", "scripts/restart_", "scripts/seed_"):
        assert pat in src, f"Missing dockerignore pattern: {pat}"


# ----------------------------- High-level assertions --------------------------


def test_no_top_level_debian_in_dockerfile():
    """No FROM should be a bare `debian:*` or `ubuntu:*` image -
    those would be the worst-of-both-worlds (slim, but no distroless).
    """
    src = _read_dockerfile()
    from_lines = [ln for ln in src.splitlines() if ln.strip().startswith("FROM ")]
    for ln in from_lines:
        assert not re.search(r"FROM (debian|ubuntu):", ln), (
            f"Do not use bare debian: or ubuntu: in Dockerfile: {ln!r}"
        )


def test_no_sudo_in_dockerfile():
    """Distroless has no sudo. Even if it did, sudo in a container
    is a smell. Catch any regression.
    """
    src = _read_dockerfile()
    assert "sudo" not in src.lower(), "Dockerfile must not reference sudo"


def test_no_apt_get_in_runtime_stage():
    """Distroless has no apt. Any `apt-get` in the runtime stage
    would be a build error.
    """
    src = _read_dockerfile()
    from_lines = [ln for ln in src.splitlines() if ln.strip().startswith("FROM ")]
    stages = re.split(r"^FROM .*?(?=^FROM |\Z)", src, flags=re.MULTILINE | re.DOTALL)
    runtime = [s for s in stages if s.strip()][-1]
    assert "apt-get" not in runtime, (
        "Runtime stage contains `apt-get` - distroless has no apt."
    )


# ----------------------------- docker-compose.yml ----------------------------

_DOCKER_COMPOSE = _REPO_ROOT / "docker-compose.yml"


def test_docker_compose_healthcheck_uses_cmd_not_cmd_shell():
    """The backend service's healthcheck MUST be in JSON exec form
    (`CMD`) - not `CMD-SHELL` - because the distroless runtime
    has no shell to interpret `sh -c "..."`.

    If someone reverts this to `CMD-SHELL`, the healthcheck will
    silently fail in production and Docker will mark the
    container as unhealthy.

    This is a regex-based check (we don't want to add PyYAML to
    requirements just for a single config lint).
    """
    src = _DOCKER_COMPOSE.read_text(encoding="utf-8")
    # Find the backend service block
    backend_match = re.search(
        r"^  backend:.*?(?=^  \w|\Z)",
        src,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert backend_match, "docker-compose.yml has no `backend:` service"
    backend_block = backend_match.group(0)

    # The healthcheck.test must start with "CMD" not "CMD-SHELL"
    # The YAML form is either:
    #   test: [ "CMD-SHELL", "python -c ..." ]
    #   test:
    #     - "CMD"
    #     - "python"
    #     - "-c"
    #     - "..."
    # We look for the actual test directives.
    cmd_shell = re.search(r'"CMD-SHELL"', backend_block)
    assert not cmd_shell, (
        "Backend healthcheck uses `CMD-SHELL` - this requires a shell, "
        "which the distroless runtime image does NOT have. "
        "Use JSON exec form (`CMD`) instead."
    )
    # Must reference `python` directly as the executable
    assert '"python"' in backend_block, (
        "Backend healthcheck must call `python` directly "
        "(we copied it from the builder's /usr/local)."
    )
    # And the call must go to our health endpoint
    assert "/api/v1/monitoring/health" in backend_block, (
        "Backend healthcheck must hit /api/v1/monitoring/health"
    )
