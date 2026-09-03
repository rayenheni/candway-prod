import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router';
import { motion } from 'framer-motion';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Avatar } from '@/shared/components/ui/avatar';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/shared/components/ui/tabs';
import { useLanguage } from '@/contexts/language-context';
import {
  Plus,
  Calendar,
  Clock,
  Video,
  Phone,
  Users,
  ChevronRight,
  Loader2,
} from 'lucide-react';
import apiClient from '@/lib/api-client';

function getDateLabel(isoDate: string): string {
  try {
    const date = new Date(isoDate);
    const today = new Date();
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    if (date.toDateString() === today.toDateString()) return 'Today';
    if (date.toDateString() === tomorrow.toDateString()) return 'Tomorrow';
    if (date.toDateString() === yesterday.toDateString()) return 'Yesterday';
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch {
    return isoDate;
  }
}

function formatTimeRange(isoDate: string): string {
  try {
    const start = new Date(isoDate);
    const end = new Date(start.getTime() + 60 * 60 * 1000);
    const fmt = (d: Date) =>
      d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
    return `${fmt(start)} - ${fmt(end)}`;
  } catch {
    return isoDate;
  }
}

interface ApiInterview {
  id: string;
  candidate_name: string;
  application_id: string;
  job_title: string;
  scheduled_time: string;
  type: string;
  status: string;
  meeting_link: string | null;
}

interface NeedsSchedulingItem {
  id: string;
  candidate_name: string;
  position: string;
  score: number | null;
  status: string;
}

const typeIcons: Record<string, typeof Video> = {
  Video: Video,
  'Phone Screen': Phone,
  Technical: Video,
  Behavioral: Video,
  'Portfolio Review': Video,
};

export default function InterviewsListPage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('all');
  const [interviews, setInterviews] = useState<ApiInterview[]>([]);
  const [needsScheduling, setNeedsScheduling] = useState<NeedsSchedulingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadInterviews = () => {
    setLoading(true);
    apiClient
      .get<ApiInterview[]>('/recruiter/interviews/upcoming')
      .then((res) => setInterviews(Array.isArray(res) ? res : []))
      .catch((err) => {
        setInterviews([]);
        setError(err?.message || 'Failed to load interviews');
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadInterviews();
  }, []);

  useEffect(() => {
    apiClient
      .get<{ items: any[] }>('/recruiter/applications', { status: 'interviewing' })
      .then((res) => {
        const items = (res?.items || []).map((app) => ({
          id: String(app.id),
          candidate_name: app.candidate_name || app.full_name || t('role.candidate'),
          position: app.job_title || app.role || 'General Application',
          score: app.score ?? null,
          status: app.status || 'interviewing',
        }));
        setNeedsScheduling(items);
      })
      .catch(() => setNeedsScheduling([]));
  }, [t]);

  const allItems = [
    ...interviews.map((i) => ({
      id: String(i.id),
      candidate: i.candidate_name,
      role: i.job_title,
      date: getDateLabel(i.scheduled_time),
      time: formatTimeRange(i.scheduled_time),
      type: i.type,
      status: i.status,
      meetingUrl: i.meeting_link,
      applicationId: String(i.application_id),
    })),
    ...needsScheduling
      .filter((n) => !interviews.some((iv) => String(iv.application_id) === n.id))
      .map((n) => ({
        id: `sched-${n.id}`,
        candidate: n.candidate_name,
        role: n.position,
        date: '—',
        time: '',
        type: 'Scheduled',
        status: 'needs_scheduling',
        meetingUrl: null,
        applicationId: n.id,
        score: n.score,
      })),
  ];

  const displayInterviews = allItems;

  const filteredInterviews = displayInterviews.filter((interview) => {
    if (activeTab === 'all') return true;
    if (activeTab === 'upcoming') return interview.date === 'Today' || interview.date === 'Tomorrow';
    return interview.status === activeTab;
  });

  const todayCount = displayInterviews.filter((i) => i.date === 'Today').length;
  const tomorrowCount = displayInterviews.filter((i) => i.date === 'Tomorrow').length;

  const statusConfig: Record<string, { variant: string; label: string }> = {
    scheduled: { variant: 'info', label: t('candidates.scheduled') },
    rescheduled: { variant: 'info', label: t('candidates.scheduled') },
    completed: { variant: 'success', label: t('common.completed') },
    cancelled: { variant: 'danger', label: t('candidates.declined') },
    no_show: { variant: 'danger', label: t('candidates.declined') },
    needs_scheduling: { variant: 'warning', label: t('common.pending') },
  };

  if (loading && interviews.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-purple-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="text-center">
          <p className="text-red-500">{error}</p>
          <Button variant="outline" className="mt-4" onClick={loadInterviews}>
            {t('common.retry')}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{t('nav.interviews')}</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            {t('iv.subtitle')}
          </p>
        </div>
        <Button variant="primary" leftIcon={<Plus className="h-4 w-4" />} onClick={() => navigate('/interviews/new')}>
          {t('topbar.schedule_interview')}
        </Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card>
          <CardContent>
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50 dark:bg-blue-500/10">
                <Calendar className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <div className="text-2xl font-bold text-gray-900 dark:text-white">{todayCount}</div>
                <div className="text-sm text-gray-500 dark:text-gray-400">{t('common.today')}</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-50 dark:bg-purple-500/10">
                <Clock className="h-5 w-5 text-purple-600 dark:text-purple-400" />
              </div>
              <div>
                <div className="text-2xl font-bold text-gray-900 dark:text-white">{tomorrowCount}</div>
                <div className="text-sm text-gray-500 dark:text-gray-400">{t('common.date')}</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-50 dark:bg-amber-500/10">
                <Users className="h-5 w-5 text-amber-600 dark:text-amber-400" />
              </div>
              <div>
                <div className="text-2xl font-bold text-gray-900 dark:text-white">{needsScheduling.length}</div>
                <div className="text-sm text-gray-500 dark:text-gray-400">{t('common.pending')}</div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="all">{t('common.all')}</TabsTrigger>
          <TabsTrigger value="scheduled">{t('candidates.scheduled')}</TabsTrigger>
          <TabsTrigger value="completed">{t('common.completed')}</TabsTrigger>
          <TabsTrigger value="needs_scheduling">{t('common.pending')}</TabsTrigger>
        </TabsList>

        <TabsContent value={activeTab}>
          <div className="space-y-3 mt-4">
            {filteredInterviews.length === 0 ? (
              <div className="flex h-64 items-center justify-center">
                <div className="text-center">
                  <Calendar className="h-12 w-12 text-gray-300 mx-auto mb-3" />
                  <p className="text-gray-500 text-lg font-medium">{t('common.noData')}</p>
                  <p className="text-sm text-gray-400 mt-1">{t('iv.subtitle')}</p>
                  <Button variant="primary" className="mt-4" leftIcon={<Plus className="h-4 w-4" />} onClick={() => navigate('/interviews/new')}>
                    {t('topbar.schedule_interview')}
                  </Button>
                </div>
              </div>
            ) : (
              filteredInterviews.map((interview, i) => {
                const TypeIcon = typeIcons[interview.type] || Video;
                const status = statusConfig[interview.status] || statusConfig.scheduled;
                const isNeedsScheduling = interview.status === 'needs_scheduling';
                const aiScore = (interview as any).score;
                const aiColor = aiScore ? (aiScore >= 80 ? 'text-emerald-600' : aiScore >= 60 ? 'text-amber-600' : 'text-red-600') : 'text-gray-400';

                return (
                  <motion.div
                    key={interview.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3, delay: i * 0.05 }}
                  >
                    <Card hoverable className="cursor-pointer" onClick={() => {
                      if (!isNeedsScheduling) navigate(`/interviews/${interview.id}`);
                    }}>
                      <CardContent>
                        <div className="flex items-center gap-4">
                          <Avatar name={interview.candidate} size="md" />

                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-semibold text-gray-900 dark:text-white">
                                {interview.candidate}
                              </span>
                              <Badge variant={status.variant as any} size="sm">
                                {status.label}
                              </Badge>
                            </div>
                            <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">{interview.role}</p>
                            {!isNeedsScheduling && (
                              <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
                                {interview.date} · {interview.time}
                              </p>
                            )}
                          </div>

                          <div className="hidden sm:flex items-center gap-6 text-sm">
                            <div className="flex items-center gap-2 text-gray-600 dark:text-gray-400">
                              <TypeIcon className="h-4 w-4" />
                              {isNeedsScheduling ? '—' : interview.type}
                            </div>
                            {aiScore != null && (
                              <div className={`flex items-center gap-1 font-medium ${aiColor}`}>
                                <span className="text-xs">AI: {aiScore}%</span>
                              </div>
                            )}
                          </div>

                          <div className="flex items-center gap-2">
                            {isNeedsScheduling && (
                              <Button
                                variant="primary"
                                size="sm"
                                leftIcon={<Plus className="h-4 w-4" />}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  navigate(`/interviews/new?appId=${interview.applicationId}`);
                                }}
                              >
                                {t('topbar.schedule_interview')}
                              </Button>
                            )}
                            {interview.status === 'scheduled' && interview.meetingUrl && (
                              <Button variant="primary" size="sm" onClick={(e) => { e.stopPropagation(); if (interview.meetingUrl) window.open(interview.meetingUrl, '_blank'); }}>
                                Join
                              </Button>
                            )}
                            {!isNeedsScheduling && interview.status === 'completed' && (
                              <Button variant="outline" size="sm" onClick={(e) => { e.stopPropagation(); navigate(`/interviews/${interview.id}`); }}>
                                {t('common.view')}
                              </Button>
                            )}
                            {!isNeedsScheduling && (
                              <ChevronRight className="h-4 w-4 text-gray-400" />
                            )}
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  </motion.div>
                );
              })
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
