// ============================================================
// Admin Organizations Management - Candway
// Real data from /admin/organizations API
// ============================================================

import { useCallback, useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/shared/components/ui/select';
import { ConfirmDialog } from '@/shared/components/ui/dialog';
import { customToast } from '@/shared/components/ui/toast';
import {
  Building2,
  Users,
  Briefcase,
  FileText,
  Search,
  RefreshCw,
  Plus,
  Pencil,
  Trash2,
  Power,
  Database,
  ChevronLeft,
  ChevronRight,
  History,
} from 'lucide-react';
import { adminService, Organization } from '@/services/admin.service';

const TIER_STYLES: Record<string, string> = {
  free: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  starter: 'bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300',
  pro: 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300',
  enterprise: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
};

const EMPTY_FORM = {
  name: '',
  slug: '',
  domain: '',
  tier: 'free',
  max_users: 10,
  max_jobs: 50,
  max_ai_interviews: 500,
};

export default function OrganizationsPage() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [perPage] = useState(15);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [tierFilter, setTierFilter] = useState<'all' | 'free' | 'starter' | 'pro' | 'enterprise'>('all');
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Organization | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [auditFor, setAuditFor] = useState<Organization | null>(null);
  const [auditLogs, setAuditLogs] = useState<unknown[]>([]);
  const [auditLoading, setAuditLoading] = useState(false);
  const [deleteFor, setDeleteFor] = useState<Organization | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminService.getOrganizations({
        search: search || undefined,
        status: statusFilter,
        tier: tierFilter === 'all' ? undefined : tierFilter,
        page,
        per_page: perPage,
      });
      setOrganizations(data.organizations || []);
      setTotal(data.total || 0);
      setTotalPages(data.total_pages || 1);
    } catch (err) {
      console.error('Organizations load error:', err);
      customToast({ type: 'error', title: 'Organizations', message: 'Failed to load organizations.' });
    } finally {
      setLoading(false);
    }
  }, [search, statusFilter, tierFilter, page, perPage]);

  useEffect(() => { load(); }, [load]);

  const openCreate = () => {
    setEditing(null);
    setForm(EMPTY_FORM);
    setModalOpen(true);
  };

  const openEdit = (org: Organization) => {
    setEditing(org);
    setForm({
      name: org.name,
      slug: org.slug,
      domain: org.domain || '',
      tier: org.tier,
      max_users: org.max_users,
      max_jobs: org.max_jobs,
      max_ai_interviews: org.max_ai_interviews,
    });
    setModalOpen(true);
  };

  const save = async () => {
    if (!form.name.trim()) {
      customToast({ type: 'error', title: 'Organization', message: 'Name is required.' });
      return;
    }
    setSaving(true);
    try {
      if (editing) {
        await adminService.updateOrganization(editing.id, form);
        customToast({ type: 'success', title: 'Organization', message: 'Organization updated.' });
      } else {
        await adminService.createOrganization(form);
        customToast({ type: 'success', title: 'Organization', message: 'Organization created.' });
      }
      setModalOpen(false);
      load();
    } catch (err: any) {
      console.error('Save organization error:', err);
      customToast({ type: 'error', title: 'Organization', message: err?.message || 'Failed to save organization.' });
    } finally {
      setSaving(false);
    }
  };

  const toggle = async (org: Organization) => {
    try {
      const res = await adminService.toggleOrganization(org.id);
      customToast({
        type: 'success',
        title: 'Organization',
        message: res.is_active ? 'Organization activated.' : 'Organization deactivated.',
      });
      load();
    } catch (err: any) {
      console.error('Toggle organization error:', err);
      customToast({ type: 'error', title: 'Organization', message: err?.message || 'Failed to update organization.' });
    }
  };

  const remove = async (org: Organization) => {
    setDeleteFor(org);
  };

  const confirmRemove = async () => {
    if (!deleteFor) return;
    try {
      await adminService.deleteOrganization(deleteFor.id);
      customToast({ type: 'success', title: 'Organization', message: 'Organization deleted.' });
      setDeleteFor(null);
      load();
    } catch (err: any) {
      console.error('Delete organization error:', err);
      customToast({ type: 'error', title: 'Organization', message: err?.message || 'Failed to delete organization.' });
      setDeleteFor(null);
    }
  };

  const openAudit = async (org: Organization) => {
    setAuditFor(org);
    setAuditLoading(true);
    try {
      const data = await adminService.getOrganizationAudit(org.id);
      setAuditLogs(data.logs || []);
    } catch (err) {
      console.error('Audit load error:', err);
      setAuditLogs([]);
    } finally {
      setAuditLoading(false);
    }
  };

  const activeCount = organizations.filter(o => o.is_active).length;
  const totalRecruiters = organizations.reduce((sum, o) => sum + o.recruiter_count, 0);
  const totalJobs = organizations.reduce((sum, o) => sum + o.jobs_count, 0);

  const stats = [
    { label: 'Organizations', value: total, icon: Building2, color: 'text-purple-600', bg: 'bg-purple-100 dark:bg-purple-900/30' },
    { label: 'Active', value: activeCount, icon: Power, color: 'text-emerald-600', bg: 'bg-emerald-100 dark:bg-emerald-900/30' },
    { label: 'Recruiters', value: totalRecruiters, icon: Users, color: 'text-blue-600', bg: 'bg-blue-100 dark:bg-blue-900/30' },
    { label: 'Total Jobs', value: totalJobs, icon: Briefcase, color: 'text-amber-600', bg: 'bg-amber-100 dark:bg-amber-900/30' },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">Organizations</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Manage companies, tenants, quotas and subscription state</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" leftIcon={<RefreshCw className="h-4 w-4" />} onClick={load}>Refresh</Button>
          <Button variant="primary" size="sm" leftIcon={<Plus className="h-4 w-4" />} onClick={openCreate}>New Organization</Button>
        </div>
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
              <div className="text-2xl font-black text-gray-900 dark:text-white tracking-tighter">{stat.value.toLocaleString()}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="flex flex-wrap gap-2 p-1 bg-slate-100 dark:bg-white/5 rounded-lg">
        <Input
          placeholder="Search by name, slug, or domain..."
          leftIcon={<Search className="h-4 w-4" />}
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          wrapperClassName="w-full sm:w-64"
        />
        <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v as any); setPage(1); }}>
          <SelectTrigger className="w-32">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="inactive">Inactive</SelectItem>
          </SelectContent>
        </Select>
        <Select value={tierFilter} onValueChange={(v) => { setTierFilter(v as any); setPage(1); }}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="Tier" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All tiers</SelectItem>
            <SelectItem value="free">Free</SelectItem>
            <SelectItem value="starter">Starter</SelectItem>
            <SelectItem value="pro">Pro</SelectItem>
            <SelectItem value="enterprise">Enterprise</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <Card className="glass-panel border-purple-200/50">
        <CardHeader>
          <CardTitle>All Organizations ({total})</CardTitle>
          <CardDescription>Recruiter counts, job counts and storage are computed live from platform data</CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex flex-col items-center justify-center gap-3 py-16">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-purple-600 border-t-transparent" />
              <span className="text-sm text-gray-500">Loading organizations...</span>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-purple-100 dark:border-white/10">
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Organization</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Tier</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Status</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Recruiters</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Jobs</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Applications</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Storage</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {organizations.map(org => (
                    <tr key={org.id} className="border-b border-gray-50 dark:border-white/[0.02] hover:bg-purple-50/50 transition-colors">
                      <td className="py-3">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-lg bg-purple-100 dark:bg-purple-900/40 flex items-center justify-center">
                            <Building2 className="h-4 w-4 text-purple-600" />
                          </div>
                          <div>
                            <div className="text-sm font-extrabold text-gray-900 dark:text-white">{org.name}</div>
                            <div className="text-xs text-gray-500">{org.slug}{org.domain ? ` · ${org.domain}` : ''}</div>
                          </div>
                        </div>
                      </td>
                      <td className="py-3">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${TIER_STYLES[org.tier] || TIER_STYLES.free}`}>
                          {org.tier}
                        </span>
                      </td>
                      <td className="py-3">
                        <Badge variant={org.is_active ? 'success' : 'default'} size="sm" dot>{org.is_active ? 'active' : 'inactive'}</Badge>
                      </td>
                      <td className="py-3">
                        <div className="flex items-center gap-1.5 text-sm font-semibold text-gray-700 dark:text-gray-300">
                          <Users className="h-3.5 w-3.5 text-blue-500" />
                          {org.recruiter_count}
                          <span className="text-xs text-gray-400">/ {org.max_users}</span>
                        </div>
                      </td>
                      <td className="py-3">
                        <div className="flex items-center gap-1.5 text-sm font-semibold text-gray-700 dark:text-gray-300">
                          <Briefcase className="h-3.5 w-3.5 text-amber-500" />
                          {org.jobs_count}
                          <span className="text-xs text-gray-400">/ {org.max_jobs}</span>
                        </div>
                      </td>
                      <td className="py-3 text-sm font-medium text-gray-500">
                        <div className="flex items-center gap-1.5">
                          <FileText className="h-3.5 w-3.5 text-gray-400" />
                          {org.applications_count}
                        </div>
                      </td>
                      <td className="py-3 text-sm font-medium text-gray-500">
                        <div className="flex items-center gap-1.5">
                          <Database className="h-3.5 w-3.5 text-gray-400" />
                          {org.storage?.formatted || '0 B'}
                        </div>
                      </td>
                      <td className="py-3 text-right">
                        <div className="flex items-center justify-end gap-0.5">
                          <Button variant="ghost" size="xs" leftIcon={<History className="h-3.5 w-3.5 text-gray-400" />} onClick={() => openAudit(org)} />
                          <Button variant="ghost" size="xs" leftIcon={<Pencil className="h-3.5 w-3.5 text-blue-500" />} onClick={() => openEdit(org)} />
                          <Button variant="ghost" size="xs" leftIcon={<Power className={`h-3.5 w-3.5 ${org.is_active ? 'text-amber-500' : 'text-emerald-500'}`} />} onClick={() => toggle(org)} />
                          <Button variant="ghost" size="xs" leftIcon={<Trash2 className="h-3.5 w-3.5 text-red-500" />} onClick={() => remove(org)} />
                        </div>
                      </td>
                    </tr>
                  ))}
                  {organizations.length === 0 && !loading && <tr><td colSpan={8} className="py-10 text-center text-gray-400">No organizations found.</td></tr>}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-500">Page {page} of {totalPages}</span>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" leftIcon={<ChevronLeft className="h-4 w-4" />} disabled={page <= 1} onClick={() => setPage(p => Math.max(1, p - 1))}>Previous</Button>
            <Button variant="outline" size="sm" rightIcon={<ChevronRight className="h-4 w-4" />} disabled={page >= totalPages} onClick={() => setPage(p => Math.min(totalPages, p + 1))}>Next</Button>
          </div>
        </div>
      )}

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={() => !saving && setModalOpen(false)}>
          <div className="w-full max-w-lg rounded-2xl bg-white dark:bg-slate-900 p-6 shadow-2xl" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-extrabold text-gray-900 dark:text-white mb-4">
              {editing ? 'Edit Organization' : 'New Organization'}
            </h3>
            <div className="space-y-4">
              <div>
                <label className="text-xs font-bold text-gray-600 dark:text-gray-400 uppercase tracking-wide">Name *</label>
                <Input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Acme Corp" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-bold text-gray-600 dark:text-gray-400 uppercase tracking-wide">Slug</label>
                  <Input value={form.slug} onChange={e => setForm({ ...form, slug: e.target.value })} placeholder="acme-corp" />
                </div>
                <div>
                  <label className="text-xs font-bold text-gray-600 dark:text-gray-400 uppercase tracking-wide">Domain</label>
                  <Input value={form.domain} onChange={e => setForm({ ...form, domain: e.target.value })} placeholder="acme.com" />
                </div>
              </div>
              <div>
                <label className="text-xs font-bold text-gray-600 dark:text-gray-400 uppercase tracking-wide">Tier</label>
                <Select value={form.tier} onValueChange={(v) => setForm({ ...form, tier: v })}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Tier" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="free">Free</SelectItem>
                    <SelectItem value="starter">Starter</SelectItem>
                    <SelectItem value="pro">Pro</SelectItem>
                    <SelectItem value="enterprise">Enterprise</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="text-xs font-bold text-gray-600 dark:text-gray-400 uppercase tracking-wide">Max Users</label>
                  <Input type="number" value={form.max_users} onChange={e => setForm({ ...form, max_users: Number(e.target.value) })} />
                </div>
                <div>
                  <label className="text-xs font-bold text-gray-600 dark:text-gray-400 uppercase tracking-wide">Max Jobs</label>
                  <Input type="number" value={form.max_jobs} onChange={e => setForm({ ...form, max_jobs: Number(e.target.value) })} />
                </div>
                <div>
                  <label className="text-xs font-bold text-gray-600 dark:text-gray-400 uppercase tracking-wide">Max AI Interviews</label>
                  <Input type="number" value={form.max_ai_interviews} onChange={e => setForm({ ...form, max_ai_interviews: Number(e.target.value) })} />
                </div>
              </div>
            </div>
            <div className="flex items-center justify-end gap-2 mt-6">
              <Button variant="outline" size="sm" onClick={() => setModalOpen(false)} disabled={saving}>Cancel</Button>
              <Button variant="primary" size="sm" onClick={save} disabled={saving}>{saving ? 'Saving...' : editing ? 'Save Changes' : 'Create'}</Button>
            </div>
          </div>
        </div>
      )}

      {auditFor && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={() => setAuditFor(null)}>
          <div className="w-full max-w-2xl max-h-[80vh] overflow-y-auto rounded-2xl bg-white dark:bg-slate-900 p-6 shadow-2xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-extrabold text-gray-900 dark:text-white">Audit Trail — {auditFor.name}</h3>
              <Button variant="ghost" size="xs" onClick={() => setAuditFor(null)}>Close</Button>
            </div>
            {auditLoading ? (
              <div className="flex justify-center py-10">
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-purple-600 border-t-transparent" />
              </div>
            ) : auditLogs.length === 0 ? (
              <p className="py-10 text-center text-gray-400">No audit events for this organization yet.</p>
            ) : (
              <div className="space-y-3">
                {(auditLogs as any[]).map((log: any) => (
                  <div key={log.id} className="flex items-start gap-3 rounded-lg bg-slate-50 dark:bg-white/5 p-3">
                    <div className="w-2 h-2 mt-1.5 rounded-full bg-purple-500 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-bold text-gray-800 dark:text-gray-200">{log.action}</div>
                      <div className="text-xs text-gray-500 break-words">{log.details}</div>
                    </div>
                    <div className="text-xs text-gray-400 whitespace-nowrap">
                      {log.created_at}
                      {log.user_id ? ` · user #${log.user_id}` : ''}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      <ConfirmDialog
        open={deleteFor !== null}
        onOpenChange={(open) => { if (!open) setDeleteFor(null); }}
        title={`Delete "${deleteFor?.name ?? ''}"?`}
        description="This is a soft delete and can be restored via the database."
        confirmLabel="Delete"
        cancelLabel="Cancel"
        variant="danger"
        onConfirm={confirmRemove}
      />
    </div>
  );
}
