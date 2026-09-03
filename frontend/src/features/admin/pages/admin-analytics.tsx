// ============================================================
// Admin Platform Analytics - Candway
// Real data from /admin/analytics/overview|growth|revenue|ai|efficiency
// ============================================================

import { useCallback, useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { customToast } from '@/shared/components/ui/toast';
import { cn } from '@/utils/cn';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, AreaChart, Area, PieChart, Pie, Cell,
} from 'recharts';
import {
  Users, Coins, FileText, Zap, RefreshCw, TrendingUp, Wallet, Cpu, Activity, ArrowUpRight,
} from 'lucide-react';
import {
  adminService, type AnalyticsOverview, type GrowthPoint,
  type RevenueAnalytics, type AIAnalytics, type PlatformEfficiency,
} from '@/services/admin.service';

const PIE_COLORS = ['#7c3aed', '#6366f1', '#8b5cf6', '#a855f7', '#d946ef', '#ec4899', '#f59e0b', '#10b981', '#0ea5e9', '#f43f5e'];

function fmtMoney(v: number | null | undefined): string {
  const n = Number(v || 0);
  return `${n.toLocaleString('en-US', { maximumFractionDigits: 0 })} TND`;
}

function fmtNum(v: number | null | undefined): string {
  return Number(v || 0).toLocaleString('en-US');
}

export default function AdminAnalyticsPage() {
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [growth, setGrowth] = useState<GrowthPoint[]>([]);
  const [revenue, setRevenue] = useState<RevenueAnalytics | null>(null);
  const [ai, setAi] = useState<AIAnalytics | null>(null);
  const [efficiency, setEfficiency] = useState<PlatformEfficiency | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [overviewRes, growthRes, revenueRes, aiRes, effRes] = await Promise.all([
        adminService.getAnalyticsOverview().catch(() => null),
        adminService.getGrowthData(30).catch(() => [] as GrowthPoint[]),
        adminService.getRevenueAnalytics(6).catch(() => null),
        adminService.getAIAnalytics().catch(() => null),
        adminService.getPlatformEfficiency().catch(() => null),
      ]);
      setOverview(overviewRes);
      setGrowth(growthRes);
      setRevenue(revenueRes);
      setAi(aiRes);
      setEfficiency(effRes);
    } catch (err) {
      console.error('Platform analytics load error:', err);
      customToast({ type: 'error', title: 'Platform Analytics', message: 'Failed to load analytics data.' });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleRefresh = () => {
    setRefreshing(true);
    load();
  };

  const modelData = Object.entries(ai?.model_usage || {}).map(([name, count]) => ({ name, count }));
  const growthPoints = growth.map((g, i) => ({ ...g, index: i }));

  const kpis = [
    { label: 'Total Users', value: fmtNum(overview?.users?.total), icon: Users, color: 'text-indigo-600 bg-indigo-50 dark:bg-indigo-500/10', sub: overview?.users?.growth_rate != null ? `+${overview.users.growth_rate}% growth` : '—' },
    { label: 'Platform Revenue', value: fmtMoney(revenue?.total_revenue), icon: Coins, color: 'text-amber-600 bg-amber-50 dark:bg-amber-500/10', sub: `${(revenue?.monthly_trend?.length || 0)} months tracked` },
    { label: 'Total Applications', value: fmtNum(overview?.activity?.applications), icon: FileText, color: 'text-purple-600 bg-purple-50 dark:bg-purple-500/10', sub: `${fmtNum(overview?.activity?.jobs)} jobs · ${fmtNum(overview?.activity?.interviews)} interviews` },
    { label: 'AI Executions', value: fmtNum(ai?.total_executions), icon: Zap, color: 'text-fuchsia-600 bg-fuchsia-50 dark:bg-fuchsia-500/10', sub: ai?.estimated_cost_usd != null ? `~$${ai.estimated_cost_usd.toFixed(2)} est. cost` : '—' },
  ];

  return (
    <div className="space-y-8">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Badge variant="default" size="sm" dot>Platform-wide</Badge>
          </div>
          <h1 className="text-3xl font-black text-gray-900 dark:text-white mt-1">Platform Analytics</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400 font-medium">Real-time KPIs across users, revenue, activity and AI infrastructure</p>
        </div>
        <Button variant="outline" leftIcon={<RefreshCw className={cn('h-4 w-4 text-purple-600', refreshing && 'animate-spin')} />} onClick={handleRefresh} disabled={loading}>
          {refreshing ? 'Syncing...' : 'Refresh Metrics'}
        </Button>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center gap-3 py-24">
          <div className="h-10 w-10 animate-spin rounded-full border-2 border-purple-600 border-t-transparent" />
          <span className="text-sm text-gray-500">Loading platform analytics...</span>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {kpis.map((stat, i) => (
              <motion.div key={stat.label} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: i * 0.05 }}>
                <Card hoverable className="p-5 border-purple-200/70 dark:border-purple-500/20">
                  <div className="flex items-center justify-between">
                    <div className={cn('flex h-10 w-10 items-center justify-center rounded-xl', stat.color)}>
                      <stat.icon className="h-5 w-5" />
                    </div>
                    <span className="text-xs font-bold text-gray-500 dark:text-gray-400">{stat.sub}</span>
                  </div>
                  <div className="mt-4">
                    <div className="text-2xl sm:text-3xl font-black text-gray-900 dark:text-white">{stat.value}</div>
                    <div className="text-sm font-medium text-gray-500 dark:text-gray-400">{stat.label}</div>
                  </div>
                </Card>
              </motion.div>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card className="glass-panel border-purple-200/50">
              <CardHeader>
                <CardTitle className="flex items-center gap-2"><TrendingUp className="h-5 w-5 text-purple-600" /> Revenue Trend</CardTitle>
                <CardDescription>Monthly platform revenue (paid transactions)</CardDescription>
              </CardHeader>
              <CardContent className="mt-4">
                {!revenue?.monthly_trend?.length ? (
                  <p className="py-16 text-center text-sm text-gray-500 dark:text-gray-400">No revenue data available yet.</p>
                ) : (
                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={revenue.monthly_trend}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                      <XAxis dataKey="month" tick={{ fontSize: 12 }} stroke="#9ca3af" />
                      <YAxis tick={{ fontSize: 12 }} stroke="#9ca3af" />
                      <Tooltip />
                      <Bar dataKey="revenue" name="Revenue (TND)" fill="#7c3aed" radius={[6, 6, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>

            <Card className="glass-panel border-purple-200/50">
              <CardHeader>
                <CardTitle className="flex items-center gap-2"><Activity className="h-5 w-5 text-indigo-600" /> User & Job Growth</CardTitle>
                <CardDescription>Daily signups and job posts over the last 30 days</CardDescription>
              </CardHeader>
              <CardContent className="mt-4">
                {growthPoints.length === 0 ? (
                  <p className="py-16 text-center text-sm text-gray-500 dark:text-gray-400">No growth data available yet.</p>
                ) : (
                  <ResponsiveContainer width="100%" height={260}>
                    <AreaChart data={growthPoints}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                      <XAxis dataKey="index" tick={false} stroke="#9ca3af" />
                      <YAxis tick={{ fontSize: 12 }} stroke="#9ca3af" />
                      <Tooltip labelFormatter={(_, payload) => {
                        const idx = Number(payload?.[0]?.payload?.index ?? 0);
                        return growthPoints[idx]?.date || '';
                      }} />
                      <Legend />
                      <Area type="monotone" dataKey="new_users" name="New Users" stroke="#6366f1" fill="#6366f1" fillOpacity={0.25} />
                      <Area type="monotone" dataKey="new_jobs" name="New Jobs" stroke="#a855f7" fill="#a855f7" fillOpacity={0.25} />
                    </AreaChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <Card className="glass-panel border-purple-200/50">
              <CardHeader>
                <CardTitle className="flex items-center gap-2"><Wallet className="h-5 w-5 text-amber-600" /> AI Efficiency</CardTitle>
                <CardDescription>ROI of AI infrastructure spend</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-4 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10">
                    <span className="text-xs font-bold text-gray-500">Revenue / AI cost</span>
                    <Badge variant={Number(efficiency?.roi_multiplier || 0) > 0 ? 'success' : 'default'} size="sm">
                      {Number(efficiency?.roi_multiplier || 0).toFixed(2)}x
                    </Badge>
                  </div>
                  <div className="flex items-center justify-between p-4 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10">
                    <span className="text-xs font-bold text-gray-500">Estimated AI cost</span>
                    <span className="text-sm font-black text-gray-900 dark:text-white">${Number(efficiency?.ai_cost_usd || 0).toFixed(2)}</span>
                  </div>
                  <div className="flex items-center justify-between p-4 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10">
                    <span className="text-xs font-bold text-gray-500">Token usage</span>
                    <span className="text-sm font-black text-gray-900 dark:text-white">{fmtNum(efficiency?.token_usage)}</span>
                  </div>
                  <div className="flex items-center justify-between p-4 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10">
                    <span className="text-xs font-bold text-gray-500">Avg cost / execution</span>
                    <span className="text-sm font-black text-gray-900 dark:text-white">${Number(efficiency?.avg_cost_per_execution || 0).toFixed(4)}</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="glass-panel border-purple-200/50">
              <CardHeader>
                <CardTitle className="flex items-center gap-2"><Cpu className="h-5 w-5 text-purple-600" /> Model Usage</CardTitle>
                <CardDescription>LLM distribution across executions</CardDescription>
              </CardHeader>
              <CardContent className="mt-4">
                {modelData.length === 0 ? (
                  <p className="py-16 text-center text-sm text-gray-500 dark:text-gray-400">No model usage recorded yet.</p>
                ) : (
                  <>
                    <ResponsiveContainer width="100%" height={200}>
                      <PieChart>
                        <Pie data={modelData} dataKey="count" nameKey="name" cx="50%" cy="50%" outerRadius={80} label>
                          {modelData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                        </Pie>
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                    <div className="mt-3 space-y-1.5">
                      {modelData.map((m, i) => (
                        <div key={m.name} className="flex items-center justify-between text-xs">
                          <span className="flex items-center gap-2 font-medium text-gray-600 dark:text-gray-300">
                            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: PIE_COLORS[i % PIE_COLORS.length] }} />
                            {m.name}
                          </span>
                          <span className="font-black text-gray-900 dark:text-white">{m.count}</span>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </CardContent>
            </Card>

            <Card className="glass-panel border-purple-200/50">
              <CardHeader>
                <CardTitle className="flex items-center gap-2"><Activity className="h-5 w-5 text-fuchsia-600" /> Latest AI Events</CardTitle>
                <CardDescription>Most recent AI inference activity</CardDescription>
              </CardHeader>
              <CardContent className="mt-2">
                {!ai?.latest_events?.length ? (
                  <p className="py-16 text-center text-sm text-gray-500 dark:text-gray-400">No AI events recorded yet.</p>
                ) : (
                  <div className="space-y-2 max-h-[280px] overflow-y-auto pr-1">
                    {ai.latest_events.map((ev, i) => (
                      <div key={i} className="flex items-start gap-3 p-3 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10">
                        <ArrowUpRight className="h-4 w-4 text-purple-500 mt-0.5 shrink-0" />
                        <div className="min-w-0">
                          <p className="text-xs font-bold text-gray-800 dark:text-gray-200 truncate">{ev.action || '—'}</p>
                          <p className="text-[11px] text-gray-500 dark:text-gray-400">{(ev.target || '—')} · {ev.time || '—'}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}