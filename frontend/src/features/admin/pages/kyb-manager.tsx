// ============================================================
// Admin Company KYB Manager - Candway
// Real data from /admin/kyb (company-level Know-Your-Business review)
// ============================================================

import { useCallback, useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { PromptDialog } from '@/shared/components/ui/dialog';
import { customToast } from '@/shared/components/ui/toast';
import { CheckCircle2, XCircle, FileText, RefreshCw, AlertCircle, Building2 } from 'lucide-react';
import { adminService, type KybCompany } from '@/services/admin.service';
import { cn } from '@/utils/cn';

type KybTab = 'pending' | 'approved' | 'rejected';

const TAB_STYLE: Record<KybTab, string> = {
  pending: 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300',
  approved: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300',
  rejected: 'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-300',
};

export default function KybManagerPage() {
  const [tab, setTab] = useState<KybTab>('pending');
  const [companies, setCompanies] = useState<KybCompany[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [busy, setBusy] = useState<number | null>(null);
  const [rejecting, setRejecting] = useState<KybCompany | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminService.getKyb(tab, page, 30);
      setCompanies(data.companies || []);
      setTotal(data.total || 0);
    } catch (err) {
      console.error('KYB load error:', err);
      customToast({ type: 'error', title: 'KYB', message: 'Failed to load KYB submissions.' });
    } finally {
      setLoading(false);
    }
  }, [tab, page]);

  useEffect(() => { load(); }, [load]);

  const handleAction = async (c: KybCompany, action: 'approve' | 'reject') => {
    if (action === 'reject') {
      setRejecting(c);
      return;
    }
    setBusy(c.company_id);
    try {
      await adminService.approveKyb(c.company_id);
      customToast({ type: 'success', title: 'KYB Approved', message: c.company_name });
      load();
    } catch (err: any) {
      customToast({ type: 'error', title: 'Action Failed', message: err?.message || 'Could not update KYB status.' });
    } finally {
      setBusy(null);
    }
  };

  const confirmReject = async (reason: string) => {
    if (!rejecting) return;
    const c = rejecting;
    setBusy(c.company_id);
    try {
      await adminService.rejectKyb(c.company_id, reason);
      customToast({ type: 'success', title: 'KYB Rejected', message: c.company_name });
      load();
    } catch (err: any) {
      customToast({ type: 'error', title: 'Action Failed', message: err?.message || 'Could not update KYB status.' });
    } finally {
      setBusy(null);
      setRejecting(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Badge variant="warning" className="bg-amber-600 text-white" size="sm">Company KYB</Badge>
          </div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">Company Verification (KYB)</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Review company documents and approve or reject Know-Your-Business submissions</p>
        </div>
        <Button variant="outline" size="sm" leftIcon={<RefreshCw className="h-4 w-4" />} onClick={load}>Refresh</Button>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2">
        {(['pending', 'approved', 'rejected'] as KybTab[]).map((t) => (
          <button
            key={t}
            onClick={() => { setTab(t); setPage(1); }}
            className={cn(
              'px-4 py-2 rounded-full text-sm font-semibold capitalize transition-colors',
              tab === t
                ? 'bg-purple-600 text-white'
                : 'bg-gray-100 text-gray-500 dark:bg-white/5 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-white/10'
            )}
          >
            {t}
          </button>
        ))}
      </div>

      <Card className="glass-panel border-purple-200/50">
        <CardHeader>
          <div className="flex items-center justify-between w-full">
            <div>
              <CardTitle>{tab === 'pending' ? 'Pending Review' : tab === 'approved' ? 'Approved Companies' : 'Rejected Companies'}</CardTitle>
              <CardDescription>{total} company submission{total !== 1 ? 's' : ''}</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center gap-3 py-16">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-purple-600 border-t-transparent" />
              <span className="text-sm text-gray-500">Loading KYB submissions...</span>
            </div>
          ) : companies.length === 0 ? (
            <div className="text-center py-16 text-gray-400">
              <AlertCircle className="h-8 w-8 mx-auto mb-2" />
              <p>No company submissions in this state.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {companies.map((c) => (
                <div key={c.company_id} className="flex flex-col lg:flex-row lg:items-center justify-between p-5 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10">
                  <div className="flex items-start gap-4 flex-1">
                    <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-purple-100 dark:bg-purple-500/20 text-purple-600 dark:text-purple-300">
                      <Building2 className="h-5 w-5" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="text-base font-extrabold text-gray-900 dark:text-white">{c.company_name}</h3>
                        <Badge variant="default" size="sm" className={cn('capitalize', TAB_STYLE[tab])}>{c.kyb_status || '—'}</Badge>
                      </div>
                      <p className="text-xs text-gray-400 mt-1">
                        {c.tax_id ? `MF: ${c.tax_id} · ` : ''}
                        {c.billing_email ? `${c.billing_email} · ` : ''}
                        {c.owner_name ? `Owner: ${c.owner_name}` : ''}
                      </p>
                      {c.billing_address && <p className="text-xs text-gray-400 mt-0.5">{c.billing_address}</p>}
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {c.kyb_documents && c.kyb_documents.length > 0 ? (
                          c.kyb_documents.map((d, i) => (
                            <a
                              key={i}
                              href={'/' + d.url}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1 rounded-lg bg-purple-50 dark:bg-purple-950/40 border border-purple-100 dark:border-purple-500/20 px-2 py-1 text-xs font-medium text-purple-700 dark:text-purple-300 hover:bg-purple-100 dark:hover:bg-purple-900/40"
                            >
                              <FileText className="h-3 w-3" />{d.name}
                            </a>
                          ))
                        ) : (
                          <span className="inline-flex items-center gap-1 rounded-lg bg-gray-100 dark:bg-white/[0.04] px-2 py-1 text-xs text-gray-400">
                            <FileText className="h-3 w-3" />No documents uploaded
                          </span>
                        )}
                      </div>
                      {c.created_at && <p className="text-xs text-gray-400 mt-2">Created: {new Date(c.created_at).toLocaleDateString()}</p>}
                    </div>
                  </div>
                  {tab === 'pending' && (
                    <div className="flex items-center gap-2 mt-4 lg:mt-0 lg:ml-4 shrink-0">
                      <Button
                        variant="outline"
                        size="sm"
                        leftIcon={<XCircle className="h-4 w-4 text-red-500" />}
                        onClick={() => handleAction(c, 'reject')}
                        disabled={busy === c.company_id}
                        className="border-red-200 text-red-700"
                      >
                        Reject
                      </Button>
                      <Button
                        variant="primary"
                        size="sm"
                        leftIcon={busy === c.company_id ? undefined : <CheckCircle2 className="h-4 w-4" />}
                        onClick={() => handleAction(c, 'approve')}
                        disabled={busy === c.company_id}
                        className="bg-emerald-600 hover:bg-emerald-700"
                      >
                        Approve
                      </Button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <PromptDialog
        open={rejecting !== null}
        onOpenChange={(open) => { if (!open) setRejecting(null); }}
        title={`Reject ${rejecting?.company_name ?? 'company'}?`}
        description="Provide a reason. It will be sent to the company owner."
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
