import { useState, useMemo, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { motion } from 'framer-motion';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { customToast } from '@/shared/components/ui/toast';
import { useLanguage } from '@/contexts/language-context';
import { cn } from '@/utils/cn';
import { candidatesService } from '@/services/candidates.service';
import { jobsService } from '@/services/jobs.service';
import { SourceBadge } from '@/shared/components/source-badge';
import {
  Search,
  Loader2,
  Send,
  XCircle,
  Star,
  BarChart3,
  CheckSquare,
  Square,
} from 'lucide-react';

const AVATAR_COLORS = [
  'bg-gradient-to-br from-emerald-500 to-teal-600',
  'bg-gradient-to-br from-violet-500 to-purple-600',
  'bg-gradient-to-br from-blue-500 to-indigo-600',
  'bg-gradient-to-br from-pink-500 to-rose-600',
  'bg-gradient-to-br from-amber-500 to-orange-600',
  'bg-gradient-to-br from-cyan-500 to-blue-600',
];

function aiScoreColor(score: number) {
  if (score >= 80) return 'text-emerald-600 dark:text-emerald-400';
  if (score >= 65) return 'text-amber-500';
  return 'text-red-500';
}

function avatarColorFor(name: string) {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

function initials(name: string) {
  return name.split(' ').map(s => s[0]).join('').slice(0, 2).toUpperCase();
}

function CandidateAvatar({ app }: { app: any }) {
  const [broken, setBroken] = useState(false);
  const name = app.candidate_name || app.full_name || 'U';
  const photo = app.photo_url || app.avatar_url;
  if (photo && !broken) {
    return (
      <img
        src={photo}
        alt={name}
        className="h-9 w-9 rounded-full object-cover shrink-0"
        onError={() => setBroken(true)}
      />
    );
  }
  return (
    <div className={cn('flex h-9 w-9 items-center justify-center rounded-full text-white text-xs font-bold shrink-0', avatarColorFor(name))}>
      {initials(name)}
    </div>
  );
}

function statusBadgeClass(status: string, displayStatus?: string) {
  const s = displayStatus || status;
  if (s === 'hired') return 'bg-violet-50 text-violet-600 dark:bg-violet-500/10 dark:text-violet-400';
  if (s === 'interviewing' || s === 'interview') return 'bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400';
  if (s === 'invited') return 'bg-indigo-50 text-indigo-600 dark:bg-indigo-500/10 dark:text-indigo-400';
  if (s === 'shortlisted') return 'bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400';
  if (s === 'rejected') return 'bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-400';
  if (s === 'offer_declined') return 'bg-rose-50 text-rose-600 dark:bg-rose-500/10 dark:text-rose-400';
  if (s === 'active') return 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400';
  return 'bg-gray-100 text-gray-600 dark:bg-white/10 dark:text-gray-400';
}

function interviewInfoFor(app: any, t: (k: string) => string): { label: string; cls: string } {
  const state = app.interview_state || app.interview_entity?.interview_state;
  if (state === 'completed' || state === 'flagged') return { label: t('common.completed'), cls: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400' };
  if (state === 'in_progress') return { label: t('iv.tab.inProgress'), cls: 'bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400' };
  if (state === 'invited') return { label: t('candidates.scheduled'), cls: 'bg-indigo-50 text-indigo-600 dark:bg-indigo-500/10 dark:text-indigo-400' };
  if (state === 'paused') return { label: t('common.pending'), cls: 'bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400' };
  if (state === 'expired') return { label: t('common.expired'), cls: 'bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-400' };
  if (state === 'not_started') return { label: t('recruiter.dash.stage.applied'), cls: 'bg-gray-100 text-gray-600 dark:bg-white/10 dark:text-gray-400' };
  return { label: '—', cls: 'bg-gray-100 text-gray-500 dark:bg-white/5 dark:text-gray-500' };
}

function formatDate(value?: string | null) {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return '—';
  }
}

export default function ApplicationsPage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const [search, setSearch] = useState('');
  const [debouncedQ, setDebouncedQ] = useState('');
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [jobFilter, setJobFilter] = useState<number | undefined>(() => {
    const jp = searchParams.get('job_id');
    return jp ? Number(jp) : undefined;
  });
  const [statusFilter, setStatusFilter] = useState<string | undefined>(() => searchParams.get('status') || undefined);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [inviteThreshold, setInviteThreshold] = useState(70);

  const urlStatus = searchParams.get('status') || undefined;
  useEffect(() => {
    if (urlStatus !== statusFilter) {
      setStatusFilter(urlStatus);
      setPage(1);
    }
  }, [urlStatus]);

  const { data, isLoading } = useQuery({
    queryKey: ['recruiter-applications', { page, jobFilter, status: statusFilter, q: debouncedQ }],
    queryFn: () => candidatesService.getApplications({ page, per_page: 20, job_id: jobFilter, status: statusFilter, q: debouncedQ || undefined }),
  });

  const { data: myJobs } = useQuery({
    queryKey: ['recruiter-my-jobs'],
    queryFn: () => jobsService.getJobs({ per_page: 100 }),
    staleTime: 60_000,
  });

  const items = data?.items ?? [];
  const pagination = data?.pagination ?? { total: 0, page: 1, per_page: 20 };

  const aiLabelFor = (score: number) => {
    if (score >= 80) return t('candidates.fit.strong');
    if (score >= 65) return t('candidates.fit.good');
    if (score >= 50) return t('candidates.fit.fair');
    return t('candidates.fit.needsReview');
  };

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setDebouncedQ(search.trim()), 300);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [search]);

  useEffect(() => {
    setPage(1);
  }, [debouncedQ]);

  useEffect(() => {
    setPage(1);
  }, [jobFilter]);

  useEffect(() => {
    setSelected(new Set());
  }, [jobFilter, page]);

  const eligibleForInterview = (a: any) => {
    const s = a.status;
    return !['rejected', 'hired', 'withdrawn', 'offer_declined'].includes(s);
  };

  const selectedIds = useMemo(() => Array.from(selected), [selected]);
  const allVisibleSelected = items.length > 0 && items.every((a) => selected.has(a.id));

  const toggleAll = () => {
    setSelected(allVisibleSelected ? new Set() : new Set(items.map((a) => a.id)));
  };

  const toggleOne = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const inviteMutation = useMutation({
    mutationFn: (ids: Array<string | number>) => candidatesService.inviteInterviews(ids),
    onSuccess: (res: any) => {
      const invitedCount = Array.isArray(res?.invited) ? res.invited.length : 0;
      customToast({
        type: 'success',
        title: t('recruiter.bulkInvite.toastSentTitle'),
        message: res?.message || `${invitedCount} ${t('apps.bulkInvite.invitedCount')}`,
        duration: 6000,
      });
      queryClient.invalidateQueries({ queryKey: ['recruiter-applications'] });
      setSelected(new Set());
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail || t('apps.bulkInvite.inviteError');
      customToast({ type: 'error', title: t('common.status'), message: detail });
    },
  });

  const rejectMutation = useMutation({
    mutationFn: (ids: Array<string | number>) => candidatesService.bulkUpdateStatus(ids, 'rejected'),
    onSuccess: () => {
      customToast({ type: 'success', title: t('candidates.tab.rejected'), message: t('apps.bulkReject.success') });
      queryClient.invalidateQueries({ queryKey: ['recruiter-applications'] });
      setSelected(new Set());
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail || t('apps.bulkReject.error');
      customToast({ type: 'error', title: t('common.status'), message: detail });
    },
  });

  const shortlistMutation = useMutation({
    mutationFn: (ids: Array<string | number>) => candidatesService.bulkUpdateStatus(ids, 'shortlisted'),
    onSuccess: () => {
      customToast({ type: 'success', title: t('candidates.tab.shortlisted'), message: t('apps.bulkShortlist.success') });
      queryClient.invalidateQueries({ queryKey: ['recruiter-applications'] });
      setSelected(new Set());
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail || t('apps.bulkShortlist.error');
      customToast({ type: 'error', title: t('common.status'), message: detail });
    },
  });

  const qualifiedMutation = useMutation({
    mutationFn: (jobId: number) => candidatesService.inviteQualified(jobId, inviteThreshold),
    onSuccess: (res: any) => {
      customToast({
        type: 'success',
        title: t('recruiter.bulkInvite.toastSentTitle'),
        message: res?.message || t('apps.qualifiedInvite.success'),
        duration: 6000,
      });
      queryClient.invalidateQueries({ queryKey: ['recruiter-applications'] });
      setSelected(new Set());
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail || t('apps.qualifiedInvite.error');
      customToast({ type: 'error', title: t('common.status'), message: detail });
    },
  });

  const singleInvite = (id: string) => {
    const app = items.find((a: any) => String(a.id) === String(id));
    if (app && !eligibleForInterview(app)) {
      customToast({ type: 'warning', title: t('common.status'), message: t('apps.bulkInvite.notEligible') });
      return;
    }
    inviteMutation.mutate([id]);
  };

  const jobOptions: any[] = myJobs?.items ?? [];
  const busy = inviteMutation.isPending || rejectMutation.isPending || shortlistMutation.isPending || qualifiedMutation.isPending;

  return (
    <div className="space-y-6">
      <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-gray-900 dark:text-white tracking-tight">{t('nav.recruiter_applications')}</h1>
          <p className="mt-2 text-sm sm:text-base text-gray-500 dark:text-gray-400">{t('candidates.subtitle')}</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t('common.search')}
            className="w-full pl-10 pr-4 py-2.5 rounded-2xl bg-white dark:bg-white/[0.04] border border-gray-200 dark:border-white/10 text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-violet-500/30 focus:border-violet-500 transition-all"
          />
        </div>
        <select
          value={jobFilter ?? ''}
          onChange={(e) => { setJobFilter(e.target.value ? Number(e.target.value) : undefined); setPage(1); }}
          className="px-4 py-2.5 rounded-2xl bg-white dark:bg-white/[0.04] border border-gray-200 dark:border-white/10 text-sm text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-2 focus:ring-violet-500/30"
        >
          <option value="">{t('candidates.allJobs')}</option>
          {jobOptions.map((j: any) => (
            <option key={j.id} value={j.id}>{j.title}</option>
          ))}
        </select>
        <span className="text-sm text-gray-400">{(pagination.total ?? 0).toLocaleString()} {t('candidates.candidatesLabel')}</span>
      </div>

      {/* Bulk actions */}
      <div className="flex flex-wrap items-center gap-2">
        {selectedIds.length > 0 && (
          <span className="text-sm font-semibold text-violet-600 dark:text-violet-400">{selectedIds.length} {t('common.selected')}</span>
        )}
        <Button
          variant="outline"
          size="sm"
          disabled={selectedIds.length === 0 || busy}
          onClick={() => inviteMutation.mutate(selectedIds)}
        >
          <Send className="h-4 w-4" /> {t('topbar.schedule_interview')}
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={selectedIds.length === 0 || busy}
          onClick={() => rejectMutation.mutate(selectedIds)}
        >
          <XCircle className="h-4 w-4" /> {t('common.delete')}
        </Button>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={!jobFilter || busy}
            title={jobFilter ? t('apps.qualifiedInvite.title') : t('apps.qualifiedInvite.selectJobFirst')}
            onClick={() => jobFilter && qualifiedMutation.mutate(jobFilter)}
          >
            <BarChart3 className="h-4 w-4" /> {t('candidates.aiParse')}
          </Button>
          <label className="flex items-center gap-1.5 text-xs font-medium text-gray-500 dark:text-gray-400">
            {t('apps.filter.minScore')}
            <input
              type="number"
              min={0}
              max={100}
              value={inviteThreshold}
              onChange={(e) => setInviteThreshold(Number(e.target.value))}
              disabled={!jobFilter}
              className="w-16 px-2 py-1.5 rounded-lg bg-white dark:bg-white/[0.04] border border-gray-200 dark:border-white/10 text-sm text-gray-700 dark:text-gray-300 disabled:opacity-50"
              title={t('apps.filter.minThreshold')}
            />
          </label>
        </div>
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="flex items-center justify-center py-20"><Loader2 className="h-8 w-8 animate-spin text-violet-600" /></div>
      ) : items.length === 0 ? (
        <Card className="p-10 text-center">
          <p className="text-sm text-gray-500 dark:text-gray-400">{t('common.noData')}</p>
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-100 dark:border-white/5">
                  <th className="text-left px-4 py-3 w-10">
                    <button onClick={toggleAll} className="text-gray-400 hover:text-violet-600 transition-colors" title={t('apps.filter.selectAll')}>
                      {allVisibleSelected ? <CheckSquare className="h-4 w-4" /> : <Square className="h-4 w-4" />}
                    </button>
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{t('candidates.col.candidate')}</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{t('candidates.col.jobs')}</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{t('recruiter.interviewAnalysis.cvMatch')}</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{t('common.status')}</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{t('candidates.col.interview')}</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{t('recruiter.chatbotLeads.colSource')}</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{t('common.date')}</th>
                  <th className="text-right px-4 py-3"><span className="sr-only">{t('common.actions')}</span></th>
                </tr>
              </thead>
              <tbody>
                {items.map((app: any, i: number) => {
                  const cvMatch = app.cv_score ?? app.score ?? 0;
                  const isSelected = selected.has(app.id);
                  const iv = interviewInfoFor(app, t);
                  return (
                    <motion.tr
                      key={app.id}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: i * 0.02 }}
                      className={cn(
                        'border-b border-gray-50 dark:border-white/[0.02] hover:bg-gray-50 dark:hover:bg-white/[0.02] transition-colors',
                        isSelected && 'bg-violet-50/60 dark:bg-violet-500/[0.06]',
                      )}
                    >
                      <td className="px-4 py-3">
                        <button onClick={() => toggleOne(app.id)} className="text-gray-400 hover:text-violet-600 transition-colors">
                          {isSelected ? <CheckSquare className="h-4 w-4" /> : <Square className="h-4 w-4" />}
                        </button>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <CandidateAvatar app={app} />
                          <div>
                            <p className="text-sm font-medium text-gray-900 dark:text-white">{app.candidate_name || app.full_name || t('role.candidate')}</p>
                            <p className="text-xs text-gray-500">{app.candidate_email || app.email || ''}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <p className="text-sm text-gray-700 dark:text-gray-300">{app.job_title || app.declared_role || '—'}</p>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <span className={cn('text-sm font-bold', aiScoreColor(cvMatch))}>{cvMatch}</span>
                          <span className="text-xs text-gray-400">{aiLabelFor(cvMatch)}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={cn('inline-flex px-2.5 py-0.5 rounded-full text-[11px] font-semibold uppercase tracking-wider', statusBadgeClass(app.status, app.display_status))}>
                          {app.display_status === 'offer_declined' ? t('candidates.declined') : app.display_status || app.status || t('recruiter.dash.stage.applied')}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={cn('inline-flex px-2.5 py-0.5 rounded-full text-[11px] font-semibold uppercase tracking-wider', iv.cls)}>
                          {iv.label}
                        </span>
                      </td>
                      <td className="px-4 py-3"><SourceBadge source={app.source} /></td>
                      <td className="px-4 py-3 text-sm text-gray-500">{formatDate(app.created_at)}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1.5">
                          <Button
                            variant="primary"
                            size="xs"
                            onClick={() => navigate(`/candidates/${app.id}?tab=cv`)}
                            title={t('apps.actions.review')}
                            className="whitespace-nowrap"
                          >
                            {t('common.view')}
                          </Button>
                          <button
                            disabled={busy}
                            onClick={() => singleInvite(app.id)}
                            title={t('topbar.schedule_interview')}
                            className="p-1.5 rounded-lg hover:bg-violet-50 hover:text-violet-600 dark:hover:bg-white/5 text-gray-400 transition-colors disabled:opacity-50"
                          >
                            <Send className="h-4 w-4" />
                          </button>
                          <button
                            disabled={busy}
                            onClick={() => rejectMutation.mutate([app.id])}
                            title={t('common.delete')}
                            className="p-1.5 rounded-lg hover:bg-red-50 hover:text-red-600 dark:hover:bg-white/5 text-gray-400 transition-colors disabled:opacity-50"
                          >
                            <XCircle className="h-4 w-4" />
                          </button>
                          <button
                            disabled={busy}
                            onClick={() => shortlistMutation.mutate([app.id])}
                            title={t('candidates.tab.shortlisted')}
                            className="p-1.5 rounded-lg hover:bg-amber-50 hover:text-amber-600 dark:hover:bg-white/5 text-gray-400 transition-colors disabled:opacity-50"
                          >
                            <Star className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => navigate(`/recruiter/interview-analysis?id=${app.id}`)}
                            title={t('nav.analytics')}
                            className="p-1.5 rounded-lg hover:bg-violet-50 hover:text-violet-600 dark:hover:bg-white/5 text-gray-400 transition-colors"
                          >
                            <BarChart3 className="h-4 w-4" />
                          </button>
                        </div>
                      </td>
                    </motion.tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {pagination.total_pages && pagination.total_pages > 1 ? (
            <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100 dark:border-white/5">
              <span className="text-xs text-gray-500">{t('common.showing')} {pagination.page} {t('common.of')} {pagination.total_pages}</span>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>{t('common.previous')}</Button>
                <Button variant="outline" size="sm" disabled={page >= (pagination.total_pages ?? 1)} onClick={() => setPage(p => p + 1)}>{t('common.next')}</Button>
              </div>
            </div>
          ) : null}
        </Card>
      )}
    </div>
  );
}