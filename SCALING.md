# Horizontal Scaling Guide

## Architecture Overview

```
User → Nginx (reverse proxy / TLS termination)
         ↓
    Gunicorn workers (stateless FastAPI)
         ↓
    ┌──────┬──────┬──────┐
    │ MySQL │ Redis │ S3   │  (stateful — scale up, not out)
    └──────┴──────┴──────┘
```

All application state lives in MySQL (applications, users, scores) and Redis (rate limiter, token blacklist, session cache). Gunicorn workers are **stateless** — they can be scaled horizontally behind the load balancer.

## Scaling Gunicorn Workers

### Current config (4 workers, 2 threads):
```bash
gunicorn backend.app:app --worker-class uvicorn.workers.UvicornWorker --workers 4 --threads 2
```

### Small deployment (2 vCPU / 4 GB):
```
--workers 2 --threads 4
```

### Medium deployment (4 vCPU / 8 GB):
```
--workers 4 --threads 4
```

### Large deployment (8 vCPU / 16 GB):
```
--workers 8 --threads 2
```

**Formula**: `workers = (2 × vCPU) + 1` for CPU-bound, or `workers = vCPU` for I/O-bound with threads.

## Multi-Worker Considerations

### Redis-backed shared cache
The `system_config_cache.py` module uses Redis instead of a process-local dict, so all `n` workers share the same cached SystemConfig. Every worker reads from the same Redis key with a 60-second TTL.

**Required**: Set `REDIS_URL` in all environments. The cache degrades gracefully (falls back to empty dict) if Redis is unavailable.

### Rate limiting
The `RateLimitMiddleware` uses Redis-backed sliding window counters. Each worker increments the same Redis counter, so rate limits are enforced globally — not per-worker.

### Token blacklist
The `token_blacklist` module uses Redis with a shared key prefix (`candway_blacklist:*`). Logging out on one worker invalidates the token for all workers.

### Audit trail
The `ai_audit_logs` table in MySQL is the single source of truth. All workers write to the same table. The `log_ai_call()` function opens a new DB session per write — safe for concurrent workers.

### Scheduled jobs
`APScheduler` runs in the **primary worker only**. In multi-instance deployments (multiple containers), only one container should run the scheduler. Use `SCHEDULER_ENABLED=true/false` env var to designate the primary.

## Database Connection Pooling

SQLAlchemy is configured with:
```python
engine = create_engine(DATABASE_URL, pool_size=10, max_overflow=20)
```

With 4 workers, this allows up to `4 × (10 + 20) = 120` concurrent DB connections. Adjust `pool_size` based on MySQL's `max_connections`:
```
max_connections >= workers × (pool_size + max_overflow)
```

## Redis Connection Pooling

The app creates one Redis connection per module (dependencies, token_blacklist, system_config_cache, rate_limiter). Each connection uses a separate `redis.asyncio.from_url()`.

For high-traffic deployments, use a connection pool:
```python
import redis.asyncio as aioredis
pool = aioredis.ConnectionPool.from_url(REDIS_URL, max_connections=50)
```

## Redis Sentinel / Cluster

For production HA, replace the single Redis instance with Redis Sentinel:

`docker-compose.ha.yml`:
```yaml
redis-sentinel:
  image: bitnami/redis-sentinel:latest
  environment:
    - REDIS_MASTER_HOST=redis-master
    - REDIS_MASTER_PORT_NUMBER=6379

redis-master:
  image: bitnami/redis:latest
  environment:
    - REDIS_REPLICATION_MODE=master

redis-replica:
  image: bitnami/redis:latest
  environment:
    - REDIS_REPLICATION_MODE=slave
    - REDIS_MASTER_HOST=redis-master
```

## Multi-Instance Deployment

### Kubernetes (k8s) deployment:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: candway-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: candway-backend
  template:
    metadata:
      labels:
        app: candway-backend
    spec:
      containers:
        - name: backend
          image: candway/backend:latest
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: db-secret
                  key: url
            - name: REDIS_URL
              valueFrom:
                secretKeyRef:
                  name: redis-secret
                  key: url
            - name: SCHEDULER_ENABLED
              value: "false"  # Only one pod runs the scheduler
          ports:
            - containerPort: 8000
          livenessProbe:
            httpGet:
              path: /api/v1/monitoring/health
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 15
          resources:
            requests:
              cpu: "500m"
              memory: "512Mi"
            limits:
              cpu: "2"
              memory: "2Gi"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: candway-scheduler
spec:
  replicas: 1
  selector:
    matchLabels:
      app: candway-scheduler
  template:
    metadata:
      labels:
        app: candway-scheduler
    spec:
      containers:
        - name: scheduler
          image: candway/backend:latest
          command: ["python", "-m", "backend.scheduler_main"]
          env:
            - name: SCHEDULER_ENABLED
              value: "true"
```

### Environment Variables for Scaling

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKERS` | `4` | Gunicorn worker count |
| `WORKER_THREADS` | `2` | Threads per worker |
| `DB_POOL_SIZE` | `10` | SQLAlchemy pool size |
| `DB_MAX_OVERFLOW` | `20` | SQLAlchemy max overflow |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `SCHEDULER_ENABLED` | `true` | Run APScheduler in this process |
| `PROMETHEUS_MULTIPROC_MODE` | `all` | Required for multi-worker Prometheus metrics |

## Prometheus Multi-Process Mode

When running multiple Gunicorn workers, Prometheus metrics must be collected using multiprocess mode:

```python
from prometheus_client import multiprocess
from prometheus_client import generate_latest, CollectorRegistry

registry = CollectorRegistry()
multiprocess.MultiProcessCollector(registry)
data = generate_latest(registry)
```

Set environment:
```
PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_metrics
prometheus_multiproc_dir=/tmp/prometheus_metrics
```

## Tenant Isolation (Multi-Tenant)

Company-level data isolation is enforced at the application layer:

1. JWT contains company membership (embedded at login)
2. `get_current_user()` attaches `_company_id` to the user object
3. `tenant.py` provides `get_current_company()` and `company_scoped_query()` helpers
4. All recruiter endpoints filter by `company_id`

Every `Application` record has a `company_id` column (nullable for backward compatibility with existing data).

## Health Checks

| Endpoint | Purpose | Auth |
|----------|---------|------|
| `GET /api/v1/monitoring/health` | DB + disk + memory health | Public |
| `GET /api/v1/monitoring/status` | High-level system status | Public |
| `GET /api/v1/monitoring/metrics/prometheus` | Prometheus scrape endpoint | Public |

## Monitoring Stack

- **Prometheus**: Scrapes `/api/v1/monitoring/metrics/prometheus` every 15s
- **Grafana**: Dashboards for interview throughput, AI latency, error rates, drift
- **Redis**: Tracks active sessions, rate limit counters, token blacklist

## Capacity Planning

### Per-1000-concurrent-users:
- **Compute**: 2× 4-vCPU instances (with 1 standby for HA)
- **Memory**: 8 GB RAM per instance
- **Database**: MySQL 8.0 with 4 vCPU / 16 GB RAM
- **Redis**: 2 GB RAM (1 master, 1 replica with Sentinel)
- **Storage**: 50 GB SSD for MySQL + 10 GB for Redis persistence

### Bottlenecks to monitor:
1. **DB connection saturation** → increase `pool_size` or add read replicas
2. **Redis memory** → tune `maxmemory` and eviction policy (`allkeys-lru`)
3. **AI API rate limits** → distribute across multiple API keys
4. **Gunicorn worker timeout** → increase `--timeout` for long-running AI calls
