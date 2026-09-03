import { useState, useEffect } from 'react';
import { useLanguage } from '@/contexts/language-context';
import { useNavigate, useParams } from 'react-router';
import { motion } from 'framer-motion';
import { Card } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { ConfirmDialog } from '@/shared/components/ui/dialog';
import { customToast } from '@/shared/components/ui/toast';
import { cn } from '@/utils/cn';
import { skillTreesService, type RubricDetail } from '@/services/skill-trees.service';
import {
  TreePine, Pencil, ArrowLeft, Briefcase, Users, Loader2,
  FileText, MapPin, Clock, CheckCircle2, XCircle, Trash2, Copy,
} from 'lucide-react';

const levelColors: Record<string, string> = {
  beginner: 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-700',
  intermediate: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-700',
  advanced: 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-700',
  expert: 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-700',
};

function scoreColor(score: number | null | undefined) {
  const s = score ?? 0;
  if (s >= 80) return 'text-emerald-600 dark:text-emerald-400';
  if (s >= 60) return 'text-blue-600 dark:text-blue-400';
  return 'text-amber-500';
}

export default function SkillTreeDetailPage() {
  const { t } = useLanguage();
  const { id } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState<RubricDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(false);
  const [confirmArchiveOpen, setConfirmArchiveOpen] = useState(false);

  const goBack = () => {
    if (window.history.length > 1) {
      navigate(-1);
    } else {
      navigate('/rubrics');
    }
  };

  const load = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const detail = await skillTreesService.getDetail(Number(id));
      setData(detail);
    } catch {
      customToast({ type: 'error', title: t('recruiter.skillTreeDetail.loadFailedTitle'), message: t('recruiter.skillTreeDetail.loadFailedMessage') });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-8 w-8 animate-spin text-purple-500" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-center">
        <TreePine className="h-12 w-12 text-gray-300 dark:text-gray-600 mb-3" />
        <p className="text-base font-medium text-gray-500">{t('recruiter.skillTreeDetail.notFound')}</p>
        <Button variant="outline" className="mt-4" onClick={goBack}>{t('recruiter.skillTreeDetail.back')}</Button>
      </div>
    );
  }

  const categories = data.rubric_json?.categories ?? [];
  const linkedJobs = data.linked_jobs ?? [];
  const candidates = data.evaluated_candidates ?? [];

  const handleDuplicate = async () => {
    try {
      const res = await skillTreesService.duplicate(Number(id));
      customToast({ type: 'success', title: t('recruiter.skillTreeDetail.duplicatedTitle'), message: t('recruiter.skillTreeDetail.duplicatedMessage') });
      navigate(`/skill-tree/${res.id}`);
    } catch {
      customToast({ type: 'error', title: t('recruiter.skillTreeDetail.failedTitle'), message: t('recruiter.skillTreeDetail.duplicateFailedMessage') });
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await skillTreesService.delete(Number(id));
      customToast({ type: 'success', title: t('recruiter.skillTreeDetail.archivedTitle'), message: t('recruiter.skillTreeDetail.archivedMessage') });
      goBack();
    } catch {
      customToast({ type: 'error', title: t('recruiter.skillTreeDetail.failedTitle'), message: t('recruiter.skillTreeDetail.archiveFailedMessage') });
      setDeleting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" leftIcon={<ArrowLeft className="h-4 w-4" />} onClick={goBack}>{t('recruiter.skillTreeDetail.back')}</Button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">{data.job_name || data.title || `Rubric #${data.id}`}</h1>
              <Badge variant="primary" size="sm">v{data.version ?? 1}</Badge>
              {data.seniority && <Badge size="sm">{data.seniority}</Badge>}
            </div>
            {data.description && <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{data.description}</p>}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" leftIcon={<Copy className="h-4 w-4" />} onClick={handleDuplicate}>{t('recruiter.skillTreeDetail.duplicate')}</Button>
          <Button variant="outline" size="sm" leftIcon={<Trash2 className="h-4 w-4" />} onClick={() => setConfirmArchiveOpen(true)} disabled={deleting} className="text-red-500 hover:text-red-700">{t('recruiter.skillTreeDetail.archive')}</Button>
          <Button variant="primary" size="sm" leftIcon={<Pencil className="h-4 w-4" />} onClick={() => navigate(`/skill-tree-create?edit=${data.id}`)} className="font-bold shadow-md shadow-purple-500/25">{t('recruiter.skillTreeDetail.editRubric')}</Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="glass-panel border-purple-200/50 p-5 text-center">
          <div className="text-3xl font-extrabold text-purple-600 dark:text-purple-400">{categories.length}</div>
          <div className="text-xs font-bold uppercase tracking-wider text-gray-400 mt-1">{t('recruiter.skillTreeDetail.categories')}</div>
        </Card>
        <Card className="glass-panel border-purple-200/50 p-5 text-center">
          <div className="text-3xl font-extrabold text-blue-600 dark:text-blue-400">{data.skill_count ?? 0}</div>
          <div className="text-xs font-bold uppercase tracking-wider text-gray-400 mt-1">{t('recruiter.skillTreeDetail.skills')}</div>
        </Card>
        <Card className="glass-panel border-purple-200/50 p-5 text-center">
          <div className="flex items-center justify-center gap-1 text-3xl font-extrabold text-emerald-600 dark:text-emerald-400">
            <Briefcase className="h-5 w-5" />
            <span>{linkedJobs.length}</span>
          </div>
          <div className="text-xs font-bold uppercase tracking-wider text-gray-400 mt-1">{t('recruiter.skillTreeDetail.linkedJobs')}</div>
        </Card>
        <Card className="glass-panel border-purple-200/50 p-5 text-center">
          <div className="flex items-center justify-center gap-1 text-3xl font-extrabold text-amber-600 dark:text-amber-400">
            <Users className="h-5 w-5" />
            <span>{candidates.length}</span>
          </div>
          <div className="text-xs font-bold uppercase tracking-wider text-gray-400 mt-1">{t('recruiter.skillTreeDetail.evaluatedCandidates')}</div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Rubric structure */}
        <Card className="glass-panel border-purple-200/50 p-6">
          <h3 className="text-base font-extrabold text-gray-900 dark:text-white mb-5 flex items-center gap-2">
            <TreePine className="h-4 w-4 text-purple-500" /> {t('recruiter.skillTreeDetail.rubricStructure')}
          </h3>
          {categories.length === 0 ? (
            <p className="text-sm text-gray-400 dark:text-gray-500 italic">{t('recruiter.skillTreeDetail.noCategories')}</p>
          ) : (
            <div className="space-y-5">
              {categories.map((c, ci) => {
                const subs = Array.isArray(c.subcategories) ? c.subcategories : [];
                const skills = subs.flatMap((s: Record<string, unknown>) =>
                  Array.isArray(s.skills) ? s.skills : [],
                );
                return (
                  <div key={ci}>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-extrabold text-gray-900 dark:text-white">{String(c.name ?? '')}</span>
                      <div className="flex items-center gap-2">
                        <Badge variant="default" size="sm">Weight {String(c.weight ?? 1)}</Badge>
                        <Badge variant="outline" size="sm">{skills.length} skills</Badge>
                      </div>
                    </div>
                    <div className="space-y-1.5">
                      {skills.map((s, si) => {
                        const level = String(s.level ?? 'intermediate');
                        return (
                          <div key={si} className="flex items-center justify-between rounded-lg bg-gray-50 dark:bg-white/[0.03] px-3 py-2">
                            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">{String(s.name ?? '')}</span>
                            <div className="flex items-center gap-2">
                              <Badge size="sm" className={cn(levelColors[level] ?? levelColors.intermediate)}>{level}</Badge>
                              <Badge variant="outline" size="sm">{String(s.weight ?? 1)}</Badge>
                              {Boolean(s.is_required ?? s.required) && <Badge variant="warning" size="sm">{t('recruiter.skillTreeDetail.required')}</Badge>}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </Card>

        {/* Linked jobs */}
        <div className="space-y-6">
          <Card className="glass-panel border-purple-200/50 p-6">
            <h3 className="text-base font-extrabold text-gray-900 dark:text-white mb-5 flex items-center gap-2">
              <Briefcase className="h-4 w-4 text-blue-500" /> {t('recruiter.skillTreeDetail.linkedJobs')} ({linkedJobs.length})
            </h3>
            {linkedJobs.length === 0 ? (
              <p className="text-sm text-gray-400 dark:text-gray-500 italic">
                This rubric is not linked to any job yet. Use it when creating a campaign or in the job wizard.
              </p>
            ) : (
              <div className="space-y-2.5">
                {linkedJobs.map((j) => (
                  <motion.div key={j.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
                    className="flex items-center justify-between rounded-xl border border-gray-100 dark:border-white/[0.06] px-4 py-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-bold text-gray-900 dark:text-white truncate">{j.title}</span>
                        <Badge variant={j.status === 'active' ? 'success' : 'outline'} size="sm">{j.status}</Badge>
                      </div>
                      <div className="flex items-center gap-3 mt-1 text-xs text-gray-400">
                        {j.location && <span className="flex items-center gap-1"><MapPin className="h-3 w-3" />{j.location}</span>}
                        {j.type && <span>{j.type}</span>}
                        {j.link_type?.startsWith('campaign') && <span className="flex items-center gap-1"><FileText className="h-3 w-3" />{t('recruiter.skillTreeDetail.viaCampaign')}</span>}
                      </div>
                    </div>
                    <Button variant="ghost" size="sm" onClick={() => navigate(`/jobs/${j.id}`)}>{t('recruiter.skillTreeDetail.open')}</Button>
                  </motion.div>
                ))}
              </div>
            )}
          </Card>

          <Card className="glass-panel border-purple-200/50 p-6">
            <h3 className="text-base font-extrabold text-gray-900 dark:text-white mb-5 flex items-center gap-2">
              <Users className="h-4 w-4 text-amber-500" /> {t('recruiter.skillTreeDetail.evaluatedCandidates')} ({candidates.length})
            </h3>
            {candidates.length === 0 ? (
              <p className="text-sm text-gray-400 dark:text-gray-500 italic">
                No candidates have been scored against this rubric yet. Once AI interviews run, results appear here.
              </p>
            ) : (
              <div className="space-y-2.5">
                {candidates.map((cand) => (
                  <div key={cand.application_id}
                    className="flex items-center justify-between rounded-xl border border-gray-100 dark:border-white/[0.06] px-4 py-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-bold text-gray-900 dark:text-white truncate">{cand.candidate_name}</span>
                        {cand.status && (
                          cand.status === 'hired' || cand.status === 'offer_sent'
                            ? <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                            : cand.status === 'rejected' || cand.status === 'withdrawn'
                              ? <XCircle className="h-4 w-4 text-red-500" />
                              : <Clock className="h-4 w-4 text-blue-400" />
                        )}
                      </div>
                      <div className="flex items-center gap-3 mt-1 text-xs text-gray-400">
                        {cand.email && <span>{cand.email}</span>}
                        {cand.job_title && <span>· {cand.job_title}</span>}
                        {cand.evaluated_at && <span>· {new Date(cand.evaluated_at).toLocaleDateString()}</span>}
                      </div>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <div className="text-right">
                        <div className={cn('text-lg font-extrabold', scoreColor(cand.final_score))}>{cand.final_score ?? '—'}</div>
                        <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400">{t('recruiter.skillTreeDetail.final')}</div>
                      </div>
                      {typeof cand.rubric_score === 'number' && (
                        <div className="text-right">
                          <div className={cn('text-lg font-extrabold', scoreColor(cand.rubric_score))}>{cand.rubric_score}</div>
                          <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400">{t('recruiter.skillTreeDetail.rubric')}</div>
                        </div>
                      )}
                      <Button variant="ghost" size="sm" onClick={() => navigate(`/candidates/${cand.application_id}`)}>{t('recruiter.skillTreeDetail.view')}</Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>

      <ConfirmDialog
        open={confirmArchiveOpen}
        onOpenChange={setConfirmArchiveOpen}
        title={t('recruiter.skillTreeDetail.archive')}
        description={t('recruiter.skillTreeDetail.archiveConfirm')}
        confirmLabel={t('recruiter.skillTreeDetail.archive')}
        cancelLabel={t('common.cancel')}
        variant="danger"
        onConfirm={() => { setConfirmArchiveOpen(false); handleDelete(); }}
        loading={deleting}
      />
    </div>
  );
}
