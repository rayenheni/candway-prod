import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Avatar } from '@/shared/components/ui/avatar';
import { Badge } from '@/shared/components/ui/badge';
import { Input } from '@/shared/components/ui/input';
import { EmptyState } from '@/shared/components/ui/empty-state';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/shared/components/ui/dialog';
import { customToast } from '@/shared/components/ui/toast';
import { interviewsService } from '@/services/interviews.service';
import { candidatesService } from '@/services/candidates.service';
import { cn } from '@/utils/cn';
import { useLanguage } from '@/contexts/language-context';
import {
  ChevronLeft, Loader2, Calendar, Clock, Video, Phone, Users,
  MapPin, Link2, FileText, UserCircle, CheckCircle2, XCircle,
  Star, Pencil, Send, RefreshCw,
} from 'lucide-react';

interface FeedbackItem {
  id: string;
  interviewer_name: string;
  interviewer_email?: string | null;
  technical_rating?: number | null;
  communication_rating?: number | null;
  culture_fit_rating?: number | null;
  problem_solving_rating?: number | null;
  overall_rating: number;
  strengths?: string | null;
  concerns?: string | null;
  additional_notes?: string | null;
  recommendation: string;
  created_at: string;
}

interface InterviewDetail {
  id: number;
  application_id: number;
  candidate_name: string;
  candidate_email: string;
  photo_url?: string | null;
  job_title: string;
  scheduled_time: string;
  duration_minutes: number;
  type: string;
  meeting_link: string | null;
  location: string | null;
  status: string;
  agenda: string | null;
  interviewers: { id: number; name: string; email: string; role: string; status: string }[];
  feedback_collected: boolean;
  ai_score: number | null;
  cv_score: number | null;
  application_status: string;
  created_at: string;
  internal_notes: string | null;
  feedback: FeedbackItem[];
}

const typeIcons: Record<string, typeof Video> = {
  video: Video,
  phone: Phone,
  onsite: Users,
  technical: FileText,
  behavioral: Users,
  panel: Users,
};

const statusConfig: Record<string, { variant: string }> = {
  scheduled: { variant: 'info' },
  rescheduled: { variant: 'info' },
  completed: { variant: 'success' },
  cancelled: { variant: 'danger' },
  no_show: { variant: 'danger' },
};

const recommendationVariants: Record<string, string> = {
  strong_yes: 'success',
  yes: 'success',
  maybe: 'warning',
  no: 'danger',
  strong_no: 'danger',
};

const APPLICATION_STATUS_VALUES = ['pending', 'screening', 'interviewing', 'shortlisted', 'offer', 'hired', 'rejected', 'archived'];

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleString(undefined, {
      weekday: 'long',
      month: 'long',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function formatShortDate(iso: string) {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function RatingStars({ value }: { value: number }) {
  return (
    <div className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((n) => (
        <Star
          key={n}
          className={cn(
            'h-3.5 w-3.5',
            n <= value ? 'fill-amber-400 text-amber-400' : 'text-gray-300 dark:text-gray-600'
          )}
        />
      ))}
      <span className="ml-1.5 text-sm font-semibold text-gray-700 dark:text-gray-300">{value}/5</span>
    </div>
  );
}

export default function InterviewDetailPage() {
  const navigate = useNavigate();
  const { id } = useParams();
  const { t } = useLanguage();

  const statusLabels: Record<string, string> = {
    scheduled: t('iv.status.scheduled'),
    rescheduled: t('iv.status.rescheduled'),
    completed: t('iv.status.completed'),
    cancelled: t('iv.status.cancelled'),
    no_show: t('iv.status.noShow'),
  };
  const recommendationLabels: Record<string, string> = {
    strong_yes: t('iv.recommendation.strong_yes'),
    yes: t('iv.recommendation.yes'),
    maybe: t('iv.recommendation.maybe'),
    no: t('iv.recommendation.no'),
    strong_no: t('iv.recommendation.strong_no'),
  };
  const ratingLabels = ['', t('iv.rating.poor'), t('iv.rating.fair'), t('iv.rating.good'), t('iv.rating.veryGood'), t('iv.rating.excellent')];

  const [interview, setInterview] = useState<InterviewDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [editOpen, setEditOpen] = useState(false);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [cancelOpen, setCancelOpen] = useState(false);

  const [editForm, setEditForm] = useState({ scheduledTime: '', meetingLink: '', location: '', agenda: '' });
  const [feedbackForm, setFeedbackForm] = useState({
    overall_rating: 4,
    technical_rating: 0,
    communication_rating: 0,
    culture_fit_rating: 0,
    problem_solving_rating: 0,
    recommendation: 'yes',
    strengths: '',
    concerns: '',
    additional_notes: '',
  });
  const [saving, setSaving] = useState(false);
  const [statusUpdating, setStatusUpdating] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    interviewsService
      .getInterview(id as string)
      .then((res: any) => {
        setInterview(res);
      })
      .catch((err) => setError(err?.message || t('iv.detailLoadError')))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    if (id) load();
  }, [id, load]);

  const handleSave = async () => {
    if (!interview) return;
    setSaving(true);
    try {
      await interviewsService.updateInterview(String(interview.id), {
        scheduled_time: editForm.scheduledTime || undefined,
        meeting_link: editForm.meetingLink || undefined,
        location: editForm.location || undefined,
        agenda: editForm.agenda || undefined,
      } as any);
      customToast({ type: 'success', title: t('iv.updatedTitle') });
      setEditOpen(false);
      load();
    } catch (e: any) {
      customToast({ type: 'error', title: t('iv.updateFailedTitle'), message: e?.message });
    } finally {
      setSaving(false);
    }
  };

  const handleSubmitFeedback = async () => {
    if (!interview) return;
    setSaving(true);
    try {
      await interviewsService.submitFeedback(String(interview.id), {
        overall_rating: feedbackForm.overall_rating,
        technical_rating: feedbackForm.technical_rating || undefined,
        communication_rating: feedbackForm.communication_rating || undefined,
        culture_fit_rating: feedbackForm.culture_fit_rating || undefined,
        problem_solving_rating: feedbackForm.problem_solving_rating || undefined,
        recommendation: feedbackForm.recommendation,
        strengths: feedbackForm.strengths || undefined,
        concerns: feedbackForm.concerns || undefined,
        additional_notes: feedbackForm.additional_notes || undefined,
      } as any);
      customToast({ type: 'success', title: t('iv.feedbackSubmittedTitle') });
      setFeedbackOpen(false);
      load();
    } catch (e: any) {
      customToast({ type: 'error', title: t('iv.feedbackFailedTitle'), message: e?.message });
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = async () => {
    if (!interview) return;
    setSaving(true);
    try {
      await interviewsService.cancelInterview(String(interview.id), 'Cancelled from detail page');
      customToast({ type: 'success', title: t('iv.cancelledTitle') });
      setCancelOpen(false);
      load();
    } catch (e: any) {
      customToast({ type: 'error', title: t('iv.cancelFailedTitle'), message: e?.message });
    } finally {
      setSaving(false);
    }
  };

  const handleStatusChange = async (status: string) => {
    if (!interview || status === interview.application_status) return;
    setStatusUpdating(true);
    try {
      await candidatesService.updateApplicationStatus(String(interview.application_id), status);
      customToast({ type: 'success', title: t('iv.statusUpdatedTitle'), message: t('iv.statusUpdatedMsg').replace('{status}', status) });
      load();
    } catch (e: any) {
      customToast({ type: 'error', title: t('iv.statusUpdateFailedTitle'), message: e?.message });
    } finally {
      setStatusUpdating(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-purple-600" />
      </div>
    );
  }

  if (error || !interview) {
    return (
      <EmptyState
        icon={<XCircle className="h-6 w-6 text-red-400" />}
        title={t('iv.detailNotFoundTitle')}
        description={error || t('iv.detailNotFoundDesc')}
        action={{ label: t('iv.backToInterviews'), onClick: () => navigate('/interviews') }}
      />
    );
  }

  const TypeIcon = typeIcons[interview.type] || Video;
  const statusVariant = statusConfig[interview.status]?.variant || 'default';
  const statusLabel = statusLabels[interview.status] || interview.status;
  const canGiveFeedback = interview.status === 'completed' || interview.status === 'scheduled';

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={() => navigate('/interviews')}>
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">{interview.candidate_name}</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">{interview.job_title}</p>
        </div>
        <Badge variant={statusVariant as any} size="lg" dot>
          {statusLabel}
        </Badge>
      </div>

      <div className="grid md:grid-cols-3 gap-6 items-start">
        <div className="md:col-span-2 space-y-6">
          <Card className="glass-panel border-purple-200/60 dark:border-purple-500/20">
            <CardContent className="pt-6">
              <div className="flex flex-col sm:flex-row sm:items-center gap-4">
                <Avatar src={interview.photo_url} name={interview.candidate_name} size="lg" />
                <div className="flex-1 min-w-0">
                  <div className="font-bold text-lg text-gray-900 dark:text-white">{interview.candidate_name}</div>
                  <div className="text-sm text-gray-500 dark:text-gray-400">{interview.candidate_email}</div>
                  <div className="mt-1 text-sm text-gray-600 dark:text-gray-300">
                    {t('iv.applicationFor')} <span className="font-semibold">{interview.job_title}</span>
                    <span className="mx-1.5 text-gray-300">·</span>
                    {t('common.status')}:{' '}
                    <label className="inline-flex items-center gap-1.5">
                      <select
                        value={interview.application_status || 'pending'}
                        onChange={(e) => handleStatusChange(e.target.value)}
                        disabled={statusUpdating}
                        className="rounded-lg border border-purple-200/60 bg-white/70 dark:border-white/10 dark:bg-white/5 dark:text-white px-2 py-0.5 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-purple-500/20 disabled:opacity-60 [&>option]:bg-white [&>option]:text-gray-900"
                      >
                        {APPLICATION_STATUS_VALUES.map((v) => (
                          <option key={v} value={v}>{t(`iv.appStatus.${v}`)}</option>
                        ))}
                      </select>
                      {statusUpdating && <Loader2 className="h-3.5 w-3.5 animate-spin text-purple-500" />}
                    </label>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2 shrink-0">
                  <Button variant="outline" size="sm" leftIcon={<Pencil className="h-3.5 w-3.5" />} onClick={() => {
                    setEditForm({
                      scheduledTime: interview.scheduled_time?.slice(0, 16) || '',
                      meetingLink: interview.meeting_link || '',
                      location: interview.location || '',
                      agenda: interview.agenda || '',
                    });
                    setEditOpen(true);
                  }}>
                    {t('common.edit')}
                  </Button>
                  {interview.status !== 'cancelled' && interview.status !== 'completed' && (
                    <Button variant="danger" size="sm" leftIcon={<XCircle className="h-3.5 w-3.5" />} onClick={() => setCancelOpen(true)}>
                      {t('common.cancel')}
                    </Button>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <Card variant="elevated">
              <CardContent>
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-50 dark:bg-purple-500/10">
                    <Calendar className="h-5 w-5 text-purple-600 dark:text-purple-400" />
                  </div>
                  <div className="min-w-0">
                    <div className="text-[10px] font-bold text-gray-400 uppercase">{t('iv.status.scheduled')}</div>
                    <div className="text-sm font-bold text-gray-900 dark:text-white truncate">
                      {new Date(interview.scheduled_time).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card variant="elevated">
              <CardContent>
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50 dark:bg-blue-500/10">
                    <Clock className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                  </div>
                  <div>
                    <div className="text-[10px] font-bold text-gray-400 uppercase">{t('common.time')}</div>
                    <div className="text-sm font-bold text-gray-900 dark:text-white">
                      {new Date(interview.scheduled_time).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card variant="elevated">
              <CardContent>
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 dark:bg-indigo-500/10">
                    <Clock className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
                  </div>
                  <div>
                    <div className="text-[10px] font-bold text-gray-400 uppercase">{t('iv.duration')}</div>
                    <div className="text-sm font-bold text-gray-900 dark:text-white">{interview.duration_minutes} {t('camp.create.min')}</div>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card variant="elevated">
              <CardContent>
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-50 dark:bg-amber-500/10">
                    <TypeIcon className="h-5 w-5 text-amber-600 dark:text-amber-400" />
                  </div>
                  <div>
                    <div className="text-[10px] font-bold text-gray-400 uppercase">{t('iv.type')}</div>
                    <div className="text-sm font-bold text-gray-900 dark:text-white capitalize">{interview.type}</div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="grid md:grid-cols-2 gap-6">
            <Card className="glass-panel border-purple-200/60 dark:border-purple-500/20">
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Link2 className="h-4 w-4 text-purple-500" />
                  {t('iv.meetingDetails')}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-start gap-3">
                  <Link2 className="h-4 w-4 text-gray-400 mt-0.5 shrink-0" />
                  <div className="min-w-0">
                    <div className="text-xs text-gray-400">{t('iv.meetingLink')}</div>
                    {interview.meeting_link ? (
                      <a href={interview.meeting_link} target="_blank" rel="noreferrer" className="text-sm font-medium text-purple-600 dark:text-purple-400 hover:underline break-all">
                        {interview.meeting_link}
                      </a>
                    ) : (
                      <div className="text-sm text-gray-400">{t('iv.notProvided')}</div>
                    )}
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <MapPin className="h-4 w-4 text-gray-400 mt-0.5 shrink-0" />
                  <div>
                    <div className="text-xs text-gray-400">{t('common.location')}</div>
                    <div className="text-sm font-medium text-gray-800 dark:text-gray-200">{interview.location || t('iv.notSpecified')}</div>
                  </div>
                </div>
                {interview.meeting_link && (
                  <Button variant="primary" size="sm" className="w-full" onClick={() => window.open(interview.meeting_link, '_blank')}>
                    <Video className="h-4 w-4" />
                    {t('iv.joinInterview')}
                  </Button>
                )}
              </CardContent>
            </Card>

            <Card className="glass-panel border-purple-200/60 dark:border-purple-500/20">
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Users className="h-4 w-4 text-purple-500" />
                  {t('iv.interviewers')}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {interview.interviewers.length === 0 ? (
                  <p className="text-sm text-gray-400">{t('iv.noInterviewers')}</p>
                ) : (
                  interview.interviewers.map((iv) => (
                    <div key={iv.id} className="flex items-center gap-3">
                      <Avatar name={iv.name} size="sm" />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-semibold text-gray-800 dark:text-gray-200 truncate">{iv.name}</div>
                        <div className="text-xs text-gray-400 truncate">{iv.email}</div>
                      </div>
                      <Badge variant="default" size="sm" dot>{iv.role || t('iv.interviewer')}</Badge>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>
          </div>

          <Card className="glass-panel border-purple-200/60 dark:border-purple-500/20">
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <FileText className="h-4 w-4 text-purple-500" />
                {t('iv.agendaNotes')}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {interview.agenda ? (
                <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{interview.agenda}</p>
              ) : (
                <p className="text-sm text-gray-400">{t('iv.noAgenda')}</p>
              )}
              {interview.internal_notes && (
                <div className="mt-4 p-3 rounded-lg bg-amber-50 dark:bg-amber-500/10 text-sm text-amber-800 dark:text-amber-300">
                  <span className="font-bold">{t('iv.internalNotes')}:</span> {interview.internal_notes}
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="glass-panel border-purple-200/60 dark:border-purple-500/20">
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <UserCircle className="h-4 w-4 text-purple-500" />
                {t('iv.feedback')}
              </CardTitle>
              <CardDescription>{t('iv.feedbackDesc')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {interview.feedback.length === 0 ? (
                <div className="text-center py-8">
                  <p className="text-sm text-gray-400 mb-3">{t('iv.noFeedback')}</p>
                  {canGiveFeedback && (
                    <Button variant="outline" size="sm" leftIcon={<Send className="h-3.5 w-3.5" />} onClick={() => setFeedbackOpen(true)}>
                      {t('iv.addFeedback')}
                    </Button>
                  )}
                </div>
              ) : (
                <>
                  <div className="flex justify-end">
                    {canGiveFeedback && (
                      <Button variant="outline" size="sm" leftIcon={<Send className="h-3.5 w-3.5" />} onClick={() => setFeedbackOpen(true)}>
                        {t('iv.addFeedback')}
                      </Button>
                    )}
                  </div>
                  {interview.feedback.map((fb) => {
                    const rec = { label: recommendationLabels[fb.recommendation] || fb.recommendation, variant: recommendationVariants[fb.recommendation] || 'default' };
                    return (
                      <div key={fb.id} className="p-4 rounded-xl bg-white/60 dark:bg-white/[0.03] border border-gray-100 dark:border-white/10 space-y-3">
                        <div className="flex items-center justify-between gap-3 flex-wrap">
                          <div className="flex items-center gap-2">
                            <Avatar name={fb.interviewer_name} size="sm" />
                            <div>
                              <div className="text-sm font-semibold text-gray-800 dark:text-gray-200">{fb.interviewer_name}</div>
                              <div className="text-xs text-gray-400">{formatShortDate(fb.created_at)}</div>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <Badge variant={rec.variant as any} size="sm">{rec.label}</Badge>
                            <Badge variant="primary" size="sm">{fb.overall_rating}/5</Badge>
                          </div>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                          {fb.technical_rating != null && (
                            <div>
                              <div className="text-[10px] font-bold text-gray-400 uppercase mb-1">{t('iv.ratingDim.technical')}</div>
                              <RatingStars value={fb.technical_rating} />
                            </div>
                          )}
                          {fb.communication_rating != null && (
                            <div>
                              <div className="text-[10px] font-bold text-gray-400 uppercase mb-1">{t('iv.ratingDim.communication')}</div>
                              <RatingStars value={fb.communication_rating} />
                            </div>
                          )}
                          {fb.culture_fit_rating != null && (
                            <div>
                              <div className="text-[10px] font-bold text-gray-400 uppercase mb-1">{t('iv.ratingDim.cultureFit')}</div>
                              <RatingStars value={fb.culture_fit_rating} />
                            </div>
                          )}
                          {fb.problem_solving_rating != null && (
                            <div>
                              <div className="text-[10px] font-bold text-gray-400 uppercase mb-1">{t('iv.ratingDim.problemSolving')}</div>
                              <RatingStars value={fb.problem_solving_rating} />
                            </div>
                          )}
                        </div>

                        {fb.strengths && (
                          <div>
                            <div className="text-[10px] font-bold text-emerald-500 uppercase mb-1 flex items-center gap-1">
                              <CheckCircle2 className="h-3 w-3" /> {t('iv.strengths')}
                            </div>
                            <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{fb.strengths}</p>
                          </div>
                        )}
                        {fb.concerns && (
                          <div>
                            <div className="text-[10px] font-bold text-red-500 uppercase mb-1 flex items-center gap-1">
                              <XCircle className="h-3 w-3" /> {t('iv.concerns')}
                            </div>
                            <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{fb.concerns}</p>
                          </div>
                        )}
                        {fb.additional_notes && (
                          <div>
                            <div className="text-[10px] font-bold text-gray-400 uppercase mb-1">{t('iv.additionalNotes')}</div>
                            <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{fb.additional_notes}</p>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          <Card variant="glass" padding="md" className="border-purple-200/60 dark:border-purple-500/20">
            <CardContent className="p-0 space-y-4">
              <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider">{t('iv.overview')}</h3>
              <div className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-400">{t('iv.status.scheduled')}</span>
                  <span className="font-semibold text-gray-800 dark:text-gray-200">{formatDate(interview.scheduled_time)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">{t('iv.duration')}</span>
                  <span className="font-semibold text-gray-800 dark:text-gray-200">{interview.duration_minutes} {t('camp.create.minutes')}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">{t('iv.type')}</span>
                  <span className="font-semibold text-gray-800 dark:text-gray-200 capitalize">{interview.type}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">{t('iv.feedback')}</span>
                  <span className="font-semibold text-gray-800 dark:text-gray-200">
                    {interview.feedback_collected ? `${interview.feedback.length} ${t('iv.submitted')}` : t('iv.notSubmitted')}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>

          {interview.ai_score != null && (
            <Card variant="glass" padding="md" className="border-purple-200/60 dark:border-purple-500/20">
              <CardContent className="p-0">
                <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3">{t('iv.aiAssessment')}</h3>
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">{t('iv.aiScore')}</span>
                    <span className="font-black text-purple-600 dark:text-purple-400">{interview.ai_score}%</span>
                  </div>
                  {interview.cv_score != null && (
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">{t('iv.cvScore')}</span>
                      <span className="font-semibold text-gray-800 dark:text-gray-200">{interview.cv_score}%</span>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          <Button variant="outline" className="w-full" leftIcon={<RefreshCw className="h-4 w-4" />} onClick={load}>
            {t('common.refresh')}
          </Button>
        </div>
      </div>

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('iv.editTitle')}</DialogTitle>
            <DialogDescription>{t('iv.editDesc')}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <Input
              label={t('iv.dateTimeLabel')}
              type="datetime-local"
              value={editForm.scheduledTime}
              onChange={(e) => setEditForm({ ...editForm, scheduledTime: e.target.value })}
              leftIcon={<Calendar className="h-4 w-4 text-purple-500" />}
            />
            <Input
              label={t('iv.meetingLink')}
              type="url"
              placeholder="https://meet.google.com/..."
              value={editForm.meetingLink}
              onChange={(e) => setEditForm({ ...editForm, meetingLink: e.target.value })}
              leftIcon={<Link2 className="h-4 w-4 text-indigo-500" />}
            />
            <Input
              label={t('common.location')}
              placeholder={t('iv.locationPlaceholder')}
              value={editForm.location}
              onChange={(e) => setEditForm({ ...editForm, location: e.target.value })}
              leftIcon={<MapPin className="h-4 w-4 text-amber-500" />}
            />
            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('iv.agendaNotes')}</label>
              <textarea
                value={editForm.agenda}
                onChange={(e) => setEditForm({ ...editForm, agenda: e.target.value })}
                rows={3}
                className="w-full rounded-xl border border-purple-200/60 bg-white/70 p-3 text-sm focus:ring-2 focus:ring-purple-500/20 dark:border-white/10 dark:bg-white/5 dark:text-white"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOpen(false)} disabled={saving}>{t('common.cancel')}</Button>
            <Button variant="primary" onClick={handleSave} disabled={saving} leftIcon={saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Pencil className="h-4 w-4" />}>
              {t('iv.saveChanges')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={feedbackOpen} onOpenChange={setFeedbackOpen}>
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>{t('iv.submitFeedback')}</DialogTitle>
            <DialogDescription>{t('iv.feedbackDialogDesc')}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2 max-h-[60vh] overflow-y-auto pr-1">
            <div className="grid grid-cols-2 gap-4">
              {([
                ['technical_rating', 'technical'],
                ['communication_rating', 'communication'],
                ['culture_fit_rating', 'cultureFit'],
                ['problem_solving_rating', 'problemSolving'],
              ] as const).map(([key, dimKey]) => (
                <div key={key} className="space-y-1.5">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t(`iv.ratingDim.${dimKey}`)}</label>
                  <div className="flex gap-1">
                    {[1, 2, 3, 4, 5].map((n) => (
                      <button
                        key={n}
                        type="button"
                        onClick={() => setFeedbackForm({ ...feedbackForm, [key]: feedbackForm[key] === n ? 0 : n })}
                        className={cn(
                          'h-9 w-9 rounded-lg flex items-center justify-center border transition-all',
                          feedbackForm[key] >= n
                            ? 'bg-amber-100 dark:bg-amber-500/20 border-amber-300 dark:border-amber-500/40'
                            : 'border-gray-200 dark:border-white/10 hover:border-amber-300'
                        )}
                      >
                        <Star className={cn('h-4 w-4', feedbackForm[key] >= n ? 'fill-amber-400 text-amber-400' : 'text-gray-300 dark:text-gray-600')} />
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('iv.overallRating')} *</label>
              <div className="flex gap-1">
                {[1, 2, 3, 4, 5].map((n) => (
                  <button
                    key={n}
                    type="button"
                    onClick={() => setFeedbackForm({ ...feedbackForm, overall_rating: n })}
                    className={cn(
                      'h-10 flex-1 rounded-lg border text-xs font-bold transition-all',
                      feedbackForm.overall_rating === n
                        ? 'bg-purple-600 text-white border-purple-600 shadow-md shadow-purple-500/25'
                        : 'border-gray-200 dark:border-white/10 text-gray-500 dark:text-gray-400 hover:border-purple-300'
                    )}
                  >
                    {n}
                  </button>
                ))}
              </div>
              <p className="text-xs text-gray-400">{ratingLabels[feedbackForm.overall_rating]}</p>
            </div>

            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('iv.recommendationLabel')} *</label>
              <div className="grid grid-cols-3 gap-2">
                {(['strong_yes', 'yes', 'maybe', 'no', 'strong_no'] as const).map((r) => (
                  <button
                    key={r}
                    type="button"
                    onClick={() => setFeedbackForm({ ...feedbackForm, recommendation: r })}
                    className={cn(
                      'px-3 py-2 rounded-lg border-2 text-xs font-bold transition-all capitalize',
                      feedbackForm.recommendation === r
                        ? 'border-purple-500 bg-purple-50 dark:bg-purple-500/10 text-purple-700 dark:text-purple-300'
                        : 'border-gray-200 dark:border-white/10 text-gray-500 dark:text-gray-400 hover:border-purple-300'
                    )}
                  >
                    {t(`iv.recommendation.${r}`)}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('iv.strengths')}</label>
              <textarea
                value={feedbackForm.strengths}
                onChange={(e) => setFeedbackForm({ ...feedbackForm, strengths: e.target.value })}
                rows={2}
                placeholder={t('iv.strengthsPlaceholder')}
                className="w-full rounded-xl border border-purple-200/60 bg-white/70 p-3 text-sm focus:ring-2 focus:ring-purple-500/20 dark:border-white/10 dark:bg-white/5 dark:text-white"
              />
            </div>
            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('iv.concerns')}</label>
              <textarea
                value={feedbackForm.concerns}
                onChange={(e) => setFeedbackForm({ ...feedbackForm, concerns: e.target.value })}
                rows={2}
                placeholder={t('iv.concernsPlaceholder')}
                className="w-full rounded-xl border border-purple-200/60 bg-white/70 p-3 text-sm focus:ring-2 focus:ring-purple-500/20 dark:border-white/10 dark:bg-white/5 dark:text-white"
              />
            </div>
            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('iv.additionalNotes')}</label>
              <textarea
                value={feedbackForm.additional_notes}
                onChange={(e) => setFeedbackForm({ ...feedbackForm, additional_notes: e.target.value })}
                rows={2}
                className="w-full rounded-xl border border-purple-200/60 bg-white/70 p-3 text-sm focus:ring-2 focus:ring-purple-500/20 dark:border-white/10 dark:bg-white/5 dark:text-white"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setFeedbackOpen(false)} disabled={saving}>{t('common.cancel')}</Button>
            <Button variant="primary" onClick={handleSubmitFeedback} disabled={saving} leftIcon={saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}>
              {t('iv.submitFeedback')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={cancelOpen} onOpenChange={setCancelOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('iv.cancelInterviewTitle')}</DialogTitle>
            <DialogDescription>{t('iv.cancelConfirm').replace('{name}', interview.candidate_name)}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCancelOpen(false)} disabled={saving}>{t('iv.keepInterview')}</Button>
            <Button variant="danger" onClick={handleCancel} disabled={saving} leftIcon={saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <XCircle className="h-4 w-4" />}>
              {t('iv.cancelInterviewTitle')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
