import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Loader2, DollarSign, Cpu, Coins, RefreshCcw } from 'lucide-react';
import { cn } from '@/utils/cn';
import { orgService, type OrgOverview } from '@/services/org.service';
import CreditPricing from '@/shared/components/credit-pricing';
import { customToast } from '@/shared/components/ui/toast';

export default function OrgAnalyticsListPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<OrgOverview | null>(null);
  const [credits, setCredits] = useState<{ granted: number; purchased: number; consumed: number; refunded: number; pricing?: Record<string, number> } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    Promise.all([orgService.getOverview(), orgService.getCreditEconomy()])
      .then(([ov, cr]) => { if (!cancelled) { setData(ov); setCredits(cr); } })
      .catch(() => { if (!cancelled) customToast({ type: 'error', title: 'Failed to load analytics' }); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return <div className="flex items-center justify-center py-12"><Loader2 className="h-8 w-8 animate-spin text-purple-600" /></div>;
  }

  const funnel = data?.funnel ?? { applied: 0, screening: 0, interview: 0, offer: 0, hired: 0 };
  const pipelineStages = [
    { name: 'Applied', count: funnel.applied, color: 'bg-gray-500' },
    { name: 'Screening', count: funnel.screening, color: 'bg-blue-500' },
    { name: 'Interview', count: funnel.interview, color: 'bg-purple-500' },
    { name: 'Offer', count: funnel.offer, color: 'bg-amber-500' },
    { name: 'Hired', count: funnel.hired, color: 'bg-emerald-500' },
  ];
  const maxFunnel = Math.max(...pipelineStages.map((s) => s.count), 1);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Organization Analytics</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Company-wide recruitment and AI usage</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardContent>
            <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400"><DollarSign className="h-3.5 w-3.5" /> AI Cost</div>
            <div className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">${(data?.ai?.cost_usd ?? 0).toFixed(2)}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400"><Cpu className="h-3.5 w-3.5" /> AI Calls</div>
            <div className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">{data?.ai?.calls ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400"><Coins className="h-3.5 w-3.5" /> Credits Consumed</div>
            <div className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">{data?.ai?.credits ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400"><RefreshCcw className="h-3.5 w-3.5" /> Credits Granted</div>
            <div className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">{credits?.granted ?? 0}</div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2">
          <CardContent>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Recruiters</h3>
            {!data?.recruiter_kpis?.length ? (
              <p className="text-sm text-gray-500 dark:text-gray-400 py-8 text-center">No recruiters yet.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                      <th className="py-2 font-medium">Recruiter</th>
                      <th className="py-2 font-medium text-right">Jobs</th>
                      <th className="py-2 font-medium text-right">Applications</th>
                      <th className="py-2 font-medium text-right">Interviews</th>
                      <th className="py-2 font-medium text-right">Hired</th>
                      <th className="py-2 font-medium text-right">Avg Score</th>
                      <th className="py-2 font-medium text-right">AI Calls</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.recruiter_kpis.map((r) => (
                      <tr key={r.user_id} className="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50 cursor-pointer" onClick={() => navigate(`/org/analytics/${r.user_id}`)}>
                        <td className="py-3">
                          <div className="font-medium text-gray-900 dark:text-white">{r.name || 'Unnamed'}</div>
                          <div className="text-xs text-gray-400">{r.email}</div>
                        </td>
                        <td className="py-3 text-right">{r.active_jobs}</td>
                        <td className="py-3 text-right">{r.total_applications}</td>
                        <td className="py-3 text-right">{r.interviews?.total ?? 0}</td>
                        <td className="py-3 text-right">{r.hired}</td>
                        <td className="py-3 text-right">{r.avg_score || '—'}</td>
                        <td className="py-3 text-right">{r.ai?.calls ?? 0}</td>
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
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Company Pipeline</h3>
            <div className="space-y-3">
              {pipelineStages.map((stage) => (
                <div key={stage.name} className="flex items-center gap-3">
                  <span className="w-20 text-sm text-gray-500 dark:text-gray-400">{stage.name}</span>
                  <div className="flex-1 h-2 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden">
                    <div className={cn('h-full rounded-full transition-all duration-500', stage.color)} style={{ width: `${(stage.count / maxFunnel) * 100}%` }} />
                  </div>
                  <span className="text-sm font-semibold text-gray-900 dark:text-white">{stage.count}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <CreditPricing
        pricing={credits?.pricing}
        title="AI Credit Pricing"
        description="Credits are consumed for AI actions across your company. Prices are set by the platform admin."
      />
    </div>
  );
}
