// ============================================================
// Admin KYB Verifications Manager - Candway Tunisia
// Real data from /admin/verifications
// ============================================================

import { useCallback, useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Avatar } from '@/shared/components/ui/avatar';
import { customToast } from '@/shared/components/ui/toast';
import { Search, CheckCircle2, XCircle, FileText, RefreshCw, AlertCircle } from 'lucide-react';
import { adminService } from '@/services/admin.service';

interface Verification {
  id: number;
  user_id: number;
  company_name: string;
  matricule_fiscale: string;
  registre_commerce_id?: string;
  address?: string;
  document_url?: string;
  status: string;
  created_at?: string | null;
  admin_notes?: string | null;
}
export default function VerificationsManagerPage() {
  const [verifs, setVerifs] = useState<Verification[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  void setPage;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data: any = await adminService.getModerationQueue({ status: 'pending', page });
      setVerifs(data.verifications || []);
      setTotal(data.total || 0);
    } catch (err) {
      console.error('Verifications load error:', err);
      customToast({ type: 'error', title: 'Verifications', message: 'Failed to load verifications.' });
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => { load(); }, [load]);

  const handleAction = async (id: number, action: 'approve' | 'reject', reason?: string) => {
    try {
      if (action === 'approve') {
        await adminService.moderateContent(String(id), 'approve');
      } else {
        await adminService.moderateContent(String(id), 'reject', reason || 'Insufficient documentation');
      }
      setVerifs(v => v.filter(v => v.id !== id));
      setTotal(t => t - 1);
      customToast({
        type: action === 'approve' ? 'success' : 'warning',
        title: `KYB ${action === 'approve' ? 'Approved' : 'Rejected'}`,
        message: 'Company verification status updated.',
      });
    } catch (err: any) {
      customToast({ type: 'error', title: 'Action Failed', message: err?.message || 'Could not update verification.' });
    }
  };

  const filtered = verifs.filter(v =>
    (v.company_name || '').toLowerCase().includes(search.toLowerCase()) ||
    (v.matricule_fiscale || '').toLowerCase().includes(search.toLowerCase()) ||
    (v.registre_commerce_id || '').toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Badge variant="warning" className="bg-amber-600 text-white" size="sm">Tunisia KYB Compliance</Badge>
          </div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">KYB Verifications</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Verify company legal documents for Tunisian enterprise accounts</p>
        </div>
        <Button variant="outline" size="sm" leftIcon={<RefreshCw className="h-4 w-4" />} onClick={load}>Refresh</Button>
      </div>

      <Card className="glass-panel border-purple-200/50">
        <CardHeader>
          <div className="flex items-center justify-between w-full">
            <div>
              <CardTitle>Pending Verifications ({filtered.length})</CardTitle>
              <CardDescription>Review and approve company registration documents ({total} total pending)</CardDescription>
            </div>
            <Input
              placeholder="Search company..."
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
              <span className="text-sm text-gray-500">Loading verifications...</span>
            </div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-16 text-gray-400">
              <AlertCircle className="h-8 w-8 mx-auto mb-2" />
              <p>No verifications match your filters.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {filtered.map(v => (
                <div key={v.id} className="flex flex-col sm:flex-row sm:items-center justify-between p-5 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10">
                  <div className="flex items-start gap-4 flex-1">
                    <Avatar name={v.company_name || 'Company'} size="md" square className="ring-2 ring-purple-200/50" />
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-base font-extrabold text-gray-900 dark:text-white">{v.company_name}</h3>
                        <Badge variant={v.status === 'approved' ? 'success' : v.status === 'rejected' ? 'danger' : 'warning'} size="sm" dot>{v.status}</Badge>
                      </div>
                      <p className="text-xs text-gray-400 mt-0.5">MF: {v.matricule_fiscale}{v.registre_commerce_id ? ` • RC: ${v.registre_commerce_id}` : ''}</p>
                      {v.address && <p className="text-xs text-gray-400 mt-0.5">{v.address}</p>}
                      <div className="flex flex-wrap gap-1.5 mt-2">
                        {v.document_url ? (
                          <Badge variant="default" size="sm" className="flex items-center gap-1 bg-purple-50 dark:bg-purple-950/40">
                            <FileText className="h-3 w-3" />Document on file
                          </Badge>
                        ) : (
                          <Badge variant="default" size="sm" className="flex items-center gap-1 bg-gray-100 dark:bg-white/[0.04]">
                            <FileText className="h-3 w-3" />No document uploaded
                          </Badge>
                        )}
                      </div>
                      {v.admin_notes && (
                        <div className="mt-2 text-xs text-red-500 bg-red-50 dark:bg-red-950/20 px-2 py-1 rounded border border-red-100 dark:border-red-900/30">
                          <span className="font-bold">Admin Note:</span> {v.admin_notes}
                        </div>
                      )}
                      {v.created_at && (
                        <p className="text-xs text-gray-400 mt-2">Submitted: {new Date(v.created_at).toLocaleDateString()}</p>
                      )}
                    </div>
                  </div>
                  {v.status === 'pending' && (
                    <div className="flex items-center gap-2 mt-4 sm:mt-0 sm:ml-4 shrink-0">
                      <Button
                        variant="outline"
                        size="sm"
                        leftIcon={<XCircle className="h-4 w-4 text-red-500" />}
                        onClick={() => handleAction(v.id, 'reject', 'Insufficient documentation')}
                        className="border-red-200 text-red-700"
                      >
                        Reject
                      </Button>
                      <Button
                        variant="primary"
                        size="sm"
                        leftIcon={<CheckCircle2 className="h-4 w-4" />}
                        onClick={() => handleAction(v.id, 'approve')}
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
    </div>
  );
}
