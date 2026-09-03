import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router';
import { motion } from 'framer-motion';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { backgroundChecksService } from '@/services/background-checks.service';
import { Search, ShieldCheck, AlertTriangle, CheckCircle, Clock, XCircle, ExternalLink, Loader2 } from 'lucide-react';

const statusConfig: Record<string, { label: string; variant: 'success' | 'warning' | 'danger' | 'primary'; icon: React.ElementType }> = {
  clear: { label: 'Clear', variant: 'success', icon: CheckCircle },
  pending: { label: 'Pending', variant: 'warning', icon: Clock },
  issue: { label: 'Issue', variant: 'danger', icon: XCircle },
  in_progress: { label: 'In Progress', variant: 'primary', icon: Clock },
};

export default function BackgroundChecksPage() {
  const navigate = useNavigate();
  const [checks, setChecks] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  useEffect(() => {
    Promise.all([
      backgroundChecksService.list(),
      backgroundChecksService.getStats(),
    ]).then(([listRes, statsRes]) => {
      setChecks(listRes?.items ?? []);
      setStats(statsRes);
    }).catch(() => {
      setChecks([]);
    }).finally(() => setLoading(false));
  }, []);

  const filtered = checks.filter(c =>
    (c.candidate_name ?? c.candidate ?? '').toLowerCase().includes(search.toLowerCase()) ||
    (c.position ?? '').toLowerCase().includes(search.toLowerCase())
  );

  const statsCards = stats ? [
    { label: 'Total Checks', value: stats.total_checks ?? checks.length, color: 'text-purple-600', bg: 'bg-purple-100 dark:bg-purple-500/20', icon: ShieldCheck },
    { label: 'Clear', value: stats.clear_count ?? checks.filter(c => c.status === 'clear').length, color: 'text-emerald-600', bg: 'bg-emerald-100 dark:bg-emerald-500/20', icon: CheckCircle },
    { label: 'Pending', value: stats.pending_count ?? checks.filter(c => c.status === 'pending' || c.status === 'in_progress').length, color: 'text-amber-600', bg: 'bg-amber-100 dark:bg-amber-500/20', icon: Clock },
    { label: 'Issues', value: stats.issue_count ?? checks.filter(c => c.status === 'issue').length, color: 'text-red-600', bg: 'bg-red-100 dark:bg-red-500/20', icon: AlertTriangle },
  ] : [];

  const handleViewReport = (appId: string) => {
    navigate(`/background-checks/${appId}`);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 text-violet-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">Background Checks</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Verify candidate credentials and compliance records</p>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {statsCards.map((stat, i) => (
          <motion.div key={stat.label} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: i * 0.05 }}>
            <Card className="glass-panel border-purple-200/50">
              <CardContent className="p-5">
                <div className="flex items-center gap-3">
                  <div className={`flex h-12 w-12 items-center justify-center rounded-xl ${stat.bg} ${stat.color}`}>
                    <stat.icon className="h-6 w-6" />
                  </div>
                  <div>
                    <div className="text-2xl font-black text-gray-900 dark:text-white">{stat.value}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">{stat.label}</div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      <Card className="glass-panel border-purple-200/50">
        <CardContent className="p-5">
          <div className="mb-4">
            <Input placeholder="Search by candidate or position..." leftIcon={<Search className="h-4 w-4 text-purple-500" />} value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-purple-100 dark:border-white/10">
                  <th className="text-left py-3 px-2 text-xs font-bold text-gray-500 uppercase tracking-wider">Candidate</th>
                  <th className="text-left py-3 px-2 text-xs font-bold text-gray-500 uppercase tracking-wider">Position</th>
                  <th className="text-left py-3 px-2 text-xs font-bold text-gray-500 uppercase tracking-wider">Status</th>
                  <th className="text-left py-3 px-2 text-xs font-bold text-gray-500 uppercase tracking-wider">Initiated</th>
                  <th className="text-right py-3 px-2 text-xs font-bold text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((check, i) => {
                  const statusKey = check.status ?? 'pending';
                  const config = statusConfig[statusKey] || statusConfig.pending;
                  const StatusIcon = config.icon;
                  const candidateName = check.candidate_name ?? check.candidate ?? 'Unknown';
                  return (
                    <motion.tr
                      key={check.id}
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.25, delay: i * 0.03 }}
                      className="border-b border-purple-50 dark:border-white/5 hover:bg-purple-50/50 dark:hover:bg-white/[0.02] transition-colors"
                    >
                      <td className="py-3 px-2">
                        <span className="font-extrabold text-gray-900 dark:text-white">{candidateName}</span>
                      </td>
                      <td className="py-3 px-2 text-gray-600 dark:text-gray-400">{check.position ?? check.job_title ?? ''}</td>
                      <td className="py-3 px-2">
                        <Badge variant={config.variant} size="sm"><StatusIcon className="h-3 w-3" />{config.label}</Badge>
                      </td>
                      <td className="py-3 px-2 text-gray-500">{check.initiated_at ? new Date(check.initiated_at).toLocaleDateString() : check.initiated ?? '—'}</td>
                      <td className="py-3 px-2 text-right">
                        <Button variant="ghost" size="xs" leftIcon={<ExternalLink className="h-3.5 w-3.5" />} onClick={() => handleViewReport(check.id)}>View Report</Button>
                      </td>
                    </motion.tr>
                  );
                })}
              </tbody>
            </table>
            {filtered.length === 0 && (
              <div className="py-12 text-center text-gray-500">
                <ShieldCheck className="h-8 w-8 mx-auto mb-2 text-purple-300" />
                <p>No background checks match your search</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
