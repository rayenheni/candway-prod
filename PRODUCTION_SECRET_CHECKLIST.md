# Production Secret Checklist

> Use this checklist before every production deployment.

## 1. Required Secrets

| # | Secret | Source | Verification |
|---|--------|--------|-------------|
| 1 | `SECRET_KEY` | `openssl rand -hex 32` | Unique per environment |
| 2 | `CANDWAY_FIELD_ENCRYPTION_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` | Present and valid |
| 3 | `DATABASE_URL` | Create dedicated user | No root user, no placeholder password |
| 4 | `MYSQL_ROOT_PASSWORD` | `openssl rand -base64 32` | Docker-only, not for app connection |
| 5 | `MYSQL_PASSWORD` | `openssl rand -base64 32` | Matches user in DATABASE_URL |
| 6 | `REDIS_PASSWORD` | `openssl rand -base64 32` | Present in REDIS_URL |
| 7 | `REDIS_URL` | `redis://:password@host:6379/0` | References REDIS_PASSWORD |
| 8 | `GROQ_API_KEY` | https://console.groq.com | Active, not expired, not placeholder |
| 9 | `SMTP_PASSWORD` | Gmail App Password | App-specific, not regular password |
| 10 | `ALLOWED_ORIGINS` | Your domain | No wildcards, no localhost |

## 2. Secret Isolation Rules

| Rule | Enforcement |
|------|-------------|
| No secret may appear in source code | Bandit + manual review |
| No `.env` file committed to git | `.gitignore` + pre-commit hook |
| No secret shared between environments | Unique per dev/staging/prod |
| No placeholder values in production | `startup.py` blocks on `changeme`/`your_` |
| No secrets in API responses | `mask_value()` in admin settings |
| No secrets in logs | `SecretStr` in Pydantic models |

## 3. Production Guardrails

- `config.py` raises `ValueError` if `SECRET_KEY` is missing
- `startup.py` raises `RuntimeError` if `CANDWAY_FIELD_ENCRYPTION_KEY` is missing
- `startup.py` blocks if `GROQ_API_KEY` contains placeholder value
- Admin settings API returns masked secrets (last 4 chars visible)
- All sensitive keys stored encrypted in `SystemConfig` table

## 4. Pre-Deploy Verification

```bash
# 1. Check no .env committed
git ls-files | grep -E '\.env$'

# 2. Scan for placeholder values
grep -rn "changeme\|your_\|REPLACE_WITH\|gsk_your" .env.production

# 3. Run security scan
bandit -r backend/ -ll -ii

# 4. Verify startup validates all keys
python -c "from backend.config import get_settings; s = get_settings(); print('OK')"

# 5. Check admin API masks secrets
curl -H "Authorization: Bearer $ADMIN_TOKEN" https://yourdomain.com/api/v1/admin/settings \
  | grep -E 'groq_api_key|smtp_password'
# Expected: "****...abc"
```

## 5. Incident Response: Secret Compromise

| Scenario | Action |
|----------|--------|
| `SECRET_KEY` leaked | Rotate immediately. All JWTs become invalid. All users must re-login. |
| `CANDWAY_FIELD_ENCRYPTION_KEY` leaked | Rotate, then re-encrypt all PII columns via `scripts/reencrypt_pii.py` |
| `GROQ_API_KEY` leaked | Revoke key in Groq console. Generate new key. |
| DB password leaked | Change password. Update DATABASE_URL. Restart app. |
| .env file committed to git | Rotate ALL secrets in file. Purge from git history with `git-filter-repo`. |

## 6. Secrets Never to Store

| Credential | Why | Alternative |
|-----------|-----|-------------|
| SSH private keys | Change per host | Use SSH certificates or SSM |
| Cloud provider keys | Massive blast radius | Use IAM roles / workload identity |
| Personal access tokens | Tied to individuals | Use service accounts |
| Database root password | Too privileged | Use app-specific user |
