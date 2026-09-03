# Architecture Challenge — Multi-Entry AI Interview

> **Auditor's Note:** The previous audit assumed campaign-driven architecture. This document challenges that assumption and redesigns from the constraint that the AI Interview Engine must support unlimited entry points.

---

## 0. The Core Insight

The previous audit had a fundamental blind spot: **it treated Campaign as the primary context for the AI Interview**.

The codebase actually reflects a different reality — the AI Interview Engine is already entry-point-agnostic at its core. It reads from `Application`, and navigates a fallback chain:

```python
# chat.py:490-498 — instructions resolve from any available source
job_instructions = app.job.interview_instructions if app.job else None
campaign_instructions = app.batch_job.interview_instructions if app.batch_job else None
raw_instructions = job_instructions or campaign_instructions or ""

# chat.py:703-728 — rubric resolves from any available source
session_rubric_id = _es.rubric_id       # pinned at session start
if session_rubric_id: load_rubric_by_id(session_rubric_id)
else: load_current_rubric_record(app.job_id)  # fallback to job

# utils.py:626-629 — question count resolves from any source
job_total = app.job.total_questions if app.job else None
batch_total = app.batch_job.total_questions if app.batch_job else None
return job_total or batch_total or INTERVIEW_TOTAL_QUESTIONS
```

The engine already does multi-source resolution. The problem: **it does it live, every time, without freezing the result.**

The correct architecture doesn't force everything through Campaign. It formalizes the **Configuration Resolver** pattern that the codebase is already doing ad-hoc.

---

## 1. What Should Be the Runtime Source of Truth?

**Answer: A new `EvaluationConfigSnapshot` — not Job, not Campaign, not Application, not Rubric.**

Here is why each existing entity fails:

| Entity | Why It Cannot Be SSOT |
|--------|----------------------|
| **Job** | A job may have no campaign; a campaign may override job settings; an individual audit may use a different rubric than the job |
| **Campaign (BatchJob)** | Not every interview belongs to a campaign (Apply to Job, API, certification) |
| **Rubric** | Rubric defines evaluation criteria only — not language, instructions, question count, or scoring weights |
| **Application** | Application is a pipeline state machine, not a configuration holder. It already has too many responsibilities |
| **EvaluationSession** | Session is a lifecycle object (state machine, timers, turns). Mixing mutable lifecycle state with immutable configuration is the current problem |

The runtime SSOT must be:
- **Immutable** after creation
- **Self-contained** (no references to live data)
- **Entry-point-agnostic** (same shape regardless of origin)
- **Created before the engine runs** (so the engine reads frozen data)

This entity does not yet exist in the codebase. The closest is `RubricSnapshot`, but it only freezes the rubric, not the full configuration.

---

## 2. How Should Configuration Be Resolved?

**Every entry point should produce an identical `ResolvedEvaluationConfig` through a Configuration Resolver.**

```
Entry Point ──→ Configuration Resolver ──→ ResolvedEvaluationConfig ──→ AI Engine
                      │                                     │
                      │  reads live data                     │  reads frozen data
                      ▼                                     ▼
               Job, Rubric, Campaign,                EvaluationConfigSnapshot
               defaults, overrides                   (immutable, hashed)
```

The resolver follows a **Resolution Hierarchy**:

```
Explicit Overrides (per-candidate, recruiter-set)
       ↓
Campaign Config (if interview belongs to a campaign)
       ↓
Job Config (if interview belongs to a job)
       ↓
Rubric Defaults (passing_score, criteria, levels)
       ↓
System Defaults (language="English", max_questions=10, time_limit=1800, scoring_weights)
```

Each level **overrides** the level below it. The result is a **fully resolved, self-contained configuration** with no dangling references.

The resolver must be able to run with **minimal context** — at minimum a `rubric_id` (to get evaluation criteria). All other fields have system defaults.

---

## 3. Should the AI Engine Know the Entry Point?

**No. The AI Engine must be completely unaware of the entry point.**

### Advantages of entry-point ignorance:

1. **Determinism:** Same `ResolvedEvaluationConfig` + same candidate input = same evaluation. Entry point is irrelevant.
2. **Testability:** Unit tests inject a mock config. No need to mock campaigns, jobs, or rubrics.
3. **Future-proofing:** New entry points (API, certification, marketplace assessment) produce the same config shape. Engine never changes.
4. **Security:** The engine has no access to the campaign/job context — it cannot accidentally leak data it shouldn't know about.
5. **Simplicity:** One code path, one data contract.

### Disadvantages:

1. **Traceability:** The engine cannot report "this interview failed because the campaign config was invalid." But that's the resolver's job, not the engine's.
2. **Error reporting:** Config validation errors must be caught by the resolver before the engine starts. This is a one-time cost per entry point.

**Verdict:** The advantages overwhelmingly win. The engine should receive exactly one object: `ResolvedEvaluationConfig`.

---

## 4. The Abstraction to Introduce

**`ResolvedEvaluationConfig`** — a self-contained, immutable configuration object.

```python
@dataclass(frozen=True)
class ResolvedEvaluationConfig:
    """Frozen configuration for one AI interview evaluation.
    
    Created by a Configuration Resolver from whatever context is available.
    The AI Engine reads ONLY this object — it has no access to live data.
    """
    # Identity (for traceability, not used by engine logic)
    config_id: str                    # UUID
    snapshot_hash: str                # SHA-256 of content

    # Skills — fully resolved, with all definitions
    skills: list[ResolvedSkill]
    
    # Rubric — fully resolved, with criteria and levels
    rubric_criteria: list[ResolvedCriterion]
    
    # Interview configuration
    language: str                     # "English", "French", "Arabic"
    interview_instructions: str       # Resolved recruiter instructions
    max_questions: int                # e.g. 10
    time_limit_seconds: int           # e.g. 1800
    adaptive_difficulty: bool         # Whether to adapt difficulty
    
    # Scoring configuration
    passing_score: float              # e.g. 60.0
    scoring_weights: ScoringWeights   # e.g. {cv: 0.25, rubric: 0.40, human: 0.10, coverage: 0.25}
    coverage_bonus_max: float         # e.g. 0.25

    # Audit trail
    resolved_from: str                # "job:42", "campaign:7", "direct", "api"
    resolved_at: datetime
    source_version: int               # version of the source config
```

**Why this shape:**
- `skills` and `rubric_criteria` are the **resolved** (not referenced) data. No FK lookups needed.
- Scoring weights are part of the config, not hardcoded in Python.
- `snapshot_hash` enables integrity verification.
- `resolved_from` provides traceability without coupling the engine.

Compare to the proposed `EngineReadOnlyConfig` in the architecture doc — it's the same concept, just with field names that match the existing codebase vocabulary.

---

## 5. Data Flow — All Entry Points Converge

### Entry Point 1: Apply to Job

```
Candidate applies → Application created
       │
       ▼
Interview starts (first message / handshake)
       │
       ▼
Configuration Resolver:
  1. Read Application.job_id → Job
  2. Read Job.rubric_id → Rubric
  3. Resolve skills + criteria from Rubric
  4. Use Job.interview_instructions (if present)
  5. Fill gaps with system defaults (language=English, 
     max_questions=10, scoring_weights=default)
  6. CREATE EvaluationConfigSnapshot (immutable, hashed)
  7. Link snapshot to EvaluationSession
       │
       ▼
AI Engine receives ResolvedEvaluationConfig
       │
       ▼
Interview proceeds with frozen config
```

### Entry Point 2: Campaign Manager

```
Recruiter creates campaign → BatchJob
       │
       ▼
Recruiter configures campaign evaluation settings
  (or uses defaults)
       │
       ▼
Interview starts (first message / handshake)
       │
       ▼
Configuration Resolver:
  1. Read Application.batch_job → BatchJob
  2. Read BatchJob.rubric_id → Rubric
  3. Read BatchJob.language, .interview_instructions,
     .target_role (as config hints)
  4. Resolve skills + criteria from Rubric
  5. Apply campaign overrides over rubric defaults
  6. Fill remaining gaps with system defaults
  7. CREATE EvaluationConfigSnapshot (immutable, hashed)
  8. Link snapshot to EvaluationSession
       │
       ▼
AI Engine receives ResolvedEvaluationConfig
       │
       ▼
Interview proceeds with frozen config
```

**Optimization for Campaigns:** The snapshot CAN be created at **campaign publish time** and reused for all candidates. The resolver checks for a pre-existing campaign snapshot first. If found, skip resolution. This ensures all candidates in the same campaign use identical config.

### Entry Point 3: Individual Recruiter Audit

```
Recruiter uploads single CV → Application created
       │
       ▼
Recruiter selects rubric (or system picks job's rubric)
       │
       ▼
Interview starts
       │
       ▼
Configuration Resolver:
  1. Read recruiter's rubric selection → Rubric
     (or fallback to Application.job_id → Job → Rubric)
  2. Resolve skills + criteria from Rubric
  3. Use recruiter's custom instructions (if provided)
  4. Fill gaps with system defaults
  5. CREATE EvaluationConfigSnapshot (immutable, hashed)
  6. Link snapshot to EvaluationSession
       │
       ▼
AI Engine receives ResolvedEvaluationConfig
       │
       ▼
Interview proceeds with frozen config
```

### Entry Point 4: Future API / Certification / Marketplace

```
External system calls POST /api/v1/interview/start
  with { rubric_id, language, max_questions, ... }
       │
       ▼
Configuration Resolver:
  1. Read Rubric from rubric_id (or accept pre-resolved JSON)
  2. Merge with API-provided overrides
  3. Use provided values for everything else
  4. CREATE EvaluationConfigSnapshot (immutable, hashed)
  5. Link snapshot to EvaluationSession
       │
       ▼
AI Engine receives ResolvedEvaluationConfig
       │
       ▼
Interview proceeds with frozen config
```

### The Convergence Point

```
                    ┌──────────────────┐
                    │ Apply to Job     │
                    └────────┬─────────┘
                             │
                    ┌──────────────────┐
                    │ Campaign Manager │
                    └────────┬─────────┘
                             │
                    ┌──────────────────┐
                    │ Individual Audit │
                    └────────┬─────────┘
                             │
                    ┌──────────────────┐
                    │ Future API       │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────────────────────────┐
                    │      Configuration Resolver          │
                    │                                      │
                    │  Takes: rubric_id + context hints    │
                    │  Returns: ResolvedEvaluationConfig   │
                    │  Side-effect: CREATE snapshot row    │
                    └──────────────────┬───────────────────┘
                                       │
                                       ▼
                    ┌──────────────────────────────────────┐
                    │    EvaluationConfigSnapshot (table)   │
                    │    immutable, hashed, self-contained  │
                    └──────────────────┬───────────────────┘
                                       │
                                       ▼
                    ┌──────────────────────────────────────┐
                    │      EvaluationSession                │
                    │  (linked to snapshot, NOT to config)  │
                    │  Manages only lifecycle state         │
                    └──────────────────┬───────────────────┘
                                       │
                                       ▼
                    ┌──────────────────────────────────────┐
                    │      AI Interview Engine              │
                    │  Reads: ResolvedEvaluationConfig      │
                    │  Writes: InterviewTurn, Score         │
                    │  Knows: NOTHING about entry point     │
                    └──────────────────────────────────────┘
```

---

## 6. When Should the Snapshot Be Created?

**At interview start — specifically, at the `INITIALIZING → IN_PROGRESS` state transition.**

This is the exact moment when:
1. The Application exists (it must, to have an interview)
2. The candidate has engaged (sent the first message)
3. Configuration decisions can no longer be deferred
4. The evaluation must be reproducible

### Why NOT at other points:

| Point | Why It Fails |
|-------|-------------|
| **Campaign creation** | Not every interview belongs to a campaign. The campaign may be created but never used. |
| **Job creation** | Job defines the role, not the evaluation config. Multiple campaigns with different configs can reference the same job. |
| **Candidate assignment** | For "Apply to Job", there is no assignment step. The candidate applies directly. |
| **First AI question** | Too late. The engine needs config to generate the first question. The snapshot must exist before the first LLM call. |
| **CV upload** | CV upload and interview are separate concerns. A candidate may upload CV but never interview. |

### The One Exception: Campaign Pre-Snapshot

For the **Campaign** entry point only, a snapshot CAN be created at **campaign publish time** as an optimization:

```
Campaign publish → Create snapshot → All candidates use same snapshot
```

The interface at interview start:
```
if app.batch_job and app.batch_job.active_snapshot_id:
    snapshot = load_snapshot(app.batch_job.active_snapshot_id)
else:
    snapshot = create_snapshot(app)  # resolve from context
```

This gives campaigns consistency without forcing the pattern on other entry points.

---

## 7. Challenge the Previous Audit

### Recommendations That Were Correct (survive the challenge)

1. **RubricSnapshot is underutilized** — Still true. The snapshot should be created at interview start, used by the engine, not lazily at scoring time.

2. **`language` duplication is dangerous** — Still true. But the fix is not "move to campaign." Instead: **resolve at snapshot creation, eliminate from runtime reads.**

3. **Scoring weights should not be hardcoded** — Still true. But they should be configurable PER CONFIG, not per campaign. Each ResolvedEvaluationConfig carries its own weights.

4. **Rubric JSON blob is a leaky abstraction** — Still true. But the path to fixing it is through the snapshot, not through schema normalization. Store the resolved rubric in the snapshot JSON; the live Rubric table can remain as-is.

5. **No config versioning** — Still true. But versioning should live on `EvaluationConfigSnapshot`, not on campaign. Each snapshot has a version chain regardless of entry point.

### Recommendations That Were Incorrect (assumed campaign-driven)

| Previous Recommendation | Why It's Wrong | Corrected |
|------------------------|---------------|-----------|
| **R1: "Implement CampaignEvaluationConfig as SSOT"** | Campaign is only one entry point. SSOT must be entry-point-agnostic. | **Implement `EvaluationConfigSnapshot` as the runtime SSOT.** Campaign config is one possible source for the resolver, not the SSOT itself. |
| **R2: "Move passing_score from Rubric to campaign config"** | Passing score is a candidate-level decision, not a campaign decision. Different entry points need different passing scores. | **Move passing_score into `EvaluationConfigSnapshot`.** The resolver pulls it from campaign (if available) → rubric default → system default. |
| **R3: "Remove language from BatchJob"** | Removing it from BatchJob breaks the campaign flow where the recruiter sets language once for all candidates. | **Keep language on BatchJob as a resolver hint.** Don't remove it — just ensure the snapshot is the runtime source. |
| **R4: "Campaign should own interview configuration"** | This was the fundamental wrong assumption. Campaign is one producer of config, not the owner. | **No single entity owns the config.** Each entry point produces it through the resolver. The snapshot is the frozen result. |
| **R5: "Create snapshot at campaign publish time"** | Only works for campaigns. Individual audits, job applications, and API calls need different timing. | **Create snapshot at interview start** for all entry points. Allow pre-creation only as a campaign optimization. |

### Previous Conclusions That Are No Longer Valid

**CP-1: "The target architecture doc is the correct direction."**

The target architecture doc (`ai_hiring_campaign_manager.md`) is **too campaign-centric**. Its `CampaignEvaluationConfig` → `EvaluationConfigSnapshot` → `CandidateEvaluationSnapshot` chain assumes campaign ownership. For a multi-entry-point system, the chain should be:

```
[Context: Job/Campaign/Audit/API]
       ↓
Configuration Resolver
       ↓
EvaluationConfigSnapshot          ← entry-point agnostic
       ↓
EvaluationSession (linked to snapshot)
       ↓
AI Engine reads ResolvedEvaluationConfig
```

The `CandidateEvaluationSnapshot` is unnecessary if the snapshot is created at interview start — the `EvaluationSession.snapshot_id` serves the same purpose.

**CP-2: "The Configuration Resolver should be part of the campaign publish flow."**

Wrong. The resolver should be a **standalone service** that any entry point can call. It takes a `rubric_id` and optional overrides; it returns a `ResolvedEvaluationConfig`. Campaign publish can call it, but so can the job application flow and the individual audit flow.

**CP-3: "BatchJob should own the evaluation config."**

Wrong. BatchJob is one possible **input** to the resolver. The resolver reads BatchJob columns (language, instructions, rubric_id) as hints, not as authoritative configuration. The authoritative config is the frozen snapshot.

---

## 8. What This Means for the Codebase

### New Entity: `evaluation_config_snapshots`

```sql
CREATE TABLE evaluation_config_snapshots (
    id              INTEGER PRIMARY KEY AUTO_INCREMENT,
    
    -- Fully resolved, self-contained configuration
    resolved_skills_json         JSON NOT NULL,     -- skills with keywords, levels
    resolved_rubric_json         JSON NOT NULL,     -- criteria with weights, levels
    scoring_rules_json           JSON NOT NULL,     -- weights, formula, coverage_bonus
    interview_config_json        JSON NOT NULL,     -- language, instructions, limits
    passing_score                FLOAT NOT NULL,
    
    -- Integrity
    snapshot_hash                VARCHAR(64) NOT NULL,  -- SHA-256
    
    -- Audit
    resolved_from                VARCHAR(100),     -- "job:42", "campaign:7", "direct"
    source_config_version        INTEGER DEFAULT 1,
    created_by                   INTEGER REFERENCES users(id),
    created_at                   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_ecs_created (created_at)
);
```

### Modified Entity: `evaluation_sessions`

Add column:
```sql
ALTER TABLE evaluation_sessions 
    ADD COLUMN evaluation_config_snapshot_id INTEGER 
    REFERENCES evaluation_config_snapshots(id);
```

This replaces the current scatter of `rubric_id`, `rubric_version`, `rubric_snapshot_id`, and `language` on EvaluationSession.

### New Service: `ConfigurationResolver`

```python
class ConfigurationResolver:
    """Produces an immutable ResolvedEvaluationConfig from any context."""
    
    @staticmethod
    def resolve(
        *,
        db: Session,
        rubric_id: Optional[int] = None,
        job_id: Optional[int] = None,
        campaign_id: Optional[int] = None,
        recruiter_id: Optional[int] = None,
        language_override: Optional[str] = None,
        instructions_override: Optional[str] = None,
        max_questions_override: Optional[int] = None,
        time_limit_override: Optional[int] = None,
        scoring_weights_override: Optional[dict] = None,
        passing_score_override: Optional[float] = None,
    ) -> ResolvedEvaluationConfig:
        """Resolve a complete evaluation configuration.
        
        Resolution hierarchy (each level overrides the previous):
        1. System defaults
        2. Rubric defaults (passing_score, criteria)
        3. Job config (instructions, if no campaign)
        4. Campaign config (language, instructions, overrides)
        5. Explicit overrides (recruiter or API-provided)
        
        The result is hashed and persisted as an immutable snapshot.
        """
```

### Impact on AI Engine

Current code in `chat.py:603-627`:
```python
if is_handshake:
    pinned_rubric_id = ...
    pinned_rubric_version = ...
    sync_ai_interview_session(db, app, rubric_id=..., rubric_version=...)
```

Should become:
```python
if is_handshake:
    if not _es.evaluation_config_snapshot_id:
        config = ConfigurationResolver.resolve(
            db=db,
            job_id=app.job_id,
            campaign_id=app.batch_job_id if app.batch_job else None,
            rubric_id=app.rubric_id,
            language_override=app.language,
        )
        _es.evaluation_config_snapshot_id = config.config_id
```

Then every subsequent read of language, rubric, instructions, max_questions, scoring_weights, passing_score reads from `_es.config_snapshot` — never from live tables.

### Migration Path

1. Create `evaluation_config_snapshots` table
2. Add `evaluation_config_snapshot_id` to `evaluation_sessions`
3. Build `ConfigurationResolver` service
4. At interview start (chat.py handshake path), call resolver, store snapshot_id
5. Modify AI Engine to read from snapshot instead of live data
6. Backfill: create snapshots for existing in-progress sessions
7. (Optional) Add campaign publish hook to pre-create snapshots

---

## 9. Summary: Before vs After

| Concern | Before (Current) | After (Proposed) |
|---------|-----------------|-----------------|
| **Runtime SSOT** | None — reads from 5+ live tables | `EvaluationConfigSnapshot` (immutable, hashed) |
| **Entry point** | Engine navigates fallback chains | Engine knows nothing — config is pre-resolved |
| **Snapshot timing** | Lazily at scoring time (RubricSnapshot) | At interview start (full config snapshot) |
| **Config versioning** | None | Snapshot hash + source_config_version |
| **Scoring weights** | Hardcoded in Python | Per-config in `scoring_rules_json` |
| **Question count** | Hardcoded constant | Per-config in `interview_config_json` |
| **Language** | 4 places, live reads | Resolved once into snapshot |
| **Campaign coupling** | Campaign is assumed primary | Campaign is one input among many |
| **Future entry points** | Require engine changes | Only need a new resolver path |
