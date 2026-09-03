// ============================================================
// Admin Recruiter Usage Hub - Candway Tunisia
// Real data from /admin/users/usage + /admin/analytics/ai
// ============================================================

import { useCallback, useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/shared/components/ui/tabs';
import { customToast } from '@/shared/components/ui/toast';
import { cn } from '@/utils/cn';
import { Users, BarChart3, TrendingUp, Search, Download, RefreshCw, Briefcase } from 'lucide-react';
import { adminService, RecruiterUsageRow } from '@/services/admin.service';

export default function RecruiterUsagePage() {
  const [recruiters, setRecruiters] = useState<RecruiterUsageRow[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [expandedRow, setExpandedRow] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [aiAnalytics, setAiAnalytics] = useState<any>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [usersRes, aiRes] = await Promise.all([
        adminService.getRecruiterUsage({ page: 1, per_page: 100 }),
        adminService.getAIAnalytics(),
      ]);
      setRecruiters(usersRes.users || []);
      setAiAnalytics(aiRes);
    } catch (err) {
      console.error('Recruiter usage load error:', err);
      customToast({ type: 'error', title: 'Usage', message: 'Failed to load recruiter usage.' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const filtered = recruiters.filter(r =>
    (r.name || '').toLowerCase().includes(search.toLowerCase()) ||
    (r.email || '').toLowerCase().includes(search.toLowerCase()) ||
    (r.plan_name || '').toLowerCase().includes(search.toLowerCase())
  );

  const handleExport = () => {
    const rows = [
      ['name', 'email', 'tier', 'plan', 'jobs_used', 'jobs_limit', 'active_jobs', 'cvs_used', 'cv_limit', 'interviews_used', 'interview_limit'],
      ...filtered.map(r => [r.name, r.email, r.tier, r.plan_name, r.usage_jobs, r.usage_jobs, r.active_jobs, r.usage_cvs, r.cv_limit, r.usage_ai_interviews, r.ai_interview_limit]),
    ];
    const csv = rows.map(row => row.map(c => `"${String(c ?? '').replace(/"/g, '""')}"`).join(',')).join('\n');
    const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'recruiter-usage.csv';
    a.click();
    URL.revokeObjectURL(url);
    customToast({ type: 'success', title: 'Export Complete', message: 'Usage report downloaded as CSV.' });
  };

  const handleRowClick = (id: number) => {
    setExpandedRow(expandedRow === id ? null : id);
  };

  const totalApiCalls = aiAnalytics?.total_executions || 0;
  const activeCount = recruiters.filter(r => (r.usage_cvs || 0) > 0 || (r.usage_ai_interviews || 0) > 0 || (r.active_jobs || 0) > 0).length;

  const stats = [
    { label: 'Total Recruiters', value: String(recruiters.length), icon: Users, color: 'text-purple-600 bg-purple-50 dark:bg-purple-500/10' },
    { label: 'Active', value: String(activeCount), icon: TrendingUp, color: 'text-emerald-600 bg-emerald-50 dark:bg-emerald-500/10' },
    { label: 'Total CVs Processed', value: String(recruiters.reduce((s, r) => s + (r.usage_cvs || 0), 0).toLocaleString()), icon: BarChart3, color: 'text-blue-600 bg-blue-50 dark:bg-blue-500/10' },
    { label: 'AI Executions', value: totalApiCalls > 0 ? totalApiCalls.toLocaleString() : '0', icon: Briefcase, color: 'text-amber-600 bg-amber-50 dark:bg-amber-500/10' },
  ];

  const selected = recruiters.find(r => r.id === expandedRow);

  const quotaBar = (used: number, limit: number) => {
    const pct = limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0;
    return (
      <div className="w-full">
        <div className="h-1.5 w-full rounded-full bg-gray-100 dark:bg-white/10 overflow-hidden">
          <div className={cn('h-full rounded-full', pct >= 90 ? 'bg-red-500' : pct >= 60 ? 'bg-amber-500' : 'bg-emerald-500')} style={{ width: `${pct}%` }} />
        </div>
        <span className="text-[10px] text-gray-400">{used}/{limit}</span>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">Recruiter Usage Hub</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Monitor recruiter quota consumption and platform engagement</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" leftIcon={<RefreshCw className="h-4 w-4" />} onClick={load}>Refresh</Button>
          <Button variant="outline" leftIcon={<Download className="h-4 w-4" />} onClick={handleExport} className="font-bold">Export CSV</Button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat, i) => (
          <motion.div key={stat.label} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: i * 0.05 }}>
            <Card hoverable className="p-5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className={cn('flex h-10 w-10 items-center justify-center rounded-xl', stat.color)}>
                    <stat.icon className="h-5 w-5" />
                  </div>
                  <span className="text-xs font-black uppercase text-gray-500">{stat.label}</span>
                </div>
                <div className="text-2xl font-black text-gray-900 dark:text-white">{stat.value}</div>
              </div>
            </Card>
          </motion.div>
        ))}
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="overview">Recruiters</TabsTrigger>
          <TabsTrigger value="analytics">AI Analytics</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <Card className="glass-panel border-purple-200/50">
            <CardHeader>
              <div className="flex items-center justify-between w-full">
                <div>
                  <CardTitle>Recruiter Quota Usage</CardTitle>
                  <CardDescription>{filtered.length} recruiters match current filters</CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  <Input placeholder="Search recruiter or plan..." leftIcon={<Search className="h-4 w-4" />} value={search} onChange={(e) => setSearch(e.target.value)} wrapperClassName="w-64" />
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="py-16 text-center text-gray-400">Loading recruiters...</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left">
                    <thead>
                      <tr className="border-b border-purple-100 dark:border-white/10">
                        <th className="py-3 text-xs font-bold text-gray-500 uppercase">Recruiter</th>
                        <th className="py-3 text-xs font-bold text-gray-500 uppercase">Plan</th>
                        <th className="py-3 text-xs font-bold text-gray-500 uppercase">Active Jobs</th>
                        <th className="py-3 text-xs font-bold text-gray-500 uppercase">Jobs Used</th>
                        <th className="py-3 text-xs font-bold text-gray-500 uppercase">CVs Used</th>
                        <th className="py-3 text-xs font-bold text-gray-500 uppercase">AI Interviews</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.map((r, i) => (
                        <motion.tr
                          key={r.id}
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          transition={{ delay: i * 0.03 }}
                          className={cn(
                            'border-b border-gray-50 dark:border-white/[0.02] transition-colors cursor-pointer',
                            expandedRow === r.id ? 'bg-purple-50/80 dark:bg-purple-900/20' : 'hover:bg-purple-50/50 dark:hover:bg-white/[0.02]'
                          )}
                          onClick={() => handleRowClick(r.id)}
                        >
                          <td className="py-3">
                            <div className="flex items-center gap-2">
                              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-100 dark:bg-purple-900/50">
                                <Users className="h-4 w-4 text-purple-600 dark:text-purple-400" />
                              </div>
                              <div>
                                <div className="text-sm font-bold text-gray-900 dark:text-white">{r.name}</div>
                                <div className="text-xs text-gray-500">{r.email}</div>
                              </div>
                            </div>
                          </td>
                          <td className="py-3">
                            <Badge variant="info" size="sm">{r.tier || 'free'}</Badge>
                          </td>
                          <td className="py-3 text-sm font-bold text-gray-900 dark:text-white">{r.active_jobs}</td>
                          <td className="py-3 w-32">{quotaBar(r.usage_jobs || 0, r.usage_jobs || 0)}</td>
                          <td className="py-3 w-32">{quotaBar(r.usage_cvs || 0, r.cv_limit || 0)}</td>
                          <td className="py-3 w-32">{quotaBar(r.usage_ai_interviews || 0, r.ai_interview_limit || 0)}</td>
                        </motion.tr>
                      ))}
                      {filtered.length === 0 && !loading && <tr><td colSpan={6} className="py-10 text-center text-gray-400">No recruiters found.</td></tr>}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="analytics">
          <Card className="glass-panel border-purple-200/50">
            <CardHeader>
              <CardTitle>AI Analytics Overview</CardTitle>
              <CardDescription>Model usage and costs from the AI analytics service</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-4 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10 text-center">
                  <div className="text-2xl font-black text-gray-900 dark:text-white">{aiAnalytics?.total_executions || 0}</div>
                  <div className="text-xs font-medium text-gray-500">Total Executions</div>
                </div>
                <div className="p-4 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10 text-center">
                  <div className="text-2xl font-black text-gray-900 dark:text-white">{aiAnalytics?.total_tokens || 0}</div>
                  <div className="text-xs font-medium text-gray-500">Total Tokens</div>
                </div>
                <div className="p-4 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10 text-center">
                  <div className="text-2xl font-black text-gray-900 dark:text-white">${(aiAnalytics?.estimated_cost_usd || 0).toFixed(4)}</div>
                  <div className="text-xs font-medium text-gray-500">Estimated Cost (USD)</div>
                </div>
                <div className="p-4 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10 text-center">
                  <div className="text-2xl font-black text-gray-900 dark:text-white">{Object.keys(aiAnalytics?.model_usage || {}).length}</div>
                  <div className="text-xs font-medium text-gray-500">Models Used</div>
                </div>
              </div>
              {Object.keys(aiAnalytics?.model_usage || {}).length > 0 && (
                <div className="mt-6">
                  <h4 className="text-xs font-bold text-gray-500 uppercase mb-3">Breakdown by Model</h4>
                  <div className="space-y-2">
                    {Object.entries(aiAnalytics.model_usage).map(([model, count]) => (
                      <div key={model} className="flex items-center justify-between p-3 rounded-lg bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10">
                        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">{model}</span>
                        <span className="text-sm font-bold text-gray-900 dark:text-white">{String(count)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {selected && (
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="glass-panel border-purple-200/50">
            <CardHeader>
              <div>
                <CardTitle>{selected.name} — Quota Consumption</CardTitle>
                <CardDescription>{selected.email} &bull; {selected.plan_name || selected.tier} plan</CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div>
                  <h4 className="text-xs font-bold text-gray-500 uppercase mb-3">Jobs Posted</h4>
                  <div className="text-3xl font-black text-gray-900 dark:text-white">{selected.usage_jobs}</div>
                  <p className="text-xs text-gray-400 mt-1">{selected.active_jobs} active jobs now</p>
                </div>
                <div>
                  <h4 className="text-xs font-bold text-gray-500 uppercase mb-3">CVs Processed</h4>
                  <div className="text-3xl font-black text-gray-900 dark:text-white">{selected.usage_cvs}<span className="text-base text-gray-400"> / {selected.cv_limit}</span></div>
                </div>
                <div>
                  <h4 className="text-xs font-bold text-gray-500 uppercase mb-3">AI Interviews</h4>
                  <div className="text-3xl font-black text-gray-900 dark:text-white">{selected.usage_ai_interviews}<span className="text-base text-gray-400"> / {selected.ai_interview_limit}</span></div>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}
    </div>
  );
}
