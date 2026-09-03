// ============================================================
// Admin System Health & Technical Logs - Candway Platform
// Real data from /monitoring/health, /admin/logs, /admin/background-jobs
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
import { Database, HardDrive, Activity, RefreshCw, Search, Filter, Download, Clock } from 'lucide-react';
import { adminService, type BackgroundJob, type SystemEvent } from '@/services/admin.service';

interface HealthService {
  name: string;
  status: 'operational' | 'degraded' | 'down';
  detail: string;
}

interface LogEntry {
  level: string;
  message: string;
  time: string;
}

const CHECK_LABELS: Record<string, string> = {
  database: 'Database',
  disk: 'Disk Storage',
  memory: 'Memory',
};

function mapStatus(value: string): HealthService['status'] {
  const v = (value || '').toLowerCase();
  if (v === 'healthy' || v === 'ok') return 'operational';
  if (v === 'warning' || v === 'degraded') return 'degraded';
  if (v === 'unhealthy' || v === 'failed' || v === 'down') return 'down';
  return 'degraded';
}

export default function SystemHealthPage() {
  const [services, setServices] = useState<HealthService[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [jobs, setJobs] = useState<BackgroundJob[]>([]);
  const [events, setEvents] = useState<SystemEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState('health');
  const [logSearch, setLogSearch] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [health, logData, jobData] = await Promise.all([
        adminService.getPlatformHealth(),
        adminService.getSystemLogs(200),
        adminService.getBackgroundJobs(),
      ]);

      const checks = health?.checks || {};
      const mapped: HealthService[] = Object.entries(checks).map(([name, value]) => ({
        name: CHECK_LABELS[name] || name.replace(/_/g, ' '),
        status: mapStatus(value),
        detail: value,
      }));
      if (mapped.length > 0) {
        mapped.unshift({ name: 'API / App', status: health?.status === 'unhealthy' ? 'down' : 'operational', detail: health?.status || 'unknown' });
      }
      setServices(mapped);

      const parsed: LogEntry[] = (logData?.logs || []).map((line: string) => {
        const levelMatch = line.match(/\b(INFO|WARN|ERROR|DEBUG)\b/);
        return {
          level: levelMatch ? levelMatch[1] : 'INFO',
          message: line.slice(0, 200),
          time: '',
        };
      });
      setLogs(parsed);

      setJobs(jobData?.active_batch_jobs || []);
      setEvents(jobData?.recent_system_events || []);
    } catch (err) {
      console.error('Health load error:', err);
      customToast({ type: 'error', title: 'System Health', message: 'Failed to load health data.' });
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

  const filteredLogs = logs.filter(l =>
    l.message.toLowerCase().includes(logSearch.toLowerCase()) ||
    l.level.toLowerCase().includes(logSearch.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Badge variant={services.length === 0 || services.some(s => s.status === 'down') ? 'danger' : 'success'} size="sm" dot>
              {services.length === 0 || services.some(s => s.status === 'down') ? 'Cluster Status: Degraded' : 'Cluster Status: Normal'}
            </Badge>
          </div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white mt-1">System Health & Logs</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Infrastructure monitoring for the Candway Tunisia platform</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" leftIcon={<Download className="h-4 w-4" />} onClick={async () => {
            try {
              const data = await adminService.getSystemLogs(5000);
              const blob = new Blob([data.logs.join('\n')], { type: 'text/plain' });
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url; a.download = `candway-logs-${new Date().toISOString()}.log`;
              a.click(); URL.revokeObjectURL(url);
            } catch (err) {
              customToast({ type: 'error', title: 'Export', message: 'Failed to export logs.' });
            }
          }}>Export</Button>
          <Button variant="outline" onClick={handleRefresh} leftIcon={<RefreshCw className={cn('h-4 w-4', isRefreshing && 'animate-spin')} />}>
            {isRefreshing ? 'Syncing...' : 'Refresh Health'}
          </Button>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="health">Infrastructure Health</TabsTrigger>
          <TabsTrigger value="logs">Application Logs</TabsTrigger>
          <TabsTrigger value="jobs">Background Jobs</TabsTrigger>
        </TabsList>

        <TabsContent value="health">
          <Card className="glass-panel border-purple-200/50">
            <CardHeader>
              <CardTitle>Live Service Status</CardTitle>
              <CardDescription>Real-time operational health of the Candway platform</CardDescription>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="flex flex-col items-center justify-center gap-3 py-16">
                  <div className="h-8 w-8 animate-spin rounded-full border-2 border-purple-600 border-t-transparent" />
                  <span className="text-sm text-gray-500">Loading health...</span>
                </div>
              ) : services.length === 0 ? (
                <div className="text-center py-16 text-gray-400">No health data available.</div>
              ) : (
                <div className="space-y-3">
                  {services.map((svc, i) => (
                    <motion.div
                      key={svc.name}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.3, delay: i * 0.05 }}
                      className="flex items-center justify-between p-4 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10"
                    >
                      <div className="flex items-center gap-3">
                        {svc.name === 'Database' ? <Database className="h-5 w-5 text-blue-500" /> :
                         svc.name === 'Disk Storage' ? <HardDrive className="h-5 w-5 text-emerald-500" /> :
                         <Activity className="h-5 w-5 text-purple-500" />}
                        <div>
                          <div className="text-sm font-extrabold text-gray-900 dark:text-white">{svc.name}</div>
                          <div className="flex items-center gap-2 text-xs text-gray-500 mt-0.5">
                            <Clock className="h-3 w-3" />
                            <span>{svc.detail}</span>
                          </div>
                        </div>
                      </div>
                      <Badge
                        variant={svc.status === 'operational' ? 'success' : svc.status === 'degraded' ? 'warning' : 'danger'}
                        size="sm"
                        dot
                      >
                        {svc.status}
                      </Badge>
                    </motion.div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="logs">
          <Card className="glass-panel border-purple-200/50">
            <CardHeader>
              <div className="flex items-center justify-between w-full">
                <div>
                  <CardTitle>Application Logs</CardTitle>
                  <CardDescription>Filtered logs from the past 24 hours</CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  <Input
                    placeholder="Search logs..."
                    leftIcon={<Search className="h-4 w-4" />}
                    value={logSearch}
                    onChange={(e) => setLogSearch(e.target.value)}
                    wrapperClassName="w-48"
                  />
                  <Button variant="outline" leftIcon={<Filter className="h-4 w-4" />} onClick={() => setLogSearch('')}>Clear</Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 font-mono text-xs max-h-[500px] overflow-y-auto">
                {filteredLogs.length === 0 ? (
                  <div className="text-center py-10 text-slate-300">No log entries matching your search.</div>
                ) : (
                  filteredLogs.map((log, i) => (
                    <div key={i} className="flex items-start gap-3 p-2 rounded-lg bg-white/40 dark:bg-black/20 border border-transparent hover:border-purple-200 dark:hover:border-purple-500/20 transition-colors">
                      <span className={cn(
                        'text-xs font-bold mt-0.5 w-10 text-right shrink-0',
                        log.level === 'ERROR' ? 'text-red-500' : log.level === 'WARN' ? 'text-amber-500' : 'text-blue-500'
                      )}>{log.level}</span>
                      <span className="text-gray-700 dark:text-gray-300 break-all">{log.message}</span>
                      <span className="text-purple-500 font-medium shrink-0">{log.time || '—'}</span>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="jobs">
          <Card className="glass-panel border-purple-200/50">
            <CardHeader>
              <CardTitle>Background Processing Jobs</CardTitle>
              <CardDescription>Active batch jobs and recent system events</CardDescription>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="flex flex-col items-center justify-center gap-3 py-16">
                  <div className="h-8 w-8 animate-spin rounded-full border-2 border-purple-600 border-t-transparent" />
                  <span className="text-sm text-gray-500">Loading jobs...</span>
                </div>
              ) : (
                <div className="space-y-6">
                  <div>
                    <h4 className="text-xs font-black text-slate-400 uppercase tracking-widest mb-3">Active Batch Jobs</h4>
                    {jobs.length === 0 ? (
                      <p className="text-sm text-gray-400">No active batch jobs.</p>
                    ) : (
                      <div className="space-y-2">
                        {jobs.map((job) => (
                          <div key={job.id} className="flex items-center justify-between p-3 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10">
                            <div className="min-w-0">
                              <p className="text-sm font-semibold text-gray-900 dark:text-white truncate">{job.title || `Job #${job.id}`}</p>
                              <p className="text-xs text-gray-500">{job.target_role || '—'}{job.worker_status ? ` • ${job.worker_status}` : ''}</p>
                            </div>
                            <Badge variant="warning" size="sm" dot>{job.status}</Badge>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  <div>
                    <h4 className="text-xs font-black text-slate-400 uppercase tracking-widest mb-3">Recent System Events</h4>
                    {events.length === 0 ? (
                      <p className="text-sm text-gray-400">No recent system events.</p>
                    ) : (
                      <div className="space-y-2 font-mono text-xs max-h-[300px] overflow-y-auto">
                        {events.map((ev) => (
                          <div key={ev.id} className="flex items-start gap-3 p-2 rounded-lg bg-white/40 dark:bg-black/20 border border-transparent">
                            <span className="text-purple-500 font-medium shrink-0">{ev.action}</span>
                            <span className="text-gray-700 dark:text-gray-300 break-all">{ev.details || ''}</span>
                            <span className="text-gray-400 shrink-0 ml-auto">{ev.timestamp ? new Date(ev.timestamp).toLocaleString() : ''}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
