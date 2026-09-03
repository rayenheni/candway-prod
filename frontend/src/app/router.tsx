// ============================================================
// Candway Platform - Router Configuration With Complete Page Mapping
// ============================================================

import { createBrowserRouter, Navigate } from 'react-router';
import { lazy, Suspense } from 'react';

import { AuthLayout } from '@/layouts/auth-layout';
import { DashboardLayout } from '@/layouts/dashboard-layout';
import { ProtectedRoute, RoleGuard, InterviewRoomRoute, InterviewAnalysisRoute } from '@/app/guards/auth-guard';
import { RouteErrorPage } from '@/app/error-boundary';
import type { UserRole } from '@/types';

function PageLoader() {
  return (
    <div className="flex items-center justify-center h-full min-h-[400px]">
      <div className="flex flex-col items-center gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-purple-600 border-t-transparent" />
        <span className="text-sm text-gray-500 dark:text-gray-400 font-medium">Loading Candway Module...</span>
      </div>
    </div>
  );
}

// ---- Landing & Auth ----
const CandwayLanding     = lazy(() => import('@/features/marketing/pages/candway-landing'));
const LoginPage         = lazy(() => import('@/features/auth/pages/login'));
const RegisterPage      = lazy(() => import('@/features/auth/pages/register'));
const RegisterCompanyPage = lazy(() => import('@/features/auth/pages/register-company'));
const ForgotPasswordPage= lazy(() => import('@/features/auth/pages/forgot-password'));
const ResetPasswordPage = lazy(() => import('@/features/auth/pages/reset-password'));
const VerifyEmailPage   = lazy(() => import('@/features/auth/pages/verify-email'));
const VerifyOtpPage     = lazy(() => import('@/features/auth/pages/verify-otp'));
const GoogleCallbackPage= lazy(() => import('@/features/auth/pages/google-callback'));
const InterviewAccessPage = lazy(() => import('@/features/auth/pages/interview-access'));

// ---- Public Marketing ----
const MarketingLayout  = lazy(() => import('@/features/marketing/components/marketing-layout'));
const PricingPage      = lazy(() => import('@/features/marketing/pages/pricing'));
const BlogsPage        = lazy(() => import('@/features/marketing/pages/blogs'));
const BlogDetailPage   = lazy(() => import('@/features/marketing/pages/blog-detail'));
const OpportunitiesPage= lazy(() => import('@/features/marketing/pages/opportunities'));
const PrivacyPage      = lazy(() => import('@/features/marketing/pages/privacy'));
const TermsPage        = lazy(() => import('@/features/marketing/pages/terms'));
const PublicJobsPage   = lazy(() => import('@/features/marketing/pages/public-jobs'));
const PublicJobDetailPage = lazy(() => import('@/features/marketing/pages/public-jobs').then(m => ({ default: m.PublicJobDetailPage })));
const PublicCoursesPage = lazy(() => import('@/features/marketing/pages/public-courses'));

// ---- Role Dashboards ----
const RoleBasedDashboard = lazy(() => import('@/features/dashboard/pages/role-based-dashboard'));

// ---- Recruitment Suite ----
const JobWizardPage       = lazy(() => import('@/features/recruiter/pages/job-wizard'));
const PipelineBoardPage   = lazy(() => import('@/features/pipeline/pages/pipeline-board'));
const CandidatesListPage  = lazy(() => import('@/features/candidates/pages/candidates-list'));
const ApplicationDetailPage = lazy(() => import('@/features/candidates/pages/application-detail'));
const ApplicationsPage = lazy(() => import('@/features/recruiter/pages/applications-page'));
const BillingPage = lazy(() => import('@/features/recruiter/pages/billing'));
const ChatbotLeadsPage = lazy(() => import('@/features/recruiter/pages/chatbot-leads'));
const JdEditorPage = lazy(() => import('@/features/recruiter/pages/jd-editor'));
const AutoJobPage = lazy(() => import('@/features/recruiter/pages/auto-job'));
const GhostReportPage = lazy(() => import('@/features/recruiter/pages/ghost-report'));
const ComparePage = lazy(() => import('@/features/recruiter/pages/compare'));
const BiasAnalyticsPage = lazy(() => import('@/features/recruiter/pages/bias-analytics'));
const CalendarSettingsPage = lazy(() => import('@/features/recruiter/pages/calendar-settings'));
const SkillTreeCreatePage = lazy(() => import('@/features/recruiter/pages/skill-tree-create'));
const SkillTreeDetailPage = lazy(() => import('@/features/recruiter/pages/skill-tree-detail'));

// ---- Reports ----
const ReportBuilderPage = lazy(() => import('@/features/reports/pages/report-builder'));

// ---- Interviews ----
const RoleBasedInterviews = lazy(() => import('@/features/interviews/pages/role-based-interviews'));
const InterviewAnalysisPage = lazy(() => import('@/features/interviews/pages/role-based-interview-analysis'));
const InterviewRoomPage = lazy(() => import('@/features/interviews/pages/interview-room'));

const ScheduleInterviewPage = lazy(() => import('@/features/interviews/pages/schedule-interview'));

const InterviewDetailPage = lazy(() => import('@/features/interviews/pages/interview-detail'));
// ---- Jobs ----
const RoleBasedJobs             = lazy(() => import('@/features/jobs/pages/role-based-jobs'));
const RoleBasedJobDetail        = lazy(() => import('@/features/jobs/pages/role-based-job-detail'));

// ---- Candidate Interactive ----
const CVBuilderPage         = lazy(() => import('@/features/cv-builder/pages/cv-builder-page'));
const CVReviewPage          = lazy(() => import('@/features/cv-review/pages/cv-review-page'));
const ApplicationsTrackerPage = lazy(() => import('@/features/candidate/pages/applications-tracker'));
const CandidateApplicationDetailPage = lazy(() => import('@/features/candidate/pages/candidate-application-detail'));
const OnboardingPage        = lazy(() => import('@/features/candidate/pages/onboarding'));
const MarketplacePage       = lazy(() => import('@/features/candidate/pages/marketplace'));

// ---- Intelligence & Evaluation ----
const AnalyticsDashboard = lazy(() => import('@/features/analytics/pages/analytics-dashboard'));
const ReportsDashboard   = lazy(() => import('@/features/reports/pages/reports-dashboard'));
const SkillTreesPage     = lazy(() => import('@/features/skill-trees/pages/skill-trees-page'));
const SkillProgressPage  = lazy(() => import('@/features/skill-progress/pages/skill-progress-page'));
const RubricsPage        = lazy(() => import('@/features/rubrics/pages/rubrics-page'));

// ---- Learning & Certifications ----
const CoursesListPage    = lazy(() => import('@/features/courses/pages/courses-list'));
const AchievementsPage   = lazy(() => import('@/features/achievements/pages/achievements-page'));

// ---- Engage Suite ----
const MessagesPage       = lazy(() => import('@/features/messages/pages/messages-page'));
const CalendarPage       = lazy(() => import('@/features/calendar/pages/calendar-page'));
const CampaignsListPage  = lazy(() => import('@/features/email-campaigns/pages/campaigns-list'));
const CopilotPage        = lazy(() => import('@/features/recruiter/pages/copilot'));

// ---- Admin Suite ----
const AdminUsersPage         = lazy(() => import('@/features/admin/pages/users-management'));
const SubscriptionsManager   = lazy(() => import('@/features/admin/pages/subscriptions-manager'));
const AIMonitoringPage       = lazy(() => import('@/features/admin/pages/ai-monitoring'));
const PromptManagementPage   = lazy(() => import('@/features/admin/pages/prompt-management'));

// ---- Settings & Help ----
const SettingsPage     = lazy(() => import('@/features/settings/pages/settings-page'));
const ComingSoonPage   = lazy(() => import('@/shared/components/ui/coming-soon'));

const EmailTemplatesPage= lazy(() => import('@/features/recruiter/pages/email-templates'));
const CampaignDetailPage= lazy(() => import('@/features/recruiter/pages/campaign-detail'));
const CampaignCreatePage= lazy(() => import('@/features/recruiter/pages/campaign-create'));
const CampaignComparePage= lazy(() => import('@/features/recruiter/pages/campaign-compare'));
const SystemHealthPage  = lazy(() => import('@/features/admin/pages/system-health'));

// ---- New Admin Pages ----
const ContentManagerPage      = lazy(() => import('@/features/admin/pages/content-manager'));
const OpportunitiesManager    = lazy(() => import('@/features/admin/pages/opportunities-manager'));
const VerificationsManager    = lazy(() => import('@/features/admin/pages/verifications-manager'));
const CoursesManagerPage      = lazy(() => import('@/features/admin/pages/courses-manager'));
const PaymentsPage            = lazy(() => import('@/features/admin/pages/payments'));
       const FinanceDashboardPage    = lazy(() => import('@/features/admin/pages/finance-dashboard'));
       const InvoicesPage            = lazy(() => import('@/features/admin/pages/invoices'));
       const PaymentProofsPage       = lazy(() => import('@/features/admin/pages/payment-proofs'));
const MarketingPage           = lazy(() => import('@/features/admin/pages/marketing'));
const AnnouncementsPage       = lazy(() => import('@/features/admin/pages/announcements'));
const RecruiterUsagePage      = lazy(() => import('@/features/admin/pages/recruiter-usage'));
const RubricBuilderAdminPage  = lazy(() => import('@/features/admin/pages/rubric-builder'));
const SupportInboxPage        = lazy(() => import('@/features/admin/pages/support'));
const AiSalesPage             = lazy(() => import('@/features/admin/pages/ai-sales'));
const AbTestingPage           = lazy(() => import('@/features/admin/pages/ab-testing'));
const CategoriesAdminPage     = lazy(() => import('@/features/admin/pages/categories'));
const AdminJobsPage           = lazy(() => import('@/features/admin/pages/admin-jobs'));
const AdminRubricsPage        = lazy(() => import('@/features/admin/pages/admin-rubrics-list'));
const OrganizationsPage       = lazy(() => import('@/features/admin/pages/organizations'));
const KybManagerPage          = lazy(() => import('@/features/admin/pages/kyb-manager'));
const AdminAnalyticsPage      = lazy(() => import('@/features/admin/pages/admin-analytics'));

// ---- New Recruiter Pages ----
const ScoringPreviewPage      = lazy(() => import('@/features/recruiter/pages/scoring-preview'));
const EeoDashboardPage        = lazy(() => import('@/features/recruiter/pages/eeo-dashboard'));
const EeoCoveragePage         = lazy(() => import('@/features/recruiter/pages/eeo-coverage'));

// ---- New Candidate Pages ----
const ProfileVisitorsPage     = lazy(() => import('@/features/candidate/pages/profile-visitors'));
const CandidateOwnProfilePage = lazy(() => import('@/features/candidate/pages/candidate-own-profile'));
const QualificationsPage      = lazy(() => import('@/features/candidate/pages/qualifications'));
const CandidateEsignViewPage  = lazy(() => import('@/features/candidate/pages/candidate-esign-view'));
const PublicProfilePage       = lazy(() => import('@/features/candidate/pages/public-profile'));

// ---- New Mentor Pages ----
const MentorStudentsPage      = lazy(() => import('@/features/mentor/pages/mentor-students'));
const MentorWalletPage        = lazy(() => import('@/features/mentor/pages/mentor-wallet'));

// ---- Org Portal (company admin) ----
const OrgDashboardPage        = lazy(() => import('@/features/org/pages/org-dashboard'));
const OrgMembersPage          = lazy(() => import('@/features/org/pages/org-members'));
const OrgAnalyticsListPage    = lazy(() => import('@/features/org/pages/org-analytics-list'));
const OrgAnalyticsDetailPage  = lazy(() => import('@/features/org/pages/org-analytics-detail'));
const OrgBillingPage          = lazy(() => import('@/features/org/pages/org-billing'));

function S({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<PageLoader />}>{children}</Suspense>;
}

function allowed(roles: UserRole[], children: React.ReactNode) {
  return <RoleGuard roles={roles}>{children}</RoleGuard>;
}

export const router = createBrowserRouter([
  {
    path: '/',
    element: <S><CandwayLanding /></S>,
    errorElement: <RouteErrorPage />,
  },
  {
    path: '/landing',
    element: <S><CandwayLanding /></S>,
  },
  // ---- Auth (Pre-Login) ----
  {
    path: '/auth',
    element: <AuthLayout />,
    errorElement: <RouteErrorPage />,
    children: [
      { path: 'login', element: <S><LoginPage /></S> },
      { path: 'register', element: <S><RegisterPage /></S> },
      { path: 'register-company', element: <S><RegisterCompanyPage /></S> },
      { path: 'forgot-password', element: <S><ForgotPasswordPage /></S> },
      { path: 'reset-password', element: <S><ResetPasswordPage /></S> },
      { path: 'verify-email', element: <S><VerifyEmailPage /></S> },
      { path: 'verify-otp', element: <S><VerifyOtpPage /></S> },
      { path: 'interview-access', element: <S><InterviewAccessPage /></S> },
      { path: '', element: <Navigate to="/auth/login" replace /> },
    ],
  },
  // ---- Google OAuth Callback (full-screen, standalone) ----
  {
    path: '/auth/google/callback',
    element: <S><GoogleCallbackPage /></S>,
    errorElement: <RouteErrorPage />,
  },
  // ---- Public Marketing Pages ----
  {
    path: '/pricing',
    element: <S><MarketingLayout><PricingPage /></MarketingLayout></S>,
  },
  {
    path: '/blogs',
    element: <S><BlogsPage /></S>,
  },
  {
    path: '/blog/:slug',
    element: <S><BlogDetailPage /></S>,
  },
  {
    path: '/opportunities',
    element: <S><MarketingLayout><OpportunitiesPage /></MarketingLayout></S>,
  },
  {
    path: '/privacy',
    element: <S><MarketingLayout><PrivacyPage /></MarketingLayout></S>,
  },
  {
    path: '/terms',
    element: <S><MarketingLayout><TermsPage /></MarketingLayout></S>,
  },
  {
    path: '/careers',
    element: <S><PublicJobsPage /></S>,
  },
  {
    path: '/careers/:jobId',
    element: <S><PublicJobDetailPage /></S>,
  },
  {
    path: '/catalog',
    element: <S><MarketingLayout><PublicCoursesPage /></MarketingLayout></S>,
  },
  // ---- Authenticated Dashboard Shell ----
  {
    path: '/',
    element: <ProtectedRoute><DashboardLayout /></ProtectedRoute>,
    errorElement: <RouteErrorPage />,
    children: [
      // Central Role Dashboard
      { path: 'dashboard', element: <S><RoleBasedDashboard /></S> },
      { path: 'candidate-dashboard', element: <S><RoleBasedDashboard /></S> },
      { path: 'admin', element: <S><RoleBasedDashboard /></S> },
      { path: 'admin/dashboard', element: allowed(['admin'], <S><Navigate to="/dashboard" replace /></S>) },
      { path: 'mentor', element: <S><RoleBasedDashboard /></S> },

      // Recruitment
      { path: 'jobs/new', element: allowed(['recruiter', 'admin'], <S><JobWizardPage /></S>) },
      { path: 'jobs/:id', element: allowed(['candidate', 'recruiter', 'admin'], <S><RoleBasedJobDetail /></S>) },
      { path: 'candidates', element: allowed(['recruiter', 'admin', 'mentor'], <S><CandidatesListPage /></S>) },
      { path: 'candidates/:id', element: allowed(['recruiter', 'admin', 'mentor'], <S><ApplicationDetailPage /></S>) },
      { path: 'candidates/c/:candidateId', element: allowed(['recruiter', 'admin', 'mentor'], <S><ApplicationDetailPage /></S>) },
      { path: 'recruiter/applications', element: allowed(['recruiter', 'admin', 'mentor'], <S><ApplicationsPage /></S>) },
      { path: 'pipeline', element: allowed(['recruiter', 'admin'], <S><PipelineBoardPage /></S>) },
      { path: 'scoring-preview', element: allowed(['recruiter', 'admin'], <S><ScoringPreviewPage /></S>) },
      { path: 'billing', element: allowed(['recruiter', 'admin'], <S><BillingPage /></S>) },
      { path: 'chatbot-leads', element: allowed(['recruiter', 'admin'], <S><ChatbotLeadsPage /></S>) },
      { path: 'jd-editor', element: allowed(['recruiter', 'admin'], <S><JdEditorPage /></S>) },
      { path: 'auto-job', element: allowed(['recruiter', 'admin'], <S><AutoJobPage /></S>) },
      { path: 'ghost-report', element: allowed(['recruiter', 'admin'], <S><GhostReportPage /></S>) },
      { path: 'compare', element: allowed(['recruiter', 'admin'], <S><ComparePage /></S>) },
      { path: 'bias-analytics', element: allowed(['recruiter', 'admin'], <S><BiasAnalyticsPage /></S>) },
      { path: 'calendar-settings', element: allowed(['recruiter', 'admin'], <S><CalendarSettingsPage /></S>) },
      { path: 'skill-tree-create', element: allowed(['recruiter', 'admin'], <S><SkillTreeCreatePage /></S>) },
      { path: 'skill-tree/:id', element: allowed(['recruiter', 'admin'], <S><SkillTreeDetailPage /></S>) },
      { path: 'report-builder', element: allowed(['recruiter', 'admin'], <S><ReportBuilderPage /></S>) },
      { path: 'campaigns/new', element: allowed(['recruiter', 'admin'], <S><CampaignCreatePage /></S>) },
      { path: 'campaigns/compare', element: allowed(['recruiter', 'admin'], <S><CampaignComparePage /></S>) },
      { path: 'campaigns/:id', element: allowed(['recruiter', 'admin'], <S><CampaignDetailPage /></S>) },
      { path: 'eeo/dashboard', element: allowed(['recruiter', 'admin'], <S><EeoDashboardPage /></S>) },
      { path: 'eeo/coverage', element: allowed(['recruiter', 'admin'], <S><EeoCoveragePage /></S>) },

      // Interviews
      { path: 'interviews', element: allowed(['candidate', 'recruiter', 'admin', 'mentor'], <S><RoleBasedInterviews /></S>) },
      { path: 'interviews/new', element: allowed(['recruiter', 'admin'], <S><ScheduleInterviewPage /></S>) },
      { path: 'interviews/:id', element: allowed(['recruiter', 'admin'], <S><InterviewDetailPage /></S>) },
      { path: 'interviews/:id/analysis', element: <InterviewAnalysisRoute><S><InterviewAnalysisPage /></S></InterviewAnalysisRoute> },
      { path: 'interview-analysis', element: <InterviewAnalysisRoute><S><InterviewAnalysisPage /></S></InterviewAnalysisRoute> },
      { path: 'candidate/interview-analysis', element: <InterviewAnalysisRoute><S><InterviewAnalysisPage /></S></InterviewAnalysisRoute> },
      { path: 'recruiter/interview-analysis', element: <InterviewAnalysisRoute><S><InterviewAnalysisPage /></S></InterviewAnalysisRoute> },

      // Candidate Interactive
      { path: 'jobs', element: allowed(['candidate', 'recruiter', 'admin'], <S><RoleBasedJobs /></S>) },
      { path: 'cv-builder', element: allowed(['candidate', 'admin'], <S><CVBuilderPage /></S>) },
      { path: 'cv-review', element: allowed(['candidate', 'admin'], <S><CVReviewPage /></S>) },
      { path: 'applications', element: allowed(['candidate', 'admin'], <S><ApplicationsTrackerPage /></S>) },
      { path: 'applications/:id', element: allowed(['candidate', 'admin'], <S><CandidateApplicationDetailPage /></S>) },
      { path: 'profile-visitors', element: allowed(['candidate', 'admin'], <S><ProfileVisitorsPage /></S>) },
      { path: 'profile', element: allowed(['candidate', 'admin'], <S><CandidateOwnProfilePage /></S>) },
      { path: 'candidate/profile', element: allowed(['candidate', 'admin'], <S><CandidateOwnProfilePage /></S>) },
      { path: 'profile-view', element: allowed(['candidate', 'admin'], <S><PublicProfilePage /></S>) },
      { path: 'profile-view/:userId', element: <S><PublicProfilePage /></S> },
      { path: 'public-profile', element: <S><PublicProfilePage /></S> },
      { path: 'public-profile/:userId', element: <S><PublicProfilePage /></S> },
      { path: 'qualifications', element: allowed(['candidate', 'admin'], <S><QualificationsPage /></S>) },
      { path: 'esign-view', element: allowed(['candidate', 'admin'], <S><CandidateEsignViewPage /></S>) },
      { path: 'documents', element: <S><Navigate to="/qualifications" replace /></S> },
      { path: 'cv-selection', element: <S><Navigate to="/cv-builder" replace /></S> },

      // Intelligence
      { path: 'analytics', element: allowed(['recruiter', 'admin'], <S><AnalyticsDashboard /></S>) },
      { path: 'reports', element: allowed(['recruiter', 'admin'], <S><ReportsDashboard /></S>) },
      { path: 'skill-trees', element: allowed(['recruiter', 'admin', 'mentor'], <S><SkillTreesPage /></S>) },
      { path: 'skill-progress', element: allowed(['candidate', 'admin'], <S><SkillProgressPage /></S>) },
      { path: 'rubrics', element: allowed(['recruiter', 'admin', 'mentor'], <S><RubricsPage /></S>) },

      // Learning
      { path: 'courses', element: allowed(['candidate', 'admin', 'mentor'], <S><CoursesListPage /></S>) },

      { path: 'achievements', element: allowed(['candidate', 'admin'], <S><AchievementsPage /></S>) },

      // Engage
      { path: 'messages', element: allowed(['candidate', 'recruiter', 'admin', 'mentor'], <S><MessagesPage /></S>) },
      { path: 'calendar', element: allowed(['candidate', 'recruiter', 'admin', 'mentor'], <S><CalendarPage /></S>) },
      { path: 'email-campaigns', element: allowed(['recruiter', 'admin'], <S><CampaignsListPage /></S>) },
      { path: 'campaigns', element: allowed(['recruiter', 'admin'], <S><CampaignsListPage /></S>) },
      { path: 'copilot', element: allowed(['recruiter', 'admin'], <S><CopilotPage /></S>) },

      // Admin
      { path: 'admin/users', element: allowed(['admin'], <S><AdminUsersPage /></S>) },
      { path: 'admin/organizations', element: allowed(['admin'], <S><OrganizationsPage /></S>) },
      { path: 'admin/kyb', element: allowed(['admin'], <S><KybManagerPage /></S>) },
      { path: 'admin/subscriptions', element: allowed(['admin'], <S><SubscriptionsManager /></S>) },
      { path: 'admin/moderation', element: allowed(['admin'], <S><VerificationsManager /></S>) },
      { path: 'admin/analytics', element: allowed(['admin'], <S><AdminAnalyticsPage /></S>) },
      { path: 'admin/content', element: allowed(['admin'], <S><ContentManagerPage /></S>) },
      { path: 'admin/opportunities', element: allowed(['admin'], <S><OpportunitiesManager /></S>) },
      { path: 'admin/courses', element: allowed(['admin'], <S><CoursesManagerPage /></S>) },
      { path: 'admin/ai-monitoring', element: allowed(['admin'], <S><AIMonitoringPage /></S>) },
      { path: 'admin/logs', element: allowed(['admin'], <S><SystemHealthPage /></S>) },
      { path: 'admin/permissions', element: allowed(['admin'], <S><ComingSoonPage title="RBAC Permissions" /></S>) },
      { path: 'admin/prompt-management', element: allowed(['admin'], <S><PromptManagementPage /></S>) },
      { path: 'admin/settings', element: allowed(['admin'], <S><SettingsPage /></S>) },
      { path: 'admin/payments', element: allowed(['admin'], <S><PaymentsPage /></S>) },
      { path: 'admin/payment-proofs', element: allowed(['admin'], <S><PaymentProofsPage /></S>) },
      { path: 'admin/finance', element: allowed(['admin'], <S><FinanceDashboardPage /></S>) },
      { path: 'admin/invoices', element: allowed(['admin'], <S><InvoicesPage /></S>) },
      { path: 'admin/marketing', element: allowed(['admin'], <S><MarketingPage /></S>) },
      { path: 'admin/announcements', element: allowed(['admin'], <S><AnnouncementsPage /></S>) },
      { path: 'admin/recruiter-usage', element: allowed(['admin'], <S><RecruiterUsagePage /></S>) },
      { path: 'admin/rubric-builder', element: allowed(['admin'], <S><RubricBuilderAdminPage /></S>) },
      { path: 'admin/support', element: allowed(['admin'], <S><SupportInboxPage /></S>) },
      { path: 'admin/ai-sales', element: allowed(['admin'], <S><AiSalesPage /></S>) },
      { path: 'admin/ab-testing', element: allowed(['admin'], <S><AbTestingPage /></S>) },
      { path: 'admin/categories', element: allowed(['admin'], <S><CategoriesAdminPage /></S>) },
       { path: 'admin/jobs', element: allowed(['admin'], <S><AdminJobsPage /></S>) },
      { path: 'admin/rubrics', element: allowed(['admin'], <S><AdminRubricsPage /></S>) },

      // Org Portal (company admin)
      { path: 'org', element: allowed(['company'], <S><OrgDashboardPage /></S>) },
      { path: 'org/dashboard', element: allowed(['company'], <S><OrgDashboardPage /></S>) },
      { path: 'org/members', element: allowed(['company'], <S><OrgMembersPage /></S>) },
      { path: 'org/analytics', element: allowed(['company'], <S><OrgAnalyticsListPage /></S>) },
      { path: 'org/analytics/:userId', element: allowed(['company'], <S><OrgAnalyticsDetailPage /></S>) },
      { path: 'org/billing', element: allowed(['company'], <S><OrgBillingPage /></S>) },


      // Mentor
      { path: 'mentor/mentees', element: allowed(['mentor', 'admin'], <S><CandidatesListPage /></S>) },
      { path: 'mentor/sessions', element: allowed(['mentor', 'admin'], <S><RoleBasedInterviews /></S>) },
      { path: 'mentor/reviews', element: allowed(['mentor', 'admin'], <S><CVReviewPage /></S>) },
      { path: 'mentor/resources', element: allowed(['mentor', 'admin'], <S><CoursesListPage /></S>) },
      { path: 'mentor/messages', element: allowed(['mentor', 'admin'], <S><MessagesPage /></S>) },
      { path: 'mentor/students', element: allowed(['mentor', 'admin'], <S><MentorStudentsPage /></S>) },
      { path: 'mentor/wallet', element: allowed(['mentor', 'admin'], <S><MentorWalletPage /></S>) },
      { path: 'mentor/community', element: allowed(['mentor', 'admin'], <S><ComingSoonPage title="Mentor Community" /></S>) },
      { path: 'mentor/courses', element: allowed(['mentor', 'admin'], <S><CoursesListPage /></S>) },
      { path: 'mentor/profile', element: allowed(['mentor', 'admin'], <S><ComingSoonPage title="Mentor Profile Editor" /></S>) },
      { path: 'mentor/settings', element: allowed(['mentor', 'admin'], <S><SettingsPage /></S>) },

      // Legacy route redirects
      { path: 'comparison', element: <Navigate to="/compare" replace /> },
      { path: 'skill-tree', element: <Navigate to="/skill-trees" replace /> },
      { path: 'skill-tree-list', element: <Navigate to="/skill-trees" replace /> },
      { path: 'subscription', element: <Navigate to="/billing" replace /> },
      { path: 'landing', element: <Navigate to="/dashboard" replace /> },

      // Universal
      { path: 'settings', element: <S><SettingsPage /></S> },
      { path: 'settings/:tab', element: <S><SettingsPage /></S> },
      { path: 'help', element: <S><Navigate to="/settings" replace /></S> },
      { path: 'notifications', element: <S><Navigate to="/settings/notifications" replace /></S> },

      // Placeholder Bridges
      { path: 'onboarding', element: allowed(['candidate', 'admin'], <S><OnboardingPage /></S>) },
      { path: 'marketplace', element: allowed(['candidate', 'admin'], <S><MarketplacePage /></S>) },
      { path: 'email-templates', element: allowed(['recruiter', 'admin'], <S><EmailTemplatesPage /></S>) },
    ],
  },
  // ---- Interview Room (Full-Screen, No Sidebar/Topbar) ----
  {
    path: 'interviews/room',
    element: <InterviewRoomRoute><S><InterviewRoomPage /></S></InterviewRoomRoute>,
    errorElement: <RouteErrorPage />,
  },
  {
    path: 'interviews/room/:sessionId',
    element: <InterviewRoomRoute><S><InterviewRoomPage /></S></InterviewRoomRoute>,
    errorElement: <RouteErrorPage />,
  },
  { path: '*', element: <Navigate to="/dashboard" replace />, errorElement: <RouteErrorPage /> },
]);
