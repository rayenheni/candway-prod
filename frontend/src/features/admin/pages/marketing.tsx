// ============================================================
// Admin Marketing & Campaigns - Candway
// Real data from /admin/marketing/leads, /admin/coupons
// ============================================================

import { useCallback, useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/shared/components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/shared/components/ui/dialog';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/shared/components/ui/select';
import { customToast } from '@/shared/components/ui/toast';
import { Plus, Send, Trash2, RefreshCw, Gift, Search } from 'lucide-react';
import { adminService } from '@/services/admin.service';

interface MarketingLead {
  id: number;
  email: string;
  name: string;
  company: string;
  status: string;
  created_at: string | null;
}

interface Coupon {
  id: number;
  code: string;
  discount_percent: number;
  expires_in_days: number;
  is_active: boolean;
  created_at: string | null;
}

export default function MarketingPage() {
  const [activeTab, setActiveTab] = useState('campaigns');
  const [leads, setLeads] = useState<MarketingLead[]>([]);
  const [coupons, setCoupons] = useState<Coupon[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [isCampaignOpen, setIsCampaignOpen] = useState(false);
  const [isCouponOpen, setIsCouponOpen] = useState(false);
  const [campaignForm, setCampaignForm] = useState({ subject: '', content: '' });
  const [couponForm, setCouponForm] = useState({ code: '', discount_percent: 10, expires_in_days: 30 });

  const loadLeads = useCallback(async () => {
    try {
      const data: any = await adminService.getMarketingLeads({ page: 1, per_page: 100 });
      setLeads(data.leads || []);
    } catch (err) {
      console.error('Leads load error:', err);
      customToast({ type: 'error', title: 'Marketing', message: 'Failed to load leads.' });
    }
  }, []);

  const loadCoupons = useCallback(async () => {
    try {
      const data: any = await adminService.getCoupons({ page: 1, per_page: 100 });
      setCoupons(data.coupons || []);
    } catch (err) {
      console.error('Coupons load error:', err);
    }
  }, []);

  const loadAll = useCallback(async () => {
    setLoading(true);
    await Promise.all([loadLeads(), loadCoupons()]);
    setLoading(false);
  }, [loadLeads, loadCoupons]);

  useEffect(() => { loadAll(); }, [loadAll]);

  const handleSendCampaign = async () => {
    if (!campaignForm.subject || !campaignForm.content) {
      customToast({ type: 'warning', title: 'Validation', message: 'Subject and Content are required.' });
      return;
    }
    try {
      const res: any = await adminService.sendMarketingCampaign(campaignForm);
      customToast({ type: 'success', title: 'Campaign Sent', message: `${res.message || 'Campaign queued.'}` });
      setIsCampaignOpen(false);
      setCampaignForm({ subject: '', content: '' });
    } catch (err: any) {
      customToast({ type: 'error', title: 'Send Failed', message: err?.message || 'Could not send campaign.' });
    }
  };

  const handleCreateCoupon = async () => {
    if (!couponForm.code) {
      customToast({ type: 'warning', title: 'Validation', message: 'Coupon code is required.' });
      return;
    }
    try {
      await adminService.createCoupon(couponForm);
      customToast({ type: 'success', title: 'Coupon Created', message: `Coupon ${couponForm.code} created.` });
      setIsCouponOpen(false);
      setCouponForm({ code: '', discount_percent: 10, expires_in_days: 30 });
      loadCoupons();
    } catch (err: any) {
      customToast({ type: 'error', title: 'Create Failed', message: err?.message || 'Could not create coupon.' });
    }
  };

  const handleDeleteCoupon = async (id: number) => {
    if (!confirm('Delete this coupon?')) return;
    try {
      await adminService.deleteCoupon(id);
      setCoupons(c => c.filter(x => x.id !== id));
      customToast({ type: 'warning', title: 'Deleted', message: 'Coupon removed.' });
    } catch (err: any) {
      customToast({ type: 'error', title: 'Failed', message: err?.message || 'Could not delete coupon.' });
    }
  };

  const filteredLeads = leads.filter(l => {
    const q = search.toLowerCase();
    const matches = l.email.toLowerCase().includes(q) || l.name.toLowerCase().includes(q) || l.company.toLowerCase().includes(q);
    const matchesStatus = statusFilter === 'all' || l.status === statusFilter;
    return matches && matchesStatus;
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Marketing & Campaigns</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Manage marketing leads, campaigns, and promotional coupons</p>
        </div>
        <Button variant="outline" size="sm" leftIcon={<RefreshCw className="h-4 w-4" />} onClick={loadAll}>Refresh</Button>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="campaigns">Marketing Leads</TabsTrigger>
          <TabsTrigger value="coupons">Coupons</TabsTrigger>
          <TabsTrigger value="stats">Campaign Stats</TabsTrigger>
        </TabsList>

        <TabsContent value="campaigns">
          <Card className="glass-panel border-purple-200/50">
          <CardHeader>
              <div className="flex items-center justify-between w-full">
                <div>
                  <CardTitle>Sales Leads ({filteredLeads.length})</CardTitle>
                  <CardDescription>{leads.length} total leads collected</CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  <Input placeholder="Search leads..." leftIcon={<Search className="h-4 w-4" />} value={search} onChange={(e) => setSearch(e.target.value)} wrapperClassName="w-48" />
                  <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v)}>
                    <SelectTrigger className="w-32"><SelectValue placeholder="All Status" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Status</SelectItem>
                      <SelectItem value="new">New</SelectItem>
                      <SelectItem value="contacted">Contacted</SelectItem>
                      <SelectItem value="qualified">Qualified</SelectItem>
                      <SelectItem value="interested">Interested</SelectItem>
                      <SelectItem value="converted">Converted</SelectItem>
                      <SelectItem value="rejected">Rejected</SelectItem>
                    </SelectContent>
                  </Select>
                  <Button variant="primary" size="sm" leftIcon={<Send className="h-4 w-4" />} onClick={() => setIsCampaignOpen(true)}>Send Campaign</Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="py-16 text-center text-gray-400">Loading leads...</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left">
                    <thead>
                      <tr className="border-b border-purple-100 dark:border-white/10">
                        <th className="py-3 text-xs font-bold text-gray-500 uppercase">Name</th>
                        <th className="py-3 text-xs font-bold text-gray-500 uppercase">Email</th>
                        <th className="py-3 text-xs font-bold text-gray-500 uppercase">Company</th>
                        <th className="py-3 text-xs font-bold text-gray-500 uppercase">Status</th>
                        <th className="py-3 text-xs font-bold text-gray-500 uppercase">Created</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredLeads.map(l => (
                        <tr key={l.id} className="border-b border-gray-50 dark:border-white/[0.02] hover:bg-purple-50/50 transition-colors">
                          <td className="py-3 text-sm font-bold text-gray-900 dark:text-white">{l.name || l.email}</td>
                          <td className="py-3 text-sm text-gray-500">{l.email}</td>
                          <td className="py-3 text-sm font-medium text-gray-500">{l.company || '—'}</td>
                          <td className="py-3"><Badge variant={l.status === 'new' ? 'default' : l.status === 'contacted' ? 'info' : l.status === 'qualified' ? 'primary' : 'success'} size="sm" dot>{l.status}</Badge></td>
                          <td className="py-3 text-sm text-gray-500">{l.created_at ? new Date(l.created_at).toLocaleDateString() : '—'}</td>
                        </tr>
                      ))}
                      {filteredLeads.length === 0 && !loading && <tr><td colSpan={5} className="py-10 text-center text-gray-400">No leads found.</td></tr>}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="coupons">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-lg font-bold text-gray-900 dark:text-white">Promotional Coupons</h3>
            <Button variant="primary" size="sm" leftIcon={<Plus className="h-4 w-4" />} onClick={() => setIsCouponOpen(true)}>New Coupon</Button>
          </div>
          {loading ? (
            <div className="py-16 text-center text-gray-400">Loading coupons...</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-purple-100 dark:border-white/10">
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Code</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Discount</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Expires</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Status</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {coupons.map(c => (
                    <tr key={c.id} className="border-b border-gray-50 dark:border-white/[0.02] hover:bg-purple-50/50 transition-colors">
                      <td className="py-3"><code className="text-sm font-mono font-bold text-gray-900 dark:text-white">{c.code}</code></td>
                      <td className="py-3 text-sm font-medium text-gray-500">{c.discount_percent}%</td>
                      <td className="py-3 text-sm text-gray-500">{c.expires_in_days} days</td>
                      <td className="py-3"><Badge variant={c.is_active ? 'success' : 'default'} size="sm" dot>{c.is_active ? 'active' : 'inactive'}</Badge></td>
                      <td className="py-3 text-right">
                        <Button variant="ghost" size="xs" leftIcon={<Trash2 className="h-3.5 w-3.5 text-red-500" />} onClick={() => handleDeleteCoupon(c.id)} />
                      </td>
                    </tr>
                  ))}
                  {coupons.length === 0 && !loading && <tr><td colSpan={5} className="py-10 text-center text-gray-400">No coupons found.</td></tr>}
                </tbody>
              </table>
            </div>
          )}
        </TabsContent>

        <TabsContent value="stats">
          <Card className="glass-panel border-purple-200/50">
            <CardHeader><CardTitle>Campaign Performance</CardTitle></CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 bg-white/60 dark:bg-white/[0.02] rounded-xl border border-purple-100 dark:border-white/10">
                  <div>
                    <div className="font-bold text-gray-900 dark:text-white">Total Leads</div>
                    <div className="text-sm text-gray-500">All collected marketing leads</div>
                  </div>
                  <div className="text-2xl font-black text-purple-600">{leads.length}</div>
                </div>
                <div className="flex items-center justify-between p-4 bg-white/60 dark:bg-white/[0.02] rounded-xl border border-purple-100 dark:border-white/10">
                  <div>
                    <div className="font-bold text-gray-900 dark:text-white">Active Coupons</div>
                    <div className="text-sm text-gray-500">Currently valid discount codes</div>
                  </div>
                  <div className="text-2xl font-black text-emerald-600">{coupons.filter(c => c.is_active).length}</div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Dialog open={isCampaignOpen} onOpenChange={setIsCampaignOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Send Marketing Campaign</DialogTitle>
            <DialogDescription>Compose and send a campaign email to all non-admin users.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 my-4">
            <Input label="Subject" placeholder="Campaign subject" value={campaignForm.subject} onChange={(e) => setCampaignForm(f => ({ ...f, subject: e.target.value }))} />
            <textarea
              className="w-full rounded-xl border border-purple-200/60 bg-white/70 p-3 text-sm focus:ring-2 focus:ring-purple-500/20 dark:border-white/10 dark:bg-white/5 dark:text-white"
              rows={6}
              placeholder="Email content..."
              value={campaignForm.content}
              onChange={(e) => setCampaignForm(f => ({ ...f, content: e.target.value }))}
            />
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setIsCampaignOpen(false)}>Cancel</Button>
            <Button variant="primary" leftIcon={<Send className="h-4 w-4" />} onClick={handleSendCampaign}>Send Campaign</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={isCouponOpen} onOpenChange={setIsCouponOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Coupon</DialogTitle>
            <DialogDescription>Create a new promotional discount code.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 my-4">
            <Input label="Coupon Code" placeholder="e.g. WELCOME2026" value={couponForm.code} onChange={(e) => setCouponForm(f => ({ ...f, code: e.target.value }))} />
            <Input label="Discount (%)" type="number" placeholder="10" value={couponForm.discount_percent} onChange={(e) => setCouponForm(f => ({ ...f, discount_percent: parseInt(e.target.value) || 0 }))} />
            <Input label="Expires In (days)" type="number" placeholder="30" value={couponForm.expires_in_days} onChange={(e) => setCouponForm(f => ({ ...f, expires_in_days: parseInt(e.target.value) || 0 }))} />
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setIsCouponOpen(false)}>Cancel</Button>
            <Button variant="primary" leftIcon={<Gift className="h-4 w-4" />} onClick={handleCreateCoupon}>Create Coupon</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
