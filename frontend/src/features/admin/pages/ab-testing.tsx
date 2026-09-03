// ============================================================
// Admin A/B Testing - Candway
// Real data from /admin/ab-testing/config, /admin/ab-testing/stats, /admin/experiments
// ============================================================

import { useCallback, useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Switch } from '@/shared/components/ui/switch';
import { Input } from '@/shared/components/ui/input';
import { customToast } from '@/shared/components/ui/toast';
import { Beaker, BarChart3, TrendingUp, CheckCircle2, RefreshCw } from 'lucide-react';
import { adminService } from '@/services/admin.service';

interface Experiment {
  id: number;
  name: string;
  model_a: string;
  model_b: string;
  sample_size_a: number;
  sample_size_b: number;
  avg_score_a: number;
  avg_score_b: number;
  is_active: boolean;
  conclusion: string | null;
  started_at: string | null;
  ended_at: string | null;
}

export default function ABTestingPage() {
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [config, setConfig] = useState<{ ab_test_enabled: boolean; ab_test_bucket_size: number } | null>(null);
  const [stats, setStats] = useState<any>(null);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [expRes, cfgRes, statsRes] = await Promise.all([
        adminService.getExperiments(),
        adminService.getABTestConfig(),
        adminService.getABTestStats(7),
      ]);
      setExperiments((expRes.experiments || []) as Experiment[]);
      setConfig(cfgRes);
      setStats(statsRes);
    } catch (err) {
      console.error('AB testing load error:', err);
      customToast({ type: 'error', title: 'A/B Testing', message: 'Failed to load experiment data.' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);

  const handleToggleConfig = async (enabled: boolean) => {
    try {
      await adminService.updateABTestConfig({ ab_test_enabled: enabled, ab_test_bucket_size: config?.ab_test_bucket_size || 10 });
      setConfig(c => c ? { ...c, ab_test_enabled: enabled } : c);
      customToast({ type: 'success', title: 'Config Updated', message: `A/B testing ${enabled ? 'enabled' : 'disabled'}.` });
    } catch (err: any) {
      customToast({ type: 'error', title: 'Failed', message: err?.message || 'Could not update config.' });
    }
  };

  const filtered = experiments.filter(e => e.name.toLowerCase().includes(search.toLowerCase()));

  const statCards = [
    { label: 'Active Experiments', value: experiments.filter(e => e.is_active).length, icon: Beaker, color: 'text-purple-600 bg-purple-100 dark:bg-purple-900/30' },
    { label: 'Completed', value: experiments.filter(e => !e.is_active && e.conclusion).length, icon: CheckCircle2, color: 'text-emerald-600 bg-emerald-100 dark:bg-emerald-900/30' },
    { label: 'Total Variants', value: experiments.length * 2, icon: BarChart3, color: 'text-blue-600 bg-blue-100 dark:bg-blue-900/30' },
    { label: 'Avg Lift', value: stats?.stats ? `${Math.round(stats.stats.reduce((s: any, r: any) => s + (r.success_rate || 0), 0) / (stats.stats.length || 1))}%` : '0%', icon: TrendingUp, color: 'text-amber-600 bg-amber-100 dark:bg-amber-900/30' },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">A/B Scoring Experiments</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Run and analyze A/B tests across scoring models and candidate experience</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" leftIcon={<RefreshCw className="h-4 w-4" />} onClick={loadAll}>Refresh</Button>
        </div>
      </div>

      <Card className="glass-panel border-purple-200/50 dark:border-purple-500/20">
        <CardHeader>
          <CardTitle>A/B Test Configuration</CardTitle>
          <CardDescription>Enable or disable A/B testing across the platform</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Switch checked={config?.ab_test_enabled || false} onCheckedChange={handleToggleConfig} disabled={!config} />
              <div>
                <span className="font-bold text-gray-900 dark:text-white">A/B Testing {config?.ab_test_enabled ? 'Enabled' : 'Disabled'}</span>
                <p className="text-sm text-gray-500">Bucket size: {config?.ab_test_bucket_size || 10}%</p>
              </div>
            </div>
            <Button variant="outline" size="sm" onClick={async () => {
              if (config) {
                await adminService.resetABTestStats();
                customToast({ type: 'success', title: 'Stats Reset', message: 'A/B test statistics have been reset.' });
                loadAll();
              }
            }}>Reset Stats</Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((stat) => (
          <Card key={stat.label} className="glass-panel border-purple-200/50">
            <CardContent className="p-5">
              <div className="flex justify-between items-start mb-3">
                <div className={`text-xs font-black uppercase tracking-widest ${stat.color.split(' ')[0] || 'text-purple-600'}`}>{stat.label}</div>
                <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${stat.color}`}>
                  <stat.icon className="h-4 w-4" />
                </div>
              </div>
              <div className="text-2xl font-black text-gray-900 dark:text-white tracking-tighter">{stat.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card className="glass-panel border-purple-200/50">
        <CardHeader>
          <div className="flex items-center justify-between w-full">
            <div>
              <CardTitle>Active Experiments</CardTitle>
              <CardDescription>{filtered.length} experiments found</CardDescription>
            </div>
            <Input placeholder="Search experiments..." leftIcon={<><Beaker className="h-4 w-4" /></>} value={search} onChange={(e) => setSearch(e.target.value)} wrapperClassName="w-64" />
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex flex-col items-center justify-center gap-3 py-16">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-purple-600 border-t-transparent" />
              <span className="text-sm text-gray-500">Loading experiments...</span>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-purple-100 dark:border-white/10">
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Name</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Models</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Status</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Sample (A/B)</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Scores (A/B)</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Conclusion</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(exp => (
                    <tr key={exp.id} className="border-b border-gray-50 dark:border-white/[0.02] hover:bg-purple-50/50 transition-colors">
                      <td className="py-3 text-sm font-bold text-gray-900 dark:text-white">{exp.name || `Experiment #${exp.id}`}</td>
                      <td className="py-3 text-sm text-gray-500">{exp.model_a} vs {exp.model_b}</td>
                      <td className="py-3">
                        <Badge variant={exp.is_active ? 'info' : 'default'} size="sm" dot>{exp.is_active ? 'running' : 'paused'}</Badge>
                      </td>
                      <td className="py-3 text-sm text-gray-500">{exp.sample_size_a} / {exp.sample_size_b}</td>
                      <td className="py-3 text-sm text-gray-500">{exp.avg_score_a?.toFixed(2) || 0} / {exp.avg_score_b?.toFixed(2) || 0}</td>
                      <td className="py-3 text-sm text-gray-500">{exp.conclusion || '—'}</td>
                    </tr>
                  ))}
                  {filtered.length === 0 && !loading && <tr><td colSpan={6} className="py-10 text-center text-gray-400">No experiments found.</td></tr>}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
