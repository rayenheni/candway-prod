# P1-1: `Application.evaluation_state` — Deprecated Column Inventory

**Status:** ⚠️ NOT SAFE TO DROP — still actively read in production code

## Model Definition

`backend/database.py` ~line 399:
```python
evaluation_state = Column(Text, default="pending")
```

## Read Sites (Production Code) — 12 total

| # | File | Line | Code |
|---|------|------|------|
| 1 | `scoring_jobs.py` | 172 | `Application.evaluation_state == "override"` (SQLAlchemy query filter) |
| 2 | `scoring_jobs.py` | 192 | `_ev = app.evaluation_state` |
| 3 | `scoring_jobs.py` | 197 | `_eval_state = getattr(_ev, 'state', None) or app.evaluation_state` |
| 4 | `applications.py` | 502 | `_ev = app.evaluation_state` |
| 5 | `evaluation.py` | 102 | `_ev = app.evaluation_state` (foreground path) |
| 6 | `evaluation.py` | 111 | `_eval_state = (_es.status ...) or (_ev.evaluation_state ...)` (fallback) |
| 7 | `evaluation.py` | 161 | `_ev = app.evaluation_state` (background path) |
| 8 | `evaluation.py` | 164 | `_eval_state = (_es.status ...) or (_ev.evaluation_state ...)` (fallback) |
| 9 | `evaluation.py` | 801 | `_ev = app.evaluation_state` |
| 10 | `onboarding.py` | 1238 | `_ev = app.evaluation_state` |
| 11 | `interviews.py` (candidate) | 239 | `_ev = app.evaluation_state` |
| 12 | `test_interview.py` | 565, 587 | `assert test_application.evaluation_state == "failed"` (test assertions) |

## Write Sites

**None found in production code.** All writes now go through `sync_evaluation_state()` in `entity_writer.py`, which writes to `EvaluationSession.status`.

The `Application.evaluation_state` column is **read-only** as of the P0-1 refactor. It is never written to in production code—only read as a fallback when `EvaluationSession` is not yet available.

## Pattern

All reads follow the same pattern:
```python
_ev = app.evaluation_state                            # get the deprecated column
_eval_state = getattr(_ev, 'state', None) or _ev.evaluation_state  # try EvaluationSession first, fall back
```

This means reads are _tolerable_ (they try the canonical source first), but the column cannot be dropped until all these reads stop relying on `app.evaluation_state` entirely.

## Migration Path to Drop Column

1. Ensure `EvaluationSession.status` is always populated before any code reads `app.evaluation_state`
2. Replace each read site to use only `EvaluationSession.status` (remove `or app.evaluation_state` fallback)
3. Remove the column from the model in a migration
4. Remove the column from GDPR scrubbing lists in `gdpr_erasure.py` (line 275 area)

## Dependencies on This Column

- GDPR erasure: already lists `evaluation_state` in `_PII_APPLICATION_COLUMNS` (line 275) — must be removed when column is dropped
- `sync_evaluation_state()` in `entity_writer.py`: no longer writes to this column (writes only to `EvaluationSession.status`)
