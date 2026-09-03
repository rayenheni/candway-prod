import { useCallback, useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { useLanguage } from '@/contexts/language-context';
import { cn } from '@/utils/cn';
import {
  Loader2,
  CreditCard,
  Upload,
  Building2,
  ShieldCheck,
  Download,
  Check,
  AlertTriangle,
  FileText,
} from 'lucide-react';
import {
  orgService,
  type OrgBillingPlan,
  type OrgBillingSummary,
  type OrgBillingTx,
  type OrgInvoice,
  type OrgKyb,
} from '@/services/org.service';
import { customToast } from '@/shared/components/ui/toast';

type Tab = 'plans' | 'invoices' | 'kyb';

const STATUS_BADGES: Record<string, string> = {
  pending: 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300',
  succeeded: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300',
  Failed: 'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-300',
  active: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300',
  trialing: 'bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-300',
  expired: 'bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-300',
};

export default function OrgBillingPage() {
  const { t } = useLanguage();
  const [tab, setTab] = useState<Tab>('plans');
  const [summary, setSummary] = useState<OrgBillingSummary | null>(null);
  const [plans, setPlans] = useState<OrgBillingPlan[]>([]);
  const [transactions, setTransactions] = useState<OrgBillingTx[]>([]);
  const [invoices, setInvoices] = useState<OrgInvoice[]>([]);
  const [kyb, setKyb] = useState<OrgKyb | null>(null);
  const [loading, setLoading] = useState(true);
  const [cycle, setCycle] = useState<'monthly' | 'yearly'>('monthly');
  const [selectedPlan, setSelectedPlan] = useState<OrgBillingPlan | null>(null);
  const [subscribing, setSubscribing] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [kybSaving, setKybSaving] = useState(false);
  const [kybForm, setKybForm] = useState({ billing_email: '', billing_address: '', tax_id: '' });
  const fileRef = useRef<HTMLInputElement>(null);
  const [kybUploading, setKybUploading] = useState(false);
  const kybFileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      orgService.getBillingSummary(),
      orgService.getBillingPlans(),
      orgService.getTransactions(),
      orgService.getInvoices(),
      orgService.getKyb(),
    ])
      .then(([s, p, t, i, k]) => {
        setSummary(s);
        setPlans(p);
        setTransactions(t.transactions);
        setInvoices(i.invoices);
        setKyb(k);
        setKybForm({
          billing_email: k.billing_email || '',
          billing_address: k.billing_address || '',
          tax_id: k.tax_id || '',
        });
      })
      .catch(() => customToast({ type: 'error', title: 'Failed to load billing data' }))
      .finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  const subscribe = async (plan: OrgBillingPlan) => {
    setSelectedPlan(plan);
    setSubscribing(true);
    try {
      const res = await orgService.subscribeCompany({ plan_id: plan.id, billing_cycle: cycle });
      customToast({ type: 'success', title: res.message });
      load();
      fileRef.current?.click();
    } catch (e) {
      customToast({ type: 'error', title: (e as Error).message });
    } finally {
      setSubscribing(false);
    }
  };

  const onReceiptFile = async (ev: React.ChangeEvent<HTMLInputElement>) => {
    const file = ev.target.files?.[0];
    ev.target.value = '';
    if (!file) return;
    if (!summary?.pending_transaction) return;
    setUploading(true);
    try {
      await orgService.uploadReceipt(summary.pending_transaction.id, file);
      customToast({ type: 'success', title: 'Receipt uploaded', message: 'Your company subscription is pending admin approval.' });
      load();
    } catch (e) {
      customToast({ type: 'error', title: (e as Error).message });
    } finally {
      setUploading(false);
    }
  };

  const saveKyb = async () => {
    if (!kybForm.billing_email.trim()) {
      customToast({ type: 'error', title: 'Billing email is required' });
      return;
    }
    setKybSaving(true);
    try {
      const res = await orgService.submitKyb({
        billing_email: kybForm.billing_email.trim(),
        billing_address: kybForm.billing_address.trim() || undefined,
        tax_id: kybForm.tax_id.trim() || undefined,
      });
      customToast({ type: 'success', title: res.message });
      load();
    } catch (e) {
      customToast({ type: 'error', title: (e as Error).message });
    } finally {
      setKybSaving(false);
    }
  };

  const onKybDocsFile = async (ev: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(ev.target.files || []);
    ev.target.value = '';
    if (!files.length) return;
    setKybUploading(true);
    try {
      const res = await orgService.uploadKybDocuments(files);
      customToast({ type: 'success', title: res.message });
      load();
    } catch (e) {
      customToast({ type: 'error', title: (e as Error).message });
    } finally {
      setKybUploading(false);
    }
  };

  const downloadInvoice = async (inv: OrgInvoice) => {
    try {
      const blob = await orgService.downloadInvoice(inv.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Invoice-${inv.invoice_number}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      customToast({ type: 'success', title: 'Invoice downloaded' });
    } catch {
      customToast({ type: 'error', title: 'Download failed', message: 'Could not generate the invoice PDF.' });
    }
  };

  const pendingTx = summary?.pending_transaction;
  const hasActiveSub = summary?.subscription_status === 'active';

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-8 w-8 animate-spin text-purple-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{t('nav.billing')}</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{t('billing.subtitle')}</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={load}>{t('common.refresh')}</Button>
        </div>
      </div>

      {/* Company plan + seats status */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="flex items-center gap-3 pt-6">
            <div className="p-2.5 rounded-xl bg-purple-100 dark:bg-purple-500/20 text-purple-600 dark:text-purple-300">
              <CreditCard className="h-5 w-5" />
            </div>
            <div>
              <div className="text-sm text-gray-500 dark:text-gray-400">{t('billing.title')}</div>
              <div className="text-lg font-bold text-gray-900 dark:text-white capitalize">
                {summary?.plan?.name || '—'}
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 pt-6">
            <div className="p-2.5 rounded-xl bg-blue-100 dark:bg-blue-500/20 text-blue-600 dark:text-blue-300">
              <Building2 className="h-5 w-5" />
            </div>
            <div>
              <div className="text-sm text-gray-500 dark:text-gray-400">{t('org.members')}</div>
              <div className="text-lg font-bold text-gray-900 dark:text-white">
                {summary?.seats.used ?? 0} / {summary?.seats.limit ?? 0}
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 pt-6">
            <div className={cn('p-2.5 rounded-xl', summary?.kyb_status === 'approved'
              ? 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-600 dark:text-emerald-300'
              : 'bg-amber-100 dark:bg-amber-500/20 text-amber-600 dark:text-amber-300')}>
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <div className="text-sm text-gray-500 dark:text-gray-400">{t('org.kybTitle')}</div>
              <div className="text-lg font-bold text-gray-900 dark:text-white capitalize">
                {summary?.kyb_status || '—'}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {pendingTx && (
        <Card className="border-amber-300 dark:border-amber-500/40">
          <CardContent className="pt-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2 font-semibold text-amber-700 dark:text-amber-300">
                  <AlertTriangle className="h-4 w-4" />
                  Payment pending — #{pendingTx.id}
                </div>
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                  {pendingTx.description} · {pendingTx.amount_ttc} {pendingTx.currency}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <input ref={fileRef} type="file" hidden accept=".pdf,.png,.jpg,.jpeg" onChange={onReceiptFile} />
                <Button
                  variant="primary"
                  leftIcon={uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                  onClick={() => fileRef.current?.click()}
                  disabled={uploading}
                >
                  {pendingTx.proof_url ? t('common.upload') : t('common.upload')}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Tabs */}
      <div className="flex gap-2 border-b border-gray-200 dark:border-gray-800">
        {([
          ['plans', t('billing.title')],
          ['invoices', t('billing.invoices')],
          ['kyb', t('org.kybTitle')],
        ] as [Tab, string][]).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={cn(
              'px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors',
              tab === key
                ? 'border-purple-600 text-purple-600 dark:text-purple-400'
                : 'border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Plans tab */}
      {tab === 'plans' && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-500 dark:text-gray-400">Billing cycle:</span>
            {(['monthly', 'yearly'] as const).map((c) => (
              <button
                key={c}
                onClick={() => setCycle(c)}
                className={cn(
                  'px-3 py-1 rounded-full text-sm font-medium capitalize',
                  cycle === c
                    ? 'bg-purple-600 text-white'
                    : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300'
                )}
              >
                {c}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {plans.map((p) => {
              const price = cycle === 'monthly' ? p.price_monthly : p.price_yearly;
              const isCurrent = summary?.plan?.id === p.id;
              return (
                <Card key={p.id} className={cn(isCurrent && 'border-purple-500 ring-1 ring-purple-500')}>
                  <CardContent className="pt-6">
                    <div className="flex items-center justify-between">
                      <h3 className="text-lg font-bold text-gray-900 dark:text-white">{p.name}</h3>
                      {isCurrent && <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-purple-100 text-purple-700 dark:bg-purple-500/20 dark:text-purple-300">Current</span>}
                    </div>
                    <div className="mt-2 text-3xl font-bold text-gray-900 dark:text-white">
                      {price}
                      <span className="text-sm font-normal text-gray-400"> {p.currency}/{cycle}</span>
                    </div>
                    <ul className="mt-4 space-y-1.5 text-sm text-gray-600 dark:text-gray-300">
                      <li className="flex items-center gap-2"><Check className="h-4 w-4 text-emerald-500" /> {p.team_seat_limit} recruiter seats</li>
                      <li className="flex items-center gap-2"><Check className="h-4 w-4 text-emerald-500" /> {p.job_limit} active jobs</li>
                      <li className="flex items-center gap-2"><Check className="h-4 w-4 text-emerald-500" /> {p.credits_monthly} AI credits / month</li>
                    </ul>
                    <Button
                      id={`org-buy-${p.slug}`}
                      className="mt-4 w-full"
                      variant={isCurrent ? 'outline' : 'primary'}
                      onClick={() => subscribe(p)}
                      disabled={subscribing || !!pendingTx || hasActiveSub}
                    >
                      {subscribing && selectedPlan?.id === p.id ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                      {pendingTx ? 'Purchase pending' : hasActiveSub ? (isCurrent ? 'Active' : 'Active subscription') : isCurrent ? 'Active' : `Subscribe ${price} ${p.currency}`}
                    </Button>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </motion.div>
      )}

      {/* Invoices + transactions tab */}
      {tab === 'invoices' && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Transactions</CardTitle>
            </CardHeader>
            <CardContent>
              {!transactions.length ? (
                <p className="text-sm text-gray-500 py-6 text-center">No transactions yet.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                        <th className="py-2 font-medium">#</th>
                        <th className="py-2 font-medium">Description</th>
                        <th className="py-2 font-medium text-right">Amount (TTC)</th>
                        <th className="py-2 font-medium">Status</th>
                        <th className="py-2 font-medium">Date</th>
                      </tr>
                    </thead>
                    <tbody>
                      {transactions.map((tx) => (
                        <tr key={tx.id} className="border-b border-gray-100 dark:border-gray-800">
                          <td className="py-3">#{tx.id}</td>
                          <td className="py-3">{tx.description}</td>
                          <td className="py-3 text-right font-medium">{tx.amount_ttc} {tx.currency}</td>
                          <td className="py-3">
                            <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium capitalize', STATUS_BADGES[tx.status] || STATUS_BADGES.pending)}>{tx.status}</span>
                          </td>
                          <td className="py-3 text-gray-500">{tx.created_at ? new Date(tx.created_at).toLocaleDateString() : '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Invoices</CardTitle>
            </CardHeader>
            <CardContent>
              {!invoices.length ? (
                <p className="text-sm text-gray-500 py-6 text-center">No invoices yet — invoices are issued after payment approval.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                        <th className="py-2 font-medium">Number</th>
                        <th className="py-2 font-medium">Client</th>
                        <th className="py-2 font-medium text-right">HT</th>
                        <th className="py-2 font-medium text-right">TVA</th>
                        <th className="py-2 font-medium text-right">Total (TTC)</th>
                        <th className="py-2 font-medium text-right">PDF</th>
                      </tr>
                    </thead>
                    <tbody>
                      {invoices.map((inv) => (
                        <tr key={inv.id} className="border-b border-gray-100 dark:border-gray-800">
                          <td className="py-3 font-medium">{inv.invoice_number}</td>
                          <td className="py-3">{inv.client_name}</td>
                          <td className="py-3 text-right">{inv.amount_ht}</td>
                          <td className="py-3 text-right">{inv.tva_amount}</td>
                          <td className="py-3 text-right font-medium">{inv.total_ttc} TND</td>
                          <td className="py-3 text-right">
                            <button title="Download PDF" onClick={() => downloadInvoice(inv)} className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500">
                              <Download className="h-4 w-4" />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      )}

      {/* KYB tab */}
      {tab === 'kyb' && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <Card>
            <CardHeader>
              <CardTitle>Company Verification (KYB)</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                These details appear on your company invoices (B2B). Submitted once, approved by our team.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-xl">
                <label className="block">
                  <span className="text-sm font-medium text-gray-600 dark:text-gray-300">Billing email *</span>
                  <input
                    value={kybForm.billing_email}
                    onChange={(e) => setKybForm({ ...kybForm, billing_email: e.target.value })}
                    type="email"
                    placeholder="finance@company.com"
                    className="mt-1 w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
                  />
                </label>
                <label className="block">
                  <span className="text-sm font-medium text-gray-600 dark:text-gray-300">Tax ID / Matricule Fiscale</span>
                  <input
                    value={kybForm.tax_id}
                    onChange={(e) => setKybForm({ ...kybForm, tax_id: e.target.value })}
                    placeholder="e.g. 1234567/A/M/000"
                    className="mt-1 w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
                  />
                </label>
                <label className="block sm:col-span-2">
                  <span className="text-sm font-medium text-gray-600 dark:text-gray-300">Billing address</span>
                  <input
                    value={kybForm.billing_address}
                    onChange={(e) => setKybForm({ ...kybForm, billing_address: e.target.value })}
                    placeholder="Street, city, country"
                    className="mt-1 w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
                  />
                </label>
              </div>
              <div className="mt-4 flex items-center gap-3">
                <Button id="org-kyb-save" variant="primary" leftIcon={kybSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />} onClick={saveKyb} disabled={kybSaving}>
                  {kyb ? 'Update KYB Details' : 'Submit for Verification'}
                </Button>
                {kyb?.kyb_status && (
                  <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium capitalize', STATUS_BADGES[kyb.kyb_status] || STATUS_BADGES.pending)}>
                    {kyb.kyb_status}
                  </span>
                )}
              </div>

              <div className="mt-6 border-t border-gray-100 dark:border-gray-800 pt-5">
                <p className="text-sm font-semibold text-gray-700 dark:text-gray-300">Supporting documents</p>
                <p className="text-xs text-gray-400 mt-1 mb-3">
                  Upload your Matricule Fiscale, Registre de Commerce or other proof for the admin to verify (PDF, PNG, JPG — max 5 MB each, up to 6 files).
                </p>
                <input
                  ref={kybFileRef}
                  id="org-kyb-files"
                  type="file"
                  multiple
                  accept=".pdf,.png,.jpg,.jpeg"
                  className="hidden"
                  onChange={onKybDocsFile}
                />
                <div
                  onClick={() => kybFileRef.current?.click()}
                  className="border-2 border-dashed rounded-xl p-5 text-center cursor-pointer hover:border-purple-400 dark:hover:border-purple-500/50 text-sm text-gray-500 dark:text-gray-400"
                >
                  {kybUploading ? (
                    <span className="inline-flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" /> Uploading...</span>
                  ) : (
                    <span className="inline-flex items-center gap-2"><Upload className="h-4 w-4" /> Click to upload KYB documents</span>
                  )}
                </div>
                {kyb?.kyb_documents && kyb.kyb_documents.length > 0 && (
                  <ul className="mt-3 space-y-1.5">
                    {kyb.kyb_documents.map((d, i) => (
                      <li key={i} className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-300">
                        <FileText className="h-3.5 w-3.5 text-purple-500 shrink-0" />
                        <span className="truncate">{d.name}</span>
                        <a href={'/' + d.url} target="_blank" rel="noreferrer" className="ml-auto shrink-0 text-purple-600 hover:underline">
                          View
                        </a>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}
    </div>
  );
}
