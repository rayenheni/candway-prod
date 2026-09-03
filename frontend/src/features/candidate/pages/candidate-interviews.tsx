import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router';
import { motion } from 'framer-motion';
import { Button } from '@/shared/components/ui/button';
import { Card } from '@/shared/components/ui/card';
import { Input } from '@/shared/components/ui/input';
import { SimpleDropdown } from '@/shared/components/ui/dropdown-menu';
import { customToast } from '@/shared/components/ui/toast';
import { candidateService } from '@/services/candidate.service';
import { aiInterviewService } from '@/services/ai-interview.service';
import { cn } from '@/utils/cn';
import { useLanguage } from '@/contexts/language-context';
import {
  Search, SlidersHorizontal, Play, ChevronRight, TrendingUp, Info, MoreHorizontal,
  Trash2, Share2, Download, Loader2, Zap, Pause, Clock, BarChart3, RotateCcw,
} from 'lucide-react';

type StatusKey = 'pending' | 'in_progress' | 'paused' | 'completed' | 'under_review' | 'expired' | 'rejected';

interface Interview {
  id: string;
  role: string;
  company: string;
  initial: string;
  color: string;
  status: StatusKey;
  progress: number;
  totalSteps: number;
  score: number | null;
  scoreLabel: string;
  ranking: { rank: number; total: number; percentile: number } | null;
  dueDate: string;
  dueTime: string;
  lastActivity: string;
  daysLeft: number | null;
}

const STATUS_UI: Record<string, { label: string; bg: string; text: string }> = {
  pending:      { label: 'Pending',         bg: 'bg-gray-100 dark:bg-white/10',       text: 'text-gray-600 dark:text-gray-300' },
  in_progress:  { label: 'In Progress',     bg: 'bg-amber-50 dark:bg-amber-500/10',  text: 'text-amber-700 dark:text-amber-400' },
  paused:       { label: 'Paused',          bg: 'bg-yellow-50 dark:bg-yellow-500/10', text: 'text-yellow-700 dark:text-yellow-400' },
  completed:    { label: 'Completed',       bg: 'bg-emerald-50 dark:bg-emerald-500/10', text: 'text-emerald-700 dark:text-emerald-400' },
  under_review: { label: 'Under Review',    bg: 'bg-blue-50 dark:bg-blue-500/10',     text: 'text-blue-700 dark:text-blue-400' },
  expired:      { label: 'Expired',         bg: 'bg-red-50 dark:bg-red-500/10',       text: 'text-red-700 dark:text-red-400' },
  rejected:     { label: 'Rejected',        bg: 'bg-red-50 dark:bg-red-500/10',       text: 'text-red-700 dark:text-red-400' },
};

const NORMALIZE_STATUS: Record<string, StatusKey> = {
  'in-progress': 'in_progress',
  'under-review': 'under_review',
  'in_progress': 'in_progress',
  'under_review': 'under_review',
};

const CARD_COLORS = [
  'bg-gradient-to-br from-indigo-500 to-violet-600',
  'bg-gradient-to-br from-blue-500 to-indigo-600',
  'bg-gradient-to-br from-emerald-500 to-teal-600',
  'bg-gradient-to-br from-rose-500 to-pink-600',
  'bg-gradient-to-br from-amber-500 to-orange-600',
  'bg-gradient-to-br from-cyan-500 to-sky-600',
];

function scoreColor(score: number | null) {
  if (score === null) return 'text-gray-400';
  if (score >= 85) return 'text-emerald-600 dark:text-emerald-400';
  if (score >= 70) return 'text-violet-600 dark:text-violet-400';
  if (score >= 50) return 'text-amber-600 dark:text-amber-400';
  return 'text-red-600 dark:text-red-400';
}

function scoreLabelFor(score: number) {
  if (score >= 85) return 'EXCELLENT';
  if (score >= 70) return 'GOOD';
  if (score >= 50) return 'FAIR';
  return 'NEEDS WORK';
}

const TABS: { key: 'all' | StatusKey; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'pending', label: 'Pending' },
  { key: 'in_progress', label: 'In Progress' },
  { key: 'paused', label: 'Paused' },
  { key: 'completed', label: 'Completed' },
  { key: 'under_review', label: 'Under Review' },
  { key: 'expired', label: 'Expired' },
];

function statusSortWeight(s: StatusKey): number {
  const order: Record<string, number> = { in_progress: 0, paused: 1, pending: 2, under_review: 3, completed: 4, expired: 5, rejected: 6 };
  return order[s] ?? 99;
}

export default function CandidateInterviewsPage() {
  const navigate = useNavigate();
  const { t } = useLanguage();
  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'all' | StatusKey>('all');
  const [search, setSearch] = useState('');

  const loadInterviews = () => {
    setLoading(true);
    candidateService.getInterviewHistory()
      .then(res => {
        const data = Array.isArray(res) ? res : [];
        setInterviews(data.map((item: any, i: number) => {
          const rawStatus = (item.status ?? 'completed').toLowerCase().replace(/-/g, '_');
          const status = (NORMALIZE_STATUS[rawStatus] || rawStatus) as StatusKey;
          return {
            id: String(item.id ?? item.application_id ?? i),
            role: item.role ?? item.job_title ?? t('cand.interviews.generalAssessment'),
            company: item.company ?? item.company_name ?? 'Candway',
            initial: (item.company ?? 'C')[0],
            color: item.color ?? CARD_COLORS[i % CARD_COLORS.length],
            status,
            progress: item.progress ?? item.questions_answered ?? 0,
            totalSteps: item.total_questions ?? item.total ?? 15,
            // CANONICAL POST-INTERVIEW SCORE
            score: item.final_score ?? item.score ?? item.overall_score ?? null,
            scoreLabel: scoreLabelFor(
              item.final_score ?? item.score ?? item.overall_score ?? 0
            ),
            ranking: item.ranking ?? null,
            dueDate: item.date ? new Date(item.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—',
            dueTime: item.date ? new Date(item.date).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }) : '—',
            lastActivity: item.last_activity ? new Date(item.last_activity).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : (item.date ? new Date(item.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—'),
            daysLeft: item.days_remaining ?? item.days_left ?? null,
          };
        }));
      })
      .catch(() => setInterviews([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadInterviews(); }, []);

  const stats = useMemo(() => {
    const total = interviews.length;
    const inProgress = interviews.filter(i => i.status === 'in_progress' || i.status === 'paused').length;
    const completed = interviews.filter(i => i.status === 'completed' || i.status === 'under_review').length;
    const scores = interviews.filter(i => i.score !== null).map(i => i.score!);
    const avgScore = scores.length ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : 0;
    return { total, inProgress, completed, avgScore };
  }, [interviews]);

  const inProgress = useMemo(() => {
    const ip = interviews.filter(i => i.status === 'in_progress' || i.status === 'paused');
    return ip.sort((a, b) => (a.status === 'in_progress' ? 0 : 1) - (b.status === 'in_progress' ? 0 : 1))[0] ?? null;
  }, [interviews]);

  const filtered = useMemo(() => {
    let list = activeTab === 'all' ? [...interviews] : interviews.filter((i) => i.status === activeTab);
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter((i) => i.role.toLowerCase().includes(q) || i.company.toLowerCase().includes(q));
    }
    list.sort((a, b) => statusSortWeight(a.status) - statusSortWeight(b.status));
    return list;
  }, [interviews, activeTab, search]);

  const handleStartInterview = (interview: Interview) => {
    navigate(`/interviews/room/${interview.id}`);
  };

  const handleResume = async (interview: Interview) => {
    try {
      const res = await aiInterviewService.resumeInterview({ application_id: parseInt(interview.id) });
      if (res.can_resume) {
        navigate(`/interviews/room/${interview.id}?resume=true&step=${res.progress}`);
      } else {
        customToast({ type: 'warning', title: t('cand.interviews.cannotResume'), message: res.reason ?? t('cand.interviews.cannotResumeMsg') });
      }
    } catch {
      customToast({ type: 'error', title: t('cand.interviews.error'), message: t('cand.interviews.resumeFailedMsg') });
    }
  };

  const handlePause = async (interview: Interview) => {
    try {
      await aiInterviewService.pauseInterview({ application_id: parseInt(interview.id) });
      customToast({ type: 'success', title: t('cand.interviews.paused'), message: t('cand.interviews.pausedMsg') });
      loadInterviews();
    } catch {
      customToast({ type: 'error', title: t('cand.interviews.error'), message: t('cand.interviews.pauseFailedMsg') });
    }
  };

  const handleAnalyse = (interview: Interview) => {
    navigate(`/interviews/${interview.id}/analysis`);
  };

  const handleDownload = async (interview: Interview) => {
    try {
      const blob = await candidateService.downloadInterviewReport(interview.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `interview-report-${interview.id}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      customToast({ type: 'success', title: t('cand.interviews.reportDownloaded'), message: t('cand.interviews.reportDownloadedMsg') });
    } catch {
      customToast({ type: 'error', title: t('cand.interviews.downloadFailed'), message: t('cand.interviews.downloadFailedMsg') });
    }
  };

  const handleShare = (interview: Interview) => {
    const url = `${window.location.origin}/interviews/${interview.id}/analysis`;
    navigator.clipboard?.writeText(url).then(
      () => customToast({ type: 'success', title: t('toast.linkCopied'), message: t('toast.linkCopiedMsg') }),
      () => customToast({ type: 'error', title: t('cand.interviews.copyFailed'), message: t('cand.interviews.copyFailedMsg') }),
    );
  };

  const handleDelete = async (interview: Interview) => {
    try {
      await candidateService.resetInterview(interview.id);
      customToast({ type: 'success', title: t('cand.interviews.removed'), message: t('cand.interviews.removedMsg') });
      loadInterviews();
    } catch {
      customToast({ type: 'error', title: t('cand.interviews.error'), message: t('cand.interviews.deleteFailedMsg') });
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 text-violet-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-gray-900 dark:text-white tracking-tight">
            {t('iv.title')}
          </h1>
          <p className="mt-2 text-sm sm:text-base text-gray-500 dark:text-gray-400">
            {t('iv.subtitle')}
          </p>
        </div>
      </div>

      {/* Stats Cards */}
      {interviews.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: t('apps.total'), value: stats.total, color: 'text-violet-600 dark:text-violet-400', bg: 'bg-violet-50 dark:bg-violet-500/10', icon: BarChart3 },
            { label: t('iv.tab.inProgress'), value: stats.inProgress, color: 'text-amber-600 dark:text-amber-400', bg: 'bg-amber-50 dark:bg-amber-500/10', icon: Clock },
            { label: t('iv.tab.completed'), value: stats.completed, color: 'text-emerald-600 dark:text-emerald-400', bg: 'bg-emerald-50 dark:bg-emerald-500/10', icon: TrendingUp },
            { label: t('cand.interviews.avgScore'), value: stats.total > 0 ? `${stats.avgScore}` : '—', color: scoreColor(stats.avgScore), bg: 'bg-gray-50 dark:bg-white/5', icon: BarChart3 },
          ].map((s, i) => (
            <motion.div key={s.label} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
              <Card className="p-4 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
                <div className="flex items-center gap-3">
                  <div className={cn('h-10 w-10 rounded-xl flex items-center justify-center shrink-0', s.bg)}>
                    <s.icon className={cn('h-5 w-5', s.color)} />
                  </div>
                  <div>
                    <div className={cn('text-2xl font-extrabold', s.color)}>{s.value}</div>
                    <div className="text-[11px] font-bold text-gray-400 uppercase tracking-wider">{s.label}</div>
                  </div>
                </div>
              </Card>
            </motion.div>
          ))}
        </div>
      )}

      {/* Tabs & Search */}
      <div className="flex flex-col lg:flex-row lg:items-center gap-3">
        <div className="flex flex-wrap items-center gap-2">
          {TABS.map((tab) => {
            const isActive = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={cn(
                  'px-4 py-2 rounded-full text-sm font-semibold transition-all whitespace-nowrap',
                  isActive
                    ? 'bg-violet-600 text-white shadow-md shadow-violet-500/25'
                    : 'bg-white dark:bg-white/[0.04] text-gray-600 dark:text-gray-300 border border-gray-200 dark:border-white/10 hover:border-violet-300 dark:hover:border-violet-500/30'
                )}
              >
                {tab.label}
              </button>
            );
          })}
        </div>
        <div className="flex items-center gap-2 lg:ml-auto w-full lg:w-auto">
          <Input
            placeholder={t('iv.searchPlaceholder')}
            leftIcon={<Search className="h-4 w-4" />}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            wrapperClassName="flex-1 lg:w-72"
          />
          <button
            onClick={() => { const el = document.querySelector<HTMLInputElement>(`input[placeholder="${t('iv.searchPlaceholder')}"]`); el?.focus(); }}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full text-sm font-semibold bg-white dark:bg-white/[0.04] text-gray-600 dark:text-gray-300 border border-gray-200 dark:border-white/10 hover:border-violet-300 dark:hover:border-violet-500/30 transition-all shrink-0"
          >
            <SlidersHorizontal className="h-3.5 w-3.5" />
            {t('common.search')}
          </button>
        </div>
      </div>

      {/* In-Progress / Paused Banner */}
      {inProgress && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <Card className={cn(
            'p-5 border-0 shadow-sm',
            inProgress.status === 'paused'
              ? 'bg-gradient-to-r from-yellow-50 via-amber-50/60 to-white dark:from-yellow-500/10 dark:via-amber-500/5 dark:to-transparent'
              : 'bg-gradient-to-r from-violet-50 via-purple-50/60 to-white dark:from-violet-500/10 dark:via-purple-500/5 dark:to-transparent'
          )}>
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-center gap-4">
                <button
                  onClick={() => handleResume(inProgress)}
                  className="h-14 w-14 shrink-0 rounded-full bg-white dark:bg-white/10 border-2 border-violet-200 dark:border-violet-500/30 flex items-center justify-center shadow-sm hover:scale-105 transition-transform"
                >
                  {inProgress.status === 'paused' ? (
                    <RotateCcw className="h-5 w-5 text-yellow-600 dark:text-yellow-400" />
                  ) : (
                    <Play className="h-5 w-5 text-violet-600 dark:text-violet-400 fill-violet-600 dark:fill-violet-400 ml-0.5" />
                  )}
                </button>
                <div>
                  <h3 className="text-base font-bold text-gray-900 dark:text-white">
                    {inProgress.status === 'paused' ? t('cand.interviews.pausedTitle') : `${t('iv.continueTitle')} ${inProgress.role} ${t('iv.continueSuffix')}`}
                  </h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                    {inProgress.status === 'paused'
                      ? t('cand.interviews.pausedBody')
                      : t('iv.resumeMsg')}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {inProgress.status === 'in_progress' && (
                  <button
                    onClick={() => handlePause(inProgress)}
                    className="inline-flex items-center gap-1 text-sm font-bold text-amber-600 dark:text-amber-400 hover:text-amber-700 shrink-0 px-4 py-2 rounded-full bg-white dark:bg-white/10 shadow-sm hover:shadow-md transition-all"
                  >
                    <Pause className="h-4 w-4" />
                    {t('cand.interviews.pause')}
                  </button>
                )}
                <button
                  onClick={() => handleResume(inProgress)}
                  className="inline-flex items-center gap-1 text-sm font-bold text-violet-600 dark:text-violet-400 hover:text-violet-700 shrink-0 px-4 py-2 rounded-full bg-white dark:bg-white/10 shadow-sm hover:shadow-md transition-all"
                >
                  {t('iv.resumeBtn')}
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          </Card>
        </motion.div>
      )}

      {/* Table Card */}
      <Card className="p-0 border-0 shadow-sm bg-white dark:bg-white/[0.03] overflow-hidden">
        {interviews.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="h-16 w-16 rounded-2xl bg-violet-50 dark:bg-violet-500/10 flex items-center justify-center mb-4">
              <Zap className="h-8 w-8 text-violet-500" />
            </div>
            <p className="text-base font-bold text-gray-900 dark:text-white">{t('cand.interviews.noInterviews')}</p>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 mb-6 max-w-md">
              {t('cand.interviews.noInterviewsDesc')}
            </p>
            <div className="flex items-center gap-3">
              <Button variant="outline" size="sm" onClick={() => navigate('/jobs')} leftIcon={<Search className="h-4 w-4" />}>
                {t('cand.interviews.browseJobs')}
              </Button>
            </div>
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <Info className="h-10 w-10 text-gray-300 dark:text-gray-600 mb-3" />
            <p className="text-sm font-semibold text-gray-500 dark:text-gray-400">{t('cand.interviews.noMatch')}</p>
            <p className="text-xs text-gray-400 mt-1">{t('cand.interviews.noMatchDesc')}</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-100 dark:border-white/[0.06]">
                  <th className="text-left px-6 py-3 text-[11px] font-bold text-gray-400 uppercase tracking-wider">{t('iv.col.role')}</th>
                  <th className="text-left px-4 py-3 text-[11px] font-bold text-gray-400 uppercase tracking-wider">{t('iv.col.status')}</th>
                  <th className="text-left px-4 py-3 text-[11px] font-bold text-gray-400 uppercase tracking-wider">{t('iv.col.progress')}</th>
                  <th className="text-left px-4 py-3 text-[11px] font-bold text-gray-400 uppercase tracking-wider">{t('iv.col.score')}</th>
                  <th className="text-left px-4 py-3 text-[11px] font-bold text-gray-400 uppercase tracking-wider">{t('iv.col.due')}</th>
                  <th className="text-left px-4 py-3 text-[11px] font-bold text-gray-400 uppercase tracking-wider">{t('iv.col.activity')}</th>
                  <th className="text-right px-6 py-3 text-[11px] font-bold text-gray-400 uppercase tracking-wider">{t('iv.col.actions')}</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((iv, i) => {
                  const status = STATUS_UI[iv.status] ?? { label: iv.status, bg: 'bg-gray-100 dark:bg-white/10', text: 'text-gray-600 dark:text-gray-300' };
                  const progressPct = iv.totalSteps > 0 ? (iv.progress / iv.totalSteps) * 100 : 0;
                  const progressColor = iv.status === 'expired' || iv.status === 'rejected' ? 'bg-red-500'
                    : iv.status === 'completed' || iv.status === 'under_review' ? 'bg-emerald-500'
                    : iv.status === 'paused' ? 'bg-yellow-500'
                    : iv.status === 'pending' ? 'bg-gray-400'
                    : 'bg-violet-500';
                  const showAnalyse = iv.status === 'completed' || iv.status === 'under_review';
                  const showResume = iv.status === 'in_progress' || iv.status === 'paused';
                  const showStart = iv.status === 'pending';
                  const showDetails = iv.status === 'expired' || iv.status === 'rejected';
                  return (
                    <motion.tr
                      key={iv.id}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ duration: 0.2, delay: i * 0.02 }}
                      className="border-b border-gray-50 dark:border-white/[0.03] hover:bg-gray-50/60 dark:hover:bg-white/[0.02] transition-colors"
                    >
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <div className={cn('h-10 w-10 rounded-xl flex items-center justify-center text-white font-bold text-sm shrink-0', iv.color)}>
                            {iv.initial}
                          </div>
                          <div>
                            <div className="text-sm font-bold text-gray-900 dark:text-white">{iv.role}</div>
                            <div className="text-xs text-gray-500 dark:text-gray-400">{iv.company}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-4">
                        <div className="space-y-1">
                          <span className={cn('inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-bold', status.bg, status.text)}>
                            {status.label}
                          </span>
                          {iv.daysLeft !== null && iv.daysLeft > 0 && (iv.status === 'in_progress' || iv.status === 'paused' || iv.status === 'pending') && (
                            <div className="text-[11px] text-amber-600 dark:text-amber-400 font-medium flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              {iv.daysLeft} {iv.daysLeft !== 1 ? t('iv.daysLeft') : t('cand.interviews.dayLeft')}
                            </div>
                          )}
                          {iv.daysLeft !== null && iv.daysLeft <= 0 && iv.status !== 'expired' && iv.status !== 'completed' && (
                            <div className="text-[11px] text-red-600 dark:text-red-400 font-medium flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              {t('cand.interviews.dueToday')}
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-4">
                        <div className="space-y-1.5 w-24">
                          <span className="text-sm font-semibold text-gray-700 dark:text-gray-300">{iv.progress} / {iv.totalSteps}</span>
                          <div className="h-1.5 rounded-full bg-gray-100 dark:bg-white/10 overflow-hidden">
                            <div className={cn('h-full rounded-full transition-all duration-500', progressColor)} style={{ width: `${Math.max(progressPct, 3)}%` }} />
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-4">
                        {iv.score !== null ? (
                          <div>
                            <div className={cn('text-lg font-extrabold', scoreColor(iv.score))}>{iv.score}</div>
                            <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400">{iv.scoreLabel}</div>
                            {iv.ranking && (
                              <div className="mt-1 inline-flex items-center gap-1 rounded-full bg-emerald-50 dark:bg-emerald-500/10 px-2 py-0.5 text-[10px] font-bold text-emerald-600 dark:text-emerald-400">
                                <TrendingUp className="h-3 w-3" />
                                #{iv.ranking.rank}/{iv.ranking.total}
                              </div>
                            )}
                          </div>
                        ) : (
                          <span className="text-sm text-gray-400">—</span>
                        )}
                      </td>
                      <td className="px-4 py-4 text-sm text-gray-600 dark:text-gray-300">
                        <div>{iv.dueDate}</div>
                        <div className="text-xs text-gray-400">{iv.dueTime}</div>
                      </td>
                      <td className="px-4 py-4 text-sm text-gray-600 dark:text-gray-300">
                        <div>{iv.lastActivity}</div>
                        <div className="text-xs text-gray-400">{t('iv.activityDetected')}</div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center justify-end gap-2">
                          {showAnalyse && (
                            <button
                              onClick={() => handleAnalyse(iv)}
                              className="inline-flex items-center gap-1 text-xs font-bold text-violet-600 dark:text-violet-400 hover:text-violet-700 px-2.5 py-1.5 rounded-lg hover:bg-violet-50 dark:hover:bg-violet-500/10 transition-colors"
                            >
                              <TrendingUp className="h-3.5 w-3.5" /> {t('iv.analyse')}
                            </button>
                          )}
                          {showResume && (
                            <button
                              onClick={() => handleResume(iv)}
                              className="inline-flex items-center gap-1 text-xs font-bold text-emerald-600 dark:text-emerald-400 hover:text-emerald-700 px-2.5 py-1.5 rounded-lg hover:bg-emerald-50 dark:hover:bg-emerald-500/10 transition-colors"
                            >
                              <Play className="h-3.5 w-3.5 fill-current" /> {t('iv.resume')}
                            </button>
                          )}
                          {showStart && (
                            <button
                              onClick={() => handleStartInterview(iv)}
                              className="inline-flex items-center gap-1 text-xs font-bold text-violet-600 dark:text-violet-400 hover:text-violet-700 px-2.5 py-1.5 rounded-lg hover:bg-violet-50 dark:hover:bg-violet-500/10 transition-colors"
                            >
                              <Zap className="h-3.5 w-3.5" /> {t('cand.interviews.start')}
                            </button>
                          )}
                          {showDetails && (
                            <button
                              onClick={() => handleAnalyse(iv)}
                              className="inline-flex items-center gap-1 text-xs font-bold text-gray-500 dark:text-gray-400 hover:text-gray-700 px-2.5 py-1.5 rounded-lg hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
                            >
                              <Info className="h-3.5 w-3.5" /> {t('iv.details')}
                            </button>
                          )}
                          <SimpleDropdown
                            trigger={
                              <button className="h-7 w-7 flex items-center justify-center rounded-lg text-gray-400 hover:bg-gray-100 dark:hover:bg-white/10 transition-colors">
                                <MoreHorizontal className="h-4 w-4" />
                              </button>
                            }
                            items={[
                              ...(showResume ? [{
                                label: t('cand.interviews.pauseInterview'),
                                icon: <Pause className="h-4 w-4 text-amber-500" />,
                                onClick: () => handlePause(iv),
                              }] : []),
                              { label: t('cand.interviews.viewAnalysis'), icon: <TrendingUp className="h-4 w-4 text-violet-500" />, onClick: () => handleAnalyse(iv) },
                              { label: t('ivan.downloadReport'), icon: <Download className="h-4 w-4 text-blue-500" />, onClick: () => handleDownload(iv) },
                              { label: t('ivan.shareResults'), icon: <Share2 className="h-4 w-4 text-emerald-500" />, onClick: () => handleShare(iv) },
                              { label: t('cand.interviews.deleteRecord'), icon: <Trash2 className="h-4 w-4" />, danger: true, onClick: () => handleDelete(iv) },
                            ]}
                            align="end"
                          />
                        </div>
                      </td>
                    </motion.tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Practice Banner */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
      >
        <Card className="p-5 border-0 shadow-sm bg-gradient-to-r from-violet-50 via-purple-50/60 to-white dark:from-violet-500/10 dark:via-purple-500/5 dark:to-transparent">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="h-12 w-12 shrink-0 rounded-xl bg-white dark:bg-white/10 flex items-center justify-center shadow-sm">
                <Info className="h-6 w-6 text-violet-600 dark:text-violet-400" />
              </div>
              <div>
                <h4 className="text-base font-bold text-gray-900 dark:text-white">{t('cand.interviews.noSelfServeTitle')}</h4>
                <p className="text-sm text-gray-500 dark:text-gray-400">{t('cand.interviews.noSelfServeDesc')}</p>
              </div>
            </div>
            <button
              onClick={() => navigate('/jobs')}
              className="inline-flex items-center gap-1 text-sm font-bold text-violet-600 dark:text-violet-400 hover:text-violet-700 shrink-0 px-4 py-2 rounded-full bg-white dark:bg-white/10 shadow-sm hover:shadow-md transition-all"
            >
              {t('cand.interviews.browseJobs')}
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </Card>
      </motion.div>
    </div>
  );
}
