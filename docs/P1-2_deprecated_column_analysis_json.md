# P1-2: `Application.analysis_json` — Deprecated Column Inventory

**Status:** ❌ HEAVILY USED — 195+ matches across 15+ files. NOT safe to drop.

## Usage Summary

`analysis_json` is a JSON-bag column on `Application` that stores CV analysis, interview evaluation data, scoring results, etc. It is read and written extensively throughout the codebase.

## File-by-File Breakdown

### Production code (reads + writes)

| File | Read Count | Write Count | Usage Pattern |
|------|-----------|------------|---------------|
| `ai/scoring_jobs.py` | 9 | 1 (via sync_cv_document) | getattr fallback → json.loads → process → write back |
| `routers/ai_interview/evaluation.py` | 14 | 4 (via sync_cv_document) | Foreground + background eval: read, merge, write back |
| `routers/ai_interview/chat.py` | 2 | 1 (via sync_cv_document) | Read during chat, write updated analysis |
| `routers/ai_interview/session.py` | 2 | 0 | Display existing analysis data |
| `routers/ai_interview/media.py` | 1 | 1 (via sync_cv_document) | Read, modify, write |
| `routers/recruiter_candidates/applications.py` | 3 | 1 (via sync_cv_document) | Tag storage + display |
| `routers/recruiter_candidates/scoring.py` | 8 | 1 (via sync_cv_document) | Scoring; deep read/write |
| `routers/recruiter_enhancements/previews.py` | 1 | 0 | Simple read for display |
| `routers/onboarding.py` | 2 | 2 (1 sync_cv_document, 1 direct) | Onboarding data merge |
| `routers/candidate/applications.py` | 9 | 3 (via sync_cv_document) | Candidate-side: read, modify, write |
| `routers/candidate/jobs.py` | 1 | 0 | Display analysis on job listing |
| `routers/search.py` | 3 | 0 | Return analysis in search results |
| `routers/recruiter_candidates/search.py` | 2 | 0 | Search result display |
| `routers/recruiter_campaigns/candidates.py` | 1 | 0 | Campaign candidate display |
| `routers/recruiter_campaigns/upload.py` | 0 | 1 (via sync_cv_document) | Upload → analyze → write |
| `entity_writer.py` | 0 | 1 (sync_cv_document writes analysis_json) | Central write function |
| `gdpr_erasure.py` | 0 | 0 | Listed in `_PII_APPLICATION_COLUMNS` for scrubbing |

### Test code

| File | Lines | Usage |
|------|-------|-------|
| `test_interview.py` | 538 | Read for test assertions |

## Key Observation

The `getattr(_cv, 'analysis_json', None) or app.analysis_json` pattern is used everywhere. `_cv` refers to a `CVDocument` model which has its own `analysis_json` column. The code tries `CVDocument.analysis_json` first, falls back to `Application.analysis_json`.

**There is no canonical replacement.** `CVDocument.analysis_json` partially overlaps, but many paths write directly to `Application.analysis_json` without going through `CVDocument`.

## Migration Path

1. Migrate all data from `Application.analysis_json` → `CVDocument.analysis_json` (if not already synced)
2. Replace each read to use only `CVDocument.analysis_json`
3. Remove writes to `Application.analysis_json` in `sync_cv_document()`
4. Drop the column in a migration
5. Remove from `gdpr_erasure.py` `_PII_APPLICATION_COLUMNS`

This is a **large, high-risk** migration and is not recommended for the current deployment cycle.
