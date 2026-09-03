// ============================================================
// Admin Category Manager - Candway
// Real data from /admin/categories API
// ============================================================

import { useCallback, useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/shared/components/ui/dialog';
import { customToast } from '@/shared/components/ui/toast';
import { FolderTree, Plus, Edit, Trash2, Save, X, RefreshCw } from 'lucide-react';
import { adminService } from '@/services/admin.service';

interface Category {
  id: number;
  name: string;
  slug: string;
  type: string;
  parent_id?: number | null;
  jobs_count?: number;
  is_active?: boolean;
}

export default function CategoriesPage() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState({ name: '', type: '' });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data: any = await adminService.getCategories({ page: 1, per_page: 100 });
      setCategories(data.categories || []);
    } catch (err) {
      console.error('Categories load error:', err);
      customToast({ type: 'error', title: 'Categories', message: 'Failed to load categories.' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const openCreate = () => {
    setEditingId(null);
    setForm({ name: '', type: 'job' });
    setIsDialogOpen(true);
  };

  const openEdit = (cat: Category) => {
    setEditingId(cat.id);
    setForm({ name: cat.name, type: cat.type });
    setIsDialogOpen(true);
  };

  const handleSave = async () => {
    if (!form.name.trim() || !form.type) {
      customToast({ type: 'warning', title: 'Validation', message: 'Name and Type are required.' });
      return;
    }
    try {
      if (editingId) {
        await adminService.updateCategory(editingId, { name: form.name.trim(), type: form.type });
        customToast({ type: 'success', title: 'Category Updated', message: `"${form.name}" has been updated.` });
      } else {
        await adminService.createCategory({ name: form.name.trim(), type: form.type });
        customToast({ type: 'success', title: 'Category Created', message: `"${form.name}" has been created.` });
      }
      setIsDialogOpen(false);
      load();
    } catch (err: any) {
      customToast({ type: 'error', title: editingId ? 'Update Failed' : 'Create Failed', message: err?.message || 'Could not save category.' });
    }
  };

  const handleDelete = async (cat: Category) => {
    if (!confirm(`Remove "${cat.name}"?`)) return;
    try {
      await adminService.deleteCategory(cat.id);
      setCategories(c => c.filter(x => x.id !== cat.id));
      customToast({ type: 'warning', title: 'Category Deleted', message: `"${cat.name}" has been removed.` });
    } catch (err: any) {
      customToast({ type: 'error', title: 'Delete Failed', message: err?.message || 'Could not delete category.' });
    }
  };

  const filtered = categories.filter(c =>
    c.name.toLowerCase().includes(search.toLowerCase()) ||
    c.type.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">Category Manager</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Organize job categories, subcategories, and ordering</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" leftIcon={<RefreshCw className="h-4 w-4" />} onClick={load}>Refresh</Button>
          <Button variant="primary" size="sm" leftIcon={<Plus className="h-4 w-4" />} onClick={openCreate} className="font-bold shadow-md shadow-purple-500/25">New Category</Button>
        </div>
      </div>

      <Input
        placeholder="Search categories..."
        leftIcon={<FolderTree className="h-4 w-4" />}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        wrapperClassName="w-64"
      />

      <Card className="glass-panel border-purple-200/50 dark:border-purple-500/20">
        <CardHeader>
          <CardTitle>Job Categories</CardTitle>
          <CardDescription>{filtered.length} categories</CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex flex-col items-center justify-center gap-3 py-16">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-purple-600 border-t-transparent" />
              <span className="text-sm text-gray-500">Loading categories...</span>
            </div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-16 text-gray-400">No categories found.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-purple-100 dark:border-white/10">
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Name</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Slug</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Type</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Jobs</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Status</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((cat) => (
                    <tr key={cat.id} className="border-b border-gray-50 dark:border-white/[0.02] hover:bg-purple-50/50 transition-colors">
                      <td className="py-3">
                        <div className="flex items-center gap-3">
                          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-100 dark:bg-purple-900/50">
                            <FolderTree className="h-4 w-4 text-purple-600 dark:text-purple-400" />
                          </div>
                          <span className="text-sm font-extrabold text-gray-900 dark:text-white">{cat.name}</span>
                        </div>
                      </td>
                      <td className="py-3 text-sm font-mono text-gray-500">{cat.slug}</td>
                      <td className="py-3 text-sm font-medium text-gray-500">{cat.type}</td>
                      <td className="py-3 text-sm font-medium text-gray-500">{cat.jobs_count || 0}</td>
                      <td className="py-3">
                        <Badge variant="success" size="sm" dot>active</Badge>
                      </td>
                      <td className="py-3 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Button variant="ghost" size="xs" onClick={() => openEdit(cat)}><Edit className="h-3.5 w-3.5 text-blue-500" /></Button>
                          <Button variant="ghost" size="xs" onClick={() => handleDelete(cat)}><Trash2 className="h-3.5 w-3.5 text-red-500" /></Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="text-purple-900 dark:text-white">{editingId ? 'Edit Category' : 'Create New Category'}</DialogTitle>
            <DialogDescription>{editingId ? 'Update category details.' : 'Add a new job category to the system.'}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 my-4">
            <Input label="Category Name" placeholder="e.g. Data Science & AI" value={form.name} onChange={(e) => setForm(f => ({ ...f, name: e.target.value }))} />
            <Input label="Type" placeholder="job" value={form.type} onChange={(e) => setForm(f => ({ ...f, type: e.target.value }))} />
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setIsDialogOpen(false)} leftIcon={<X className="h-4 w-4" />}>Cancel</Button>
            <Button variant="primary" onClick={handleSave} leftIcon={<Save className="h-4 w-4" />}>{editingId ? 'Update' : 'Create'} Category</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
