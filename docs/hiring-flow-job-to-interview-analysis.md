# Candway — End-to-End Hiring Flow
### Job Creation + Rubric → AI Interview → Interview Analysis (Recruiter & Candidate Views)

> Code-verified explanation of the full business flow. All file/line references point to the current codebase (backend = FastAPI, frontend = React SPA).

---

## 1. Overview

Candway's core hiring loop connects **three players** through one continuous data pipeline:

1. **Recruiter** creates a Job, optionally attaches an **Evaluation Rubric**, and publishes it.
2. **Candidate** discovers the job, applies, and takes a **live AI interview** in the candidate platform.
3. **Recruiter** reviews the **AI interview analysis** (scoring, rubric breakdown, recommendation, trust) in their dashboard; the **candidate** sees their own results/feedback in theirs.

The central concept that ties all three together is the **Rubric** (`rubrics` table). It defines *what good looks like* for a role and is threaded through scoring on every step.

```
[Recruiter]              [Candidate]                  [Both]
 Job Wizard ──► Job ──► Public board ──► Apply ──► AI Interview ──► Analysis
     │            │          ▲                            │              │
     │            │          │                            │              │
     └─► Rubric ──┘          └── scored against the       ▼              ▼
         (criteria_json)         job's rubric       Recruiter view   Candidate view
```

---

## 2. Stage 1 — Job Creation & Evaluation Rubric

### 2.1 The Job Wizard (`/recruiter/jobs/new`)

Recruiters build a job through a **5-step wizard** (`frontend/src/features/recruiter/pages/job-wizard.tsx`) backed by `backend/routers/recruiter_job_wizard.py`.

| Frontend step | Backend endpoint | What it collects |
|---|---|---|
| 1. Basic Info | `POST /recruiter/jobs/wizard/start` then `PATCH /recruiter/jobs/wizard/{id}/step1` | Title, category (JobCategory), department, employment type, location, recruiter assignment, salary (AI-suggestable) |
| 2. Role & Outcomes | `PATCH .../step2` | Role overview, day-to-day, must-have outcomes |
| 3. Rubric Evaluation | `PATCH .../step3` + `PATCH .../step4` | **Rubric source** (3 options, see 2.2), skills/weights, evaluation categories, AI scoring config |
| 4. Pipeline | `PATCH .../step5` | Pipeline stages |
| 5. Review → Publish | `POST /recruiter/jobs/wizard/{id}/publish` | Review screen; publish flips `Job.is_active = True` |

**Progress gating** — `_compute_progress` (`recruiter_job_wizard.py`) tracks `completed_steps`. Since a wizard fix, steps 3+4 count as complete when `job.rubric_id` is set (a linked library rubric) *or* when inline `JobSkill` rows exist — so library-linked jobs can publish.

### 2.2 The three Rubric sources (Step 3)

A rubric is a reusable, versioned definition of *"what we evaluate"*. The wizard offers three ways to attach one:

1. **Use Existing Rubric** — pick from the rubric library (`GET /recruiter/campaigns/rubrics`); the wizard sends `skill_tree_id` and the backend sets `Job.rubric_id`.
2. **Create New Rubric** — navigates to the standalone Rubric Builder (`/skill-tree-create?return_to=/jobs/new?edit={jobId}`); after save it returns with `?rubric_id={id}` and auto-links it.
3. **Build Rubric Inline** — the old flat editor inside the wizard (skills + evaluation categories + AI config); creates `JobSkill`/`JobEvaluationFramework` rows and leaves `Job.rubric_id` NULL (no reusable library row).

**AI Scoring Configuration** is *always visible* regardless of rubric source (a prior bug hid it for library rubrics). It persists to `JobAIConfig`/`ai_config` and includes:
- Enable AI Scoring, Explain AI Decisions, Evidence-Based Scoring, Prioritize Verified Skills, Ignore Missing CV
- Min Recommended Score, Auto-Shortlist, Auto-Reject, Custom Instructions

> ⚠️ Current finding: `JobAIConfig` is persisted and surfaced but **not yet consumed** by the scoring engine — it is write-only for now (auto-shortlist/auto-reject/min-score are not enforced in the analysis pipeline).

### 2.3 The Rubric model

`Rubric` / `RubricDB` (table `rubrics`, model in `backend/rubric/scoring.py`):

| Field | Purpose |
|---|---|
| `title` | e.g. "Marketing Lead" |
| `job_id` | legacy **job-bound** rubrics only; `NULL` for standalone library rubrics |
| `criteria_json` | nested structure: `{categories: [{name, weight, skills: [{name, level, weight, required, keywords}]}]}` |
| `version` | increments on every edit |
| `is_active` | only the newest version is active |
| `company_id` | tenant isolation (company-scoped) |

**Versioning on edit** — `PUT /recruiter/skill-trees/{tree_id}` (`recruiter_skill_trees.py` `update_skill_tree`) deactivates the old row and inserts a new version row. A recent fix **re-points** `Job.rubric_id` / `BatchJob.rubric_id` from the old version to the new one so linked jobs keep working (previously they silently referenced the now-inactive version → "not linked to any job yet").

### 2.4 Where the rubric lives vs. inline rows

| Artifact | Used for | Created when |
|---|---|---|
| `rubrics` row (library) | Reusable, versioned rubric shared across jobs/campaigns; drives `RubricScoringDetail` scoring | "Use Existing" or "Create New" |
| `JobSkill` rows | Inline flat skill list (fallback mode) | "Build Inline" |
| `JobEvaluationFramework` | Inline categories/weights | "Build Inline" |
| `JobAIConfig` | AI scoring settings (write-only today) | any source |
| `BatchJob.rubric_id` | **Campaign** batch jobs reference a rubric the same way | campaign creation |

### 2.5 Publish & candidate-facing consumption

`POST /recruiter/jobs/wizard/{id}/publish` sets the job active. Candidates then see it via:
- `GET /jobs/public` (public board `/careers`) and `GET /jobs/public/{id}`
- `GET /candidate/jobs` (matches) — candidate job matching/search

At apply time the application is **linked to the job's rubric** (resolved via `Job.rubric_id`, falling back to the job-bound `RubricDB`). This is what lets the AI interview score against the correct rubric.

---

## 3. Stage 2 — The Candidate AI Interview

### 3.1 Applying

- `POST /candidate/applications` — candidate applies to a job → `Application` row.
- Application lifecycle statuses: `applied → screening → interviewing → offer → hired` (plus `pending`, `invited`, `analyzing`, `analysis_failed`, `failed`, `withdrawn`...).
- A candidate may also start a **direct interview** without a specific job: `POST /candidate/interviews/direct-start` (used during onboarding; takes `rubric_id`, role title, skills).

### 3.2 Starting the session

`POST /ai/interview/...` + `InterviewStarter.start()` (`backend/rubric/interview_starter.py`):
- Sets `app.interview_state = "in_progress"`.
- Creates an **`EntryPoint`** (source_type + source_id = the job) and persists a **config snapshot** (`EvaluationConfigSnapshot`) via `config_resolver.py`.
- Creates the **`EvaluationSession`** — the container that holds the whole interview's state and result.

The **config snapshot** (`ResolvedEvaluationConfig` in `config_snapshot.py`) freezes what the interview will use: rubric_id/version, total_questions (default 15), time_limit_seconds (default 1800), passing_score, max_score (100), interview_instructions, language, question_generation_prompt, evaluation_criteria, scoring_weights. Freezing the config means later rubric edits don't retroactively change an in-flight interview.

### 3.3 Question generation (AI)

`POST /ai/interview/generate-interview` (`ai_interview/questions.py`) — quota + access gated, prompt-injection sanitized. `generate_skill_driven_turn` (`backend/ai/interview.py:422`) produces interview questions grounded in the **job's skills/rubric**.

### 3.4 The live interview room (turn loop)

Frontend: `frontend/src/features/interviews/pages/interview-room.tsx`.
Backend: `POST /ai/interview/chat` (`backend/routers/ai_interview/chat.py`, ~1300 lines).

Per turn:
1. Candidate answers; the AI model scores the answer against the rubric.
2. `RubricScoringDetail` rows are written (skill, score, weight, feedback, matched keywords, missing competencies) — this is the *evidence trail*.
3. `InterviewTurn` rows record turn text + timestamps (`backend/interview_turns.py` `write_turn`).
4. `engine_v2_state` (in `Application.analysis_json`) holds live `score_breakdown`, `current_q_index`, `time_left` (countdown), per-turn score.
5. Proctoring (`POST /ai/interview/sync-proctoring`) records violations → trust penalties (`VIOLATION_PENALTIES`).
6. Optional video upload (`POST /ai/interview/upload-video`, `/upload-segment`).

### 3.5 Final evaluation (background)

`run_background_final_evaluation(application_id, company_id)` (`backend/routers/ai_interview/evaluation.py:53`):
- Own session, **validates company_id** (tenant-safe).
- Marks session `pending → running → completed`.
- **Rubric aggregation path** (preferred): reads `RubricScoringDetail` rows → `aggregate_scores()` (`backend/rubric/scoring_aggregator.py`) → `InterviewScoringSummary` (overall score, categories, skill_scores, coverage %).
- Fallback: `evaluate_complete_interview()` (Groq LLM, JSON-schema-validated, 300s timeout).
- All AI output passes `AIOutputValidator` (`backend/ai/validation.py`).
- Persists via **`ScoringService`** (`backend/scoring_service.py`) — the *single canonical writer* of `EvaluationResult`.

### 3.6 The canonical scoring formula

`backend/scoring_service.py`:

```
final_score = cv_score * 0.25 + rubric_score * 0.50 + rubric_coverage_pct * 0.25
```

If a job has **no rubric**: `cv_score` weight becomes 0.75 and rubric weight 0.0. Clamped to 0–100.

`human_integrity_score` is preserved in the database for historical compatibility but has **zero weight** in the canonical formula.

**Dimension weights** (used in turn-level adaptive scoring, `scoring_transparent.py`):
`Technical 0.40 · Communication 0.20 · Problem Solving 0.20 · Adaptability 0.10 · Confidence 0.10`, plus integrity/gaming penalties.

---

## 4. Stage 3 — AI Interview Analysis

### 4.1 The canonical analysis payload

`GET /recruiter/applications/{app_id}/scores` (`backend/routers/recruiter_candidates/scoring.py:1372`) returns **35 keys**. The important ones:

| Key | Meaning |
|---|---|
| `cv_score` | CV-based score (from `EvaluationResult`) |
| `overall_score` / `score` / `interview_score` / `analysis_score` | all alias `EvaluationResult.final_score` |
| `rubric_score`, `rubric_coverage_pct`, `rubric_version`, `scoring_model`, `rubric_available` | how rubric-driven the result is |
| `category_breakdown` | per-category rubric scores (`score_breakdown.category_scores`) |
| `skill_breakdown` | per-skill: `{name, score, is_required, assessed, category, explanation, evidence}` |
| `gaps` | missing/weak competencies |
| `evidence` | joined `RubricScoringDetail` rows: `{skill_name, turn_number, question, answer, matched_keywords, missing_competencies, explanation, final_score}` |
| `questions` | per-evidence `{id, title, category, duration, score, label, answer, justification}` |
| `ai_feedback` | `[{title, body}]` from skill explanations |
| `interview_details` | rubric version / score / coverage / assessed skills |
| `penalty_breakdown` | `{integrity_penalty, gaming_penalty, timing_penalty, proctoring_violations_count, trust_score}` |
| `trust` | `{score, coverage, quality, count}` |
| `recommendation` | `{label, status}` |
| `is_rubric_driven` | whether the result came from rubric scoring |

### 4.2 Recommendations & labels

| Threshold | Recommendation (scores API) | Label (PDF / background) |
|---|---|---|
| ≥ 75 / 80 | **Strong Hire** | Strong Hire / Exceptional |
| ≥ 60 / 65 | **Hire** | Recommended / Strong |
| ≥ 45 / 50 | **Consider** | Consider / Competent |
| < 45 / 40 | **Low Priority** | Not Recommended / Developing |

(First number = scores API at `scoring.py:1631`; second = `scoring_transparent.py:464`; `Manual Review Required` if integrity penalty ≥ 15.) Integrity penalties / proctoring violations can force manual review.

### 4.3 Trust score

`trust_score = max(0, 100 − integrity_penalty)`, where `integrity_penalty` is derived from proctoring violations (`scoring_transparent.py` `calculate_integrity_penalty`). Gaming attempts add +10.

---

## 5. Recruiter View (`/recruiter/interview-analysis`)

Frontend: `frontend/src/features/recruiter/pages/recruiter-interview-analysis.tsx` (rendered via role switcher from `router.tsx:306-308`). Loads `candidatesService.getAIScore(appId)` (= the 4.1 payload) + `getApplication(appId)` for meta.

**8 tabs**: `overview · answers · ai · insights · details · activity · advanced · skilltree` ("**Rubric Breakdown**").

- **Rubric Breakdown tab** — `data.rubric` category scores, `skill_breakdown` rows with AI justification, `evidence` answer/quote rows, `gaps`, stat cards (rubric score / coverage / version).
- **Pipeline stage advancement** — `NEXT_STAGE` map (`applied→screening→interviewing→offer→hired`) via `PUT /recruiter/applications/{id}/status`.
- **Notes** — `PUT /recruiter/applications/{id}/notes`.
- **Score override** — `POST /recruiter/applications/{app_id}/override-score` (writes `overrides` + `override_history`; clears `needs_review` when raising).
- **Compare** — `POST /recruiter/applications/compare` (2–5 candidates) and per-candidate `GET .../score-comparison` (Groq, 1 credit).
- **Ghost report** — `GET /recruiter/applications/{app_id}/ghost-data` (FeatureFlag `ghost_report`-gated; anonymized recruiter-ready report). Bulk variant: `POST /applications/bulk-ghost-data`.
- **Ranked candidates** — `GET /recruiter/jobs/{job_id}/candidates/ranked` (sorted by `final_score`).
- **Logs/transcript** — `GET /recruiter/applications/{app_id}/logs` (PII-stripped for non-Pro).

**PII masking**: non-Pro recruiters see masked names (`"X. Candidate"`), hidden emails/phones, stripped transcript logs — enforced at the API layer.

### 5.1 Offer flow (after a good interview)

`POST /recruiter/offers/send` (`backend/routers/recruiter_offers.py:173`) →
- Creates `Offer` (company-scoped, `signature_request_id` from e-sign envelope), sets `app.status = "offer"`, emails candidate, fires `offer_sent` webhook.
- Candidate responds via `POST /recruiter/offers/respond/{offer_id}?accept=...` → `accepted` → `app.status = "hired"`; `declined` → `offer_declined`.
- E-signature flow: `GET /{offer_id}/signing-url` + `esign-status`; signing marks `hired`.

---

## 6. Candidate View (`/candidate/interview-analysis`)

Frontend: `frontend/src/features/candidate/pages/interview-analysis.tsx` (632 lines) via role switcher. Loads `GET /candidate/interviews/{app_id}/analysis` (`candidate/interviews.py:328`).

**4 tabs**: `overview · questions · feedback · recommendation`.

What it contains:
- `score` + `score_label` (≥85 Excellent · ≥70 Good · ≥50 Fair · else Needs Work)
- `verdict`, `metrics`, `performance_overview`, per-question scores
- `score_timeline`, `highlights`, `interview_details`, `recommendations`, `roadmap`
- `skill_breakdown` + `gaps`
- Live-score fallback while the interview is still in progress (reads `engine_v2_state.score_breakdown.final_score`, then turn-average).

**History** — `candidate-interviews.tsx` → `GET /candidate/interviews/history` (`interviews.py:214`): each interview card shows role, company, status, **`days_remaining`** from a **7-day expiry window**; auto-expired past 7 days. Links to the analysis page.

**Extras**:
- Download report (PDF) → `GET /candidate/applications/{id}/pdf` (`pdf_generator.py` `generate_interview_pdf`).
- Reset interview → `POST /candidate/reset-interview` (max 10 / 24h).
- `candidate-profile.tsx` Activity Timeline + Skill Tree tabs surface interview/analysis events and skills to the candidate.

---

## 7. Data flow map (which table feeds what)

```
rubrics.criteria_json ──► EvaluationConfigSnapshot (frozen at start)
                              │
                              ▼
JobSkills / rubric skills ──► AI question generation (generate_skill_driven_turn)
                              │
                              ▼
             InterviewTurn rows + RubricScoringDetail (evidence per answer)
                              │
                              ▼
        EvaluationSession ──► run_background_final_evaluation (aggregate or LLM)
                              │
                              ▼
        ScoringService.compute_final_score ──► EvaluationResult (final_score, rubric_score)
                              │
              ┌───────────────┴────────────────┐
              ▼                                 ▼
   GET /recruiter/applications/{id}/scores    GET /candidate/interviews/{id}/analysis
   → RecruiterInterviewAnalysis (8 tabs)      → CandidateInterviewAnalysis (4 tabs)
```

---

## 8. Key architectural guarantees

1. **Single canonical scorer** — `ScoringService` (`backend/scoring_service.py`) is the only writer of `EvaluationResult`; optimistic-locked (`version_id_col` + `StaleDataError` retry).
2. **Tenant isolation everywhere** — `get_application_for_recruiter`/`get_job_for_recruiter` (404 on mismatch), background evaluation validates `company_id`, all `EvaluationResult`/`RubricScoringDetail` writes company-scoped.
3. **Rubric aggregation beats LLM** — deterministic `RubricScoringDetail` aggregation takes priority over the LLM evaluation; AI output is always schema-validated; failures return `None` (no fabricated scores).
4. **Config snapshotting** — a live interview is frozen to the rubric version/config it started with, so later edits never skew an in-flight evaluation.
5. **PII masking is unconditional** — non-Pro recruiters get anonymized candidate data.

---

## 9. Known gaps / current findings (as of this doc)

- **`ScoringService.set_evaluation_result(...)` is called but does not exist** — `backend/routers/ai_interview/evaluation.py:380` (inside `run_background_final_evaluation`'s happy path) calls a method that `ScoringService` (`backend/scoring_service.py`) never defines. **Both** scoring routes (rubric aggregation → line 253, and LLM `evaluate_complete_interview` → line 270) produce a `final_score` and flow into this call → `AttributeError` → caught by the outer `except` at `evaluation.py:464` which marks `evaluation_state="failed"` + session status `failed` and **re-raises**. Net effect: the AI-completion scoring path can mark the evaluation failed instead of persisting the result. The methods that DO exist are `compute_final_score` (:98), `set_cv_only` (:277), `set_verdict` (:305) — `set_evaluation_result` looks like a renamed/dead-call that needs repair or re-wiring.
- **`JobAIConfig` is write-only** — AI scoring settings (auto-shortlist/auto-reject/min-score) are persisted but not yet enforced by the analysis pipeline.
- **Application status CHECK constraint vs. offer flow** — `backend/models/ats/application.py:52` allows statuses `pending/screening/interviewing/offer/rejected/analyzed/failed/applied/invited/active/analyzing/analysis_failed/hired` but **not `offer_declined`**; `backend/routers/recruiter_offers.py:464` writes `app.status = "offer_declined"` on decline. On a DB enforcing the constraint this would fail the write (no issue on MySQL if the CHECK is non-strict in this DB's mode — verify on live DB).
