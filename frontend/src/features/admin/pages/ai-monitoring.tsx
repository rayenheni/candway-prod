// ============================================================
// Admin AI Monitoring Dashboard - Candway
// Real data from /admin/analytics/ai, /admin/prompts/monitoring/live
// ============================================================

import { useCallback, useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { customToast } from '@/shared/components/ui/toast';
import { CheckCircle2, XCircle, RefreshCw, TrendingUp, Zap, ShieldCheck, Activity } from 'lucide-react';
import { cn } from '@/utils/cn';
import { adminService, AIAnalytics } from '@/services/admin.service';

interface LiveEvent {
  id: number;
  status: string;
  response_time_ms?: number | null;
  output_score?: number | null;
  executed_at?: string | null;
}

interface LiveMonitoring {
  recent_executions?: { total?: number; successful?: number; failed?: number; success_rate?: number };
  system_health?: { status?: string; audit_events_last_hour?: number };
  recent_events?: LiveEvent[];
}

export default function AIMonitoringPage() {
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [aiAnalytics, setAiAnalytics] = useState<AIAnalytics | null>(null);
  const [live, setLive] = useState<LiveMonitoring | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [analytics, liveData] = await Promise.all([
        adminService.getAIAnalytics(),
        adminService.getPromptMonitoringLive<LiveMonitoring>(),
      ]);
      setAiAnalytics(analytics);
      setLive(liveData);
    } catch (err) {
      console.error('AI monitoring load error:', err);
      customToast({ type: 'error', title: 'AI Monitoring', message: 'Failed to load AI metrics.' });
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleRefresh = () => {
    setIsRefreshing(true);
    load();
  };

  const recentRequests = (live?.recent_events || []).map((ev) => ({
    id: ev.id,
    status: ev.status || 'unknown',
    duration: ev.response_time_ms != null ? `${ev.response_time_ms}ms` : '—',
    score: ev.output_score != null ? String(ev.output_score) : '—',
    timestamp: ev.executed_at ? new Date(ev.executed_at).toLocaleTimeString() : '—',
  }));

  const successRate = live?.recent_executions?.success_rate;
  const systemStatus = live?.system_health?.status;

  const aiStats = [
    { label: 'Total Executions', value: String(aiAnalytics?.total_executions || 0), trend: aiAnalytics?.total_executions ? `${aiAnalytics.total_executions} calls` : '0', icon: Zap, color: 'text-purple-600 bg-purple-50 dark:bg-purple-500/10' },
    { label: 'Model Usage Diversity', value: `${Object.keys(aiAnalytics?.model_usage || {}).length} models`, trend: Object.keys(aiAnalytics?.model_usage || {}).length ? 'in use' : '—', icon: TrendingUp, color: 'text-blue-600 bg-blue-50 dark:bg-blue-500/10' },
    { label: 'Recent Success Rate', value: successRate != null ? `${successRate.toFixed(1)}%` : '—', trend: `${live?.recent_executions?.total ?? 0} runs`, icon: ShieldCheck, color: 'text-amber-600 bg-amber-50 dark:bg-amber-500/10' },
    { label: 'Scoring Events (1h)', value: `${(live?.recent_events || []).length} events`, trend: `${live?.recent_executions?.failed ?? 0} failed`, icon: Activity, color: 'text-indigo-600 bg-indigo-50 dark:bg-indigo-500/10' },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Badge variant={systemStatus === 'healthy' ? 'success' : systemStatus === 'degraded' ? 'warning' : 'default'} size="sm" dot>
              {systemStatus ? `AI Engine: ${systemStatus}` : 'AI Engine: unknown'}
            </Badge>
          </div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white mt-1">AI Engine Monitoring</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Real-time observability of LLM calls and scoring accuracy</p>
        </div>
        <Button variant="outline" onClick={handleRefresh} leftIcon={<RefreshCw className={cn('h-4 w-4 text-purple-600', isRefreshing && 'animate-spin')} />}>
          {isRefreshing ? 'Syncing...' : 'Refresh Metrics'}
        </Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {aiStats.map((stat, i) => (
          <motion.div key={stat.label} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: i * 0.05 }}>
            <Card hoverable className="p-5">
              <div className="flex items-center justify-between">
                <div className={cn('flex h-10 w-10 items-center justify-center rounded-xl', stat.color)}>
                  <stat.icon className="h-5 w-5" />
                </div>
                <div className="text-xs font-bold text-gray-500 dark:text-gray-400">{stat.trend}</div>
              </div>
              <div className="mt-4">
                <div className="text-2xl font-black text-gray-900 dark:text-white">{stat.value}</div>
                <div className="text-sm font-medium text-gray-500 dark:text-gray-400">{stat.label}</div>
              </div>
            </Card>
          </motion.div>
        ))}
      </div>

      <Card className="glass-panel border-purple-200/50">
        <CardHeader>
          <CardTitle>Live Inference Requests</CardTitle>
          <CardDescription>Recent prompt executions in the last hour</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-purple-100 dark:border-white/10">
                  <th className="py-3 text-xs font-bold text-gray-500 uppercase">ID</th>
                  <th className="py-3 text-xs font-bold text-gray-500 uppercase">Status</th>
                  <th className="py-3 text-xs font-bold text-gray-500 uppercase">Duration</th>
                  <th className="py-3 text-xs font-bold text-gray-500 uppercase">Output Score</th>
                  <th className="py-3 text-xs font-bold text-gray-500 uppercase">Time</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan={5} className="py-12 text-center text-gray-400">Loading AI activity...</td></tr>
                ) : recentRequests.length === 0 ? (
                  <tr><td colSpan={5} className="py-12 text-center text-gray-400">No recent AI requests.</td></tr>
                ) : (
                  recentRequests.map((req) => (
                    <tr key={req.id} className="border-b border-gray-50 dark:border-white/[0.02] hover:bg-purple-50/50 dark:hover:bg-white/[0.02] transition-colors">
                      <td className="py-3 text-sm font-mono text-gray-500">#{req.id}</td>
                      <td className="py-3">
                        {req.status === 'success' ? (
                          <Badge variant="success" size="sm"><CheckCircle2 className="h-3 w-3 mr-1" />Success</Badge>
                        ) : (
                          <Badge variant="danger" size="sm"><XCircle className="h-3 w-3 mr-1" />{req.status || 'failed'}</Badge>
                        )}
                      </td>
                      <td className="py-3 text-sm font-medium text-gray-500">{req.duration}</td>
                      <td className="py-3 text-sm font-medium text-gray-500">{req.score}</td>
                      <td className="py-3 text-sm font-medium text-gray-500">{req.timestamp}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
