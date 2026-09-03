import { motion } from 'framer-motion';
import { useNavigate } from 'react-router';
import { useAuth } from '@/contexts/auth-context';
import { useLanguage } from '@/contexts/language-context';
import { useRecruiterStats, useApplications } from '@/shared/hooks';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Avatar } from '@/shared/components/ui/avatar';
import { cn } from '@/utils/cn';
import {
  Briefcase, Users, Calendar,
  Plus, Target, ChevronRight, Loader2,
} from 'lucide-react';

export default function RecruiterDashboard() {
  const { user } = useAuth();
  const { t } = useLanguage();
  const navigate = useNavigate();
  const { data: stats, isLoading: statsLoading } = useRecruiterStats();
  const { data: appsData, isLoading: appsLoading } = useApplications({ per_page: 5 });

  const statCards = [
    { label: t('recruiter.dash.activeJobs'), value: stats?.active_jobs_count ?? '—', icon: Briefcase, color: 'bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400' },
    { label: t('recruiter.dash.totalApplications'), value: stats?.total_applications ?? '—', icon: Users, color: 'bg-purple-50 text-purple-600 dark:bg-purple-500/10 dark:text-purple-400' },
    { label: t('recruiter.dash.interviews'), value: stats?.scheduled_interviews ?? stats?.interviewing ?? '—', icon: Calendar, color: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400' },
    { label: t('recruiter.dash.avgTimeToHire'), value: stats?.avg_time_to_hire ?? '—', icon: Target, color: 'bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400' },
  ];

  const pipelineStages = [
    { name: t('recruiter.dash.stage.applied'), count: Number(stats?.applied ?? stats?.total_applications ?? 0), color: 'bg-gray-500', href: '/recruiter/applications?status=applied' },
    { name: t('recruiter.dash.stage.screening'), count: Number(stats?.screening_count ?? 0), color: 'bg-blue-500', href: '/recruiter/applications?status=screening' },
    { name: t('recruiter.dash.stage.interview'), count: Number(stats?.interviewing ?? 0), color: 'bg-purple-500', href: '/interviews' },
    { name: t('recruiter.dash.stage.offer'), count: Number(stats?.offer_count ?? 0), color: 'bg-amber-500', href: '/recruiter/applications?status=offer' },
    { name: t('recruiter.dash.stage.hired'), count: Number(stats?.hired ?? 0), color: 'bg-emerald-500', href: '/recruiter/applications?status=hired' },
  ];

  const hasPipelineActivity = !statsLoading && (Number(stats?.total_applications ?? 0) > 0 || (appsData?.items ?? []).length > 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{t('recruiter.dash.welcome')}, {user?.firstName} 👋</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{t('recruiter.dash.subtitle')}</p>
        </div>
        <div className="flex items-center gap-3">
          {hasPipelineActivity ? (
            <>
              <Button id="review-applications-btn" variant="primary" leftIcon={<Users className="h-4 w-4" />} onClick={() => navigate('/recruiter/applications')}>{t('candidates.title')}</Button>
              <Button id="post-new-job-btn" variant="outline" leftIcon={<Plus className="h-4 w-4" />} onClick={() => navigate('/jobs/new')}>{t('recruiter.dash.postJob')}</Button>
            </>
          ) : (
            <Button id="post-new-job-btn" variant="primary" leftIcon={<Plus className="h-4 w-4" />} onClick={() => navigate('/jobs/new')}>{t('recruiter.dash.postJob')}</Button>
          )}
        </div>
      </div>

      {statsLoading ? (
        <div className="flex items-center justify-center py-12"><Loader2 className="h-8 w-8 animate-spin text-purple-600" /></div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {statCards.map((stat, i) => (
              <motion.div key={stat.label} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: i * 0.05 }}>
                <Card hoverable>
                  <CardContent>
                    <div className="flex items-center justify-between">
                      <div className={cn('flex h-10 w-10 items-center justify-center rounded-xl', stat.color)}><stat.icon className="h-5 w-5" /></div>
                    </div>
                    <div className="mt-4">
                      <div className="text-2xl font-bold text-gray-900 dark:text-white">{stat.value}</div>
                      <div className="text-sm text-gray-500 dark:text-gray-400">{stat.label}</div>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <Card className="lg:col-span-2">
              <CardContent>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{t('dash.pipelineOverview')}</h3>
                </div>
                <div className="space-y-3">
                  {pipelineStages.map((stage) => (
                    <button
                      key={stage.name}
                      onClick={() => navigate(stage.href)}
                      title={`${t('common.view')} ${stage.name} ${t('recruiter.dash.applications')}`}
                      className="w-full flex items-center gap-3 group"
                    >
                      <div className={cn('h-2.5 w-2.5 rounded-full shrink-0', stage.color)} />
                      <span className="text-sm text-gray-600 dark:text-gray-400 w-24 text-left group-hover:text-violet-600 dark:group-hover:text-violet-400 transition-colors">{stage.name}</span>
                      <div className="flex-1 h-2 bg-gray-100 dark:bg-white/5 rounded-full overflow-hidden">
                        <div className={cn('h-full rounded-full transition-all', stage.color)} style={{ width: `${Math.min(100, (stage.count / Math.max(1, pipelineStages[0].count)) * 100)}%` }} />
                      </div>
                      <span className="text-sm font-medium text-gray-700 dark:text-gray-300 w-10 text-right">{stage.count}</span>
                      <ChevronRight className="h-4 w-4 text-gray-300 group-hover:text-violet-500 transition-colors shrink-0" />
                    </button>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{t('dash.recentApplications')}</h3>
                  <button
                    onClick={() => navigate('/recruiter/applications')}
                    className="inline-flex items-center gap-1 text-xs font-semibold text-violet-600 dark:text-violet-400 hover:underline"
                  >
                    {t('common.viewAll')} <ChevronRight className="h-3 w-3" />
                  </button>
                </div>
                {appsLoading ? (
                  <div className="flex justify-center py-4"><Loader2 className="h-5 w-5 animate-spin text-purple-600" /></div>
                ) : (
                  <div className="space-y-3">
                    {(appsData?.items ?? []).slice(0, 5).map((app: any) => (
                      <div
                        key={app.id}
                        onClick={() => navigate(`/candidates/${app.id}`)}
                        className="flex items-center gap-3 p-2 rounded-xl hover:bg-gray-50 dark:hover:bg-white/[0.02] cursor-pointer transition-colors group"
                      >
                        <Avatar name={app.candidate_name || app.full_name || '?'} size="sm" />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-gray-900 dark:text-white truncate group-hover:text-purple-700 dark:group-hover:text-purple-400 transition-colors">{app.candidate_name || app.full_name || t('role.candidate')}</p>
                          <p className="text-xs text-gray-500 truncate">{app.job_title || app.declared_role || t('nav.recruiter_applications')}</p>
                        </div>
                        {(() => {
                          const interviewDone = ['completed', 'flagged'].includes(app.interview_state);
                          // CANONICAL SCORE CONTRACT:
                          // pre-interview -> cv_score
                          // post-interview -> final_score
                          const score = interviewDone
                            ? (app.final_score ?? app.score ?? null)
                            : (app.cv_score ?? null);
                          if (score == null || score <= 0) return null;
                          return (
                            <div className={cn('text-xs font-bold px-2 py-0.5 rounded', score >= 80 ? 'bg-emerald-50 text-emerald-600' : score >= 60 ? 'bg-amber-50 text-amber-600' : 'bg-red-50 text-red-600')}>
                              {score}
                            </div>
                          );
                        })()}
                        <ChevronRight className="h-3.5 w-3.5 text-gray-300 dark:text-gray-600 opacity-0 group-hover:opacity-100 transition-opacity" />
                      </div>
                    ))}
                    {(!appsData?.items || appsData.items.length === 0) && (
                      <p className="text-sm text-gray-400 text-center py-4">{t('common.noData')}</p>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}