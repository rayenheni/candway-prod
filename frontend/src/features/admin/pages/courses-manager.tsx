// ============================================================
// Admin Courses Manager - Candway Tunisia
// Real data from /admin/courses API
// ============================================================

import { useCallback, useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Tabs, TabsList, TabsTrigger } from '@/shared/components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/shared/components/ui/dialog';
import { customToast } from '@/shared/components/ui/toast';
import { Search, CheckCircle2, XCircle, Star, RefreshCw, ExternalLink } from 'lucide-react';
import { adminService } from '@/services/admin.service';
import type { Course } from '@/services/admin.service';

export default function CoursesManagerPage() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [loading, setLoading] = useState(true);
  const [detailOpen, setDetailOpen] = useState<Course | null>(null);
  const [isExternalOpen, setIsExternalOpen] = useState(false);
  const [externalForm, setExternalForm] = useState({
    title: '', description: '', category: '', difficulty: '',
    duration: '' as string | number, thumbnail_url: '', price: '' as string | number, url: ''
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data: any = await adminService.getCourses({ status: 'all', page: 1, per_page: 100 });
      setCourses(data.courses || []);
    } catch (err) {
      console.error('Courses load error:', err);
      customToast({ type: 'error', title: 'Courses', message: 'Failed to load courses.' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleApprove = async (id: number) => {
    try {
      await adminService.approveCourse(id);
      setCourses(c => c.map(c => c.id === id ? { ...c, status: 'published' } : c));
      customToast({ type: 'success', title: 'Course Approved', message: 'Course is now live on the platform.' });
    } catch (err: any) {
      customToast({ type: 'error', title: 'Action Failed', message: err?.message || 'Could not approve course.' });
    }
  };

  const handleReject = async (id: number) => {
    try {
      await adminService.rejectCourse(id);
      setCourses(c => c.map(c => c.id === id ? { ...c, status: 'rejected' } : c));
      customToast({ type: 'warning', title: 'Course Rejected', message: 'Course has been rejected.' });
    } catch (err: any) {
      customToast({ type: 'error', title: 'Action Failed', message: err?.message || 'Could not reject course.' });
    }
  };

  const handleCreateExternal = async () => {
    try {
      await adminService.createExternalCourse({
        ...externalForm,
        duration: typeof externalForm.duration === 'string' ? parseInt(externalForm.duration) || 0 : externalForm.duration,
        price: typeof externalForm.price === 'string' ? parseFloat(externalForm.price) || 0 : externalForm.price,
      });
      customToast({ type: 'success', title: 'External Course Created', message: 'New external course has been added.' });
      setIsExternalOpen(false);
      setExternalForm({ title: '', description: '', category: '', difficulty: '', duration: '', thumbnail_url: '', price: '', url: '' });
      load();
    } catch (err: any) {
      customToast({ type: 'error', title: 'Create Failed', message: err?.message || 'Could not create external course.' });
    }
  };

  const filtered = courses.filter(c => {
    const q = search.toLowerCase();
    const matchesSearch = c.title.toLowerCase().includes(q) || c.category.toLowerCase().includes(q);
    const matchesStatus = statusFilter === 'all' || c.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const stats = [
    { label: 'Total Courses', value: courses.length, icon: Star, color: 'text-purple-600', bg: 'bg-purple-100 dark:bg-purple-900/30' },
    { label: 'Published', value: courses.filter(c => c.status === 'published').length, icon: CheckCircle2, color: 'text-emerald-600', bg: 'bg-emerald-100 dark:bg-emerald-900/30' },
    { label: 'Pending Review', value: courses.filter(c => c.status === 'pending_review').length, icon: XCircle, color: 'text-amber-600', bg: 'bg-amber-100 dark:bg-amber-900/30' },
    { label: 'Rejected', value: courses.filter(c => c.status === 'rejected').length, icon: XCircle, color: 'text-red-600', bg: 'bg-red-100 dark:bg-red-900/30' },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">Courses Manager</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Manage published courses and approve new submissions</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" leftIcon={<RefreshCw className="h-4 w-4" />} onClick={load}>Refresh</Button>
          <Button variant="primary" size="sm" leftIcon={<>
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6l4 2" /></svg>
          </>} onClick={() => setIsExternalOpen(true)}>
            Add External
          </Button>
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
              <div className="text-2xl font-black text-gray-900 dark:text-white tracking-tighter">{stat.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card className="glass-panel border-purple-200/50 dark:border-purple-500/20">
        <CardHeader>
          <div className="flex items-center justify-between w-full">
            <div>
              <CardTitle>All Courses ({filtered.length})</CardTitle>
              <CardDescription>{courses.filter(c => c.status === 'pending_review').length} pending approval</CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Tabs value={statusFilter} onValueChange={setStatusFilter} className="w-auto">
                <TabsList>
                  <TabsTrigger value="all">All</TabsTrigger>
                  <TabsTrigger value="pending_review">Pending</TabsTrigger>
                  <TabsTrigger value="published">Published</TabsTrigger>
                </TabsList>
              </Tabs>
              <Input placeholder="Search courses..." leftIcon={<Search className="h-4 w-4" />} value={search} onChange={(e) => setSearch(e.target.value)} wrapperClassName="w-64" />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex flex-col items-center justify-center gap-3 py-16">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-purple-600 border-t-transparent" />
              <span className="text-sm text-gray-500">Loading courses...</span>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-purple-100 dark:border-white/10">
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Course</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Instructor</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Status</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Price</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Created</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(c => (
                    <tr key={c.id} className="border-b border-gray-50 dark:border-white/[0.02] hover:bg-purple-50/50 transition-colors">
                      <td className="py-3">
                        <div className="text-sm font-extrabold text-gray-900 dark:text-white">{c.title}</div>
                        <div className="text-xs text-gray-500">{c.category}</div>
                      </td>
                      <td className="py-3 text-sm font-medium text-gray-500">{c.mentor_name || '—'}</td>
                      <td className="py-3">
                        <Badge variant={c.status === 'published' ? 'success' : c.status === 'pending_review' ? 'warning' : 'danger'} size="sm" dot>{c.status}</Badge>
                      </td>
                      <td className="py-3 text-sm font-medium text-gray-500">{c.price || 0} TND</td>
                      <td className="py-3 text-sm font-medium text-gray-500">{c.created_at ? new Date(c.created_at).toLocaleDateString() : '—'}</td>
                      <td className="py-3 text-right">
                        {c.status === 'pending_review' ? (
                          <div className="flex items-center justify-end gap-1">
                            <Button variant="ghost" size="xs" leftIcon={<XCircle className="h-4 w-4 text-red-500" />} onClick={() => handleReject(c.id)} />
                            <Button variant="ghost" size="xs" leftIcon={<CheckCircle2 className="h-4 w-4 text-emerald-500" />} onClick={() => handleApprove(c.id)} />
                          </div>
                        ) : (
                          <Button variant="ghost" size="xs" leftIcon={<ExternalLink className="h-3.5 w-3.5" />} onClick={() => setDetailOpen(c)} />
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {filtered.length === 0 && !loading && (
                <div className="text-center py-10 text-sm text-gray-400">No courses found.</div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={!!detailOpen} onOpenChange={() => setDetailOpen(null)}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>{detailOpen?.title}</DialogTitle>
            <DialogDescription>Category: {detailOpen?.category} • Instructor: {detailOpen?.mentor_name}</DialogDescription>
          </DialogHeader>
          {detailOpen && (
            <div className="space-y-4">
              <p className="text-sm text-gray-600">Price: {detailOpen.price} TND</p>
              <p className="text-sm text-gray-600">Status: {detailOpen.status}</p>
              <p className="text-xs text-gray-400">Created: {new Date(detailOpen.created_at).toLocaleString()}</p>
            </div>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={isExternalOpen} onOpenChange={setIsExternalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create External Course</DialogTitle>
            <DialogDescription>Add a new external course (links to external platform).</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 my-4">
            <Input label="Title" placeholder="Course name" value={externalForm.title} onChange={(e) => setExternalForm(f => ({ ...f, title: e.target.value }))} />
            <Input label="Category" placeholder="e.g. Frontend" value={externalForm.category} onChange={(e) => setExternalForm(f => ({ ...f, category: e.target.value }))} />
            <Input label="Difficulty" placeholder="Beginner / Intermediate / Advanced" value={externalForm.difficulty} onChange={(e) => setExternalForm(f => ({ ...f, difficulty: e.target.value }))} />
            <Input label="Duration (hours)" placeholder="Duration" value={externalForm.duration} onChange={(e) => setExternalForm(f => ({ ...f, duration: e.target.value }))} />
            <Input label="Thumbnail URL" placeholder="https://..." value={externalForm.thumbnail_url} onChange={(e) => setExternalForm(f => ({ ...f, thumbnail_url: e.target.value }))} />
            <Input label="Price (TND)" placeholder="0 = free" value={externalForm.price} onChange={(e) => setExternalForm(f => ({ ...f, price: e.target.value }))} />
            <Input label="External URL" placeholder="https://..." value={externalForm.url} onChange={(e) => setExternalForm(f => ({ ...f, url: e.target.value }))} />
            <Input label="Description" placeholder="Short description" value={externalForm.description} onChange={(e) => setExternalForm(f => ({ ...f, description: e.target.value }))} />
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setIsExternalOpen(false)}>Cancel</Button>
            <Button variant="primary" onClick={handleCreateExternal} disabled={!externalForm.title || !externalForm.url}>Create</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
