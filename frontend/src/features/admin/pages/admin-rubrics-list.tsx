// ============================================================
// Admin Rubrics Management - Candway Platform
// Real data from /admin/rubrics
// ============================================================

import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { SimpleDropdown } from '@/shared/components/ui/dropdown-menu';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/shared/components/ui/dialog';
import { customToast } from '@/shared/components/ui/toast';
import { Search, Plus, MoreHorizontal, FileText, CheckCircle2, XCircle, Clock, Eye } from 'lucide-react';
import { adminService } from '@/services/admin.service';

interface Rubric {
  id: number;
  name: string;
  job_id: number | null;
  version: number;
  status: string;
  skills_count: number;
  applications: number;
  updated_at: string | null;
}

interface RubricStats {
  total: number;
  active: number;
  draft: number;
}

export default function AdminRubricsPage() {
  const navigate = useNavigate();
  const [rubrics, setRubrics] = useState<Rubric[]>([]);
  const [stats, setStats] = useState<RubricStats>({ total: 0, active: 0, draft: 0 });
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [viewing, setViewing] = useState<Rubric | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminService.getRubrics();
      setRubrics(data.rubrics);
      setStats(data.stats);
    } catch (err) {
      console.error('Rubrics load error:', err);
      customToast({ type: 'error', title: 'Rubrics', message: 'Failed to load rubrics.' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const filtered = rubrics.filter(r =>
    r.name.toLowerCase().includes(search.toLowerCase())
  );

  const getJobLabel = (jobId: number | null) => {
    if (!jobId) return 'Standalone';
    return `Job #${jobId}`;
  };

  const statusVariant = (status: string) => {
    if (status === 'active') return 'success';
    if (status === 'draft') return 'warning';
    return 'default';
  };

  const handleView = async (r: Rubric) => {
    try {
      const detail = await adminService.getRubric(r.id);
      setViewing({ ...r, skills_count: detail.skills_count });
    } catch (err: any) {
      customToast({ type: 'error', title: 'View Failed', message: err?.message || 'Could not load rubric.' });
    }
  };

  const handleDelete = async (r: Rubric) => {
    if (!confirm(`Delete rubric "${r.name}"?`)) return;
    try {
      await adminService.deleteRubric(r.id);
      setRubrics(prev => prev.filter(x => x.id !== r.id));
      setStats(prev => ({ ...prev, total: prev.total - 1, [r.status === 'active' ? 'active' : 'draft']: prev[r.status === 'active' ? 'active' : 'draft'] - 1 }));
      customToast({ type: 'warning', title: 'Deleted', message: 'Rubric removed.' });
    } catch (err: any) {
      customToast({ type: 'error', title: 'Delete Failed', message: err?.message || 'Could not delete rubric.' });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs font-bold text-slate-400 mb-3">
            <span className="text-indigo-600">Rubrics</span>
          </div>
          <h1 className="text-2xl font-black text-gray-900 dark:text-white tracking-tight">Rubric Management</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Manage skill rubrics for all your open roles.</p>
        </div>
        <Button variant="primary" leftIcon={<Plus className="h-4 w-4" />} onClick={() => navigate('/admin/rubric-builder')}>
          New Rubric
        </Button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {[
          { label: 'Total Rubrics', value: stats.total, icon: FileText, color: 'bg-violet-50 text-violet-600 dark:bg-violet-500/10 dark:text-violet-400' },
          { label: 'Active', value: stats.active, icon: CheckCircle2, color: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400' },
          { label: 'Drafts', value: stats.draft, icon: Clock, color: 'bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400' },
        ].map((stat) => (
          <Card key={stat.label} className="glass-panel border-purple-200/50 dark:border-purple-500/20">
            <CardContent className="p-5">
              <div className="flex justify-between items-start mb-3">
                <div className={`text-xs font-black uppercase tracking-widest ${stat.color.split(' ')[1]}`}>{stat.label}</div>
                <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${stat.color}`}>
                  <stat.icon className="h-4 w-4" />
                </div>
              </div>
              <div className="text-3xl font-black text-gray-900 dark:text-white tracking-tighter">{stat.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="flex gap-2 p-1 bg-slate-100 dark:bg-white/5 rounded-lg">
        <Input
          placeholder="Search by rubric name..."
          leftIcon={<Search className="h-4 w-4" />}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          wrapperClassName="border-0 bg-transparent shadow-none focus:ring-0"
          className="border-0 bg-transparent shadow-none focus:ring-0"
        />
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center gap-3 py-24">
          <div className="h-10 w-10 animate-spin rounded-full border-2 border-purple-600 border-t-transparent" />
          <span className="text-sm text-gray-500">Loading rubrics...</span>
        </div>
      ) : (
        <Card className="glass-panel border-purple-200/50">
          <CardHeader>
            <CardTitle>Rubric Library</CardTitle>
            <CardDescription>{filtered.length} of {rubrics.length} rubrics</CardDescription>
          </CardHeader>
          <CardContent>
            {filtered.length === 0 ? (
              <div className="text-center py-16">
                <FileText className="h-12 w-12 mx-auto text-slate-300 mb-4" />
                <h3 className="text-base font-black text-slate-700 mb-1">No rubrics match your filters</h3>
                <p className="text-sm text-slate-400">Try a different search or filter.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead>
                    <tr className="border-b border-purple-100 dark:border-white/10">
                      <th className="py-3 text-xs font-bold text-gray-500 uppercase">Rubric</th>
                      <th className="py-3 text-xs font-bold text-gray-500 uppercase">Status</th>
                      <th className="py-3 text-xs font-bold text-gray-500 uppercase">Version</th>
                      <th className="py-3 text-xs font-bold text-gray-500 uppercase">Criteria</th>
                      <th className="py-3 text-xs font-bold text-gray-500 uppercase">Updated</th>
                      <th className="py-3 text-xs font-bold text-gray-500 uppercase text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((r) => (
                      <tr key={r.id} className="border-b border-gray-50 dark:border-white/[0.02] hover:bg-purple-50/50 dark:hover:bg-white/[0.02] transition-colors">
                        <td className="py-3">
                          <div className="text-sm font-extrabold text-gray-900 dark:text-white">{r.name}</div>
                          <div className="text-xs text-gray-500">{getJobLabel(r.job_id)}</div>
                        </td>
                        <td className="py-3">
                          <Badge variant={statusVariant(r.status) === 'success' ? 'success' : statusVariant(r.status) === 'warning' ? 'warning' : 'default'} size="sm" dot>
                            {r.status}
                          </Badge>
                        </td>
                        <td className="py-3 text-sm font-medium text-gray-500">v{r.version}</td>
                        <td className="py-3 text-sm font-medium text-gray-500">{r.skills_count}</td>
                        <td className="py-3 text-sm text-gray-500 font-medium">
                          {r.updated_at ? new Date(r.updated_at).toLocaleDateString() : '—'}
                        </td>
                        <td className="py-3 text-right">
                          <SimpleDropdown
                            trigger={<button className="p-2 rounded-lg hover:bg-purple-100 dark:hover:bg-white/10 transition-colors"><MoreHorizontal className="h-4 w-4 text-gray-500" /></button>}
                            items={[
                              { label: 'View', icon: <Eye className="h-4 w-4 text-purple-500" />, onClick: () => handleView(r) },
                              { label: 'Edit', icon: <Plus className="h-4 w-4 text-amber-500" />, onClick: () => navigate('/admin/rubric-builder') },
                              { label: 'Delete', icon: <XCircle className="h-4 w-4 text-red-500" />, onClick: () => handleDelete(r) },
                            ]}
                            align="end"
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Dialog open={!!viewing} onOpenChange={(open) => { if (!open) setViewing(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="text-purple-900 dark:text-white">{viewing?.name || 'Rubric'}</DialogTitle>
            <DialogDescription>{getJobLabel(viewing?.job_id ?? null)} &bull; v{viewing?.version} &bull; {viewing?.status}</DialogDescription>
          </DialogHeader>
          <div className="my-4 space-y-3">
            <div className="flex items-center justify-between p-4 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10">
              <div>
                <div className="text-sm font-medium text-gray-500">Criteria</div>
                <div className="text-2xl font-black text-gray-900 dark:text-white">{viewing?.skills_count ?? 0}</div>
              </div>
              <FileText className="h-6 w-6 text-purple-500" />
            </div>
            <div className="flex items-center justify-between p-4 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10">
              <div>
                <div className="text-sm font-medium text-gray-500">Last updated</div>
                <div className="text-base font-bold text-gray-900 dark:text-white">{viewing?.updated_at ? new Date(viewing.updated_at).toLocaleDateString() : '—'}</div>
              </div>
              <Clock className="h-5 w-5 text-gray-400" />
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
