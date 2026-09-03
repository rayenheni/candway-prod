import { useState, useMemo, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import { DndContext, DragEndEvent, DragOverlay, DragStartEvent, pointerWithin, PointerSensor, useSensor, useSensors } from '@dnd-kit/core';
import { SortableContext, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { Card } from '@/shared/components/ui/card';
import { Avatar } from '@/shared/components/ui/avatar';
import { customToast } from '@/shared/components/ui/toast';
import { useLanguage } from '@/contexts/language-context';
import { cn } from '@/utils/cn';
import { jobsService } from '@/services/jobs.service';
import { candidatesService } from '@/services/candidates.service';
import {
  Users, UserCheck, Clock, Loader2, Search,
  TrendingUp, GripVertical, ChevronDown, ChevronUp
} from 'lucide-react';

const VALID_STATUSES = [
  'pending', 'screening', 'interviewing', 'offer', 'rejected', 'analyzed', 'failed',
  'applied', 'invited', 'active', 'analyzing', 'analysis_failed', 'hired',
  'offer_declined', 'withdrawn', 'imported', 'reviewed', 'shortlisted',
];

const DEFAULT_STAGES = [
  { id: 'applied', name: 'Applied', slug: 'applied', color: '#64748b' },
  { id: 'screening', name: 'Screening', slug: 'screening', color: '#0ea5e9' },
  { id: 'interviewing', name: 'Interview', slug: 'interviewing', color: '#8b5cf6' },
  { id: 'shortlisted', name: 'Shortlisted', slug: 'shortlisted', color: '#f59e0b' },
  { id: 'offer', name: 'Offer', slug: 'offer', color: '#f97316' },
  { id: 'hired', name: 'Hired', slug: 'hired', color: '#10b981' },
  { id: 'rejected', name: 'Rejected', slug: 'rejected', color: '#ef4444' },
];

function normalizeStatus(status: string | null): string {
  switch (status) {
    case 'new':
    case 'pending':
    case 'applied':
    case 'invited':
      return 'applied';
    case 'screened':
    case 'screening':
    case 'analyzing':
    case 'analyzed':
    case 'analysis_failed':
      return 'screening';
    case 'interview':
    case 'interviewing':
    case 'active':
      return 'interviewing';
    case 'shortlisted':
      return 'shortlisted';
    case 'offer':
    case 'offer_declined':
      return 'offer';
    case 'hired':
      return 'hired';
    case 'rejected':
    case 'failed':
      return 'rejected';
    default:
      return 'applied';
  }
}

function SortableCard({ candidate }: { candidate: any }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: candidate.id });
  const style = { transform: CSS.Transform.toString(transform), transition };
  return (
    <div ref={setNodeRef} style={style} className={cn(isDragging && 'opacity-30')}>
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} layout transition={{ duration: 0.2 }}>
        <Card hoverable className="border border-gray-100 dark:border-white/5">
          <div className="p-2">
            <div className="flex items-start gap-1.5">
              <button {...attributes} {...listeners} className="mt-0.5 text-gray-300 dark:text-gray-600 cursor-grab active:cursor-grabbing touch-none">
                <GripVertical className="h-3.5 w-3.5" />
              </button>
              <Avatar name={candidate.candidate_name || '?'} size="sm" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-1">
                  <span className="text-xs font-medium text-gray-900 dark:text-white truncate">{candidate.candidate_name || 'Unknown'}</span>
                  {candidate.score != null && (
                    <span className={cn('flex h-5 w-5 items-center justify-center rounded text-[9px] font-bold shrink-0',
                      candidate.score >= 90 ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400' :
                      candidate.score >= 80 ? 'bg-blue-50 text-blue-700 dark:bg-blue-500/10 dark:text-blue-400' :
                      'bg-gray-100 text-gray-600 dark:bg-white/[0.06] dark:text-gray-400')}>
                      {candidate.score}
                    </span>
                  )}
                </div>
                <p className="text-[10px] text-gray-500 dark:text-gray-400 mt-0.5 truncate">{candidate.job_title || candidate.role || 'Application'}</p>
                {candidate.created_at && <p className="text-[10px] text-gray-400 mt-0.5">{candidate.created_at}</p>}
              </div>
            </div>
          </div>
        </Card>
      </motion.div>
    </div>
  );
}

function DragCard({ candidate }: { candidate: any }) {
  return (
    <Card className="border border-violet-200 dark:border-violet-500/30 shadow-lg rotate-[2deg]">
      <div className="p-3">
        <div className="flex items-start gap-2">
          <Avatar name={candidate.candidate_name || '?'} size="sm" />
          <div className="flex-1 min-w-0">
            <span className="text-sm font-medium text-gray-900 dark:text-white">{candidate.candidate_name || 'Unknown'}</span>
            <p className="text-xs text-gray-500 mt-0.5">{candidate.job_title || candidate.role || 'Application'}</p>
          </div>
        </div>
      </div>
    </Card>
  );
}

function StaticCard({ candidate }: { candidate: any }) {
  return (
    <Card className="border border-gray-100 dark:border-white/5">
      <div className="p-3">
        <div className="flex items-start gap-2">
          <Avatar name={candidate.candidate_name || '?'} size="sm" />
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-1">
              <span className="text-sm font-medium text-gray-900 dark:text-white truncate">{candidate.candidate_name || 'Unknown'}</span>
              {candidate.score != null && (
                <span className={cn('flex h-6 w-6 items-center justify-center rounded text-[10px] font-bold shrink-0',
                  candidate.score >= 90 ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400' :
                  candidate.score >= 80 ? 'bg-blue-50 text-blue-700 dark:bg-blue-500/10 dark:text-blue-400' :
                  'bg-gray-100 text-gray-600 dark:bg-white/[0.06] dark:text-gray-400')}>
                  {candidate.score}
                </span>
              )}
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 truncate">{candidate.job_title || candidate.role || 'Application'}</p>
            {candidate.created_at && <p className="text-[11px] text-gray-400 mt-1">{candidate.created_at}</p>}
          </div>
        </div>
      </div>
    </Card>
  );
}

function EmptyDropZone({ slug }: { slug: string }) {
  const { setNodeRef, isOver } = useSortable({
    id: `dropzone-${slug}`,
    disabled: { draggable: true, droppable: false },
  });
  return (
    <div ref={setNodeRef}
      className={cn('flex items-center justify-center h-20 rounded-xl border-2 border-dashed transition-colors',
        isOver ? 'border-violet-400 bg-violet-50/50 dark:bg-violet-500/10' : 'border-gray-200 dark:border-white/5'
      )}>
      <span className={cn('text-xs', isOver ? 'text-violet-600 font-medium' : 'text-gray-400')}>
        {isOver ? 'Drop here' : 'No candidates'}
      </span>
    </div>
  );
}

export default function PipelineBoardPage() {
  const { t } = useLanguage();
  const qc = useQueryClient();
  const [jobFilter, setJobFilter] = useState('');
  const [search, setSearch] = useState('');
  const [expandedStage, setExpandedStage] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);

  const defaultStagesWithTranslations = useMemo(() => [
    { id: 'applied', name: t('recruiter.dash.stage.applied'), slug: 'applied', color: '#64748b' },
    { id: 'screening', name: t('recruiter.dash.stage.screening'), slug: 'screening', color: '#0ea5e9' },
    { id: 'interviewing', name: t('recruiter.dash.stage.interview'), slug: 'interviewing', color: '#8b5cf6' },
    { id: 'shortlisted', name: t('candidates.tab.shortlisted'), slug: 'shortlisted', color: '#f59e0b' },
    { id: 'offer', name: t('recruiter.dash.stage.offer'), slug: 'offer', color: '#f97316' },
    { id: 'hired', name: t('recruiter.dash.stage.hired'), slug: 'hired', color: '#10b981' },
    { id: 'rejected', name: t('candidates.tab.rejected'), slug: 'rejected', color: '#ef4444' },
  ], [t]);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  const { data: jobsData } = useQuery({ queryKey: ['jobs'], queryFn: () => jobsService.getJobs({ per_page: 100 }) });
  const jobs: any[] = (jobsData as any)?.items ?? [];

  const { data: stagesData } = useQuery({
    queryKey: ['pipeline-stages', jobFilter],
    queryFn: () => jobFilter ? jobsService.getJobPipelineStages(jobFilter) : Promise.resolve(defaultStagesWithTranslations),
    enabled: !!jobFilter,
  });

  const stages = useMemo(() => {
    if (!jobFilter) return defaultStagesWithTranslations;
    const custom = (stagesData as any[]) ?? [];
    if (custom.length === 0) return defaultStagesWithTranslations;
    const mapped = custom.map((s: any) => ({ ...s, id: s.slug }));
    if (!mapped.some((s: any) => s.slug === 'rejected')) {
      const rejected = defaultStagesWithTranslations.find((s) => s.slug === 'rejected');
      if (rejected) mapped.push(rejected);
    }
    return mapped;
  }, [jobFilter, stagesData, defaultStagesWithTranslations]);

  const { data: appsData, isLoading } = useQuery({
    queryKey: ['applications', jobFilter],
    queryFn: () => candidatesService.getApplications({ per_page: 500, ...(jobFilter ? { job_id: Number(jobFilter) } : {}) }),
  });
  const apps: any[] = (appsData as any)?.items ?? [];
  const pipelineStats = (appsData as any)?.pipeline_stats;

  const updateStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => candidatesService.updateApplicationStatus(id, status),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['applications'] });
      qc.invalidateQueries({ queryKey: ['recruiter-applications'] });
      qc.invalidateQueries({ queryKey: ['candidates'] });
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail || 'Could not update application status.';
      customToast({ type: 'error', title: t('common.status'), message: detail });
    },
  });

  const activeCandidate = useMemo(() => apps.find((a: any) => String(a.id) === activeId), [apps, activeId]);

  const handleDragStart = useCallback((event: DragStartEvent) => {
    setActiveId(String(event.active.id));
  }, []);

  const handleDragEnd = useCallback((event: DragEndEvent) => {
    setActiveId(null);
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const appId = String(active.id);
    const overSlug = String(over.data?.current?.sortable?.containerId || over.id);
    const app = apps.find((a: any) => String(a.id) === appId);
    if (!app) return;
    if (!normalizeStatus(overSlug) || !VALID_STATUSES.includes(overSlug)) {
      customToast({ type: 'warning', title: t('common.status'), message: `Custom stage '${overSlug}' is not movable.` });
      return;
    }
    if (normalizeStatus(app.status) === overSlug) return;
    updateStatus.mutate({ id: appId, status: overSlug });
  }, [apps, updateStatus, t]);

  const handleMoveToStage = useCallback((appId: string, targetSlug: string) => {
    const app = apps.find((a: any) => String(a.id) === appId);
    if (!app || normalizeStatus(app.status) === targetSlug) return;
    if (!normalizeStatus(targetSlug) || !VALID_STATUSES.includes(targetSlug)) {
      customToast({ type: 'warning', title: t('common.status'), message: `Custom stage '${targetSlug}' is not movable.` });
      return;
    }
    updateStatus.mutate({ id: appId, status: targetSlug });
  }, [apps, updateStatus, t]);

  const filteredApps = useMemo(() => {
    if (!search) return apps;
    const q = search.toLowerCase();
    return apps.filter((a: any) =>
      (a.candidate_name || '').toLowerCase().includes(q) ||
      (a.job_title || '').toLowerCase().includes(q) ||
      (a.email || '').toLowerCase().includes(q)
    );
  }, [apps, search]);

  const grouped = useMemo(() => {
    return stages.map(s => ({
      ...s,
      items: filteredApps.filter((a: any) => normalizeStatus(a.status) === s.slug),
    }));
  }, [stages, filteredApps]);

  const totalInPipeline = grouped.reduce((sum, s) => sum + s.items.length, 0);

  const statCards = [
    { label: t('recruiter.dash.totalApplications'), value: pipelineStats?.total_applications ?? totalInPipeline, icon: Users, color: 'bg-violet-50 text-violet-600 dark:bg-violet-500/10 dark:text-violet-400' },
    { label: t('candidates.title'), value: pipelineStats?.total_candidates ?? '—', icon: UserCheck, color: 'bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400' },
    { label: t('recruiter.dash.interviews'), value: pipelineStats?.new_this_week ?? '—', icon: Clock, color: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400' },
    { label: t('recruiter.dash.stage.interview'), value: pipelineStats?.conversion_rates?.app_to_interview != null ? `${pipelineStats.conversion_rates.app_to_interview}%` : '—', icon: TrendingUp, color: 'bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400' },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-4xl font-extrabold text-gray-900 dark:text-white tracking-tight">{t('nav.pipeline')}</h1>
          <p className="mt-1 sm:mt-2 text-sm text-gray-500 dark:text-gray-400">{t('dash.trackApplications')}</p>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((stat) => (
          <Card key={stat.label}>
            <div className="p-4 flex items-center gap-4">
              <div className={cn('p-2.5 rounded-xl', stat.color)}>
                <stat.icon className="h-5 w-5" />
              </div>
              <div>
                <p className="text-xs text-gray-500 dark:text-gray-400">{stat.label}</p>
                <p className="text-xl font-bold text-gray-900 dark:text-white">{stat.value}</p>
              </div>
            </div>
          </Card>
        ))}
      </div>

      <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
        <div className="relative flex-1 w-full sm:max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder={t('common.search')} className="w-full pl-10 pr-4 py-2 rounded-2xl bg-white dark:bg-white/[0.04] border border-gray-200 dark:border-white/10 text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-violet-500/30 focus:border-violet-500 transition-all" />
        </div>
        <select value={jobFilter} onChange={e => setJobFilter(e.target.value)}
          className="w-full sm:w-auto px-3 py-2 rounded-2xl bg-white dark:bg-white/[0.04] border border-gray-200 dark:border-white/10 text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-violet-500/30">
          <option value="">{t('candidates.allJobs')}</option>
          {jobs.map((j: any) => <option key={j.id} value={j.id}>{j.title}</option>)}
        </select>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-20"><Loader2 className="h-8 w-8 animate-spin text-violet-600" /></div>
      ) : (
        <>
          {/* Mobile: accordion pipeline */}
          <div className="md:hidden space-y-3">
            {grouped.map((stage) => {
              const isOpen = expandedStage === stage.slug;
              return (
                <Card key={stage.slug} className="overflow-hidden">
                  <button onClick={() => setExpandedStage(isOpen ? null : stage.slug)}
                    className="w-full flex items-center gap-3 p-4 text-left">
                    <div className="h-3 w-3 rounded-full shrink-0" style={{ backgroundColor: stage.color || '#64748b' }} />
                    <span className="text-sm font-semibold text-gray-900 dark:text-white">{stage.name}</span>
                    <span className="text-xs font-medium text-gray-400 ml-auto">{stage.items.length}</span>
                    {isOpen ? <ChevronUp className="h-4 w-4 text-gray-400" /> : <ChevronDown className="h-4 w-4 text-gray-400" />}
                  </button>
                  <AnimatePresence>
                    {isOpen && (
                      <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                        <div className="px-4 pb-4 space-y-2">
                          {stage.items.length === 0 ? (
                            <div className="flex items-center justify-center h-12 rounded-xl border border-dashed border-gray-200 dark:border-white/5">
                              <span className="text-xs text-gray-400">{t('common.noData')}</span>
                            </div>
                          ) : (
                            stage.items.map((candidate: any) => (
                              <div key={candidate.id} className="relative">
                                <StaticCard candidate={candidate} />
                                <select onChange={e => handleMoveToStage(candidate.id, e.target.value)}
                                  value={normalizeStatus(candidate.status) ?? stages[0]?.slug ?? 'applied'}
                                  className="absolute bottom-2 right-2 text-[10px] px-1.5 py-0.5 rounded bg-white dark:bg-gray-800 border border-gray-200 dark:border-white/10 text-gray-600 dark:text-gray-400">
                                  {stages.map(s => (
                                    <option key={s.slug} value={s.slug}>{s.name}</option>
                                  ))}
                                </select>
                              </div>
                            ))
                          )}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </Card>
              );
            })}
          </div>

          {/* Desktop: kanban board */}
          <div className="hidden md:block">
            <DndContext
              sensors={sensors}
              collisionDetection={pointerWithin}
              onDragStart={handleDragStart}
              onDragEnd={handleDragEnd}
            >
              <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3">
                {grouped.map((stage) => {
                  const sentinelId = `dropzone-${stage.slug}`;
                  const itemIds = stage.items.length > 0
                    ? stage.items.map((i: any) => i.id)
                    : [sentinelId];
                  return (
                    <div key={stage.slug} className="min-w-0">
                      <div className="flex items-center gap-2 mb-3 px-1">
                        <div className="h-2.5 w-2.5 rounded-full shrink-0" style={{ backgroundColor: stage.color || '#64748b' }} />
                        <span className="text-sm font-medium text-gray-700 dark:text-gray-300 truncate">{stage.name}</span>
                        <span className="text-xs font-medium text-gray-400 dark:text-gray-500 ml-auto">{stage.items.length}</span>
                      </div>
                      <SortableContext id={stage.slug} items={itemIds} strategy={verticalListSortingStrategy}>
                        <div className="space-y-2 min-h-[120px] rounded-xl border-2 border-dashed border-transparent transition-colors">
                          {stage.items.length === 0 ? (
                            <EmptyDropZone slug={stage.slug} />
                          ) : (
                            stage.items.map((candidate: any) => (
                              <SortableCard key={candidate.id} candidate={candidate} />
                            ))
                          )}
                        </div>
                      </SortableContext>
                    </div>
                  );
                })}
              </div>

              <DragOverlay>
                {activeCandidate ? <DragCard candidate={activeCandidate} /> : null}
              </DragOverlay>
            </DndContext>
          </div>
        </>
      )}
    </div>
  );
}
