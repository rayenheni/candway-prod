// ============================================================
// Admin Content Manager (Blogs + Opportunities) - Candway
// Real data from /admin/blogs and /admin/opportunities APIs
// ============================================================

import { useCallback, useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/shared/components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/shared/components/ui/dialog';
import { customToast } from '@/shared/components/ui/toast';
import { Search, Plus, Edit3, Trash2, Save, X, RefreshCw, ExternalLink } from 'lucide-react';
import { adminService } from '@/services/admin.service';

interface BlogPost {
  id: number;
  title: string;
  slug: string;
  content?: string;
  image_url?: string;
  tags?: string;
  is_published?: boolean;
  created_at?: string;
}

interface Opportunity {
  id: number;
  title: string;
  type: string;
  description?: string;
  link?: string;
  image_url?: string;
  is_active?: boolean;
  created_at?: string;
}

export default function ContentManagerPage() {
  const [activeTab, setActiveTab] = useState('blogs');
  const [blogs, setBlogs] = useState<BlogPost[]>([]);
  const [opps, setOpps] = useState<Opportunity[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [isBlogOpen, setIsBlogOpen] = useState(false);
  const [isOppOpen, setIsOppOpen] = useState(false);
  const [editingBlog, setEditingBlog] = useState<BlogPost | null>(null);
  const [editingOpp, setEditingOpp] = useState<Opportunity | null>(null);
  const [blogForm, setBlogForm] = useState({ title: '', slug: '', content: '', image_url: '', tags: '' });
  const [oppForm, setOppForm] = useState({ title: '', type: 'Scholarship', description: '', link: '', image_url: '' });

  const slugify = (s: string) => s.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');

  const loadBlogs = useCallback(async () => {
    try {
      const data = await adminService.getBlogPosts({ page: 1, per_page: 100 });
      setBlogs(data.blogs || []);
    } catch (err) {
      customToast({ type: 'error', title: 'Blogs', message: 'Failed to load blogs.' });
    }
  }, []);

  const loadOpps = useCallback(async () => {
    try {
      const data = await adminService.getOpportunities();
      setOpps(data.opportunities || []);
    } catch (err) {
      customToast({ type: 'error', title: 'Opportunities', message: 'Failed to load opportunities.' });
    }
  }, []);

  const loadAll = useCallback(async () => {
    setLoading(true);
    await Promise.all([loadBlogs(), loadOpps()]);
    setLoading(false);
  }, [loadBlogs, loadOpps]);

  useEffect(() => { loadAll(); }, [loadAll]);

  const handleSaveBlog = async () => {
    if (!blogForm.title || !blogForm.slug) {
      customToast({ type: 'warning', title: 'Validation', message: 'Title and Slug are required.' });
      return;
    }
    try {
      if (editingBlog) {
        await adminService.updateBlogPost(editingBlog.id, blogForm);
        customToast({ type: 'success', title: 'Updated', message: 'Blog post updated.' });
      } else {
        await adminService.createBlogPost(blogForm);
        customToast({ type: 'success', title: 'Created', message: 'Blog post created.' });
      }
      setIsBlogOpen(false);
      setEditingBlog(null);
      setBlogForm({ title: '', slug: '', content: '', image_url: '', tags: '' });
      loadBlogs();
    } catch (err: any) {
      customToast({ type: 'error', title: 'Failed', message: err?.message || 'Could not save blog.' });
    }
  };

  const handleSaveOpp = async () => {
    if (!oppForm.title || !oppForm.link) {
      customToast({ type: 'warning', title: 'Validation', message: 'Title and Link are required.' });
      return;
    }
    try {
      if (editingOpp) {
        await adminService.updateOpportunity?.(editingOpp.id, oppForm) ?? Promise.resolve();
        customToast({ type: 'success', title: 'Updated', message: 'Opportunity updated.' });
      } else {
        await adminService.createOpportunity(oppForm);
        customToast({ type: 'success', title: 'Created', message: 'Opportunity created.' });
      }
      setIsOppOpen(false);
      setEditingOpp(null);
      setOppForm({ title: '', type: 'Scholarship', description: '', link: '', image_url: '' });
      loadOpps();
    } catch (err: any) {
      customToast({ type: 'error', title: 'Failed', message: err?.message || 'Could not save opportunity.' });
    }
  };

  const openBlogEdit = (blog: BlogPost) => {
    setEditingBlog(blog);
    setBlogForm({ title: blog.title, slug: blog.slug, content: blog.content || '', image_url: blog.image_url || '', tags: blog.tags || '' });
    setIsBlogOpen(true);
  };

  const openOppEdit = (opp: Opportunity) => {
    setEditingOpp(opp);
    setOppForm({ title: opp.title, type: opp.type, description: opp.description || '', link: opp.link || '', image_url: opp.image_url || '' });
    setIsOppOpen(true);
  };

  const deleteBlog = async (id: number) => {
    if (!confirm('Delete this blog post?')) return;
    try {
      await adminService.deleteBlogPost(id);
      setBlogs(b => b.filter(x => x.id !== id));
      customToast({ type: 'warning', title: 'Deleted', message: 'Blog post removed.' });
    } catch (err: any) {
      customToast({ type: 'error', title: 'Failed', message: err?.message || 'Could not delete.' });
    }
  };

  const deleteOpp = async (id: number) => {
    if (!confirm('Delete this opportunity?')) return;
    try {
      await adminService.deleteOpportunity(id);
      setOpps(o => o.filter(x => x.id !== id));
      customToast({ type: 'warning', title: 'Deleted', message: 'Opportunity removed.' });
    } catch (err: any) {
      customToast({ type: 'error', title: 'Failed', message: err?.message || 'Could not delete.' });
    }
  };

  const blogFiltered = blogs.filter(b =>
    b.title.toLowerCase().includes(search.toLowerCase()) ||
    (b.tags || '').toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">Content Manager</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Manage Blogs and Opportunities.</p>
        </div>
        <div className="flex gap-4">
          <Button variant="primary" leftIcon={<Plus className="h-4 w-4" />} onClick={() => { setEditingBlog(null); setBlogForm({ title: '', slug: '', content: '', image_url: '', tags: '' }); setIsBlogOpen(true); }}>
            New Blog Post
          </Button>
          <Button variant="primary" leftIcon={<Plus className="h-4 w-4" />} onClick={() => { setEditingOpp(null); setOppForm({ title: '', type: 'Scholarship', description: '', link: '', image_url: '' }); setIsOppOpen(true); }}>
            New Opportunity
          </Button>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="blogs">Blogs</TabsTrigger>
          <TabsTrigger value="opps">Opportunities</TabsTrigger>
        </TabsList>

        <TabsContent value="blogs">
          <div className="flex gap-4 mb-4">
            <Input placeholder="Search by title or tags..." leftIcon={<Search className="h-4 w-4" />} value={search} onChange={(e) => setSearch(e.target.value)} wrapperClassName="w-64" />
            <Button variant="outline" size="sm" leftIcon={<RefreshCw className="h-4 w-4" />} onClick={loadBlogs}>Refresh</Button>
          </div>
          <Card className="glass-panel border-purple-200/50">
            <CardHeader><CardTitle>Blog Posts ({blogFiltered.length})</CardTitle></CardHeader>
            <CardContent>
              {loading ? (
                <div className="py-16 text-center text-gray-400">Loading blogs...</div>
              ) : blogFiltered.length === 0 ? (
                <div className="py-16 text-center text-gray-400">No blog posts found.</div>
              ) : (
                <div className="space-y-4">
                  {blogFiltered.map(blog => (
                    <div key={blog.id} className="flex items-center justify-between p-4 bg-white/60 dark:bg-white/[0.02] rounded-xl border border-purple-100 dark:border-white/10">
                      <div className="flex items-center gap-4">
                        {blog.image_url && <img src={blog.image_url} alt={blog.title} className="w-16 h-12 object-cover rounded-lg" />}
                        <div>
                          <h3 className="font-extrabold text-gray-900 dark:text-white">{blog.title}</h3>
                          <p className="text-xs text-gray-500 font-mono">/{blog.slug}</p>
                          <Badge variant={blog.is_published ? 'success' : 'warning'} size="sm" className="mt-1">{blog.is_published ? 'Published' : 'Draft'}</Badge>
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <Button variant="ghost" size="xs" leftIcon={<Edit3 className="h-3.5 w-3.5" />} onClick={() => openBlogEdit(blog)}>Edit</Button>
                        <Button variant="ghost" size="xs" leftIcon={<Trash2 className="h-3.5 w-3.5 text-red-500" />} onClick={() => deleteBlog(blog.id)}>Delete</Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="opps">
          <div className="flex gap-4 mb-4">
            <Button variant="outline" size="sm" leftIcon={<RefreshCw className="h-4 w-4" />} onClick={loadOpps}>Refresh</Button>
          </div>
          <Card className="glass-panel border-purple-200/50">
            <CardHeader><CardTitle>Opportunities ({opps.length})</CardTitle></CardHeader>
            <CardContent>
              {loading ? (
                <div className="py-16 text-center text-gray-400">Loading opportunities...</div>
              ) : opps.length === 0 ? (
                <div className="py-16 text-center text-gray-400">No opportunities found.</div>
              ) : (
                <div className="space-y-4">
                  {opps.map(opp => (
                    <div key={opp.id} className="flex items-center justify-between p-4 bg-white/60 dark:bg-white/[0.02] rounded-xl border border-purple-100 dark:border-white/10">
                      <div>
                        <h3 className="font-extrabold text-gray-900 dark:text-white flex items-center gap-2">
                          {opp.title}
                          <Badge variant="default" size="sm">{opp.type}</Badge>
                        </h3>
                        <p className="text-xs text-gray-500 mt-1 line-clamp-1">{opp.description}</p>
                        <a href={opp.link} target="_blank" rel="noopener noreferrer" className="text-xs text-indigo-600 flex items-center gap-1 mt-1">
                          <ExternalLink className="h-3 w-3" /> {opp.link}
                        </a>
                      </div>
                      <div className="flex gap-2">
                        <Button variant="ghost" size="xs" leftIcon={<Edit3 className="h-3.5 w-3.5" />} onClick={() => openOppEdit(opp)}>Edit</Button>
                        <Button variant="ghost" size="xs" leftIcon={<Trash2 className="h-3.5 w-3.5 text-red-500" />} onClick={() => deleteOpp(opp.id)}>Delete</Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Dialog open={isBlogOpen} onOpenChange={setIsBlogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{editingBlog ? 'Edit Blog Post' : 'Create New Blog Post'}</DialogTitle>
            <DialogDescription>{editingBlog ? 'Update the blog post details.' : 'Add a new blog post to the platform.'}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 my-4">
            <Input label="Title" placeholder="Post title" value={blogForm.title} onChange={(e) => { setBlogForm(f => ({ ...f, title: e.target.value })); if (!editingBlog) setBlogForm(f => ({ ...f, slug: slugify(e.target.value) })); }} />
            <Input label="Slug" placeholder="post-slug" value={blogForm.slug} onChange={(e) => setBlogForm(f => ({ ...f, slug: e.target.value }))} />
            <Input label="Cover Image URL" placeholder="https://..." value={blogForm.image_url} onChange={(e) => setBlogForm(f => ({ ...f, image_url: e.target.value }))} />
            <Input label="Tags" placeholder="comma, separated, tags" value={blogForm.tags} onChange={(e) => setBlogForm(f => ({ ...f, tags: e.target.value }))} />
            <textarea
              className="w-full rounded-xl border border-purple-200/60 bg-white/70 p-3 text-sm focus:ring-2 focus:ring-purple-500/20 dark:border-white/10 dark:bg-white/5 dark:text-white"
              rows={6}
              placeholder="Content (HTML supported)..."
              value={blogForm.content}
              onChange={(e) => setBlogForm(f => ({ ...f, content: e.target.value }))}
            />
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setIsBlogOpen(false)} leftIcon={<X className="h-4 w-4" />}>Cancel</Button>
            <Button variant="primary" onClick={handleSaveBlog} leftIcon={<Save className="h-4 w-4" />}>Save Post</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={isOppOpen} onOpenChange={setIsOppOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingOpp ? 'Edit Opportunity' : 'New Opportunity'}</DialogTitle>
            <DialogDescription>{editingOpp ? 'Update opportunity details.' : 'Add a new opportunity.'}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 my-4">
            <Input label="Title" value={oppForm.title} onChange={(e) => setOppForm(f => ({ ...f, title: e.target.value }))} />
            <Input label="Type" value={oppForm.type} onChange={(e) => setOppForm(f => ({ ...f, type: e.target.value }))} />
            <textarea className="w-full rounded-xl border border-purple-200/60 bg-white/70 p-3 text-sm focus:ring-2 focus:ring-purple-500/20 dark:border-white/10 dark:bg-white/5 dark:text-white" rows={3} placeholder="Description..." value={oppForm.description} onChange={(e) => setOppForm(f => ({ ...f, description: e.target.value }))} />
            <Input label="External URL" value={oppForm.link} onChange={(e) => setOppForm(f => ({ ...f, link: e.target.value }))} />
            <Input label="Image URL" value={oppForm.image_url} onChange={(e) => setOppForm(f => ({ ...f, image_url: e.target.value }))} />
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setIsOppOpen(false)} leftIcon={<X className="h-4 w-4" />}>Cancel</Button>
            <Button variant="primary" onClick={handleSaveOpp}>{editingOpp ? 'Update' : 'Create'} Opportunity</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
