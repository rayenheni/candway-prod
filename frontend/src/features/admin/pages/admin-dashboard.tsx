// ============================================================
// Admin Dashboard - Candway Platform
// Real KPIs from /admin/stats, /admin/activity, /admin/analytics/daily-report
// ============================================================

import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { customToast } from '@/shared/components/ui/toast';
import { cn } from '@/utils/cn';
import {
  Users, Coins, Briefcase, Clock, RefreshCw, Zap,
  CheckCircle2, AlertTriangle, Activity, ArrowRight, BarChart3,
} from 'lucide-react';
import { adminService } from '@/services/admin.service';
import type { AdminDashboardStats, ActivityLog, HealthResponse } from '@/services/admin.service';

interface StatCardProps {
  label: string;
  value: string;
  icon: React.ElementType;
  color: string;
  change?: string;
}

interface AIReport {
  sentiment?: string;
  executive_summary?: string;
  key_wins?: string[];
  risks?: string[];
  recommendations?: string[];
}

function StatCard({ label, value, icon: Icon, color, change }: StatCardProps) {
  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
      <Card className="glass-panel border-purple-200/50 dark:border-purple-500/20">
        <CardContent className="p-6">
          <div className="flex items-center justify-between mb-4">
            <div className={cn('flex h-12 w-12 items-center justify-center rounded-xl', color)}>
              <Icon className="h-6 w-6" />
            </div>
            {change && <span className="text-xs font-bold text-emerald-500">{change}</span>}
          </div>
          <div className="text-3xl font-black text-gray-900 dark:text-white tracking-tighter">{value}</div>
          <div className="text-[10px] font-black text-gray-400 uppercase tracking-widest mt-1">{label}</div>
        </CardContent>
      </Card>
    </motion.div>
  );
}

export default function AdminDashboardPage() {
  const navigate = useNavigate();
  const [stats, setStats] = useState<AdminDashboardStats | null>(null);
  const [activity, setActivity] = useState<ActivityLog[]>([]);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [actionQueue, setActionQueue] = useState<AdminDashboardStats['action_queue']>({ pending_courses: 0, pending_payments: 0, pending_subs: 0, open_tickets: 0 });
  const [aiReport, setAiReport] = useState<AIReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshingAI, setRefreshingAI] = useState(false);

  const loadAll = useCallback(async () => {
    try {
      const [statsRes, activityRes, healthRes] = await Promise.all([
        adminService.getAdminDashboardStats(),
        adminService.getRecentActivity(),
        adminService.getPlatformHealth().catch(() => null),
      ]);

      setStats(statsRes);
      setActivity(activityRes);
      setHealth(healthRes);
      setActionQueue(statsRes.action_queue || { pending_courses: 0, pending_payments: 0, pending_subs: 0, open_tickets: 0 });
    } catch (err) {
      console.error('Admin dashboard load error:', err);
      customToast({ type: 'error', title: 'Dashboard', message: 'Failed to load dashboard data.' });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  const loadAIReport = useCallback(async () => {
    try {
      const report = await adminService.getAIReport();
      setAiReport(report as AIReport);
    } catch {
      setAiReport(null);
    }
  }, []);

  useEffect(() => { loadAll(); loadAIReport(); }, [loadAll, loadAIReport]);

  const handleRefresh = () => {
    setRefreshing(true);
    loadAll();
  };

  const handleRefreshAI = async () => {
    setRefreshingAI(true);
    try {
      const report = await adminService.refreshAIReport();
      setAiReport(report as AIReport);
      customToast({ type: 'success', title: 'AI Report', message: 'Intelligence report refreshed.' });
    } catch (err: any) {
      customToast({ type: 'error', title: 'AI Report', message: err?.message || 'Failed to refresh report.' });
    } finally {
      setRefreshingAI(false);
    }
  };

  const handleBackup = async () => {
    try {
      const blob = await adminService.backupDatabase();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const date = new Date().toISOString().slice(0, 10);
      a.download = `candway_backup_${date}.db`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      customToast({ type: 'success', title: 'Backup', message: 'Database backup downloaded.' });
    } catch (err: any) {
      customToast({ type: 'error', title: 'Backup', message: err?.message || 'Backup failed.' });
    }
  };

  const formatMoney = (v: number | null | undefined) => {
    const n = Number(v || 0);
    return `${n.toLocaleString('en-US', { maximumFractionDigits: 0 })} TND`;
  };

  const sentinels = [
    { label: 'Pending Courses', count: actionQueue.pending_courses || 0, icon: Briefcase, color: 'bg-purple-100 text-purple-600', href: '/admin/courses' },
    { label: 'Pending Payments', count: actionQueue.pending_payments || 0, icon: Coins, color: 'bg-amber-100 text-amber-600', href: '/admin/payments' },
    { label: 'Open Tickets', count: actionQueue.open_tickets || 0, icon: Clock, color: 'bg-blue-100 text-blue-600', href: '/admin/support' },
    { label: 'Pending Subs', count: actionQueue.pending_subs || 0, icon: Users, color: 'bg-pink-100 text-pink-600', href: '/admin/subscriptions' },
  ];

  const healthOk = health?.status === 'ok' || health?.status === 'healthy';
  const clusterLabel = !health ? 'Status: Unknown' : healthOk ? 'Cluster Status: Normal' : 'Cluster Status: Degraded';
  const globalLabel = !health ? 'Unknown' : healthOk ? 'Operational' : 'Degraded';

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-24">
        <div className="h-10 w-10 animate-spin rounded-full border-2 border-purple-600 border-t-transparent" />
        <span className="text-sm text-gray-500">Loading admin dashboard...</span>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex justify-between items-center">
        <div>
          <div className="flex items-center gap-2">
            <Badge variant={!health ? 'default' : healthOk ? 'success' : 'warning'} size="sm" dot>{clusterLabel}</Badge>
          </div>
          <h1 className="text-3xl font-black text-gray-900 dark:text-white mt-1">Admin Control Center</h1>
          <p className="text-slate-500 mt-1 font-medium">Monitoring platform health and mission status.</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex flex-col items-end">
            <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Global Status</span>
            <span className={cn('text-xs font-bold flex items-center gap-1.5', !health ? 'text-slate-400' : healthOk ? 'text-emerald-500' : 'text-amber-500')}>
              <span className={cn('w-1.5 h-1.5 rounded-full animate-pulse', !health ? 'bg-slate-400' : healthOk ? 'bg-emerald-500' : 'bg-amber-500')}></span>
              <span>{globalLabel}</span>
            </span>
          </div>
          <Button variant="outline" size="sm" leftIcon={<Briefcase className="h-4 w-4" />} onClick={handleBackup}>
            DB Backup
          </Button>
          <Button variant="outline" size="sm" leftIcon={<RefreshCw className={cn("h-4 w-4", refreshing && "animate-spin")} />} onClick={handleRefresh}>
            {refreshing ? 'Refreshing...' : 'Refresh'}
          </Button>
          <Button variant="primary" size="sm" leftIcon={<BarChart3 className="h-4 w-4" />} onClick={() => navigate('/admin/analytics')}>
            Deep Analytics
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
        <StatCard
          label="Managed Users"
          value={String(stats?.users?.total || 0)}
          icon={Users}
          color="bg-indigo-50 text-indigo-600 dark:bg-indigo-500/10 dark:text-indigo-400"
          change={`+${stats?.users?.growth_rate || 0}%`}
        />
        <StatCard
          label="Revenue (TND)"
          value={formatMoney(stats?.revenue?.total)}
          icon={Coins}
          color="bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400"
        />
        <StatCard
          label="Platform Listings"
          value={String(stats?.activity?.jobs || 0)}
          icon={Briefcase}
          color="bg-purple-50 text-purple-600 dark:bg-purple-500/10 dark:text-purple-400"
        />
        <StatCard
          label="Active Queue"
          value={String((sentinels[0].count + sentinels[1].count + sentinels[2].count + sentinels[3].count))}
          icon={Clock}
          color="bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-12">
        <div className="lg:col-span-2 space-y-8">
          <Card className="glass-panel border-purple-200/50">
            <CardHeader>
              <CardTitle className="flex items-center gap-3">
                <Clock className="h-5 w-5 text-indigo-600" />
                Operation Queue
              </CardTitle>
              <CardDescription>Actionable items requiring admin attention</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {sentinels.map((s) => (
                  <motion.div key={s.label} whileHover={{ scale: 1.02 }}>
                    <a
                      href={s.href}
                      className="block p-6 bg-slate-50/50 dark:bg-white/[0.02] rounded-2xl border border-purple-100 dark:border-white/10 flex items-center justify-between group hover:bg-white hover:border-indigo-100 hover:shadow-lg transition-all"
                    >
                      <div className="flex items-center gap-4">
                        <div className={cn('w-10 h-10 rounded-xl flex items-center justify-center text-sm', s.color)}>
                          <s.icon className="h-5 w-5" />
                        </div>
                        <div>
                          <div className="text-[10px] font-black text-slate-400 uppercase tracking-wider">{s.label}</div>
                          <div className="text-lg font-black text-slate-800 dark:text-white">{s.count} Task{s.count !== 1 ? 's' : ''}</div>
                        </div>
                      </div>
                      <ArrowRight className="h-4 w-4 text-slate-300 group-hover:text-indigo-600 group-hover:translate-x-1 transition-all" />
                    </a>
                  </motion.div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card className="glass-panel border-purple-200/50 dark:border-purple-500/20 bg-gradient-to-r from-purple-50 to-indigo-50/50 dark:from-purple-950/20">
            <CardHeader>
              <CardTitle className="flex items-center gap-3">
                <Zap className="h-5 w-5 text-purple-600" />
                AI Strategic Intelligence
              </CardTitle>
              <CardDescription>Machine learning distribution & behavioral logs</CardDescription>
            </CardHeader>
            <CardContent>
              {aiReport ? (
                <div className="space-y-6">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-black uppercase text-indigo-400">AI Executive Summary</span>
                    <Badge variant={aiReport.sentiment === 'Positive' ? 'success' : aiReport.sentiment === 'Neutral' ? 'warning' : 'danger'} size="sm">
                      {aiReport.sentiment || 'Analyzing'}
                    </Badge>
                  </div>
                  <p className="text-sm text-slate-700 dark:text-gray-300 font-medium leading-relaxed">
                    {aiReport.executive_summary || 'No summary available.'}
                  </p>
                  <div className="grid md:grid-cols-2 gap-8 mt-6">
                    <div>
                      <h4 className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-4">Strategic Wins</h4>
                      <div className="space-y-3">
                        {(aiReport.key_wins || []).length > 0 ? (
                          aiReport.key_wins!.map((w, i) => (
                            <div key={i} className="flex items-start gap-3">
                              <div className="w-5 h-5 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center text-[10px] flex-shrink-0 mt-0.5">
                                <CheckCircle2 className="h-3 w-3" />
                              </div>
                              <span className="text-xs text-slate-600 dark:text-gray-300 font-medium">{w}</span>
                            </div>
                          ))
                        ) : (
                          <p className="text-xs text-slate-400 italic">No significant wins recorded today.</p>
                        )}
                      </div>
                    </div>
                    <div>
                      <h4 className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-4">Operational Risks</h4>
                      <div className="space-y-3">
                        {(aiReport.risks || []).length > 0 ? (
                          aiReport.risks!.map((r, i) => (
                            <div key={i} className="flex items-start gap-3">
                              <div className="w-5 h-5 bg-amber-100 text-amber-600 rounded-full flex items-center justify-center text-[10px] flex-shrink-0 mt-0.5">
                                <AlertTriangle className="h-3 w-3" />
                              </div>
                              <span className="text-xs text-slate-600 dark:text-gray-300 font-medium">{r}</span>
                            </div>
                          ))
                        ) : (
                          <p className="text-xs text-slate-400 italic">No critical risks identified.</p>
                        )}
                      </div>
                    </div>
                  </div>
                  {(aiReport.recommendations || []).length > 0 && (
                    <div className="pt-4 border-t border-slate-50 dark:border-white/10">
                      <h4 className="text-[10px] font-black text-indigo-600 uppercase tracking-widest mb-4">Actionable Recommendations</h4>
                      <div className="flex flex-wrap gap-2">
                        {aiReport.recommendations!.map((rec, i) => (
                          <span key={i} className="px-4 py-2 bg-indigo-50 text-indigo-600 rounded-xl text-[11px] font-bold border border-indigo-100/50">
                            {rec}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-8">
                  <p className="text-xs text-slate-400 font-medium mb-4">No strategic analysis generated for today yet.</p>
                  <Button variant="primary" size="sm" onClick={handleRefreshAI} disabled={refreshingAI}>
                    {refreshingAI ? 'Analyzing...' : 'Generate Daily Intelligence'}
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-8">
          <Card className="glass-panel border-purple-200/50">
            <CardHeader>
              <CardTitle className="flex items-center gap-3">
                <Activity className="h-5 w-5 text-indigo-600" />
                Live Audit
              </CardTitle>
              <Badge variant="default" size="sm" className="text-[9px] text-slate-400">
                Real-time
              </Badge>
            </CardHeader>
            <CardContent>
              <div className="space-y-4 max-h-[600px] overflow-y-auto pr-2">
                {activity.length === 0 ? (
                  <div className="text-center py-10 text-slate-300">
                    <Clock className="h-6 w-6 mx-auto mb-2" />
                    <p className="text-sm">No activity recorded.</p>
                  </div>
                ) : (
                  activity.slice(0, 20).map((log, i) => (
                    <motion.div
                      key={log.id || i}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.2, delay: i * 0.02 }}
                      className="p-4 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-[10px] font-black text-indigo-600 uppercase tracking-tighter">
                          {log.action || '—'}
                        </span>
                        <span className="text-[9px] text-slate-400 font-bold">
                          {log.created_at ? new Date(log.created_at as string).toLocaleTimeString() : '—'}
                        </span>
                      </div>
                      <p className="text-xs text-slate-600 dark:text-gray-300 break-all">
                        {typeof log.details === 'string' ? log.details : JSON.stringify(log.details || '—')}
                      </p>
                    </motion.div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
