# P2-1: Soft-Delete → Hard-Delete Migration Plan

**Goal:** Convert soft-delete (`deleted_at` column) to true cascading hard-delete for all 9 models that currently use the pattern.

**Status:** 📋 Plan only — NOT yet implemented.

---

## Current State

### Models with `deleted_at` Column

| # | Class | Table | `deleted_at` Line | Indexed? | CASCADE Child Tables |
|---|-------|-------|-------------------|----------|---------------------|
| 1 | `User` | `users` | 139 | Yes | `jobs`, `applications`, `comments`, `messages` |
| 2 | `BatchJob` | `batch_jobs` | 270 | Yes | None |
| 3 | `Application` | `applications` | 415 | Yes | `evaluation_sessions`, `interview_turns`, `evaluation_results`, `comments`, `notes` |
| 4 | `Comment` | `comments` | 676 | No | None |
| 5 | `Job` | `jobs` | 900 | Yes | `applications` |
| 6 | `Qualification` | `qualifications` | 969 | No | None |
| 7 | `Course` | `courses` | 1222 | Yes | None |
| 8 | `Message` | `messages` | 2072 | No | None |
| 9 | `Company` | `companies` | 2409 | No | `users`, `jobs` |

### Query Pattern

Consistent across the codebase:
```python
.query(Model).filter(Model.deleted_at.is_(None))
```

~30+ locations across routers, services, workers, scripts. One legacy exception: `admin/users.py:43` uses `User.deleted_at == None`.

### Set Pattern

- **Delete:** `obj.deleted_at = datetime.now(UTC)`
- **Restore:** `obj.deleted_at = None`

No reusable utility function exists. Only `AnalyticsService._alive(query, model)` is a shared helper.

---

## Migration Strategy

### Phase 1: Add Missing FKs with `ON DELETE CASCADE`

Currently, child tables reference parents but **may lack** explicit FK constraints or use `ON DELETE SET NULL`. Ensure all child tables have:

```sql
ALTER TABLE child_table
ADD CONSTRAINT fk_child_parent
FOREIGN KEY (parent_id) REFERENCES parent_table(id)
ON DELETE CASCADE;
```

### Phase 2: Add Hard-Delete Queries

For each model, add a function that hard-deletes records with `deleted_at IS NOT NULL`:

```python
def hard_delete_expired(model_class, db_session, older_than_days=30):
    cutoff = datetime.now(UTC) - timedelta(days=older_than_days)
    db_session.query(model_class).filter(
        model_class.deleted_at.is_not(None),
        model_class.deleted_at < cutoff
    ).delete(synchronize_session='fetch')
```

### Phase 3: Create Scheduled Job

Add a Celery/APScheduler task that runs daily:

1. Hard-delete expired soft-deleted records from all 9 models
2. Respect cascade order: children before parents
3. Log count of hard-deleted rows per model

### Phase 4: Audit & Remove Indexes

After sufficient time with no rollbacks needed:
- Drop the `deleted_at` column from each model
- Remove index `idx_<table>_deleted_at` where applicable
- Remove `Model.deleted_at.is_(None)` filters from queries (they become no-ops)
- Optionally keep the filters for safety if column remains in model

---

## Order of Operations

### Immediate (P2-1 Priority)

1. Audit existing FK constraints with `ON DELETE CASCADE` between all 9 tables
2. Add missing FK cascades (especially Application → EvaluationSession, Job → Application)
3. Create hard-delete utility function
4. Create scheduled cleanup job
5. Add `hard_delete_expired` call to existing maintenance tasks

### Future (Post-deployment)

6. After 30+ days with zero rollbacks, drop `deleted_at` columns
7. Remove `deleted_at.is_(None)` query filters
8. Remove `deleted_at = Column(...)` from model definitions

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Data loss from premature hard-delete | High | Use grace period (30+ days); log all deletions; support dry-run mode |
| Orphaned child records | Medium | Add FK CASCADE constraints before any hard-delete runs |
| Broken queries that still read `deleted_at` | Low | Column stays in model during grace period; filters remain no-ops |
| Restore requests after hard-delete | Medium | Implement archive table or backup-restore workflow if needed |
