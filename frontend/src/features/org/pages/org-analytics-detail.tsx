import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Loader2, ArrowLeft, Briefcase, Users, Calendar, Star } from 'lucide-react';
import { cn } from '@/utils/cn';
import { orgService, type OrgRecruiterDetail } from '@/services/org.service';
import { customToast } from '@/shared/components/ui/toast';

export default function OrgAnalyticsDetailPage() {
  const { userId } = useParams<{ userId: string }>();
  const navigate = useNavigate();
  const [data, setData] = useState<OrgRecruiterDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    orgService.getRecruiterDetail(Number(userId))
      .then((res) => { if (!cancelled) setData(res); })
      .catch(() => { if (!cancelled) customToast({ type: 'error', title: 'Failed to load recruiter analytics' }); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [userId]);

  if (loading) {
    return <div className="flex items-center justify-center py-12"><Loader2 className="h-8 w-8 animate-spin text-purple-600" /></div>;
  }
  if (!data) return null;

  const k = data.kpis;
  const maxTrend = Math.max(...data.trends.map((t) => t.count), 1);

  const statCards = [
    { label: 'Active Jobs', value: k.active_jobs, icon: Briefcase, color: 'bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400' },
    { label: 'Applications', value: k.total_applications, icon: Users, color: 'bg-purple-50 text-purple-600 dark:bg-purple-500/10 dark:text-purple-400' },
    { label: 'Interviews Completed', value: k.interviews?.completed ?? 0, icon: Calendar, color: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400' },
    { label: 'Avg Score', value: k.avg_score || '—', icon: Star, color: 'bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400' },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/org/analytics')} className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500">
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{k.name || 'Recruiter'}</h1>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{k.email}</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((stat) => (
          <Card key={stat.label} hoverable>
            <CardContent>
              <div className={cn('flex h-10 w-10 items-center justify-center rounded-xl', stat.color)}><stat.icon className="h-5 w-5" /></div>
              <div className="mt-4">
                <div className="text-2xl font-bold text-gray-900 dark:text-white">{stat.value}</div>
                <div className="text-sm text-gray-500 dark:text-gray-400">{stat.label}</div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardContent>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Applications (7 days)</h3>
            <div className="space-y-2">
              {data.trends.map((t) => (
                <div key={t.date} className="flex items-center gap-3">
                  <span className="w-24 text-xs text-gray-500 dark:text-gray-400">{t.date.slice(5)}</span>
                  <div className="flex-1 h-2 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden">
                    <div className="h-full rounded-full bg-purple-500" style={{ width: `${(t.count / maxTrend) * 100}%` }} />
                  </div>
                  <span className="text-xs font-semibold text-gray-900 dark:text-white">{t.count}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Score Distribution</h3>
            <div className="grid grid-cols-4 gap-2">
              {Object.entries(data.score_distribution).map(([range, count]) => (
                <div key={range} className="rounded-xl bg-gray-50 dark:bg-gray-800/60 p-3 text-center">
                  <div className="text-lg font-bold text-gray-900 dark:text-white">{count}</div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">{range}</div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardContent>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Jobs ({data.jobs.length})</h3>
          {!data.jobs.length ? (
            <p className="text-sm text-gray-500 dark:text-gray-400 py-4 text-center">No jobs yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                    <th className="py-2 font-medium">Job</th>
                    <th className="py-2 font-medium">Status</th>
                    <th className="py-2 font-medium text-right">Applications</th>
                    <th className="py-2 font-medium text-right">Hired</th>
                  </tr>
                </thead>
                <tbody>
                  {data.jobs.map((j) => (
                    <tr key={j.id} className="border-b border-gray-100 dark:border-gray-800">
                      <td className="py-3 font-medium text-gray-900 dark:text-white">{j.title}</td>
                      <td className="py-3">
                        <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', j.is_active ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300' : 'bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-300')}>
                          {j.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="py-3 text-right">{j.applicant_count}</td>
                      <td className="py-3 text-right">{j.hired_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Recent Applications</h3>
          {!data.recent_applications.length ? (
            <p className="text-sm text-gray-500 dark:text-gray-400 py-4 text-center">No recent applications.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                    <th className="py-2 font-medium">Candidate</th>
                    <th className="py-2 font-medium">Status</th>
                    <th className="py-2 font-medium text-right">Score</th>
                    <th className="py-2 font-medium text-right">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent_applications.map((a) => (
                    <tr key={a.id} className="border-b border-gray-100 dark:border-gray-800">
                      <td className="py-3 font-medium text-gray-900 dark:text-white">{a.full_name}</td>
                      <td className="py-3">
                        <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300 capitalize">{a.status}</span>
                      </td>
                      <td className="py-3 text-right">{a.score || '—'}</td>
                      <td className="py-3 text-right text-gray-500">{a.created_at ? a.created_at.slice(0, 10) : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
