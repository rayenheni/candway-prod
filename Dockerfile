# =============================================================================
# Candway — Multi-stage build: React SPA (Node) + Backend (Python distroless)
# =============================================================================
#
# Stage 1 (frontend-builder): Node 22 alpine builds the Vite SPA into dist/
# Stage 2 (builder):          Python 3.11 slim compiles Python wheels
# Stage 3 (nginx):            nginx:alpine serves the React SPA + proxies API
# Stage 4 (runtime):          distroless Python runs FastAPI/Gunicorn
#
# In docker-compose, nginx depends on both runtime and uses shared volumes
# to serve static files from the frontend build.
# =============================================================================

# ---- STAGE 1: Frontend builder (React + Vite) --------------------------------
FROM node:22-alpine AS frontend-builder

WORKDIR /frontend

# Install dependencies first (layer cache — only re-runs on package.json change)
COPY frontend/package*.json ./
RUN npm ci --prefer-offline

# Copy source and build
COPY frontend/ .
RUN npm run build
# Output is in /frontend/dist/ (= static/app/ relative to project root)

# ---- STAGE 2: Python builder ------------------------------------------------
# Compile wheels into /install so we can copy just the artefacts
# into the distroless runtime layer.
FROM python:3.11-slim AS builder

WORKDIR /build

# System packages needed ONLY to compile C extensions.
# These do NOT land in the final image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first so Docker layer cache is preserved
# when only the source code changes.
COPY requirements.txt .

# Install into /install (a self-contained prefix we will copy
# wholesale into the runtime layer).
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt \
    && pip install --no-cache-dir --prefix=/install gunicorn

# Pre-create the uploads directory + a .keep file
RUN mkdir -p /build/staging/backend/uploads \
    && touch /build/staging/backend/uploads/.keep


# ---- STAGE 3: Nginx (serves React SPA, proxies /api to FastAPI) -------------
FROM nginx:1.27-alpine AS nginx

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy our nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy React SPA build output from frontend-builder
COPY --from=frontend-builder /frontend/dist /usr/share/nginx/html

EXPOSE 80 443
STOPSIGNAL SIGTERM
CMD ["nginx", "-g", "daemon off;"]


# ---- STAGE 4: FastAPI runtime (distroless) ----------------------------------
# distroless cc-debian12: glibc + libssl + ca-certificates + tzdata,
# running as the built-in `nonroot` user (uid 65532).
FROM gcr.io/distroless/cc-debian12:nonroot AS runtime

WORKDIR /app

# Copy the Python interpreter and all installed packages from
# the builder.
COPY --from=builder /usr/local /usr/local

# Copy the application source.
COPY --chown=nonroot:nonroot backend/ /app/backend/
COPY --chown=nonroot:nonroot alembic/ /app/alembic/
COPY --chown=nonroot:nonroot alembic.ini /app/alembic.ini
COPY --chown=nonroot:nonroot requirements.txt /app/requirements.txt

# Copy the pre-created uploads dir
COPY --from=builder --chown=nonroot:nonroot /build/staging/backend/uploads/ /app/backend/uploads/

# Create static/app directory for the SPA (populated at runtime if needed)
# Note: In the Docker Compose setup, nginx serves the SPA directly.
# This empty dir is only needed if running backend standalone (without nginx).
COPY --from=frontend-builder --chown=nonroot:nonroot /frontend/dist/ /app/static/app/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8000

EXPOSE 8000

STOPSIGNAL SIGTERM

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/monitoring/health', timeout=5)"

CMD ["gunicorn", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "backend.app:create_app()", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
