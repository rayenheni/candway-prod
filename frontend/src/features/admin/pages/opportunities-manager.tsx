// ============================================================
// Admin Opportunities Manager - Candway Tunisia
// Real data from /admin/opportunities API
// ============================================================

import { useCallback, useEffect, useState } from 'react';
import { Card } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/shared/components/ui/dialog';
import { customToast } from '@/shared/components/ui/toast';
import { Search, Plus, Edit3, Trash2, RefreshCw, ExternalLink } from 'lucide-react';
import { adminService } from '@/services/admin.service';

interface Opportunity {
  id: number;
  title: string;
  type: string;
  description: string;
  link: string;
  image_url: string | null;
  is_active: boolean;
  created_at: string;
}

export default function OpportunitiesManagerPage() {
  const [opps, setOpps] = useState<Opportunity[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [editing, setEditing] = useState<Opportunity | null>(null);
  const [form, setForm] = useState({
    title: '', type: 'Scholarship', description: '', link: '', image_url: ''
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data: any = await adminService.getOpportunities();
      setOpps(data.opportunities || []);
    } catch (err) {
      console.error('Opportunities load error:', err);
      customToast({ type: 'error', title: 'Opportunities', message: 'Failed to load opportunities.' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleSave = async () => {
    if (!form.title || !form.link) {
      customToast({ type: 'warning', title: 'Validation', message: 'Title and Link are required.' });
      return;
    }
    try {
      if (editing) {
        await adminService.updateOpportunity(editing.id, form);
        customToast({ type: 'success', title: 'Opportunity Updated', message: 'Opportunity changes saved.' });
      } else {
        await adminService.createOpportunity(form);
        customToast({ type: 'success', title: 'Opportunity Created', message: 'New opportunity has been deployed.' });
      }
      setIsAddOpen(false);
      setEditing(null);
      setForm({ title: '', type: 'Scholarship', description: '', link: '', image_url: '' });
      load();
    } catch (err: any) {
      customToast({ type: 'error', title: editing ? 'Update Failed' : 'Create Failed', message: err?.message || 'Could not save opportunity.' });
    }
  };

  const handleEdit = (opp: Opportunity) => {
    setEditing(opp);
    setForm({
      title: opp.title || '',
      type: opp.type || 'Scholarship',
      description: opp.description || '',
      link: opp.link || '',
      image_url: opp.image_url || '',
    });
    setIsAddOpen(true);
  };

  const handleDelete = async (opp: Opportunity) => {
    if (!confirm(`Remove "${opp.title}"?`)) return;
    try {
      await adminService.deleteOpportunity(opp.id);
        setOpps(o => o.filter(x => x.id !== opp.id));
      customToast({ type: 'warning', title: 'Deleted', message: 'Opportunity removed.' });
    } catch (err: any) {
      customToast({ type: 'error', title: 'Delete Failed', message: err?.message || 'Could not delete.' });
    }
  };

  const filtered = opps.filter(o =>
    o.title.toLowerCase().includes(search.toLowerCase()) ||
    o.type.toLowerCase().includes(search.toLowerCase())
  );

  const typeVariant = (type: string) => {
    const map: Record<string, 'primary' | 'info' | 'success' | 'warning' | 'default'> = {
      Scholarship: 'primary',
      Grant: 'info',
      Event: 'success',
      Hackathon: 'warning',
    };
    return map[type] || 'default';
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">Opportunities Manager</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Manage competitions, grants, and mentorship programs</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" leftIcon={<RefreshCw className="h-4 w-4" />} onClick={load}>Refresh</Button>
          <Button variant="primary" size="sm" leftIcon={<Plus className="h-4 w-4" />} onClick={() => setIsAddOpen(true)}>
            New Opportunity
          </Button>
        </div>
      </div>

      <Input placeholder="Search opportunities..." leftIcon={<Search className="h-4 w-4" />} value={search} onChange={(e) => setSearch(e.target.value)} />

      {loading ? (
        <div className="flex flex-col items-center justify-center gap-3 py-16">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-purple-600 border-t-transparent" />
          <span className="text-sm text-gray-500">Loading opportunities...</span>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filtered.map(o => (
            <Card key={o.id} hoverable className="p-5">
              <div className="flex items-center justify-between mb-3">
                <Badge variant={typeVariant(o.type)} size="sm">{o.type}</Badge>
                <Badge variant={o.is_active ? 'success' : 'default'} size="sm" dot>{o.is_active ? 'active' : 'inactive'}</Badge>
              </div>
              <h3 className="text-base font-extrabold text-gray-900 dark:text-white">{o.title || '—'}</h3>
              {o.description && <p className="text-sm text-gray-500 mt-2 line-clamp-2">{o.description}</p>}
              <div className="flex items-center gap-4 mt-3 text-xs text-gray-500">
                <span className="flex items-center gap-1 font-medium">
                  <ExternalLink className="h-3 w-3 text-indigo-500" />
                  {o.link ? (
                    <a href={o.link} target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:text-indigo-800 truncate max-w-xs">
                      {o.link}
                    </a>
                  ) : 'No link set'}
                </span>
                <span className="font-bold text-purple-600">{o.created_at ? new Date(o.created_at).toLocaleDateString() : '—'}</span>
              </div>
              <div className="flex gap-2 mt-4 pt-3 border-t border-purple-100/60">
                <Button variant="ghost" size="xs" leftIcon={<Edit3 className="h-3.5 w-3.5" />} onClick={() => handleEdit(o)}>Edit</Button>
                <Button variant="ghost" size="xs" leftIcon={<Trash2 className="h-3.5 w-3.5 text-red-500" />} onClick={() => handleDelete(o)}>Delete</Button>
              </div>
            </Card>
          ))}
          {filtered.length === 0 && !loading && (
            <div className="col-span-full text-center py-16 text-gray-400">
              No opportunities match your search.
            </div>
          )}
        </div>
      )}

      <Dialog open={isAddOpen} onOpenChange={(open) => { setIsAddOpen(open); if (!open) setEditing(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? 'Edit Opportunity' : 'Create New Opportunity'}</DialogTitle>
            <DialogDescription>{editing ? 'Update the opportunity details.' : 'Add a new scholarship, grant, or event to the platform.'}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 my-4">
            <Input label="Title" placeholder="Opportunity name" value={form.title} onChange={(e) => setForm(f => ({ ...f, title: e.target.value }))} />
            <Input label="Type" placeholder="Scholarship / Grant / Event / Hackathon" value={form.type} onChange={(e) => setForm(f => ({ ...f, type: e.target.value }))} />
            <Input label="External URL" placeholder="https://..." value={form.link} onChange={(e) => setForm(f => ({ ...f, link: e.target.value }))} />
            <Input label="Thumbnail URL" placeholder="https://..." value={form.image_url} onChange={(e) => setForm(f => ({ ...f, image_url: e.target.value }))} />
            <textarea
              className="w-full rounded-xl border border-purple-200/60 bg-white/70 p-3 text-sm focus:ring-2 focus:ring-purple-500/20 dark:border-white/10 dark:bg-white/5 dark:text-white"
              rows={4}
              placeholder="Description..."
              value={form.description}
              onChange={(e) => setForm(f => ({ ...f, description: e.target.value }))}
            />
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => { setIsAddOpen(false); setEditing(null); }}>Cancel</Button>
            <Button variant="primary" onClick={handleSave}>{editing ? 'Save Changes' : 'Deploy Opportunity'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
