// ============================================================
// Admin Jobs Management - Candway
// Real data from /admin/jobs API
// ============================================================

import { useCallback, useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/shared/components/ui/select';
import { customToast } from '@/shared/components/ui/toast';
import { Briefcase, CheckCircle2, Search, RefreshCw, BarChart3 } from 'lucide-react';
import { adminService, AdminJob } from '@/services/admin.service';

export default function AdminJobsPage() {
  const [jobs, setJobs] = useState<AdminJob[]>([]);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data: any = await adminService.getJobs({ status: statusFilter, page: 1, per_page: 100 });
      setJobs(data.jobs || []);
    } catch (err) {
      console.error('Admin jobs load error:', err);
      customToast({ type: 'error', title: 'Jobs', message: 'Failed to load jobs.' });
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { load(); }, [load]);

  const getStatusBadge = (job: AdminJob) => {
    const config: Record<string, { variant: 'success' | 'default' }> = {
      active: { variant: 'success' },
      inactive: { variant: 'default' },
    };
    const status = job.is_active ? 'active' : 'inactive';
    const c = config[status] || config.inactive;
    return <Badge variant={c.variant} size="sm" dot>{status}</Badge>;
  };

  const filtered = jobs.filter(job =>
    job.title.toLowerCase().includes(search.toLowerCase()) ||
    job.company.toLowerCase().includes(search.toLowerCase()) ||
    job.recruiter_name.toLowerCase().includes(search.toLowerCase())
  );

  const openCount = jobs.filter(j => j.is_active).length;
  const closedCount = jobs.filter(j => !j.is_active).length;

  const stats = [
    { label: 'Total Jobs', value: jobs.length, icon: Briefcase, color: 'text-purple-600', bg: 'bg-purple-100 dark:bg-purple-900/30' },
    { label: 'Open', value: openCount, icon: CheckCircle2, color: 'text-emerald-600', bg: 'bg-emerald-100 dark:bg-emerald-900/30' },
    { label: 'Closed', value: closedCount, icon: BarChart3, color: 'text-blue-600', bg: 'bg-blue-100 dark:bg-blue-900/30' },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">Jobs Management</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Monitor all platform job listings across companies</p>
        </div>
        <Button variant="outline" size="sm" leftIcon={<RefreshCw className="h-4 w-4" />} onClick={load}>Refresh</Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat) => (
          <Card key={stat.label} className="glass-panel border-purple-200/50">
            <CardContent className="p-5">
              <div className="flex justify-between items-start mb-3">
                <div className={`text-xs font-black uppercase tracking-widest ${stat.color}`}>{stat.label}</div>
                <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${stat.bg}`}>
                  <stat.icon className="h-4 w-4" />
                </div>
              </div>
              <div className="text-2xl font-black text-gray-900 dark:text-white tracking-tighter">{stat.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="flex gap-2 p-1 bg-slate-100 dark:bg-white/5 rounded-lg">
        <Input
          placeholder="Search jobs, companies, or recruiters..."
          leftIcon={<Search className="h-4 w-4" />}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          wrapperClassName="w-full sm:w-64"
        />
        <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v as any)}>
          <SelectTrigger className="w-32">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="inactive">Inactive</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <Card className="glass-panel border-purple-200/50">
        <CardHeader>
          <CardTitle>Job Listings ({filtered.length})</CardTitle>
          <CardDescription>All job listings across all companies and recruiters</CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex flex-col items-center justify-center gap-3 py-16">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-purple-600 border-t-transparent" />
              <span className="text-sm text-gray-500">Loading jobs...</span>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-purple-100 dark:border-white/10">
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Job Title</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Company</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Recruiter</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Status</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Applicants</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(job => (
                    <tr key={job.id} className="border-b border-gray-50 dark:border-white/[0.02] hover:bg-purple-50/50 transition-colors">
                      <td className="py-3">
                        <div className="text-sm font-extrabold text-gray-900 dark:text-white">{job.title}</div>
                        {job.location && <div className="text-xs text-gray-500">{job.location}</div>}
                      </td>
                      <td className="py-3 text-sm font-medium text-gray-700 dark:text-gray-300">{job.company}</td>
                      <td className="py-3 text-sm font-medium text-gray-500">{job.recruiter_name}</td>
                      <td className="py-3">{getStatusBadge(job)}</td>
                      <td className="py-3 text-sm font-medium text-gray-500">{job.applicant_count}</td>
                    </tr>
                  ))}
                  {filtered.length === 0 && !loading && <tr><td colSpan={5} className="py-10 text-center text-gray-400">No jobs found.</td></tr>}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
