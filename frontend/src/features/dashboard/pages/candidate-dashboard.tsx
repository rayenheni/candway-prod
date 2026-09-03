import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router';
import { motion } from 'framer-motion';
import { useAuth } from '@/contexts/auth-context';
import { useLanguage } from '@/contexts/language-context';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Avatar } from '@/shared/components/ui/avatar';
import { cn } from '@/utils/cn';
import {
  Briefcase, Calendar, TrendingUp, ArrowUpRight, ArrowDownRight, Clock, Target,
  ChevronRight, Award, Zap, Loader2,
} from 'lucide-react';
import { candidateService } from '@/services/candidate.service';
import { customToast } from '@/shared/components/ui/toast';

const statusColors: Record<string, string> = {
  pending: 'default',
  screening: 'info',
  shortlisted: 'primary',
  interview: 'warning',
  offer: 'success',
  hired: 'success',
  rejected: 'danger',
  withdrawn: 'default',
  offer_declined: 'danger',
};

export default function CandidateDashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { t } = useLanguage();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await candidateService.getDashboard();
      setData(res);
    } catch (err) {
      console.error('Failed to load candidate dashboard:', err);
      setData(null);
      customToast?.({ type: 'error', title: t('candidate.dash.unavailable'), message: t('candidate.dash.unavailableMsg') });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  const stats = [
    {
      label: t('dash.activeApplications'), value: data?.applications_count ?? 0,
      change: data?.applications_change, icon: Briefcase,
      color: 'bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400',
    },
    {
      label: t('dash.interviews'), value: data?.interviews_count ?? (data?.upcoming_interviews ?? []).length,
      change: data?.interviews_change, icon: Calendar,
      color: 'bg-purple-50 text-purple-600 dark:bg-purple-500/10 dark:text-purple-400',
    },
    {
      label: t('dash.profileViews'), value: data?.profile_views ?? 0,
      change: data?.profile_views_growth ? `+${data.profile_views_growth}` : null, icon: TrendingUp,
      color: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400',
    },
    {
      label: t('dash.skillScore'), value: data?.score ?? 0,
      change: data?.score_change, icon: Target,
      color: 'bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400',
    },
  ];

  const statusLabel = (s: string) => {
    const labels: Record<string, string> = {
      pending: t('iv.tab.pending'),
      screening: t('recruiter.dash.stage.screening'),
      shortlisted: t('candidates.tab.shortlisted'),
      interview: t('apps.interview'),
      offer: t('org.offer'),
      hired: t('candidates.tab.hired'),
      rejected: t('apps.rejected'),
      withdrawn: t('apps.withdrawn'),
      offer_declined: t('recruiter.offers.status.declined'),
    };
    return labels[s] || (s.charAt(0).toUpperCase() + s.slice(1));
  };

  const trendFor = (change?: string | null) => {
    if (change == null) return null;
    const trimmed = change.trim();
    if (!trimmed || trimmed === '+0' || trimmed === '0') return null;
    return trimmed.startsWith('-') ? 'down' : 'up';
  };

  const applications = data?.applications ?? [];
  const skills = data?.skills ?? [];
  const achievements = data?.achievements ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            {t('dash.welcomeCandidate')} {user?.firstName || data?.name || t('candidate.dash.there')}!
          </h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            {t('dash.candidateSubtitle')}
          </p>
        </div>
        <Button variant="primary" leftIcon={<Zap className="h-4 w-4" />} onClick={() => navigate('/jobs')}>
          {t('dash.findJobs')}
        </Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat, i) => (
          <motion.div key={stat.label} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: i * 0.05 }}>
            <Card hoverable>
              <CardContent>
                <div className="flex items-center justify-between">
                  <div className={cn('flex h-10 w-10 items-center justify-center rounded-xl', stat.color)}>
                    <stat.icon className="h-5 w-5" />
                  </div>
                {stat.change != null && stat.change !== '' && stat.change !== '+0' && trendFor(stat.change) && (
                  <div className={cn('flex items-center gap-1 text-xs font-medium', trendFor(stat.change) === 'up' ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600')}>
                    {trendFor(stat.change) === 'up' ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
                    {stat.change}
                  </div>
                )}
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
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.2 }} className="lg:col-span-2">
          <Card>
            <CardHeader action={
              <Button variant="ghost" size="sm" rightIcon={<ChevronRight className="h-4 w-4" />} onClick={() => navigate('/applications')}>
                {t('dash.viewAll')}
              </Button>
            }>
              <CardTitle>{t('dash.myApplications')}</CardTitle>
              <CardDescription>{t('dash.trackApplications')}</CardDescription>
            </CardHeader>
            <CardContent>
                {applications.length === 0 ? (
                  <div className="text-center py-8">
                    <Briefcase className="h-10 w-10 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
                    <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">{t('candidate.dash.noApplications')}</p>
                    <Button variant="primary" size="sm" onClick={() => navigate('/jobs')}>{t('dash.findJobs')}</Button>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {applications.map((app: any) => {
                      const appDate = app.created_at ? new Date(app.created_at).toLocaleDateString() : null;
                      return (
                        <div
                          key={app.id}
                          onClick={() => navigate(`/applications?focus=${app.id}`)}
                          className="flex items-center gap-4 p-4 rounded-xl border border-gray-100 dark:border-white/[0.04] hover:border-gray-200 dark:hover:border-white/[0.08] cursor-pointer transition-all group"
                        >
                          <Avatar name={app.company || app.title} size="md" square />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium text-gray-900 dark:text-white group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">{app.title || app.role}</span>
                              <Badge variant={(statusColors[app.status] || 'default') as any} size="sm">
                                {statusLabel(app.status || 'pending')}
                              </Badge>
                            </div>
                            <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{app.company || t('candidate.dash.company')}</div>
                            {appDate && (
                              <div className="flex items-center gap-1 mt-1">
                                <Clock className="h-3 w-3 text-gray-300" />
                                <span className="text-xs text-gray-400">{appDate}</span>
                              </div>
                            )}
                          </div>
                          <ChevronRight className="h-4 w-4 text-gray-300 dark:text-gray-600 opacity-0 group-hover:opacity-100 transition-opacity" />
                        </div>
                      );
                    })}
                  </div>
                )}
            </CardContent>
          </Card>
        </motion.div>

        <div className="space-y-6">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.3 }}>
            <Card>
              <CardHeader>
                <CardTitle>{t('candidate.dash.mySkills')}</CardTitle>
                <CardDescription>{skills.length} {t('candidate.dash.skillsFromProfile')}</CardDescription>
              </CardHeader>
              <CardContent>
                {skills.length === 0 ? (
                  <div className="text-center py-6 text-gray-500 dark:text-gray-400 text-sm">
                    <p className="mb-3">{t('candidate.dash.updateProfileToAddSkills')}</p>
                    <Button variant="outline" size="sm" onClick={() => navigate('/profile')}>{t('candidate.dash.updateProfile')}</Button>
                  </div>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {skills.map((s: string) => (
                      <span key={s} className="px-2.5 py-1 text-xs font-medium rounded-full bg-blue-50 text-blue-700 dark:bg-blue-500/10 dark:text-blue-300">
                        {s}
                      </span>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.4 }}>
            <Card>
              <CardHeader>
                <CardTitle>{t('dash.achievements')}</CardTitle>
                <CardDescription>{achievements.filter((a: any) => a.unlocked).length} {t('common.of')} {achievements.length} {t('candidate.dash.unlocked')}</CardDescription>
              </CardHeader>
              <CardContent>
                {achievements.length === 0 ? (
                  <div className="text-center py-6 text-gray-500 dark:text-gray-400 text-sm">
                    {t('candidate.dash.noAchievements')}
                  </div>
                ) : (
                  <div className="grid grid-cols-4 gap-2">
                    {achievements.map((a: any) => (
                      <div key={a.slug} className={cn('flex flex-col items-center gap-1.5 p-2 rounded-xl transition-all', a.unlocked ? 'bg-gray-50 dark:bg-white/[0.04]' : 'opacity-40 grayscale')} title={a.name}>
                        <Award className={cn('w-6 h-6', a.unlocked ? 'text-blue-500' : 'text-gray-400')} />
                        <span className="text-[10px] text-center text-gray-600 dark:text-gray-400 leading-tight">{a.name}</span>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
