// ============================================================
// Admin System Announcements - Candway
// Real data from /admin/announcements API
// ============================================================

import { useCallback, useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/shared/components/ui/dialog';
import { customToast } from '@/shared/components/ui/toast';
import { cn } from '@/utils/cn';
import { Bell, Plus, Calendar, Clock, Edit3, Archive, Search, RefreshCw } from 'lucide-react';
import { adminService } from '@/services/admin.service';

interface Announcement {
  id: number;
  title: string;
  message: string;
  type: string;
  target_role: string;
  is_active: boolean;
  created_at: string;
  expires_at?: string;
}

const audienceOptions = [
  { value: 'all', label: 'All Users' },
  { value: 'recruiters', label: 'Recruiters' },
  { value: 'candidates', label: 'Candidates' },
  { value: 'mentors', label: 'Mentors' },
];

const typeOptions = [
  { value: 'info', label: 'Info' },
  { value: 'warning', label: 'Warning' },
  { value: 'success', label: 'Success' },
  { value: 'urgent', label: 'Urgent' },
];

const audienceBadgeVariant: Record<string, 'primary' | 'info' | 'success' | 'warning' | 'default'> = {
  all: 'primary',
  recruiters: 'info',
  candidates: 'success',
  mentors: 'warning',
};

export default function AnnouncementsPage() {
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [editing, setEditing] = useState<Announcement | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [form, setForm] = useState({
    title: '', message: '', type: 'info', target_role: 'all', expires_at: ''
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data: any = await adminService.getAnnouncements();
      setAnnouncements(data.announcements || []);
    } catch (err) {
      console.error('Announcements load error:', err);
      customToast({ type: 'error', title: 'Announcements', message: 'Failed to load announcements.' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const filtered = announcements.filter(a =>
    a.title?.toLowerCase().includes(search.toLowerCase()) ||
    (a.message || '').toLowerCase().includes(search.toLowerCase())
  );

  const handleCreate = async () => {
    if (!form.title.trim() || !form.message.trim()) {
      customToast({ type: 'error', title: 'Validation Error', message: 'Title and content are required.' });
      return;
    }
    try {
      if (editing) {
        await adminService.updateAnnouncement(editing.id, form);
        customToast({ type: 'success', title: 'Announcement Updated', message: 'Changes saved.' });
      } else {
        await adminService.createAnnouncement(form);
        customToast({ type: 'success', title: 'Announcement Created', message: 'Announcement has been broadcast.' });
      }
      setIsAddOpen(false);
      setEditing(null);
      setForm({ title: '', message: '', type: 'info', target_role: 'all', expires_at: '' });
      load();
    } catch (err: any) {
      customToast({ type: 'error', title: 'Failed', message: err?.message || 'Could not save announcement.' });
    }
  };

  const handleEdit = (ann: Announcement) => {
    setEditing(ann);
    setForm({
      title: ann.title || '',
      message: ann.message || '',
      type: ann.type || 'info',
      target_role: ann.target_role || 'all',
      expires_at: ann.expires_at ? ann.expires_at.slice(0, 10) : '',
    });
    setIsAddOpen(true);
  };

  const handleArchive = async (ann: Announcement) => {
    setBusyId(ann.id);
    try {
      const res = await adminService.archiveAnnouncement(ann.id);
      setAnnouncements(prev => prev.map(a => a.id === ann.id ? { ...a, is_active: res.is_active } : a));
      customToast({ type: 'warning', title: res.is_active ? 'Restored' : 'Archived', message: res.is_active ? 'Announcement is now active.' : 'Announcement archived.' });
    } catch (err: any) {
      customToast({ type: 'error', title: 'Archive Failed', message: err?.message || 'Could not archive announcement.' });
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">System Announcements</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Create and manage platform-wide communications for all user segments</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" leftIcon={<RefreshCw className="h-4 w-4" />} onClick={load}>Refresh</Button>
          <Button variant="primary" leftIcon={<Plus className="h-4 w-4" />} onClick={() => setIsAddOpen(true)} className="font-bold shadow-md shadow-purple-500/25">New Announcement</Button>
        </div>
      </div>

      <Card className="glass-panel border-purple-200/50">
        <CardHeader>
          <div className="flex items-center justify-between w-full">
            <div>
              <CardTitle>All Announcements</CardTitle>
              <CardDescription>{announcements.filter(a => a.is_active).length} active, {announcements.filter(a => !a.is_active).length} inactive</CardDescription>
            </div>
            <Input placeholder="Search announcements..." leftIcon={<Search className="h-4 w-4" />} value={search} onChange={(e) => setSearch(e.target.value)} wrapperClassName="w-64" />
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="py-16 text-center text-gray-400">Loading announcements...</div>
          ) : (
            <div className="space-y-3">
              {filtered.map((ann, i) => (
                <motion.div
                  key={ann.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3, delay: i * 0.03 }}
                  className="flex items-start gap-4 p-4 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10 hover:shadow-sm transition-all"
                >
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-purple-100 dark:bg-purple-900/50">
                    <Bell className="h-5 w-5 text-purple-600 dark:text-purple-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="text-sm font-extrabold text-gray-900 dark:text-white">{ann.title}</h3>
                      <Badge variant={audienceBadgeVariant[ann.target_role || 'all']} size="sm" className="capitalize">
                        {audienceOptions.find(o => o.value === (ann.target_role || 'all'))?.label || 'All Users'}
                      </Badge>
                      <Badge variant={ann.is_active ? 'success' : 'default'} size="sm" dot>{ann.is_active ? 'published' : 'inactive'}</Badge>
                      <Badge variant="default" size="sm">{typeOptions.find(o => o.value === ann.type)?.label || ann.type}</Badge>
                    </div>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 line-clamp-2">{ann.message}</p>
                    <div className="flex items-center gap-4 mt-2 text-xs text-gray-400">
                      <span className="flex items-center gap-1"><Calendar className="h-3 w-3" />{ann.created_at ? new Date(ann.created_at).toLocaleDateString() : '—'}</span>
                      {ann.expires_at && <span className="flex items-center gap-1"><Clock className="h-3 w-3" />Expires: {new Date(ann.expires_at).toLocaleDateString()}</span>}
                    </div>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <Button variant="ghost" size="xs" leftIcon={<Edit3 className="h-3.5 w-3.5 text-amber-500" />} onClick={() => handleEdit(ann)} />
                    <Button variant="ghost" size="xs" disabled={busyId === ann.id} leftIcon={<Archive className="h-3.5 w-3.5 text-red-500" />} onClick={() => handleArchive(ann)} />
                  </div>
                </motion.div>
              ))}
              {filtered.length === 0 && !loading && (
                <div className="text-center py-10 text-sm text-gray-400">No announcements match your search.</div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={isAddOpen} onOpenChange={(open) => { setIsAddOpen(open); if (!open) setEditing(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="text-purple-900 dark:text-white">{editing ? 'Edit Announcement' : 'New System Announcement'}</DialogTitle>
            <DialogDescription>{editing ? 'Update this announcement.' : 'Create a platform-wide or targeted announcement for specific user segments.'}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 my-4">
            <Input label="Announcement Title" placeholder="e.g. Platform Maintenance Notice" value={form.title} onChange={(e) => setForm(f => ({ ...f, title: e.target.value }))} />
            <div>
              <label className="block text-sm font-bold text-gray-700 dark:text-gray-300 mb-1.5">Content</label>
              <textarea className="w-full rounded-xl border border-purple-200/60 bg-white/70 p-3 text-sm min-h-[100px] focus:ring-2 focus:ring-purple-500/20 dark:border-white/10 dark:bg-white/5 dark:text-white" placeholder="Write your announcement content..." value={form.message} onChange={(e) => setForm(f => ({ ...f, message: e.target.value }))} />
            </div>
            <div>
              <label className="block text-sm font-bold text-gray-700 dark:text-gray-300 mb-1.5">Type</label>
              <div className="flex gap-2 flex-wrap">
                {typeOptions.map(o => (
                  <button key={o.value} onClick={() => setForm(f => ({ ...f, type: o.value }))} className={`${form.type === o.value ? 'bg-purple-600 text-white border-purple-600' : 'bg-white/60 dark:bg-white/5 border-purple-200/60 dark:border-white/10 text-gray-600 dark:text-gray-400'} px-3 py-2 text-xs font-bold rounded-xl border transition-colors capitalize`}>
                    {o.label}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm font-bold text-gray-700 dark:text-gray-300 mb-1.5">Target Audience</label>
              <div className="flex gap-2 flex-wrap">
                {audienceOptions.map(o => (
                  <button key={o.value} onClick={() => setForm(f => ({ ...f, target_role: o.value }))} className={cn('px-3 py-2 text-xs font-bold rounded-xl border transition-colors capitalize', form.target_role === o.value ? 'bg-purple-600 text-white border-purple-600' : 'bg-white/60 dark:bg-white/5 border-purple-200/60 dark:border-white/10 text-gray-600 dark:text-gray-400 hover:border-purple-400')}>
                    {o.label}
                  </button>
                ))}
              </div>
            </div>
            <Input label="Expires At (optional)" type="text" placeholder="e.g. 2026-08-01" value={form.expires_at} onChange={(e) => setForm(f => ({ ...f, expires_at: e.target.value }))} />
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => { setIsAddOpen(false); setEditing(null); }}>Cancel</Button>
            <Button variant="primary" onClick={handleCreate}>{editing ? 'Save Changes' : 'Create Announcement'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
