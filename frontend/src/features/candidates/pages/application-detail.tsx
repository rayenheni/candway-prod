// ============================================================
// Recruiter Candidate Profile - Matches Candway Production UI
// ============================================================

import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link, useSearchParams } from 'react-router';
import { motion } from 'framer-motion';
import { Card } from '@/shared/components/ui/card';
import { customToast } from '@/shared/components/ui/toast';
import { Loader2 } from 'lucide-react';
import { cn } from '@/utils/cn';
import { useLanguage } from '@/contexts/language-context';
import { candidatesService } from '@/services/candidates.service';
import { candidateService } from '@/services/candidate.service';
import { subscriptionService } from '@/services/subscription.service';
import { useAuth } from '@/contexts/auth-context';
import { CVEvaluation } from '@/shared/components/cv-evaluation';
import {
  ChevronRight,
  CheckCircle2,
  XCircle,
  MapPin,
  Briefcase,
  Mail,
  Phone,
  Calendar,
  Clock,
  Video,
  Download,
  FileText,
  TrendingUp,
  Shield,
  Wifi,
  User,
  Monitor,
  Users,
  Send,
  MessageSquare,
  Star,
  Sparkles,
} from 'lucide-react';

type Tab =
  | 'overview'
  | 'interviews'
  | 'notes'
  | 'timeline'
  | 'cv';

export default function ApplicationDetailPage() {
  const { t } = useLanguage();
  const { id, candidateId } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const tabParam = searchParams.get('tab');
  const [activeTab, setActiveTab] = useState<Tab>(() => {
    if (tabParam && ['overview', 'cv', 'interviews', 'notes', 'timeline'].includes(tabParam)) return tabParam as Tab;
    return 'overview';
  });

  const TABS: { id: Tab; label: string }[] = [
    { id: 'overview', label: t('cprofile.overview') },
    { id: 'cv', label: t('cprofile.cvEvaluation') },
    { id: 'interviews', label: t('cprofile.interviews') },
    { id: 'notes', label: t('cprofile.notes') },
    { id: 'timeline', label: t('cprofile.timeline') },
  ];
  const [comment, setComment] = useState('');
  const [note, setNote] = useState('');
  const [candidate, setCandidate] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [photoBroken, setPhotoBroken] = useState(false);
  const [appId, setAppId] = useState<string | undefined>(candidateId ? undefined : id);
  const [applications, setApplications] = useState<any[]>([]);

  const [scheduledInterviews, setScheduledInterviews] = useState<any[]>([]);
  const [loadingNotes, setLoadingNotes] = useState(false);
  const { user } = useAuth();
  const [recruiterTier, setRecruiterTier] = useState<string | undefined>(undefined);

  useEffect(() => {
    if (user?.role === 'recruiter' || user?.role === 'admin') {
      subscriptionService.getStatus()
        .then((status: any) => setRecruiterTier(status?.tier))
        .catch(() => setRecruiterTier(undefined));
    }
  }, [user?.role]);

  const isProRecruiter = ['pro', 'pro_plus', 'enterprise'].includes(recruiterTier || '');

  useEffect(() => {
    if (candidateId) {
      setLoading(true);
      setPhotoBroken(false);
      candidatesService.getCandidateProfile(candidateId)
        .then((profile: any) => {
          setCandidate(profile || {});
          setApplications(Array.isArray(profile?.applications) ? profile.applications : []);
          const repApp = profile?.best_application_id ? String(profile.best_application_id) : '';
          setAppId(repApp || undefined);
          setNote((profile as any)?.recruiter_notes || '');
          const userId = (profile as any)?.user_id;
          if (userId) {
            candidateService.recordProfileView(userId).catch(() => {});
          }
          if (repApp) {
            candidatesService.getScheduledInterviews(repApp).catch(() => [])
              .then((schData) => setScheduledInterviews(Array.isArray(schData) ? schData : []));
          }
        })
        .catch(() => {
          setCandidate(null);
          setScheduledInterviews([]);
        })
        .finally(() => setLoading(false));
      return;
    }
    if (!id) return;
    setLoading(true);
    setPhotoBroken(false);
    Promise.all([
      candidatesService.getApplication(id).catch(() => null),
      candidatesService.getScheduledInterviews(id).catch(() => [])
    ])
      .then(([appData, schData]) => {
        setCandidate(appData || {});
        setScheduledInterviews(Array.isArray(schData) ? schData : []);
        setNote((appData as any)?.recruiter_notes || '');
        const userId = (appData as any)?.user_id;
        if (userId) {
          candidateService.recordProfileView(userId).catch(() => {});
        }
      })
      .catch(() => {
        setCandidate(null);
        setScheduledInterviews([]);
      })
      .finally(() => setLoading(false));
  }, [id, candidateId]);

  useEffect(() => {
    if (!appId || !candidate) return;
    setLoadingNotes(true);
    candidatesService.getNotes(appId)
      .then((res: any) => setNote(res?.notes || ''))
      .catch(() => setNote(''))
      .finally(() => setLoadingNotes(false));
  }, [appId, candidate]);

  if (loading) {
    return <div className="flex items-center justify-center h-64"><Loader2 className="h-8 w-8 animate-spin text-violet-600" /></div>;
  }
  if (!candidate) {
    return <div className="text-center py-16 text-gray-500">{t('appdetail.notFound')}</div>;
  }

  const cName = candidate.full_name || candidate.candidate_name || t('appdetail.unknown');
  const cInitials = cName.split(' ').map((s: string) => s[0]).slice(0, 2).join('').toUpperCase() || '?';
  const cRole = candidate.role || candidate.declared_role || 'N/A';
  const cEmail = candidate.email || 'N/A';
  const cPhone = candidate.phone || 'N/A';
  const cStage = candidate.status || candidate.stage || 'N/A';
  const cDeclined = candidate.is_declined || false;
  const interviewDone = ['completed', 'flagged'].includes(candidate.interview_state);
  const cScore = interviewDone
    ? (candidate.score ?? candidate.cv_score ?? 0)
    : (candidate.cv_score ?? candidate.score ?? 0);
  const cScoreLabel = interviewDone ? t('appdetail.overallScore') : t('appdetail.cvMatch');
  const cSkills: string[] = Array.isArray(candidate.skills) ? candidate.skills : [];
  const cAnalysis = candidate.analysis || {};

  const circumference = 2 * Math.PI * 54;
  const dash = (cScore / 100) * circumference;

  const handleSendComment = async () => {
    if (!comment.trim() || !appId) return;
    try {
      await candidatesService.addNote(appId, comment.trim());
      setNote(comment.trim());
      setComment('');
      customToast({ type: 'success', title: t('appdetail.noteSaved'), message: t('appdetail.noteSavedMsg') });
    } catch {
      customToast({ type: 'error', title: t('appdetail.saveFailed'), message: t('appdetail.noteSaveError') });
    }
  };

  const handleMoveStage = async (status: string) => {
    if (!appId) return;
    try {
      await candidatesService.updateApplicationStatus(appId, status);
      setCandidate((prev: any) => ({ ...prev, status }));
      customToast({ type: 'success', title: t('appdetail.stageUpdated'), message: t('appdetail.stageUpdatedMsg').replace('{status}', status) });
    } catch {
      customToast({ type: 'error', title: t('appdetail.updateFailed'), message: t('appdetail.stageUpdateError') });
    }
  };

  const handleGenerateReport = () => {
    navigate(`/ghost-report?app=${appId}`);
  };

  const handleAIInsights = () => {
    navigate(`/recruiter/interview-analysis?id=${appId}`);
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* ===== Breadcrumb ===== */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-base">
          <Link to="/candidates" className="font-semibold text-violet-600 dark:text-violet-400 hover:underline">
            {t('candidates.stat.candidates')}
          </Link>
          <ChevronRight className="h-4 w-4 text-gray-300" />
          <span className="font-semibold text-gray-900 dark:text-white">{cName}</span>
        </div>
        {isProRecruiter && (
          <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-violet-50 dark:bg-violet-500/10 text-xs font-bold text-violet-600 dark:text-violet-400">
            PRO <Star className="h-3 w-3 fill-current" />
          </span>
        )}
      </div>

      {candidateId && applications.length > 1 && (
        <Card className="p-4 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-violet-50 dark:bg-violet-500/10 text-xs font-bold text-violet-600 dark:text-violet-400">
              <Users className="h-3.5 w-3.5" /> {applications.length} {t('appdetail.applications')}
            </span>
            {applications.map((a) => {
              const isActive = a.id === (candidate as any)?.id;
              return (
                <button
                  key={a.id}
                  onClick={() => navigate(`/candidates/${a.id}`)}
                  className={cn(
                    'px-3 py-1.5 rounded-full text-xs font-semibold transition-colors',
                    isActive
                      ? 'bg-violet-600 text-white'
                      : 'bg-gray-100 dark:bg-white/[0.06] text-gray-600 dark:text-gray-300 hover:bg-violet-100 dark:hover:bg-violet-500/15'
                  )}
                >
                  {a.job_title || `${t('appdetail.application')} #${a.id}`}
                </button>
              );
            })}
          </div>
        </Card>
      )}

      {/* ===== Header Card ===== */}
      <Card className="p-6 md:p-8 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_auto_auto] gap-8 items-start">
          {/* Left: identity */}
          <div className="flex items-start gap-5 min-w-0">
            {candidate.photo_url && !photoBroken ? (
              <img
                src={candidate.photo_url}
                alt={cName}
                onError={() => setPhotoBroken(true)}
                className="h-24 w-24 rounded-full object-cover bg-violet-100 dark:bg-violet-500/15 shrink-0"
              />
            ) : (
              <div className="h-24 w-24 rounded-full bg-violet-100 dark:bg-violet-500/15 flex items-center justify-center text-violet-600 dark:text-violet-400 text-3xl font-extrabold shrink-0">
                {cInitials}
              </div>
            )}
            <div className="min-w-0 space-y-2.5">
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-3xl font-extrabold text-gray-900 dark:text-white tracking-tight">{cName}</h1>
                <CheckCircle2 className="h-5 w-5 text-violet-500 shrink-0" />
                <span className="px-3 py-1 rounded-full bg-red-50 dark:bg-red-500/10 text-[11px] font-bold tracking-wide text-red-500">
                  {cStage}
                </span>
                {cDeclined && (
                  <div className="px-4 py-2 rounded-xl border border-red-300 dark:border-red-500/40 bg-red-50/40 dark:bg-red-500/5">
                    <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-red-500">
                      <XCircle className="h-3.5 w-3.5" /> {t('cprofile.candidateDeclined')}
                    </div>
                    <div className="text-xs italic text-red-400 mt-0.5">{t('cprofile.noReason')}</div>
                  </div>
                )}
              </div>

              <p className="text-lg text-gray-600 dark:text-gray-300">{cRole}</p>

              <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 text-sm text-gray-500 dark:text-gray-400">
                <span className="inline-flex items-center gap-1.5"><MapPin className="h-3.5 w-3.5 text-gray-400" /> {candidate.location || '--'}</span>
                <span className="inline-flex items-center gap-1.5"><Briefcase className="h-3.5 w-3.5 text-gray-400" /> {candidate.years_experience ?? '--'}</span>
                <span className="inline-flex items-center gap-1.5"><Mail className="h-3.5 w-3.5 text-gray-400" /> {cEmail}</span>
                <span className="inline-flex items-center gap-1.5"><Phone className="h-3.5 w-3.5 text-gray-400" /> {cPhone}</span>
                {candidate.linkedin_url ? (
                  <a href={candidate.linkedin_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-violet-600 dark:text-violet-400 hover:underline">
                    <svg className="h-3.5 w-3.5" fill="currentColor" viewBox="0 0 24 24"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>
                    LinkedIn
                  </a>
                ) : (
                  <span className="inline-flex items-center gap-1.5">
                    <svg className="h-3.5 w-3.5 text-gray-400" fill="currentColor" viewBox="0 0 24 24"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>
                    --
                  </span>
                )}
              </div>

              <p className="text-sm italic text-gray-400">{candidate.skills?.length ? `${candidate.skills.length} ${t('appdetail.skillsListed')}` : t('cprofile.noSkillsListed')}</p>
            </div>
          </div>

          {/* Middle: Match ring */}
          <div className="flex flex-col items-center gap-3 lg:px-8 lg:border-l lg:border-gray-100 dark:lg:border-white/[0.06]">
            <div className="relative h-32 w-32">
              <svg className="h-32 w-32 -rotate-90" viewBox="0 0 120 120">
                <circle cx="60" cy="60" r="54" fill="none" stroke="currentColor" strokeWidth="9" className="text-gray-100 dark:text-white/5" />
                <motion.circle
                  cx="60" cy="60" r="54" fill="none" stroke="#7C3AED" strokeWidth="9" strokeLinecap="round"
                  initial={{ strokeDasharray: `0 ${circumference}` }}
                  animate={{ strokeDasharray: `${dash} ${circumference - dash}` }}
                  transition={{ duration: 1, ease: 'easeOut' }}
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-4xl font-extrabold text-gray-900 dark:text-white">{cScore}</span>
                <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">{cScoreLabel}</span>
              </div>
            </div>
            <span className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full bg-violet-50 dark:bg-violet-500/10 text-sm font-semibold text-violet-700 dark:text-violet-300">
              <TrendingUp className="h-3.5 w-3.5" /> {interviewDone ? (candidate.score_label || t('appdetail.evaluated')) : (cScore >= 80 ? t('appdetail.strongCvMatch') : cScore >= 65 ? t('appdetail.goodCvMatch') : t('appdetail.cvMatch'))}
            </span>
            <p className="text-sm text-gray-500 dark:text-gray-400">{cAnalysis.summary ? (interviewDone ? t('appdetail.aiAnalysisComplete') : t('appdetail.cvAnalysisComplete')) : t('cprofile.aiAnalysisProgress')}</p>
          </div>

          {/* Right: Actions */}
          <div className="flex flex-col gap-3 w-full lg:w-56">
            <label className="flex flex-col gap-1.5">
              <span className="text-[11px] font-bold uppercase tracking-wider text-gray-400">{t('candidates.allStages')}</span>
              <select
                value={candidate.status || 'screening'}
                onChange={(e) => handleMoveStage(e.target.value)}
                className="w-full px-4 py-3 rounded-2xl bg-violet-600 hover:bg-violet-700 text-white text-sm font-bold shadow-md shadow-violet-500/25 transition-colors focus:outline-none [&>option]:bg-white [&>option]:text-gray-900"
              >
                <option value="screening">{t('org.screening')}</option>
                <option value="interviewing">{t('org.interview')}</option>
                <option value="shortlisted">{t('candidates.stat.shortlisted')}</option>
                <option value="offer">{t('org.offer')}</option>
                <option value="hired">{t('org.hired')}</option>
                <option value="rejected">{t('common.delete')}</option>
              </select>
            </label>
            <button
              onClick={() => navigate(`/interviews/new?appId=${appId}`)}
              className="w-full py-3.5 rounded-2xl bg-violet-50 dark:bg-violet-500/10 hover:bg-violet-100 dark:hover:bg-violet-500/20 text-violet-700 dark:text-violet-300 text-base font-bold transition-colors inline-flex items-center justify-center gap-2"
            >
              <Calendar className="h-4.5 w-4.5" /> {t('cprofile.scheduleInterview')}
            </button>
            <button
              onClick={() => {
                if (candidate.cv_url) {
                  window.open(candidate.cv_url, '_blank', 'noopener');
                } else {
                  customToast({ type: 'warning', title: 'No CV', message: 'No CV document is available for this candidate.' });
                }
              }}
              className="w-full py-3.5 rounded-2xl bg-gray-50 dark:bg-white/[0.04] hover:bg-gray-100 dark:hover:bg-white/[0.08] text-gray-700 dark:text-gray-300 text-base font-bold transition-colors inline-flex items-center justify-center gap-2"
            >
              <Download className="h-4.5 w-4.5" /> {t('common.export')} CV
            </button>
            <button
              onClick={() => handleMoveStage('rejected')}
              disabled={candidate.status === 'rejected'}
              className="w-full py-3.5 rounded-2xl bg-gray-50 dark:bg-white/[0.04] hover:bg-gray-100 dark:hover:bg-white/[0.08] text-gray-700 dark:text-gray-300 text-base font-bold transition-colors inline-flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <XCircle className="h-4.5 w-4.5 text-violet-500" /> {candidate.status === 'rejected' ? t('common.delete') : t('cprofile.reject')}
            </button>
            <button
              onClick={handleGenerateReport}
              className="w-full py-3.5 rounded-2xl bg-gray-50 dark:bg-white/[0.04] hover:bg-gray-100 dark:hover:bg-white/[0.08] text-gray-700 dark:text-gray-300 text-base font-bold transition-colors inline-flex items-center justify-center gap-2"
            >
              <FileText className="h-4.5 w-4.5" /> {t('recruiter.ghostReport.preview')}
            </button>
          </div>
        </div>
      </Card>

      {/* ===== Tabs + Content ===== */}
      <div className="rounded-xl border border-gray-100 dark:border-white/[0.06] bg-white dark:bg-[#1a1429] shadow-sm overflow-hidden h-fit">
        <div className="flex items-center gap-1 overflow-x-auto px-4 border-b border-gray-100 dark:border-white/[0.06] scrollbar-none">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'px-4 py-4 text-sm font-semibold whitespace-nowrap border-b-2 transition-colors',
                activeTab === tab.id
                  ? 'border-violet-600 text-violet-600 dark:border-violet-400 dark:text-violet-400'
                  : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
        {activeTab === 'overview' && (
          <motion.div
            key="overview"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="grid grid-cols-1 lg:grid-cols-[1fr_400px] gap-6 items-start p-7"
          >
            {/* LEFT column */}
            <div className="space-y-6">
              {/* Candidate Snapshot */}
              <Card className="p-7 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
                <h3 className="text-sm font-bold uppercase tracking-wider text-gray-900 dark:text-white mb-6">{t('cprofile.overview')}</h3>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-x-8 gap-y-7">
                  {[
                    { label: t('cprofile.experience'), value: candidate.years_experience ?? '--' },
                    { label: t('cprofile.contactInfo'), value: candidate.location ?? '--' },
                    { label: t('cprofile.salary'), value: candidate.salary_expectation ?? '--' },
                    { label: t('jobs.col.type'), value: candidate.work_type ?? '--' },
                    { label: t('cprofile.keyStrengths'), value: candidate.languages || '--' },
                    { label: t('cprofile.growthAreas'), value: candidate.relocation_willing ?? '--' },
                  ].map((item) => (
                    <div key={item.label}>
                      <div className="text-[11px] font-bold uppercase tracking-wider text-gray-400 mb-1.5">{item.label}</div>
                      <div className={cn('text-lg font-bold', item.value === '--' ? 'text-gray-300 dark:text-gray-600' : 'text-gray-900 dark:text-white')}>
                        {item.value}
                      </div>
                    </div>
                  ))}
                </div>
              </Card>

              {/* About */}
              <Card className="p-7 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
                <h3 className="text-sm font-bold uppercase tracking-wider text-gray-900 dark:text-white mb-4">{t('cprofile.about')}</h3>
                <p className="text-base text-gray-500 dark:text-gray-400">{candidate.bio || cAnalysis.summary || t('cprofile.noSummary')}</p>
              </Card>

              {/* Experience */}
              <Card className="p-7 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-bold uppercase tracking-wider text-gray-900 dark:text-white">{t('cprofile.experience')}</h3>
                  <span className="text-gray-300 dark:text-gray-600">{Array.isArray(cAnalysis.experience) ? `${cAnalysis.experience.length} ${t('appdetail.positions')}` : '--'}</span>
                </div>
                {Array.isArray(cAnalysis.experience) && cAnalysis.experience.length > 0 ? (
                  <div className="space-y-4">
                    {cAnalysis.experience.map((exp: any, i: number) => (
                      <div key={i} className="flex gap-4">
                        <div className="flex flex-col items-center">
                          <div className="h-2.5 w-2.5 rounded-full bg-violet-500 mt-1.5" />
                          {i < cAnalysis.experience.length - 1 && <div className="w-px flex-1 bg-gray-100 dark:bg-white/[0.06]" />}
                        </div>
                        <div className="pb-2">
                          <p className="text-sm font-bold text-gray-900 dark:text-white">{exp.role || exp.title || exp.position || t('appdetail.role')}</p>
                          <p className="text-xs text-gray-500">{exp.company || exp.organization || ''}</p>
                          <p className="text-xs text-gray-400 mt-0.5">{exp.duration || exp.period || ''}</p>
                          {exp.description && <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{exp.description}</p>}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-base italic text-gray-400">No experience data available</p>
                )}
              </Card>

              {/* Skills */}
              <Card className="p-7 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
                <h3 className="text-sm font-bold uppercase tracking-wider text-gray-900 dark:text-white mb-4">Skills & Competencies</h3>
                {cSkills.length === 0 ? (
                  <p className="text-base italic text-gray-400">No skills data</p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {cSkills.map((s) => (
                      <span key={s} className="px-3 py-1.5 rounded-xl bg-violet-50 dark:bg-violet-500/10 text-sm font-semibold text-violet-700 dark:text-violet-300">
                        {s}
                      </span>
                    ))}
                  </div>
                )}
              </Card>

              {/* Documents */}
              <Card className="p-7 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-bold uppercase tracking-wider text-gray-900 dark:text-white">Documents</h3>
                  <span className="text-sm text-gray-400">{candidate.cv_url ? '1 file' : '0 files'}</span>
                </div>
                {candidate.cv_url ? (
                  <button
                    onClick={() => window.open(candidate.cv_url, '_blank', 'noopener')}
                    className="w-full flex items-center gap-3 p-4 rounded-2xl border border-gray-100 dark:border-white/[0.06] hover:border-violet-300 transition-colors text-left"
                  >
                    <FileText className="h-5 w-5 text-violet-500 shrink-0" />
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-gray-900 dark:text-white truncate">Resume / CV</p>
                      <p className="text-xs text-gray-500">Click to open</p>
                    </div>
                  </button>
                ) : (
                  <div className="flex flex-col items-center justify-center py-8 text-center">
                    <FileText className="h-8 w-8 text-gray-200 dark:text-gray-700 mb-2" />
                    <p className="text-sm text-gray-400">No documents uploaded yet</p>
                  </div>
                )}
              </Card>
            </div>

            {/* RIGHT sidebar */}
            <div className="space-y-6 lg:sticky lg:top-20">
              {/* Interview Summary */}
              <Card className="p-6 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <MessageSquare className="h-4.5 w-4.5 text-violet-500" />
                    <h3 className="text-sm font-bold uppercase tracking-wider text-gray-900 dark:text-white">Interview Summary</h3>
                  </div>
                  <span className="px-3 py-1 rounded-full bg-violet-50 dark:bg-violet-500/10 text-[11px] font-bold text-violet-600 dark:text-violet-400">
                    AI Generated
                  </span>
                </div>
                {cScore > 0 || (candidate.total_questions ?? 0) > 0 ? (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-500 dark:text-gray-400">Overall Score</span>
                      <span className={cn('text-lg font-extrabold', cScore >= 80 ? 'text-emerald-500' : cScore >= 60 ? 'text-amber-500' : 'text-blue-500')}>{cScore}%</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-500 dark:text-gray-400">Questions Answered</span>
                      <span className="text-sm font-bold text-gray-900 dark:text-white">
                        {candidate.timeline?.completed_questions ?? 0}/{candidate.total_questions ?? 0}
                      </span>
                    </div>
                    {Array.isArray(candidate.competencies) || (candidate.competencies && typeof candidate.competencies === 'object' && Object.keys(candidate.competencies).length > 0) ? (
                      <div className="space-y-2 pt-1">
                        {Object.entries(candidate.competencies).slice(0, 4).map(([k, v]) => (
                          <div key={k} className="flex items-center justify-between text-sm">
                            <span className="text-gray-500 dark:text-gray-400 capitalize">{k.replace(/_/g, ' ')}</span>
                            <span className="font-semibold text-gray-700 dark:text-gray-300">{v as number}%</span>
                          </div>
                        ))}
                      </div>
                    ) : cAnalysis.summary ? (
                      <p className="text-sm text-gray-600 dark:text-gray-300">{cAnalysis.summary}</p>
                    ) : null}
                  </div>
                ) : (
                  <p className="text-sm italic text-gray-400">No interview data available yet.</p>
                )}
              </Card>
              <Card className="p-6 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
                <div className="flex items-center justify-between mb-5">
                  <div className="flex items-center gap-2">
                    <Shield className="h-4.5 w-4.5 text-violet-500" />
                    <h3 className="text-sm font-bold uppercase tracking-wider text-gray-900 dark:text-white">Interview Integrity</h3>
                  </div>
                  <span className={cn('px-3 py-1 rounded-full text-[11px] font-bold', (candidate.trust_score ?? 100) >= 80 ? 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400' : 'bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400')}>
                    {(candidate.trust_score ?? 100) >= 80 ? 'Verified' : 'Review'}
                  </span>
                </div>
                <div className="space-y-3.5">
                  <div className="flex items-center gap-2.5 text-sm font-semibold text-violet-600 dark:text-violet-400">
                    <CheckCircle2 className="h-4 w-4 shrink-0" /> Integrity Score: {candidate.trust_score ?? 100}/100
                  </div>
                  <div className="flex items-center gap-2.5 text-sm text-gray-500 dark:text-gray-400">
                    <Monitor className="h-4 w-4 text-gray-400 shrink-0" /> {candidate.tab_switches ?? 0} tab switch{(candidate.tab_switches ?? 0) === 1 ? '' : 'es'} detected
                  </div>
                  <div className="flex items-center gap-2.5 text-sm text-gray-500 dark:text-gray-400">
                    <User className="h-4 w-4 text-gray-400 shrink-0" /> {candidate.identity_verified ? 'Identity verified' : 'Identity not verified'}
                  </div>
                  {Array.isArray(candidate.proctoring_violations) && candidate.proctoring_violations.length > 0 && (
                    <div className="flex items-center gap-2.5 text-sm text-amber-600 dark:text-amber-400">
                      <Wifi className="h-4 w-4 shrink-0" /> {candidate.proctoring_violations.length} proctoring violation{(candidate.proctoring_violations.length || 0) === 1 ? '' : 's'}
                    </div>
                  )}
                </div>
              </Card>

              {/* Team Collaboration */}
              <Card className="p-6 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
                <div className="flex items-center gap-2 mb-5">
                  <Users className="h-4.5 w-4.5 text-violet-500" />
                  <h3 className="text-sm font-bold uppercase tracking-wider text-gray-900 dark:text-white">Recruiter Notes</h3>
                </div>

                {note ? (
                  <p className="text-sm text-gray-600 dark:text-gray-300 mb-4 p-3 rounded-xl bg-gray-50 dark:bg-white/[0.03] whitespace-pre-wrap">{note}</p>
                ) : (
                  <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-6">
                    No notes yet. Start the discussion!
                  </p>
                )}

                <div className="flex items-center gap-2 mt-2">
                  <input
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSendComment()}
                    placeholder="Add a note..."
                    className="flex-1 h-12 px-4 rounded-xl bg-gray-50 dark:bg-white/[0.04] border border-gray-100 dark:border-white/[0.06] text-sm text-gray-900 dark:text-white placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-violet-500/20 focus:border-violet-400 transition-all"
                  />
                  <button
                    onClick={handleSendComment}
                    className="h-12 px-5 rounded-xl bg-violet-600 hover:bg-violet-700 text-white text-sm font-bold inline-flex items-center gap-1.5 shadow-md shadow-violet-500/25 transition-colors shrink-0"
                  >
                    <Send className="h-4 w-4" /> Save
                  </button>
                </div>
              </Card>

              {/* Quick Actions */}
              <Card className="p-6 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
                <h3 className="text-sm font-bold uppercase tracking-wider text-gray-900 dark:text-white mb-5">Quick Actions</h3>
                <div className="space-y-3">
                  <button
                    onClick={() => navigate('/messages')}
                    className="w-full py-3.5 rounded-2xl bg-violet-600 hover:bg-violet-700 text-white text-base font-bold shadow-md shadow-violet-500/25 transition-colors inline-flex items-center justify-center gap-2"
                  >
                    <MessageSquare className="h-4.5 w-4.5" /> Message Candidate
                  </button>
                  <button
                    onClick={handleAIInsights}
                    className="w-full py-3.5 rounded-2xl bg-gray-50 dark:bg-white/[0.04] hover:bg-gray-100 dark:hover:bg-white/[0.08] text-gray-700 dark:text-gray-300 text-base font-bold transition-colors inline-flex items-center justify-center gap-2"
                  >
                    <Sparkles className="h-4.5 w-4.5 text-amber-500" /> AI Insights
                  </button>
                </div>
              </Card>
            </div>
          </motion.div>
        )}

        {activeTab === 'cv' && (
          <motion.div key="cv" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
            <div className="p-7">
              <CVEvaluation
                cvScore={candidate.cv_score ?? undefined}
                cvRubricWeighted={
                  typeof cAnalysis.cv_rubric_weighted === 'boolean'
                    ? cAnalysis.cv_rubric_weighted
                    : undefined
                }
                cvScoringMethod={cAnalysis.scoring_method}
                cvCoveragePct={cAnalysis.coverage_pct}
                cvSkillBreakdown={Object.entries(cAnalysis.skill_scores || {}).map(([name, details]: any) => ({
                  name,
                  score: details?.score ?? 0,
                  weight: details?.weight,
                  normalized_weight: details?.normalized_weight,
                  level: details?.level,
                  feedback: details?.feedback,
                  category: details?.category,
                }))}
                cvEvidence={Object.entries(cAnalysis.skill_scores || {}).map(([name, details]: any) => ({
                  skill_name: name,
                  score: details?.score ?? 0,
                  weight: details?.normalized_weight,
                  feedback: details?.feedback,
                }))}
                cvMissingSkills={cAnalysis.missing_skills}
              />
            </div>
          </motion.div>
        )}

        {activeTab === 'timeline' && (
          <motion.div key="timeline" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
            <div className="p-7">
              <h3 className="text-sm font-bold uppercase tracking-wider text-gray-900 dark:text-white mb-6">Activity Timeline</h3>
              <ActivityTimeline candidate={candidate} />
            </div>
          </motion.div>
        )}

        {activeTab === 'notes' && (
          <motion.div key="notes" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
            <div className="p-7">
              <h3 className="text-sm font-bold uppercase tracking-wider text-gray-900 dark:text-white mb-4">Recruiter Notes</h3>
              {loadingNotes ? (
                <div className="flex items-center justify-center py-8"><Loader2 className="h-6 w-6 animate-spin text-violet-600" /></div>
              ) : (
                <div className="space-y-4">
                  <textarea
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    placeholder="Add notes about this candidate..."
                    className="w-full h-40 px-4 py-3 rounded-xl bg-gray-50 dark:bg-white/[0.04] border border-gray-100 dark:border-white/[0.06] text-sm text-gray-900 dark:text-white placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-violet-500/20 focus:border-violet-400 transition-all resize-y"
                  />
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-400">{note.length}/5000</span>
                    <button
                      onClick={handleSendComment}
                      className="px-6 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-700 text-white text-sm font-bold shadow-md shadow-violet-500/25 transition-colors"
                    >
                      Save Notes
                    </button>
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}

        {activeTab === 'interviews' && (
          <motion.div
            key="interviews"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <div className="p-6">
              <div className="flex items-center justify-between mb-5">
                <h3 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2">
                  <Calendar className="h-4.5 w-4.5 text-violet-500" />
                  Scheduled Interviews ({scheduledInterviews.length})
                </h3>
                <button
onClick={() => navigate(`/interviews/new?appId=${appId}`)}
                  className="px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-700 text-white text-sm font-bold shadow-md shadow-violet-500/25 transition-colors inline-flex items-center gap-2"
                >
                  <Calendar className="h-4 w-4" /> Schedule
                </button>
              </div>

              {scheduledInterviews.length === 0 ? (
                <div className="text-center py-10">
                  <Calendar className="h-10 w-10 text-gray-200 dark:text-gray-700 mx-auto mb-3" />
                  <p className="text-sm text-gray-500">No interviews have been scheduled for this candidate yet.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {scheduledInterviews.map((iv: any) => {
                    const ivStatus = iv.status || 'scheduled';
                    const statusCls =
                      ivStatus === 'cancelled'
                        ? 'bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400'
                        : ivStatus === 'completed'
                        ? 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                        : ivStatus === 'no_show'
                        ? 'bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400'
                        : 'bg-violet-50 dark:bg-violet-500/10 text-violet-600 dark:text-violet-400';
                    return (
                      <button
                        key={iv.id}
                        onClick={() => navigate(`/interviews/${iv.id}`)}
                        className="w-full border border-gray-100 dark:border-white/[0.06] rounded-2xl p-4 flex items-center gap-4 hover:bg-gray-50 dark:hover:bg-white/[0.02] transition-colors text-left"
                      >
                        <div className="h-11 w-11 rounded-xl bg-violet-100 dark:bg-violet-500/15 flex items-center justify-center text-violet-600 dark:text-violet-400 shrink-0">
                          {iv.type ? iv.type[0].toUpperCase() : 'I'}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-base font-bold text-gray-900 dark:text-white capitalize">{iv.type || 'Interview'}</div>
                          <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400 mt-0.5 flex-wrap">
                            <span className="inline-flex items-center gap-1">
                              <Calendar className="h-3 w-3" />
                              {iv.scheduled_time ? new Date(iv.scheduled_time).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : 'N/A'}
                            </span>
                            <span>|</span>
                            <span className="inline-flex items-center gap-1">
                              <Clock className="h-3 w-3" /> {iv.duration_minutes || 60} min
                            </span>
                            {iv.meeting_link && (
                              <>
                                <span>|</span>
                                <span className="inline-flex items-center gap-1">
                                  <Video className="h-3 w-3" /> Virtual
                                </span>
                              </>
                            )}
                          </div>
                        </div>
                        <span className={`px-3 py-1 rounded-lg text-[11px] font-bold capitalize shrink-0 ${statusCls}`}>
                          {ivStatus}
                        </span>
                        <ChevronRight className="h-4 w-4 text-gray-400 shrink-0" />
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </motion.div>
        )}

        {activeTab !== 'overview' && activeTab !== 'interviews' && activeTab !== 'timeline' && activeTab !== 'notes' && activeTab !== 'cv' && (
          <motion.div key={activeTab} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
            <div className="p-10">
              <div className="flex flex-col items-center text-center py-10 space-y-3">
                <FileText className="h-10 w-10 text-gray-200 dark:text-gray-700" />
                <h3 className="text-lg font-bold text-gray-900 dark:text-white">
                  {TABS.find((t) => t.id === activeTab)?.label}
                </h3>
                <p className="text-sm text-gray-400">No data available yet for this candidate.</p>
              </div>
            </div>
          </motion.div>
        )}
    </div>
    </div>
  );
}

function ActivityTimeline({ candidate }: { candidate: any }) {
  const events: { date?: string; label: string; detail: string; icon: string }[] = [];

  if (candidate.created_at) {
    events.push({
      date: candidate.created_at,
      label: 'Application submitted',
      detail: 'Candidate applied to this position.',
      icon: '📥',
    });
  }
  if (candidate.analyzed_at) {
    events.push({
      date: candidate.analyzed_at,
      label: 'CV analyzed',
      detail: 'Intelligence Engine processed the CV and produced a score.',
      icon: '🧠',
    });
  }
  if (candidate.interview_scheduled_at) {
    events.push({
      date: candidate.interview_scheduled_at,
      label: 'Interview scheduled',
      detail: 'An interview session was scheduled for this candidate.',
      icon: '📅',
    });
  }
  const totalQ = candidate.total_questions ?? candidate.timeline?.total_questions ?? 0;
  const doneQ = candidate.timeline?.completed_questions ?? 0;
  if (totalQ > 0 || doneQ > 0) {
    events.push({
      date: candidate.interview_last_saved || candidate.status_changed_at || undefined,
      label: `Interview in progress`,
      detail: `${doneQ}/${totalQ} questions answered so far.`,
      icon: '🎤',
    });
  }
  if (candidate.feedback_submitted_at) {
    events.push({
      date: candidate.feedback_submitted_at,
      label: 'Interview feedback submitted',
      detail: 'Interviewer feedback was recorded for this candidate.',
      icon: '📝',
    });
  }
  if (candidate.status_changed_at) {
    events.push({
      date: candidate.status_changed_at,
      label: `Status changed to "${candidate.status}"`,
      detail: 'The application stage was updated.',
      icon: '🔄',
    });
  }
  if (candidate.offer_sent_at) {
    events.push({
      date: candidate.offer_sent_at,
      label: 'Offer sent',
      detail: 'An offer was sent to the candidate.',
      icon: '✉️',
    });
  }
  const subs = Array.isArray(candidate.scorecard_submissions) ? candidate.scorecard_submissions : [];
  subs.forEach((s: any) => {
    events.push({
      date: s.submitted_at,
      label: `Scorecard submitted (${s.overall_score ?? '--'}/100)`,
      detail: `${s.scorecard_name || 'Scorecard'} — ${s.recommendation || 'recommendation'}`,
      icon: '🏆',
    });
  });

  const sorted = events
    .filter((e) => e.date)
    .sort((a, b) => new Date(b.date as string).getTime() - new Date(a.date as string).getTime());

  if (sorted.length === 0) {
    return (
      <div className="text-center py-10">
        <p className="text-sm italic text-gray-400">No activity recorded yet for this candidate.</p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {sorted.map((e, i) => (
        <div key={i} className="flex gap-4">
          <div className="flex flex-col items-center">
            <div className="h-9 w-9 rounded-full bg-violet-50 dark:bg-violet-500/10 flex items-center justify-center text-base shrink-0">
              {e.icon}
            </div>
            {i < sorted.length - 1 && <div className="w-px flex-1 bg-gray-100 dark:bg-white/[0.06]" />}
          </div>
          <div className="pb-4">
            <p className="text-sm font-bold text-gray-900 dark:text-white">{e.label}</p>
            <p className="text-xs text-gray-400 mt-0.5">
              {e.date ? new Date(e.date).toLocaleString() : ''}
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{e.detail}</p>
          </div>
        </div>
      ))}
    </div>
  );
}