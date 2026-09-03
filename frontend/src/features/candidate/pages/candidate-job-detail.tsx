import { useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { candidateService } from '@/services/candidate.service';
import { Card } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { customToast } from '@/shared/components/ui/toast';
import { useLanguage } from '@/contexts/language-context';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { ArrowLeft, MapPin, Clock, Briefcase, SendHorizontal, Loader2, Calendar, Hourglass, PlayCircle } from 'lucide-react';

const SAFE_TAGS = new Set(['b', 'i', 'em', 'strong', 'u', 'br', 'p', 'ul', 'ol', 'li', 'h2', 'h3', 'h4', 'span', 'a']);
const SAFE_ATTRS: Record<string, Set<string>> = { a: new Set(['href', 'title']) };

function sanitizeHtml(html: string): string {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const walk = (node: Node) => {
    const children = Array.from(node.childNodes);
    for (const child of children) {
      if (child.nodeType === 1) {
        const el = child as Element;
        const tag = el.tagName.toLowerCase();
        if (!SAFE_TAGS.has(tag)) {
          el.replaceWith(...el.childNodes);
          continue;
        }
        for (const attr of Array.from(el.attributes)) {
          if (tag === 'a' && attr.name === 'href' && /^javascript:/i.test(attr.value)) {
            el.removeAttribute(attr.name);
            continue;
          }
          if (!SAFE_ATTRS[tag]?.has(attr.name)) {
            el.removeAttribute(attr.name);
          }
        }
        walk(el);
      }
    }
  };
  walk(doc.body);
  return doc.body.innerHTML;
}

export default function CandidateJobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const jobId = Number(id);
  const { t } = useLanguage();
  const [applyOpen, setApplyOpen] = useState(false);
  const [applySource, setApplySource] = useState('');

  const { data: job, isLoading, error } = useQuery({
    queryKey: ['candidate-job', jobId],
    queryFn: () => candidateService.getJob(jobId),
    enabled: !!jobId,
  });

  const applyMutation = useMutation({
    mutationFn: (source: string) => candidateService.applyToJob(jobId, source || 'direct'),
    onSuccess: (res: any) => {
      queryClient.invalidateQueries({ queryKey: ['candidate-jobs'] });
      queryClient.invalidateQueries({ queryKey: ['candidate-job', jobId] });
      const applicationId = res?.application_id || jobId;
      localStorage.setItem('active_app_id', String(applicationId));
      setApplyOpen(false);
      setApplySource('');
      customToast({
        type: 'success',
        title: t('jobs.apply.applied'),
        message: t('jobs.apply.success'),
        duration: 6000,
      });
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail || err?.message || t('jobs.apply.errorFallback');
      customToast({ type: 'error', title: t('jobs.apply.failed'), message: detail });
    },
  });

  const safeDescription = useMemo(() => job?.description ? sanitizeHtml(job.description) : '', [job?.description]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-violet-600" />
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="text-center py-20">
        <p className="text-gray-500 dark:text-gray-400 text-lg font-medium">{t('jobs.notFound')}</p>
        <Button variant="ghost" className="mt-4" onClick={() => navigate('/jobs')}>
          <ArrowLeft className="h-4 w-4 mr-2" /> {t('jobs.apply.backToJobs')}
        </Button>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <Button variant="ghost" size="sm" onClick={() => navigate('/jobs')}>
        <ArrowLeft className="h-4 w-4 mr-2" /> {t('jobs.apply.backToJobs')}
      </Button>

      <Card>
        <div className="p-6 sm:p-8">
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-6">
            <div>
              <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white">{job.title}</h1>
              {job.company && (
                <p className="text-lg text-gray-500 dark:text-gray-400 mt-1">{job.company}</p>
              )}
            </div>
          </div>

          <div className="flex flex-wrap gap-3 mb-6">
            <div className="flex items-center gap-1.5 text-sm text-gray-500">
              <MapPin className="h-4 w-4" />
              <span>{job.location || 'Remote'}</span>
            </div>
            <div className="flex items-center gap-1.5 text-sm text-gray-500">
              <Briefcase className="h-4 w-4" />
              <span>{job.type || 'Full-time'}</span>
            </div>
            {job.salary_range && (
              <span className="inline-flex items-center px-2.5 py-0.5 text-xs font-medium rounded-full bg-violet-50 text-violet-700 dark:bg-violet-500/10 dark:text-violet-300">
                {job.salary_range}
              </span>
            )}
            <div className="flex items-center gap-1.5 text-sm text-gray-500">
              <Calendar className="h-4 w-4" />
              <span>Posted {job.created_at || 'Recently'}</span>
            </div>
            {job.valid_through && (
              <div className="flex items-center gap-1.5 text-sm text-gray-500">
                <Clock className="h-4 w-4" />
                <span>Valid until {job.valid_through}</span>
              </div>
            )}
          </div>

          {(job.required_skills || []).length > 0 && (
            <div className="mb-6">
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Required Skills</h3>
              <div className="flex flex-wrap gap-2">
                {job.required_skills.map((skill: string) => (
                  <span key={skill} className="text-xs px-3 py-1 rounded-full bg-violet-50 text-violet-700 dark:bg-violet-500/10 dark:text-violet-300 font-medium">
                    {skill}
                  </span>
                ))}
              </div>
            </div>
          )}

          {job.description && (
            <div className="mb-6">
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Job Description</h3>
              <div
                className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed prose prose-sm dark:prose-invert max-w-none"
                dangerouslySetInnerHTML={{ __html: safeDescription }}
              />
            </div>
          )}

          {job.interview_instructions && (
            <div className="mb-6 p-4 bg-amber-50 dark:bg-amber-500/10 rounded-lg border border-amber-200 dark:border-amber-500/20">
              <h3 className="text-sm font-semibold text-amber-800 dark:text-amber-300 mb-1">Interview Instructions</h3>
              <p className="text-sm text-amber-700 dark:text-amber-400">{job.interview_instructions}</p>
            </div>
          )}

          <div className="pt-6 border-t border-gray-100 dark:border-white/5">
            {job.already_applied ? (
              ['invited', 'interviewing', 'interview'].includes(job.application_status) ? (
                <div className="flex flex-col sm:flex-row sm:items-center gap-3">
                  <Button
                    variant="primary"
                    size="lg"
                    className="w-full sm:w-auto"
                    leftIcon={<PlayCircle className="h-4 w-4" />}
                    onClick={() => navigate(`/interviews/room/${job.application_id || jobId}`)}
                  >
                    Start AI Interview
                  </Button>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    You have been invited to an AI interview for this position.
                  </p>
                </div>
              ) : (
                <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400 text-sm font-medium">
                  <Hourglass className="h-5 w-5" />
                  Application under review
                  <span className="font-normal text-gray-400">— the recruiter will invite you to the AI interview if you're shortlisted.</span>
                </div>
              )
            ) : (
              <Button
                variant="primary"
                size="lg"
                className="w-full sm:w-auto"
                leftIcon={<SendHorizontal className="h-4 w-4" />}
                onClick={() => setApplyOpen(true)}
                disabled={applyMutation.isPending}
              >
                {applyMutation.isPending ? t('jobs.apply.applying') : t('jobs.apply.title')}
              </Button>
            )}
          </div>
        </div>
      </Card>

      <Dialog open={applyOpen} onOpenChange={setApplyOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{t('jobs.apply.title')}</DialogTitle>
            <DialogDescription>{t('jobs.apply.heardAbout')}</DialogDescription>
          </DialogHeader>
          <select
            value={applySource}
            onChange={(e) => setApplySource(e.target.value)}
            className="w-full rounded-lg border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 px-3 py-2 text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500/40"
          >
            <option value="">{t('jobs.apply.sourcePlaceholder')}</option>
            <option value="linkedin">{t('sources.linkedin')}</option>
            <option value="social_media">{t('sources.socialMedia')}</option>
            <option value="website">{t('sources.website')}</option>
            <option value="referral">{t('sources.referral')}</option>
            <option value="direct">{t('sources.direct')}</option>
            <option value="other">{t('sources.other')}</option>
          </select>
          <DialogFooter>
            <button
              onClick={() => setApplyOpen(false)}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 dark:text-gray-300 dark:bg-white/10 dark:hover:bg-white/15 transition-colors"
            >
              {t('common.cancel')}
            </button>
            <button
              onClick={() => applyMutation.mutate(applySource || 'direct')}
              disabled={applyMutation.isPending}
              className="px-4 py-2 text-sm font-medium text-white bg-violet-600 hover:bg-violet-700 rounded-lg transition-colors disabled:opacity-50"
            >
              {applyMutation.isPending ? t('jobs.apply.applying') : t('jobs.apply.submit')}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
