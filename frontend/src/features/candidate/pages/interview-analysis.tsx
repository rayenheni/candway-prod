import { useState, useEffect } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router';
import { motion, AnimatePresence } from 'framer-motion';
import { Card } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { customToast } from '@/shared/components/ui/toast';
import { useLanguage } from '@/contexts/language-context';
import { candidateService } from '@/services/candidate.service';
import { cn } from '@/utils/cn';
import {
  ArrowLeft, Download, TrendingUp, TrendingDown, Clock, ChevronDown, ChevronRight,
  ClipboardCheck, CheckCircle2, Lightbulb, Sparkles, Target, Loader2,
} from 'lucide-react';

type Tab = 'overview' | 'rubric' | 'questions' | 'feedback' | 'recommendation';

const TABS: { id: Tab; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'rubric', label: 'Rubric & Skills' },
  { id: 'questions', label: 'Questions Review' },
  { id: 'feedback', label: 'AI Feedback' },
  { id: 'recommendation', label: 'Recommendation' },
];

const scoreQualifier = (score: number | null | undefined): string => {
  if (score === null || score === undefined || Number.isNaN(score)) return 'Not available';
  if (score >= 80) return 'Excellent';
  if (score >= 60) return 'Good';
  return 'Fair';
};

interface AnalysisData {
  overall_score: number | null;
  score_label: string;
  role: string;
  company: string;
  interview_type: string;
  date: string;
  duration: string;
  rubric: string;
  is_rubric_driven?: boolean;
  rubric_score?: number | null;
  rubric_coverage_pct?: number | null;
  rubric_version?: number | null;
  category_breakdown?: Array<{ name: string; score: number; weight?: number; coverage_pct?: number }>;
  skill_breakdown?: Array<{ name: string; score: number; is_required?: boolean; category?: string }>;
  gaps?: any[];
  questions: Array<{
    id: number;
    title: string;
    question: string;
    answer: string;
    score: number;
    duration: string;
    feedback: string;
  }>;
  feedback_sections: Array<{ title: string; score: number; text: string }>;
  recommendations: Array<{ title: string; desc: string; tag: string }>;
  strengths: string[];
  improvements: string[];
  highlights: {
    best: { label: string; score: number | null; text: string };
    worst: { label: string; score: number | null; text: string };
    longest: { label: string; duration: string };
  };
  details: Array<{ label: string; value: string }>;
  reasoning?: string;
  status?: string | null;
  ranking?: { rank: number; total: number; percentile: number; score: number } | null;
  scoring_breakdown?: {
    final_score: number | null;
    cv_score: number | null;
    rubric_score: number | null;
    human_score: number | null;
    rubric_coverage_pct: number | null;
    coverage_bonus: number | null;
    has_rubric: boolean;
    weights: { cv: number; rubric: number; human: number; coverage: number };
    computed: number | null;
  } | null;
}

export default function InterviewAnalysisPage() {
  const { t } = useLanguage();
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [showAllQuestions, setShowAllQuestions] = useState(false);
  const [expandedQ, setExpandedQ] = useState<number | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisData | null>(null);
  const [loading, setLoading] = useState(true);

  const appId = id || searchParams.get('id') || searchParams.get('application_id') || '';

  useEffect(() => {
    if (!appId) {
      setLoading(false);
      return;
    }
    candidateService.getInterviewAnalysis(appId)
      .then(res => {
        const d = res;
        const rawDate = d.date ?? d.created_at;
        const details = d.details ?? d.interview_details ?? {};
        const detailMap: Record<string, string> =
          typeof details === 'object' && details !== null ? details : {};
        setAnalysis({
          overall_score: d.score ?? d.overall_score ?? null,
          score_label: d.score_label ?? (d.score === null || d.score === undefined ? 'N/A' : 'N/A'),
          role: d.role ?? d.job_title ?? t('cand.interviewAnalysis.notAvailable'),
          company: d.company ?? d.company_name ?? t('cand.interviewAnalysis.notAvailable'),
          interview_type: d.interview_type ?? t('cand.interviewAnalysis.notAvailable'),
          date: rawDate
            ? new Date(rawDate).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
            : t('cand.interviewAnalysis.notAvailable'),
          duration: d.duration ?? t('cand.interviewAnalysis.notAvailable'),
          rubric: d.is_rubric_driven
            ? (d.rubric_version != null ? `${t('cand.interviewAnalysis.rubric')} v${d.rubric_version}` : t('cand.interviewAnalysis.rubricBased'))
            : t('cand.interviewAnalysis.noRubricAttached'),
          is_rubric_driven: d.is_rubric_driven ?? false,
          rubric_score: d.rubric_score ?? null,
          rubric_coverage_pct: d.rubric_coverage_pct ?? null,
          rubric_version: d.rubric_version ?? null,
          category_breakdown: d.category_breakdown ?? [],
          skill_breakdown: d.skill_breakdown ?? [],
          gaps: d.gaps ?? [],
          questions: (d.questions ?? []).map((q: any, i: number) => ({
            id: q.id ?? i + 1,
            title: q.title ?? q.question ?? `${t('cand.interviewAnalysis.question')} ${i + 1}`,
            question: q.question ?? '',
            answer: q.answer ?? '',
            score: q.score ?? null,
            duration: q.duration ?? '0:00',
            feedback: q.feedback ?? '',
          })),
          feedback_sections: (d.feedback_sections ?? d.feedback ?? d.performance_overview ?? []).map((f: any) => ({
            title: f.title ?? f.label ?? f.category ?? t('cand.interviewAnalysis.notAvailable'),
            score: f.score ?? null,
            text: f.text ?? f.comment ?? '',
          })),
          recommendations: Array.isArray(d.recommendations ?? d.improvements)
            ? (d.recommendations ?? d.improvements).map((r: any) => ({
                title: r.title ?? r.area ?? t('cand.interviewAnalysis.notAvailable'),
                desc: r.desc ?? r.description ?? '',
                tag: r.tag ?? r.priority ?? 'Medium',
              }))
            : [],
          strengths: d.strengths ?? [],
          improvements: d.improvements ?? d.weaknesses ?? [],
          highlights: (() => {
            const h = d.highlights ?? {};
            const best = h.best ?? h.best_moment;
            const worst = h.worst ?? h.worst_moment;
            const longest = h.longest ?? h.longest_answer;
            return {
              best: { label: best?.topic ?? t('cand.interviewAnalysis.notAvailable'), score: best?.score ?? null, text: '' },
              worst: { label: worst?.topic ?? t('cand.interviewAnalysis.notAvailable'), score: worst?.score ?? null, text: '' },
              longest: { label: longest?.topic ?? t('cand.interviewAnalysis.notAvailable'), duration: longest?.duration ?? t('cand.interviewAnalysis.notAvailable') },
            };
          })(),
          status: detailMap.status ?? d.status ?? d.interview_state ?? null,
          ranking: d.ranking ?? null,
          scoring_breakdown: d.scoring_breakdown ?? null,
          reasoning: d.reasoning ?? '',
          details: [
            { label: t('ivan.interviewId'), value: detailMap.interview_id ?? t('cand.interviewAnalysis.notAvailable') },
            { label: t('ivan.startedAt'), value: detailMap.started_at ?? t('cand.interviewAnalysis.notAvailable') },
            { label: t('ivan.submittedAt'), value: detailMap.submitted_at ?? t('cand.interviewAnalysis.notAvailable') },
            { label: t('ivan.totalQuestions'), value: detailMap.total_questions != null ? String(detailMap.total_questions) : String((d.questions ?? []).length) },
            { label: t('ivan.yourResponses'), value: detailMap.responses != null ? String(detailMap.responses) : String((d.questions ?? []).length) },
          ],
        });
      })
      .catch(() => customToast({ type: 'error', title: t('cand.interviews.error'), message: t('cand.interviewAnalysis.loadFailed') }))
      .finally(() => setLoading(false));
  }, [appId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 text-violet-500 animate-spin" />
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <p className="text-base font-semibold text-gray-500 dark:text-gray-400">{t('cand.interviewAnalysis.notFound')}</p>
        <Button variant="outline" className="mt-4" onClick={() => navigate('/interviews')}>{t('ivan.backToInterviews')}</Button>
      </div>
    );
  }

  const overallScore = analysis.overall_score;
  const scoreLabel =
    analysis.score_label && analysis.score_label !== 'N/A'
      ? analysis.score_label
      : overallScore === null
        ? t('cand.interviewAnalysis.notAvailable')
        : overallScore >= 85 ? t('cand.interviewAnalysis.excellent') : overallScore >= 70 ? t('cand.interviewAnalysis.good') : overallScore >= 50 ? t('cand.interviewAnalysis.fair') : t('cand.interviewAnalysis.needsWork');
  const circumference = 2 * Math.PI * 70;
  const dash = overallScore === null ? 0 : (overallScore / 100) * circumference;

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <button
        onClick={() => navigate('/interviews')}
        className="inline-flex items-center gap-2 text-base font-semibold text-violet-600 dark:text-violet-400 hover:text-violet-700 transition-colors"
      >
        <ArrowLeft className="h-5 w-5" />
        {t('ivan.backToInterviews')}
      </button>

      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-gray-900 dark:text-white tracking-tight">
            {t('ivan.title')}
          </h1>
          <p className="mt-2 text-sm sm:text-base text-gray-500 dark:text-gray-400">
            {t('ivan.subtitle')}
          </p>
        </div>
        <Button
          variant="outline"
          leftIcon={<Download className="h-4 w-4" />}
          onClick={async () => {
            try {
              const blob = await candidateService.downloadInterviewReport(appId);
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = `interview-report-${appId}.pdf`;
              a.click();
              URL.revokeObjectURL(url);
            } catch {
              customToast({ type: 'error', title: t('cand.interviews.downloadFailed'), message: t('cand.interviewAnalysis.downloadFailedMsg') });
            }
          }}
          className="font-semibold shrink-0"
        >
          {t('ivan.downloadReport')}
        </Button>
      </div>

      <Card className="p-6 md:p-7 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
        <div className="flex flex-col lg:flex-row lg:items-center gap-6">
          <div className="flex items-center gap-4 min-w-[240px]">
            <div className="h-14 w-14 rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-white text-xl font-bold shrink-0">
              {analysis.role[0] || '?'}
            </div>
            <div>
              <h2 className="text-xl font-extrabold text-gray-900 dark:text-white">{analysis.role}</h2>
              <p className="text-sm text-gray-500 dark:text-gray-400">{analysis.company}</p>
            </div>
          </div>

          <div className="flex flex-wrap items-start gap-8 flex-1">
            <div>
              <div className="text-[11px] font-bold uppercase tracking-wider text-gray-400 mb-1">{t('ivan.interviewType')}</div>
              <div className="text-base font-bold text-gray-900 dark:text-white">{analysis.interview_type}</div>
            </div>
            <div>
              <div className="text-[11px] font-bold uppercase tracking-wider text-gray-400 mb-1">{t('common.date')}</div>
              <div className="text-base font-bold text-gray-900 dark:text-white">{analysis.date}</div>
            </div>
            <div>
              <div className="text-[11px] font-bold uppercase tracking-wider text-gray-400 mb-1">{t('ivan.duration')}</div>
              <div className="text-base font-bold text-gray-900 dark:text-white">{analysis.duration}</div>
            </div>
          </div>

          <div className="rounded-2xl bg-emerald-50/70 dark:bg-emerald-500/10 border border-emerald-100 dark:border-emerald-500/20 px-8 py-5 text-center shrink-0">
            <div className="text-[11px] font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-1">{t('ivan.overallScore')}</div>
            <div className="text-4xl font-extrabold text-amber-500">{overallScore === null ? t('cand.interviewAnalysis.notAvailable') : overallScore}</div>
            <div className="text-sm font-semibold text-amber-500">{scoreLabel}</div>
          </div>
        </div>
      </Card>

      <div className="border-b border-gray-200 dark:border-white/[0.08]">
        <div className="flex items-center gap-8 overflow-x-auto">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'pb-3 text-base font-semibold whitespace-nowrap border-b-2 -mb-px transition-colors',
                activeTab === tab.id
                  ? 'border-violet-600 text-violet-600 dark:border-violet-400 dark:text-violet-400'
                  : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_400px] gap-6 items-start">
        <div className="space-y-6">
          <AnimatePresence mode="wait">
            {activeTab === 'overview' && (
              <motion.div key="ov" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="space-y-6">
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
                        <span className="text-4xl font-extrabold text-gray-900 dark:text-white">{overallScore === null ? t('cand.interviewAnalysis.notAvailable') : overallScore}</span>
                        <span className="text-[11px] font-bold uppercase tracking-wider text-gray-400 mt-1">{t('ivan.overallScore')}</span>
                        <span className="text-sm font-semibold text-amber-500 mt-0.5">{scoreLabel}</span>
                      </div>
                    </div>
                  </div>

                  <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-violet-50 dark:bg-violet-500/10 text-xs font-semibold text-violet-700 dark:text-violet-300">
                    <ClipboardCheck className="h-3.5 w-3.5" />
                    {analysis.rubric}
                  </div>
                </Card>

                {analysis.ranking && (
                  <Card className="p-7 border border-emerald-100 dark:border-emerald-500/15 shadow-sm bg-white dark:bg-white/[0.03]">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                      <div className="flex items-center gap-4">
                        <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center text-white font-extrabold text-lg shrink-0">
                          #{analysis.ranking.rank}
                        </div>
                        <div>
                          <h3 className="text-base font-extrabold text-gray-900 dark:text-white">{t('cand.interviewAnalysis.rankTitle')}</h3>
                          <p className="text-sm text-gray-500 dark:text-gray-400">{t('cand.interviewAnalysis.rankSubtitle')}</p>
                        </div>
                      </div>
                      <div className="text-right shrink-0">
                        <div className="text-3xl font-extrabold text-emerald-600 dark:text-emerald-400">{analysis.ranking.rank}<span className="text-lg text-gray-400">/{analysis.ranking.total}</span></div>
                        <div className="text-xs font-bold text-emerald-600/80">{t('cand.interviewAnalysis.topPercentile').replace('{pct}', String(analysis.ranking.percentile))}</div>
                      </div>
                    </div>
                    <div className="mt-5">
                      <div className="h-2.5 rounded-full bg-gray-100 dark:bg-white/10 overflow-hidden">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${analysis.ranking.percentile}%` }}
                          transition={{ duration: 0.8, ease: 'easeOut' }}
                          className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-500"
                        />
                      </div>
                      <p className="text-xs text-gray-400 mt-2">{t('cand.interviewAnalysis.rankDesc')}</p>
                    </div>
                  </Card>
                )}

                {analysis.scoring_breakdown && analysis.scoring_breakdown.final_score != null && (
                  <Card className="p-7 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
                    <div className="flex items-center gap-2 mb-1">
                      <Target className="h-5 w-5 text-violet-500" />
                      <h3 className="text-xl font-extrabold text-gray-900 dark:text-white">{t('cand.interviewAnalysis.scoreFormulaTitle')}</h3>
                    </div>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-2 mb-6">{t('cand.interviewAnalysis.scoreFormulaDesc')}</p>

                    <div className="flex flex-wrap items-center gap-2 mb-6">
                      {[
                        { label: t('cand.interviewAnalysis.cvComponent'), score: analysis.scoring_breakdown.cv_score, weight: analysis.scoring_breakdown.weights.cv, color: 'text-violet-600 dark:text-violet-400', bar: 'bg-violet-500' },
                        { label: t('cand.interviewAnalysis.rubricComponent'), score: analysis.scoring_breakdown.rubric_score, weight: analysis.scoring_breakdown.weights.rubric, color: 'text-blue-600 dark:text-blue-400', bar: 'bg-blue-500' },
                        { label: t('cand.interviewAnalysis.humanComponent'), score: analysis.scoring_breakdown.human_score, weight: analysis.scoring_breakdown.weights.human, color: 'text-emerald-600 dark:text-emerald-400', bar: 'bg-emerald-500' },
                        { label: t('cand.interviewAnalysis.coverageComponent'), score: analysis.scoring_breakdown.coverage_bonus, weight: analysis.scoring_breakdown.weights.coverage, color: 'text-amber-600 dark:text-amber-400', bar: 'bg-amber-500' },
                      ].filter((c) => c.weight > 0).map((c) => (
                        <div key={c.label} className="flex-1 min-w-[160px] rounded-xl border border-gray-100 dark:border-white/[0.06] bg-gray-50/50 dark:bg-white/[0.02] p-4">
                          <div className="flex items-center justify-between mb-1.5">
                            <span className="text-xs font-bold text-gray-500 dark:text-gray-400">{c.label}</span>
                            <span className="text-xs font-bold text-gray-400">{Math.round(c.weight * 100)}%</span>
                          </div>
                          <div className={cn('text-2xl font-extrabold', c.color)}>{c.score === null || c.score === undefined ? '—' : Math.round(c.score)}</div>
                          <div className="h-1.5 rounded-full bg-gray-100 dark:bg-white/10 overflow-hidden mt-2">
                            <div className={cn('h-full rounded-full', c.bar)} style={{ width: `${Math.max(0, Math.min(100, c.score ?? 0))}%` }} />
                          </div>
                        </div>
                      ))}
                    </div>

                    <div className="rounded-xl bg-violet-50/60 dark:bg-violet-500/5 p-4 text-sm text-gray-600 dark:text-gray-300">
                      {analysis.scoring_breakdown.has_rubric
                        ? `Final Score = CV (${Math.round(analysis.scoring_breakdown.weights.cv * 100)}%) + Interview (${Math.round(analysis.scoring_breakdown.weights.rubric * 100)}%) + Coverage (${Math.round(analysis.scoring_breakdown.weights.coverage * 100)}%)`
                        : `Final Score = CV (${Math.round((analysis.scoring_breakdown.weights?.cv || 0.75) * 100)}%) + Coverage (${Math.round((analysis.scoring_breakdown.weights?.coverage || 0.25) * 100)}%)`}
                    </div>
                  </Card>
                )}

                <Card className="p-7 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
                  <h3 className="text-xl font-extrabold text-gray-900 dark:text-white">{t('ivan.performance')}</h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-2 mb-6">{t('ivan.scoreOverTimeSub')}</p>

                  <div className="relative h-56 w-full">
                    <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="h-full w-full">
                      {[20, 40, 60, 80].map((y) => (
                        <line key={y} x1="0" y1={y} x2="100" y2={y} stroke="currentColor" strokeWidth="0.3" className="text-gray-100 dark:text-white/5" />
                      ))}
                      <defs>
                        <linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#8B5CF6" stopOpacity="0.25" />
                          <stop offset="100%" stopColor="#8B5CF6" stopOpacity="0" />
                        </linearGradient>
                      </defs>
                      {analysis.questions.length > 0 && (
                        <>
                          <motion.polyline
                            points={analysis.questions.map((q, i) => {
                              const x = (i / (analysis.questions.length - 1 || 1)) * 100;
                              const y = 100 - (q.score ?? 0) * 0.8 - 10;
                              return `${x},${y}`;
                            }).join(' ')}
                            fill="none"
                            stroke="#8B5CF6"
                            strokeWidth="1.2"
                            strokeLinejoin="round"
                            strokeLinecap="round"
                            vectorEffect="non-scaling-stroke"
                            initial={{ pathLength: 0 }}
                            animate={{ pathLength: 1 }}
                            transition={{ duration: 1.2, ease: 'easeOut' }}
                          />
                          <polygon points={`0,100 ${analysis.questions.map((q, i) => {
                            const x = (i / (analysis.questions.length - 1 || 1)) * 100;
                            const y = 100 - (q.score ?? 0) * 0.8 - 10;
                            return `${x},${y}`;
                          }).join(' ')} 100,100`} fill="url(#areaFill)" />
                        </>
                      )}
                    </svg>
                    <div className="absolute inset-x-0 bottom-0 flex justify-between text-[10px] text-gray-400 px-1 -mb-5">
                      {analysis.questions.length > 0 ? (
                        <>
                          <span>{t('cand.interviewAnalysis.q')}1</span><span>{t('cand.interviewAnalysis.q')}{Math.ceil(analysis.questions.length / 2)}</span><span>{t('cand.interviewAnalysis.q')}{analysis.questions.length}</span>
                        </>
                      ) : (
                        <span>{t('cand.interviewAnalysis.noScoredQuestions')}</span>
                      )}
                    </div>
                  </div>
                </Card>

                {analysis.questions.length > 0 && (
                  <Card className="p-7 border border-violet-100 dark:border-violet-500/15 shadow-sm bg-white dark:bg-white/[0.03]">
                    <h3 className="text-xl font-extrabold text-gray-900 dark:text-white">{t('ivan.questionsReview')}</h3>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-2 mb-5">{t('ivan.reviewSub')}</p>

                    <AnimatePresence>
                      {showAllQuestions && (
                        <motion.div
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: 'auto' }}
                          exit={{ opacity: 0, height: 0 }}
                          className="space-y-3 mb-4 overflow-hidden"
                        >
                          {analysis.questions.map((q) => (
                            <div key={q.id} className="rounded-xl border border-gray-100 dark:border-white/[0.06] overflow-hidden">
                              <button
                                onClick={() => setExpandedQ(expandedQ === q.id ? null : q.id)}
                                className="w-full flex items-center justify-between gap-3 p-4 hover:bg-gray-50 dark:hover:bg-white/[0.02] transition-colors text-left"
                              >
                                <div className="flex items-center gap-3 min-w-0">
                                  <span className="h-7 w-7 rounded-lg bg-violet-100 dark:bg-violet-500/15 text-violet-700 dark:text-violet-300 text-xs font-bold flex items-center justify-center shrink-0">
                                    {q.id}
                                  </span>
                                  <div className="min-w-0">
                                    <div className="text-sm font-bold text-gray-900 dark:text-white truncate">{q.title}</div>
                                    <div className="text-xs text-gray-500 truncate">{q.question}</div>
                                  </div>
                                </div>
                                <div className="flex items-center gap-3 shrink-0">
                                  <span className={cn('text-sm font-extrabold', q.score === null || q.score === undefined ? 'text-gray-400' : q.score >= 60 ? 'text-emerald-600' : 'text-amber-500')}>{q.score === null || q.score === undefined ? '—' : q.score}</span>
                                  <ChevronDown className={cn('h-4 w-4 text-gray-400 transition-transform', expandedQ === q.id && 'rotate-180')} />
                                </div>
                              </button>
                              {expandedQ === q.id && (
                                <div className="px-4 pb-4 space-y-3 border-t border-gray-50 dark:border-white/[0.04] pt-3">
                                  <div>
                                    <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-1">{t('cand.interviewAnalysis.yourAnswer')}</div>
                                    <p className="text-sm text-gray-600 dark:text-gray-300">{q.answer}</p>
                                  </div>
                                  <div className="rounded-lg bg-violet-50/60 dark:bg-violet-500/5 p-3">
                                    <div className="text-[10px] font-bold uppercase tracking-wider text-violet-600 dark:text-violet-400 mb-1 flex items-center gap-1">
                                      <Sparkles className="h-3 w-3" /> {t('ivan.aiFeedback')}
                                    </div>
                                    <p className="text-sm text-gray-700 dark:text-gray-300">{q.feedback}</p>
                                  </div>
                                  <div className="text-xs text-gray-400 flex items-center gap-1">
                                    <Clock className="h-3 w-3" /> {t('cand.interviewAnalysis.answerDuration')} {q.duration}
                                  </div>
                                </div>
                              )}
                            </div>
                          ))}
                        </motion.div>
                      )}
                    </AnimatePresence>

                    <button
                      onClick={() => setShowAllQuestions(!showAllQuestions)}
                      className="w-full flex items-center justify-center gap-2 py-4 rounded-xl border border-gray-200 dark:border-white/10 text-base font-bold text-violet-600 dark:text-violet-400 hover:bg-violet-50/50 dark:hover:bg-white/[0.02] transition-colors"
                    >
                      {showAllQuestions ? t('ivan.hideAll') : t('ivan.showAll')}
                      <ChevronDown className={cn('h-5 w-5 transition-transform', showAllQuestions && 'rotate-180')} />
                    </button>
                  </Card>
                )}
              </motion.div>
            )}

            {activeTab === 'rubric' && (
              <motion.div key="rubric" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="space-y-6">
                <Card className="p-7 border border-violet-100 dark:border-violet-500/15 shadow-sm bg-white dark:bg-white/[0.03]">
                  <div className="flex items-center gap-2 mb-1">
                    <Sparkles className="h-5 w-5 text-violet-500" />
                    <h3 className="text-xl font-extrabold text-gray-900 dark:text-white">{t('cand.interviewAnalysis.rubricSkillAssessment')}</h3>
                  </div>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">
                    {t('cand.interviewAnalysis.rubricDesc')}
                  </p>

                  {(analysis.is_rubric_driven || (analysis.category_breakdown?.length ?? 0) > 0 || (analysis.skill_breakdown?.length ?? 0) > 0) ? (
                  <>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
                    <div className="rounded-2xl bg-violet-50/70 dark:bg-violet-500/10 border border-violet-100 dark:border-violet-500/20 p-4 text-center">
                      <div className="text-[11px] font-bold uppercase tracking-wider text-violet-500 mb-1">{t('cand.interviewAnalysis.rubricScore')}</div>
                      <div className="text-3xl font-extrabold text-violet-600 dark:text-violet-400">
                        {analysis.rubric_score !== null && analysis.rubric_score !== undefined ? Math.round(analysis.rubric_score) : t('cand.interviewAnalysis.notAvailable')}
                      </div>
                    </div>
                    <div className="rounded-2xl bg-emerald-50/70 dark:bg-emerald-500/10 border border-emerald-100 dark:border-emerald-500/20 p-4 text-center">
                      <div className="text-[11px] font-bold uppercase tracking-wider text-emerald-500 mb-1">{t('cand.interviewAnalysis.evaluationCoverage')}</div>
                      <div className="text-3xl font-extrabold text-emerald-600 dark:text-emerald-400">
                        {analysis.rubric_coverage_pct !== null && analysis.rubric_coverage_pct !== undefined ? `${analysis.rubric_coverage_pct}%` : t('cand.interviewAnalysis.notAvailable')}
                      </div>
                    </div>
                    <div className="rounded-2xl bg-blue-50/70 dark:bg-blue-500/10 border border-blue-100 dark:border-blue-500/20 p-4 text-center">
                      <div className="text-[11px] font-bold uppercase tracking-wider text-blue-500 mb-1">{t('cand.interviewAnalysis.rubricVersion')}</div>
                      <div className="text-3xl font-extrabold text-blue-600 dark:text-blue-400">
                        {analysis.rubric_version !== null && analysis.rubric_version !== undefined ? `v${analysis.rubric_version}` : t('cand.interviewAnalysis.noRubricVersion')}
                      </div>
                    </div>
                  </div>

                  {analysis.category_breakdown && analysis.category_breakdown.length > 0 && (
                    <div className="mb-8 space-y-4">
                      <h4 className="text-base font-extrabold text-gray-900 dark:text-white flex items-center gap-2">
                        <TrendingUp className="h-4 w-4 text-violet-500" /> {t('cand.interviewAnalysis.categoryBreakdown')}
                      </h4>
                      <div className="space-y-4">
                        {analysis.category_breakdown.map((cat) => (
                          <div key={cat.name} className="flex items-center gap-4">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center justify-between mb-1.5">
                                <span className="text-sm font-bold text-gray-900 dark:text-white">{cat.name}</span>
                                <span className={cn('text-base font-extrabold', cat.score >= 75 ? 'text-emerald-600' : cat.score >= 60 ? 'text-blue-600' : 'text-amber-500')}>
                                  {Math.round(cat.score)}/100
                                </span>
                              </div>
                              <div className="h-2 rounded-full bg-gray-100 dark:bg-white/10 overflow-hidden">
                                <div
                                  className={cn('h-full rounded-full', cat.score >= 75 ? 'bg-emerald-500' : cat.score >= 60 ? 'bg-blue-500' : 'bg-amber-500')}
                                  style={{ width: `${cat.score}%` }}
                                />
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {analysis.skill_breakdown && analysis.skill_breakdown.length > 0 && (
                    <div className="mb-8 space-y-3">
                      <h4 className="text-base font-extrabold text-gray-900 dark:text-white flex items-center gap-2">
                        <CheckCircle2 className="h-4 w-4 text-emerald-500" /> {t('cand.interviewAnalysis.assessedCompetencies')}
                      </h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {analysis.skill_breakdown.map((sk) => (
                          <div key={sk.name} className="p-4 rounded-xl border border-gray-100 dark:border-white/[0.06] bg-gray-50/50 dark:bg-white/[0.02] flex items-center justify-between">
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="text-sm font-bold text-gray-900 dark:text-white">{sk.name}</span>
                                {sk.is_required && (
                                  <span className="px-1.5 py-0.5 rounded bg-amber-50 text-[10px] font-bold text-amber-600 dark:bg-amber-500/10 dark:text-amber-400">{t('cand.interviewAnalysis.required')}</span>
                                )}
                              </div>
                              {sk.category && <span className="text-xs text-gray-400">{sk.category}</span>}
                            </div>
                            <span className={cn('text-base font-extrabold', sk.score >= 75 ? 'text-emerald-600' : sk.score >= 60 ? 'text-blue-600' : 'text-amber-500')}>
                              {Math.round(sk.score)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {analysis.gaps && analysis.gaps.length > 0 && (
                    <div className="space-y-3">
                      <h4 className="text-base font-extrabold text-gray-900 dark:text-white flex items-center gap-2">
                        <Lightbulb className="h-4 w-4 text-amber-500" /> {t('cand.interviewAnalysis.recommendedAreas')}
                      </h4>
                      <div className="flex flex-wrap gap-2">
                        {analysis.gaps.map((gap, i) => (
                          <span key={i} className="px-3 py-1.5 rounded-lg bg-amber-50 dark:bg-amber-500/10 border border-amber-100 dark:border-amber-500/20 text-xs font-semibold text-amber-700 dark:text-amber-300">
                            {typeof gap === 'string' ? gap : gap?.skill || gap?.category || JSON.stringify(gap)}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  </>
                  ) : (
                    <div className="flex flex-col items-center justify-center py-10 text-center">
                      <Sparkles className="h-10 w-10 text-gray-300 dark:text-gray-600 mb-3" />
                      <p className="text-base font-medium text-gray-500 dark:text-gray-400">{t('cand.interviewAnalysis.noRubric')}</p>
                      <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">{t('cand.interviewAnalysis.noRubricDesc')}</p>
                    </div>
                  )}
                </Card>
              </motion.div>
            )}

            {activeTab === 'questions' && (
              <motion.div key="qs" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                <Card className="p-7 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
                  <h3 className="text-xl font-extrabold text-gray-900 dark:text-white mb-1">{t('ivan.questionsReview')}</h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">{t('cand.interviewAnalysis.allQuestions')} {analysis.questions.length} {t('cand.interviewAnalysis.questionsWithScoring')}</p>
                  <div className="space-y-4">
                    {analysis.questions.map((q) => (
                      <div key={q.id} className="rounded-2xl border border-gray-100 dark:border-white/[0.06] p-5">
                        <div className="flex items-start justify-between gap-4 mb-3">
                          <div className="flex items-start gap-3">
                            <span className="h-8 w-8 rounded-xl bg-violet-100 dark:bg-violet-500/15 text-violet-700 dark:text-violet-300 text-sm font-bold flex items-center justify-center shrink-0">
                              {q.id}
                            </span>
                            <div>
                              <div className="text-base font-bold text-gray-900 dark:text-white">{q.title}</div>
                              <div className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">{q.question}</div>
                            </div>
                          </div>
                          <div className="text-right shrink-0">
                            <div className={cn('text-xl font-extrabold', q.score === null || q.score === undefined ? 'text-gray-400' : q.score >= 60 ? 'text-emerald-600' : 'text-amber-500')}>{q.score === null || q.score === undefined ? '—' : q.score}</div>
                            <div className="text-[10px] text-gray-400 flex items-center gap-1 justify-end"><Clock className="h-3 w-3" />{q.duration}</div>
                          </div>
                        </div>
                        <p className="text-sm text-gray-600 dark:text-gray-300 mb-3 pl-11">{q.answer}</p>
                        <div className="ml-11 rounded-xl bg-violet-50/60 dark:bg-violet-500/5 p-3">
                          <div className="text-[10px] font-bold uppercase tracking-wider text-violet-600 dark:text-violet-400 mb-1 flex items-center gap-1">
                            <Sparkles className="h-3 w-3" /> {t('ivan.aiFeedback')}
                          </div>
                          <p className="text-sm text-gray-700 dark:text-gray-300">{q.feedback}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              </motion.div>
            )}

            {activeTab === 'feedback' && (
              <motion.div key="fb" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                <Card className="p-7 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
                  <h3 className="text-xl font-extrabold text-gray-900 dark:text-white mb-1">{t('cand.interviewAnalysis.detailedAiFeedback')}</h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">{t('cand.interviewAnalysis.detailedAiFeedbackDesc')}</p>
                  <div className="space-y-5">
                    {analysis.feedback_sections.length > 0 ? (
                      analysis.feedback_sections.map((s, i) => (
                        <motion.div key={s.title} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.06 }} className="rounded-2xl border border-gray-100 dark:border-white/[0.06] p-5">
                          <div className="flex items-center justify-between mb-2">
                            <h4 className="text-base font-bold text-gray-900 dark:text-white">{s.title}</h4>
                            <span className={cn('text-lg font-extrabold', s.score === null || s.score === undefined ? 'text-gray-400' : s.score >= 70 ? 'text-emerald-600' : s.score >= 55 ? 'text-amber-500' : 'text-red-500')}>{s.score === null || s.score === undefined ? '—' : s.score}</span>
                          </div>
                          {s.score !== null && s.score !== undefined && (
                          <div className="h-2 rounded-full bg-gray-100 dark:bg-white/10 overflow-hidden mb-3">
                            <motion.div
                              initial={{ width: 0 }} animate={{ width: `${s.score}%` }} transition={{ duration: 0.6, delay: i * 0.06 }}
                              className={cn('h-full rounded-full', s.score >= 70 ? 'bg-emerald-500' : s.score >= 55 ? 'bg-amber-500' : 'bg-red-500')}
                            />
                          </div>
                          )}
                          <p className="text-sm text-gray-600 dark:text-gray-300 leading-relaxed">{s.text || t('cand.interviewAnalysis.noFeedbackText')}</p>
                        </motion.div>
                      ))
                    ) : (
                      <div className="flex flex-col items-center justify-center py-10 text-center">
                        <Sparkles className="h-10 w-10 text-gray-300 dark:text-gray-600 mb-3" />
                        <p className="text-base font-medium text-gray-500 dark:text-gray-400">{t('cand.interviewAnalysis.noAiFeedback')}</p>
                        <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">{t('cand.interviewAnalysis.noAiFeedbackDesc')}</p>
                      </div>
                    )}
                  </div>
                </Card>
              </motion.div>
            )}

            {activeTab === 'recommendation' && (
              <motion.div key="rec" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="space-y-6">
                <Card className="p-7 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
                  <div className="flex items-center gap-2 mb-4">
                    <Lightbulb className="h-5 w-5 text-amber-500" />
                    <h3 className="text-xl font-extrabold text-gray-900 dark:text-white">{t('cand.interviewAnalysis.personalizedRecommendations')}</h3>
                  </div>
                  <div className="space-y-4">
                    {analysis.recommendations.length > 0 ? (
                      analysis.recommendations.map((r, i) => (
                      <div key={i} className="flex items-start gap-4 p-4 rounded-2xl border border-gray-100 dark:border-white/[0.06]">
                        <div className="h-9 w-9 rounded-xl bg-violet-100 dark:bg-violet-500/15 flex items-center justify-center shrink-0">
                          <Target className="h-4.5 w-4.5 text-violet-600 dark:text-violet-400" />
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <h4 className="text-base font-bold text-gray-900 dark:text-white">{r.title}</h4>
                            <span className={cn(
                              'px-2 py-0.5 rounded-full text-[10px] font-bold uppercase',
                              r.tag === 'High Priority' ? 'bg-red-50 text-red-600 dark:bg-red-500/10' :
                              r.tag === 'Medium' ? 'bg-amber-50 text-amber-600 dark:bg-amber-500/10' :
                              'bg-gray-100 text-gray-500 dark:bg-white/10'
                            )}>{r.tag}</span>
                          </div>
                          <p className="text-sm text-gray-600 dark:text-gray-300 mt-1">{r.desc}</p>
                        </div>
                      </div>
                      ))
                    ) : (
                      <div className="flex flex-col items-center justify-center py-10 text-center">
                        <Target className="h-10 w-10 text-gray-300 dark:text-gray-600 mb-3" />
                        <p className="text-base font-medium text-gray-500 dark:text-gray-400">{t('cand.interviewAnalysis.noRecommendations')}</p>
                        <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">{t('cand.interviewAnalysis.noRecommendationsDesc')}</p>
                      </div>
                    )}
                  </div>
                </Card>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <div className="space-y-6 lg:sticky lg:top-20">
          <Card className="p-6 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
            <h3 className="text-lg font-extrabold text-gray-900 dark:text-white mb-4">{t('ivan.aiSummary')}</h3>
            <p className="text-sm text-gray-600 dark:text-gray-300 mb-5">
              {analysis.reasoning && analysis.reasoning.trim() && analysis.reasoning !== 'Analysis complete.'
                ? analysis.reasoning
                : t('cand.interviewAnalysis.noAiSummary')}
            </p>

            {analysis.strengths.length > 0 && (
              <div className="mb-5">
                <h4 className="text-base font-bold text-gray-900 dark:text-white mb-2 flex items-center gap-1.5">
                  <CheckCircle2 className="h-4 w-4 text-emerald-500" /> {t('ivan.strengths')}
                </h4>
                <ul className="space-y-1.5">
                  {analysis.strengths.map((s, i) => (
                    <li key={i} className="text-sm text-gray-600 dark:text-gray-400 flex items-start gap-2">
                      <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 mt-1.5 shrink-0" />
                      {s}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {analysis.improvements.length > 0 && (
              <div>
                <h4 className="text-base font-bold text-gray-900 dark:text-white mb-2 flex items-center gap-1.5">
                  <TrendingUp className="h-4 w-4 text-amber-500" /> {t('ivan.areasImprove')}
                </h4>
                <ul className="space-y-1.5">
                  {analysis.improvements.map((s, i) => (
                    <li key={i} className="text-sm text-gray-600 dark:text-gray-400 flex items-start gap-2">
                      <span className="h-1.5 w-1.5 rounded-full bg-amber-500 mt-1.5 shrink-0" />
                      {s}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </Card>

          <Card className="p-6 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
            <h3 className="text-lg font-extrabold text-gray-900 dark:text-white mb-5">{t('ivan.highlights')}</h3>
            <div className="space-y-3">
              <div className="flex items-center gap-3 p-3.5 rounded-2xl bg-emerald-50/60 dark:bg-emerald-500/5">
                <div className="h-10 w-10 rounded-xl bg-emerald-100 dark:bg-emerald-500/15 flex items-center justify-center shrink-0">
                  <TrendingUp className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400">{t('ivan.bestMoment')}</div>
                  <div className="text-sm font-bold text-gray-900 dark:text-white truncate">{analysis.highlights.best.label}</div>
                </div>
                <div className="text-right shrink-0">
                  <div className="text-lg font-extrabold text-emerald-600 dark:text-emerald-400">{analysis.highlights.best.score === null || analysis.highlights.best.score === undefined ? '—' : analysis.highlights.best.score}</div>
                  <div className="text-[9px] font-bold uppercase text-emerald-600/70">{scoreQualifier(analysis.highlights.best.score)}</div>
                </div>
              </div>

              <div className="flex items-center gap-3 p-3.5 rounded-2xl bg-amber-50/60 dark:bg-amber-500/5">
                <div className="h-10 w-10 rounded-xl bg-amber-100 dark:bg-amber-500/15 flex items-center justify-center shrink-0">
                  <TrendingDown className="h-5 w-5 text-amber-600 dark:text-amber-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400">{t('ivan.needsImprovement')}</div>
                  <div className="text-sm font-bold text-gray-900 dark:text-white truncate">{analysis.highlights.worst.label}</div>
                </div>
                <div className="text-right shrink-0">
                  <div className="text-lg font-extrabold text-amber-500">{analysis.highlights.worst.score === null || analysis.highlights.worst.score === undefined ? '—' : analysis.highlights.worst.score}</div>
                  <div className="text-[9px] font-bold uppercase text-amber-500/70">{scoreQualifier(analysis.highlights.worst.score)}</div>
                </div>
              </div>

              <div className="flex items-center gap-3 p-3.5 rounded-2xl bg-pink-50/60 dark:bg-pink-500/5">
                <div className="h-10 w-10 rounded-xl bg-pink-100 dark:bg-pink-500/15 flex items-center justify-center shrink-0">
                  <Clock className="h-5 w-5 text-pink-600 dark:text-pink-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400">{t('ivan.longestAnswer')}</div>
                  <div className="text-sm font-bold text-gray-900 dark:text-white truncate">{analysis.highlights.longest.label}</div>
                </div>
                <div className="text-right shrink-0">
                  <div className="text-lg font-extrabold text-gray-900 dark:text-white">{analysis.highlights.longest.duration}</div>
                  <div className="text-[9px] font-bold uppercase text-gray-400">{t('ivan.duration')}</div>
                </div>
              </div>
            </div>
          </Card>

          <Card className="p-6 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
            <h3 className="text-lg font-extrabold text-gray-900 dark:text-white mb-5">{t('ivan.details')}</h3>
            <div className="space-y-3.5">
              {analysis.details.map((row) => (
                <div key={row.label} className="flex items-center justify-between gap-4">
                  <span className="text-sm text-gray-500 dark:text-gray-400">{row.label}</span>
                  <span className="text-sm font-bold text-gray-900 dark:text-white text-right">{row.value}</span>
                </div>
              ))}
              {analysis.status && (
                <div className="flex items-center justify-between gap-4">
                  <span className="text-sm text-gray-500 dark:text-gray-400">{t('ivan.status')}</span>
                  <span className="px-3 py-1 rounded-lg bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 text-xs font-bold">
                    {analysis.status}
                  </span>
                </div>
              )}
            </div>
          </Card>

          <Card className="p-6 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
            <h3 className="text-lg font-extrabold text-gray-900 dark:text-white mb-2">{t('ivan.nextSteps')}</h3>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-5">
              {t('ivan.keepImproving')}
            </p>
            <button
              onClick={() => navigate('/interviews')}
              className="w-full flex items-center justify-between gap-2 px-4 py-3.5 rounded-xl border border-gray-200 dark:border-white/10 text-base font-semibold text-gray-900 dark:text-white hover:bg-gray-50 dark:hover:bg-white/[0.03] transition-colors mb-3"
            >
              {t('ivan.backToInterviews')}
              <ChevronRight className="h-5 w-5 text-gray-400" />
            </button>
            <Button
              variant="primary"
              className="w-full py-3.5 text-base font-bold shadow-md shadow-violet-500/25"
              onClick={() => navigate('/interviews')}
            >
              {t('ivan.backToInterviews')}
            </Button>
          </Card>
        </div>
      </div>

      <p className="text-center text-sm text-gray-400 dark:text-gray-500 py-4">
        {t('ivan.aiDisclaimer')}
      </p>
    </div>
  );
}