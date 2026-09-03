// ============================================================
// Candidate Application Detail — Status + AI Interview Analysis
// ============================================================

import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router';
import { motion, AnimatePresence } from 'framer-motion';
import { Card } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { customToast } from '@/shared/components/ui/toast';
import { useLanguage } from '@/contexts/language-context';
import { candidateService } from '@/services/candidate.service';
import { cn } from '@/utils/cn';
import {
  ArrowLeft, Download, Clock, CheckCircle2, XCircle, RotateCcw,
  TrendingUp, TrendingDown, ChevronDown, ChevronRight, Loader2,
  FileText, BarChart3, Lightbulb, Target, Sparkles, Send,
  Search, Users,
} from 'lucide-react';

type Tab = 'overview' | 'questions' | 'feedback' | 'recommendations';

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: 'overview', label: 'Overview', icon: BarChart3 },
  { id: 'questions', label: 'Questions', icon: FileText },
  { id: 'feedback', label: 'Feedback', icon: Lightbulb },
  { id: 'recommendations', label: 'Recommendations', icon: Sparkles },
];

const STATUS_CONFIG: Record<string, { label: string; bg: string; text: string; dot: string; icon: React.ElementType }> = {
  applied:    { label: 'Applied',    bg: 'bg-amber-50 dark:bg-amber-500/10',   text: 'text-amber-700 dark:text-amber-400',   dot: 'bg-amber-500', icon: Send },
  in_review:  { label: 'In Review',  bg: 'bg-orange-50 dark:bg-orange-500/10', text: 'text-orange-700 dark:text-orange-400', dot: 'bg-orange-500', icon: Search },
  interview:  { label: 'Interview',  bg: 'bg-emerald-50 dark:bg-emerald-500/10', text: 'text-emerald-700 dark:text-emerald-400', dot: 'bg-emerald-500', icon: Users },
  offered:    { label: 'Offered',    bg: 'bg-violet-50 dark:bg-violet-500/10', text: 'text-violet-700 dark:text-violet-400', dot: 'bg-violet-500', icon: CheckCircle2 },
  rejected:   { label: 'Rejected',   bg: 'bg-red-50 dark:bg-red-500/10',       text: 'text-red-700 dark:text-red-400',       dot: 'bg-red-500', icon: XCircle },
  withdrawn:  { label: 'Withdrawn',  bg: 'bg-gray-100 dark:bg-white/10',       text: 'text-gray-600 dark:text-gray-400',     dot: 'bg-gray-400', icon: RotateCcw },
  offer_declined: { label: 'Offer Declined', bg: 'bg-rose-50 dark:bg-rose-500/10', text: 'text-rose-700 dark:text-rose-400', dot: 'bg-rose-500', icon: XCircle },
};

export default function CandidateApplicationDetailPage() {
  const { t } = useLanguage();
  const { id } = useParams();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [expandedQ, setExpandedQ] = useState<number | null>(null);

  const [appData, setAppData] = useState<any>(null);
  const [analysis, setAnalysis] = useState<any>(null);
  const [loadingApp, setLoadingApp] = useState(true);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);

  // Fetch application detail
  useEffect(() => {
    if (!id) return;
    setLoadingApp(true);
    candidateService.getApplicationDetail(id)
      .then((res) => setAppData(res))
      .catch(() => {
        customToast({ type: 'error', title: t('cand.appDetail.notFound'), message: t('cand.appDetail.notFoundMsg') });
        navigate('/applications');
      })
      .finally(() => setLoadingApp(false));
  }, [id, navigate]);

  // Fetch interview analysis when app has interview data
  useEffect(() => {
    if (!id || !appData) return;
    const hasInterview = appData.interview_state === 'completed' || appData.score != null;
    if (!hasInterview) return;
    setLoadingAnalysis(true);
    candidateService.getInterviewAnalysis(id)
      .then((res) => setAnalysis(res))
      .catch(() => {})
      .finally(() => setLoadingAnalysis(false));
  }, [id, appData]);

  if (loadingApp) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 text-violet-500 animate-spin" />
      </div>
    );
  }

  if (!appData) return null;

  const status = STATUS_CONFIG[appData.status] || STATUS_CONFIG.applied;
  const hasAnalysis = analysis != null;

  // CANONICAL SCORE CONTRACT:
  // interview analysis -> final_score
  // before interview   -> cv_score
  const overallScore = hasAnalysis
    ? ((analysis.final_score as number | undefined) ?? 0)
    : ((appData.cv_score as number | undefined) ?? 0);
  const scoreLabel = hasAnalysis
    ? (analysis.score_label || (overallScore >= 85 ? t('cand.interviewAnalysis.excellent') : overallScore >= 70 ? t('cand.interviewAnalysis.good') : overallScore >= 50 ? t('cand.interviewAnalysis.fair') : t('cand.interviewAnalysis.needsWork')))
    : (appData.status === 'interview' ? t('iv.tab.inProgress') : t('cand.appDetail.na'));

  const circumference = 2 * Math.PI * 70;
  const dash = (overallScore / 100) * circumference;

  const handleDownloadReport = async () => {
    try {
      const blob = await candidateService.downloadInterviewReport(id!);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `interview-report-${id}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      customToast({ type: 'error', title: t('cand.interviews.downloadFailed'), message: t('cand.appDetail.reportUnavailable') });
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Back nav */}
      <button
        onClick={() => navigate('/applications')}
        className="inline-flex items-center gap-2 text-base font-semibold text-violet-600 dark:text-violet-400 hover:text-violet-700 transition-colors"
      >
        <ArrowLeft className="h-5 w-5" />
        {t('cand.appDetail.backToApplications')}
      </button>

      {/* Header + Score */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-gray-900 dark:text-white tracking-tight">
            {t('cand.appDetail.title')}
          </h1>
          <p className="mt-2 text-sm sm:text-base text-gray-500 dark:text-gray-400">
            {appData.job_title} — {appData.company_name}
          </p>
        </div>
        {hasAnalysis && (
          <Button
            variant="outline"
            leftIcon={<Download className="h-4 w-4" />}
            onClick={handleDownloadReport}
            className="font-semibold shrink-0"
          >
            {t('ivan.downloadReport')}
          </Button>
        )}
      </div>

      {/* Status Card */}
      <Card className="p-6 md:p-7 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
        <div className="flex flex-col lg:flex-row lg:items-center gap-6">
          <div className="flex items-center gap-4 min-w-[240px]">
            <div className="h-14 w-14 rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-white text-xl font-bold shrink-0">
              {(appData.job_title || '?')[0]}
            </div>
            <div>
              <h2 className="text-xl font-extrabold text-gray-900 dark:text-white">{appData.job_title}</h2>
              <p className="text-sm text-gray-500 dark:text-gray-400">{appData.company_name}</p>
            </div>
          </div>

          <div className="flex flex-wrap items-start gap-8 flex-1">
            <div>
              <div className="text-[11px] font-bold uppercase tracking-wider text-gray-400 mb-1">{t('common.status')}</div>
              <span className={cn('inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold uppercase tracking-wide', status.bg, status.text)}>
                <span className={cn('h-1.5 w-1.5 rounded-full', status.dot)} />
                {status.label}
              </span>
            </div>
            <div>
              <div className="text-[11px] font-bold uppercase tracking-wider text-gray-400 mb-1">{t('apps.applied')}</div>
              <div className="text-base font-bold text-gray-900 dark:text-white">
                {appData.created_at ? new Date(appData.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : t('cand.appDetail.na')}
              </div>
            </div>
            <div>
              <div className="text-[11px] font-bold uppercase tracking-wider text-gray-400 mb-1">{t('cand.appDetail.interviewState')}</div>
              <div className="text-base font-bold text-gray-900 dark:text-white capitalize">
                {(appData.interview_state || 'not_started').replace('_', ' ')}
              </div>
            </div>
            {appData.declared_role && (
              <div>
                <div className="text-[11px] font-bold uppercase tracking-wider text-gray-400 mb-1">{t('cand.appDetail.role')}</div>
                <div className="text-base font-bold text-gray-900 dark:text-white">{appData.declared_role}</div>
              </div>
            )}
          </div>

          {/* Score circle */}
          {overallScore > 0 && (
            <div className="rounded-2xl bg-emerald-50/70 dark:bg-emerald-500/10 border border-emerald-100 dark:border-emerald-500/20 px-8 py-5 text-center shrink-0">
              <div className="text-[11px] font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-1">{t('cand.appDetail.score')}</div>
              <div className="text-4xl font-extrabold text-amber-500">{Math.round(overallScore)}</div>
              <div className="text-sm font-semibold text-amber-500">{scoreLabel}</div>
            </div>
          )}
        </div>
      </Card>

      {/* Loading analysis indicator */}
      {loadingAnalysis && (
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <Loader2 className="h-4 w-4 animate-spin" />
          {t('cand.appDetail.loadingAnalysis')}
        </div>
      )}

      {/* Tabs (only when analysis is available) */}
      {hasAnalysis && (
        <>
          <div className="border-b border-gray-200 dark:border-white/[0.08]">
            <div className="flex items-center gap-8 overflow-x-auto">
              {TABS.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    'inline-flex items-center gap-1.5 pb-3 text-base font-semibold whitespace-nowrap border-b-2 -mb-px transition-colors',
                    activeTab === tab.id
                      ? 'border-violet-600 text-violet-600 dark:border-violet-400 dark:text-violet-400'
                      : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
                  )}
                >
                  <tab.icon className="h-4 w-4" />
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {/* Tab content */}
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_400px] gap-6 items-start">
            <div className="space-y-6">
              <AnimatePresence mode="wait">
                {activeTab === 'overview' && (
                  <motion.div key="ov" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="space-y-6">
                    {/* Performance overview */}
                    {analysis.performance_overview?.length > 0 && (
                      <Card className="p-7 border border-violet-100 dark:border-violet-500/15 shadow-sm bg-white dark:bg-white/[0.03]">
                        <h3 className="text-xl font-extrabold text-gray-900 dark:text-white">{t('ivan.performance')}</h3>
                        <p className="text-sm text-gray-500 dark:text-gray-400 mt-2 mb-8">{t('ivan.perfSub')}</p>

                        <div className="flex justify-center mb-6">
                          <div className="relative h-48 w-48">
                            <svg className="h-48 w-48 -rotate-90" viewBox="0 0 160 160">
                              <circle cx="80" cy="80" r="70" fill="none" stroke="currentColor" strokeWidth="11" className="text-gray-100 dark:text-white/5" />
                              <motion.circle
                                cx="80" cy="80" r="70" fill="none" stroke="#F59E0B" strokeWidth="11"
                                strokeLinecap="round"
                                initial={{ strokeDasharray: `0 ${circumference}` }}
                                animate={{ strokeDasharray: `${dash} ${circumference - dash}` }}
                                transition={{ duration: 1, ease: 'easeOut' }}
                              />
                            </svg>
                            <div className="absolute inset-0 flex flex-col items-center justify-center">
                              <span className="text-4xl font-extrabold text-gray-900 dark:text-white">{Math.round(overallScore)}</span>
                              <span className="text-[11px] font-bold uppercase tracking-wider text-gray-400 mt-1">{t('cand.appDetail.overall')}</span>
                              <span className="text-sm font-semibold text-amber-500 mt-0.5">{scoreLabel}</span>
                            </div>
                          </div>
                        </div>

                        <div className="space-y-4">
                          {analysis.performance_overview.map((item: any, i: number) => (
                            <div key={i} className="flex items-center gap-4">
                              <span className="text-sm font-semibold text-gray-700 dark:text-gray-200 w-44 truncate">{item.label}</span>
                              <div className="flex-1 h-2.5 rounded-full bg-gray-100 dark:bg-white/5 overflow-hidden">
                                <motion.div
                                  className="h-full rounded-full bg-gradient-to-r from-amber-400 to-amber-500"
                                  initial={{ width: 0 }}
                                  animate={{ width: `${item.score}%` }}
                                  transition={{ duration: 0.8, delay: i * 0.1 }}
                                />
                              </div>
                              <span className="text-sm font-bold text-gray-900 dark:text-white w-10 text-right">{item.score}</span>
                            </div>
                          ))}
                        </div>
                      </Card>
                    )}

                    {/* Strengths & Weaknesses */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      {analysis.strengths?.length > 0 && (
                        <Card className="p-6 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
                          <div className="flex items-center gap-2 mb-4">
                            <TrendingUp className="h-5 w-5 text-emerald-500" />
                            <h3 className="text-base font-bold text-gray-900 dark:text-white">{t('ivan.strengths')}</h3>
                          </div>
                          <ul className="space-y-2">
                            {analysis.strengths.map((s: string, i: number) => (
                              <li key={i} className="flex items-start gap-2 text-sm text-gray-600 dark:text-gray-300">
                                <CheckCircle2 className="h-4 w-4 text-emerald-500 mt-0.5 shrink-0" />
                                {s}
                              </li>
                            ))}
                          </ul>
                        </Card>
                      )}
                      {analysis.weaknesses?.length > 0 && (
                        <Card className="p-6 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
                          <div className="flex items-center gap-2 mb-4">
                            <TrendingDown className="h-5 w-5 text-amber-500" />
                            <h3 className="text-base font-bold text-gray-900 dark:text-white">{t('ivan.areasImprove')}</h3>
                          </div>
                          <ul className="space-y-2">
                            {analysis.weaknesses.map((w: string, i: number) => (
                              <li key={i} className="flex items-start gap-2 text-sm text-gray-600 dark:text-gray-300">
                                <Target className="h-4 w-4 text-amber-500 mt-0.5 shrink-0" />
                                {w}
                              </li>
                            ))}
                          </ul>
                        </Card>
                      )}
                    </div>
                  </motion.div>
                )}

                {activeTab === 'questions' && (
                  <motion.div key="q" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="space-y-4">
                    {analysis.questions?.length > 0 ? analysis.questions.map((q: any, i: number) => (
                      <Card key={i} className="p-5 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
                        <button
                          onClick={() => setExpandedQ(expandedQ === i ? null : i)}
                          className="w-full flex items-start gap-3 text-left"
                        >
                          <div className={cn(
                            'h-8 w-8 rounded-lg flex items-center justify-center text-xs font-bold shrink-0',
                            q.score >= 80 ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400'
                              : q.score >= 60 ? 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-400'
                              : 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-400'
                          )}>
                            {q.score}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-bold text-gray-900 dark:text-white">{t('cand.appDetail.q')}{q.number}: {q.question}</div>
                            <div className="text-xs text-gray-400 mt-1">{q.type} · {q.difficulty} · {q.duration}</div>
                          </div>
                          {expandedQ === i ? <ChevronDown className="h-4 w-4 text-gray-400 mt-1 shrink-0" /> : <ChevronRight className="h-4 w-4 text-gray-400 mt-1 shrink-0" />}
                        </button>
                        <AnimatePresence>
                          {expandedQ === i && (
                            <motion.div
                              initial={{ height: 0, opacity: 0 }}
                              animate={{ height: 'auto', opacity: 1 }}
                              exit={{ height: 0, opacity: 0 }}
                              className="overflow-hidden"
                            >
                              <div className="mt-4 pt-4 border-t border-gray-100 dark:border-white/[0.06] space-y-3">
                                <div>
                                  <div className="text-[11px] font-bold uppercase tracking-wider text-gray-400 mb-1">{t('cand.interviewAnalysis.yourAnswer')}</div>
                                  <p className="text-sm text-gray-600 dark:text-gray-300 whitespace-pre-wrap">{q.answer || t('cand.appDetail.noAnswer')}</p>
                                </div>
                                {q.feedback && (
                                  <div>
                                    <div className="text-[11px] font-bold uppercase tracking-wider text-gray-400 mb-1">{t('ivan.aiFeedback')}</div>
                                    <p className="text-sm text-gray-600 dark:text-gray-300">{q.feedback}</p>
                                  </div>
                                )}
                              </div>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </Card>
                    )) : (
                      <Card className="p-10 text-center text-gray-400">
                        <FileText className="h-10 w-10 mx-auto mb-3 text-gray-300" />
                        <p className="text-sm font-semibold">{t('cand.appDetail.noQuestions')}</p>
                      </Card>
                    )}
                  </motion.div>
                )}

                {activeTab === 'feedback' && (
                  <motion.div key="fb" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="space-y-6">
                    {analysis.performance_overview?.length > 0 ? (
                      <Card className="p-7 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
                        <h3 className="text-xl font-extrabold text-gray-900 dark:text-white mb-6">{t('cand.appDetail.detailedFeedback')}</h3>
                        <div className="space-y-6">
                          {analysis.performance_overview.map((f: any, i: number) => (
                            <div key={i} className="space-y-2">
                              <div className="flex items-center justify-between">
                                <span className="text-sm font-bold text-gray-900 dark:text-white">{f.label}</span>
                                <span className="text-sm font-bold text-amber-500">{f.score}/100</span>
                              </div>
                              <div className="h-2 rounded-full bg-gray-100 dark:bg-white/5 overflow-hidden">
                                <div className="h-full rounded-full bg-gradient-to-r from-amber-400 to-amber-500" style={{ width: `${f.score}%` }} />
                              </div>
                              {f.label_score && (
                                <p className="text-xs font-semibold text-gray-400">{f.label_score}</p>
                              )}
                            </div>
                          ))}
                        </div>
                      </Card>
                    ) : (
                      <Card className="p-10 text-center text-gray-400">
                        <Lightbulb className="h-10 w-10 mx-auto mb-3 text-gray-300" />
                        <p className="text-sm font-semibold">{t('cand.appDetail.noFeedback')}</p>
                      </Card>
                    )}
                  </motion.div>
                )}

                {activeTab === 'recommendations' && (
                  <motion.div key="rec" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="space-y-6">
                    {analysis.recommendations?.length > 0 ? (
                      <Card className="p-7 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
                        <h3 className="text-xl font-extrabold text-gray-900 dark:text-white mb-6">{t('cand.appDetail.aiRecommendations')}</h3>
                        <div className="space-y-4">
                          {analysis.recommendations.map((r: any, i: number) => (
                            <div key={i} className="flex items-start gap-3 p-4 rounded-xl bg-violet-50/50 dark:bg-violet-500/5 border border-violet-100 dark:border-violet-500/10">
                              <Sparkles className="h-5 w-5 text-violet-500 mt-0.5 shrink-0" />
                              <div>
                                <div className="text-sm font-bold text-gray-900 dark:text-white">{r.title || r.area || t('ivan.recommendation')}</div>
                                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{r.desc || r.description || ''}</p>
                                {r.tag && (
                                  <span className="inline-block mt-2 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-violet-100 text-violet-600 dark:bg-violet-500/15 dark:text-violet-400">
                                    {r.tag}
                                  </span>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </Card>
                    ) : (
                      <Card className="p-10 text-center text-gray-400">
                        <Sparkles className="h-10 w-10 mx-auto mb-3 text-gray-300" />
                        <p className="text-sm font-semibold">{t('cand.appDetail.noRecommendations')}</p>
                      </Card>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Sidebar */}
            <Card className="p-6 border-0 shadow-sm bg-white dark:bg-white/[0.03] lg:sticky lg:top-20 space-y-6">
              <h3 className="text-base font-bold text-gray-900 dark:text-white">{t('ivan.details')}</h3>
              <div className="space-y-4 text-sm">
                {[
                  { label: t('ivan.interviewId'), value: `INT-${String(appData.id).padStart(9, '0')}` },
                  { label: t('cand.appDetail.type'), value: analysis?.interview_type || t('ivan.aiInterview') },
                  { label: t('ivan.duration'), value: analysis?.duration || t('cand.appDetail.na') },
                  { label: t('ivan.totalQuestions'), value: String(analysis?.total_questions ?? 0) },
                  { label: t('cand.appDetail.responses'), value: String(analysis?.completed_questions ?? 0) },
                  { label: t('common.status'), value: analysis?.interview_details?.status || (appData.interview_state || 'not_started').replace('_', ' ') },
                ].map((row) => (
                  <div key={row.label} className="flex items-center justify-between">
                    <span className="text-gray-500 dark:text-gray-400">{row.label}</span>
                    <span className="font-semibold text-gray-900 dark:text-white capitalize">{row.value}</span>
                  </div>
                ))}
              </div>

              {analysis?.interview_details?.days_remaining > 0 && (
                <div className="flex items-center gap-2 p-3 rounded-xl bg-amber-50 dark:bg-amber-500/10 border border-amber-100 dark:border-amber-500/20">
                  <Clock className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                  <span className="text-sm font-semibold text-amber-700 dark:text-amber-400">
                    {analysis.interview_details.days_remaining} {t('cand.appDetail.daysRemaining')}
                  </span>
                </div>
              )}

              {hasAnalysis && analysis.score_timeline?.length > 1 && (
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-gray-400 mb-3">{t('cand.appDetail.scoreTrend')}</h4>
                  <div className="flex items-end gap-1 h-16">
                    {analysis.score_timeline.map((pt: any, i: number) => (
                      <div key={i} className="flex-1 flex flex-col items-center gap-1">
                        <div
                          className="w-full rounded-sm bg-gradient-to-t from-amber-400 to-amber-500"
                          style={{ height: `${Math.max(4, (pt.score / 100) * 100)}%` }}
                        />
                        <span className="text-[9px] text-gray-400">{pt.q}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </Card>
          </div>
        </>
      )}

      {/* No analysis state */}
      {!hasAnalysis && !loadingAnalysis && (
        <Card className="p-10 text-center text-gray-400">
          <BarChart3 className="h-10 w-10 mx-auto mb-3 text-gray-300" />
          <p className="text-sm font-semibold">{t('cand.appDetail.noAnalysis')}</p>
          <p className="text-xs text-gray-400 mt-1">{t('cand.appDetail.noAnalysisDesc')}</p>
        </Card>
      )}
    </div>
  );
}
