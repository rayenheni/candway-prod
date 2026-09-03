// ============================================================
// Candidate Applications Tracker - Matches Candway Production UI
// ============================================================

import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router';
import { motion } from 'framer-motion';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { candidateService } from '@/services/candidate.service';
import { useLanguage } from '@/contexts/language-context';
import { Card } from '@/shared/components/ui/card';
import { SimpleDropdown } from '@/shared/components/ui/dropdown-menu';
import { customToast } from '@/shared/components/ui/toast';
import { cn } from '@/utils/cn';
import {
  FileText,
  LayoutGrid,
  Send,
  Search,
  Users,
  CheckCircle2,
  XCircle,
  RotateCcw,
  CheckCircle,
  Eye,
  MoreVertical,
  PieChart,
  PlayCircle,
  Hourglass,
} from 'lucide-react';

type StatusKey = 'applied' | 'in_review' | 'invited' | 'interview' | 'offered' | 'rejected' | 'withdrawn' | 'offer_declined';

interface Application {
  id: string;
  title: string;
  company: string;
  verified: boolean;
  status: StatusKey;
  applied: string;
  lastUpdate: string;
  nextStep: string;
  initial: string;
  color: string;
}

const STATUS_CONFIG: Record<StatusKey, { label: string; bg: string; text: string; dot: string }> = {
  applied:    { label: 'Applied',    bg: 'bg-amber-50 dark:bg-amber-500/10',   text: 'text-amber-700 dark:text-amber-400',   dot: 'bg-amber-500' },
  in_review:  { label: 'In Review',  bg: 'bg-orange-50 dark:bg-orange-500/10', text: 'text-orange-700 dark:text-orange-400', dot: 'bg-orange-500' },
  invited:    { label: 'Invited',    bg: 'bg-indigo-50 dark:bg-indigo-500/10', text: 'text-indigo-700 dark:text-indigo-400', dot: 'bg-indigo-500' },
  interview:  { label: 'Interview',  bg: 'bg-emerald-50 dark:bg-emerald-500/10', text: 'text-emerald-700 dark:text-emerald-400', dot: 'bg-emerald-500' },
  offered:    { label: 'Offered',    bg: 'bg-violet-50 dark:bg-violet-500/10', text: 'text-violet-700 dark:text-violet-400', dot: 'bg-violet-500' },
  rejected:   { label: 'Rejected',   bg: 'bg-red-50 dark:bg-red-500/10',       text: 'text-red-700 dark:text-red-400',       dot: 'bg-red-500' },
  withdrawn:  { label: 'Withdrawn',  bg: 'bg-gray-100 dark:bg-white/10',       text: 'text-gray-600 dark:text-gray-400',     dot: 'bg-gray-400' },
  offer_declined: { label: 'Offer Declined', bg: 'bg-rose-50 dark:bg-rose-500/10', text: 'text-rose-700 dark:text-rose-400', dot: 'bg-rose-500' },
};

const NEXT_STEP: Record<StatusKey, string> = {
  applied: 'Awaiting review',
  in_review: 'Under review',
  invited: 'Interview invitation received',
  interview: 'Interview scheduled',
  offered: 'Review offer',
  rejected: 'Application closed',
  withdrawn: '—',
  offer_declined: 'Offer declined',
};

const CARD_COLORS = [
  'bg-gradient-to-br from-indigo-500 to-violet-600',
  'bg-gradient-to-br from-violet-500 to-purple-600',
  'bg-gradient-to-br from-blue-500 to-indigo-600',
  'bg-gradient-to-br from-pink-500 to-rose-600',
  'bg-gradient-to-br from-emerald-500 to-teal-600',
];

const TABS: { key: 'all' | StatusKey; label: string; icon: React.ElementType }[] = [
  { key: 'all', label: 'All Jobs', icon: LayoutGrid },
  { key: 'applied', label: 'Applied', icon: Send },
  { key: 'in_review', label: 'In Review', icon: Search },
  { key: 'invited', label: 'Invited', icon: Hourglass },
  { key: 'interview', label: 'Interview', icon: Users },
  { key: 'offered', label: 'Offered', icon: CheckCircle2 },
  { key: 'rejected', label: 'Rejected', icon: XCircle },
  { key: 'withdrawn', label: 'Withdrawn', icon: RotateCcw },
  { key: 'offer_declined', label: 'Offer Declined', icon: XCircle },
];

function normalizeStatus(status?: string): StatusKey {
  const s = (status || '').toLowerCase().replace(/\s+/g, '_');
  if (['invited', 'interviewing', 'interview'].includes(s)) return 'interviewing' === s || s === 'interview' ? 'interview' : 'invited';
  if (['screening', 'analyzing', 'analyzed', 'analysis_failed', 'failed', 'reviewed'].includes(s)) return 'in_review';
  if (['applied', 'in_review', 'interview', 'offered', 'rejected', 'withdrawn', 'offer_declined', 'invited'].includes(s)) return s as StatusKey;
  return 'applied';
}

export default function ApplicationsTrackerPage() {
  const [activeTab, setActiveTab] = useState<'all' | StatusKey>('all');
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { t } = useLanguage();
  const [withdrawingId, setWithdrawingId] = useState<string | null>(null);

  const { data: dashboard, isLoading } = useQuery({
    queryKey: ['candidate-dashboard'],
    queryFn: async () => {
      const res = await candidateService.getDashboardSummary();
      return res;
    },
  });

  const applications = useMemo<Application[]>(() => {
    if (!dashboard?.applications) return [];
    return dashboard.applications.map((app, i) => ({
      id: String(app.id),
      title: app.title || t('apps.tracker.untitledRole'),
      company: app.company || t('apps.tracker.unknownCompany'),
      verified: true,
      status: normalizeStatus(app.status),
      applied: app.date || 'N/A',
      lastUpdate: app.date || 'N/A',
      nextStep: NEXT_STEP[normalizeStatus(app.status)] || t('apps.awaitingResponse'),
      initial: app.company ? app.company.charAt(0).toUpperCase() : 'C',
      color: CARD_COLORS[i % CARD_COLORS.length],
    }));
  }, [dashboard, t]);

  const filtered = useMemo(
    () => (activeTab === 'all' ? applications : applications.filter((a) => a.status === activeTab)),
    [applications, activeTab]
  );

  const counts = useMemo(() => {
    const c: Record<StatusKey, number> = { applied: 0, in_review: 0, invited: 0, interview: 0, offered: 0, rejected: 0, withdrawn: 0, offer_declined: 0 };
    applications.forEach((a) => { c[a.status]++; });
    return c;
  }, [applications]);

  const total = applications.length;

  // Donut chart geometry
  const segments = [
    { key: 'applied', value: counts.applied, color: '#6366F1' },
    { key: 'interview', value: counts.interview, color: '#10B981' },
    { key: 'in_review', value: counts.in_review, color: '#F59E0B' },
    { key: 'invited', value: counts.invited, color: '#8B5CF6' },
    { key: 'rejected', value: counts.rejected, color: '#EF4444' },
  ];
  const circumference = 2 * Math.PI * 42;
  let offsetAcc = 0;

  const handleView = (app: Application) => {
    navigate(`/applications/${app.id}`);
  };

  const handleWithdraw = async (app: Application) => {
    if (withdrawingId) return;
    setWithdrawingId(app.id);
    try {
      await candidateService.withdrawApplication(app.id);
      customToast({ type: 'success', title: t('apps.tracker.withdrawn'), message: `${t('apps.tracker.withdrewFor')} ${app.title}.` });
      await queryClient.invalidateQueries({ queryKey: ['candidate-dashboard'] });
    } catch (err) {
      customToast({ type: 'error', title: t('apps.tracker.withdrawFailed'), message: t('apps.tracker.withdrawFailedMsg') });
      console.error('Withdraw error:', err);
    } finally {
      setWithdrawingId(null);
    }
  };

  if (isLoading) {
    return <div className="flex justify-center items-center py-20 text-gray-500">{t('apps.tracker.loading')}</div>;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-violet-600 dark:text-violet-400 mb-2">
          <FileText className="h-3.5 w-3.5" />
          {t('apps.eyebrow')}
        </div>
        <h1 className="text-3xl sm:text-4xl font-extrabold text-gray-900 dark:text-white tracking-tight">
          {t('apps.title')}
        </h1>
        <p className="mt-2 text-sm sm:text-base text-gray-500 dark:text-gray-400">
          {t('apps.subtitle')}
        </p>
      </div>

      {/* Filter Tabs */}
      <div className="flex flex-wrap items-center gap-2">
        {TABS.map((tab) => {
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                'inline-flex items-center gap-1.5 px-4 py-2 rounded-full text-sm font-semibold transition-all whitespace-nowrap',
                isActive
                  ? 'bg-violet-600 text-white shadow-md shadow-violet-500/25'
                  : 'bg-white dark:bg-white/[0.04] text-gray-600 dark:text-gray-300 border border-gray-200 dark:border-white/10 hover:border-violet-300 dark:hover:border-violet-500/30'
              )}
            >
              <tab.icon className="h-3.5 w-3.5" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Main content grid */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-6 items-start">
        {/* Applications Table */}
        <Card className="p-0 border-0 shadow-sm bg-white dark:bg-white/[0.03] overflow-hidden">
          <div className="flex items-center gap-2 px-6 py-4 border-b border-gray-100 dark:border-white/[0.06]">
            <CheckCircle className="h-4 w-4 text-emerald-500" />
            <span className="text-sm font-semibold text-gray-700 dark:text-gray-200">{filtered.length} {t('apps.found')}</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-100 dark:border-white/[0.06]">
                  <th className="text-left px-6 py-3 text-[11px] font-bold text-gray-400 uppercase tracking-wider">{t('apps.col.jobCompany')}</th>
                  <th className="text-left px-4 py-3 text-[11px] font-bold text-gray-400 uppercase tracking-wider">{t('apps.col.status')}</th>
                  <th className="text-left px-4 py-3 text-[11px] font-bold text-gray-400 uppercase tracking-wider">{t('apps.col.applied')}</th>
                  <th className="text-left px-4 py-3 text-[11px] font-bold text-gray-400 uppercase tracking-wider">{t('apps.col.lastUpdate')}</th>
                  <th className="text-left px-4 py-3 text-[11px] font-bold text-gray-400 uppercase tracking-wider">{t('apps.col.nextStep')}</th>
                  <th className="text-right px-6 py-3 text-[11px] font-bold text-gray-400 uppercase tracking-wider">{t('apps.col.actions')}</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((app, i) => {
                  const status = STATUS_CONFIG[app.status] || STATUS_CONFIG.applied;
                  return (
                    <motion.tr
                      key={app.id}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ duration: 0.2, delay: i * 0.02 }}
                      className="border-b border-gray-50 dark:border-white/[0.03] hover:bg-gray-50/60 dark:hover:bg-white/[0.02] transition-colors"
                    >
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <div className={cn('h-10 w-10 rounded-xl flex items-center justify-center text-white font-bold text-sm shrink-0', app.color)}>
                            {app.initial}
                          </div>
                          <div>
                            <div className="text-sm font-bold text-gray-900 dark:text-white">{app.title}</div>
                            <div className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400">
                              {app.company}
                              {app.verified && <CheckCircle2 className="h-3 w-3 text-violet-500" />}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-4">
                        <span className={cn('inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold uppercase tracking-wide', status.bg, status.text)}>
                          <span className={cn('h-1.5 w-1.5 rounded-full', status.dot)} />
                          {status.label}
                        </span>
                      </td>
                      <td className="px-4 py-4 text-sm text-gray-600 dark:text-gray-300">{app.applied}</td>
                      <td className="px-4 py-4 text-sm text-gray-600 dark:text-gray-300">{app.lastUpdate}</td>
                      <td className="px-4 py-4">
                        <span className="text-sm font-medium text-violet-600 dark:text-violet-400 inline-flex items-center gap-1">
                          → {app.nextStep}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => handleView(app)}
                            className="h-8 w-8 flex items-center justify-center rounded-lg text-gray-400 hover:bg-violet-50 hover:text-violet-600 dark:hover:bg-white/10 transition-colors"
                          >
                            <Eye className="h-4 w-4" />
                          </button>
                          <SimpleDropdown
                            trigger={
                              <button className="h-8 w-8 flex items-center justify-center rounded-lg text-gray-400 hover:bg-violet-50 hover:text-violet-600 dark:hover:bg-white/10 transition-colors">
                                <MoreVertical className="h-4 w-4" />
                              </button>
                            }
                            items={[
                              { label: t('apps.tracker.viewDetails'), icon: <Eye className="h-4 w-4 text-violet-500" />, onClick: () => handleView(app) },
                              ...(app.status === 'invited' || app.status === 'interview'
                                ? [{
                                    label: t('apps.tracker.startAiInterview'),
                                    icon: <PlayCircle className="h-4 w-4 text-emerald-500" />,
                                    onClick: () => navigate(`/interviews/room/${app.id}`),
                                  }]
                                : []),
                              ...(app.status !== 'withdrawn'
                                ? [{
                                    label: withdrawingId === app.id ? t('apps.tracker.withdrawing') : t('apps.tracker.withdrawApplication'),
                                    icon: <XCircle className="h-4 w-4" />,
                                    onClick: () => handleWithdraw(app),
                                    danger: true,
                                    disabled: !!withdrawingId,
                                  }]
                                : []),
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
        </Card>

        {/* Application Overview Sidebar */}
        <Card className="p-6 border-0 shadow-sm bg-white dark:bg-white/[0.03] lg:sticky lg:top-20">
          <div className="flex items-center gap-2.5 mb-6">
            <div className="h-9 w-9 rounded-xl bg-violet-100 dark:bg-violet-500/15 flex items-center justify-center">
              <PieChart className="h-4.5 w-4.5 text-violet-600 dark:text-violet-400" />
            </div>
            <h3 className="text-base font-bold text-gray-900 dark:text-white">{t('apps.overview')}</h3>
          </div>

          {/* Donut Chart */}
          <div className="flex items-center justify-center mb-6">
            <div className="relative h-44 w-44">
              <svg className="h-44 w-44 -rotate-90" viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="42" fill="none" stroke="currentColor" strokeWidth="10" className="text-gray-100 dark:text-white/5" />
                {segments.map((seg) => {
                  if (seg.value === 0) return null;
                  const length = (seg.value / total) * circumference;
                  const dasharray = `${length} ${circumference - length}`;
                  const dashoffset = -offsetAcc;
                  offsetAcc += length;
                  return (
                    <circle
                      key={seg.key}
                      cx="50" cy="50" r="42"
                      fill="none"
                      stroke={seg.color}
                      strokeWidth="10"
                      strokeDasharray={dasharray}
                      strokeDashoffset={dashoffset}
                      strokeLinecap="round"
                    />
                  );
                })}
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-3xl font-extrabold text-gray-900 dark:text-white">{total}</span>
                <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">{t('apps.total')}</span>
              </div>
            </div>
          </div>

          {/* Legend */}
          <div className="space-y-3">
            {[
              { label: t('apps.legend.applied'), color: 'bg-indigo-500', value: counts.applied },
              { label: t('apps.legend.invited'), color: 'bg-violet-500', value: counts.invited },
              { label: t('apps.legend.interview'), color: 'bg-emerald-500', value: counts.interview },
              { label: t('apps.legend.review'), color: 'bg-amber-500', value: counts.in_review },
              { label: t('apps.legend.rejected'), color: 'bg-red-500', value: counts.rejected },
            ].map((row) => (
              <div key={row.label} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className={cn('h-2.5 w-2.5 rounded-full', row.color)} />
                  <span className="text-sm text-gray-600 dark:text-gray-300">{row.label}</span>
                </div>
                <span className="text-sm font-bold text-gray-900 dark:text-white">{row.value}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
