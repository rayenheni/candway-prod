// ============================================================
// Admin Invoicing & Fiscal Records - Candway
// Real data from /admin/invoices API
// ============================================================

import { useCallback, useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/shared/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/shared/components/ui/dialog';
import { customToast } from '@/shared/components/ui/toast';
import { cn } from '@/utils/cn';
import { FileText, Download, Search, Plus, CheckCircle2, Clock, AlertCircle, RefreshCw } from 'lucide-react';
import { adminService } from '@/services/admin.service';

interface Invoice {
  id: number;
  invoice_number: string;
  user_id: number;
  amount_ht: number;
  tva_rate: number;
  tva_amount: number;
  stamp_duty: number;
  total_ttc: number;
  client_name: string;
  status: string;
  created_at: string;
  transaction_id?: number;
}

const statusConfig: Record<string, { variant: 'success' | 'warning' | 'danger' | 'default' | 'info'; icon: React.ElementType }> = {
  paid: { variant: 'success', icon: CheckCircle2 },
  draft: { variant: 'default', icon: Clock },
  pending: { variant: 'warning', icon: Clock },
  overdue: { variant: 'danger', icon: AlertCircle },
  cancelled: { variant: 'default', icon: AlertCircle },
};

export default function InvoicesPage() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [form, setForm] = useState({ user_id: '', amount_ht: '', description: '' });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data: any = await adminService.getInvoices({ page: 1, per_page: 100 });
      setInvoices(data.invoices || []);
    } catch (err) {
      console.error('Invoices load error:', err);
      customToast({ type: 'error', title: 'Invoices', message: 'Failed to load invoices.' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const filtered = invoices.filter(inv => {
    const matchesSearch = inv.invoice_number.toLowerCase().includes(search.toLowerCase()) ||
      inv.client_name.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = statusFilter === 'all' || inv.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const handleCreateInvoice = async () => {
    if (!form.user_id || !form.amount_ht) {
      customToast({ type: 'warning', title: 'Validation', message: 'User ID and Amount are required.' });
      return;
    }
    try {
      await adminService.generateInvoice({
        user_id: parseInt(form.user_id),
        amount_ht: parseFloat(form.amount_ht),
      });
      customToast({ type: 'success', title: 'Invoice Created', message: 'Invoice generated successfully.' });
      setIsCreateOpen(false);
      setForm({ user_id: '', amount_ht: '', description: '' });
      load();
    } catch (err: any) {
      customToast({ type: 'error', title: 'Create Failed', message: err?.message || 'Could not create invoice.' });
    }
  };

  const handleDownloadPDF = async (id: number) => {
    try {
      const blob = await adminService.downloadInvoicePDF(id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Invoice_${id}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      customToast({ type: 'success', title: 'Download Started', message: 'Invoice PDF downloaded.' });
    } catch (err: any) {
      customToast({ type: 'error', title: 'Download Failed', message: err?.message || 'Could not download PDF.' });
    }
  };

  const getStatusIcon = (status: string) => {
    const config = statusConfig[status];
    if (!config) return null;
    const Icon = config.icon;
    return <Icon className={cn('h-3.5 w-3.5',
      status === 'paid' ? 'text-emerald-500' :
      status === 'pending' ? 'text-amber-500' :
      status === 'overdue' ? 'text-red-500' : 'text-gray-400')} />;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Invoicing & Fiscal Records</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Create, manage, and monitor all fiscal documents</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" leftIcon={<RefreshCw className="h-4 w-4" />} onClick={load}>Refresh</Button>
          <Button variant="primary" leftIcon={<Plus className="h-4 w-4" />} onClick={() => setIsCreateOpen(true)}>Create Invoice</Button>
        </div>
      </div>

      <Card className="glass-panel border-purple-200/50 dark:border-purple-500/20">
        <CardHeader>
          <div className="flex items-center justify-between w-full">
            <div>
              <CardTitle>All Invoices ({filtered.length})</CardTitle>
              <CardDescription>{invoices.filter(i => i.status === 'paid').length} paid, {invoices.filter(i => i.status === 'pending').length} pending, {invoices.filter(i => i.status === 'overdue').length} overdue</CardDescription>
            </div>
                <div className="flex items-center gap-2">
                  <Input placeholder="Search invoices..." leftIcon={<Search className="h-4 w-4" />} value={search} onChange={(e) => setSearch(e.target.value)} wrapperClassName="w-48" />
                  <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v)}>
                    <SelectTrigger className="w-36"><SelectValue placeholder="All Status" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Status</SelectItem>
                      <SelectItem value="paid">Paid</SelectItem>
                      <SelectItem value="draft">Draft</SelectItem>
                      <SelectItem value="pending">Pending</SelectItem>
                      <SelectItem value="overdue">Overdue</SelectItem>
                      <SelectItem value="cancelled">Cancelled</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex flex-col items-center justify-center gap-3 py-16">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-purple-600 border-t-transparent" />
              <span className="text-sm text-gray-500">Loading invoices...</span>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-purple-100 dark:border-white/10">
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Invoice #</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Client</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Amount</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Status</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase">Date</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase" style={{ width: '50px' }}>PDF</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((inv) => (
                    <tr key={inv.id} className="border-b border-gray-50 dark:border-white/[0.02] hover:bg-purple-50/50 dark:hover:bg-white/[0.02] transition-colors">
                      <td className="py-3 text-sm font-bold text-gray-900 dark:text-white">{inv.invoice_number || `INV-${inv.id}`}</td>
                      <td className="py-3 text-sm font-medium text-gray-700 dark:text-gray-300">{inv.client_name}</td>
                      <td className="py-3 text-sm font-bold text-gray-900 dark:text-white">{inv.total_ttc?.toLocaleString() || 0} TND</td>
                      <td className="py-3">
                        <Badge variant={statusConfig[inv.status]?.variant || 'default'} size="sm" dot className="gap-1">
                          {getStatusIcon(inv.status)}
                          {inv.status}
                        </Badge>
                      </td>
                      <td className="py-3 text-sm text-gray-500">{inv.created_at ? new Date(inv.created_at).toLocaleDateString() : '—'}</td>
                      <td className="py-3">
                        <Button variant="ghost" size="xs" leftIcon={<Download className="h-3.5 w-3.5 text-gray-500" />} onClick={() => handleDownloadPDF(inv.id)} />
                      </td>
                    </tr>
                  ))}
                  {filtered.length === 0 && !loading && (
                    <tr><td colSpan={6} className="py-12 text-center text-gray-400">No invoices match your filters.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="text-purple-900 dark:text-white">Create New Invoice</DialogTitle>
            <DialogDescription>Generate a fiscal invoice for a tenant company.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 my-4">
            <Input
              label="User ID"
              placeholder="Recipient user ID"
              value={form.user_id}
              onChange={(e) => setForm(f => ({ ...f, user_id: e.target.value }))}
            />
            <Input
              label="Amount HT (TND)"
              placeholder="e.g. 2400.00"
              value={form.amount_ht}
              onChange={(e) => setForm(f => ({ ...f, amount_ht: e.target.value }))}
            />
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Description</label>
              <textarea
                className="w-full rounded-xl border border-purple-200/60 bg-white/70 p-3 text-sm min-h-[100px] focus:ring-2 focus:ring-purple-500/20 dark:border-white/10 dark:bg-white/5 dark:text-white"
                placeholder="Invoice description or notes..."
                value={form.description}
                onChange={(e) => setForm(f => ({ ...f, description: e.target.value }))}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setIsCreateOpen(false)}>Cancel</Button>
            <Button variant="primary" onClick={handleCreateInvoice} leftIcon={<FileText className="h-4 w-4" />}>Generate Invoice</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
