# ADR-001: Scoring Architecture Remediation

**Status:** Accepted  
**Date:** 2026-06-12  
**Deciders:** Staff Architect  
**Driver:** Audit finding — multiple competing score sources, rubric_score hardcoded to 0

---

## Context

The previous scoring architecture had:

- **4 competing score values** per application (`EvaluationResult.final_score`, `Application.analysis_score`, `analysis_json.score`, `Application.cv_score`)
- **10 bypass paths** where scoring occurred outside the canonical rubric system
- **Critical bug**: `ScoringService.compute_final_score()` hardcoded `rubric_score = 0.0` at `backend/scoring_service.py:74`, causing rubric contribution to always be 0
- **Dead code**: `RecommendedVerdict` table fully defined by never written to
- **Broken verdict reads**: Multiple locations reading non-existent or hardcoded `None` verdict values

## Decision

### 1. Canonical Score Source

`EvaluationResult.final_score` is the **ONLY** canonical score.

All other score fields (`Application.analysis_score`, `analysis_json.score`, etc.) are **legacy mirrors** that must NOT be read by new code. They remain populated for backward compatibility.

### 2. Canonical Verdict Source

`EvaluationResult.verdict` (new column) is the canonical verdict field.

Legacy storage in `score_breakdown["verdict"]` JSON continues to be written for backward compatibility during migration. `RecommendedVerdict` table remains defined but is not written to by application code (retained for migration history).

### 3. Single Writer

Only `ScoringService` may write:
- `EvaluationResult.final_score` → via `compute_final_score()`
- `EvaluationResult.verdict` → via `set_verdict()`, `set_cv_only()`, `report_fraud()`
- `EvaluationResult.rubric_score` → via `compute_final_score(override_rubric_score=...)`

Any service writing scores or verdicts directly to DB violates the architecture.

## Changes Applied

### Critical Fix: rubric_score propagation

**File:** `backend/scoring_service.py:76`  
**Before:** `rubric_score = 0.0`  
**After:** `rubric_score = override_rubric_score if override_rubric_score is not None else 0.0`  
**Impact:** Rubric scores now propagate into `final_score`. The formula `cv*0.25 + rubric*0.40 + human*0.10 + coverage*0.25` now actually uses the rubric component.

**Also added:** `override_rubric_coverage_pct` parameter (line 66) so coverage can also propagate.

### Verdict Canonical Column

**File:** `backend/models/evaluation.py:170`  
**Added:** `verdict = Column(String(50), nullable=True, index=True)` on `EvaluationResult`  
**Migration:** `alembic/versions/e5f4d3c2b1a0_add_verdict_to_evaluation_result.py` — adds column + backfills from `score_breakdown["verdict"]` and `recommended_verdicts.decision`

### Campaign Upload Score Fix

**File:** `backend/routers/recruiter_campaigns/upload.py:129`  
**Before:** `ScoringService.compute_final_score(app, db, computed_by="campaign_upload")` (no overrides → score always 10)  
**After:** `compute_final_score(..., override_cv_score=final_score)` (uses AI-analyzed score)

### Rubric Evaluation Score Fix

**File:** `backend/routers/ai_interview/evaluation.py:313-316`  
**Before:** `compute_final_score(app, db, computed_by="evaluation_rubric")` (no overrides)  
**After:** `compute_final_score(app, db, computed_by="evaluation_rubric", override_rubric_score=rubric_overall, override_rubric_coverage_pct=rubric_overall)`

### Verdict Reader Fixes

| File | Before | After |
|------|--------|-------|
| `candidate/applications.py:804` | `_sc_verdict = None` | `ScoringService.get_canonical_verdict(app, db)` |
| `candidate/applications.py:1293` | `analysis.get("verdict", "Pending Review")` | 3-tier fallback from canonical verdict |
| `candidate/interviews.py:161` | `_sc_verdict = None` | Reads from `EvaluationResult.verdict` → `score_breakdown["verdict"]` |
| `candidate/interviews.py:245` | `_sc_verdict_i = None` | Same |
| `candidate/cv.py:505` | `app_record.verdict` (non-existent attr) | `score.verdict if score else None` |
| `candidate/profile.py:234` | `"verdict": None` | 3-tier fallback from canonical verdict |
| `entity_enricher.py:34` | `(s.score_breakdown or {}).get("verdict")` | `s.verdict or ...` (new column priority) |
| `recruiter_candidates/search.py:665` | `"verdict": None` | 3-tier fallback from canonical verdict |

### Analysis Score Reader Fix

**File:** `backend/routers/recruiter_candidates/scoring.py:1310`  
**Before:** `"analysis_score": app.analysis_score` (bypasses canonical)  
**After:** `"analysis_score": _sc_scores_final` (maps from canonical `final_score`)

### v3.1: Rubric Router Single-Writer Enforcement

**File:** `backend/scoring_service.py:59-67`  
**Added parameters** to `compute_final_score()`:
- `extra_breakdown: Optional[Dict[str, Any]] = None` — rubric-specific breakdown data merged into `score_record.score_breakdown` after canonical fields
- `confidence_lower: Optional[float] = None` — rubric confidence interval
- `confidence_upper: Optional[float] = None`

**File:** `backend/rubric/rubric_router.py:356-378`  
**Before:** Direct write to `EvaluationResult.final_score = summary.overall_score` (line 371), `EvaluationResult.score_breakdown = break_down` (line 374), and a separate constructor `EvaluationResult(final_score=summary.overall_score)` (line 393). These direct writes were then immediately overwritten by `ScoringService.compute_final_score()` at line 401, destroying the rubric-rich `score_breakdown` (category_scores, skill_scores, gaps).  
**After:** All writes route through `ScoringService.compute_final_score()` with `extra_breakdown=break_down`, `confidence_lower`, `confidence_upper`, and `override_rubric_coverage_pct`. The rubric-specific breakdown data is preserved by merging into `score_breakdown` after canonical fields.

### v3.1: Validation Placeholder Documentation

**File:** `backend/ai/validation.py:153-154`  
**Change:** Added docstring comment documenting that `EvaluationResult(final_score=0.0)` is a deliberate placeholder for "pending review" (NOT NULL constraint forces a value; 0.0 signals un-scored).

## Risks

| Risk | Mitigation |
|------|-----------|
| Existing API consumers depend on `analysis_score` field | Field name preserved in API; source changed to canonical final_score |
| Campaign uploads without AI analysis still get low scores | `override_cv_score=None` preserves previous behavior (no false inflation) |
| DB migration may be slow on large evaluation_results tables | Backfill uses single UPDATE with JSON_EXTRACT — optimized for MySQL |
| No test coverage for rubric_score propagation | Manual verification of formula: `cv*0.25 + rubric*0.40 + human*0.10` |
| v3.1: Rubric breakdown was destroyed by ScoringService overwrite | Now merged via `extra_breakdown` parameter in `compute_final_score()` |
| v3.1: `ai/validation.py` creates EvaluationResult directly (bypass) | v3.2: replaced with `scoring_status='NEEDS_REVIEW'` — no sentinel 0.0 |

### v3.2: Scoring State Machine Enforcement

**Goal:** Eliminate ALL numeric sentinel score values. Replace with explicit state machine.

**Model change:** `backend/models/evaluation.py:160-164`
- Added `scoring_status = Column(String(20), nullable=False, default="PENDING", index=True)`
- Values: `PENDING`, `SCORED`, `FAILED`, `NEEDS_REVIEW`
- Changed `final_score = Column(Float, nullable=False, ...)` → `nullable=True`
- `final_score` is ONLY valid when `scoring_status == 'SCORED'`

**Migration:** `alembic/versions/d6e7f8a9b0c1_add_scoring_status_state_machine.py`
- Adds column + index
- Backfills: `needs_review` → NEEDS_REVIEW, `final_score > 0` → SCORED, rest → PENDING
- Makes `final_score` nullable
- Adds check constraints

**Single-writer enforcement:**
| File | Change |
|------|--------|
| `scoring_service.py:compute_final_score` | Sets `scoring_status='SCORED'` |
| `scoring_service.py:report_fraud` | Sets `scoring_status='FAILED'`, clears `final_score=None` |
| `scoring_service.py:set_verdict` | No sentinel `final_score=0.0`; sets `scoring_status='SCORED'` |
| `rubric_router.py:273-276` | Replaced `final_score=0` with `scoring_status='PENDING'` |
| `ai/validation.py:_mark_needs_review` | Sets `scoring_status='NEEDS_REVIEW'`, no `final_score=0.0` |

**Ranking truth enforcement:**
| File | Line | Before | After |
|------|------|--------|-------|
| `scoring.py` | 1415, 1448, 1472 | `composite_score` sort | `final_score` sort |
| `search.py` | 263, 313 | `cv_score` in talent scout | `final_score` |
| `search.py` | 327 | `semantic_score` sort | `score` (final_score) sort |
| `bot_router.py` | 122 | `a.overall_score or a.cv_score` | canonical `evaluation_result.final_score` |
| `copilot_engine.py` | 82 | Cosine similarity sort | primary: `final_score`, secondary: similarity |

## Rollout Plan (v3.2)

1. Apply code changes (done)
2. Run migration `d6e7f8a9b0c1` to add `scoring_status` column, backfill, make `final_score` nullable
3. Run migration `e5f4d3c2b1a0` to add `verdict` column + backfill (if not already run)
4. Run `scripts/backfill_extracted_entities.py` to backfill verdicts from `score_breakdown`
5. Manual verification: check evaluation_results table has correct `scoring_status` values
6. Monitor: verify candidate rankings are stable (should be unchanged since SCORED status matches previous non-zero scores)
7. Deprecate: mark `Application.analysis_score` as deprecated in v3.next

## Consequences (v3.2)

**Positive:**
- No numeric sentinel values — scoring state is explicit via `scoring_status` enum
- `final_score` is NULL when not scored (no ambiguity between "scored 0" and "not yet scored")
- Single-writer rule fully enforced — 0 production violations remain
- All ranking endpoints use `EvaluationResult.final_score` as the sole sort key
- External systems (`assessment_service`, `scorecards`, `scoring_transparent`) confirmed ISOLATED/READ-ONLY
- `composite_score` no longer used as a ranking alias — `final_score` is the direct sort key

**Negative:**
- 27 test files still create `EvaluationResult` with hardcoded `final_score` (test seed data — acceptable)
- `analysis_columns.py` still writes legacy `Application.analysis_score` mirror (v3.next cleanup)
- `RecommendedVerdict` table remains dead code (cleanup deferred to v3.next)
- `scoring_transparent.py` still uses `composite_score` in its in-memory `ScoreBreakdown` dataclass (not persisted, not used for ranking)
