// ============================================================
// Admin Payment Proofs - Candway (Sprint 19 S10)
// Real data from /admin/payment-proofs endpoints
// ============================================================

import { useCallback, useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/shared/components/ui/tabs';
import { PromptDialog } from '@/shared/components/ui/dialog';
import { customToast } from '@/shared/components/ui/toast';
import {
  CheckCircle2, XCircle, FileText, RefreshCw, AlertCircle, Eye, Download,
  Search, ShieldCheck, ShieldX,
} from 'lucide-react';
import { adminService, type PaymentProof } from '@/services/admin.service';
import { cn } from '@/utils/cn';

type ProofTab = 'uploaded' | 'verified' | 'rejected';

const TAB_STYLE: Record<ProofTab, string> = {
  uploaded: 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300',
  verified: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300',
  rejected: 'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-300',
};

const STATUS_STYLE: Record<string, string> = {
  pending: 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300',
  succeeded: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300',
  Failed: 'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-300',
};

function fmtDate(v: string | null): string {
  if (!v) return '—';
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString();
}

function fmtBytes(b: number | null): string {
  if (!b && b !== 0) return '—';
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / (1024 * 1024)).toFixed(1)} MB`;
}

export default function PaymentProofsPage() {
  const [tab, setTab] = useState<ProofTab>('uploaded');
  const [proofs, setProofs] = useState<PaymentProof[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<number | null>(null);
  const [search, setSearch] = useState('');
  const [rejecting, setRejecting] = useState<PaymentProof | null>(null);
  const perPage = 20;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminService.getPaymentProofs({
        page,
        per_page: perPage,
        proof_status: tab,
      });
      setProofs(data.proofs || []);
      setTotal(data.total || 0);
    } catch (err) {
      customToast({ type: 'error', title: 'Payment Proofs', message: 'Failed to load payment proofs.' });
      console.error('payment proofs load error:', err);
    } finally {
      setLoading(false);
    }
  }, [tab, page]);

  useEffect(() => { load(); }, [load]);

  const totalPages = Math.max(1, Math.ceil(total / perPage));

  const handleAction = async (p: PaymentProof, action: 'verify' | 'reject') => {
    if (action === 'reject') {
      setRejecting(p);
      return;
    }
    setBusy(p.id);
    try {
      await adminService.verifyPaymentProof(p.id);
      customToast({ type: 'success', title: 'Proof Verified', message: `Transaction #${p.id}` });
      load();
    } catch (err: any) {
      customToast({ type: 'error', title: 'Action Failed', message: err?.message || 'Could not update proof.' });
    } finally {
      setBusy(null);
    }
  };

  const confirmReject = async (notes: string) => {
    if (!rejecting) return;
    const p = rejecting;
    setBusy(p.id);
    try {
      await adminService.rejectPaymentProof(p.id, notes);
      customToast({ type: 'success', title: 'Proof Rejected', message: `Transaction #${p.id}` });
      load();
    } catch (err: any) {
      customToast({ type: 'error', title: 'Action Failed', message: err?.message || 'Could not update proof.' });
    } finally {
      setBusy(null);
      setRejecting(null);
    }
  };

  const handleDownload = async (p: PaymentProof) => {
    if (!p.proof_url) return;
    try {
      const blob = await adminService.downloadPaymentProof(p.id);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `proof-${p.id}${p.proof_file_type?.split('/').pop() ? '.' + p.proof_file_type.split('/').pop() : ''}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      customToast({ type: 'error', title: 'Download Failed', message: 'Could not download proof file.' });
    }
  };

  const filtered = proofs.filter(p =>
    p.user_name?.toLowerCase().includes(search.toLowerCase()) ||
    p.user_email?.toLowerCase().includes(search.toLowerCase()) ||
    String(p.id).includes(search)
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Badge variant="warning" className="bg-amber-600 text-white" size="sm">Payment Proofs</Badge>
          </div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">Payment Proof Review</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">View, verify, or reject uploaded payment receipts</p>
        </div>
        <Button variant="outline" size="sm" leftIcon={<RefreshCw className="h-4 w-4" />} onClick={load}>Refresh</Button>
      </div>

      <Tabs value={tab} onValueChange={(v) => { setTab(v as ProofTab); setPage(1); }}>
        <TabsList>
          <TabsTrigger value="uploaded" badge={proofs.filter(p => p.proof_status === 'uploaded').length}>Uploaded</TabsTrigger>
          <TabsTrigger value="verified" badge={proofs.filter(p => p.proof_status === 'verified').length}>Verified</TabsTrigger>
          <TabsTrigger value="rejected" badge={proofs.filter(p => p.proof_status === 'rejected').length}>Rejected</TabsTrigger>
        </TabsList>
      </Tabs>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between gap-4">
            <CardTitle className="text-base">{tab === 'uploaded' ? 'Pending Review' : tab === 'verified' ? 'Verified Proofs' : 'Rejected Proofs'}</CardTitle>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                placeholder="Search by name, email, or ID..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9 w-64"
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-sm text-gray-500">Loading...</div>
          ) : filtered.length === 0 ? (
            <div className="text-sm text-gray-500">No payment proofs found.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-gray-500">
                    <th className="text-left py-2 px-2">ID</th>
                    <th className="text-left py-2 px-2">User</th>
                    <th className="text-left py-2 px-2">Amount</th>
                    <th className="text-left py-2 px-2">Tx Status</th>
                    <th className="text-left py-2 px-2">Proof Status</th>
                    <th className="text-left py-2 px-2">File</th>
                    <th className="text-left py-2 px-2">Created</th>
                    <th className="text-left py-2 px-2">Verified</th>
                    <th className="text-right py-2 px-2">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((p) => (
                    <tr key={p.id} className="border-b last:border-0 hover:bg-gray-50 dark:hover:bg-gray-800/40">
                      <td className="py-3 px-2 font-mono">#{p.id}</td>
                      <td className="py-3 px-2">
                        <div className="font-medium text-gray-900 dark:text-white">{p.user_name || 'Unknown'}</div>
                        <div className="text-xs text-gray-500">{p.user_email}</div>
                      </td>
                      <td className="py-3 px-2">{Number(p.amount).toFixed(2)} {p.currency}</td>
                      <td className="py-3 px-2">
                        <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium', STATUS_STYLE[p.status] || 'bg-gray-100 text-gray-700')}>
                          {p.status}
                        </span>
                      </td>
                      <td className="py-3 px-2">
                        <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium', TAB_STYLE[p.proof_status as ProofTab] || 'bg-gray-100 text-gray-700')}>
                          {p.proof_status}
                        </span>
                      </td>
                      <td className="py-3 px-2">
                        {p.proof_url ? (
                          <Button variant="ghost" size="sm" leftIcon={<Eye className="h-3.5 w-3.5" />} onClick={() => window.open(p.proof_url || '', '_blank')}>View</Button>
                        ) : (
                          <span className="text-xs text-gray-500">—</span>
                        )}
                      </td>
                      <td className="py-3 px-2 text-xs text-gray-500">{fmtDate(p.created_at)}</td>
                      <td className="py-3 px-2 text-xs text-gray-500">{fmtDate(p.proof_verified_at)}</td>
                      <td className="py-3 px-2">
                        <div className="flex items-center justify-end gap-2">
                          {p.proof_status === 'uploaded' && (
                            <>
                              <Button
                                variant="ghost"
                                size="sm"
                                leftIcon={<ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />}
                                onClick={() => handleAction(p, 'verify')}
                                loading={busy === p.id}
                              >
                                Verify
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                leftIcon={<ShieldX className="h-3.5 w-3.5 text-red-600" />}
                                onClick={() => handleAction(p, 'reject')}
                                loading={busy === p.id}
                              >
                                Reject
                              </Button>
                            </>
                          )}
                          {p.proof_status === 'verified' && (
                            <Button
                              variant="ghost"
                              size="sm"
                              leftIcon={<Download className="h-3.5 w-3.5" />}
                              onClick={() => handleDownload(p)}
                            >
                              Download
                            </Button>
                          )}
                          {p.proof_status === 'rejected' && (
                            <span className="text-xs text-gray-500">{p.proof_review_notes || 'Rejected'}</span>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4">
              <div className="text-xs text-gray-500">Page {page} of {totalPages} • {total} total</div>
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</Button>
                <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>Next</Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <PromptDialog
        open={rejecting !== null}
        onOpenChange={(open) => { if (!open) setRejecting(null); }}
        title={`Reject proof for transaction #${rejecting?.id ?? ''}?`}
        description="Provide a reason. It will be sent to the payer."
        placeholder="Rejection reason"
        confirmLabel="Reject"
        cancelLabel="Cancel"
        variant="danger"
        onConfirm={confirmReject}
        loading={busy !== null}
      />
    </div>
  );
}
