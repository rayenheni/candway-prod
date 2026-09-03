# Candway Recruiter Architecture & Data Flow Audit

> **Date:** 2026-06-27  
> **Scope:** Recruiter-side only (Campaign → AI Interview → Final Report)  
> **Type:** Architecture Audit (not code review)  
> **Method:** Static analysis of models, routers, services, AI engine, rubric engine, documentation.

---

## 0. Executive Summary

The codebase has **two architectures simultaneously**: the **current runtime architecture** (what actually runs in production) and a **proposed target architecture** (described in `docs/architecture/ai_hiring_campaign_manager.md`). The target architecture is significantly better but **has not been implemented**. Critical tables like `campaign_evaluation_configs`, `evaluation_config_snapshots`, `candidate_evaluation_snapshots` do not exist in the codebase.

**The current runtime architecture has systemic problems:**

1. **No single source of truth** for campaign/evaluation configuration. Configuration is scattered across `BatchJob`, `Job`, `Application`, `Rubric`, and `EvaluationSession` with no clear winner on conflicts.
2. **The AI Interview Engine reads live mutable data** during evaluation. It is not deterministic.
3. **RubricSnapshot exists but is not reliably used** — the AI engine often reads the live rubric directly.
4. **No config versioning** — when a recruiter edits rubric weights mid-campaign, candidates already in evaluation may be affected.
5. **Configuration duplication** — `language`, `rubric_id`, `interview_instructions`, `passing_score` exist in 2–4 places each.

---

## 1. Recruiter Workflow (Current Runtime)

```
Recruiter
  │
  │  POST /api/v1/recruiter/campaigns/full
  ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. CREATE CAMPAIGN                                              │
│                                                                 │
│  API:       POST .../campaigns/full  (management.py:180)        │
│  Service:   create_full_campaign()                              │
│  Tables W:  batch_jobs (1 row)                                  │
│  Tables R:  jobs, rubrics                                       │
│  Created:   BatchJob                                             │
│  IDs:       batch_jobs.id = campaign_id                          │
│  Config:    language, interview_instructions copied to BatchJob  │
│            rubric_id copied from rubric to BatchJob              │
│                                                                 │
│  NOTE: No CampaignEvaluationConfig exists.                      │
│        No snapshot is created at campaign creation.              │
│        All config is stored as BatchJob columns.                 │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        │  recruiter uploads CVs / invites candidates
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. UPLOAD CANDIDATES / CV ANALYSIS                              │
│                                                                 │
│  API:       POST .../campaigns/{id}/upload-cvs                  │
│  Service:   upload.py → AI CV analysis                          │
│  Tables W:  applications, cv_documents, evaluation_sessions     │
│  Tables R:  batch_jobs, jobs                                    │
│  Created:   Application, CvDocument, EvaluationSession          │
│  IDs:       application_id, cv_document_id, evaluation_session_id│
│  Config:    language copied from BatchJob or Application        │
│            rubric_id copied from BatchJob→Job to Application   │
│                                                                 │
│  SSOT:      Application.rubric_id is set here                   │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        │  candidate starts interview
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. AI INTERVIEW SESSION START                                   │
│                                                                 │
│  API:       POST .../interview/start  (chat.py)                 │
│  Service:   InterviewEngine (ai/engine.py)                      │
│  Tables R:  applications, evaluation_sessions                   │
│             batch_jobs (via app.batch_job)                       │
│             jobs (via app.job)                                   │
│  Tables W:  evaluation_sessions (state transition)               │
│  Reads:     app.language, app.rubric_id, app.interview_state     │
│  Config:    language from app.language (fallback chain)          │
│            rubric from Rubric(db) via load_rubric(app.job_id)   │
│                                                                 │
│  CRITICAL:  Rubric is loaded LIVE from DB on every interview    │
│             No snapshot is used at session start                 │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        │  candidate answers questions (turn loop)
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. AI INTERVIEW TURN (Q&A)                                      │
│                                                                 │
│  API:       POST .../interview/chat  (chat.py:67)               │
│  Service:   _interview_chat_core()                              │
│  Reads:     Application, EvaluationSession, InterviewTurn       │
│             Rubric (live from DB via rubric_loader)              │
│             CvDocument (CV text for context)                    │
│  Writes:    InterviewTurn (1 row per answer)                    │
│             EvaluationSession (state updates)                   │
│                                                                 │
│  AI reads:  CV text, job description, rubric categories,        │
│             recruiter_instructions, language, calibration_data  │
│                                                                 │
│  Questions: generated by LLM via generate_skill_driven_turn()   │
│  Scoring:   evaluate_answer() → rubric_engine.score_answer()   │
│                                                                 │
│  RUBRIC:    JobRubric Pydantic model loaded from rubric_loader  │
│            Criteria+levels read from Rubric.criteria_json       │
│            Skill definitions from SkillDefinition table         │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        │  interview completed
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. FINAL EVALUATION                                             │
│                                                                 │
│  API:       POST .../interview/evaluate-final                   │
│             (evaluation.py:56)                                  │
│                                                                 │
│  Service:   evaluate_final_interview()                          │
│  Tables R:  Application, EvaluationSession, EvaluationResult    │
│             Rubric (live DB), InterviewTurn, RubricScoringDetail│
│             CvDocument                                          │
│  Tables W:  EvaluationResult, RubricScoringDetail               │
│             Application.status update                           │
│                                                                 │
│  PATH A     Rubric path:                                        │
│  (rubric):  load_rubric_by_id(rubric_db_id) from DB            │
│             → aggregate_scores() → ScoringService               │
│                                                                 │
│  PATH B     AI path (if no rubric):                             │
│  (no       evaluate_complete_interview() → LLM call            │
│   rubric):  → calculate_overall_score() → ScoringService       │
│                                                                 │
│  FINAL:     ScoringService.compute_final_score()                │
│            writes EvaluationResult with scoring_status='SCORED' │
│                                                                 │
│  IDEMP:     If already completed and not force_reevaluation,    │
│            skips. force_reevaluation resets state to pending.   │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. FINAL REPORT / VERDICT                                       │
│                                                                 │
│  API:       Various recruiter dashboard endpoints               │
│  Tables R:  EvaluationResult (final_score, verdict)             │
│             Verdict (business decision)                         │
│  Reads:     ScoringService.get_canonical_score()                │
│             ScoringService.get_canonical_verdict()              │
│                                                                 │
│  Decision:  EvaluationResult.verdict (AI)                       │
│            Verdict.decision (human override)                    │
│            ScoringService.get_canonical_verdict():              │
│              Priority: 1. Verdict table, 2. EvaluationResult   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Database Ownership Audit

### Entity Ownership Matrix

| Entity | Owner | Creator | Updater | Readers | Should NEVER Modify | Ownership Issues |
|--------|-------|---------|---------|---------|-------------------|-----------------|
| **BatchJob** | Recruiter | Campaign creation | Recruiter (campaign edit) | AI engine, Dashboard, Rubric loader | AI engine (read-only) | OK |
| **Job** | Recruiter | Job posting | Recruiter | AI engine, Campaign, Dashboard | AI engine | OK |
| **Rubric** | Recruiter/Admin | Rubric builder | Recruiter | AI engine, Scoring service, Rubric loader | AI engine, Scoring service | **RUBRIC-1: AI engine reads live rubric** |
| **RubricSnapshot** | System | ScoringService._ensure_rubric_snapshot() | NEVER (immutable) | EvaluationSession, EvaluationResult | Everyone after creation | OK — correctly immutable |
| **SkillDefinition** | System/Admin | rubric_loader._resolve_skill_definitions() | rubric_loader._sync_rubric_to_skill_definitions() | Rubric loader, AI engine | Recruiter (indirect via rubric save) | **SKILL-1: Synced from rubric, not independent** |
| **Campaign** (no config table) | Recruiter | Campaign creation | Recruiter | AI engine, Dashboard | AI engine | **CFG-1: No dedicated config table exists** |
| **EvaluationSession** | System | CV upload or interview start | AI engine | Recruiter dashboard, Scoring service | Recruiter (directly) | OK |
| **EvaluationResult** | System | ScoringService.compute_final_score() | ScoringService ONLY | Recruiter dashboard, Candidate dashboard | Anyone other than ScoringService | ADR-001 enforces single-writer |
| **Candidate** (CandidateProfile) | Candidate | Registration | Candidate | Recruiter, Admin | Recruiter (except assignment) | OK |
| **Application** | System (on apply) | CV upload / apply | System (state changes), Recruiter (notes, status) | Recruiter dashboard, AI engine | AI engine (state machine bypass) | **APP-1: AI engine writes status directly** |
| **CV Analysis** (CvDocument) | System | AI CV analysis | System (re-analysis) | AI engine, Recruiter | Recruiter | OK |
| **InterviewTurn** | System | AI engine per turn | Never (immutable after write) | Scoring service, Recruiter | Everyone after creation | OK |
| **Verdict** | Recruiter/System | ScoringService / Recruiter | Recruiter (human override via supersession) | Recruiter dashboard | AI engine | OK |

### Duplicate Ownership Findings

**OWN-1: `language` field exists in 4 places:**
- `BatchJob.language` — set at campaign creation
- `Application.language` — per-application override
- `EvaluationSession.language` — per-session
- No clear SSOT. AI engine reads from `Application.language` but `BatchJob.language` is the campaign default.

**OWN-2: `rubric_id` exists in 4 places:**
- `Job.rubric_id` — job default
- `BatchJob.rubric_id` — campaign selection
- `Application.rubric_id` — per-application pinning
- `EvaluationSession.rubric_id` — per-session pinning
- AI engine fallback chain: `EvaluationSession.rubric_id` → `Application.rubric_id` → `Job.rubric_id`. Each layer can override.

**OWN-3: `interview_instructions` exists in 2 places:**
- `Job.interview_instructions`
- `BatchJob.interview_instructions`
- AI reads from BatchJob when available, otherwise from Job. No versioning.

**OWN-4: `passing_score` exists in 2 places:**
- `Rubric.passing_score` (live)
- `RubricSnapshot.passing_score` (snapshot)
- AI reads from live Rubric, not from snapshot.

**OWN-5: `scoring_model` exists in 2 places:**
- `EvaluationResult.scoring_model` (canonical)
- `Application.rubric_id` (legacy, deprecated)

---

## 3. Source of Truth Audit

| Concept | SSOT | Location | Conflicts? |
|---------|------|----------|------------|
| **Skill Tree** | SkillDefinition table | `skill_definitions` | Synced from Rubric JSON. If Rubric JSON and SkillDefinition disagree, SkillDefinition wins (it has UUID). |
| **Rubric** | Rubric table | `rubrics` | `RubricSnapshot` is the frozen copy. If live Rubric changes, the evaluation uses live data if no snapshot was taken. |
| **Interview Language** | Application.language | `applications.language` | BatchJob.language and EvaluationSession.language also exist. Application.language wins at runtime. |
| **Passing Score** | Rubric.passing_score | `rubrics.passing_score` | Also in RubricSnapshot.passing_score. At runtime, live Rubric is read. |
| **Interview Instructions** | BatchJob.interview_instructions | `batch_jobs.interview_instructions` | Also in Job.interview_instructions. BatchJob wins if present. |
| **Scoring Weights** | HARDCODED in ScoringService | `scoring_service.py:33-38` | `CANONICAL_WEIGHTS` dict is a Python constant: cv=0.25, rubric=0.40, human=0.10, coverage=0.25. NOT configurable per campaign. |
| **Question Count** | INTERVIEW_TOTAL_QUESTIONS constant | `routers/ai_interview/utils.py` | Hardcoded constant. NOT configurable per campaign. |
| **Adaptive Difficulty** | AI engine state machine | `ai/interview_customization.py` | Runtime-only, in-memory. Not persisted as configuration. |
| **AI Model** | cascade call in llm.py | `ai/llm.py` | Not configurable per campaign. Uses Groq → DeepSeek → Gemini fallback. |
| **Candidate Status** | Application.status | `applications.status` | OK — single source. |
| **Interview Status** | EvaluationSession.interview_state | `evaluation_sessions.interview_state` | OK — single source (deprecated Application columns delegate here). |
| **Campaign Status** | BatchJob.status | `batch_jobs.status` | OK — single source. |
| **CV Score** | EvaluationResult.cv_score | `evaluation_results.cv_score` | Deprecated Application.analysis_score still exists (legacy mirror). |
| **Interview Score** | EvaluationResult.rubric_score | `evaluation_results.rubric_score` | OK after ADR-001 fix. |
| **Final Score** | EvaluationResult.final_score | `evaluation_results.final_score` | OK — canonicalized by ADR-001. |
| **Verdict** | EvaluationResult.verdict → Verdict table | Priority order in scoring_service.get_canonical_verdict() | Verdict table (human override) wins over EvaluationResult.verdict (AI). |

### Critical SSOT Issues

**SSOT-1: Scoring weights are hardcoded.** `CANONICAL_WEIGHTS` in `scoring_service.py:33-38` is a Python dict constant. Campaigns cannot customize the scoring formula. The target architecture proposes `scoring_rules` JSON on `campaign_evaluation_configs`, but this table does not exist yet.

**SSOT-2: Question count is hardcoded.** `INTERVIEW_TOTAL_QUESTIONS` from `utils.py` is used everywhere. Campaigns cannot configure interview length.

**SSOT-3: No evaluation_config SSOT exists.** Campaign configuration is distributed across 4+ tables with no single record of truth.

---

## 4. AI Interview Configuration Audit

### Current Runtime: What the AI Engine Actually Reads

```
AI Interview Engine (at runtime)
  │
  ├─ FROM Application (live DB):
  │   ├─ language
  │   ├─ rubric_id
  │   ├─ interview_state (via delegation to EvaluationSession)
  │   ├─ interview_log (via delegation to EvaluationSession)
  │   ├─ analysis_json / cv_text (via CvDocument)
  │   └─ declared_role (via CvDocument)
  │
  ├─ FROM Rubric (live DB via rubric_loader):
  │   ├─ criteria_json → all skill definitions, weights, levels
  │   ├─ skill_weights
  │   ├─ passing_score
  │   └─ max_score
  │
  ├─ FROM BatchJob (live DB via app.batch_job):
  │   ├─ language (used if app.language not set)
  │   ├─ interview_instructions
  │   └─ target_role
  │
  ├─ FROM Job (live DB via app.job):
  │   ├─ interview_instructions (fallback)
  │   ├─ required_skills
  │   └─ description
  │
  ├─ FROM EvaluationSession (live DB):
  │   ├─ interview_state
  │   ├─ calibration_json
  │   ├─ proctoring_violations
  │   └─ interview_log
  │
  └─ FROM HARDCODED CONSTANTS:
      ├─ CANONICAL_WEIGHTS (scoring_service.py)
      ├─ INTERVIEW_TOTAL_QUESTIONS (utils.py)
      └─ DIMENSION_WEIGHTS (utils.py)
```

### Detailed Configuration Trace

| Config Value | Source | Chain | Mutable? | Snapshot? |
|-------------|--------|-------|----------|-----------|
| **Language** | Application.language ← BatchJob.language ← default "English" | Application → AI | YES | NO |
| **Passing Score** | Rubric.passing_score | Rubric live → AI | YES | Sometimes (RubricSnapshot exists but AI doesn't use it) |
| **Evaluation Criteria** | Rubric.criteria_json (JSON blob) | Rubric live → rubric_loader → Pydantic JobRubric → AI | YES | Sometimes |
| **Skill List** | Rubric.criteria_json → SkillDefinition (synced) | Rubric → SkillDefinition → AI | YES (via rubric sync) | NO |
| **Skill Weight** | Rubric.skill_weights (JSON) or SkillDefinition.weight | Rubric → JobRubric.build_lookup() → AI | YES | NO |
| **Question Gen Rules** | HARDCODED in ai/interview.py (get_difficulty, get_question_type) | Python logic → AI prompt | NO | N/A |
| **Rubric Levels** | Rubric.criteria_json → SkillDefinition.levels | Rubric → SkillDefinition → rubric_engine → AI | YES | NO |
| **Adaptive Difficulty** | In-memory state in ai/interview_customization.py | Runtime state → AI | Runtime-only | NO |
| **Interview Instructions** | BatchJob.interview_instructions → normalize_instructions() → prompt injection | BatchJob → AI | YES | NO |
| **Scoring Formula** | HARDCODED in scoring_service.py (CANONICAL_WEIGHTS) | Python code → EvaluationResult | NO | N/A |
| **AI Model** | HARDCODED in ai/llm.py (Groq cascade) | llm.py → AI calls | NO | N/A |

### Key Finding: The AI Engine Reads Live Mutable Data

The AI Interview Engine at runtime reads from **at least 5 live database tables**: `Application`, `Rubric`, `BatchJob`, `Job`, `EvaluationSession`. If any of these are modified during an evaluation, the AI will see different configuration mid-interview. There is **no frozen configuration object** passed to the engine.

The target architecture proposes `EngineReadOnlyConfig` constructed from an immutable `EvaluationConfigSnapshot`. This does not exist in the current codebase.

---

## 5. Skill Tree Audit

### What Exists vs. What Is Proposed

**Current codebase:**
- `SkillDefinition` model in `backend/models/evaluation/ai.py` — normalized table with UUID, name, category, keywords, levels, weight, is_required
- **No `skill_tree_templates`, `skill_categories`, or `skill_tree_skills` tables** in the current schema
- Skills are defined **inside the Rubric JSON** (`Rubric.criteria_json`) and synced to `SkillDefinition` via `rubric_loader._sync_rubric_to_skill_definitions()`
- The recruiter skill tree router (`recruiter_skill_trees.py`) likely routes to Rubric CRUD

**Target architecture (proposed):**
- `skill_tree_templates` — admin-managed global library
- `skills` — global normalized table
- `skill_categories` — hierarchical categories per tree
- `skill_tree_skills` — links skills into tree structure
- Weight is NOT stored in skill tree — it belongs in Rubric

### Answers

| Question | Answer |
|----------|--------|
| Purpose of Skill Tree? | Organizational + defines what skills exist for evaluation |
| Does it affect scoring? | Yes — skills from Rubric define scoring criteria |
| Does AI use it? | Yes — AI reads Rubric skills via `rubric_loader` → `JobRubric.build_lookup()` |
| Can recruiter edit it? | Yes — through Rubric CRUD (skills are part of rubric_json) |
| Can campaign override it? | Partially — BatchJob can select a different rubric_id |
| Does Job reference it? | `Job.rubric_id` references Rubric, which contains skills |
| Does Campaign reference it? | `BatchJob.rubric_id` references Rubric |
| Does AI ever read it directly? | Reads via Rubric → `JobRubric` Pydantic model |
| Can multiple campaigns reuse it? | Yes — multiple BatchJobs can reference the same Rubric |

### Skill Tree Architecture Smell

**SKILL-1: Rubric is the de facto skill tree.** Skills live inside `Rubric.criteria_json` as a JSON blob. The `SkillDefinition` table is a **secondary mirror** synced from the rubric JSON, not the primary source. This means:
- A skill's definition depends on which Rubric JSON it was synced from
- If a skill appears in multiple rubrics, its definition may differ
- There is no global skill catalog that all rubrics reference

---

## 6. Rubric Audit

### What Belongs Inside Rubric

**Current `Rubric` model columns:**
- `title`, `description` — OK (metadata)
- `job_id` — OK (context) but creates coupling
- `version` — OK (versioning)
- `passing_score` — **SHOULD be in campaign config, not rubric.** Passing score is a campaign decision, not a rubric property.
- `max_score` — OK (rubric design choice)
- `weight` — OK (rubric design choice)
- `criteria_json` — OK (the actual evaluation criteria as JSON) — but this is a JSON blob containing ALL skill definitions, which is the de facto skill tree
- `skill_weights` — OK (per-criterion weights) — but these are in a separate JSON column instead of being in criteria_json
- `complexity` — OK (rubric design choice)

### Architecture Mistakes

**RBR-1: Rubric contains the Skill Tree.** `criteria_json` contains the full hierarchy of categories → subcategories → skills with descriptions, keywords, levels, weights, and is_required flags. This means the Rubric IS the skill tree. There is no separation between "what skills exist" (skill tree) and "how skills are evaluated" (rubric).

**RBR-2: Passing score on Rubric.** `Rubric.passing_score` is a campaign-level policy decision, not a rubric design property. Different campaigns using the same rubric may want different passing thresholds.

**RBR-3: JSON blob for criteria.** `criteria_json` is a deferred Text column containing a JSON serialization of the `JobRubric` Pydantic model. This means:
- No referential integrity between rubric criteria and skill definitions
- Cannot query individual criteria without loading the entire blob
- Schema migrations require JSON-level coordination

**RBR-4: `weight` on Rubric and on SkillDefinition.** There are two weight fields: `Rubric.weight` (the rubric's overall weight) and `SkillDefinition.weight` (per-skill weight). Their relationship is unclear.

---

## 7. Campaign Configuration Audit

### Current State: BatchJob IS the Campaign Configuration

`BatchJob` has these config-relevant columns:
- `title` — OK (campaign name)
- `job_id` → Job — links to job description
- `rubric_id` → Rubric — selects evaluation criteria
- `target_role` — OK (role context)
- `description` — OK (campaign description)
- `language` — interview language (DUPLICATED)
- `interview_instructions` — custom instructions (DUPLICATED)
- `template_id` → CampaignTemplate — email templates
- `email_sequence_enabled`, `email_sequence_days` — email automation
- `worker_status` — processing state

### What BatchJob Does NOT Own (but should)

| Config Value | Where It Actually Lives | Problem |
|-------------|------------------------|---------|
| Scoring weights | Hardcoded in `scoring_service.py` | Cannot configure per campaign |
| Passing score | `Rubric.passing_score` | Campaign decision lives in rubric |
| Question count | Hardcoded `INTERVIEW_TOTAL_QUESTIONS` | Cannot configure per campaign |
| Time limit | Hardcoded 1800s in `EvaluationSession.interview_time_left` | Default only, not configurable |
| Selected rubric | `BatchJob.rubric_id` → `Rubric` (live) | No snapshot, live data changes affect evaluations |
| Skill overrides | None | Cannot override rubric skill weights per campaign |
| Evaluation formula | Hardcoded in `ScoringService` | Cannot configure per campaign |

**CFG-1: Campaign has no dedicated evaluation configuration.** The proposed `CampaignEvaluationConfig` table does not exist. All evaluation configuration is either:
- On BatchJob columns (language, instructions, rubric_id)
- On Rubric (passing_score, criteria, weights)
- Hardcoded in Python (scoring weights, question count, time limit)

**CFG-2: No versioning.** When a recruiter edits a rubric or changes campaign settings, there is no version history. Candidates already in evaluation may be affected.

---

## 8. Snapshot Audit

### RubricSnapshot: Exists but Underutilized

**How it's created:**
- `RubricSnapshotter.create_from_rubric_record()` is called from `ScoringService._ensure_rubric_snapshot()`
- This is called when `ScoringService.ensure_score()` runs or during `compute_final_score()`
- **NOT called at campaign publish time** (no campaign publish mechanism exists)

**When it's created:**
- Lazily, during final score computation
- NOT at campaign creation
- NOT at interview start
- NOT at candidate assignment

**Who reads it:**
- `EvaluationSession.rubric_snapshot_id` → relationship to RubricSnapshot
- `EvaluationResult.rubric_snapshot_id` → relationship to RubricSnapshot

**Can it change?**
- Code comments say immutable. No UPDATE operations are performed on snapshots.
- No application-level enforcement (e.g., DB triggers or RLS) prevents updates.

### What DOES NOT Have a Snapshot

| Entity | Snapshot Exists? | Risk |
|--------|-----------------|------|
| **Rubric** | Yes (RubricSnapshot) | But AI engine may read live rubric instead of snapshot |
| **Campaign config** | NO | No `evaluation_config_snapshots` table exists |
| **Scoring rules** | NO | Weights are hardcoded in Python |
| **Skill tree** | NO | Skills are read from live Rubric JSON |
| **Interview config** | NO | Language, instructions read from live BatchJob/Application |

### Snapshot Gap: The Critical Risk

**SNAP-1: No configuration snapshot exists for the evaluation as a whole.** Even though `RubricSnapshot` exists for the rubric portion, there is no snapshot for the full evaluation configuration (language, instructions, passing score, scoring rules, question count). The AI engine reads these from live mutable tables.

**SNAP-2: RubricSnapshot is created lazily during scoring, not at interview start.** This means:
- If a recruiter changes the rubric mid-interview, the candidate's evaluation may use the modified rubric
- The AI question generation phase (pre-scoring) reads the live rubric, not the snapshot
- Only the final scoring phase may use the snapshot (via ScoringService)

---

## 9. Candidate Evaluation Audit

### Complete Trace: One Candidate

```
Recruiter uploads CV
  │
  ▼
1. Application created
   Tables: applications (1 row)
          cv_documents (1 row) — analysis starts
          evaluation_sessions (1 row, status="pending")
   Config: app.language ← BatchJob.language or default "English"
           app.rubric_id ← BatchJob.rubric_id or Job.rubric_id
           No snapshot taken yet
  │
  ▼
2. AI CV Analysis
   Tables: cv_documents updated (analysis_json, extracted_skills)
          skill_definitions (may be synced/created)
   Config version: live Rubric data at time of analysis
  │
  ▼
3. Candidate starts interview
   Tables: evaluation_sessions updated (status="in_progress")
   Config: rubric loaded live from DB:
            rubric_loader.load_rubric(app.job_id)
            → queries Rubric table
            → queries SkillDefinition table
            → builds JobRubric Pydantic model
           language from app.language
           recruiter_instructions from app.batch_job.interview_instructions
  │
  ▼
4. Q&A Turns (1-10)
   Tables: interview_turns (N rows)
           evaluation_sessions (state updates)
   Config: same live Rubric throughout (cached 5 min in rubric_loader._cache)
           If cache expires mid-interview, rubric is re-loaded from DB
  │
  ▼
5. Interview Complete → Final Evaluation
   Tables: evaluation_sessions (status="completed")
           evaluation_results (1 row via ScoringService)
           rubric_scoring_details (per-criterion scores)
           rubric_snapshots (1 row if ScoringService._ensure_rubric_snapshot runs)
   Config: rubric re-loaded from DB (or cache)
           if RubricSnapshot does not exist yet, it's created NOW
           live scoring weights from CANONICAL_WEIGHTS constant
  │
  ▼
6. Recruiter views final report
   Tables: evaluation_results (final_score, verdict)
           rubric_scoring_details (per-skill breakdown)
           verdicts (if human override)

   Configuration version used by candidate:
   ========================================
   - Rubric version: whatever was in Rubric table at time of evaluation
     (or cached by rubric_loader for 5 min)
   - Language: whatever Application.language was set to
   - Instructions: whatever BatchJob.interview_instructions was
   - Scoring weights: hardcoded CANONICAL_WEIGHTS
   - Question count: hardcoded INTERVIEW_TOTAL_QUESTIONS

   → NO VERSION TRACKING. Cannot determine what config this candidate used.
```

### Re-evaluation Trace

If a recruiter triggers force re-evaluation:

1. `force_reevaluation=True` flag sent to `/interview/evaluate-final`
2. `Application.evaluation_state` reset to "pending"
3. New `EvaluationSession` created (or existing one re-used)
4. New evaluation reads **current live data** from:
   - Current Rubric (may have changed since original evaluation)
   - Current BatchJob settings (may have changed)
   - Current Application settings
5. New `EvaluationResult` created
6. **Old evaluation preserved** (separate EvaluationSession)

**Key finding: Re-evaluation uses the NEW configuration, not the config that was active during the original interview.** This means a candidate's score can change based on rubric edits made after their interview.

---

## 10. Data Duplication Audit

| Data | Locations | Duplication Type | Risk |
|------|-----------|-----------------|------|
| **language** | `BatchJob`, `Application`, `EvaluationSession` | Configuration | DR-1: Conflicts possible |
| **rubric_id** | `Job`, `BatchJob`, `Application`, `EvaluationSession` | Reference chain | DR-2: Each layer can override |
| **interview_instructions** | `Job`, `BatchJob` | Configuration | DR-3: Unclear which wins |
| **passing_score** | `Rubric`, `RubricSnapshot` | Cache (acceptable) | DR-4: Live vs frozen |
| **skill_weights** | `Rubric.skill_weights` (JSON), `SkillDefinition.weight` | Mirror | DR-5: Synced but may diverge |
| **final_score** | `EvaluationResult.final_score` (canonical), `Application.analysis_score` (deprecated mirror) | Legacy mirror | DR-6: ADR-001 confirms canonical, but legacy reads still exist |
| **score_breakdown** | `EvaluationResult.score_breakdown` (JSON), `RubricScoringDetail` (normalized rows) | Dual storage | DR-7: Redundant but acceptable for queryability |

### Risk Assessment

**DR-1 (language): Acceptable with guardrails.** Application-level language should override campaign default for per-candidate customization. But the SSOT rule must be enforced: `Application.language` wins, `BatchJob.language` is the default.

**DR-2 (rubric_id chain): Dangerous.** The 4-layer fallback chain (`EvaluationSession → Application → BatchJob → Job`) means a recruiter changing `Job.rubric_id` affects all campaigns referencing that job, which affects all applications in those campaigns, which affects all evaluation sessions. This is invisible cascade.

**DR-3 (instructions): Dangerous.** Instructions in `Job` vs `BatchJob` — the AI engine uses BatchJob if available, else Job. No clear documentation of this rule.

**DR-4 (passing_score): Acceptable** if snapshot is used. But currently AI reads live rubric.

**DR-5 (skill_weights): Dangerous.** `rubric_loader._sync_rubric_to_skill_definitions()` syncs from Rubric JSON to SkillDefinition table. If a user directly edits one but not the other, they diverge.

**DR-6 (final_score): Acceptable with ADR-001.** Legacy `Application.analysis_score` is a write-through mirror for backward compatibility.

---

## 11. Runtime Audit

### Every Database Query the AI Interview Engine Makes (during one interview)

```
INTERVIEW START:
  1. SELECT * FROM applications WHERE id = ?         — load app
  2. SELECT * FROM evaluation_sessions WHERE ...      — load/create session
  3. SELECT * FROM rubrics WHERE id = ?               — load rubric (via load_rubric)
  4. SELECT * FROM skill_definitions WHERE ...        — resolve skills
  5. SELECT * FROM cv_documents WHERE application_id = ? — load CV
  6. SELECT * FROM batch_jobs WHERE id = ?            — load campaign (via app.batch_job)
  7. INSERT INTO evaluation_sessions ...              — create/update session
  8. INSERT INTO interview_turns ...                  — log turn

EACH TURN:
  9. SELECT * FROM interview_turns WHERE ...          — load history
  10. SELECT * FROM rubric (cached, may query if expired) — re-load rubric
  11. INSERT INTO interview_turns ...                 — save answer
  12. UPDATE evaluation_sessions ...                  — update state

FINAL EVALUATION:
  13. SELECT * FROM evaluation_sessions WHERE ...
  14. SELECT * FROM evaluation_results WHERE ...
  15. SELECT * FROM rubric_scoring_details WHERE ...  — existing scores
  16. SELECT * FROM rubrics WHERE ...                 — re-load rubric
  17. SELECT * FROM skill_definitions WHERE ...
  18. SELECT COUNT(*) FROM interview_turns WHERE ...  — validate turn count
  19. INSERT/UPDATE evaluation_results ...            — final score via ScoringService
  20. INSERT INTO rubric_snapshots ...                — if not already created
  21. INSERT INTO rubric_scoring_details ...          — per-criterion scores
  22. UPDATE applications.status ...                  — state transition
```

### Mutable Dependencies

Every table in the read path is mutable:
- `Rubric` — recruiter can edit any time
- `BatchJob` — recruiter can edit any time
- `Application` — recruiter/system can update
- `SkillDefinition` — sync process can update
- `EvaluationSession` — engine itself mutates this

### Is the Runtime Deterministic?

**NO.** The runtime is NOT deterministic because:

1. **Live Rubric reads**: Different evaluations of the same candidate can produce different results if the Rubric changed between evaluations.
2. **LLM non-determinism**: Question generation uses LLM with `temperature=0.4`, answer evaluation uses `temperature=0.1`. Same input → different output.
3. **Cache-dependent**: `rubric_loader` caches for 5 minutes. A mid-interview cache expiry causes a fresh DB read.
4. **State-machine-dependent**: `update_engine_state()` maintains in-memory state across turns. If the state machine is initialized differently, the interview trajectory changes.

**The target architecture achieves determinism** through `EngineReadOnlyConfig` from an immutable snapshot. This is not yet implemented.

---

## 12. Confusion Report

### C-1: "Which table should I modify to change the interview language?"

**Why it happens:** `language` is on `BatchJob` (campaign default), `Application` (per-candidate override), and `EvaluationSession` (per-session). 

**Which the AI actually uses:** `Application.language` (with a fallback to `"English"`).

**Proposed fix:** Remove `language` from `BatchJob` and `EvaluationSession`. Make `Application.language` the canonical runtime source. Set it from `BatchJob.language` at application creation time.

---

### C-2: "Which rubric does the AI actually use?"

**Why it happens:** `rubric_id` exists on `Job`, `BatchJob`, `Application`, and `EvaluationSession`. Each can differ.

**Which the AI actually uses:** At final evaluation time (`evaluation.py:259-266`):
```python
rubric_db_id = (
    getattr(_es, 'rubric_id', None)
    or getattr(_iv, 'rubric_id', None)
    or app.rubric_id
)
rubric = load_rubric_by_id(rubric_db_id) if rubric_db_id else None
if not rubric:
    rubric, rubric_db_id = load_current_rubric_record(app.job_id)
```
Priority: `EvaluationSession.rubric_id` → `Application.rubric_id` → `Job.rubric_id`

**Proposed fix:** Pin `EvaluationSession.rubric_id` at session creation time to whatever source is correct. Make this immutable for the session's lifetime.

---

### C-3: "What is the passing score?"

**Why it happens:** `Rubric.passing_score` and `RubricSnapshot.passing_score` both exist. The AI engine can read either.

**Which is used:** The AI engine reads from the live `Rubric` object (no snapshot lookup). The `RubricSnapshot.passing_score` exists but is only referenced by `EvaluationResult` after scoring.

**Proposed fix:** Move passing score to campaign config (proposed `campaign_evaluation_configs.passing_score`). Remove from Rubric.

---

### C-4: "Does scoring use snapshot or live rubric?"

**Why it happens:** `RubricSnapshot` exists and `ScoringService._ensure_rubric_snapshot()` creates it, but the AI engine's answer evaluation (`evaluate_answer()` in `ai/interview.py`) reads live `job_rubric` directly.

**Which is used:** Both! Scoring service eventually creates a snapshot (via `_ensure_rubric_snapshot`), but the per-turn scoring reads live. By the time the snapshot is created, the scoring decisions have already been made against live data.

**Proposed fix:** Create the snapshot at interview start, not at scoring time. Force the entire evaluation to use the frozen snapshot.

---

### C-5: "Where do scoring weights come from?"

**Why it happens:** `CANONICAL_WEIGHTS` is a Python constant in `scoring_service.py`. The target architecture describes `scoring_rules` JSON on `campaign_evaluation_configs`. Neither is the other.

**Which is used:** The Python constant. There is no way to configure scoring weights per campaign.

**Proposed fix:** Implement `campaign_evaluation_configs.scoring_rules` as the SSOT for scoring weights. Fall back to hardcoded defaults if not set.

---

### C-6: "How many questions will the candidate get?"

**Why it happens:** `INTERVIEW_TOTAL_QUESTIONS` is a constant in `utils.py`. The target architecture proposes `max_questions` on `campaign_evaluation_configs`.

**Which is used:** The constant. There is no way to configure per campaign.

**Proposed fix:** Add `max_questions` to campaign config (or to `BatchJob` as a temporary measure). Make it configurable per campaign.

---

## 13. Architecture Smells

### SM-1: Hidden Coupling — Rubric is the Skill Tree

The `Rubric` model's `criteria_json` contains the full skill hierarchy. This couples "what skills exist" with "how skills are evaluated". Changing a skill's definition requires loading the entire rubric JSON, modifying it, and re-saving. There is no independent skill catalog.

**Severity: High**

---

### SM-2: Circular Dependency — SkillDefinition ← Rubric

`rubric_loader._sync_rubric_to_skill_definitions()` writes to `SkillDefinition` from Rubric JSON. `rubric_loader._resolve_skill_definitions()` reads from `SkillDefinition` to enrich Rubric. This creates a sync loop where each can overwrite the other depending on which operation runs last.

**Severity: Medium**

---

### SM-3: Leaky Abstraction — Rubric JSON Blob

`Rubric.criteria_json` is a `deferred(Column(Text))` — a deferred TEXT column containing serialized JSON of the `JobRubric` Pydantic model. The database has no awareness of the schema inside this blob. Queries cannot filter by skill name or weight. Schema evolution requires application-level JSON migration.

**Severity: High**

---

### SM-4: God Object — BatchJob

`BatchJob` has 25 columns spanning campaign management (title, status), rubric reference (rubric_id), interview configuration (language, instructions), email automation (template_id, email_sequence_days), analytics (emails_sent, emails_opened), and background processing (worker_status, total_files, processed_files). This model is responsible for too many concerns.

**Severity: Medium**

---

### SM-5: Mutable Runtime Configuration

The AI Interview Engine reads live configuration from 5+ mutable tables during execution. There is no frozen configuration boundary. This means:
- Mid-interview rubric edits can affect question generation
- Mid-evaluation weight changes can affect scoring
- Configuration drift between interview start and final evaluation

**Severity: Critical**

---

### SM-6: Broken Ownership — Application Holds Interview State

Even though the architecture document says "AI interview state → EvaluationSession", the `Application` model still has deprecated columns (`_deprecated_interview_log`, `_deprecated_interview_questions`, `_deprecated_video_file_path`) and property delegations to `EvaluationSession`. The no-op setters (which silently discard writes) are a maintenance trap — developers unaware of the pattern may think they're writing to Application when the data is actually going nowhere.

**Severity: Medium**

---

### SM-7: Multiple Sources of Truth for Campaign Config

Campaign evaluation configuration is scattered across `BatchJob`, `Rubric`, `Job`, `Application`, and `EvaluationSession`. There is no single record that captures "this is the configuration that candidate X was evaluated under."

**Severity: Critical**

---

### SM-8: Versioning Problem — No Config Versioning

When a recruiter edits a rubric or campaign, there is no version history. Candidates completed before the edit may have used different config than candidates after. There is no way to audit which config version produced a given evaluation.

**Severity: High**

---

### SM-9: Configuration Drift — Scoring Weights Hardcoded

The scoring formula weights (`cv=0.25, rubric=0.40, human=0.10, coverage=0.25`) are hardcoded in `scoring_service.py`. The rubrics (`Rubric.skill_weights`) have per-skill weights, but these are only used within the rubric engine for per-criterion scoring, not for the final score computation formula.

**Severity: Medium**

---

### SM-10: Dead Code — Application.analysis_score

Per ADR-001, `Application.analysis_score` is a legacy mirror of `EvaluationResult.final_score`. It is still written by `analysis_columns.py` and read by legacy API consumers. If these two diverge (e.g., due to a bug in the write-through logic), the wrong score will be displayed.

**Severity: Low** (managed by ADR-001)

---

## 14. Final Architecture Score

### Scoring Rubric (1–10 scale)

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| **Database Architecture** | 4/10 | JSON blobs for critical data (criteria_json), scattered configuration, no referential integrity for evaluation config. The target schema (cleanly normalized) scores 8/10 but is not implemented. |
| **Data Flow** | 3/10 | Configuration flows through 4+ fallback chains. No deterministic path. AI engine reads live mutable data. No snapshot isolation. |
| **Ownership** | 5/10 | Entity ownership is well-documented in `docs/entity-ownership.md`, but the actual code violates the documented boundaries (Application holds deprecated interview state, Rubric is the skill tree). |
| **AI Evaluation Pipeline** | 6/10 | The rubric engine (`rubric_engine.py`) is clean and deterministic. ScoringService enforces single-writer. But the pipeline reads live config, and the LLM generation is non-deterministic. |
| **Campaign Architecture** | 2/10 | No dedicated campaign evaluation config exists. BatchJob is overloaded. No publish/version lifecycle. Target architecture is designed but unimplemented. |
| **Skill Tree Design** | 3/10 | Skills are embedded in Rubric JSON. No independent skill catalog. Circular sync between Rubric JSON and SkillDefinition table. |
| **Rubric Design** | 4/10 | Clean Pydantic schema but stored as a JSON blob. Passing score doesn't belong here. Criteria JSON contains skill tree (wrong concern). |
| **Snapshot Design** | 4/10 | RubricSnapshot correctly exists but is underutilized (created lazily at scoring time, not at interview start). No config snapshot exists. |
| **Runtime Determinism** | 2/10 | Not deterministic. Live mutable reads, LLM non-determinism, cache-dependent, state-machine-dependent. |
| **Maintainability** | 5/10 | Well-documented architecture goals (ADR-001, entity-ownership.md, architecture doc) but gap between documented intent and implementation. Multiple deprecation layers add cognitive load. |
| **Scalability** | 7/10 | Stateless workers, Redis caching, event logging to disk. The JSON blob pattern will hurt at scale (cannot query rubric criteria without loading entire rows). |
| **Enterprise Readiness** | 4/10 | No config versioning, no audit trail for which config version produced which evaluation, no snapshot integrity (hash exists in architecture doc but not implemented), no immutability enforcement at DB level. |

### Overall Score: **4.1/10**

The architecture has a clear target state (the `ai_hiring_campaign_manager.md` document is well-designed). The gap between current and target is the problem. Scoring would improve to ~7/10 if the proposed `CampaignEvaluationConfig`, `EvaluationConfigSnapshot`, and `CandidateEvaluationSnapshot` tables were implemented and the AI engine was forced to read only from snapshots.

---

## Recommendations (Summary)

### Critical (fix immediately)

1. **Implement `CampaignEvaluationConfig` table** as the SSOT for campaign evaluation configuration. Move `language`, `passing_score`, `scoring_rules`, `max_questions`, `time_limit_seconds`, `adaptive_difficulty`, `interview_instructions` here.

2. **Create snapshot at interview START, not at scoring time.** Create `EvaluationConfigSnapshot` when the candidate begins their interview. Force the AI engine to read ONLY from the snapshot.

3. **Decouple Rubric from Skill Tree.** Extract skills into an independent normalized catalog. Rubric should reference skills, not contain them.

### High (fix this iteration)

4. **Make question count and scoring weights configurable per campaign.** Remove hardcoded constants.

5. **Pin `rubric_id` on `EvaluationSession` at session creation** and make it immutable for the session's lifetime.

6. **Remove `language` from `BatchJob` and `EvaluationSession`.** Single source: `Application.language`, set from campaign default at application creation.

### Medium (next iteration)

7. **Drop deprecated Application columns** (after verifying no consumers): `_deprecated_interview_log`, `_deprecated_interview_questions`, `_deprecated_video_file_path`, `analysis_score`.

8. **Implement snapshot hash verification** as described in the architecture doc.

9. **Enforce immutability at the database level** for snapshot tables (triggers or RLS).

### Low (backlog)

10. **Normalize `Rubric.criteria_json`** into separate `rubric_criteria` and `rubric_levels` tables.

11. **Implement config versioning** with linked-list version chain (`supersedes_config_id`).

12. **Build admin skill tree UI** to manage skills independently from rubrics.
