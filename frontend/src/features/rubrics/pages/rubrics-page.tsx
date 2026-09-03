import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router';
import { motion } from 'framer-motion';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/shared/components/ui/dialog';
import { useAuth } from '@/contexts/auth-context';
import { useLanguage } from '@/contexts/language-context';
import { rubricsService, type RubricTemplate } from '@/services/rubrics.service';
import { jobsService } from '@/services/jobs.service';
import { Plus, FileText, Loader2, BookOpen, Briefcase, Sparkles } from 'lucide-react';

export default function RubricsPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { t } = useLanguage();
  const [rubrics, setRubrics] = useState<RubricTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  void setError;
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [jobs, setJobs] = useState<any[]>([]);
  const [loadingJobs, setLoadingJobs] = useState(false);

  const openRubric = (rubric: RubricTemplate) => {
    if (rubric.rubric_id && (user?.role === 'recruiter' || user?.role === 'admin')) {
      navigate(`/skill-tree/${rubric.rubric_id}`);
    } else {
      navigate(`/jobs/${rubric.job_id}`);
    }
  };

  useEffect(() => {
    rubricsService.getTemplates()
      .then(res => {
        const list = Array.isArray(res?.templates) ? res.templates : [];
        setRubrics(list);
      })
      .catch(() => {
        setRubrics([]);
      })
      .finally(() => setLoading(false));
  }, []);

  const openCreateDialog = async () => {
    setShowCreateDialog(true);
    setLoadingJobs(true);
    try {
      const res = await jobsService.getJobs({ per_page: 100 });
      setJobs(Array.isArray(res?.items) ? res.items : []);
    } catch {
      setJobs([]);
    } finally {
      setLoadingJobs(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{t('rubric.title')}</h1>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{t('rubric.subtitle')}</p>
          </div>
        </div>
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 text-violet-500 animate-spin" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{t('rubric.title')}</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            {t('rubric.subtitleLong')}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" leftIcon={<Sparkles className="h-4 w-4" />} onClick={() => navigate('/jobs/new')}>
            {t('rubric.newJobRubric')}
          </Button>
          <Button variant="primary" leftIcon={<Plus className="h-4 w-4" />} onClick={openCreateDialog}>
            {t('rubric.linkRubricToJob')}
          </Button>
        </div>
      </div>

      {error && (
        <Card className="glass-panel border-red-200/50">
          <CardContent className="p-4 text-sm text-red-600">{error}</CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {rubrics.length === 0 ? (
          <div className="col-span-full flex flex-col items-center justify-center py-16 text-gray-500">
            <BookOpen className="h-12 w-12 mb-4 text-purple-300" />
            <p className="text-lg font-semibold text-gray-700 dark:text-gray-300">{t('rubric.empty')}</p>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{t('rubric.emptyDesc')}</p>
            <Button variant="primary" className="mt-4" leftIcon={<Plus className="h-4 w-4" />} onClick={() => navigate('/jobs/new')}>
              {t('rubric.createJob')}
            </Button>
          </div>
        ) : rubrics.map((rubric, i) => (
          <motion.div
            key={rubric.job_id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: i * 0.05 }}
          >
            <Card hoverable className="cursor-pointer h-full" onClick={() => openRubric(rubric)}>
              <CardContent>
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50 dark:bg-blue-500/10">
                      <FileText className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold text-gray-900 dark:text-white">{rubric.job_title}</h3>
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{rubric.company || '—'}</p>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-4 mt-4 pt-3 border-t border-gray-100 dark:border-white/[0.04]">
                  <span className="text-xs text-gray-500 dark:text-gray-400">{rubric.category_count} {t('camp.create.categoriesLabel')}</span>
                  <span className="text-xs text-gray-500 dark:text-gray-400">{rubric.skill_count} {t('camp.create.skillsLabel')}</span>
                  <Badge variant="default" size="sm" className="ml-auto">{rubric.seniority}</Badge>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('rubric.linkDialogTitle')}</DialogTitle>
            <DialogDescription>{t('rubric.linkDialogDesc')}</DialogDescription>
          </DialogHeader>
          <div className="max-h-80 overflow-y-auto space-y-2">
            {loadingJobs ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 text-violet-500 animate-spin" />
              </div>
            ) : jobs.length === 0 ? (
              <div className="text-center py-8 text-sm text-gray-500">
                <p>{t('rubric.noJobsFound')}</p>
                <Button variant="outline" size="sm" className="mt-2" onClick={() => { setShowCreateDialog(false); navigate('/jobs/new'); }}>
                  {t('rubric.createJobFirst')}
                </Button>
              </div>
            ) : (
              jobs.map((job: any) => (
                <button
                  key={job.id}
                  onClick={() => { setShowCreateDialog(false); navigate(`/jobs/${job.id}`); }}
                  className="w-full text-left p-3 rounded-xl border border-gray-100 dark:border-white/[0.06] hover:border-purple-200 dark:hover:border-purple-500/30 hover:bg-purple-50/50 dark:hover:bg-purple-500/5 transition-colors flex items-center gap-3"
                >
                  <div className="h-8 w-8 rounded-lg bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center">
                    <Briefcase className="h-4 w-4 text-purple-600 dark:text-purple-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-gray-900 dark:text-white truncate">{job.title}</p>
                    <p className="text-xs text-gray-500">{job.location || '—'} &middot; {job.type || '—'}</p>
                  </div>
                  <Badge variant="outline" size="sm">{job.is_active ? t('common.active') : t('jobs.status.draft')}</Badge>
                </button>
              ))
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
