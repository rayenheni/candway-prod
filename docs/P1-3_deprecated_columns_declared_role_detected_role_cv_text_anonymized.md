# P1-3: Deprecated Columns `declared_role` / `detected_role` / `cv_text_anonymized`

**Status:** ❌ HEAVILY USED — 423+ total matches across 20+ files. NOT safe to drop.

---

## `declared_role` (111+ matches)

### Model
`Application.declared_role` — `Column(Text)` — candidate's self-reported target role.

### Read Sites (production)

| File | Lines | Pattern |
|------|-------|---------|
| `scoring_jobs.py` | 198, 283 | `getattr(_cv, 'declared_role', None) or app.declared_role` |
| `previews.py` | 141 | `app.declared_role or "General"` |
| `applications.py` | 395, 566 | `app.declared_role or "the position"` |
| `scoring.py` | 179, 330, 381, 757, 1447, 1533 | `getattr(..., 'declared_role', None) or app.declared_role` |
| `evaluation.py` | 322, 584, 851, 977, 1157, 1172, 1195, 1232 | Multiple read paths |
| `chat.py` | 405, 762, 986, 1083, 1105, 1165, 1170, 1208 | Heavy read + inline use |
| `session.py` | 241 | `app.declared_role or getattr(app, "job_title", ...)` |
| `questions.py` | 54, 133, 135, 147, 148, 267 | Question generation uses role |
| `recruiter_reengagement.py` | 131 | Read for display |
| `recruiter_interviews/scheduling.py` | 83-84 | `app.declared_role` as job title |
| `search.py` | 59, 81, 132, 230, 260, 310 | Search filter + display |
| `recruiter_candidates/search.py` | 92, 137, 161, 214, 226, 240, 253, 287, 337, 348, 367 | Heavy search query usage |

### Write Sites

| File | Lines | Pattern |
|------|-------|---------|
| `entity_writer.py` | 34, 54-55 | `obj.declared_role = declared_role` (in `sync_cv_document`) |
| `upload.py` | 329 | `declared_role=target_role or "Candidate"` |
| `test_interview.py` | 29, 54, 157, 652 | Test constructor args |
| `test_interview_turns.py` | 58 | Test constructor arg |

---

## `detected_role` (17 matches)

### Model
`Application.detected_role` — `Column(Text)` — AI-detected role from CV parsing.

### Read Sites (production)

| File | Lines | Pattern |
|------|-------|---------|
| `recruiter_candidates/search.py` | 93, 138, 162, 215, 227, 241, 254, 338, 348 | Search filter + display |

### Write Sites

| File | Lines | Pattern |
|------|-------|---------|
| `entity_writer.py` | 35, 56-57 | `obj.detected_role = detected_role` |

Read-only in practice. Only written via `sync_cv_document()`.

---

## `cv_text_anonymized` (32 matches)

### Model
`Application.cv_text_anonymized` — `Column(Text)` — PII-scrubbed CV text.

### Read Sites (production)

| File | Lines | Pattern |
|------|-------|---------|
| `scoring.py` | 756 | `getattr(..., 'cv_text_anonymized', None) or app.cv_text_anonymized` |
| `evaluation.py` | 321, 850 | `getattr(..., 'cv_text_anonymized', None) or app.cv_text_anonymized` |
| `chat.py` | 406 | `getattr(..., 'cv_text_anonymized', None) or app.cv_text_anonymized` |
| `questions.py` | 55 | `app.cv_text_anonymized or "No CV context available."` |
| `recruiter_candidates/search.py` | 84, 139, 216, 228, 242, 255, 338 | Search filter + display |
| `search.py` | 58, 94 | Search filter |

### Write Sites

| File | Lines | Pattern |
|------|-------|---------|
| `entity_writer.py` | 31, 48-49 | `obj.cv_text_anonymized = cv_text_anonymized` |
| `upload.py` | 132 | `sync_cv_document(..., cv_text_anonymized=scrub_pii(text))` |
| `test_interview.py` | 33, 161, 656 | Test constructor args |

---

## Cross-Cutting Concerns

### GDPR Erasure

All three columns are listed in `_PII_APPLICATION_COLUMNS` in `gdpr_erasure.py`:
```python
"cv_text", "cv_file_path", "cv_text_anonymized",  # cv_text_anonymized
"declared_role", "detected_role",                   # declared_role + detected_role
"evaluation_state", "extracted_skills", "cv_embedding", "analysis_json",
```

### Search Dependency

Search functionality in `recruiter_candidates/search.py` and `routers/search.py` uses these columns as SQLAlchemy query filters (`Application.declared_role.ilike(...)`, etc.). These cannot be removed until the search logic is rewritten to use the canonical source (`CVDocument` or `EvaluationSession`).

### Recommended Path

1. **Not safe to drop in current cycle.** All three columns are actively read and written.
2. When ready: migrate writes to `CVDocument` equivalents, update reads, update search queries to use `CVDocument` columns, then drop.
3. GDPR erasure list must be updated when columns are dropped.
