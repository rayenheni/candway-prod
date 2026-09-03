import { useState, useMemo, useCallback } from 'react';
import { Link } from 'react-router';
import { useQueryClient } from '@tanstack/react-query';
import { useJobs } from '@/shared/hooks';
import { Card } from '@/shared/components/ui/card';
import { Badge, type BadgeVariant } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { customToast } from '@/shared/components/ui/toast';
import { useLanguage } from '@/contexts/language-context';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  ConfirmDialog,
} from '@/shared/components/ui/dialog';
import { jobsService } from '@/services/jobs.service';
import {
  Loader2, Plus, Search, MapPin, Eye, Copy, Pencil, Trash2,
  BarChart3, Power, Download, Users, Briefcase, RefreshCw,
} from 'lucide-react';

const statusVariantMap: Record<string, BadgeVariant> = {
  published: 'success',
  draft: 'default',
  closed: 'danger',
  archived: 'outline',
};

interface RowJob {
  id: number;
  title?: string | null;
  company?: string | null;
  location?: string | null;
  salary_range?: string | null;
  type?: string | null;
  status?: string | null;
  views?: number | null;
  applicant_count?: number | null;
  created_at?: string | null;
}

function formatDate(value?: string | null): string {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

function cn(...classes: (string | boolean | undefined | null)[]): string {
  return classes.filter(Boolean).join(' ');
}

export default function JobsListPage() {
  const { t } = useLanguage();
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState('all');

  const { data, isLoading } = useJobs();
  const queryClient = useQueryClient();

  const jobsList: RowJob[] = (data as any)?.items ?? [];

  const [detailJob, setDetailJob] = useState<RowJob | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailData, setDetailData] = useState<any>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [reportJob, setReportJob] = useState<RowJob | null>(null);
  const [reportOpen, setReportOpen] = useState(false);
  const [reportData, setReportData] = useState<any>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [exporting, setExporting] = useState(false);

  const [deleteJob, setDeleteJob] = useState<RowJob | null>(null);
  const [deleting, setDeleting] = useState(false);

  const [busyId, setBusyId] = useState<number | null>(null);

  const getStatusLabel = (status?: string | null) => {
    if (status === 'published') return t('jobs.status.published');
    if (status === 'draft') return t('jobs.status.draft');
    if (status === 'closed') return t('jobs.status.closed');
    if (status === 'archived') return t('jobs.status.archived');
    return status || t('jobs.status.draft');
  };

  const refresh = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['jobs'] });
  }, [queryClient]);

  const filteredJobs = useMemo(() => {
    return jobsList.filter((job) => {
      const matchesSearch = !searchQuery ||
        job.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        job.company?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        job.location?.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesTab = activeTab === 'all' || job.status === activeTab;
      return matchesSearch && matchesTab;
    });
  }, [jobsList, searchQuery, activeTab]);

  const openDetail = async (job: RowJob) => {
    setDetailJob(job);
    setDetailOpen(true);
    setDetailData(null);
    setDetailLoading(true);
    try {
      const res = await jobsService.getJob(String(job.id));
      setDetailData(res);
    } catch (e: any) {
      customToast({ type: 'error', title: t('common.status'), message: e?.message || t('jobs.loadDetailFailed') });
    } finally {
      setDetailLoading(false);
    }
  };

  const openReport = async (job: RowJob) => {
    setReportJob(job);
    setReportOpen(true);
    setReportData(null);
    setReportLoading(true);
    try {
      const res = await jobsService.getJobReport(String(job.id));
      setReportData(res);
    } catch (e: any) {
      customToast({ type: 'error', title: t('common.status'), message: e?.message || t('jobs.loadReportFailed') });
    } finally {
      setReportLoading(false);
    }
  };

  const exportReport = async (format: 'csv' | 'pdf') => {
    if (!reportJob) return;
    setExporting(true);
    try {
      const blob = await jobsService.exportJobReport(String(reportJob.id), format);
      if (!(blob instanceof Blob)) throw new Error(t('jobs.exportInvalid'));
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `job-${reportJob.id}-report.${format}`;
      a.click();
      URL.revokeObjectURL(url);
      customToast({ type: 'success', title: t('common.status'), message: t('jobs.reportDownloaded').replace('{format}', format.toUpperCase()) });
    } catch (e: any) {
      customToast({ type: 'error', title: t('common.status'), message: e?.message || t('jobs.exportFailed') });
    } finally {
      setExporting(false);
    }
  };

  const togglePublish = async (job: RowJob) => {
    setBusyId(job.id);
    try {
      if (job.status === 'published') {
        await jobsService.closeJob(String(job.id));
        customToast({ type: 'info', title: t('common.status'), message: t('jobs.closedMsg').replace('{title}', job.title ?? '') });
      } else {
        await jobsService.publishJob(String(job.id));
        customToast({ type: 'success', title: t('common.status'), message: t('jobs.publishedMsg').replace('{title}', job.title ?? '') });
      }
      refresh();
    } catch (e: any) {
      customToast({ type: 'error', title: t('common.status'), message: e?.message || t('jobs.statusUpdateFailed') });
    } finally {
      setBusyId(null);
    }
  };

  const duplicate = async (job: RowJob) => {
    setBusyId(job.id);
    try {
      await jobsService.duplicateJob(String(job.id));
      customToast({ type: 'success', title: t('common.status'), message: t('jobs.duplicatedMsg').replace('{title}', job.title ?? '') });
      refresh();
    } catch (e: any) {
      customToast({ type: 'error', title: t('common.status'), message: e?.message || t('jobs.duplicateFailed') });
    } finally {
      setBusyId(null);
    }
  };

  const confirmDelete = async () => {
    if (!deleteJob) return;
    setDeleting(true);
    try {
      await jobsService.deleteJob(String(deleteJob.id));
      customToast({ type: 'success', title: t('common.status'), message: t('jobs.deletedMsg').replace('{title}', deleteJob.title ?? '') });
      setDeleteJob(null);
      refresh();
    } catch (e: any) {
      customToast({ type: 'error', title: t('common.status'), message: e?.message || t('jobs.deleteFailed') });
    } finally {
      setDeleting(false);
    }
  };

  const summary = reportData?.summary;
  const funnel: { stage: string; count: number; conversion: number }[] = reportData?.funnel ?? [];
  const sources: Record<string, number> = reportData?.sources ?? {};
  const recentApplicants: any[] = reportData?.recent_applicants ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-gray-900 dark:text-white tracking-tight">{t('jobs.title')}</h1>
          <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">{t('jobs.subtitle')}</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" leftIcon={<RefreshCw className="h-4 w-4" />} onClick={refresh}>{t('common.refresh')}</Button>
          <Link to="/jobs/new">
            <Button variant="primary" leftIcon={<Plus className="h-4 w-4" />}>{t('jobs.newJob')}</Button>
          </Link>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={t('common.search')}
            className="w-full pl-10 pr-4 py-2.5 rounded-2xl bg-white dark:bg-white/[0.04] border border-gray-200 dark:border-white/10 text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-violet-500/30 focus:border-violet-500 transition-all"
          />
        </div>
        <div className="flex gap-1 p-1 bg-gray-100 dark:bg-white/[0.04] rounded-2xl">
          {[
            { id: 'all', label: t('jobs.filter.all') },
            { id: 'published', label: t('jobs.filter.active') },
            { id: 'draft', label: t('jobs.status.draft') },
            { id: 'closed', label: t('jobs.status.closed') },
          ].map((tab) => (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)}
              className={cn('px-4 py-1.5 text-sm font-medium rounded-xl transition-all', activeTab === tab.id ? 'bg-white dark:bg-white/10 text-gray-900 dark:text-white shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300')}
            >{tab.label}</button>
          ))}
        </div>
      </div>

      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          {isLoading ? (
            <div className="flex items-center justify-center py-20"><Loader2 className="h-8 w-8 animate-spin text-violet-600" /></div>
          ) : (
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-gray-100 dark:border-white/10 bg-gray-50 dark:bg-white/[0.03]">
                  <th className="py-3 px-4 text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{t('jobs.col.jobTitle')}</th>
                  <th className="py-3 px-4 text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{t('common.status')}</th>
                  <th className="py-3 px-4 text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{t('jobs.col.location')}</th>
                  <th className="py-3 px-4 text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{t('jobs.col.type')}</th>
                  <th className="py-3 px-4 text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{t('jobs.col.applicants')}</th>
                  <th className="py-3 px-4 text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{t('jobs.col.views')}</th>
                  <th className="py-3 px-4 text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{t('common.date')}</th>
                  <th className="py-3 px-4 text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider text-right">{t('common.actions')}</th>
                </tr>
              </thead>
              <tbody>
                {filteredJobs.map((job) => {
                  const variant = statusVariantMap[job.status ?? ''] ?? 'default';
                  const label = getStatusLabel(job.status);
                  const isBusy = busyId === job.id;
                  return (
                    <tr key={job.id} className="border-b border-gray-50 dark:border-white/[0.02] hover:bg-purple-50/40 dark:hover:bg-white/[0.03] transition-colors">
                      <td className="py-3 px-4">
                        <button type="button" onClick={() => openDetail(job)} className="text-left group">
                          <div className="text-sm font-extrabold text-gray-900 dark:text-white group-hover:text-violet-600 dark:group-hover:text-violet-400 flex items-center gap-2">
                            <Briefcase className="h-4 w-4 text-purple-500 shrink-0" />
                            <span className="truncate max-w-[260px]">{job.title || t('cv.builder.untitled')}</span>
                          </div>
                          {job.company && <div className="text-xs text-gray-500 mt-0.5">{job.company}</div>}
                        </button>
                      </td>
                      <td className="py-3 px-4">
                        <Badge variant={variant}>{label}</Badge>
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-1.5 text-sm text-gray-500">
                          <MapPin className="h-3.5 w-3.5 shrink-0" />
                          <span className="truncate max-w-[140px]">{job.location || t('jobs.remote')}</span>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-sm text-gray-500 capitalize">{job.type ? job.type.replace('-', ' ') : '—'}</td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-1.5 text-sm font-semibold text-gray-700 dark:text-gray-300">
                          <Users className="h-3.5 w-3.5 text-violet-500" />
                          {job.applicant_count ?? 0}
                        </div>
                      </td>
                      <td className="py-3 px-4 text-sm text-gray-500">{job.views ?? 0}</td>
                      <td className="py-3 px-4 text-sm text-gray-500">{formatDate(job.created_at)}</td>
                      <td className="py-3 px-4">
                        <div className="flex items-center justify-end gap-1">
                          <button type="button" title={t('common.view')} onClick={() => openDetail(job)}
                            className="p-1.5 rounded-lg text-gray-500 hover:text-violet-600 hover:bg-violet-50 dark:hover:bg-violet-500/10 transition-colors">
                            <Eye className="h-4 w-4" />
                          </button>
                          <Link to={`/jobs/${job.id}`} title={t('common.edit')}>
                            <span className="inline-flex p-1.5 rounded-lg text-gray-500 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-500/10 transition-colors">
                              <Pencil className="h-4 w-4" />
                            </span>
                          </Link>
                          <button type="button" title={t('jobs.duplicate')} disabled={isBusy} onClick={() => duplicate(job)}
                            className="p-1.5 rounded-lg text-gray-500 hover:text-amber-600 hover:bg-amber-50 dark:hover:bg-amber-500/10 transition-colors disabled:opacity-40">
                            {isBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Copy className="h-4 w-4" />}
                          </button>
                          <button type="button" title={t('jobs.report')} onClick={() => openReport(job)}
                            className="p-1.5 rounded-lg text-gray-500 hover:text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-500/10 transition-colors">
                            <BarChart3 className="h-4 w-4" />
                          </button>
                          <button type="button" title={job.status === 'published' ? t('jobs.status.closed') : t('jobs.status.published')} disabled={isBusy} onClick={() => togglePublish(job)}
                            className={cn('p-1.5 rounded-lg transition-colors disabled:opacity-40',
                              job.status === 'published'
                                ? 'text-gray-500 hover:text-orange-600 hover:bg-orange-50 dark:hover:bg-orange-500/10'
                                : 'text-gray-500 hover:text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-500/10')}>
                            <Power className="h-4 w-4" />
                          </button>
                          <button type="button" title={t('common.delete')} onClick={() => setDeleteJob(job)}
                            className="p-1.5 rounded-lg text-gray-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-500/10 transition-colors">
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
                {filteredJobs.length === 0 && (
                  <tr>
                    <td colSpan={8} className="py-14 text-center text-gray-400">
                      <div className="flex flex-col items-center gap-2">
                        <Briefcase className="h-8 w-8" />
                        <span>{t('common.noData')}</span>
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      </Card>

      {/* Job Detail Dialog */}
      <Dialog open={detailOpen} onOpenChange={setDetailOpen}>
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>{detailJob?.title || t('jobs.title')}</DialogTitle>
            <DialogDescription>{detailJob?.company || ''}{detailJob?.location ? ` · ${detailJob.location}` : ''}</DialogDescription>
          </DialogHeader>
          {detailLoading ? (
            <div className="flex items-center justify-center py-10"><Loader2 className="h-6 w-6 animate-spin text-violet-600" /></div>
          ) : detailData ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {[
                  { label: t('jobs.col.applicants'), value: detailData.applicant_count ?? 0 },
                  { label: t('jobs.col.views'), value: detailData.views ?? 0 },
                  { label: t('common.status'), value: getStatusLabel(detailData.status) },
                  { label: t('jobs.col.type'), value: detailData.type ? String(detailData.type).replace('-', ' ') : '—' },
                ].map((item) => (
                  <div key={item.label} className="p-3 rounded-xl bg-purple-50 dark:bg-purple-500/5 border border-purple-100 dark:border-white/10">
                    <div className="text-[10px] uppercase tracking-wider text-gray-400 font-bold">{item.label}</div>
                    <div className="text-sm font-extrabold text-gray-900 dark:text-white capitalize">{item.value}</div>
                  </div>
                ))}
              </div>
              {detailData.salary_range && (
                <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-300">
                  <Briefcase className="h-4 w-4 text-emerald-500" />
                  <span className="font-medium">{t('cprofile.salary')}:</span> {detailData.salary_range}
                </div>
              )}
              {(() => {
                const skills = Array.isArray(detailData.required_skills)
                  ? detailData.required_skills
                  : typeof detailData.required_skills === 'string' && detailData.required_skills.trim()
                    ? detailData.required_skills.split(',').map((s: string) => s.trim()).filter(Boolean)
                    : [];
                return skills.length > 0 && (
                  <div>
                    <div className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">{t('cprofile.skillsCompetencies')}</div>
                    <div className="flex flex-wrap gap-1.5">
                      {skills.map((s: string, i: number) => (
                        <Badge key={i} variant="primary" size="sm">{s}</Badge>
                      ))}
                    </div>
                  </div>
                );
              })()}
              {detailData.description && (
                <div>
                  <div className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">{t('common.description')}</div>
                  <p className="text-sm text-gray-600 dark:text-gray-300 whitespace-pre-wrap max-h-48 overflow-y-auto">{detailData.description}</p>
                </div>
              )}
            </div>
          ) : (
            <div className="text-sm text-gray-400 text-center py-6">{t('common.noData')}</div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDetailOpen(false)}>{t('common.close')}</Button>
            {detailJob && (
              <Link to={`/jobs/${detailJob.id}`}>
                <Button variant="primary" leftIcon={<Pencil className="h-4 w-4" />}>{t('common.edit')}</Button>
              </Link>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Job Report Dialog */}
      <Dialog open={reportOpen} onOpenChange={setReportOpen}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-emerald-500" />
              {t('jobs.title')}: {reportJob?.title}
            </DialogTitle>
            <DialogDescription>{t('nav.analytics')}</DialogDescription>
          </DialogHeader>
          {reportLoading ? (
            <div className="flex items-center justify-center py-10"><Loader2 className="h-6 w-6 animate-spin text-violet-600" /></div>
          ) : reportData ? (
            <div className="space-y-6">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {[
                  { label: t('jobs.col.applicants'), value: summary?.total_applicants ?? 0, icon: Users },
                  { label: t('jobs.col.views'), value: summary?.views ?? 0, icon: Eye },
                  { label: t('recruiter.interviewAnalysis.cvMatch'), value: summary?.avg_cv_score != null ? `${summary.avg_cv_score}/100` : '—', icon: BarChart3 },
                  { label: t('recruiter.interviewAnalysis.overallScore'), value: summary?.avg_interview_score != null ? `${summary.avg_interview_score}/100` : '—', icon: BarChart3 },
                ].map((item) => (
                  <div key={item.label} className="p-3 rounded-xl bg-emerald-50/60 dark:bg-emerald-500/5 border border-emerald-100 dark:border-white/10">
                    <item.icon className="h-4 w-4 text-emerald-500 mb-1.5" />
                    <div className="text-[10px] uppercase tracking-wider text-gray-400 font-bold">{item.label}</div>
                    <div className="text-lg font-black text-gray-900 dark:text-white">{item.value}</div>
                  </div>
                ))}
              </div>

              <div>
                <h4 className="text-sm font-bold text-gray-700 dark:text-gray-300 mb-2">{t('nav.pipeline')}</h4>
                <div className="space-y-2">
                  {funnel.map((stage: any) => {
                    const pct = summary?.total_applicants ? (stage.count / summary.total_applicants) * 100 : 0;
                    return (
                      <div key={stage.slug || stage.stage} className="flex items-center gap-3">
                        <span className="w-24 text-xs font-medium text-gray-500">{stage.stage}</span>
                        <div className="flex-1 h-2.5 bg-gray-100 dark:bg-white/5 rounded-full overflow-hidden">
                          <div className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-violet-500 transition-all" style={{ width: `${pct}%` }} />
                        </div>
                        <span className="w-20 text-right text-xs font-semibold text-gray-600 dark:text-gray-300">
                          {stage.count} ({stage.conversion}%)
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {Object.keys(sources).length > 0 && (
                <div>
                  <h4 className="text-sm font-bold text-gray-700 dark:text-gray-300 mb-2">{t('recruiter.chatbotLeads.colSource')}</h4>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(sources).map(([source, count]) => (
                      <Badge key={source} variant="outline" size="sm">{source}: {count}</Badge>
                    ))}
                  </div>
                </div>
              )}

              {recentApplicants.length > 0 && (
                <div>
                  <h4 className="text-sm font-bold text-gray-700 dark:text-gray-300 mb-2">{t('dash.recentApplications')}</h4>
                  <div className="overflow-x-auto rounded-xl border border-gray-100 dark:border-white/10">
                    <table className="w-full text-left">
                      <thead>
                        <tr className="border-b border-gray-100 dark:border-white/10 bg-gray-50 dark:bg-white/[0.03]">
                          <th className="py-2 px-3 text-xs font-bold text-gray-500 uppercase">{t('candidates.col.name')}</th>
                          <th className="py-2 px-3 text-xs font-bold text-gray-500 uppercase">{t('common.status')}</th>
                          <th className="py-2 px-3 text-xs font-bold text-gray-500 uppercase">{t('candidates.col.score')}</th>
                          <th className="py-2 px-3 text-xs font-bold text-gray-500 uppercase">{t('common.date')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {recentApplicants.map((app) => (
                          <tr key={app.id} className="border-b border-gray-50 dark:border-white/[0.02]">
                            <td className="py-2 px-3 text-sm font-semibold text-gray-800 dark:text-gray-200">{app.full_name}</td>
                            <td className="py-2 px-3 text-sm text-gray-500 capitalize">{app.status || 'pending'}</td>
                            <td className="py-2 px-3 text-sm text-gray-500">{app.score != null ? app.score : '—'}</td>
                            <td className="py-2 px-3 text-sm text-gray-500">{formatDate(app.created_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {funnel.length === 0 && recentApplicants.length === 0 && (
                <div className="text-center text-sm text-gray-400 py-6">{t('common.noData')}</div>
              )}
            </div>
          ) : (
            <div className="text-sm text-gray-400 text-center py-6">{t('common.noData')}</div>
          )}
          <DialogFooter>
            <div className="flex items-center gap-2">
              <Button variant="outline" disabled={!reportData || exporting} onClick={() => exportReport('csv')} leftIcon={exporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}>
                CSV
              </Button>
              <Button variant="outline" disabled={!reportData || exporting} onClick={() => exportReport('pdf')} leftIcon={exporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}>
                PDF
              </Button>
              <Button variant="primary" onClick={() => setReportOpen(false)}>{t('common.close')}</Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <ConfirmDialog
        open={!!deleteJob}
        onOpenChange={(open) => { if (!deleting) setDeleteJob(open ? deleteJob : null); }}
        title={t('common.delete')}
        description={t('jobs.archiveConfirm').replace('{title}', deleteJob?.title ?? '')}
        confirmLabel={t('common.delete')}
        cancelLabel={t('common.cancel')}
        variant="danger"
        loading={deleting}
        onConfirm={confirmDelete}
      />
    </div>
  );
}
