# Candway Business Flow Documentation
## Job Creation → Rubric → AI Interview → Analysis

---

## Table of Contents
1. [Overview](#overview)
2. [Phase 1: Job Creation](#phase-1-job-creation)
3. [Phase 2: Rubric Creation & Linking](#phase-2-rubric-creation--linking)
4. [Phase 3: AI Interview Invitation](#phase-3-ai-interview-invitation)
5. [Phase 4: Interview Execution (Candidate Side)](#phase-4-interview-execution-candidate-side)
6. [Phase 5: Background Evaluation & Scoring](#phase-5-background-evaluation--scoring)
7. [Phase 6: Recruiter Analysis View](#phase-6-recruiter-analysis-view)
8. [Phase 7: Candidate Analysis View](#phase-7-candidate-analysis-view)
9. [Data Model Reference](#data-model-reference)
10. [Key Business Rules & Security](#key-business-rules--security)

---

## Overview

The Candway platform enables recruiters to create jobs, attach AI evaluation rubrics, invite candidates to AI-powered interviews, and review AI-generated analysis. The entire flow spans multiple backend services, background workers, and React frontend pages.

**Core entities involved:**
- **Job** — The position being hired for
- **Rubric** — A reusable evaluation framework with categories, skills, and weights
- **Application** — A candidate's submission for a specific job
- **EvaluationSession** — The live AI interview session
- **InterviewTurn** — Individual Q&A pairs within the session
- **EvaluationResult** — The final computed score and breakdown
- **EvaluationConfigSnapshot** — Immutable config frozen at interview start

---

## Phase 1: Job Creation

### 1.1 Entry Point

Recruiter navigates to `/jobs/new` → `frontend/src/features/recruiter/pages/job-wizard.tsx`

The wizard is a **5-step flow**:

| Step | Name | Backend Endpoint | What it saves |
|------|------|------------------|---------------|
| 1 | Basic Info | `POST /recruiter/jobs/wizard/start` then `PATCH /{id}/step1` | Job title, category, type, location, salary, hiring manager |
| 2 | Role & Outcomes | `PATCH /{id}/step2` | `JobRoleOverview` rows (4 Q&A fields + optional AI summary) |
| 3 | Rubric Evaluation | `PATCH /{id}/step3` | `JobSkill` rows + optional `job.rubric_id` link |
| 4 | Pipeline & AI Config | `PATCH /{id}/step4` | `JobEvaluationFramework` + `JobAIConfig` |
| 5 | Review & Publish | `POST /{id}/publish` | Sets `is_active=True`, denormalizes `required_skills` |

### 1.2 Step 1 — Basic Info

**Frontend** collects: title, category (company-scoped `JobCategory`), employment type, workplace type, location, openings count, hiring manager, salary range, internal reference.

**Backend** (`recruiter_job_wizard.py`):
- `POST /start` creates a draft `Job` row with `is_active=False`, `rubric_id=NULL`, `recruiter_id=current_user.id`, `company_id=tenant`.
- Returns `job_id` for subsequent steps.
- Step 1 data is validated via `Step1BasicInfo` Pydantic schema.

### 1.3 Step 2 — Role & Outcomes

Recruiter answers 4 structured questions about the role (e.g., "What does success look like in 90 days?"). Optional AI-generated summary via `POST /ai/generate-summary` (1 credit).

**Backend** saves `JobRoleOverview` rows (`question_key`, `question`, `answer`).

### 1.4 Step 3 — Rubric Evaluation (THE CRITICAL STEP)

This is where the job gets linked to an evaluation rubric. The frontend offers **three options**:

#### Option A: Use Existing Rubric
- Recruiter picks from `/recruiter/campaigns/rubrics` (integer IDs).
- Frontend sends `skill_tree_id: <integer>` in `PATCH /{id}/step3`.

#### Option B: Create New Rubric
- Frontend navigates to `/skill-tree-create?return_to=/jobs/new?edit={jobId}`.
- After creating the rubric, the builder redirects back to the wizard with `?rubric_id={id}`.
- The wizard auto-selects the new rubric and switches to "Use Existing Rubric" mode.

#### Option C: Build Rubric Inline
- Recruiter defines skills directly in the wizard (name, level, weight 1-100).
- No reusable rubric is created; skills live only in `JobSkill` rows.

**Backend logic** (`save_step3` in `recruiter_job_wizard.py`):
```python
# 1. Always delete old inline skills, then re-insert
db.query(JobSkill).filter(JobSkill.job_id == job.id).delete()
for idx, skill in enumerate(req.skills):
    db.add(JobSkill(company_id=job.company_id, job_id=job.id, ...))

# 2. Link rubric if skill_tree_id provided
if req.skill_tree_id:
    rubric = db.query(Rubric).filter(
        Rubric.id == req.skill_tree_id,
        Rubric.is_active,
        (Rubric.company_id == company_id) | (Rubric.company_id.is_(None)),
    ).first()
    if rubric:
        job.rubric_id = rubric.id   # ← THE LINK
```

**Result matrix:**

| Option | `skill_tree_id` sent | `job.rubric_id` after step 3 |
|--------|---------------------|------------------------------|
| Use Existing | Integer rubric ID | Set to that rubric's `id` |
| Create New | `null` initially | Set when returning from builder |
| Build Inline | `null` | Stays `NULL` |

### 1.5 Step 4 — Pipeline & AI Config

Recruiter configures:
- **Screening questions** (`JobScreeningQuestion` rows)
- **Pipeline stages** (`JobPipelineStage` rows)
- **AI Scoring Configuration** (always visible regardless of rubric option):
  - Enable AI Scoring
  - Explain AI Decisions
  - Evidence-Based Scoring
  - Prioritize Verified Skills
  - Ignore Missing CV
  - Minimum Recommended Score
  - Auto-Shortlist threshold
  - Auto-Reject threshold
  - Custom Instructions

Saved via `PATCH /{id}/step4` → `JobEvaluationFramework` + `JobAIConfig` rows.

### 1.6 Step 5 — Review & Publish

**Progress computation** (`_compute_progress`):
```python
steps = []
if job.title:                           steps.append(1)
if JobRoleOverview exists:              steps.append(2)
if JobSkill exists:                     steps.append(3)
if JobEvaluationFramework exists:       steps.append(4)
if job.rubric_id:                       steps.append(3), steps.append(4)  # library rubric satisfies both
if JobScreeningQuestion OR JobPipelineStage exists:  steps.append(5)
```

**Critical rule**: A linked library rubric (`job.rubric_id IS NOT NULL`) counts as completing **both** step 3 and step 4, because the rubric's skills/categories live in the `rubrics` row, not in inline `JobSkill`/`JobEvaluationFramework` rows.

**Publish gate** (`POST /{id}/publish`):
1. Validates all 5 steps have data
2. Checks recruiter's plan hasn't hit job-slot limit (`SubscriptionService.can_perform_action`)
3. Sets `is_active=True`
4. Denormalizes `required_skills` (comma-joined skill names from `JobSkill` rows)

---

## Phase 2: Rubric Creation & Linking

### 2.1 The Rubric Model

**Table**: `rubrics` (`backend/models/evaluation/scoring.py`)

```python
class Rubric(Base, TenantMixin):
    id              # Integer PK
    job_id          # FK → jobs.id (nullable — NULL = standalone library rubric)
    company_id      # TenantMixin (NOT NULL)
    version         # Integer (increments on edit)
    title           # String(255)
    description     # Text
    passing_score   # Float, default 0.0
    max_score       # Float, default 100.0
    weight          # Float, default 1.0
    criteria_json   # Text — JSON: [{name, skills: [{name,level,required,keywords}], weight}]
    skill_weights   # Text — JSON skill weight map
    complexity      # String(50), default "intermediate"
    created_by      # FK → users.id
    is_active       # Integer (1=active, 0=archived)
```

### 2.2 Standalone Rubric Creation

**Endpoint**: `POST /recruiter/skill-trees/standalone`

**Frontend**: `frontend/src/features/recruiter/pages/skill-tree-create.tsx`

**UI Structure**:
- Root node = "Categories" container (depth 0)
- Category nodes (depth 1, purple border) — each has a `weight` input
- Skill nodes (depth 2) — each has `name`, `level` select (beginner/intermediate/advanced/expert), `weight` input, `required` toggle

**Save payload** (`skillNodeToCategory`):
```json
{
  "name": "Senior Frontend Engineer",
  "categories": [
    {
      "name": "Technical Skills",
      "weight": 50,
      "skills": [
        { "name": "React", "level": "advanced", "weight": 40, "is_required": true, "keywords": [] }
      ]
    }
  ],
  "skill_count": 3
}
```

**Backend** (`recruiter_skill_trees.py`):
1. Validates via `StandaloneSkillTreeCreate` schema
2. Normalizes categories via `_normalize_categories()` — accepts both flat `{name, skills:[]}` and nested `{name, weight, subcategories:[]}` shapes
3. Creates `Rubric` row with `job_id=None` (standalone library rubric)
4. Returns the new rubric `id` (integer)

### 2.3 Rubric Edit (Versioning)

**Endpoint**: `PUT /recruiter/skill-trees/{tree_id}`

When a rubric is edited:
1. A **new version** is created (`version = old.version + 1`, `is_active=True`)
2. The old version is deactivated (`is_active=False`)
3. **Re-pointing**: `Job.rubric_id` and `BatchJob.rubric_id` are updated from the old version ID to the new one
4. This prevents orphaned job links after edits

### 2.4 AI Generate

**Endpoint**: `POST /recruiter/skill-trees/ai/generate`

**Flow**:
1. Takes `title` (required, max 200 chars) + optional `description` (max 1000 chars)
2. **Consumes 1 credit** via `consume_credits_or_402` (rollback on failure)
3. Builds prompt asking for JSON with 2-4 categories, each with weighted skills (name, level, required, weight)
4. Calls `call_groq_cascade` (with PII masking, token budget, prompt injection scan)
5. On success → returns `{success: true, source: "ai", categories: [...]}`
6. On failure → rolls back credit, returns deterministic `_fallback_generated_rubric()` (3 categories: Technical Skills, Soft Skills, Experience & Impact)

### 2.5 Rubric Detail Page

**Endpoint**: `GET /recruiter/skill-trees/{tree_id}/detail`

Returns:
- Rubric structure (`categories`, `skills`, `weights`)
- `linked_jobs` — jobs with `Job.rubric_id == id` (direct) or `BatchJob.rubric_id == id` (campaign)
- `campaign_count` — number of campaigns using this rubric
- `evaluated_candidates` — candidates scored against this rubric (join `EvaluationResult → EvaluationSession → Application`)

**Frontend** (`skill-tree-detail.tsx`):
- Stat cards: Categories, Skills, Linked Jobs, Evaluated Candidates
- Rubric Structure panel (categories → skills with level/weight/required badges)
- Linked Jobs panel → navigates to `/jobs/{id}`
- Evaluated Candidates panel → navigates to `/candidates/{app_id}`
- Actions: Edit, Duplicate, Archive

### 2.6 Rubric Library

**Endpoint**: `GET /recruiter/skill-trees` (list all company rubrics)

**Frontend** (`skill-tree-library.tsx`):
- Searchable grid of rubrics
- Shows skill count, usage (campaign_count), categories
- **View** → `/skill-tree/{id}` detail page
- **Use** → currently shows toast "Rubric ready to use in campaign creation" (stub)
- **Create Rubric** → `/skill-tree-create`

---

## Phase 3: AI Interview Invitation

### 3.1 Invitation Creation

**Endpoint**: `POST /recruiter/send-invitation`

**File**: `backend/routers/recruiter_candidates/invitations.py`

**Flow**:
1. **Application lookup** — `get_application_for_recruiter(app_id, recruiter, db)` enforces tenant isolation (404 on mismatch)
2. **Candidate account provisioning** — `ensure_candidate_account(db, email, full_name)` creates a `User` row if none exists, generates a plaintext temp password
3. **HMAC token generation** — `generate_interview_token(app.id)` produces a time-limited (24h), single-use HMAC-signed token:
   - Format: `{nonce}:{hmac_sha256_signature}`
   - Bound to `app_id` + current UTC day
4. **Tracking URL** — Built as `/api/v1/track/click/{tracking_token}?token={interview_token}&email={candidate_email}`
5. **Email assembly**:
   - Personalizes subject/body (AI-generated or recruiter-provided)
   - Replaces `{{INTERVIEW_LINK}}`, `{{EMAIL}}`, `{{PASSWORD}}` placeholders
   - Appends invisible open-pixel `<img>` for open tracking
6. **SMTP sending** — Reads recruiter's SMTP config or falls back to global `SystemConfig` SMTP
7. **State update** — `app.status = "invited"`

**Invitation link format**:
```
{frontend_url}/candidate/interview?id={app.id}&token={interview_token}
```

### 3.2 AI-Generated Invitation

**Endpoint**: `POST /recruiter/generate-invitation`

Optional AI step that drafts a personalized email. Costs **1 credit** (rollback on failure).

### 3.3 Bulk Invitation

**Endpoint**: `POST /recruiter/applications/bulk-invite`

- Hard-capped at **500 recipients** per request
- Each application is tenant-validated
- Actual sending queued via `BackgroundTasks.add_task(email_service.send_bulk_emails, ...)`

### 3.4 Re-invite for Unregistered Candidates

**Endpoint**: `POST /recruiter/campaigns/{batch_id}/reinvite-unregistered`

- Targets applications with `status=imported` or `status=pending` and no hashed password
- **24h Redis cooldown** per candidate prevents spam
- Sends "Complete Your AI Interview" reminder

---

## Phase 4: Interview Execution (Candidate Side)

### 4.1 Navigation to Interview Room

Candidate clicks the invitation link:
```
/candidate/interview?id={app.id}&token={interview_token}
```

**Frontend** (`frontend/src/features/candidates/pages/candidate-interviews.tsx`):
- Reads `?id=` and `?token=` query params
- Validates token via backend API
- Navigates to `/interviews/room/{appId}`

### 4.2 Session Creation

**File**: `backend/routers/ai_interview/chat.py`

When candidate sends their first message (typically "ready"):

1. **Auto-start** if no `EvaluationSession` exists:
   ```python
   if _es is None or getattr(_es, "config_snapshot", None) is None:
       from backend.rubric.interview_starter import InterviewStarter
       started_session = InterviewStarter.start(db, app)
   ```

2. **`InterviewStarter.start()`** (`backend/rubric/interview_starter.py`):
   - Sets `app.interview_state = "in_progress"`
   - Builds `EntryPoint(source_type="job_apply", source_id=app.job_id, application_id=app.id, campaign_id=app.batch_id)`
   - Resolves `EvaluationConfigSnapshot`:
     - If campaign has a pre-generated `active_snapshot_id`, reuses it
     - Otherwise, loads job's rubric and creates a fresh snapshot with: `total_questions`, `time_limit_seconds`, `language`, `interview_instructions`, rubric JSON, scoring weights
   - Creates `EvaluationSession` via `sync_ai_interview_session()`:
     - `interview_state = "in_progress"`
     - `interview_time_left = config_snapshot.time_limit_seconds` (default 1800s = 30min)
     - Attaches `evaluation_config_snapshot_id`, `rubric_id`, `rubric_version`
   - Propagates `app.language = config_snapshot.language`

### 4.3 The Chat Loop

**Endpoint**: `POST /ai/interview/chat`

**Core logic** (`_interview_chat_core` in `chat.py`):

1. **Auth** — Resolves application via JWT (logged-in candidate/recruiter) or HMAC token (guest link)
2. **Rate limiting** — 10 requests per 300 seconds per user/app
3. **Idempotency guard** — `interview_turn_seq` atomically incremented; concurrent duplicates return `"duplicate"`
4. **State checks** — Rejects if `completed` (409) or `time_left <= 0` (410 → expired)
5. **Input sanitization** — `AISecurity.sanitize_input()` + `detect_prompt_injection()`
6. **Answer evaluation** — `evaluate_answer()` scores the response (0-100) against the last question's focus area
7. **Lazy answer detection** — Short/empty answers trigger a hard 20-point penalty
8. **Anti-gaming** — Pattern detection spikes engine sigma by 15 points
9. **Early exit check** — `should_early_exit()` terminates if candidate consistently scores <35 after 3+ questions
10. **Next question generation** — `generate_skill_driven_turn()` produces the next AI question considering:
    - CV context, declared role, job description
    - Rubric categories and seniority
    - Recruiter custom instructions
    - Engine state (covered skills, focus, live metrics)
    - Falls back: worker queue → direct `call_groq_cascade` → `get_fallback_turn()`

**Response** includes:
```json
{
  "reply": "Next question text...",
  "current_score": 72.5,
  "time_left": 1420,
  "progress": {"current": 3, "total": 10},
  "skills": ["React", "TypeScript"],
  "score_label": "Good",
  "feedback": "Strong technical answer...",
  "is_complete": false
}
```

### 4.4 Turn Persistence

Every Q&A pair is saved as an `InterviewTurn` row via `write_turn()`:
- `evaluation_session_id`, `turn_number` (unique per session)
- Encrypted `question`, `answer`, `feedback`, `reasoning`
- `score`, `quality`, `type`, `difficulty`, `response_time_seconds`
- Timestamps

### 4.5 Time Limits

| Mechanism | Detail |
|-----------|--------|
| Default | 1800 seconds (30 min) on `EvaluationSession.interview_time_left` |
| Snapshot override | `EvaluationConfigSnapshot.time_limit_seconds` (recruiter-configured) takes precedence |
| Frontend timer | Decrements local `timeLeft` every 1s |
| Expiry | Backend transitions to `expired` (410); frontend redirects to `/interviews` |
| Pause/Resume | Pause snapshots remaining time; resume resets `opened_at` |
| End early | `POST /ai/interview/end` → transitions to `evaluating` |

### 4.6 Interview Completion

Evaluation is triggered in **three ways**:

1. **Max questions reached** (in-chat) — `turn >= max_turns` → background task enqueued
2. **Early exit** — consistent low scores → background task enqueued
3. **Manual End button** — `POST /ai/interview/end` → background task enqueued

All three set:
- `interview_state = "completed"` or `"evaluating"`
- `evaluation_state = "pending"`
- Enqueue `run_background_final_evaluation(app.id, app.company_id)` as `BackgroundTask`

---

## Phase 5: Background Evaluation & Scoring

### 5.1 Background Final Evaluation

**File**: `backend/routers/ai_interview/evaluation.py:53-473`

`run_background_final_evaluation(application_id, company_id)` opens its own DB session and:

1. **Tenant-scoped lookup** — `Application.id == application_id AND Application.company_id == company_id`
2. **Claim evaluation** — Atomically updates `EvaluationSession.status = "running"` (only if `"pending"`)
3. **Load QA pairs** — Primary: `interview_turns` table via `load_turns()`. Fallback: legacy `interview_log` JSON
4. **Load violations** — Proctoring violations from `EvaluationSession.proctoring_violations`
5. **Scoring path selection**:
   - **Rubric exists**: Load `RubricScoringDetail` rows, call `aggregate_scores()` for deterministic weighted scoring
   - **No rubric**: Call `evaluate_complete_interview()` (AI holistic evaluation via Groq)
6. **Output validation** — `AIOutputValidator.validate("final_evaluation", result)` ensures schema match
7. **Score persistence** — `ScoringService.set_evaluation_result()` writes `EvaluationResult`
8. **Dashboard insights** — `derive_dashboard_insights_from_skills()` generates strengths/weaknesses/action_plan
9. **Recruiter notification** — Sends completion email with optional PDF report
10. **State finalization** — `evaluation_state = "completed"`, `EvaluationSession.status = "completed"`

### 5.2 Rubric-Based Scoring (Deterministic)

**Per-skill scoring** (`rubric/rubric_engine.py:score_answer()`):
- Matches evidence sentences against rubric `LevelDescriptor` keywords using regex (`\bkeyword\b`)
- If match ratio ≥ 40% → assigns that level's `score_threshold` as base score
- Quality multiplier: **strong=1.0**, **medium=0.7**, **weak=0.4**
- Produces `SkillScoreResult` with confidence interval (±5 for strong, ±10 for medium, ±20 for weak)

**Aggregation** (`rubric/scoring_aggregator.py:aggregate_scores()`):
- **Best-score-per-skill**: keeps highest `final_score` for each skill across all turns
- **Subcategory score**: weighted average of skill scores within subcategory (by skill weight)
- **Category score**: weighted average of subcategory scores within category (by category weight)
- **Overall score**: weighted average of category scores (by category weight)
- **Gaps**: any category below 55 triggers gap entry (minor/moderate/critical)
- **Coverage**: `skills_scored / skills_total × 100`

### 5.3 AI Holistic Scoring (Non-Rubric)

When no rubric is configured:
- `evaluate_complete_interview()` sends all Q&A pairs to Groq in a single prompt with `json_mode=True`
- Returns `{final_score, skill_metrics, strengths, weaknesses, detailed_feedback, explainability, ...}`
- Schema-validated against `EvaluationResponse` Pydantic model

### 5.4 Final Score Computation

**`ScoringService.compute_final_score()`** — the ONLY function that writes `EvaluationResult.final_score`:

```
final_score = cv_score × 0.25 + rubric_score × 0.50 + coverage_pct × 0.25
```

| Component | Weight (with rubric) | Weight (no rubric) |
|-----------|---------------------|-------------------|
| `cv_score` | 0.25 | 0.75 |
| `rubric_score` | 0.50 | 0.0 |
| `coverage_pct` | 0.25 | 0.25 |

`coverage_pct` is used directly (0–100 scale) multiplied by the coverage weight.

**Scoring status machine** (CHECK constraint at DB level):
- `PENDING` → `final_score` must be NULL
- `SCORED` → `final_score` must be non-NULL
- `FAILED` → `final_score` must be NULL (fraud/scoring error)
- `NEEDS_REVIEW` → `final_score` must be NULL

### 5.5 What Gets Stored

| Table | Purpose |
|-------|---------|
| `evaluation_results` | Canonical score: `cv_score`, `rubric_score`, `final_score`, `verdict`, `score_breakdown` (JSON), `scoring_status` |
| `rubric_scoring_details` | Per-criterion scores: `criterion_name`, `score`, `weight`, `feedback`, `question`, `answer`, `source` |
| `interview_turns` | Per-question: `turn_number`, `question`, `answer`, `score`, `response_time_seconds` |
| `rubric_snapshots` | Immutable rubric copy at evaluation time |
| `evaluation_config_snapshots` | Frozen config: `resolved_rubric_json`, `rubric_id`, `rubric_version`, `total_questions`, `time_limit_seconds` |

---

## Phase 6: Recruiter Analysis View

### 6.1 API Endpoint

**`GET /recruiter/applications/{app_id}/scores`**

**Authorization**: `require_recruiter` + `get_application_for_recruiter` (tenant-scoped, 404 on mismatch)

### 6.2 Response Shape

```json
{
  "application_id": 66,
  "candidate_name": "J. Candidate",       // masked unless pro tier
  "cv_score": 72.5,
  "overall_score": 81.3,
  "rubric_score": 78.0,
  "rubric_coverage_pct": 85.0,
  "scoring_model": "rubric",
  "rubric_version": 3,
  "rubric_available": true,
  "category_breakdown": [
    {"name": "Backend", "score": 85, "weight": 1.0, "coverage_pct": 90, ...}
  ],
  "skill_breakdown": [
    {"name": "React", "score": 90, "is_required": true, "assessed": true,
     "explanation": "...", "evidence": [...]}
  ],
  "gaps": [{"category": "Backend", "score": 45, "expected": 55, "gap_pct": 18, "severity": "moderate"}],
  "evidence": [
    {"skill_name": "React", "turn_number": 1, "question": "...", "answer": "...",
     "matched_keywords": [], "missing_competencies": [],
     "explanation": "...", "final_score": 90, "overridden": false}
  ],
  "needs_review": false,
  "penalty_breakdown": {
    "integrity_penalty": 0.0, "gaming_penalty": 0.0,
    "timing_penalty": 0.0, "proctoring_violations_count": 0, "trust_score": 100.0
  },
  "rubric": [{"label": "Backend", "score": 85, "qualifier": "Excellent"}],
  "questions": [{"id": 1, "title": "React", "category": "React", "score": 90,
                 "label": "Excellent", "answer": "...", "justification": "..."}],
  "ai_feedback": [{"title": "React", "body": "Candidate demonstrated strong..."}],
  "interview_details": [{"label": "Rubric Score", "value": "78.0"}, ...],
  "recommendation": {"label": "Strong Hire", "status": "SCREENING"},
  "trust": {"score": 100, "coverage": 85, "quality": 100, "count": 3},
  "is_rubric_driven": true
}
```

### 6.3 Frontend Page

**File**: `frontend/src/features/recruiter/pages/recruiter-interview-analysis.tsx`

**Tabs**:
1. **Overview** — Overall score, CV score, rubric score, recommendation badge, trust score, interview details
2. **Rubric Breakdown** (formerly "Skill Tree") — Category scores, skill scores + AI justification, evidence rows with answer/quote, gaps list, rubric score/coverage/version stat cards
3. **Questions** — Full Q&A list with scores, labels, candidate answers, AI justifications

**Name masking**: Non-pro recruiters see `"J. Candidate"` instead of full name; non-pro email = `"hidden@candway.com"`.

### 6.4 Ghost Report (Anti-Bias Feature)

**Endpoint**: `GET /recruiter/applications/{app_id}/ghost-data`

**Feature gate**: `has_feature(db, "ghost_report", recruiter, company_id)` — Pro/Pro+/Enterprise required.

**What it does**:
1. **Anonymizes** the candidate: `"Candidate #{app_id}"`, strips pronouns ("he"/"she" → "they")
2. Removes PII from interview log
3. Builds a clean report with scores, anonymized summary, strengths/weaknesses, top 3 Q&A highlights

---

## Phase 7: Candidate Analysis View

### 7.1 API Endpoint

**`GET /candidate/interviews/{app_id}/analysis`**

**Authorization**: `get_application_for_candidate` (ownership-scoped)

### 7.2 Response Shape

Candidate-optimized view with:
- `category_breakdown`, `skill_breakdown`, `gaps` (same as recruiter)
- `questions_data` with full Q&A, scores, feedback, response times
- `performance_overview` (rubric categories or derived dimension scores)
- `score_timeline`, `highlights` (best/worst moments)
- `interview_details` (started_at, submitted_at, duration, status)
- `is_rubric_driven`, `rubric_version`, `rubric_score`, `rubric_coverage_pct`
- `recommendations` (AI-generated career recommendations)
- `roadmap` (career roadmap JSON if generated)

**No name masking** — candidates see their own full data.

### 7.3 Frontend Page

**File**: `frontend/src/features/candidates/pages/candidate-interview-analysis.tsx` (or similar)

Candidates see:
- Their overall score with color-coded feedback
- Breakdown by rubric category
- Individual question reviews with their answers and AI feedback
- Recommendations for improvement
- Option to download PDF report (1 credit via `POST /applications/{id}/pdf`)

---

## Data Model Reference

### Core Entities

```
Job (TenantMixin)
├── id, title, description, location, salary_range, type
├── recruiter_id → User
├── company_id → Company (TenantMixin)
├── rubric_id → Rubric (nullable)
├── is_active, deleted_at
└── required_skills (denormalized string)

Rubric (TenantMixin)
├── id (Integer PK)
├── job_id → Job (nullable — NULL = standalone)
├── company_id → Company
├── version, title, description
├── criteria_json (Text — JSON: [{name, weight, subcategories:[{name, weight, skills:[...]}]}])
├── passing_score, max_score, weight
├── is_active
└── created_by → User

Application
├── id, user_id → User
├── job_id → Job
├── batch_id → BatchJob (nullable)
├── company_id → Company (TenantMixin)
├── status (applied, invited, in_progress, completed, etc.)
├── interview_state, evaluation_state
├── overall_score, cv_score
├── rubric_id → Rubric (denormalized snapshot)
└── final_eval_done, final_eval_timestamp

EvaluationSession (TenantMixin)
├── id, application_id → Application
├── company_id → Company
├── evaluation_config_snapshot_id → EvaluationConfigSnapshot
├── rubric_id → Rubric, rubric_version
├── interview_state (not_started, in_progress, completed, evaluating, expired)
├── evaluation_state (pending, running, completed, failed)
├── interview_log (JSON — legacy transcript)
├── interview_questions (JSON)
├── proctoring_violations (JSON)
├── interview_time_left (seconds)
├── interview_turn_seq (idempotency counter)
└── status

InterviewTurn
├── id, evaluation_session_id → EvaluationSession
├── application_id → Application (alternate FK)
├── turn_number (unique per session)
├── question, answer, feedback, reasoning (EncryptedText)
├── score, quality, type, difficulty
├── response_time_seconds
└── timestamp

EvaluationResult (TenantMixin)
├── id, evaluation_session_id → EvaluationSession (1:1 unique)
├── application_id → Application
├── rubric_id → Rubric, rubric_version, rubric_snapshot_id
├── cv_score, rubric_score, human_integrity_score
├── rubric_coverage_pct, final_score
├── scoring_status (PENDING|SCORED|FAILED|NEEDS_REVIEW)
├── verdict, score_breakdown (JSON)
├── confidence_lower, confidence_upper
├── scoring_model, needs_review, fraud_score
└── created_at

RubricScoringDetail (TenantMixin)
├── id, evaluation_result_id → EvaluationResult
├── criterion_name, criterion_key
├── question, answer
├── score, weight, max_score
├── feedback, source
└── created_at

EvaluationConfigSnapshot (TenantMixin)
├── id, hash (unique)
├── source_type, source_id
├── total_questions, time_limit_seconds
├── language, interview_instructions
├── rubric_id, rubric_version
├── resolved_rubric_json (deferred JSON)
├── resolved_skills_json (deferred JSON)
├── config_json (deferred, full blob)
└── evaluation_sessions → EvaluationSession
```

### Relationships

```
Job 1 ──► N JobSkill
Job 1 ──► 1 JobEvaluationFramework
Job 1 ──► N JobScreeningQuestion
Job 1 ──► N JobPipelineStage
Job 1 ──► 1 JobAIConfig
Job 1 ──► N JobRoleOverview
Job 1 ──► N Application
Job N ──► 1 Rubric (via job.rubric_id)

Application 1 ──► N EvaluationSession
EvaluationSession 1 ──► 1 EvaluationResult
EvaluationSession 1 ──► N InterviewTurn
EvaluationResult 1 ──► N RubricScoringDetail

BatchJob 1 ──► N Application
BatchJob N ──► 1 Rubric (via batch_job.rubric_id)
```

---

## Key Business Rules & Security

### Tenant Isolation
- All reads/writes filter by `company_id` (TenantMixin)
- Cross-tenant access returns **404** (never 403) to prevent resource enumeration
- Background tasks open their own `SessionLocal()` and validate `company_id` before proceeding

### Rubric Versioning
- Editing a rubric creates a new version (version + 1) and deactivates the old one
- `Job.rubric_id` and `BatchJob.rubric_id` are automatically re-pointed to the new version
- Evaluation snapshots (`EvaluationConfigSnapshot`) store the rubric state at interview start — historical evaluations don't change when rubrics are edited

### Credit System
- AI operations consume credits inline with rollback on failure
- `consume_credits_or_402` raises 402 if insufficient credits
- Idempotency keys prevent double-debit on retried requests

### AI Security
- PII masking is **always enforced** before data leaves to external providers (no toggle)
- Prompt injection scanning covers both user AND system messages
- Output validation ensures AI responses match expected schemas
- Token budgets enforce 90% safety margin on context windows
- Cost budgets track per-call/daily/monthly spending

### Scoring Integrity
- `ScoringService` is the **single writer** for `EvaluationResult.final_score`
- All scoring paths (AI, rubric, manual, recalibration) funnel through `compute_final_score()`
- `EvaluationResult.scoring_status` has a CHECK constraint: `PENDING`/`FAILED`/`NEEDS_REVIEW` → NULL final_score; `SCORED` → non-NULL final_score

### Interview Security
- HMAC-signed interview tokens (24h expiry, single-use)
- Rate limiting: 10 requests per 300 seconds per user/app
- Idempotency guards prevent duplicate turn creation
- Input sanitization + prompt injection detection on every chat message

---

## End-to-End Flow Diagram

```
RECRUITER SIDE                              CANDIDATE SIDE
─────────────                               ──────────────

1. Create Job (wizard)
   ├── Step 1: Basic Info
   ├── Step 2: Role & Outcomes
   ├── Step 3: Rubric Evaluation
   │     ├── Use Existing Rubric → job.rubric_id = rubric.id
   │     ├── Create New Rubric → navigate to /skill-tree-create
   │     │     └── return with ?rubric_id={id} → auto-select
   │     └── Build Rubric Inline → JobSkill rows only
   ├── Step 4: Pipeline + AI Config
   └── Step 5: Publish → is_active=True
         │
         ▼
2. Invite Candidate
   POST /recruiter/send-invitation
     ├── ensure_candidate_account()
     ├── generate_interview_token()
     └── SMTP email with interview link
          │
          ▼  Candidate clicks link
          │
3. Candidate Starts Interview
   GET /candidate/interview?id={app}&token={token}
     └── navigate to /interviews/room/{appId}
          │
          ▼
   POST /ai/interview/chat {message: "ready"}
     ├── InterviewStarter.start()
     │     ├── ConfigurationResolver.resolve() → EvaluationConfigSnapshot
     │     └── sync_ai_interview_session() → EvaluationSession
     ├── generate_skill_driven_turn() → AI question
     └── write_turn() → InterviewTurn
          │
          ▼  [Loop: answer → evaluate → next question]
          │
   POST /ai/interview/end {reason: "candidate_ended"}
     ├── interview_state = "evaluating"
     └── background_tasks.add_task(run_background_final_evaluation)
          │
          ▼
4. Background Evaluation
   run_background_final_evaluation(app_id, company_id)
     ├── Load QA from interview_turns
     ├── Rubric scoring OR AI holistic evaluation
     ├── ScoringService.compute_final_score()
     ├── Write EvaluationResult + RubricScoringDetail
     ├── email_service.send_interview_complete_email()
     └── evaluation_state = "completed"
          │
          ▼
5. Analysis Views
   Recruiter: GET /recruiter/applications/{id}/scores
     └── Frontend: recruiter-interview-analysis.tsx
           ├── Overview tab
           ├── Rubric Breakdown tab
           └── Questions tab
                 │
                 └── Ghost Report (Pro+)
                       └── Anonymized candidate view

   Candidate: GET /candidate/interviews/{id}/analysis
     └── Frontend: candidate-interview-analysis.tsx
           ├── Score + breakdown
           ├── Q&A review
           ├── Recommendations
           └── PDF download (1 credit)
```

---

*Document generated: 2026-08-08*
*Codebase: Candway Platform (masar_landing_page)*
