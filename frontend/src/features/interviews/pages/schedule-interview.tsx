import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Avatar } from '@/shared/components/ui/avatar';
import { Badge } from '@/shared/components/ui/badge';
import { Input } from '@/shared/components/ui/input';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/shared/components/ui/select';
import { customToast } from '@/shared/components/ui/toast';
import { interviewsService } from '@/services/interviews.service';
import apiClient from '@/lib/api-client';
import { cn } from '@/utils/cn';
import { useLanguage } from '@/contexts/language-context';
import {
  ChevronLeft, Loader2, Save, Video, Phone, Users, CalendarClock,
  Link2, MapPin, FileText, Sparkles, CheckCircle2,
} from 'lucide-react';

interface ApplicationOption {
  id: string;
  candidate_name: string;
  job_title: string;
  score: number | null;
  status: string;
}

const INTERVIEW_TYPES = [
  { value: 'video', icon: Video },
  { value: 'phone', icon: Phone },
  { value: 'onsite', icon: Users },
  { value: 'technical', icon: FileText },
  { value: 'behavioral', icon: Users },
  { value: 'panel', icon: Users },
];

const DURATION_OPTIONS = [15, 30, 45, 60, 90, 120];

export default function ScheduleInterviewPage() {
  const navigate = useNavigate();
  const { t } = useLanguage();
  const [searchParams] = useSearchParams();
  const preselectedAppId = searchParams.get('appId');

  const [applications, setApplications] = useState<ApplicationOption[]>([]);
  const [loadingApps, setLoadingApps] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [formData, setFormData] = useState({
    applicationId: preselectedAppId || '',
    scheduledTime: '',
    duration: 60,
    type: 'video',
    meetingLink: '',
    location: '',
    agenda: '',
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    setLoadingApps(true);
    apiClient
      .get<{ items: any[] }>('/recruiter/applications', { status: 'interviewing' })
      .then((res) => {
        const items = (res?.items || []).map((app) => ({
          id: String(app.id),
          candidate_name: app.candidate_name || app.full_name || t('iv.fallbackCandidate'),
          job_title: app.job_title || app.role || t('iv.fallbackGeneralApplication'),
          score: app.score ?? null,
          status: app.status || 'interviewing',
        }));
        setApplications(items);
        if (!preselectedAppId && items.length > 0) {
          setFormData((prev) => ({ ...prev, applicationId: items[0].id }));
        }
      })
      .catch((err) => {
        setError(err?.message || t('iv.scheduleLoadError'));
      })
      .finally(() => setLoadingApps(false));
  }, [preselectedAppId]);

  const selectedApp = applications.find((a) => a.id === formData.applicationId);
  const preselectedApp = preselectedAppId
    ? applications.find((a) => a.id === preselectedAppId)
    : undefined;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.applicationId) {
      setSubmitError(t('iv.scheduleSelectCandidate'));
      return;
    }
    if (!formData.scheduledTime) {
      setSubmitError(t('iv.scheduleSelectDateTime'));
      return;
    }

    setIsSubmitting(true);
    setSubmitError(null);

    try {
      await interviewsService.scheduleInterview({
        applicationId: Number(formData.applicationId),
        scheduledAt: formData.scheduledTime,
        duration: formData.duration,
        type: formData.type,
        meetingUrl: formData.meetingLink || undefined,
        location: formData.location || undefined,
        notes: formData.agenda || undefined,
      });
      customToast({ type: 'success', title: t('iv.scheduleSuccessTitle'), message: t('iv.scheduleSuccessMsg') });
      navigate('/interviews');
    } catch (err: any) {
      setSubmitError(err?.message || t('iv.scheduleFailed'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const getMinDateTime = () => {
    const d = new Date();
    d.setMinutes(d.getMinutes() + 30);
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={() => navigate('/interviews')}>
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white flex items-center gap-2">
            <CalendarClock className="h-6 w-6 text-purple-500" />
            {t('iv.scheduleTitle')}
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {t('iv.scheduleSubtitle')}
          </p>
        </div>
      </div>

      {loadingApps ? (
        <Card className="glass-panel border-purple-200/60 dark:border-purple-500/20">
          <CardContent className="pt-6 flex flex-col items-center justify-center py-16">
            <Loader2 className="h-8 w-8 animate-spin text-purple-600" />
            <p className="mt-3 text-sm text-gray-500 dark:text-gray-400">{t('iv.scheduleLoading')}</p>
          </CardContent>
        </Card>
      ) : error ? (
        <Card className="glass-panel border-purple-200/60 dark:border-purple-500/20">
          <CardContent className="pt-6 text-center py-12">
            <p className="text-red-500">{error}</p>
            <Button variant="outline" className="mt-4" onClick={() => window.location.reload()}>
              {t('common.retry')}
            </Button>
          </CardContent>
        </Card>
      ) : applications.length === 0 ? (
        <Card className="glass-panel border-purple-200/60 dark:border-purple-500/20">
          <CardContent className="pt-6 text-center py-16">
            <div className="mx-auto w-16 h-16 rounded-full bg-purple-50 dark:bg-purple-500/10 flex items-center justify-center mb-4">
              <Users className="h-8 w-8 text-purple-400" />
            </div>
            <p className="font-bold text-gray-800 dark:text-gray-200 mb-1">{t('iv.scheduleEmptyTitle')}</p>
            <p className="text-sm text-gray-500 dark:text-gray-400 max-w-md mx-auto">
              {t('iv.scheduleEmptyDesc')}
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid md:grid-cols-3 gap-6 items-start">
          <div className="md:col-span-2 space-y-6">
            {preselectedApp && (
              <Card variant="glass" padding="md" className="border-purple-200/60 dark:border-purple-500/20">
                <CardContent className="p-0">
                  <div className="flex items-center gap-3">
                    <Avatar name={preselectedApp.candidate_name} size="lg" />
                    <div className="flex-1 min-w-0">
                      <div className="font-bold text-gray-900 dark:text-white truncate flex items-center gap-2">
                        {preselectedApp.candidate_name}
                        <Badge variant="info" size="sm">{t('iv.status.interviewing')}</Badge>
                      </div>
                      <div className="text-sm text-gray-500 dark:text-gray-400 truncate">
                        {preselectedApp.job_title}
                      </div>
                    </div>
                    {preselectedApp.score != null && (
                      <div className="text-right shrink-0">
                        <div className="text-lg font-black text-purple-600 dark:text-purple-400">
                          {preselectedApp.score}%
                        </div>
                        <div className="text-[10px] font-bold text-gray-400 uppercase">{t('iv.aiScore')}</div>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}

            <Card className="glass-panel border-purple-200/60 dark:border-purple-500/20">
              <CardContent className="pt-6">
                <form onSubmit={handleSubmit} className="space-y-6">
                  <div className="space-y-1.5">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                      {t('iv.candidateLabel')} <span className="text-purple-500">*</span>
                    </label>
                    <Select
                      value={formData.applicationId}
                      onValueChange={(v) => setFormData({ ...formData, applicationId: v })}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder={t('iv.selectCandidatePlaceholder')} />
                      </SelectTrigger>
                      <SelectContent>
                        {applications.map((app) => (
                          <SelectItem key={app.id} value={app.id}>
                            {app.candidate_name} — {app.job_title}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="sm:col-span-2">
                      <Input
                        label={`${t('iv.dateTimeLabel')} *`}
                        type="datetime-local"
                        value={formData.scheduledTime}
                        onChange={(e) => setFormData({ ...formData, scheduledTime: e.target.value })}
                        min={getMinDateTime()}
                        leftIcon={<CalendarClock className="h-4 w-4 text-purple-500" />}
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      {t('iv.durationLabel')} <span className="text-purple-500">*</span>
                    </label>
                    <div className="flex flex-wrap gap-2">
                      {DURATION_OPTIONS.map((d) => (
                        <button
                          key={d}
                          type="button"
                          className={cn(
                            'px-4 py-2 text-sm font-bold rounded-xl border-2 transition-all',
                            formData.duration === d
                              ? 'bg-purple-600 text-white border-purple-600 shadow-md shadow-purple-500/25'
                              : 'bg-white dark:bg-white/5 text-gray-600 dark:text-gray-400 border-gray-200 dark:border-white/10 hover:border-purple-300'
                          )}
                          onClick={() => setFormData({ ...formData, duration: d })}
                        >
                          {d} {t('camp.create.min')}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      {t('iv.typeLabel')} <span className="text-purple-500">*</span>
                    </label>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                      {INTERVIEW_TYPES.map((it) => (
                        <button
                          key={it.value}
                          type="button"
                          className={cn(
                            'flex flex-col items-center gap-1.5 p-3 rounded-xl border-2 transition-all text-center',
                            formData.type === it.value
                              ? 'border-purple-500 bg-purple-50 dark:bg-purple-500/10 shadow-md shadow-purple-500/10'
                              : 'border-gray-200 dark:border-white/10 bg-white/50 dark:bg-white/[0.02] hover:border-purple-300'
                          )}
                          onClick={() => setFormData({ ...formData, type: it.value })}
                        >
                          <it.icon className={cn('h-5 w-5', formData.type === it.value ? 'text-purple-600 dark:text-purple-400' : 'text-gray-400')} />
                          <span className="text-xs font-bold text-gray-800 dark:text-gray-200">{t(`iv.type.${it.value}`)}</span>
                          <span className="text-[10px] text-gray-400 hidden sm:block">{t(`iv.type.${it.value}Desc`)}</span>
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <Input
                      label={t('iv.meetingLink')}
                      type="url"
                      placeholder="https://meet.google.com/..."
                      value={formData.meetingLink}
                      onChange={(e) => setFormData({ ...formData, meetingLink: e.target.value })}
                      leftIcon={<Link2 className="h-4 w-4 text-indigo-500" />}
                    />
                    <Input
                      label={t('common.location')}
                      placeholder={t('iv.locationPlaceholder')}
                      value={formData.location}
                      onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                      leftIcon={<MapPin className="h-4 w-4 text-amber-500" />}
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                      {t('iv.agendaNotes')}
                    </label>
                    <textarea
                      value={formData.agenda}
                      onChange={(e) => setFormData({ ...formData, agenda: e.target.value })}
                      placeholder={t('iv.agendaPlaceholder')}
                      rows={4}
                      className="w-full rounded-xl border border-purple-200/60 bg-white/70 p-3 text-sm focus:ring-2 focus:ring-purple-500/20 dark:border-white/10 dark:bg-white/5 dark:text-white min-h-[80px] resize-none"
                    />
                  </div>

                  {submitError && (
                    <p className="text-sm text-red-500">{submitError}</p>
                  )}

                  <div className="flex justify-end gap-3 pt-2 border-t border-gray-100 dark:border-white/10">
                    <Button variant="outline" onClick={() => navigate('/interviews')} disabled={isSubmitting}>
                      {t('common.cancel')}
                    </Button>
                    <Button
                      variant="primary"
                      size="lg"
                      className="px-8 font-bold shadow-lg shadow-purple-500/25"
                      leftIcon={isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                      type="submit"
                      disabled={isSubmitting}
                    >
                      {isSubmitting ? t('iv.scheduling') : t('iv.scheduleTitle')}
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          </div>

          <div className="space-y-4">
            <Card variant="glass" padding="md" className="border-purple-200/60 dark:border-purple-500/20">
              <CardContent className="p-0">
                <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                  <Sparkles className="h-3.5 w-3.5 text-purple-500" />
                  {t('iv.summary')}
                </h3>
                <dl className="space-y-3">
                  <div>
                    <dt className="text-xs text-gray-400">{t('iv.candidateLabel')}</dt>
                    <dd className="text-sm font-bold text-gray-800 dark:text-gray-200 truncate">
                      {selectedApp?.candidate_name || '—'}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-gray-400">{t('iv.position')}</dt>
                    <dd className="text-sm font-bold text-gray-800 dark:text-gray-200 truncate">
                      {selectedApp?.job_title || '—'}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-gray-400">{t('iv.dateTimeLabel')}</dt>
                    <dd className="text-sm font-bold text-gray-800 dark:text-gray-200">
                      {formData.scheduledTime
                        ? new Date(formData.scheduledTime).toLocaleString(undefined, {
                            weekday: 'short',
                            month: 'short',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit',
                          })
                        : t('iv.notSetYet')}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-gray-400">{t('iv.type')}</dt>
                    <dd className="text-sm font-bold text-gray-800 dark:text-gray-200 capitalize">
                      {formData.type || '—'}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-gray-400">{t('iv.duration')}</dt>
                    <dd className="text-sm font-bold text-gray-800 dark:text-gray-200">
                      {formData.duration} {t('camp.create.minutes')}
                    </dd>
                  </div>
                </dl>
              </CardContent>
            </Card>

            <div className="flex items-start gap-2 p-3 rounded-xl bg-purple-50 dark:bg-purple-500/10 text-purple-700 dark:text-purple-300 text-sm">
              <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{t('iv.scheduleNotice')}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
