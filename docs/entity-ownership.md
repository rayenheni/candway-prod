# Entity Ownership — Candway Domain Model

## 1. User (Identity & Authentication ONLY)

**File:** `backend/models/foundation/user.py`

**Owns:**
- `id` — primary identifier
- `email` — login credential
- `hashed_password` — authentication secret
- `temp_password` — one-time invite passwords
- `role` — `candidate`, `recruiter`, `mentor`, `admin`
- `email_verified` — identity confirmation
- `is_locked`, `lockout_until` — account security
- `marketing_consent`, `data_processing_consent` — GDPR
- `deleted_at` — soft delete
- `created_at` — account creation

**Does NOT own:**
- Personal profile data (name, phone, bio, skills, etc.) → profile tables
- Company/SMTP settings → RecruiterProfile
- Usage quotas → profile tables
- Subscription/payment details → SubscriptionPlan, Transaction (future: split)

**Relationships:**
- `candidate_profile` → CandidateProfile (1:1)
- `recruiter_profile` → RecruiterProfile (1:1)
- `admin_profile` → AdminProfile (1:1)
- `applications` → Application (1:N)

---

## 2. CandidateProfile (Candidate Personal & Professional Data)

**File:** `backend/models/evaluation/profile.py`

**Owns:**
- `user_id` → User (1:1)
- `name`, `phone`, `email` — contact info
- `headline` — professional tagline
- `bio` — professional summary
- `skills` — self-declared skills (Text/JSON)
- `languages`, `availability`, `work_preference`
- `salary_expectation_min`, `salary_expectation_max`
- `linkedin_url`, `github_url`, `portfolio_url`, `avatar_url`
- `profile_views`, `profile_views_growth` — engagement stats
- Usage tracking: `candidate_cv_uploads_this_month`, `candidate_ai_analyses_this_month`, `candidate_pdf_downloads_this_month`, `candidate_usage_reset_date`

**Does NOT own:**
- Authentication credentials → User
- CV analysis data → CvDocument (per-application)
- Skills extracted by AI → ExtractedSkill, SkillProfile
- Interview results → EvaluationSession, EvaluationResult

---

## 3. RecruiterProfile (Recruiter Company & Settings)

**File:** `backend/models/evaluation/profile.py`

**Owns:**
- `user_id` → User (1:1)
- `company_name`, `company_description`, `company_logo_url` — company branding
- `smtp_host`, `smtp_port`, `smtp_user`, `smtp_password` — email sending
- `usage_jobs`, `usage_cvs`, `usage_ai_interviews`, `usage_reset_date` — quota tracking
- `email_settings` — JSON: auto-email config, templates
- `linkedin_settings` — JSON: LinkedIn integration config

**Does NOT own:**
- Company tenant record → Company
- Jobs posted → Job (owned by User, scoped to Company)
- Candidates or applications → Application

---

## 4. AdminProfile (Admin Permissions)

**File:** `backend/models/evaluation/profile.py`

**Owns:**
- `user_id` → User (1:1)
- `permissions` — Text: CSV of permission flags
- `is_super_admin` — Boolean override

---

## 5. Application (Hiring Transaction)

**File:** `backend/models/ats/application.py`

**Owns:**
- `user_id` → candidate User
- `company_id`, `job_id`, `batch_id` — context
- `full_name`, `email`, `phone` — snapshot of candidate at time of application
- `status` — pipeline state machine (`pending`, `screening`, `interviewing`, `offer`, `rejected`, `hired`, etc.)
- `source` — how they applied (LinkedIn, Referral, Direct, etc.)
- `recruiter_notes` — human feedback
- `assigned_to`, `assigned_at` — recruiter assignment
- `declined_at`, `decline_reason`, `decline_initiated_by` — structured declines
- `invited_at`, `opened_at`, `clicked_at` — campaign tracking
- `language` — interview language override
- `application_stage_history` → ApplicationStageHistory (stage transitions)
- `interactions` → CandidateInteraction (communication log)
- `interviews_list` → Interview (scheduled human interviews)
- `offers` → Offer
- `background_checks` → BackgroundCheck
- `comments_list`, `ratings_list`, `activity_logs_list` — collaboration
- `scorecard_submissions` → ScorecardSubmission (human scorecards)
- `eeo_consent` → EEOConsent

**Does NOT own:**
- AI interview state → EvaluationSession
- AI scores → EvaluationResult
- CV analysis → CvDocument
- Candidate profile data → CandidateProfile
- Learning journey → Enrollment, CareerRoadmap

**Application = the hiring transaction.** It tracks the candidate's journey through the pipeline, recruiter interactions, and human decisions. AI evaluation results are linked via EvaluationSession but owned by EvaluationResult.

---

## 6. EvaluationSession (AI Interview Lifecycle)

**File:** `backend/models/evaluation/evaluation.py`

**Owns:**
- `application_id` → Application (N:1 — multiple re-evaluations possible)
- `company_id`, `candidate_id`, `context_type`, `context_id`
- `status` — session state machine (`created`, `in_progress`, `paused`, `completed`, `expired`, `failed`, `flagged`)
- `interview_state` — interview state (`not_started`, `in_progress`, `completed`, `expired`, `flagged`, `paused`)
- `interview_progress` — question count
- `interview_time_left` — timer
- `interview_last_saved` — resume timestamp
- `interview_log` — full conversation transcript (JSON)
- `interview_questions` — generated questions (JSON)
- `generated_questions` — raw generated question set
- `proctoring_violations` — integrity events (JSON)
- `video_file_path`, `video_transcript`, `video_analysis_json`
- `interview_reset_count`, `interview_last_reset_at`, `interview_turn_seq`
- `calibration_json`, `calibration_score`, `calibration_verified_skills`
- `rubric_id`, `rubric_version` — rubric pinning
- `interview_turns` → InterviewTurn (individual Q&A)
- `cv_document` → CvDocument (link to CV used)
- `evaluation_result` → EvaluationResult (1:1 — the score)

**Does NOT own:**
- The hiring decision → Verdict (manual), EvaluationResult.verdict (AI)
- The application pipeline status → Application.status
- Candidate personal data → CandidateProfile

**EvaluationSession = one AI evaluation attempt.** It contains everything about the AI interview: questions asked, answers given, proctoring events, timing, calibration, and the resulting score.

---

## 7. EvaluationResult (Canonical Score Record)

**File:** `backend/models/evaluation/evaluation.py`

**Owns:**
- `evaluation_session_id` → EvaluationSession (1:1)
- `rubric_id`, `rubric_version` — which rubric produced this score
- `cv_score`, `rubric_score`, `human_integrity_score` — component scores
- `rubric_coverage_pct` — how many skills were assessed
- `scoring_status` — `PENDING`, `SCORED`, `FAILED`, `NEEDS_REVIEW`
- `final_score` — THE canonical score (0-100)
- `confidence_lower`, `confidence_upper` — reliability interval
- `verdict` — AI recommendation (pass/fail/strong_hire/etc.)
- `score_breakdown` — JSON detail (legacy — being deprecated)
- `fraud_score`, `fraud_reported_by`, `fraud_reported_at`
- `needs_review`, `needs_review_reason` — human review flags
- `scoring_model`, `computed_by`, `computed_at`
- `rubric_scoring_details` → RubricScoringDetail (per-criterion scores)

**Does NOT own:**
- The final hire decision → Verdict (human override)
- The interview transcript → EvaluationSession.interview_log
- CV text → CvDocument

**EvaluationResult = THE single source of truth for scoring.** Every score in the system must trace back to exactly one EvaluationResult row. No other table holds a canonical score.

---

## 8. CvDocument (CV Analysis Output)

**File:** `backend/models/ats/application.py`

**Owns:**
- `application_id` → Application (1:1)
- `evaluation_session_id` → EvaluationSession (nullable, 1:1)
- `cv_text`, `cv_file_path`, `cv_text_anonymized`
- `extracted_skills` — JSON list of skills from CV
- `cv_embedding` — vector embedding
- `analysis_json` — full AI analysis result
- `cv_review_json` — CV improvement suggestions
- `roadmap_json` — career roadmap from CV
- `detected_role`, `declared_role`

**One CvDocument per Application.** Stores everything derived from the candidate's CV/resume.

---

## 9. Verdict (Human Business Decision)

**File:** `backend/models/evaluation/verdict.py`

**Owns:**
- `application_id` → Application
- `decision` — `pass`, `fail`, `strong_hire`, etc.
- `reason` — human justification
- `decided_by` — who decided
- `source` — `ai`, `recruiter`, `admin`, `system`
- `evaluation_session_id` → EvaluationSession (which eval informed this)
- `superseded_at`, `superseded_by` — appeal/override chain
- `adverse_action_sent` — compliance

**Verdict = the human-overridable business decision.** The AI verdict lives in EvaluationResult.verdict. The human decision lives in Verdict.decision. This separation allows audit trails for overrides.

---

## 10. InterviewTurn (Individual Q&A)

**File:** `backend/models/evaluation/ai.py`

**Owns:**
- `evaluation_session_id` → EvaluationSession
- `turn_number` — 1-based position
- `question` — encrypted question text
- `answer` — encrypted candidate answer
- `score` — per-question AI score (0-100)
- `feedback` — AI feedback text
- `reasoning` — AI reasoning for the score
- `quality` — `high`, `medium`, `low`
- `type` — `technical`, `behavioral`, `scenario`
- `difficulty` — `junior`, `mid`, `senior`
- `response_time_seconds`
- `status` — `answered`, `pending`, `skipped`

**One row per question-answer pair.** Replaces the legacy `Application.interview_qa_structured` JSON bag. High cardinality — always queried via `evaluation_session_id`.

---

## 11. SkillProfile (Aggregated Skill Intelligence)

**File:** `backend/models/evaluation/skill_profile.py` (NEW)

**Owns:**
- `user_id` → User (candidate)
- `skill_name` → normalized skill name
- `skill_id` → SkillDefinition UUID
- `proficiency` — 0-100 aggregated score
- `confidence` — how reliable this assessment is (0-100)
- `sources` — JSON: array of source objects:
  ```json
  [
    {"source": "cv_analysis", "application_id": 42, "score": 85, "date": "..."},
    {"source": "interview", "evaluation_session_id": 7, "score": 72, "date": "..."},
    {"source": "assessment", "assessment_invitation_id": 3, "score": 90, "date": "..."},
    {"source": "recruiter_validation", "recruiter_id": 5, "score": 80, "date": "..."}
  ]
  ```
- `last_assessed_at` — most recent assessment date
- `created_at`, `updated_at`

**SkillProfile = the candidate's skill intelligence across all sources.** CV analysis gives a baseline, interviews validate depth, assessments test precision, and recruiters add human judgment. Learning recommendations (courses, roadmaps) are derived from the gaps in this profile vs. job requirements.

**Does NOT own:**
- A single assessment instance → ExtractedSkill, InterviewTurn, AssessmentInvitation
- Course progress → Enrollment, LessonProgress
- Career roadmap → CareerRoadmap

---

## Ownership Summary

| Entity | Owns | Does NOT Own |
|--------|------|-------------|
| **User** | Identity, auth, role, security | Profile data, settings, quotas |
| **CandidateProfile** | Personal info, skills, preferences, usage | Auth, CV analysis, interview results |
| **RecruiterProfile** | Company, SMTP, quotas, integrations | Jobs, candidates |
| **AdminProfile** | Permissions, super-admin flag | — |
| **Application** | Pipeline state, notes, assignment, history | Interview state, scores, CV data |
| **EvaluationSession** | Interview lifecycle, questions, answers, turns | Scores, verdicts, human decisions |
| **EvaluationResult** | Final score, component scores, verdict | Interview transcript, CV text |
| **CvDocument** | CV text, analysis, embeddings | Scores, interview data |
| **Verdict** | Human decision, override chain, compliance | AI scores |
| **InterviewTurn** | Per-question Q&A, per-turn scores | Aggregated scores, final verdict |
| **SkillProfile** | Aggregated skill intelligence, sources | Individual assessments, course progress |
