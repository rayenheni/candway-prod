import { useState, useMemo, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router';
import { motion } from 'framer-motion';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useCandidates } from '@/shared/hooks';
import { Card } from '@/shared/components/ui/card';
import { customToast } from '@/shared/components/ui/toast';
import { useLanguage } from '@/contexts/language-context';
import { cn } from '@/utils/cn';
import { candidatesService } from '@/services/candidates.service';
import { messagesService } from '@/services/messages.service';
import { jobsService } from '@/services/jobs.service';
import { SourceBadge } from '@/shared/components/source-badge';
import {
  Search,
  Loader2,
  Eye,
  MessageCircle,
  Inbox,
  Send,
  XCircle,
  CheckSquare,
  Square,
  RefreshCw,
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

function CandidateAvatar({ candidate }: { candidate: any }) {
  const [broken, setBroken] = useState(false);
  const name = candidate.candidate_name || candidate.full_name || 'U';
  const photo = candidate.photo_url || candidate.avatar_url;
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

function timeAgo(iso: string) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const diff = Date.now() - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return d.toLocaleDateString();
}

export default function CandidatesListPage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [debouncedQ, setDebouncedQ] = useState('');
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [jobFilter, setJobFilter] = useState<number | undefined>();
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [inviteThreshold, setInviteThreshold] = useState(70);

  const aiLabelFor = (score: number) => {
    if (score >= 80) return t('candidates.fit.strong');
    if (score >= 65) return t('candidates.fit.good');
    if (score >= 50) return t('candidates.fit.fair');
    return t('candidates.fit.needsReview');
  };

  const { data, isLoading } = useCandidates({
    page,
    per_page: 20,
    q: debouncedQ || undefined,
    status: statusFilter,
    job_id: jobFilter,
  });

  const { data: myJobs } = useQuery({
    queryKey: ['recruiter-my-jobs'],
    queryFn: () => jobsService.getJobs({ per_page: 100 }),
    staleTime: 60_000,
  });

  useEffect(() => {
    setSelected(new Set());
  }, [statusFilter, jobFilter, page]);

  const items: any[] = (data as any)?.items ?? [];
  const pagination = (data as any)?.pagination ?? { total: 0, page: 1, per_page: 20 };
  const totalPages = pagination.total_pages ?? (Math.ceil(pagination.total / pagination.per_page) || 1);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setDebouncedQ(search.trim()), 300);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [search]);

  useEffect(() => {
    setPage(1);
  }, [debouncedQ]);

  const eligibleForInterview = (c: any) => {
    const s = c.status;
    return !['rejected', 'hired', 'withdrawn', 'offer_declined'].includes(s);
  };

  const selectedIds = useMemo(() => Array.from(selected), [selected]);
  const allVisibleSelected = items.length > 0 && items.every((c) => selected.has(c.id));

  const toggleAll = () => {
    setSelected(allVisibleSelected ? new Set() : new Set(items.map((c) => c.id)));
  };

  const toggleOne = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const inviteMutation = useMutation({
    mutationFn: (ids: number[]) => candidatesService.inviteInterviews(ids),
    onSuccess: (res: any) => {
      const invitedCount = Array.isArray(res?.invited) ? res.invited.length : 0;
      customToast({
        type: 'success',
        title: t('recruiter.bulkInvite.toastSentTitle'),
        message: res?.message || `${invitedCount} candidate(s) invited.`,
        duration: 6000,
      });
      queryClient.invalidateQueries({ queryKey: ['candidates'] });
      setSelected(new Set());
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail || 'Could not send interview invites.';
      customToast({ type: 'error', title: t('common.status'), message: detail });
    },
  });

  const rejectMutation = useMutation({
    mutationFn: (ids: number[]) => candidatesService.bulkUpdateStatus(ids, 'rejected'),
    onSuccess: () => {
      customToast({ type: 'success', title: t('candidates.tab.rejected'), message: 'Selected candidate(s) moved to Rejected.' });
      queryClient.invalidateQueries({ queryKey: ['candidates'] });
      setSelected(new Set());
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail || 'Could not reject the selected candidates.';
      customToast({ type: 'error', title: t('common.status'), message: detail });
    },
  });

  const qualifiedMutation = useMutation({
    mutationFn: (jobId: number) => candidatesService.inviteQualified(jobId, inviteThreshold),
    onSuccess: (res: any) => {
      customToast({
        type: 'success',
        title: t('recruiter.bulkInvite.toastSentTitle'),
        message: res?.message || 'Qualified candidates invited to AI interviews.',
        duration: 6000,
      });
      queryClient.invalidateQueries({ queryKey: ['candidates'] });
      setSelected(new Set());
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail || 'Could not invite qualified candidates.';
      customToast({ type: 'error', title: t('common.status'), message: detail });
    },
  });

  const messageMutation = useMutation({
    mutationFn: (candidate: any) =>
      messagesService.createConversation(
        candidate.user_id ? [candidate.user_id] : [],
        `Hi ${candidate.candidate_name?.split(' ')[0] || 'there'}, I found your profile on Candway.`,
      ),
    onSuccess: () => {
      customToast({ type: 'success', title: t('msg.title'), message: 'Message them from your inbox.' });
      navigate('/messages');
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail || 'Could not start a conversation with this candidate.';
      customToast({ type: 'error', title: t('common.status'), message: detail });
    },
  });

  const jobOptions: any[] = myJobs?.items ?? [];
  const busy =
    inviteMutation.isPending || rejectMutation.isPending || qualifiedMutation.isPending;

  return (
    <div className="space-y-6">
      <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-gray-900 dark:text-white tracking-tight">{t('candidates.title')}</h1>
          <p className="mt-2 text-sm sm:text-base text-gray-500 dark:text-gray-400">{t('candidates.subtitle')}</p>
        </div>
      </div>

      {/* Search & Filters */}
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
          value={statusFilter || ''}
          onChange={(e) => { setStatusFilter(e.target.value || undefined); setPage(1); }}
          className="px-4 py-2.5 rounded-2xl bg-white dark:bg-white/[0.04] border border-gray-200 dark:border-white/10 text-sm text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-2 focus:ring-violet-500/30"
        >
          <option value="">{t('candidates.allStages')}</option>
          <option value="applied">{t('recruiter.dash.stage.applied')}</option>
          <option value="screening">{t('recruiter.dash.stage.screening')}</option>
          <option value="shortlisted">{t('candidates.tab.shortlisted')}</option>
          <option value="interviewing">{t('recruiter.dash.stage.interview')}</option>
          <option value="hired">{t('recruiter.dash.stage.hired')}</option>
          <option value="rejected">{t('candidates.tab.rejected')}</option>
        </select>
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
      </div>

      {/* Bulk Actions */}
      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
            {selectedIds.length > 0 ? (
              <span className="font-semibold">{selectedIds.length} {t('common.selected')}</span>
            ) : (
              <span className="text-gray-400">{t('candidates.moreFilters')}</span>
            )}
          </div>
          <div className="flex-1" />
          <button
            disabled={busy || selectedIds.length === 0}
            onClick={() => inviteMutation.mutate(selectedIds)}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-violet-600 text-white text-sm font-semibold shadow-sm hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {inviteMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            {t('topbar.schedule_interview')}
          </button>
          <button
            disabled={busy || selectedIds.length === 0}
            onClick={() => rejectMutation.mutate(selectedIds)}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-400 text-sm font-semibold hover:bg-red-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <XCircle className="h-4 w-4" />
            {t('common.delete')}
          </button>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">Min %</span>
            <input
              type="number"
              min={0}
              max={100}
              value={inviteThreshold}
              onChange={(e) => setInviteThreshold(Number(e.target.value) || 0)}
              className="w-16 px-2 py-1.5 rounded-lg bg-white dark:bg-white/[0.04] border border-gray-200 dark:border-white/10 text-sm text-gray-700 dark:text-gray-300"
            />
          </div>
          <button
            disabled={busy || !jobFilter}
            onClick={() => jobFilter && qualifiedMutation.mutate(jobFilter)}
            title={jobFilter ? 'Invite qualified candidates' : 'Select a job first'}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 text-white text-sm font-semibold shadow-sm hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {qualifiedMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            {t('candidates.aiParse')}
          </button>
        </div>
      </Card>

      {/* Table */}
      {isLoading ? (
        <div className="flex items-center justify-center py-20"><Loader2 className="h-8 w-8 animate-spin text-violet-600" /></div>
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-100 dark:border-white/5">
                  <th className="text-left px-4 py-3 w-10">
                    <button onClick={toggleAll} className="text-gray-400 hover:text-violet-600 transition-colors" title="Select all visible">
                      {allVisibleSelected ? <CheckSquare className="h-4 w-4" /> : <Square className="h-4 w-4" />}
                    </button>
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{t('candidates.col.candidate')}</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{t('candidates.col.jobs')}</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{t('recruiter.interviewAnalysis.overallScore')}</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{t('cprofile.skillsCompetencies')}</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{t('recruiter.chatbotLeads.colSource')}</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{t('candidates.col.activity')}</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{t('common.status')}</th>
                  <th className="text-right px-4 py-3"><span className="sr-only">{t('common.actions')}</span></th>
                </tr>
              </thead>
              <tbody>
                {items.map((candidate: any, i: number) => {
                  const score = candidate.best_score ?? candidate.score ?? candidate.cv_score ?? 0;
                  const isSelected = selected.has(candidate.id);
                  const canInvite = eligibleForInterview(candidate);
                  const skills: string[] = Array.isArray(candidate.skills) ? candidate.skills.slice(0, 3) : [];
                  const targetRole = candidate.role || candidate.job_title || '—';
                  return (
                    <motion.tr
                      key={candidate.id}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: i * 0.02 }}
                      className={cn(
                        'border-b border-gray-50 dark:border-white/[0.02] hover:bg-gray-50 dark:hover:bg-white/[0.02] transition-colors',
                        isSelected && 'bg-violet-50/60 dark:bg-violet-500/[0.06]',
                      )}
                    >
                      <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                        <button onClick={() => toggleOne(candidate.id)} className="text-gray-400 hover:text-violet-600 transition-colors">
                          {isSelected ? <CheckSquare className="h-4 w-4" /> : <Square className="h-4 w-4" />}
                        </button>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <CandidateAvatar candidate={candidate} />
                          <div>
                            <p className="text-sm font-medium text-gray-900 dark:text-white">{candidate.candidate_name || candidate.full_name || t('role.candidate')}</p>
                            <p className="text-xs text-gray-500">{candidate.email || ''}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <p className="text-sm text-gray-700 dark:text-gray-300">{targetRole}</p>
                        {candidate.role && candidate.job_title && candidate.role !== candidate.job_title && (
                          <p className="text-xs text-gray-400">{candidate.job_title}</p>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <span className={cn('text-sm font-bold', aiScoreColor(score))}>{score || '—'}</span>
                          {score > 0 && <span className="text-xs text-gray-400">{aiLabelFor(score)}</span>}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        {skills.length > 0 ? (
                          <div className="flex flex-wrap gap-1">
                            {skills.map((s) => (
                              <span key={s} className="px-2 py-0.5 rounded-md bg-gray-100 dark:bg-white/10 text-[11px] text-gray-600 dark:text-gray-300">{s}</span>
                            ))}
                            {(candidate.skills || []).length > 3 && (
                              <span className="text-[11px] text-gray-400">+{(candidate.skills).length - 3}</span>
                            )}
                          </div>
                        ) : (
                          <span className="text-xs text-gray-400">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3"><SourceBadge source={candidate.source} /></td>
                      <td className="px-4 py-3 text-sm text-gray-500">{timeAgo(candidate.last_activity || candidate.created_at)}</td>
                      <td className="px-4 py-3">
                        <span className={cn(
                          'inline-flex px-2.5 py-0.5 rounded-full text-[11px] font-semibold uppercase tracking-wider',
                          candidate.status === 'hired' ? 'bg-violet-50 text-violet-600 dark:bg-violet-500/10 dark:text-violet-400' :
                          candidate.status === 'interviewing' || candidate.status === 'interview' ? 'bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400' :
                          candidate.status === 'invited' ? 'bg-indigo-50 text-indigo-600 dark:bg-indigo-500/10 dark:text-indigo-400' :
                          candidate.status === 'shortlisted' ? 'bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400' :
                          candidate.status === 'rejected' ? 'bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-400' :
                          candidate.status === 'offer_declined' ? 'bg-rose-50 text-rose-600 dark:bg-rose-500/10 dark:text-rose-400' :
                          candidate.status === 'active' ? 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400' :
                          'bg-gray-100 text-gray-600 dark:bg-white/10 dark:text-gray-400'
                        )}>
                          {candidate.display_status === 'offer_declined' ? t('candidates.declined')
                            : candidate.display_status || candidate.status || t('recruiter.dash.stage.applied')}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1">
                          {canInvite && (
                            <button
                              disabled={busy}
                              onClick={(e) => { e.stopPropagation(); inviteMutation.mutate([candidate.id]); }}
                              title={t('topbar.schedule_interview')}
                              className="p-1.5 rounded-lg hover:bg-violet-50 hover:text-violet-600 dark:hover:bg-white/5 text-gray-400 transition-colors disabled:opacity-50"
                            >
                              <Send className="h-4 w-4" />
                            </button>
                          )}
                          <button
                            onClick={(e) => { e.stopPropagation(); messageMutation.mutate(candidate); }}
                            disabled={!candidate.user_id || messageMutation.isPending}
                            title={t('cprofile.messageCandidate')}
                            className="p-1.5 rounded-lg hover:bg-blue-50 hover:text-blue-600 dark:hover:bg-white/5 text-gray-400 transition-colors disabled:opacity-40"
                          >
                            <MessageCircle className="h-4 w-4" />
                          </button>
                          <button
                            onClick={(e) => { e.stopPropagation(); navigate(candidate.job_id ? `/recruiter/applications?job_id=${candidate.job_id}` : '/recruiter/applications'); }}
                            title={t('nav.recruiter_applications')}
                            className="p-1.5 rounded-lg hover:bg-emerald-50 hover:text-emerald-600 dark:hover:bg-white/5 text-gray-400 transition-colors"
                          >
                            <Inbox className="h-4 w-4" />
                          </button>
                          <button
                            onClick={(e) => { e.stopPropagation(); navigate(candidate.candidate_id ? `/candidates/c/${candidate.candidate_id}` : `/candidates/${candidate.id}`); }}
                            title={t('common.view')}
                            className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-white/5 text-gray-400 transition-colors"
                          >
                            <Eye className="h-4 w-4" />
                          </button>
                        </div>
                      </td>
                    </motion.tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100 dark:border-white/5">
              <p className="text-sm text-gray-500">{t('common.showing')} {(page - 1) * pagination.per_page + 1}–{Math.min(page * pagination.per_page, pagination.total)} {t('common.of')} {pagination.total}</p>
              <div className="flex gap-1">
                <button disabled={page <= 1} onClick={() => setPage(p => Math.max(1, p - 1))} className="px-3 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-white/10 disabled:opacity-50">{t('common.previous')}</button>
                <button disabled={page >= totalPages} onClick={() => setPage(p => Math.min(totalPages, p + 1))} className="px-3 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-white/10 disabled:opacity-50">{t('common.next')}</button>
              </div>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}