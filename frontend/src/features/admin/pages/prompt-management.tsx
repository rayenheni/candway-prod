// ============================================================
// Admin AI Prompt Management - Candway
// Real data from /admin/prompts API
// ============================================================

import { useCallback, useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { Input } from '@/shared/components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/shared/components/ui/dialog';
import { customToast } from '@/shared/components/ui/toast';
import { Search, Plus, Edit3, Copy, Zap, RefreshCw } from 'lucide-react';
import { adminService } from '@/services/admin.service';

interface SystemPrompt {
  id: number;
  key: string;
  content: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
}

export default function PromptManagementPage() {
  const [prompts, setPrompts] = useState<SystemPrompt[]>([]);
  const [search, setSearch] = useState('');
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [editingPrompt, setEditingPrompt] = useState<SystemPrompt | null>(null);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ key: '', content: '', description: '' });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data: any = await adminService.getSystemPrompts();
      setPrompts(data.prompts || []);
    } catch (err) {
      console.error('Prompts load error:', err);
      customToast({ type: 'error', title: 'Prompts', message: 'Failed to load prompts.' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async () => {
    if (!form.key || !form.content) {
      customToast({ type: 'warning', title: 'Validation', message: 'Key and Content are required.' });
      return;
    }
    try {
      await adminService.updateSystemPrompt(form.key, form.content);
      customToast({ type: 'success', title: 'Prompt Created', message: 'System prompt saved.' });
      setIsAddOpen(false);
      setForm({ key: '', content: '', description: '' });
      load();
    } catch (err: any) {
      customToast({ type: 'error', title: 'Create Failed', message: err?.message || 'Could not save prompt.' });
    }
  };

  const handleEditOpen = (prompt: SystemPrompt) => {
    setEditingPrompt(prompt);
    setForm({ key: prompt.key, content: prompt.content, description: prompt.description || '' });
    setIsEditOpen(true);
  };

  const handleEdit = async () => {
    if (!form.key || !form.content) {
      customToast({ type: 'warning', title: 'Validation', message: 'Key and Content are required.' });
      return;
    }
    try {
      await adminService.updateSystemPrompt(form.key, form.content, form.description || undefined);
      customToast({ type: 'success', title: 'Prompt Updated', message: 'System prompt updated.' });
      setIsEditOpen(false);
      setEditingPrompt(null);
      setForm({ key: '', content: '', description: '' });
      load();
    } catch (err: any) {
      customToast({ type: 'error', title: 'Update Failed', message: err?.message || 'Could not update prompt.' });
    }
  };

  const filtered = prompts.filter(p =>
    p.key.toLowerCase().includes(search.toLowerCase()) ||
    (p.description || '').toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">AI Prompt Management</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Manage and version control Candway LLM system prompts</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" leftIcon={<RefreshCw className="h-4 w-4" />} onClick={load}>Refresh</Button>
          <Button variant="primary" size="sm" leftIcon={<Plus className="h-4 w-4" />} onClick={() => { setEditingPrompt(null); setForm({ key: '', content: '', description: '' }); setIsAddOpen(true); }} className="font-bold shadow-md shadow-purple-500/25">
            New Prompt
          </Button>
        </div>
      </div>

      <Card className="glass-panel border-purple-200/50 dark:border-purple-500/20">
        <CardHeader>
          <div className="flex items-center justify-between w-full">
            <div>
              <CardTitle>Prompt Library</CardTitle>
              <CardDescription>{prompts.filter(p => p.is_active).length} active system prompts</CardDescription>
            </div>
            <Input
              placeholder="Search prompts..."
              leftIcon={<Search className="h-4 w-4" />}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              wrapperClassName="w-64"
            />
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex flex-col items-center justify-center gap-3 py-16">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-purple-600 border-t-transparent" />
              <span className="text-sm text-gray-500">Loading prompts...</span>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-purple-100 dark:border-white/10">
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Prompt Key</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Description</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Status</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Modified</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((p) => (
                    <tr key={p.id} className="border-b border-gray-50 dark:border-white/[0.02] hover:bg-purple-50/50 dark:hover:bg-white/[0.02] transition-colors cursor-pointer">
                      <td className="py-3">
                        <div className="flex items-center gap-2">
                          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-100 dark:bg-purple-900/50">
                            <Zap className="h-4 w-4 text-purple-600 dark:text-purple-400" />
                          </div>
                          <span className="text-sm font-extrabold text-gray-900 dark:text-white font-mono">{p.key}</span>
                        </div>
                      </td>
                      <td className="py-3 text-sm font-medium text-gray-500">{p.description || '—'}</td>
                      <td className="py-3">
                        <Badge variant={p.is_active ? 'success' : 'default'} size="sm" dot>{p.is_active ? 'active' : 'inactive'}</Badge>
                      </td>
                      <td className="py-3 text-sm font-medium text-gray-500">{p.created_at ? new Date(p.created_at).toLocaleDateString() : '—'}</td>
                      <td className="py-3 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Button variant="ghost" size="xs" leftIcon={<Edit3 className="h-3.5 w-3.5 text-amber-500" />} onClick={() => handleEditOpen(p)} />
                          <Button variant="ghost" size="xs" leftIcon={<Copy className="h-3.5 w-3.5 text-purple-500" />} onClick={() => navigator.clipboard.writeText(p.content)} />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {filtered.length === 0 && !loading && (
                <div className="text-center py-10 text-sm text-gray-400">No prompts match your search.</div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={isAddOpen || isEditOpen} onOpenChange={(open) => { if (!open) { setIsAddOpen(false); setIsEditOpen(false); setEditingPrompt(null); setForm({ key: '', content: '', description: '' }); } }}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="text-purple-900 dark:text-white">{editingPrompt ? 'Edit Prompt' : 'Create New AI Prompt'}</DialogTitle>
            <DialogDescription>{editingPrompt ? 'Update the system prompt content.' : 'Configure a new system prompt for the Candway AI engine.'}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 my-4">
            <Input label="Key" placeholder="e.g. cv_analysis" value={form.key} onChange={(e) => setForm(f => ({ ...f, key: e.target.value }))} disabled={!!editingPrompt} />
            <Input label="Description" placeholder="Brief description of this prompt's purpose" value={form.description} onChange={(e) => setForm(f => ({ ...f, description: e.target.value }))} />
            <textarea
              className="w-full rounded-xl border border-purple-200/60 bg-white/70 p-3 text-sm focus:ring-2 focus:ring-purple-500/20 dark:border-white/10 dark:bg-white/5 dark:text-white"
              rows={8}
              placeholder="Enter the full system prompt content..."
              value={form.content}
              onChange={(e) => setForm(f => ({ ...f, content: e.target.value }))}
            />
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => { setIsAddOpen(false); setIsEditOpen(false); setEditingPrompt(null); }}>Cancel</Button>
            <Button variant="primary" onClick={editingPrompt ? handleEdit : handleCreate}>{editingPrompt ? 'Update' : 'Save'} Prompt</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
