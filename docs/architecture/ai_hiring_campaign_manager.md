# AI Hiring Campaign Manager — Refactored Architecture

## A) Final Architecture Diagram

```
┌═════════════════════════════════════════════════════════════════════════┐
║                      ADMIN WORKSPACE (Templates)                       ║
║                                                                         ║
║  ┌─────────────────────┐     ┌──────────────────────────────────┐      ║
║  │  Skill Tree         │────>│  skill_tree_templates             │      ║
║  │  Template Admin     │     │  ┌─────────────────────────────┐  │      ║
║  │                     │     │  │ skills (normalized table)   │  │      ║
║  │  Purpose:           │     │  │ skill_categories            │  │      ║
║  │  Define WHAT        │     │  │ skill_tree_skills (links)   │  │      ║
║  │  skills exist.      │     │  └─────────────────────────────┘  │      ║
║  │  No evaluation      │     └──────────────────────────────────┘      ║
║  │  logic.             │                                              ║
║  └─────────────────────┘                                              ║
║                                                                         ║
║  ┌─────────────────────┐     ┌──────────────────────────────────┐      ║
║  │  Rubric Builder     │────>│  rubrics                         │      ║
║  │  (Template OR       │     │  ┌─────────────────────────────┐  │      ║
║  │   Campaign-level)   │     │  │ rubric_criteria             │  │      ║
║  │                     │     │  │ rubric_levels               │  │      ║
║  │  Purpose:           │     │  └─────────────────────────────┘  │      ║
║  │  Define HOW skills  │     └──────────────────────────────────┘      ║
║  │  are evaluated.     │                                              ║
║  └─────────────────────┘                                              ║
╚═════════════════════════════════════════════════════════════════════════╝
                                    │
        Select & Customize ─────────┼───────── (recruiter campaign setup)
                                    ▼
┌═════════════════════════════════════════════════════════════════════════┐
║                    SSOT — CampaignEvaluationConfig                     ║
║                                                                         ║
║  ┌─────────────────────────────────────────────────────────────────┐   ║
║  │  campaign_evaluation_configs                                    │   ║
║  │  ┌───────────────────────────────────────────────────────────┐  │   ║
║  │  │ status: 'draft' | 'published' | 'archived'                │  │   ║
║  │  │ version: INTEGER (auto-increment per campaign)            │  │   ║
║  │  │                                                           │  │   ║
║  │  │ skill_tree_template_id (FK — nullable)                   │  │   ║
║  │  │ rubric_id (FK — nullable)                                │  │   ║
║  │  │ campaign_id (FK → batch_jobs.id)                         │  │   ║
║  │  │                                                           │  │   ║
║  │  │ skill_weight_overrides (JSON — only deltas)              │  │   ║
║  │  │ scoring_rules (JSON — weights, formula)                  │  │   ║
║  │  │ interview_language, interview_instructions                │  │   ║
║  │  │ passing_score, time_limit_seconds, max_questions          │  │   ║
║  │  │                                                           │  │   ║
║  │  │ supersedes_config_id (FK self — version chain)           │  │   ║
║  │  │ published_at, published_by (FK → users.id)               │  │   ║
║  │  └───────────────────────────────────────────────────────────┘  │   ║
║  └─────────────────────────────────────────────────────────────────┘   ║
╚═════════════════════════════════════════════════════════════════════════╝
                                    │ PUBLISH
                                    ▼
┌═════════════════════════════════════════════════════════════════════════┐
║                   IMMUTABLE SNAPSHOT LAYER                             ║
║                                                                         ║
║  ┌─────────────────────────────────────────────────────────────────┐   ║
║  │  evaluation_config_snapshots                                   │   ║
║  │  ┌───────────────────────────────────────────────────────────┐  │   ║
║  │  │ id, config_id (FK), config_version                        │  │   ║
║  │  │                                                           │  │   ║
║  │  │ rubric_snapshot_id (FK → rubric_snapshots.id)            │  │   ║
║  │  │ resolved_skills_json (full — NOT deltas)                 │  │   ║
║  │  │ resolved_rubric_json (full — levels, indicators, etc.)   │  │   ║
║  │  │ scoring_rules_json (frozen weights)                      │  │   ║
║  │  │ interview_config_json (language, instructions, etc.)     │  │   ║
║  │  │ passing_score                                            │  │   ║
║  │  │                                                           │  │   ║
║  │  │ snapshot_hash (SHA-256 of content)                       │  │   ║
║  │  │ created_by, published_by, published_at                   │  │   ║
║  │  │ source_config_version                                    │  │   ║
║  │  │ change_summary (TEXT — human-readable diff)              │  │   ║
║  │  │ created_at (immutable)                                   │  │   ║
║  │  └───────────────────────────────────────────────────────────┘  │   ║
║  └─────────────────────────────────────────────────────────────────┘   ║
╚═════════════════════════════════════════════════════════════════════════╝
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │  assign to candidate      │  assign to candidate      │
        ▼                           ▼                           ▼
┌───────────────────┐   ┌───────────────────┐   ┌───────────────────┐
│ CandidateEval     │   │ CandidateEval     │   │ CandidateEval     │
│ Snapshot v1       │   │ Snapshot v1       │   │ Snapshot v2       │
│ (Alice)           │   │ (Bob)             │   │ (Frank)           │
│                   │   │                   │   │                   │
│ config_snapshot   │   │ config_snapshot   │   │ config_snapshot   │
│   _id =ECS-v1     │   │   _id =ECS-v1     │   │   _id =ECS-v2     │
│ application_id    │   │ application_id    │   │ application_id    │
│ campaign_id       │   │ campaign_id       │   │ campaign_id       │
└────────┬──────────┘   └────────┬──────────┘   └────────┬──────────┘
         │                       │                       │
         │ interview starts      │ interview starts      │ interview starts
         ▼                       ▼                       ▼
┌───────────────────┐   ┌───────────────────┐   ┌───────────────────┐
│ EvaluationSession │   │ EvaluationSession │   │ EvaluationSession │
│ (Alice)           │   │ (Bob)             │   │ (Frank)           │
│                   │   │                   │   │                   │
│ candidate_eval_   │   │ candidate_eval_   │   │ candidate_eval_   │
│   snapshot_id     │   │   snapshot_id     │   │   snapshot_id     │
│ rubric_snapshot_id│   │ rubric_snapshot_id│   │ rubric_snapshot_id│
│                   │   │                   │   │                   │
└────────┬──────────┘   └────────┬──────────┘   └────────┬──────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌═════════════════════════════════════════════════════════════════════════┐
║                    AI INTERVIEW ENGINE (READ-ONLY)                     ║
║                                                                         ║
║  RECEIVES: EvaluationConfigSnapshot (via candidate_eval_snapshot)       ║
║                                                                         ║
║  CAN READ:                                                              ║
║  ├─ resolved_skills      → skill definitions for question generation   ║
║  ├─ resolved_rubric      → criteria + levels for scoring              ║
║  ├─ scoring_rules        → how to compute final score                 ║
║  ├─ interview_config     → language, instructions, limits             ║
║  └─ passing_score        → pass/fail threshold                        ║
║                                                                         ║
║  CAN WRITE:                                                             ║
║  ├─ interview_turns      → questions & answers                         ║
║  ├─ rubric_scoring_details → per-criterion scores                     ║
║  ├─ extracted_skills     → evidence extracted from answers            ║
║  └─ evaluation_results   → final scores via ScoringService            ║
║                                                                         ║
║  CANNOT WRITE:                                                          ║
║  ├─ skills               ║  ├─ rubrics            ║  ├─ configs       ║
║  ├─ snapshots            ║  ├─ templates          ║  └─ campaigns     ║
║                                                                         ║
╚═════════════════════════════════════════════════════════════════════════╝
```

---

## B) Clean Database Schema

### Entity Responsibility Summary

| Entity | Owner | Scope | Mutability | Purpose |
|--------|-------|-------|------------|---------|
| `skill_tree_templates` | Admin | Global | Mutable (draft) | Defines WHAT skills exist |
| `skills` | Admin | Global | Mutable | Canonical skill definitions |
| `skill_categories` | Admin | Per-tree | Mutable | Category hierarchy in a tree |
| `skill_tree_skills` | Admin | Per-tree | Mutable | Links skills into tree structure |
| `rubrics` | Admin/Recruiter | Job/Campaign | Mutable (draft) | Defines HOW skills are evaluated |
| `rubric_criteria` | Admin/Recruiter | Per-rubric | Mutable | Scoring criteria linked to skills |
| `rubric_levels` | Admin/Recruiter | Per-criterion | Mutable | Score bands with indicators |
| `campaign_evaluation_configs` | Recruiter | Per-campaign | Mutable (draft) | **SSOT** — combines tree + rubric |
| `evaluation_config_snapshots` | System | Per-publish | **IMMUTABLE** | Frozen config at publish time |
| `rubric_snapshots` | System | Per-snapshot | **IMMUTABLE** | Frozen rubric at snapshot time |
| `candidate_evaluation_snapshots` | System | Per-candidate | Immutable after creation | Links candidate to snapshot |
| `evaluation_sessions` | System | Per-interview | Mutable | Interview lifecycle |
| `evaluation_results` | System | Per-session | Mutable (append) | Final scores & breakdown |
| `rubric_scoring_details` | System | Per-result | Immutable after write | Per-criterion scores |

---

### 1. `skills` — Global normalized skill definitions

```sql
CREATE TABLE skills (
    id              VARCHAR(36) PRIMARY KEY,   -- UUID
    name            VARCHAR(200) NOT NULL,
    description     TEXT,
    keywords        JSON,                       -- Keywords for evidence matching
    metadata        JSON,                       -- Extensible (source, version, etc.)
    
    -- Audit
    created_by      INTEGER REFERENCES users(id),
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    archived_at     DATETIME,
    
    UNIQUE INDEX uq_skill_name (name),
    INDEX idx_skills_archived (archived_at)
);
```

**Design note:** `keywords` and `metadata` are JSON because they are inherently variable-length lists/dicts that are always read together with the skill row and never queried independently. Using JSON here avoids 3 additional junction tables with negligible query cost.

### 2. `skill_tree_templates` — Admin-managed global skill tree library

```sql
CREATE TABLE skill_tree_templates (
    id              INTEGER PRIMARY KEY AUTO_INCREMENT,
    title           VARCHAR(255) NOT NULL,
    description     TEXT,
    industry        VARCHAR(100),               -- "tech", "finance", "healthcare"
    role_category   VARCHAR(100),               -- "engineering", "sales", "marketing"
    seniority       VARCHAR(50),                -- "junior", "mid", "senior", "lead"
    
    -- Lifecycle
    status          VARCHAR(20) NOT NULL DEFAULT 'draft',
                    -- 'draft' | 'published' | 'archived'
    version         INTEGER NOT NULL DEFAULT 1,
    
    -- Audit
    created_by      INTEGER REFERENCES users(id),
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    published_at    DATETIME,
    archived_at     DATETIME,
    
    INDEX idx_stt_status (status),
    INDEX idx_stt_industry (industry),
    INDEX idx_stt_role (role_category)
);
```

### 3. `skill_categories` — Hierarchical categories within a skill tree

```sql
CREATE TABLE skill_categories (
    id                      INTEGER PRIMARY KEY AUTO_INCREMENT,
    skill_tree_template_id  INTEGER NOT NULL REFERENCES skill_tree_templates(id),
    parent_category_id      INTEGER REFERENCES skill_categories(id),  -- self-referential for nesting
    name                    VARCHAR(200) NOT NULL,
    description             TEXT,
    sort_order              INTEGER NOT NULL DEFAULT 0,
    
    INDEX idx_sc_tree (skill_tree_template_id),
    INDEX idx_sc_parent (parent_category_id)
);
```

### 4. `skill_tree_skills` — Links skills into a tree with position metadata

```sql
CREATE TABLE skill_tree_skills (
    id                      INTEGER PRIMARY KEY AUTO_INCREMENT,
    skill_tree_template_id  INTEGER NOT NULL REFERENCES skill_tree_templates(id),
    category_id             INTEGER NOT NULL REFERENCES skill_categories(id),
    skill_id                VARCHAR(36) NOT NULL REFERENCES skills(id),
    parent_skill_node_id    INTEGER REFERENCES skill_tree_skills(id), -- for sub-skills
    sort_order              INTEGER NOT NULL DEFAULT 0,
    is_required             BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Weight is NOT stored here — it belongs in the Rubric
    
    INDEX idx_sts_tree (skill_tree_template_id),
    INDEX idx_sts_category (category_id),
    INDEX idx_sts_skill (skill_id),
    UNIQUE INDEX uq_sts_tree_skill (skill_tree_template_id, skill_id)
);
```

**Boundary enforcement:** `skill_tree_skills` contains NO scoring data (no weight, no score, no level). This table only defines WHAT skills exist in the tree and how they are organized. All evaluation-related data belongs in the Rubric tables.

### 5. `rubrics` — Evaluation rubric definitions

```sql
CREATE TABLE rubrics (
    id              INTEGER PRIMARY KEY AUTO_INCREMENT,
    skill_tree_template_id INTEGER REFERENCES skill_tree_templates(id),  -- nullable: rubric can be general
    title           VARCHAR(255) NOT NULL,
    description     TEXT,
    
    -- Scope: template-level (shared) or campaign-level (private copy)
    scope           VARCHAR(20) NOT NULL DEFAULT 'template',
                    -- 'template' | 'campaign'
    
    -- Lifecycle
    status          VARCHAR(20) NOT NULL DEFAULT 'draft',
                    -- 'draft' | 'published' | 'archived'
    version         INTEGER NOT NULL DEFAULT 1,
    
    -- Default passing threshold (can be overridden in campaign config)
    default_passing_score FLOAT DEFAULT 60.0,
    default_max_score     FLOAT DEFAULT 100.0,
    
    -- Audit
    created_by      INTEGER REFERENCES users(id),
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    published_at    DATETIME,
    archived_at     DATETIME,
    
    INDEX idx_rubrics_scope (scope),
    INDEX idx_rubrics_status (status),
    INDEX idx_rubrics_tree (skill_tree_template_id)
);
```

### 6. `rubric_criteria` — Individual scoring criteria (each linked to a skill)

```sql
CREATE TABLE rubric_criteria (
    id              INTEGER PRIMARY KEY AUTO_INCREMENT,
    rubric_id       INTEGER NOT NULL REFERENCES rubrics(id),
    skill_id        VARCHAR(36) REFERENCES skills(id),  -- nullable: general criterion
    name            VARCHAR(255) NOT NULL,
    description     TEXT,
    
    -- Scoring
    weight          FLOAT NOT NULL DEFAULT 1.0,       -- relative weight in final score
    max_score       FLOAT NOT NULL DEFAULT 100.0,
    sort_order      INTEGER NOT NULL DEFAULT 0,
    
    -- Evidence rules
    min_evidence_count       INTEGER DEFAULT 1,
    require_technical_proof  BOOLEAN DEFAULT FALSE,
    require_behavioral_proof BOOLEAN DEFAULT FALSE,
    
    INDEX idx_rc_rubric (rubric_id),
    INDEX idx_rc_skill (skill_id)
);
```

**Weight ownership:** `rubric_criteria.weight` is the canonical source of scoring weights. The Skill Tree does NOT store weights. Campaign config can override these via `skill_weight_overrides` JSON.

### 7. `rubric_levels` — Score bands with performance descriptors

```sql
CREATE TABLE rubric_levels (
    id                      INTEGER PRIMARY KEY AUTO_INCREMENT,
    rubric_criterion_id     INTEGER NOT NULL REFERENCES rubric_criteria(id),
    name                    VARCHAR(100) NOT NULL,   -- "Expert", "Proficient", "Beginner"
    score_min               FLOAT NOT NULL,          -- e.g., 0, 30, 70
    score_max               FLOAT NOT NULL,          -- e.g., 30, 70, 100
    description             TEXT NOT NULL,            -- What this level means
    behavioral_indicators   JSON,                    -- ["communicates clearly", ...]
    technical_indicators    JSON,                    -- ["writes SQL joins", ...]
    evidence_requirements   JSON,                    -- ["must show code example", ...]
    sort_order              INTEGER NOT NULL DEFAULT 0,
    
    INDEX idx_rl_criterion (rubric_criterion_id),
    
    CONSTRAINT ck_rl_score_range CHECK (score_min >= 0 AND score_max <= 100 AND score_min < score_max)
);
```

**JSON note:** `behavioral_indicators`, `technical_indicators`, and `evidence_requirements` are JSON lists of descriptive strings. These are always read together with the level row, never queried independently, and inherently variable in length. Normalizing them would create 3 additional tables with no query benefit.

### 8. `campaign_evaluation_configs` — SSOT per campaign

```sql
CREATE TABLE campaign_evaluation_configs (
    id              INTEGER PRIMARY KEY AUTO_INCREMENT,
    campaign_id     INTEGER NOT NULL REFERENCES batch_jobs(id),
    
    -- Lifecycle
    status          VARCHAR(20) NOT NULL DEFAULT 'draft',
                    -- 'draft' | 'published' | 'archived'
    version         INTEGER NOT NULL DEFAULT 1,
    
    -- Source references
    skill_tree_template_id  INTEGER REFERENCES skill_tree_templates(id),
    rubric_id               INTEGER REFERENCES rubrics(id),
    
    -- Customizations (JSON deltas from template/rubric defaults)
    skill_weight_overrides  JSON,  -- {"React Hooks": {"weight": 2.0, "is_required": true}}
    
    -- Scoring rules
    scoring_rules   JSON NOT NULL,
    -- {
    --   "weights": {"cv_score": 0.25, "rubric_score": 0.40, "human_score": 0.10, "coverage_bonus": 0.25},
    --   "formula": "weighted_sum",
    --   "coverage_bonus_max": 0.25
    -- }
    
    passing_score       FLOAT NOT NULL DEFAULT 60.0,
    
    -- Interview configuration
    interview_language          VARCHAR(50) NOT NULL DEFAULT 'English',
    interview_instructions      TEXT,
    max_questions               INTEGER DEFAULT 15,
    time_limit_seconds          INTEGER DEFAULT 1800,
    adaptive_difficulty         BOOLEAN DEFAULT TRUE,
    
    -- Version chain (linked list of versions)
    supersedes_config_id INTEGER REFERENCES campaign_evaluation_configs(id),
    
    -- Audit
    created_by      INTEGER REFERENCES users(id),
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    published_at    DATETIME,
    published_by    INTEGER REFERENCES users(id),
    archived_at     DATETIME,
    
    INDEX idx_cec_campaign (campaign_id),
    INDEX idx_cec_status (status),
    UNIQUE INDEX uq_cec_campaign_version (campaign_id, version)
);
```

**Why JSON on config?** `skill_weight_overrides` and `scoring_rules` are stored as JSON because:
- They represent DELTAS from the template/rubric defaults (variable shape)
- They are never queried independently — always read with the config row
- The resolved/expanded version is what goes into the snapshot

### 9. `evaluation_config_snapshots` — Immutable frozen config

```sql
CREATE TABLE evaluation_config_snapshots (
    id              INTEGER PRIMARY KEY AUTO_INCREMENT,
    config_id       INTEGER NOT NULL REFERENCES campaign_evaluation_configs(id),
    config_version  INTEGER NOT NULL,  -- literal version for audit trail
    
    -- Frozen rubric state
    rubric_snapshot_id  INTEGER REFERENCES rubric_snapshots(id),
    
    -- FULLY RESOLVED (not deltas) — self-contained immutable snapshot
    resolved_skills_json        JSON NOT NULL,
    -- {
    --   "categories": [
    --     {"name": "Frontend", "skills": [
    --       {"name": "React Hooks", "keywords": ["useState", "useEffect"], "is_required": true}
    --     ]}
    --   ]
    -- }
    
    resolved_rubric_json        JSON NOT NULL,
    -- {
    --   "criteria": [
    --     {"skill_name": "React Hooks", "weight": 2.0, "levels": [
    --       {"score_min": 0, "score_max": 30, "description": "Basic understanding", "indicators": [...]}
    --     ]}
    --   ]
    -- }
    
    scoring_rules_json          JSON NOT NULL,
    interview_config_json       JSON NOT NULL,
    passing_score               FLOAT NOT NULL,
    
    -- Integrity
    snapshot_hash   VARCHAR(64) NOT NULL,  -- SHA-256(content)
    
    -- Audit
    created_by      INTEGER REFERENCES users(id),
    published_by    INTEGER REFERENCES users(id),
    published_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source_config_version INTEGER NOT NULL,
    change_summary  TEXT,  -- Human-readable: "Increased React weight from 1.0 to 2.0"
    
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,  -- IMMUTABLE
    
    INDEX idx_ecs_config (config_id),
    INDEX idx_ecs_snapshot (rubric_snapshot_id)
);
```

**Immutability guarantee:** Once inserted, no UPDATE or DELETE operations are permitted. This is enforced at the application layer and optionally via database triggers/RLS.

**Snapshot hash computation:**
```python
import hashlib, json
content = {
    "resolved_skills": snapshot.resolved_skills_json,
    "resolved_rubric": snapshot.resolved_rubric_json,
    "scoring_rules": snapshot.scoring_rules_json,
    "interview_config": snapshot.interview_config_json,
    "passing_score": snapshot.passing_score,
    "published_at": snapshot.published_at.isoformat(),
    "source_config_version": snapshot.source_config_version,
}
snapshot_hash = hashlib.sha256(
    json.dumps(content, sort_keys=True, default=str).encode()
).hexdigest()
```

### 10. `candidate_evaluation_snapshots` — Per-candidate config assignment

```sql
CREATE TABLE candidate_evaluation_snapshots (
    id              INTEGER PRIMARY KEY AUTO_INCREMENT,
    campaign_id     INTEGER NOT NULL REFERENCES batch_jobs(id),
    application_id  INTEGER NOT NULL REFERENCES applications(id),
    evaluation_config_snapshot_id INTEGER NOT NULL REFERENCES evaluation_config_snapshots(id),
    
    -- When this assignment was made
    assigned_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    assigned_by     VARCHAR(50) DEFAULT 'system',  -- 'system' | 'recruiter' | 're-evaluation'
    
    -- Soft-delete for re-assignment
    superseded_at   DATETIME,  -- if re-assigned to a new snapshot
    superseded_by   INTEGER REFERENCES candidate_evaluation_snapshots(id),
    
    UNIQUE INDEX uq_ces_candidate (application_id, superseded_at),
    INDEX idx_ces_campaign (campaign_id),
    INDEX idx_ces_snapshot (evaluation_config_snapshot_id)
);
```

### 11. Modified: `batch_jobs` — Link to active evaluation config

```sql
ALTER TABLE batch_jobs ADD COLUMN evaluation_config_id INTEGER 
    REFERENCES campaign_evaluation_configs(id);
ALTER TABLE batch_jobs ADD INDEX idx_bj_eval_config (evaluation_config_id);
```

### 12. Modified: `evaluation_sessions` — Link to candidate snapshot

```sql
ALTER TABLE evaluation_sessions ADD COLUMN candidate_evaluation_snapshot_id INTEGER 
    REFERENCES candidate_evaluation_snapshots(id);
ALTER TABLE evaluation_sessions ADD INDEX idx_es_candidate_snapshot (candidate_evaluation_snapshot_id);
```

Immutable `evaluation_config_snapshot_id` on `evaluation_sessions` for direct engine access:
```sql
ALTER TABLE evaluation_sessions ADD COLUMN evaluation_config_snapshot_id INTEGER 
    REFERENCES evaluation_config_snapshots(id);
ALTER TABLE evaluation_sessions ADD INDEX idx_es_config_snapshot (evaluation_config_snapshot_id);
```

### Entity-Relationship Summary

```
skill_tree_templates (1)──< skill_categories (many)
       │                           │
       │                           └── parent_category_id (self-ref)
       │
       └──< skill_tree_skills (many)
                │
                ├── skill_id ──> skills (1)
                └── parent_skill_node_id (self-ref)

rubrics (1)──< rubric_criteria (many)
                  │
                  ├── skill_id ──> skills (1, nullable)
                  └──< rubric_levels (many)

campaign_evaluation_configs (1)
    ├── campaign_id ──> batch_jobs (1)
    ├── skill_tree_template_id ──> skill_tree_templates (1, nullable)
    ├── rubric_id ──> rubrics (1, nullable)
    └── supersedes_config_id (self-ref, nullable)
           │
           └──< evaluation_config_snapshots (many)
                   │
                   ├── rubric_snapshot_id ──> rubric_snapshots (1, nullable)
                   │                               │
                   │                               └── original_rubric_id ──> rubrics (1, nullable)
                   │
                   └──< candidate_evaluation_snapshots (many)
                            │
                            ├── application_id ──> applications (1)
                            └──< evaluation_sessions (many)
                                     │
                                     ├── evaluation_result (1:1)
                                     └── rubric_scoring_details (many)
```

---

## C) Configuration Lifecycle

### State Machine

```
                          ┌─────────────────────────────┐
                          │         DRAFT               │
                          │                             │
                          │ Recruiter edits freely       │
                          │ Multiple saves OK            │
                          │ version increments on save   │
                          └─────────────┬───────────────┘
                                        │ PUBLISH
                                        ▼
                          ┌─────────────────────────────┐
                          │       PUBLISHED             │
                          │                             │
                          │ 1. CREATE snapshot          │
                          │ 2. Assign snapshot hash     │
                          │ 3. SET active config on     │
                          │    campaign                 │
                          │ 4. status = 'published'     │
                          │                             │
                          │ New candidates get this     │
                          └──────┬──────────────┬───────┘
                                 │              │
                    ┌────────────┘              └────────────┐
                    │                                         │
                    ▼                                         ▼
    ┌─────────────────────────┐             ┌─────────────────────────────┐
    │     EDIT                │             │         ARCHIVED            │
    │                         │             │                             │
    │ Creates NEW draft       │             │ No new candidates           │
    │ (version+1)             │             │ Existing evaluations        │
    │ Previous stays          │             │ preserved in snapshots      │
    │ published until re-     │             │                             │
    │ publish                 │             │ Read-only historical        │
    └─────────────────────────┘             └─────────────────────────────┘
```

### Publish Implementation (pseudo-code)

```python
def publish_config(config_id: int, published_by: int, db: Session) -> EvaluationConfigSnapshot:
    config = db.query(CampaignEvaluationConfig).get(config_id)
    assert config.status == 'draft'
    assert config.campaign_id is not None
    
    # 1. Resolve skills: merge template skills + campaign overrides
    resolved_skills = resolve_skills(config, db)
    
    # 2. Resolve rubric: merge rubric criteria + campaign weight overrides
    resolved_rubric = resolve_rubric(config, db)
    
    # 3. Create RubricSnapshot (freeze rubric state)
    rubric_snapshot = create_rubric_snapshot(config, db)
    
    # 4. Compute snapshot hash
    snapshot_hash = compute_snapshot_hash(resolved_skills, resolved_rubric, config)
    
    # 5. Create immutable snapshot
    snapshot = EvaluationConfigSnapshot(
        config_id=config.id,
        config_version=config.version,
        rubric_snapshot_id=rubric_snapshot.id,
        resolved_skills_json=resolved_skills,
        resolved_rubric_json=resolved_rubric,
        scoring_rules_json=config.scoring_rules,
        interview_config_json=build_interview_config_json(config),
        passing_score=config.passing_score,
        snapshot_hash=snapshot_hash,
        created_by=published_by,
        published_by=published_by,
        published_at=datetime.utcnow(),
        source_config_version=config.version,
        change_summary=build_change_summary(config, db),
    )
    db.add(snapshot)
    
    # 6. Update campaign's active config pointer
    campaign = db.query(BatchJob).get(config.campaign_id)
    campaign.evaluation_config_id = config.id
    
    # 7. Mark config as published
    config.status = 'published'
    config.published_at = datetime.utcnow()
    config.published_by = published_by
    
    db.commit()
    return snapshot
```

### Edit Creates New Draft

```python
def create_next_draft(current_config_id: int, created_by: int, db: Session) -> CampaignEvaluationConfig:
    current = db.query(CampaignEvaluationConfig).get(current_config_id)
    assert current.status == 'published'
    
    new_draft = CampaignEvaluationConfig(
        campaign_id=current.campaign_id,
        status='draft',
        version=current.version + 1,
        skill_tree_template_id=current.skill_tree_template_id,
        rubric_id=current.rubric_id,
        skill_weight_overrides=current.skill_weight_overrides,
        scoring_rules=current.scoring_rules,
        passing_score=current.passing_score,
        interview_language=current.interview_language,
        interview_instructions=current.interview_instructions,
        max_questions=current.max_questions,
        time_limit_seconds=current.time_limit_seconds,
        adaptive_difficulty=current.adaptive_difficulty,
        supersedes_config_id=current.id,
        created_by=created_by,
    )
    db.add(new_draft)
    db.commit()
    return new_draft
```

---

## D) Versioning Strategy

### Rules

1. **Every publish creates a new immutable snapshot.** The snapshot is never modified.
2. **Existing candidates keep their assigned snapshot.** If a candidate was assigned `snapshot v1`, they use `v1` even after `v2` is published.
3. **New candidates get the active snapshot.** When added to the campaign after publish, they get `v2`.
4. **Re-evaluation is explicit.** A recruiter can re-assign a candidate to a newer snapshot, which creates a new `candidate_evaluation_snapshot` row (superseding the old one).
5. **Version chain is a linked list.** Each config references its predecessor via `supersedes_config_id`.
6. **Snapshot hash guarantees integrity.** Any modification to snapshot data is detectable.

### Versioning Flow: Example

```
Time  Config v1 (published)
  │    ├─ Snapshot v1 created
  │    ├─ Alice assigned → candidate_eval_snapshot (v1)
  │    ├─ Bob assigned → candidate_eval_snapshot (v1)
  │    └─ Interviews use v1 snapshot
  │
  │    Recruiter edits weights → Config v2 (draft)
  │
Time  Config v2 (published)
  │    ├─ Snapshot v2 created
  │    ├─ Frank assigned → candidate_eval_snapshot (v2)
  │    ├─ Alice & Bob → still on v1 (unchanged)
  │    └─ New interviews for Frank use v2
  │
  │    Recruiter re-evaluates Alice with v2
  │    ├─ Alice's old candidate_eval_snapshot superseded
  │    ├─ New candidate_eval_snapshot (v2) created
  │    ├─ New EvaluationSession created (linked to v2 snapshot)
  │    └─ Old EvaluationSession preserved for audit
  │
Time  Config v2 archived
  │    ├─ No new candidates can be assigned
  │    └─ Existing results preserved indefinitely
```

### Snapshot Uniqueness

```sql
-- Two snapshots are identical IFF their hashes match.
-- This allows deduplication if the same config is re-published without changes.
-- Each snapshot still has a unique ID for referential integrity.
```

---

## E) AI Interview Integration Contract

### Strict Boundary: The Engine is a READ-ONLY Consumer

```python
# ─── The only interface the AI Interview Engine sees ───

class EngineReadOnlyConfig:
    """Constructed from EvaluationConfigSnapshot + RubricSnapshot at session start."""
    
    skills: dict[str, SkillDefinition]      # Fully resolved skill definitions
    rubric: dict[str, RubricCriterion]       # Fully resolved rubric criteria with levels
    scoring_rules: ScoringRules              # Weights and formula
    interview_config: InterviewConfig        # Language, instructions, limits
    passing_score: float
    
    # Hash for audit verification
    snapshot_hash: str

class SkillDefinition:
    name: str
    description: str
    keywords: list[str]
    is_required: bool
    # NO scoring data, NO weights, NO levels

class RubricCriterion:
    skill_name: str
    weight: float
    max_score: float
    levels: list[RubricLevel]

class RubricLevel:
    name: str
    score_min: float
    score_max: float
    description: str
    behavioral_indicators: list[str]
    technical_indicators: list[str]
    evidence_requirements: list[str]

class ScoringRules:
    weights: dict[str, float]   # cv, rubric, human, coverage
    coverage_bonus_max: float
```

### Engine Operations

| Operation | Reads From | Writes To | Purpose |
|-----------|-----------|-----------|---------|
| `generate_question()` | `EngineReadOnlyConfig.skills` | `InterviewTurn` | Create next question based on uncovered skills |
| `evaluate_answer()` | `EngineReadOnlyConfig.rubric` | `RubricScoringDetail`, `ExtractedSkill` | Score answer against rubric levels |
| `compute_final_score()` | `EngineReadOnlyConfig.scoring_rules` | `EvaluationResult` | Aggregate results into final score |
| `generate_report()` | `EngineReadOnlyConfig.passing_score` | `EvaluationResult.verdict` | Determine pass/fail |

### What the Engine NEVER Accesses

```
┌─────────────────────────────────────────────────────────────────────┐
│                    OFF-LIMITS TO ENGINE                              │
│                                                                     │
│  X  campaign_evaluation_configs     (never reads live config)       │
│  X  skill_tree_templates            (never reads live templates)    │
│  X  rubrics                         (never reads live rubrics)      │
│  X  skills                          (never reads live skills)       │
│  X  batch_jobs                      (never reads campaign data)     │
│  X  Users / Recruiters              (never reads user data)         │
│  X  Any mutable configuration       (never reads live data)         │
│                                                                     │
│  The engine receives ONE snapshot. That is ALL it knows.            │
└─────────────────────────────────────────────────────────────────────┘
```

### Session Initialization Flow

```python
def start_interview_session(application_id: int, db: Session) -> EvaluationSession:
    # 1. Get candidate's assigned snapshot
    ces = (
        db.query(CandidateEvaluationSnapshot)
        .filter(
            CandidateEvaluationSnapshot.application_id == application_id,
            CandidateEvaluationSnapshot.superseded_at.is_(None),
        )
        .first()
    )
    assert ces is not None, "Candidate not assigned to any evaluation config"
    
    # 2. Load the immutable config snapshot
    ecs = ces.evaluation_config_snapshot
    
    # 3. Verify snapshot integrity
    actual_hash = compute_snapshot_hash(
        ecs.resolved_skills_json,
        ecs.resolved_rubric_json,
        ecs.scoring_rules_json,
        ecs.interview_config_json,
        ecs.passing_score,
        ecs.published_at,
        ecs.source_config_version,
    )
    assert actual_hash == ecs.snapshot_hash, "Snapshot integrity check failed"
    
    # 4. Create evaluation session linked to the snapshot
    session = EvaluationSession(
        application_id=application_id,
        candidate_evaluation_snapshot_id=ces.id,
        evaluation_config_snapshot_id=ecs.id,
        rubric_snapshot_id=ecs.rubric_snapshot_id,
        status='created',
        interview_state='not_started',
    )
    db.add(session)
    db.commit()
    
    # 5. Build engine config (read-only, cached for session duration)
    engine_config = EngineReadOnlyConfig(
        skills=ecs.resolved_skills_json,
        rubric=ecs.resolved_rubric_json,
        scoring_rules=ecs.scoring_rules_json,
        interview_config=ecs.interview_config_json,
        passing_score=ecs.passing_score,
        snapshot_hash=ecs.snapshot_hash,
    )
    
    return session, engine_config
```

---

## F) Complete Data Flow: Campaign Creation to Final AI Report

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. ADMIN CREATES SKILL TREE TEMPLATE                                    │
│                                                                         │
│    Action: POST /api/v1/admin/skill-tree-templates                      │
│    Tables written: skill_tree_templates, skills,                        │
│                    skill_categories, skill_tree_skills                  │
│    Status: 'draft'                                                      │
│                                                                         │
│    Admin publishes → status='published'                                 │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 2. ADMIN/RECRUITER CREATES RUBRIC                                      │
│                                                                         │
│    Action: POST /api/v1/rubrics                                        │
│    Tables written: rubrics, rubric_criteria, rubric_levels              │
│    Links to: skill_tree_template (optional)                             │
│              skills (via rubric_criteria.skill_id)                     │
│    Status: 'draft'                                                      │
│                                                                         │
│    Publisher → status='published'                                      │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 3. RECRUITER CREATES CAMPAIGN                                          │
│                                                                         │
│    Action: POST /api/v1/recruiter/campaigns                            │
│    Tables written: batch_jobs (status='active')                         │
│                    campaign_evaluation_configs (status='draft')         │
│                                                                         │
│    Config includes: selected skill_tree_template + rubric references    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 4. RECRUITER CONFIGURES EVALUATION                                     │
│                                                                         │
│    Action: PUT /api/v1/recruiter/campaigns/{id}/evaluation-config      │
│    Updates: campaign_evaluation_configs (draft)                         │
│                                                                         │
│    Recruiter can:                                                       │
│    ├─ Select skill tree template                                        │
│    ├─ Override skill weights                                            │
│    ├─ Select rubric (or create campaign-specific rubric)                │
│    ├─ Set scoring rules and passing score                               │
│    └─ Configure interview (language, instructions, limits)              │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 5. PUBLISH CAMPAIGN CONFIGURATION                                       │
│                                                                         │
│    Action: POST /api/v1/recruiter/campaigns/{id}/publish               │
│                                                                         │
│    System:                                                              │
│    ├─ Resolve skills (template + overrides)                             │
│    ├─ Resolve rubric (criteria + weight overrides)                      │
│    ├─ Create RubricSnapshot (freeze rubric state)                       │
│    ├─ Create EvaluationConfigSnapshot (immutable, hashed)               │
│    ├─ Set batch_jobs.evaluation_config_id → config                      │
│    ├─ Set config.status = 'published'                                   │
│    └─ Return snapshot hash for audit trail                              │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 6. RECRUITER UPLOADS CANDIDATES                                        │
│                                                                         │
│    Action: POST /api/v1/recruiter/campaigns/{id}/upload-cvs            │
│                                                                         │
│    System:                                                              │
│    ├─ Create Application for each candidate                             │
│    ├─ Extract CV, analyze, compute initial cv_score                    │
│    ├─ Assign candidate_evaluation_snapshot (pointing to active config)  │
│    └─ ScoringService.compute_final_score (cv only, rest pending)       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 7. RECRUITER INVITES CANDIDATE                                         │
│                                                                         │
│    Action: POST /api/v1/recruiter/campaigns/{id}/candidates/{app}/invite│
│                                                                         │
│    System:                                                              │
│    ├─ Generate interview token                                          │
│    ├─ Create candidate user account                                     │
│    └─ Send invitation email with link                                   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 8. CANDIDATE COMPLETES AI INTERVIEW                                    │
│                                                                         │
│    Candidate clicks link → starts interview                             │
│                                                                         │
│    System:                                                              │
│    ├─ Create EvaluationSession (linked to candidate_eval_snapshot)      │
│    ├─ Load EngineReadOnlyConfig from snapshot                           │
│    ├─ Per turn:                                                         │
│    │   ├─ generate_skill_driven_turn() → InterviewTurn                 │
│    │   ├─ Candidate answers                                             │
│    │   ├─ evaluate_answer() → RubricScoringDetail + ExtractedSkill     │
│    │   └─ Update engine state                                           │
│    ├─ Final evaluation:                                                 │
│    │   ├─ aggregate_scores() → InterviewScoringSummary                 │
│    │   └─ ScoringService.compute_final_score() → EvaluationResult      │
│    └─ Generate candidate report                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 9. RECRUITER VIEWS RESULTS                                             │
│                                                                         │
│    Action: GET /api/v1/recruiter/campaigns/{id}/candidates             │
│                                                                         │
│    Reads: EvaluationResult.final_score, cv_score                        │
│           EvaluationSession.interview_state, interview_progress         │
│           RubricScoringDetail[] (per-criterion breakdown)               │
│                                                                         │
│    Every score is traceable to:                                         │
│    ├─ EvaluationResult → EvaluationSession                              │
│    ├─ → CandidateEvaluationSnapshot (which config version)              │
│    ├─ → EvaluationConfigSnapshot (immutable config)                     │
│    └─ → RubricSnapshot (frozen rubric at evaluation time)               │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## G) Migration Plan

### Phase 1: Schema Creation (Zero Downtime)

**Step 1.1** — Create new tables alongside existing ones.

```sql
-- Run in a single migration
CREATE TABLE skills (...);
CREATE TABLE skill_tree_templates (...);
CREATE TABLE skill_categories (...);
CREATE TABLE skill_tree_skills (...);
CREATE TABLE rubrics (...);           -- new rubrics table (separate from old)
CREATE TABLE rubric_criteria (...);
CREATE TABLE rubric_levels (...);
CREATE TABLE campaign_evaluation_configs (...);
CREATE TABLE evaluation_config_snapshots (...);
CREATE TABLE candidate_evaluation_snapshots (...);
```

**Step 1.2** — Add new FK columns to existing tables (all nullable).

```sql
ALTER TABLE batch_jobs ADD COLUMN evaluation_config_id INTEGER REFERENCES campaign_evaluation_configs(id);
ALTER TABLE evaluation_sessions ADD COLUMN candidate_evaluation_snapshot_id INTEGER REFERENCES candidate_evaluation_snapshots(id);
ALTER TABLE evaluation_sessions ADD COLUMN evaluation_config_snapshot_id INTEGER REFERENCES evaluation_config_snapshots(id);
```

**Rollback:** Trivially revert by dropping the new columns and tables. No production impact at this stage.

### Phase 2: Seed New Tables from Legacy Data

**Step 2.1** — Extract skills from existing `rubrics.criteria_json` into `skills` table.

```python
# One-shot script: parse all existing rubrics
for rubric in db.query(Rubric).all():
    if not rubric.criteria_json:
        continue
    job_rubric = JobRubric(**json.loads(rubric.criteria_json))
    for category in job_rubric.categories:
        for subcat in category.subcategories:
            for skill in subcat.skills:
                # Upsert into skills table
                upsert_skill(skill.name, skill.description, skill.keywords)
```

**Step 2.2** — Create skill tree templates from existing rubrics.

```python
# Each unique rubric becomes a skill_tree_template
# Each rubric's criteria_json categories → skill_categories + skill_tree_skills
```

**Step 2.3** — Extract rubric criteria and levels into new normalized tables.

```python
# Each rubric's criteria_json → rubric_criteria + rubric_levels
```

**Step 2.4** — Create campaign_evaluation_configs for active campaigns.

```python
# For each active BatchJob with associated Job.rubric_id:
#   Create a CampaignEvaluationConfig linking to the extracted rubric
#   Publish it → creates snapshot
```

**Step 2.5** — Create candidate_evaluation_snapshots for existing EvaluationSessions.

```python
# For each EvaluationSession with rubric_snapshot_id:
#   Find/create the EvaluationConfigSnapshot for that rubric version
#   Create CandidateEvaluationSnapshot pointing to it
#   Link evaluation_sessions.candidate_evaluation_snapshot_id
```

### Phase 3: Dual-Write (Transition Period)

During this phase, BOTH the old `rubrics.criteria_json` and the new normalized tables are written on every save.

```python
def save_rubric(rubric_data, db):
    # Old path (legacy)
    old_rubric = db.query(Rubric).get(rubric_data.id)
    old_rubric.criteria_json = json.dumps(rubric_data.to_legacy_format())
    
    # New path (normalized)
    save_rubric_criteria(rubric_data, db)
    save_rubric_levels(rubric_data, db)
    
    db.commit()
```

### Phase 4: Migrate Readers

All consumers switch from reading `Rubric.criteria_json` to reading the normalized tables + `EvaluationConfigSnapshot`.

```python
# Old code (before)
rubric = load_rubric(job_id)
skills = rubric.build_lookup()

# New code (after)
snapshot = session.evaluation_config_snapshot
skills = snapshot.resolved_skills_json
rubric = snapshot.resolved_rubric_json
```

### Phase 5: Remove Legacy Columns

Once all readers are migrated:

```sql
ALTER TABLE rubrics DROP COLUMN criteria_json;
ALTER TABLE rubrics DROP COLUMN skill_weights;
ALTER TABLE rubrics DROP COLUMN complexity;
-- Or keep for historical reference, add DEPRECATED marker
```

### Migration Safety

| Check | Mechanism |
|-------|-----------|
| No data loss | New tables are additive; old columns are preserved until Phase 5 |
| No downtime | All new FKs are nullable; old code paths remain active |
| Rollback ability | Reverse migration: stop writing new tables, fall back to old code |
| Audit continuity | Existing `RubricSnapshot` rows remain valid; new ones use same `rubric_snapshots` table |

---

## H) Potential Future Problems

### 1. Snapshot Storage Growth

**Problem:** Each publish creates a full copy of resolved skills and rubric. With thousands of campaigns publishing frequently, the `evaluation_config_snapshots` table can grow to millions of rows with large JSON blobs.

**Mitigation:**
- Implement snapshot retention policy: keep all published snapshots, but allow archiving of snapshots older than N months to cold storage (S3/GCS)
- Deduplicate by snapshot_hash: if two publish events produce identical content, they share the same hash (but each needs its own row for audit)
- Use compression on JSON columns at the storage engine level (InnoDB with `ROW_FORMAT=COMPRESSED`)

**Scale estimate:** 
- 10,000 campaigns × 20 publishes each × 50 KB per snapshot = 10 GB
- At scale (1M campaigns), this becomes ~1 TB — manageable with compression and partitioning

### 2. Candidate Re-Evaluation Performance

**Problem:** Re-evaluating 10,000 candidates with a new config requires creating 10,000 new `candidate_evaluation_snapshots` + `evaluation_sessions` + re-running the AI interview scoring. This can take hours.

**Mitigation:**
- Batch API: `POST /campaigns/{id}/re-evaluate` accepts optional list of candidate IDs
- Asynchronous processing with progress tracking (add `worker_status` to campaign or a new `re_evaluation_jobs` table)
- Background worker pool processes candidates in parallel
- Results are additive: old EvaluationSessions are preserved, new ones are created alongside

### 3. Config Drift — Template Evolution

**Problem:** Admin updates a Skill Tree Template after 100 campaigns have already selected and published it. Which campaigns get the update?

**Design decision:** **No auto-update.** Campaigns use snapshots, not live references. The admin update creates a new template version. Recruiters see a notification: "New template version available" and can choose to upgrade their campaign config.

**Implementation:**
- `skill_tree_templates` has `version` column
- `campaign_evaluation_configs` records `skill_tree_template_id` + version at time of selection
- Admin publishes new version → old report shows version drift
- Recruiter can "upgrade" which creates a new draft config with the new template version applied

### 4. Cross-Campaign Rubric Sharing

**Problem:** A recruiter creates a Rubric and uses it across 50 campaigns. They update the rubric. Which campaigns get affected?

**Design decision:** Only unpublished (draft) configs that reference the rubric by ID will see the updated version on next edit. Published configs are frozen in their snapshot.

**Exception:** If a recruiter explicitly re-syncs a campaign config with the latest rubric version, the system creates a new draft config and requires re-publish.

### 5. Snapshot Integrity Verification

**Problem:** Over years of operation, how do we prove that snapshots haven't been tampered with?

**Solution:** The `snapshot_hash` is a SHA-256 of the snapshot content. Additionally:

```sql
-- Create a separate audit table for snapshot hashes
CREATE TABLE snapshot_integrity_log (
    id              INTEGER PRIMARY KEY AUTO_INCREMENT,
    snapshot_id     INTEGER NOT NULL REFERENCES evaluation_config_snapshots(id),
    snapshot_hash   VARCHAR(64) NOT NULL,
    verified_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    verified_by     VARCHAR(100) NOT NULL,  -- system process name
    match           BOOLEAN NOT NULL,
    
    INDEX idx_sil_snapshot (snapshot_id),
    INDEX idx_sil_verified (verified_at)
);
```

A cron job re-verifies all snapshots periodically (e.g., weekly) and logs results.

### 6. Race Condition: Publish During Active Interview

**Problem:** A recruiter publishes a new config version while a candidate is mid-interview.

**Mitigation:**
- `candidate_evaluation_snapshot` is assigned **before** the interview starts, during candidate upload (Phase 6 in the data flow)
- The `EvaluationSession` locks the snapshot at creation time via `evaluation_config_snapshot_id`
- Publishing creates a new snapshot but does NOT affect existing sessions
- No race condition — the session's snapshot reference is immutable after session creation

### 7. Soft-Delete Cascade

**Problem:** If a Skill Tree Template is soft-deleted, should its campaigns break?

**Design decision:** No. Campaigns reference templates by ID but use snapshots for evaluation. The template ID is metadata for the recruiter's reference. Soft-delete is allowed; the snapshots remain valid. The campaign config editor shows a warning: "Original template has been archived."

### 8. Query Performance at Scale

**Problem:** `rubric_scoring_details` grows to billions of rows (one per criterion per turn per interview).

**Mitigation:**
- Partition `rubric_scoring_details` by `evaluation_result_id` (or by date range)
- Add covering index: `(evaluation_result_id, criterion_name)`
- Consider time-based partitioning: `evaluation_results.computed_at` → monthly partitions
- Archive completed results older than 2 years to a data warehouse (BigQuery/Redshift) for analytics

### 9. Scoring Weight Inconsistency

**Current issue:** `scoring_weights.py` stores weights in `User.email_settings` but `ScoringService.compute_final_score` uses hardcoded constants (`0.25, 0.40, 0.25, 0.10`). These two sources of truth are inconsistent.

**Fix in new architecture:**
- Scoring weights are stored ON the `CampaignEvaluationConfig.scoring_rules` (the SSOT)
- The snapshot freezes them at publish time
- `ScoringService.compute_final_score` reads from the snapshot, not from hardcoded constants
- The per-recruiter weights in `User.email_settings` become a "default" seed for new campaign configs, not the runtime source

```python
# New canonical scoring
def compute_final_score(snapshot: EvaluationConfigSnapshot, scores: dict) -> float:
    rules = snapshot.scoring_rules_json
    weights = rules['weights']
    return (
        scores['cv'] * weights['cv_score'] +
        scores['rubric'] * weights['rubric_score'] +
        scores['human'] * weights['human_score'] +
        coverage_bonus(scores['coverage_pct'], weights['coverage_bonus'])
    )
```

---

## Appendix: Change Summary from Current Architecture

| Aspect | Current Architecture | Refactored Architecture |
|--------|--------------------|------------------------|
| **SSOT** | `Rubric.criteria_json` (blob) | `CampaignEvaluationConfig` (relational + JSON) |
| **Skill Tree** | Embedded in `criteria_json` | Normalized: `skills`, `skill_categories`, `skill_tree_skills` |
| **Rubric** | `criteria_json` with everything merged | Normalized: `rubric_criteria` + `rubric_levels` |
| **Weights** | Mixed: skill weights in `criteria_json`, scoring weights in `User.email_settings` | All weights in `campaign_evaluation_configs.scoring_rules` + `rubric_criteria.weight` |
| **Versioning** | `Rubric.version` per job | `CampaignEvaluationConfig.version` per campaign, with snapshot chain |
| **Snapshots** | `RubricSnapshot` (rubric only) | `EvaluationConfigSnapshot` (full config: skills + rubric + rules + instructions) |
| **Candidate isolation** | Implicit via `EvaluationSession` | Explicit via `CandidateEvaluationSnapshot` |
| **Integrity** | None (no hash) | SHA-256 hash on every snapshot |
| **AI Engine input** | `JobRubric` Pydantic (from live DB or cached) | `EngineReadOnlyConfig` (from immutable snapshot only) |
| **Scoring weights** | Hardcoded constants in `ScoringService` | Frozen in snapshot, read by engine |
