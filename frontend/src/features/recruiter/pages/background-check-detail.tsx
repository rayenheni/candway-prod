import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useParams } from 'react-router';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Loader2, CheckCircle, Clock, XCircle, User, FileText, Briefcase, GraduationCap } from 'lucide-react';
import { backgroundChecksService } from '@/services/background-checks.service';

const statusConfig = {
  clear: { label: 'Clear', variant: 'success' as const, icon: CheckCircle },
  pending: { label: 'Pending', variant: 'warning' as const, icon: Clock },
  issue: { label: 'Issue', variant: 'danger' as const, icon: XCircle },
  in_progress: { label: 'In Progress', variant: 'primary' as const, icon: Clock },
};

const defaultTimelineIcon = Clock;

function normalizeCheck(data: any) {
  return {
    id: data.id,
    candidate: data.candidate_name || 'Unknown',
    position: data.position || data.type || 'Background Check',
    status: data.status || 'pending',
    personal: {
      fullName: data.personal_info?.full_name || data.personal_info?.fullName || '',
      email: data.personal_info?.email || '',
      phone: data.personal_info?.phone || '',
      address: data.personal_info?.address || '',
      nationalId: data.personal_info?.national_id || data.personal_info?.nationalId || '',
    },
    criminal: {
      status: data.criminal_records?.status || 'pending',
      details: data.criminal_records?.details || '',
      date: data.criminal_records?.date || data.criminal_records?.completed_at || '',
    },
    employment: {
      status: data.employment_history?.status || 'pending',
      details: data.employment_history?.details || '',
      date: data.employment_history?.date || data.employment_history?.completed_at || '',
    },
    education: {
      status: data.education?.status || 'pending',
      details: data.education?.details || '',
      date: data.education?.date || data.education?.completed_at || '',
    },
    timeline: (data.timeline || []).map((entry: any) => ({
      event: entry.event || '',
      date: entry.date || '',
      icon: defaultTimelineIcon,
      color: 'text-gray-500',
    })),
  };
}

export default function BackgroundCheckDetailPage() {
  const { id } = useParams();
  const [check, setCheck] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) {
      setError('Background check ID is missing.');
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    backgroundChecksService.getByApplication(id)
      .then((res: any) => {
        setCheck(normalizeCheck(res));
      })
      .catch((err: any) => {
        setError(err?.message || 'Failed to load background check.');
      })
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-purple-500" />
      </div>
    );
  }

  if (error || !check) {
    return (
      <div className="flex items-center justify-center h-full min-h-[400px]">
        <p className="text-gray-500">{error || 'Background check not found.'}</p>
      </div>
    );
  }

  const config = statusConfig[check.status as keyof typeof statusConfig] || statusConfig.pending;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div>
            <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">{check.candidate}</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">{check.position}</p>
          </div>
          <Badge variant={config.variant} size="md"><config.icon className="h-3 w-3" />{config.label}</Badge>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
            <Card className="glass-panel border-purple-200/50">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <User className="h-4 w-4 text-purple-500" />
                  Personal Information
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">Full Name</span>
                    <p className="text-sm font-semibold text-gray-900 dark:text-white mt-1">{check.personal.fullName}</p>
                  </div>
                  <div>
                    <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">Email</span>
                    <p className="text-sm font-semibold text-gray-900 dark:text-white mt-1">{check.personal.email}</p>
                  </div>
                  <div>
                    <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">Phone</span>
                    <p className="text-sm font-semibold text-gray-900 dark:text-white mt-1">{check.personal.phone}</p>
                  </div>
                  <div>
                    <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">Address</span>
                    <p className="text-sm font-semibold text-gray-900 dark:text-white mt-1">{check.personal.address}</p>
                  </div>
                  <div>
                    <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">National ID</span>
                    <p className="text-sm font-semibold text-gray-900 dark:text-white mt-1">{check.personal.nationalId}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: 0.1 }}>
            <Card className="glass-panel border-purple-200/50">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileText className="h-4 w-4 text-purple-500" />
                  Criminal Check
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-2 mb-2">
                  <Badge variant={check.criminal.status === 'clear' ? 'success' : 'danger'} size="sm">{check.criminal.status === 'clear' ? <CheckCircle className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}{check.criminal.status === 'clear' ? 'Clear' : 'Issue'}</Badge>
                  <span className="text-xs text-gray-500">{check.criminal.date}</span>
                </div>
                <p className="text-sm text-gray-700 dark:text-gray-300">{check.criminal.details}</p>
              </CardContent>
            </Card>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: 0.15 }}>
            <Card className="glass-panel border-purple-200/50">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Briefcase className="h-4 w-4 text-purple-500" />
                  Employment Verification
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-2 mb-2">
                  <Badge variant={check.employment.status === 'clear' ? 'success' : 'danger'} size="sm">{check.employment.status === 'clear' ? <CheckCircle className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}{check.employment.status === 'clear' ? 'Verified' : 'Issue'}</Badge>
                  <span className="text-xs text-gray-500">{check.employment.date}</span>
                </div>
                <p className="text-sm text-gray-700 dark:text-gray-300">{check.employment.details}</p>
              </CardContent>
            </Card>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: 0.2 }}>
            <Card className="glass-panel border-purple-200/50">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <GraduationCap className="h-4 w-4 text-purple-500" />
                  Education Check
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-2 mb-2">
                  <Badge variant={check.education.status === 'clear' ? 'success' : 'danger'} size="sm">{check.education.status === 'clear' ? <CheckCircle className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}{check.education.status === 'clear' ? 'Verified' : 'Issue'}</Badge>
                  <span className="text-xs text-gray-500">{check.education.date}</span>
                </div>
                <p className="text-sm text-gray-700 dark:text-gray-300">{check.education.details}</p>
              </CardContent>
            </Card>
          </motion.div>
        </div>

        <div className="space-y-6">
          <motion.div initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.3, delay: 0.1 }}>
            <Card className="glass-panel border-purple-200/50">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Clock className="h-4 w-4 text-purple-500" />
                  Timeline
                </CardTitle>
                <CardDescription>Background check audit trail</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="relative space-y-0">
                  {check.timeline.map((entry: any, i: number) => (
                    <div key={i} className="flex gap-3 pb-5 last:pb-0 relative">
                      <div className="flex flex-col items-center">
                        <div className={`flex h-7 w-7 items-center justify-center rounded-full bg-purple-100 dark:bg-purple-500/20 ${entry.color}`}>
                          <entry.icon className="h-3.5 w-3.5" />
                        </div>
                        {i < check.timeline.length - 1 && (
                          <div className="w-px flex-1 bg-purple-100 dark:bg-purple-500/20 mt-1" />
                        )}
                      </div>
                      <div className="flex-1 pt-0.5">
                        <p className="text-sm font-semibold text-gray-900 dark:text-white">{entry.event}</p>
                        <p className="text-xs text-gray-500 mt-0.5">{entry.date}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </motion.div>

        </div>
      </div>
    </div>
  );
}
