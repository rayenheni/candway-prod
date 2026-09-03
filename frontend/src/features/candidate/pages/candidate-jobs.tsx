import { useState } from 'react';
import { useNavigate } from 'react-router';
import { motion } from 'framer-motion';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { candidateService } from '@/services/candidate.service';
import { Card } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { customToast } from '@/shared/components/ui/toast';
import { cn } from '@/utils/cn';
import { useLanguage } from '@/contexts/language-context';
import { Search, MapPin, Clock, Briefcase, CheckCircle, Loader2, Eye, Star } from 'lucide-react';

interface Job {
  id: number;
  title: string;
  company: string | null;
  location: string;
  type: string;
  salary_range: string;
  match_score: number;
  posted_at: string;
  already_applied: boolean;
  description: string;
  required_skills: string[];
}

export default function CandidateJobsPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState<'all' | 'saved'>('all');
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { t } = useLanguage();

  const { data: jobs, isLoading, isError, refetch } = useQuery<Job[]>({
    queryKey: ['candidate-jobs'],
    queryFn: () => candidateService.getJobs(50),
  });

  const { data: savedJobs } = useQuery<any[]>({
    queryKey: ['candidate-saved-jobs'],
    queryFn: () => candidateService.getSavedJobs().then((res: any) => res?.saved_jobs ?? []),
  });

  const savedByJobId = new Map<number, number>();
  (savedJobs || []).forEach((s: any) => savedByJobId.set(Number(s.job_id), Number(s.id)));

  const filtered = (jobs || []).filter((job) => {
    const matchesSearch = !searchQuery || job.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (job.required_skills || []).some(s => s.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchesTab = activeTab === 'all' || savedByJobId.has(job.id);
    return matchesSearch && matchesTab;
  });

  const handleToggleSave = async (jobId: number) => {
    const savedRowId = savedByJobId.get(jobId);
    try {
      if (savedRowId) {
        await candidateService.removeSavedJob(String(savedRowId));
        customToast({ type: 'info', title: t('candidate.jobs.removed'), message: t('candidate.jobs.removedMsg') });
      } else {
        await candidateService.saveJob(jobId);
        customToast({ type: 'success', title: t('candidate.jobs.saved'), message: t('candidate.jobs.savedMsg') });
      }
      await queryClient.invalidateQueries({ queryKey: ['candidate-saved-jobs'] });
    } catch {
      customToast({ type: 'error', title: t('candidate.jobs.error'), message: t('candidate.jobs.savedError') });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-gray-900 dark:text-white tracking-tight">
            {t('candidate.jobs.browseTitle')}
          </h1>
          <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
            {t('candidate.jobs.browseSubtitle')}
          </p>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center gap-3">
        <div className="relative max-w-md flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={t('candidate.jobs.searchPlaceholder')}
            className="pl-10"
          />
        </div>
        <div className="flex gap-1 p-1 bg-gray-100 dark:bg-white/[0.04] rounded-2xl w-fit">
          {(['all', 'saved'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={cn(
                'inline-flex items-center gap-1.5 px-4 py-1.5 text-sm font-medium rounded-xl transition-all',
                activeTab === tab
                  ? 'bg-white dark:bg-white/10 text-gray-900 dark:text-white shadow-sm'
                  : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
              )}
            >
              {tab === 'saved' && <Star className={cn('h-3.5 w-3.5', activeTab === 'saved' && 'text-amber-400 fill-amber-400')} />}
              {tab === 'all' ? t('jobs.allJobs') : `${t('candidate.jobs.saved')} (${savedByJobId.size})`}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-violet-600" />
        </div>
      ) : isError ? (
        <div className="text-center py-20">
          <Briefcase className="mx-auto h-12 w-12 text-gray-300 dark:text-gray-600 mb-4" />
          <p className="text-gray-500 dark:text-gray-400 text-lg font-medium">{t('candidate.jobs.loadFailed')}</p>
          <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">
            {t('candidate.jobs.fetchError')}
          </p>
          <Button variant="outline" size="sm" className="mt-4" onClick={() => refetch()}>
            {t('common.retry')}
          </Button>
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-20">
          <Briefcase className="mx-auto h-12 w-12 text-gray-300 dark:text-gray-600 mb-4" />
          <p className="text-gray-500 dark:text-gray-400 text-lg font-medium">{t('candidate.jobs.noMatches')}</p>
          <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">
            {searchQuery ? t('candidate.jobs.tryDifferent') : t('candidate.jobs.checkLater')}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((job, i) => (
            <motion.div
              key={job.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.03 }}
            >
              <Card hoverable className="h-full flex flex-col">
                <div className="p-5 flex flex-col h-full">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex-1 min-w-0">
                      <h3 className="text-base font-semibold text-gray-900 dark:text-white truncate">
                        {job.title}
                      </h3>
                      {job.company && (
                        <p className="text-sm text-gray-500 mt-0.5">{job.company}</p>
                      )}
                    </div>
                    {job.match_score > 0 && (
                      <Badge variant="success" className="shrink-0 ml-2">
                        {job.match_score}% {t('candidate.jobs.match')}
                      </Badge>
                    )}
                  </div>

                  <div className="flex flex-wrap gap-2 mb-3">
                    <div className="flex items-center gap-1 text-xs text-gray-500">
                      <MapPin className="h-3 w-3" />
                      <span>{job.location || t('jobs.remote')}</span>
                    </div>
                    <div className="flex items-center gap-1 text-xs text-gray-500">
                      <Clock className="h-3 w-3" />
                      <span>{job.posted_at || t('candidate.jobs.recently')}</span>
                    </div>
                    <div className="flex items-center gap-1 text-xs text-gray-500">
                      <Briefcase className="h-3 w-3" />
                      <span>{job.type || t('candidate.jobs.fullTime')}</span>
                    </div>
                  </div>

                  {(job.required_skills || []).length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mb-4">
                      {job.required_skills.slice(0, 4).map((skill) => (
                        <span key={skill} className="text-[11px] px-2 py-0.5 rounded-full bg-violet-50 text-violet-700 dark:bg-violet-500/10 dark:text-violet-300 font-medium">
                          {skill}
                        </span>
                      ))}
                      {job.required_skills.length > 4 && (
                        <span className="text-[11px] text-gray-400">+{job.required_skills.length - 4}</span>
                      )}
                    </div>
                  )}

                   <p className="text-xs text-gray-400 dark:text-gray-500 line-clamp-2 mb-4 flex-1">
                     {job.description?.replace(/<[^>]*>/g, '') || ''}
                   </p>

                  <div className="flex items-center gap-2 pt-3 border-t border-gray-100 dark:border-white/5">
                    {job.already_applied ? (
                      <div className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400 text-sm font-medium">
                        <CheckCircle className="h-4 w-4" />
                        {t('apps.applied')}
                      </div>
                    ) : (
                      <Button
                        variant="primary"
                        size="sm"
                        className="flex-1"
                        leftIcon={<Eye className="h-3.5 w-3.5" />}
                        onClick={() => navigate(`/careers/${job.id}`)}
                      >
                        {t('candidate.jobs.viewDetails')}
                      </Button>
                    )}
                    <button
                      onClick={() => handleToggleSave(job.id)}
                      title={savedByJobId.has(job.id) ? t('candidate.jobs.removeSaved') : t('candidate.jobs.saveJob')}
                      className={cn(
                        'p-2 rounded-lg transition-colors',
                        savedByJobId.has(job.id)
                          ? 'bg-amber-50 text-amber-500 dark:bg-amber-500/10'
                          : 'text-gray-400 hover:bg-amber-50 hover:text-amber-500 dark:hover:bg-amber-500/10'
                      )}
                    >
                      <Star className={cn('h-4 w-4', savedByJobId.has(job.id) && 'fill-amber-400 text-amber-400')} />
                    </button>
                  </div>
                </div>
              </Card>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
