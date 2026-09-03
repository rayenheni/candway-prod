# Candway — Audit Complet Produit, Technique & Business

**Date :** 6 août 2026 — Réaudité et corrigé (V2)
**Auditeur :** Senior PM / SaaS B2B / HRTech / UX / QA
**Méthodologie :** Analyse exhaustive du code (backend + frontend), extraction directe des routes, modèles, composants, permissions. V2 = vérification croisée de chaque affirmation du rapport V1 contre le code réel.

---

## 1. Executive Summary

### État global

Candway est une plateforme IA de recrutement et Talent Intelligence **techniquement avancée** : ~703 route decorators backend (~577 endpoints uniques), ~119 pages frontend, 90+ modèles de données, 732 tests, et un pipeline AI complet (Groq/Gemini/DeepSeek/Ollama). L'architecture multi-tenant, la sécurité (PII masking, CSRF, rate limiting, tenant isolation) et la monétisation (crédits, subscriptions, feature flags) sont robustes.

Lacunes avant lancement public : onboarding partiel, billing manuel (pas de PSP), virus scanning absent, 3 pages "Coming Soon", i18n incomplète.

### ✅ Corrections V1 → V2 (réaudit)

| Affirmation V1 | Verdict V2 | Preuve |
|---|---|---|
| "Pas de CI/CD" | **FAUX — CI/CD EXISTE** | `.github/workflows/ci.yml` (lint/test/security) + `.github/workflows/ci-cd.yml` (ruff, mypy, bandit, safety, trivy, frontend build, tests coverage 70%, migration check, docker build) |
| "Prometheus mal configuré (8090)" | **FAUX — port correct** | `prometheus.yml:9` → `targets: ["backend:8000"]` = port réel du backend (docker-compose `127.0.0.1:8000:8000`) |
| "`.env` non-gitignoré / secrets dans git" | **FAUX — `.env` est gitignoré** | `.gitignore:29,35` → `.env` ; `git check-ignore .env` → confirmé ; `git ls-files .env` → vide. Le fichier existe localement avec de vrais secrets → **rotation conseillée avant prod** (ne pas exposer), mais pas de fuite dans le repo |
| "107 migrations" | **96 migrations** | `alembic/versions/` (96 fichiers .py) ; head = **m54** (confirmé via alembic script) |
| "66 fichiers / 724 tests" | **57 fichiers / 732 tests** | `backend/tests/` |
| "4 tests auth cassés = bug produit" | **Bug d'environnement de test, pas du produit** | `test_auth.py:60,75,116` utilisent `status.HTTP_422_UNPROCESSABLE_CONTENT`, renommé `HTTP_422_UNPROCESSABLE_ENTITY` dans starlette ≥ 0.28. Env installé : starlette 0.38.6 + fastapi 0.115.0 (requirements pinne 0.115.6 → drift). Le test login passe, erreurs = teardown SQLite (`Cannot operate on a closed database`, bug pré-existant du conftest) |

### Taux de complétion global estimé (V2)

| Niveau | Taux | Interprétation |
|--------|------|----------------|
| **Technical completion** | **74%** | Backend très complet, frontend étendu. Lacunes : virus scan, i18n, quelques pages manquantes, tests env drift |
| **Beta readiness** | **60%** | Utilisable en beta fermée ; CI/CD + monitoring en place ; onboarding/support/polish manquent |
| **SaaS readiness** | **45%** | Pas de billing automatique (PSP), process manuel de paiement |
| **Launch readiness** | **38%** | 2-3 mois de travail : sécurité fichiers, onboarding, billing, juridique |

### Plus gros risques avant lancement

| # | Risque | Impact | Priorité |
|---|--------|--------|----------|
| 1 | **Secrets non rotés** (GROQ_API_KEY, SECRET_KEY, Redis) dans `.env` local | Compromission si le fichier fuite (partage, backup) | 🔴 P0 |
| 2 | **Virus scanning absent** (`file_security.py:398,420` TODO) | Upload de fichiers malveillants possible | 🔴 P0 |
| 3 | **Onboarding candidat incomplet** | Profils incomplets → données de recrutement dégradées | 🟠 P1 |
| 4 | **Pas de billing automatique** | Paiement nécessite validation manuelle par l'admin | 🟠 P1 |
| 5 | **i18n incomplète** | Expérience dégradée pour AR/TN | 🟡 P2 |
| 6 | **3 ComingSoon pages** | Fonctionnalités annoncées mais absentes | 🟡 P2 |

### 5 priorités immédiates

| Priorité | Action | Effort |
|----------|--------|--------|
| **P0** | Rotation de tous les secrets + vérifier que `.env*` jamais commité | 1 jour |
| **P0** | Implémenter virus scanning (ClamAV / cloud API) | 2-3 jours |
| **P1** | Finaliser onboarding candidat (vérification + guard) | 2-3 jours |
| **P1** | Corriger les tests auth (starlette `HTTP_422`) + teardown SQLite | 1-2 jours |
| **P1** | Définir le workflow billing (PSP auto vs manuel documenté) | 2-3 jours |

---

## 2. Product Scope Identifié

Légende statuts : **Complete** / **Mostly complete** / **Partial** / **Started** / **Not found** / **Broken**

| Module | Description | Existe ? | Statut | Evidence |
|--------|-------------|----------|--------|----------|
| Auth & Login | JWT, OTP, guest, OAuth Google, reset | ✅ | Complete | `backend/routers/auth.py` (16-17 endpoints) |
| Multi-tenancy | TenantMixin, 404 on mismatch | ✅ | Complete | `backend/models/base.py`, `backend/authz.py` |
| User roles | 5 rôles + CompanyMember | ✅ | Complete | `backend/dependencies.py`, `frontend/src/types/index.ts` |
| Job management | CRUD, wizard, clone, AI generate | ✅ | Complete | `backend/routers/recruiter_jobs.py` (8 endpoints) |
| CV upload | PDF/PNG/JPG, extraction | ⚠️ | Mostly complete | `backend/routers/candidate/cv.py` — virus scan TODO |
| AI CV analysis | Groq/Gemini, scoring, rubric | ✅ | Complete | `backend/ai/cv_analysis.py` |
| CV builder | Builder + export | ✅ | Complete | `frontend/src/features/cv-builder/pages/cv-builder-page.tsx` |
| Candidate ranking | Scoring AI, comparison | ✅ | Complete | `backend/routers/recruiter_candidates/scoring.py` |
| Skill tree | Rubrics, criteria/levels | ✅ | Complete | `backend/models/evaluation/scoring.py`, `backend/rubric/` |
| Interview engine | Chat adaptatif, proctoring, éval | ✅ | Complete | `backend/routers/ai_interview/` (7 fichiers) |
| Candidate portal | Dashboard, jobs, applications | ✅ | Complete | `frontend/src/features/candidate/` (14 pages) |
| Recruiter dashboard | Stats, pipeline | ✅ | Complete | `frontend/src/features/dashboard/pages/recruiter-dashboard.tsx` |
| Company/Org portal | Membres, billing, KYB | ✅ | Complete | `frontend/src/features/org/` (5 pages) |
| Admin panel | 28 pages admin | ✅ | Complete | `frontend/src/features/admin/`, `backend/routers/admin/` |
| Mentor portal | Wallet, students, reviews | ⚠️ | Partial | `backend/routers/mentor.py` — community/profile = ComingSoon |
| Billing/Subscriptions | Plans, crédits, factures, receipts | ⚠️ | Partial | `backend/routers/org/billing.py` — validation manuelle |
| Credit economy | Wallet, ledger, require_credits | ✅ | Complete | `backend/models/finance/credits.py`, `backend/credit_service.py` |
| Feature flags | Kill switch, audience, rollout | ✅ | Complete | `backend/services/feature_service.py` |
| Reports | Build, save, schedule, export | ✅ | Complete | `backend/routers/recruiter_reports.py` (14 endpoints) |
| Analytics | Recruiter + admin KPIs, forecast | ✅ | Complete | `backend/admin_financial_service.py` |
| Notifications | In-app + email | ✅ | Complete | `backend/notifications.py`, `backend/routers/notifications.py` |
| Email service | SMTP, templates, séquences | ✅ | Complete | `backend/email_service.py` |
| GDPR / Data export | Export, consent, erasure | ✅ | Complete | `backend/routers/gdpr.py`, `consent.py`, `GET /auth/me/export` |
| EEO compliance | Dashboard, coverage | ✅ | Complete | `backend/routers/recruiter_eeo.py` |
| Bias detection | Gender, age, culture | ✅ | Complete | `backend/ai/bias_detection.py` |
| KYB verification | Documents, approve/reject | ✅ | Complete | `backend/routers/admin/kyb.py` |
| Messages | Conversations, unread | ✅ | Complete | `backend/routers/messages.py` |
| Calendar | Google/Outlook, sync, ICS | ✅ | Complete | `backend/routers/calendar.py` |
| Background checks | Checkr, adverse action | ⚠️ | Partial | `backend/routers/recruiter_background_checks.py` — clé API requise |
| Courses/LMS | CRUD, quizzes, progress | ✅ | Complete | `backend/models/core/lms.py`, `backend/routers/courses.py` |
| Achievements | Badges, progress | ✅ | Complete | `backend/routers/achievements.py` |
| Pipeline Kanban | DnD, stages, automation | ✅ | Complete | `frontend/src/features/pipeline/pipeline-board.tsx` |
| Bulk invite | Email/CSV, AI invitations | ✅ | Complete | `backend/routers/recruiter_candidates/invitations.py` |
| Reengagement | Campagnes, matching | ✅ | Complete | `backend/routers/recruiter_reengagement.py` |
| Chatbot leads | Capture, management | ⚠️ | Partial | `backend/routers/chatbot.py` — assignation absente |
| AI Copilot | Chat recrutement | ✅ | Complete | `backend/routers/copilot.py` |
| Ghost report | Rapport anonymisé | ✅ | Complete | `backend/routers/recruiter_candidates/scoring.py` |
| JD Bias | Analyse, rewrite | ✅ | Complete | `backend/routers/jd_bias.py` |
| Public pages | Landing, pricing, blogs | ✅ | Complete | `frontend/src/features/marketing/` (8 pages) |
| Setup wizard | Initial platform setup | ✅ | Complete | `backend/routers/setup.py` |
| Impersonation | Company → recruiter | ✅ | Complete | `backend/routers/org/members.py` |
| **Job fair module** | — | ❌ | **Not found** | Aucune route, aucun modèle |
| **Agency workflow** | — | ❌ | **Not found** | Aucune route, aucun modèle |
| Webhooks | Events, signing, dispatch | ✅ | Complete | `backend/routers/recruiter_enhancements/webhooks.py` |
| A/B testing | Experiments, variants | ✅ | Complete | `backend/models/evaluation/ai.py` |
| AI Sales | Leads, campaigns | ✅ | Complete | `backend/routers/ai_sales.py` |
| LinkedIn | OAuth, import | ⚠️ | Partial | `backend/routers/linkedin.py` — credentials requis |
| Translation | AI translate | ✅ | Complete | `backend/routers/ai_utils.py` |
| File uploads | Validation, MIME | ⚠️ | Partial | `backend/security.py` — virus scan TODO |
| Tracking | HMAC tokens | ✅ | Complete | `backend/routers/tracking.py` |
| Unsubscribe | Email unsubscribe | ✅ | Complete | `backend/routers/unsubscribe.py` |
| Support tickets | CRUD, replies | ✅ | Complete | `backend/routers/admin/tickets.py` |
| Announcements | Système-wide | ✅ | Complete | `backend/routers/admin/marketing.py` |
| CMS | Blogs, opportunities | ✅ | Complete | `backend/routers/admin/cms.py` |
| System health | Health, metrics, Prometheus | ✅ | Complete | `backend/routers/analytics/monitoring.py` |
| Prompt management | CRUD, test prompts | ✅ | Complete | `backend/routers/prompt_management.py` |
| AI monitoring | Logs, coûts, succès | ✅ | Complete | `backend/routers/admin/ai-monitoring` |
| CI/CD | GitHub Actions | ✅ | **Présent** | `.github/workflows/ci.yml` + `ci-cd.yml` |

---

## 3. Rôles Utilisateurs Identifiés

| Rôle | Description | Où trouvé | Permissions | Statut |
|------|-------------|-----------|-------------|--------|
| **Candidate** | Chercheur d'emploi | `auth/signup` (role="candidate") | Upload CV, postuler, analyses, qualifications, messages | ✅ Complet |
| **Recruiter** | Recruteur | Invité par company via `/org/members` | CRUD jobs, candidats, scoring, reports, analytics | ✅ Complet |
| **Mentor** | Mentor de carrière | Système uniquement | Reviews CV, students, wallet, courses | ⚠️ Partiel |
| **Admin** | Admin plateforme | Système uniquement | Tout admin (users, orgs, finance, content) | ✅ Complet |
| **Company** | Propriétaire de tenant | `auth/signup/org` | Membres, billing, analytics, impersonation, KYB | ✅ Complet |
| **Super Admin** | Accès total | `AdminProfile.is_super_admin = True` | Bypass toutes permissions | ✅ Complet |

### Rôles recommandés mais non implémentés

| Rôle | Recommandation | Statut |
|------|----------------|--------|
| HR Manager | Permissions RH limitées | ❌ Non implémenté |
| Hiring Manager | Avis sans gérer le process | ❌ Non implémenté |
| Agency | Agence multi-clients | ❌ Non implémenté |
| Job Fair Organizer | Événements | ❌ Non implémenté |
| Interviewer | Évaluateur externe | ❌ Non implémenté |

### Hiérarchie CompanyMember

| Rôle | Capacités |
|------|-----------|
| **owner** | Tout, impersonation |
| **admin** | Membres, billing, settings |
| **recruiter** | Jobs/candidats/entretiens |
| **member** | Accès basique |

---

## 4. Permissions Matrix

| Fonctionnalité | Super Admin | Admin | Recruiter | Company | Candidate | Mentor |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Gérer utilisateurs plateforme | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Gérer entreprises (tenants) | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Gérer membres de mon entreprise | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| Impersonner un recruteur | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ |
| Créer job | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Modifier job | ✅ | ✅ | ✅ (own) | ✅ | ❌ | ❌ |
| Supprimer job | ✅ | ✅ | ✅ (own) | ✅ | ❌ | ❌ |
| Voir tous les jobs | ✅ | ✅ | ✅ (company) | ✅ | ❌ | ❌ |
| Postuler à un job | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| Uploader CV | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| Analyser CV (AI) | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Voir candidats | ✅ | ✅ | ✅ (company) | ✅ | ❌ | ✅ (mentees) |
| Modifier score candidat | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Gérer pipeline | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Planifier entretien | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| Passer entretien AI | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| Générer rapport | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Télécharger rapport | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Voir analytics | ✅ | ✅ | ✅ (company) | ✅ | ❌ | ❌ |
| Voir finance admin | ✅ | ✅ (manage_finance) | ❌ | ❌ | ❌ | ❌ |
| Gérer billing entreprise | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| Approuver KYB | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Gérer subscriptions | ✅ | ✅ (manage_finance) | ❌ | ❌ | ❌ | ❌ |
| Gérer crédits | ✅ | ✅ (manage_finance) | ❌ | ❌ | ❌ | ❌ |
| Gérer cours | ✅ | ✅ (manage_content) | ❌ | ❌ | ❌ | ❌ |
| Gérer contenu (blogs, etc.) | ✅ | ✅ (manage_content) | ❌ | ❌ | ❌ | ❌ |
| Gérer annonces système | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Voir AI monitoring | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Gérer feature flags | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Gérer prompts AI | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Exporter données GDPR | ✅ | ✅ | ❌ | ❌ | ✅ (own) | ❌ |
| Supprimer données (erasure) | ✅ | ✅ | ❌ | ❌ | ✅ (own) | ❌ |
| Voir support tickets | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Envoyer messages | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Calendrier | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Copilot AI | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Background checks | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| EEO analytics | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Reengagement campaigns | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |

### Permissions admin (CSV dans AdminProfile.permissions)

| Permission | Accès |
|-----------|-------|
| `manage_finance` | Subscriptions, crédits, invoices, payments, finance, plans, KYB |
| `manage_content` | Cours, CMS, blogs, opportunities, jobs, organizations, settings |
| `manage_users` | Users management |
| `manage_marketing` | Marketing leads, coupons, bulk email |
| `all` | Bypass toutes les permissions spécifiques |

### Gates d'autorisation (backend/dependencies.py)

| Gate | Rôles acceptés | Usage |
|------|---------------|-------|
| `require_recruiter` | recruiter, admin | Recrutement |
| `require_candidate` | candidate, admin | Portail candidat |
| `require_mentor` | mentor, admin | Mentorat |
| `require_admin` | admin | Admin panel |
| `require_company_admin` | CompanyMember owner/admin | Portail entreprise |
| `require_org_admin` | company, organization (legacy) | Portail entreprise |
| `require_tier(X)` | hiérarchie free<starter<pro<pro_plus<enterprise | Features payantes |
| `require_credits(R,N)` | Tout user avec crédits | Features à crédit |
| `require_pro_tier` | pro, pro_plus, enterprise | Features pro |

---

## 5. Feature Inventory Détaillé

### 5.1 Auth & Autorisation

| Feature | User story | Statut | % | Evidence | Manques | Priorité |
|---|:---:|:---:|---:|---|---|:---:|
| Login email/password | Se connecter | ✅ | 95% | `auth.py:POST /auth/login` | — | — |
| Inscription candidat | Créer compte candidat | ✅ | 95% | `auth.py:POST /auth/signup` | — | — |
| Inscription entreprise | Inscrire entreprise | ✅ | 90% | `auth.py:POST /auth/signup/org` | — | — |
| Vérification OTP | Vérifier email | ✅ | 95% | `auth.py:POST /auth/verify-otp` | — | — |
| Reset password | Réinitialiser | ✅ | 95% | `auth.py` forgot/reset | — | — |
| OAuth Google | S'inscrire via Google | ✅ | 85% | `auth.py:GET /auth/google/*` | Credentials à configurer | P2 |
| Guest login | Accéder à un entretien invité | ✅ | 95% | `auth.py:POST /auth/guest-login` | — | — |
| JWT + refresh | Rester connecté | ✅ | 95% | `auth.py:POST /auth/refresh` | — | — |
| Logout blacklist | Se déconnecter | ✅ | 90% | `auth.py:POST /auth/logout` | — | — |
| Impersonation | Se faire passer pour un recruteur | ✅ | 90% | `org/members.py:POST /org/members/{id}/impersonate` | — | — |

### 5.2 Gestion des Jobs

| Feature | User story | Statut | % | Evidence | Manques | Priorité |
|---|:---:|:---:|---:|---|---|:---:|
| Créer un job | Créer une offre | ✅ | 95% | `recruiter_jobs.py:POST /recruiter/jobs` | — | — |
| Modifier un job | Modifier | ✅ | 90% | `recruiter_jobs.py:PATCH category` | Workflow complet à vérifier | P2 |
| Supprimer un job | Supprimer | ✅ | 95% | `recruiter_jobs.py:DELETE` | — | — |
| Lister les jobs | Voir mes offres | ✅ | 95% | `recruiter_jobs.py:GET /recruiter/jobs/my` | — | — |
| Cloner un job | Dupliquer | ✅ | 90% | `recruiter_jobs.py:POST clone` | — | — |
| AI Job Generation | Générer par AI | ✅ | 85% | `recruiter_jobs.py:POST generate-job` | — | — |
| Auto-create Job | Création auto | ✅ | 85% | `recruiter_jobs.py:POST auto-create` | — | — |
| Job Wizard | Wizard de création | ✅ | 90% | `recruiter_job_wizard.py` (19 endpoints) | — | — |
| AI Suggestions | Suggestions AI | ✅ | 85% | `recruiter_job_wizard.py` (8 `/ai/suggest-*`) | — | — |
| Pipeline stages | Gérer étapes | ✅ | 90% | `recruiter_jobs.py:GET pipeline-stages` | — | — |
| Job categories | Catégories | ✅ | 95% | `admin/job_categories.py` | — | — |
| Public jobs | Voir offres publiques | ✅ | 90% | `routers/public.py` | — | — |

### 5.3 CV & Analyse AI

| Feature | User story | Statut | % | Evidence | Manques | Priorité |
|---|:---:|:---:|---:|---|---|:---:|
| Upload CV | Uploader mon CV | ✅ | 90% | `candidate/cv.py:POST upload-cv` | **Virus scan manquant** | P0 |
| AI CV Analysis | Analyser mon CV | ✅ | 90% | `candidate/cv.py:POST analyze` | — | — |
| CV Review | Review basique | ✅ | 90% | `candidate/cv.py:GET cv-review` | — | — |
| CV Review enriched | Review enrichi | ✅ | 85% | `candidate/cv.py:GET cv-review/enriched` | — | — |
| CV Builder | Builder mon CV | ✅ | 85% | `frontend/cv-builder/pages/cv-builder-page.tsx` | — | — |
| Qualifications upload | Uploader diplômes | ✅ | 90% | `candidate/qualifications.py` | — | — |
| CV parsing | Extraire texte | ✅ | 85% | `ai/cv_analysis.py:extract_cv_details` | — | — |
| Skill extraction | Extraire skills | ✅ | 85% | `ai/cv_analysis.py:extract_skills_from_cv` | — | — |

### 5.4 Interview Engine

| Feature | User story | Statut | % | Evidence | Manques | Priorité |
|---|:---:|:---:|---:|---|---|:---:|
| Interview chat | Passer un entretien AI | ✅ | 90% | `ai_interview/chat.py:POST /interview/chat` | — | — |
| Practice interview | S'entraîner | ✅ | 85% | `ai_interview/chat.py:POST /interview/practice` | — | — |
| Session management | Gérer sessions | ✅ | 90% | `ai_interview/session.py` (5 endpoints) | — | — |
| Proctoring | Surveiller entretiens | ✅ | 85% | `ai_interview/session.py:POST sync-proctoring` | — | — |
| Final evaluation | Évaluer le candidat | ✅ | 90% | `ai_interview/evaluation.py:POST evaluate-final` | — | — |
| Question generation | Générer questions | ✅ | 90% | `ai_interview/questions.py:POST generate-interview` | — | — |
| Media upload (video) | Uploader vidéo | ⚠️ | 60% | `ai_interview/media.py:POST upload-video` | Transcription background | P2 |
| Voice STT/TTS | Transcrire/synthétiser | ✅ | 80% | `ai_interview/media.py:POST /voice/*` | — | — |
| Fraud report | Signaler fraude | ✅ | 85% | `ai_interview/evaluation.py:POST report-fraud` | — | — |

### 5.5 Candidats & Recrutement

| Feature | User story | Statut | % | Evidence | Manques | Priorité |
|---|:---:|:---:|---:|---|---|:---:|
| Candidate search | Chercher candidats | ✅ | 95% | `recruiter_candidates/search.py:GET /candidates/search` | — | — |
| Candidate ranking | Classer candidats | ✅ | 90% | `frontend/recruiter/pages/candidate-ranking.tsx` | — | — |
| Score comparison | Comparer CV vs interview | ✅ | 90% | `scoring.py:GET score-comparison` | — | — |
| Override score | Modifier score | ✅ | 85% | `applications.py:POST override-score` | — | — |
| Bulk invite | Inviter en masse | ✅ | 90% | `invitations.py:POST bulk-invite` | — | — |
| AI invitation | Générer invitations AI | ✅ | 85% | `invitations.py:POST generate-invitation` | — | — |
| Applications mgmt | Gérer candidatures | ✅ | 95% | `recruiter_candidates/applications.py` (9 endpoints) | — | — |
| Pipeline Kanban | Board pipeline | ✅ | 90% | `frontend/pipeline/pipeline-board.tsx` | — | — |
| Bulk actions | Actions en masse | ✅ | 90% | `applications.py:POST bulk-delete/update` | — | — |
| Notes & tags | Noter candidats | ✅ | 90% | `applications.py:PUT notes` | — | — |
| Ghost report | Rapport anonymisé | ✅ | 85% | `scoring.py:GET ghost-data` | — | — |
| Talent pool | Pools de talents | ✅ | 90% | `search.py:GET /talent-pool` | — | — |

### 5.6 Portail Candidat

| Feature | User story | Statut | % | Evidence | Manques | Priorité |
|---|:---:|:---:|---:|---|---|:---:|
| Dashboard candidat | Voir stats | ✅ | 90% | `frontend/dashboard/pages/candidate-dashboard.tsx` | — | — |
| Job search | Chercher jobs | ✅ | 90% | `candidate/jobs.py` | — | — |
| Apply to job | Postuler | ✅ | 90% | `candidate/job_detail apply` | — | — |
| Applications tracker | Suivre candidatures | ✅ | 90% | `frontend/candidate/pages/applications-tracker.tsx` | — | — |
| Withdraw application | Retirer candidature | ✅ | 90% | `candidate/applications.py:POST withdraw` | — | — |
| Profile management | Gérer profil | ✅ | 85% | `candidate/profile.py` | — | — |
| **Onboarding wizard** | **Onboarding guidé** | ⚠️ | **70%** | `frontend/candidate/pages/onboarding.tsx` | **Guard incomplet** | **P1** |
| Profile visitors | Voir visiteurs | ✅ | 85% | `candidate/profile.py` | — | — |
| Public profile | Profil partageable | ✅ | 85% | `frontend/candidate/pages/public-profile.tsx` | — | — |
| Esign (offers) | Signer électroniquement | ✅ | 85% | `recruiter_enhancements/actions.py` | — | — |

### 5.7 Entreprise (Company/Org)

| Feature | User story | Statut | % | Evidence | Manques | Priorité |
|---|:---:|:---:|---:|---|---|:---:|
| Org dashboard | Voir stats | ✅ | 90% | `frontend/org/pages/org-dashboard.tsx` | — | — |
| Member management | Gérer membres | ✅ | 95% | `org/members.py` (8 endpoints) | — | — |
| Seat enforcement | Limiter seats | ✅ | 90% | `org/members.py:_assert_seat_available` | — | — |
| Org analytics | Analytics | ✅ | 85% | `org/analytics.py` (3 endpoints) | — | — |
| KYB verification | Soumettre documents | ✅ | 90% | `org/billing.py:POST kyb/documents` | — | — |
| Invitation emails | Envoyer invitations | ✅ | 90% | `org/members.py:create_member` | — | — |

### 5.8 Billing & Payments

| Feature | User story | Statut | % | Evidence | Manques | Priorité |
|---|:---:|:---:|---:|---|---|:---:|
| Subscription plans | Voir plans | ✅ | 90% | `candidate/subscriptions.py:GET /candidate/plans` | — | — |
| Credit wallet | Voir solde | ✅ | 95% | `models/finance/credits.py:CreditWallet` | — | — |
| Consume credits | Débiter crédits | ✅ | 95% | `credit_service.py:consume_credits` | — | — |
| Grant credits (admin) | Attribuer crédits | ✅ | 90% | `admin/credits.py:POST grant` | — | — |
| **Company billing** | **Gérer abonnement** | ⚠️ | **65%** | `org/billing.py` (11 endpoints) | **Pas de paiement auto, receipt manuel** | **P1** |
| Invoice generation | Générer factures | ✅ | 90% | `models/finance/finance.py:Invoice` | — | — |
| Payment config | Voir infos bancaires | ✅ | 85% | `recruiter_settings.py:GET payment-config` | — | — |
| Admin subscriptions | Gérer abonnements | ✅ | 90% | `admin/subscriptions.py` (11 endpoints) | — | — |
| Daily renewal cron | Renouveler | ✅ | 90% | `scheduler.py:_subscription_period_cron` | — | — |
| Financial dashboard | KPIs financiers | ✅ | 90% | `admin_financial_service.py`, `admin/finance.py` | — | — |
| CSV/PDF export | Exporter | ✅ | 85% | `admin/finance.py:GET export` | — | — |

### 5.9 Admin Panel

| Feature | User story | Statut | % | Evidence | Manques | Priorité |
|---|:---:|:---:|---:|---|---|:---:|
| User management | Gérer utilisateurs | ✅ | 90% | `admin/users.py` (9 endpoints) | — | — |
| Organization management | Gérer entreprises | ✅ | 90% | `admin/organizations.py` (7 endpoints) | — | — |
| KYB approval | Approuver KYB | ✅ | 90% | `admin/kyb.py` (3 endpoints) | — | — |
| Platform health | Voir santé système | ✅ | 90% | `analytics/monitoring.py:GET /monitoring/health` | — | — |
| AI monitoring | Surveiller AI | ✅ | 85% | `admin/ai-monitoring` | — | — |
| CMS | Gérer contenu | ✅ | 90% | `admin/cms.py` (13 endpoints) | — | — |
| Course management | Gérer cours | ✅ | 85% | `admin/courses.py` (4 endpoints) | — | — |
| Marketing | Gérer marketing | ✅ | 85% | `admin/marketing.py` | — | — |
| Support tickets | Gérer tickets | ✅ | 85% | `admin/tickets.py` (5 endpoints) | — | — |
| Feature flags | Gérer flags | ✅ | 90% | `routers/feature_flags.py` (7 endpoints) | — | — |
| Prompt management | Gérer prompts | ✅ | 85% | `prompt_management.py` (19 endpoints) | — | — |
| System settings | Configurer système | ✅ | 85% | `admin/settings.py`, `routers/setup.py` | — | — |
| A/B testing | Gérer A/B tests | ✅ | 85% | `admin/ab-testing` | — | — |

### 5.10 Rapports & Analytics

| Feature | User story | Statut | % | Evidence | Manques | Priorité |
|---|:---:|:---:|---:|---|---|:---:|
| Recruiter analytics | Analytics | ✅ | 90% | `recruiter_enhancements/analytics.py` (6 endpoints) | — | — |
| Reports builder | Créer rapports | ✅ | 90% | `recruiter_reports.py` (14 endpoints) | — | — |
| Reports schedule | Planifier rapports | ✅ | 85% | `recruiter_reports.py:POST schedule` | — | — |
| Reports export | Exporter | ✅ | 85% | `recruiter_reports.py:POST export` | — | — |
| Bias analytics | Voir biais | ✅ | 85% | `frontend/recruiter/pages/bias-analytics.tsx` | — | — |
| JD Bias analysis | Analyser biais | ✅ | 90% | `jd_bias.py` (4 endpoints) | — | — |
| EEO dashboard | Dashboard EEO | ✅ | 85% | `recruiter_eeo.py` (9 endpoints) | — | — |
| Candidate comparison | Comparer candidats | ✅ | 90% | `frontend/recruiter/pages/compare.tsx` | — | — |
| Scoring preview | Prévisualiser scoring | ✅ | 85% | `recruiter_enhancements/scorecards.py` | — | — |
| Forecast (admin) | Prévisions | ✅ | 85% | `admin_financial_service.py:get_forecast` | — | — |

### 5.11 Intelligence Artificielle

| Feature | User story | Statut | % | Evidence | Manques | Priorité |
|---|:---:|:---:|---:|---|---|:---:|
| LLM cascade | Plusieurs providers | ✅ | 95% | `ai/llm.py` | — | — |
| PII masking | Masquer PII | ✅ | 95% | `ai/security.py:PIIMasker` | — | — |
| Prompt injection | Détecter injections | ✅ | 90% | `ai/security.py:detect_prompt_injection` | — | — |
| Output validation | Valider réponses | ✅ | 90% | `ai/validation.py:AIOutputValidator` | — | — |
| Token budget | Gérer tokens | ✅ | 85% | `ai/token_tracker.py` | — | — |
| Cost controller | Contrôler coûts | ✅ | 85% | `ai/cost_controller.py` | — | — |
| Bias detection | Détecter biais | ✅ | 85% | `ai/bias_detection.py` (90+ pays) | — | — |
| Anti-cheat | Détecter triche | ✅ | 85% | `ai/anti_cheat.py` | — | — |
| Explainable scoring | Expliquer scores | ✅ | 80% | `ai/explainable_scoring.py` | — | — |
| Knowledge graph | Mapper compétences | ⚠️ | 50% | `ai/knowledge_graph.py` | Pas intégré au workflow principal | P2 |
| Career roadmap | Roadmap carrière | ✅ | 85% | `ai/roadmap.py`, `routers/career.py` | — | — |
| AI Copilot | Assistant recrutement | ✅ | 90% | `routers/copilot.py:POST /hiring/chat` | — | — |
| AI Sales | Leads AI | ✅ | 85% | `routers/ai_sales.py` (6 endpoints) | — | — |
| Translation | Traduire | ✅ | 85% | `routers/ai_utils.py:POST /ai/translate` | — | — |
| Background scoring jobs | Jobs de scoring | ✅ | 85% | `ai/scoring_jobs.py` (4 fonctions) | — | — |
| Drift monitoring | Surveiller dérive | ⚠️ | 60% | `ai/drift_monitor.py` | Pas intégré au monitoring admin | P3 |
| Calibration | Calibrer scores | ⚠️ | 55% | `ai/calibration.py` | Infrastructure seulement | P3 |

### 5.12 Notifications & Email

| Feature | User story | Statut | % | Evidence | Manques | Priorité |
|---|:---:|:---:|---:|---|---|:---:|
| In-app notifications | Notifications | ✅ | 90% | `notifications.py:NotificationService` | — | — |
| Email service | Envoyer emails | ✅ | 90% | `email_service.py:EmailService` | — | — |
| Interview reminders | Rappeler entretiens | ✅ | 90% | `notifications.py:send_interview_reminder` | — | — |
| Offer expiration alerts | Alerter offres | ✅ | 85% | `notifications.py:send_offer_expiration_alert` | — | — |
| Bulk email | Envoyer en masse | ✅ | 85% | `email_service.py:send_bulk_emails` | — | — |
| Email sequences | Séquences | ✅ | 80% | `models/ats/campaign.py:EmailSequenceLog` | — | — |
| Email templates | Templates | ✅ | 85% | `models/ats/campaign.py:CampaignTemplate` | — | — |

### 5.13 Sécurité & RGPD

| Feature | User story | Statut | % | Evidence | Manques | Priorité |
|---|:---:|:---:|---:|---|---|:---:|
| CSRF protection | Protéger CSRF | ✅ | 95% | `security.py:CSRFMiddleware` | — | — |
| Rate limiting | Limiter débit | ✅ | 95% | `security.py` + Redis | — | — |
| Input sanitization | Nettoyer inputs | ✅ | 90% | `security.py:sanitize_content` (bleach) | — | — |
| Security headers | Headers | ✅ | 95% | `security.py:SecurityHeadersMiddleware` (CSP, HSTS) | — | — |
| Request ID | Tracer requêtes | ✅ | 90% | `security.py:RequestIDMiddleware` | — | — |
| GDPR export | Exporter données | ✅ | 90% | `auth.py:GET /auth/me/export` | — | — |
| GDPR erasure | Supprimer données | ✅ | 85% | `gdpr_erasure.py` | — | — |
| Consent logging | Logger consentements | ✅ | 90% | `models/foundation/user.py:ConsentLog` | — | — |
| Data masking | Masquer données | ✅ | 90% | `security.py:mask_candidate_data` | — | — |
| **File validation** | **Valider fichiers** | ⚠️ | **70%** | `security.py:validate_file` | **Virus scan = TODO** | **P0** |
| Tenant isolation | Isoler tenants | ✅ | 95% | `authz.py`, `TenantMixin`, 404 on mismatch | — | — |

---

## 6. Taux de Complétion par Module

| Module | % | Justification | Blockers | Prochaine action |
|---|---|---|:---:|---|
| Auth / login | 95% | Flux complets (JWT, OTP, guest, OAuth, refresh, logout) | — | Configurer Google OAuth |
| Admin panel | 90% | 28 pages admin, CRUD complet | ComingSoon permissions | Remplacer ComingSoon |
| Company management | 90% | Multi-tenant, members, seats, KYB, impersonation | — | — |
| User roles | 95% | 5 rôles + CompanyMember, gates complets | — | — |
| Job management | 95% | CRUD, wizard, AI generate, clone, pipeline | — | — |
| Skill tree / Rubrics | 90% | Rubrics, criteria/levels, scoring aggregator | — | — |
| CV upload | 85% | Upload, qualifications, parsing OK | **Virus scan TODO** | Implémenter ClamAV |
| CV parsing | 85% | Extraction texte + skills via AI | — | — |
| AI analysis | 90% | LLM cascade, PII, validation, bias | — | — |
| Candidate ranking | 90% | Scoring, comparison, override, ghost report | — | — |
| Candidate profile | 85% | Profile, visitors, public, onboarding partiel | Onboarding incomplet | Finaliser onboarding |
| Interview engine | 85% | Chat, session, proctoring, evaluation | Video/STT partiel | Finaliser media pipeline |
| Report generation | 90% | Build, save, schedule, export CSV/PDF | — | — |
| Dashboard analytics | 90% | Recruiter + admin, KPIs, forecast | — | — |
| Candidate portal | 88% | Dashboard, jobs, applications, profile | Onboarding | — |
| Recruiter dashboard | 90% | Stats, pipeline, applications, hooks | — | — |
| Agency workflow | 0% | Non implémenté | Tout | Décider si nécessaire |
| Job fair module | 0% | Non implémenté | Tout | Décider si nécessaire |
| Billing/payment | 65% | Wallet, ledger, subscriptions OK. Pas de PSP auto | Pas de paiement automatique | Intégrer PSP ou documenter workflow manuel |
| Notifications | 90% | In-app + email, reminders, sequences | — | — |
| Security/privacy | 88% | CSRF, rate limit, sanitization, tenant isolation | **Virus scan, secrets non rotés** | Rotation + virus scan |
| Data deletion | 85% | GDPR export + erasure | — | — |
| **Deployment readiness** | **60%** | **Dockerfile + compose + CI/CD OK. Secrets non rotés, tests env drift** | **Rotation secrets, corriger tests** | Rotation + fix tests |
| UX/frontend polish | 75% | 119 pages, 4 langues. 3 ComingSoon, i18n incomplète | ComingSoon, i18n | Compléter i18n |
| Tests | 72% | 732 tests mais teardown SQLite buggé + drift starlette | Env drift | Corriger conftest + starlette |
| Mentorat | 60% | Wallet, students, reviews OK. Community/profile = ComingSoon | Pages manquantes | Développer pages |
| LMS / Courses | 85% | CRUD, sections, lessons, quizzes, progress | — | — |
| Messaging | 85% | Conversations, messages, unread | WebSocket à vérifier | Vérifier WS |
| Calendar | 80% | Google/Outlook, sync, ICS | OAuth credentials | Configurer OAuth |
| Background checks | 50% | Modèles + routes OK. Clé Checkr requise | Clé API Checkr | Configurer Checkr |
| AI Copilot | 90% | Chat, candidats matchés, actions | — | — |
| **CI/CD** | **80%** | **GitHub Actions présent (lint, mypy, bandit, safety, trivy, tests, coverage, migration, docker)** | — | Vérifier que les runs passent réellement |

---

## 7. Taux de Complétion Global (V2)

| Niveau | Taux | Interprétation |
|---|:---:|---|
| **Technical completion** | **74%** | Backend très complet (~703 decorators, 90+ modèles), frontend étendu (119 pages), AI pipeline avancé, CI/CD présent. Lacunes : virus scan, i18n, 3 ComingSoon, knowledge graph/drift/calibration sous-utilisés |
| **Beta readiness** | **60%** | Fonctionnel en beta fermée. CI/CD + monitoring en place. Onboarding incomplet, billing manuel, tests env drift |
| **SaaS readiness** | **45%** | Pas prêt self-service payant : pas de PSP intégré, process de paiement manuel, juridique RGPD complet à valider |
| **Launch readiness** | **38%** | Lancement public : sécurité fichiers (virus scan), rotation secrets, onboarding, billing, support SLA, juridique |

### Différences entre les niveaux

| Niveau | Description |
|---|---|
| **Techniquement construite** (74%) | L'architecture existe, les endpoints sont là, les modèles sont complets. Un dev peut démontrer chaque feature |
| **Prête pour beta** (60%) | Un early adopter peut recruter avec de l'accompagnement |
| **Prête pour self-service** (45%) | Un client peut s'inscrire, payer, utiliser et obtenir du support sans intervention interne |
| **Prête pour scale** (38%) | 1000+ clients sans dégradation, monitoring + alerting fiables |

---

## 8. User Journeys

### Admin journey
```
Login → /admin/dashboard → KPIs plateforme
  → /admin/users → CRUD utilisateurs
  → /admin/organizations → Entreprises → /admin/kyb → Approuver KYB
  → /admin/subscriptions → Approuver/rejeter transactions
  → /admin/finance + /admin/payments → KPIs → Export CSV/PDF
  → /admin/content → Blogs, opportunities
  → /admin/courses → Gérer cours
  → /admin/ai-monitoring → Coûts AI, succès, prompts
  → /admin/support → Tickets
  → /admin/settings → Paramètres
```

### Company Owner journey
```
Inscription (/auth/register-company) → Verify OTP → Login
  → /org/dashboard → Stats
  → /org/members → Inviter recruteurs (seat limit)
  → /org/billing → Plan → Upload receipt → Attendre approbation admin
  → /org/analytics → KPIs recruteurs
  → Impersonner un recruteur
  → /org/billing/kyb → Soumettre documents
```

### Recruiter journey
```
Invité par company → Login
  → /dashboard → Stats
  → /jobs/new → Wizard (AI suggestions)
  → /candidates → Candidats → Scoring
  → /pipeline → DnD entre stages
  → /interviews/new → Planifier
  → /copilot → Assistant AI
  → /reports-list → Rapport → Export PDF
  → /candidate-ranking → Classement
  → /ghost-report → Rapport anonymisé
  → /billing → Abonnement
  → /messages → Communiquer
  → /calendar → Google/Outlook
  → /settings → SMTP, email
```

### Candidate journey
```
Inscription → Verify OTP → Login
  → /onboarding → Profil → CV → Skills
  → /candidate/dashboard → Stats
  → /jobs → Chercher → Postuler
  → /applications → Suivre → Retirer
  → /cv-builder → Construire → Analyser (-3 crédits)
  → /cv-review → Review enrichi (-3 crédits)
  → /interviews → Entretien AI → Analyse
  → /qualifications → Diplômes
  → /courses → Apprendre
  → /profile → Profil, visitors
  → /messages → Communiquer
```

### Mentor journey
```
Assigné par admin → Login
  → /mentor → Dashboard (étudiants, earnings, reviews)
  → /mentor/students → Roster
  → /mentor/reviews → Reviewer CV
  → /mentor/wallet → Earnings chart
  → /mentor/courses → Cours
  → /mentor/community → ❌ ComingSoon
  → /mentor/profile → ❌ ComingSoon
```

### Guest journey (candidat invité)
```
Reçoit lien HMAC → Guest login → Entretien AI (/interviews/room/{sessionId})
  → Passe l'entretien → Analyse
  → ❌ Pas d'accès au reste du portail (scope=interview)
```

---

## 9. Recommandations Stratégiques (V2)

### Court terme (0-4 semaines) — Préparer la beta fermée

| # | Action | Priorité |
|---|--------|----------|
| 1 | **Rotation de tous les secrets** + garantir `.env*` jamais commité | 🔴 P0 |
| 2 | Implémenter virus scanning (ClamAV / API cloud) | 🔴 P0 |
| 3 | Corriger les tests auth (starlette `HTTP_422`) + teardown SQLite | 🟠 P1 |
| 4 | Finaliser onboarding candidat (guard + vérification) | 🟠 P1 |
| 5 | Remplacer ou cacher les 3 ComingSoon | 🟠 P1 |
| 6 | Documenter le workflow billing manuel (si pas de PSP) | 🟠 P1 |
| 7 | **Vérifier que les GitHub Actions passent réellement** (branch main) | 🟠 P1 |
| 8 | Aligner fastapi installé (0.115.0) avec le pin (0.115.6) | 🟡 P2 |

### Moyen terme (1-3 mois) — Prêt pour beta payante

| # | Action | Priorité |
|---|--------|----------|
| 1 | Intégrer un PSP (Stripe ou Konnect Tunisie) | 🔴 P0 |
| 2 | Compléter i18n (AR + TN) | 🟠 P1 |
| 3 | Développer les pages mentor manquantes | 🟠 P1 |
| 4 | Finaliser le pipeline media vidéo | 🟠 P1 |
| 5 | Alerting (Slack/Email sur erreurs critiques) | 🟡 P2 |
| 6 | Intégrer Checkr ou désactiver la feature | 🟡 P2 |
| 7 | Performance testing (load test interview engine) | 🟡 P2 |
| 8 | Documentation API publique (Swagger personnalisée) | 🟡 P2 |

### Long terme (3-6 mois) — Scale

| # | Action | Priorité |
|---|--------|----------|
| 1 | Module Job Fair (si validé par le marché) | 🟡 P2 |
| 2 | Workflow Agency (multi-clients) | 🟡 P2 |
| 3 | Knowledge graph intégré au scoring | 🟡 P2 |
| 4 | Drift monitoring actif + alerting | 🟢 P3 |
| 5 | Calibration automatique des scores | 🟢 P3 |
| 6 | Application mobile (React Native / PWA) | 🟢 P3 |
| 7 | Multi-région (EU privacy vs MENA) | 🟢 P3 |
| 8 | Marketplace de talents inter-entreprises | 🟢 P3 |

---

## 10. Métriques Clés du Projet (V2)

| Métrique | Valeur | Source |
|----------|--------|--------|
| Route decorators backend | ~703 | `@router.(get/post/put/patch/delete)` count |
| Fichiers router backend | 134 | `backend/routers/` |
| Modèles de données | ~90 | `backend/models/` |
| Migrations DB | 96 | `alembic/versions/` (head = m54) |
| Tests backend | 732 (57 fichiers) | `backend/tests/` |
| Pages frontend | 119 | `frontend/src/features/` |
| Services frontend | 31 | `frontend/src/services/` |
| Routes frontend | ~115 | `frontend/src/app/router.tsx` |
| Composants UI partagés | 20 | `frontend/src/shared/components/ui/` |
| Hooks personnalisés | 15 | `frontend/src/shared/hooks/` |
| Langues supportées | 4 (EN, FR, AR, TN) | `frontend/src/i18n/dictionaries.ts` |
| Rôles utilisateur | 5 | `frontend/src/types/index.ts` |
| Workflows CI/CD | 2 (ci.yml + ci-cd.yml) | `.github/workflows/` |

---

*Rapport V2 généré le 6 août 2026 — Réaudit basé sur la vérification croisée des affirmations du rapport V1 contre le code réel et l'exécution de tests ciblés.*
