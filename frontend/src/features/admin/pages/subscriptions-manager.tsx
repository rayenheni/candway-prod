// ============================================================
// Admin Subscriptions Manager - Candway (Monetization S8)
// Production-ready view: manual approvals, lifecycle actions,
// full plan CRUD, and plan version history.
// ============================================================

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { Input } from '@/shared/components/ui/input';
import { Avatar } from '@/shared/components/ui/avatar';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/shared/components/ui/tabs';
import { SimpleDropdown } from '@/shared/components/ui/dropdown-menu';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/shared/components/ui/dialog';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/shared/components/ui/select';
import { customToast } from '@/shared/components/ui/toast';
import {
  Search, MoreHorizontal, CreditCard, RefreshCw, Ban, CheckCircle2, XCircle, Clock, Gift, CalendarPlus, RotateCcw,
  Pencil, Copy, Archive, Plus, Eye, Wallet, TrendingUp,
} from 'lucide-react';
import { adminService } from '@/services/admin.service';

interface PendingSub {
  id: number;
  user_id: number;
  user_name: string;
  user_email: string;
  amount: number;
  proof_url: string | null;
  date: string;
  type: string;
  description?: string | null;
}

interface ActiveSub {
  id: number;
  name: string;
  email: string;
  subscription_end: string;
  status: string;
}

interface Plan {
  id: number;
  name: string;
  slug: string;
  target_audience: string;
  price_monthly: number;
  price_yearly: number;
  currency: string;
  is_active: boolean;
  is_featured: boolean;
  credits_monthly: number;
  plan_group: string;
  job_limit?: number;
  cv_limit?: number;
  ai_interview_limit?: number;
  team_seat_limit?: number;
  candidate_cv_uploads_limit?: number;
  candidate_ai_analyses_limit?: number;
  candidate_pdf_downloads_limit?: number;
  candidate_job_matches_limit?: number;
  features?: string | string[] | null;
  permissions_json?: string | Record<string, any> | null;
}

interface PlanVersion {
  id: number;
  version: number;
  name: string;
  slug: string;
  price_monthly: number;
  price_yearly: number;
  currency: string;
  created_at?: string;
  valid_from?: string;
  valid_to?: string;
}

interface PlanDraft {
  name: string;
  slug: string;
  target_audience: string;
  price_monthly: string;
  price_yearly: string;
  currency: string;
  is_active: boolean;
  is_featured: boolean;
  credits_monthly: string;
  plan_group: string;
  job_limit: string;
  cv_limit: string;
  ai_interview_limit: string;
  team_seat_limit: string;
  candidate_cv_uploads_limit: string;
  candidate_ai_analyses_limit: string;
  candidate_pdf_downloads_limit: string;
  candidate_job_matches_limit: string;
  features: string;
  permissions_json: string;
}

const statusVariant: Record<string, 'success' | 'warning' | 'danger' | 'info' | 'default'> = {
  active: 'success',
  trialing: 'info',
  past_due: 'warning',
  pending: 'warning',
  expired: 'danger',
  canceled: 'default',
  rejected: 'danger',
};

const defaultPlanDraft: PlanDraft = {
  name: '',
  slug: '',
  target_audience: 'recruiter',
  price_monthly: '0',
  price_yearly: '0',
  currency: 'TND',
  is_active: true,
  is_featured: false,
  credits_monthly: '0',
  plan_group: 'standard',
  job_limit: '0',
  cv_limit: '0',
  ai_interview_limit: '0',
  team_seat_limit: '0',
  candidate_cv_uploads_limit: '0',
  candidate_ai_analyses_limit: '0',
  candidate_pdf_downloads_limit: '0',
  candidate_job_matches_limit: '0',
  features: '[]',
  permissions_json: '{}',
};

function fmtDate(d: string | null | undefined): string {
  if (!d) return 'N/A';
  const dt = new Date(d);
  return Number.isNaN(dt.getTime()) ? String(d) : dt.toLocaleDateString();
}

function fmtMoney(v: number | null | undefined, currency = 'TND'): string {
  return `${Number(v || 0).toFixed(0)} ${currency}`;
}

function normalizePlanDraft(plan?: Partial<Plan>): PlanDraft {
  if (!plan) return { ...defaultPlanDraft };

  return {
    name: plan.name ?? '',
    slug: plan.slug ?? '',
    target_audience: plan.target_audience ?? 'recruiter',
    price_monthly: String(plan.price_monthly ?? 0),
    price_yearly: String(plan.price_yearly ?? 0),
    currency: plan.currency ?? 'TND',
    is_active: Boolean(plan.is_active),
    is_featured: Boolean(plan.is_featured),
    credits_monthly: String(plan.credits_monthly ?? 0),
    plan_group: plan.plan_group ?? 'standard',
    job_limit: String(plan.job_limit ?? 0),
    cv_limit: String(plan.cv_limit ?? 0),
    ai_interview_limit: String(plan.ai_interview_limit ?? 0),
    team_seat_limit: String(plan.team_seat_limit ?? 0),
    candidate_cv_uploads_limit: String(plan.candidate_cv_uploads_limit ?? 0),
    candidate_ai_analyses_limit: String(plan.candidate_ai_analyses_limit ?? 0),
    candidate_pdf_downloads_limit: String(plan.candidate_pdf_downloads_limit ?? 0),
    candidate_job_matches_limit: String(plan.candidate_job_matches_limit ?? 0),
    features: Array.isArray(plan.features) ? JSON.stringify(plan.features) : (typeof plan.features === 'string' ? plan.features : '[]'),
    permissions_json: typeof plan.permissions_json === 'string' ? plan.permissions_json : JSON.stringify(plan.permissions_json ?? {}),
  };
}

export default function SubscriptionsManagerPage() {
  const [activeTab, setActiveTab] = useState('pending');
  const [pending, setPending] = useState<PendingSub[]>([]);
  const [active, setActive] = useState<ActiveSub[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [financeOverview, setFinanceOverview] = useState<Record<string, any>>({});
  const [invoices, setInvoices] = useState<any[]>([]);
  const [planDialogOpen, setPlanDialogOpen] = useState(false);
  const [historyDialogOpen, setHistoryDialogOpen] = useState(false);
  const [historyPlanName, setHistoryPlanName] = useState('');
  const [planVersions, setPlanVersions] = useState<PlanVersion[]>([]);
  const [planDraft, setPlanDraft] = useState<PlanDraft>({ ...defaultPlanDraft });
  const [draftId, setDraftId] = useState<number | null>(null);

  const [actionUser, setActionUser] = useState<ActiveSub | null>(null);
  const [actionKind, setActionKind] = useState<'change' | 'extend' | 'trial' | null>(null);
  const [selectedPlanId, setSelectedPlanId] = useState<string>('');
  const [days, setDays] = useState<string>('30');
  const [dialogOpen, setDialogOpen] = useState(false);

  const [rejectTarget, setRejectTarget] = useState<PendingSub | null>(null);
  const [rejectReason, setRejectReason] = useState('');
  const [rejectDialogOpen, setRejectDialogOpen] = useState(false);
  const [receiptTarget, setReceiptTarget] = useState<PendingSub | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [pend, act, pl, fin, inv] = await Promise.all([
        adminService.getSubscriptions<{ subscriptions: PendingSub[] }>({ per_page: 100 }),
        adminService.getActiveSubscriptions<{ subscriptions: ActiveSub[] }>({ per_page: 100 }),
        adminService.getPlans<{ plans: Plan[] }>({ per_page: 200 }),
        adminService.getFinanceOverview<Record<string, any>>(),
        adminService.getInvoices({ page: 1, per_page: 10 }),
      ]);
      setPending(pend.subscriptions ?? []);
      setActive(act.subscriptions ?? []);
      setPlans(pl.plans ?? []);
      setFinanceOverview(fin ?? {});
      setInvoices(inv?.invoices ?? []);
    } catch (err) {
      customToast({ type: 'error', title: 'Subscriptions', message: 'Failed to load subs / plans / billing data.' });
      console.error('subscriptions load error', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const refetch = async () => { await load(); };

  const openPlanEditor = (plan?: Plan) => {
    setDraftId(plan ? plan.id : null);
    setPlanDraft(normalizePlanDraft(plan));
    setPlanDialogOpen(true);
  };

  const closePlanEditor = () => {
    setPlanDialogOpen(false);
    setDraftId(null);
    setPlanDraft({ ...defaultPlanDraft });
  };

  const openPlanHistory = async (plan: Plan) => {
    try {
      const resp = await adminService.getPlanVersions<{ versions?: PlanVersion[] }>(plan.id);
      setPlanVersions(resp?.versions ?? []);
      setHistoryPlanName(plan.name);
      setHistoryDialogOpen(true);
    } catch (err) {
      customToast({ type: 'error', title: 'Versions', message: 'Unable to load plan version history.' });
      console.error(err);
    }
  };

  const savePlan = async () => {
    try {
      const payload: Record<string, any> = {
        name: planDraft.name,
        slug: planDraft.slug,
        target_audience: planDraft.target_audience,
        price_monthly: Number(planDraft.price_monthly || 0),
        price_yearly: Number(planDraft.price_yearly || 0),
        currency: planDraft.currency,
        is_active: Boolean(planDraft.is_active),
        is_featured: Boolean(planDraft.is_featured),
        credits_monthly: Number(planDraft.credits_monthly || 0),
        plan_group: planDraft.plan_group,
        job_limit: Number(planDraft.job_limit || 0),
        cv_limit: Number(planDraft.cv_limit || 0),
        ai_interview_limit: Number(planDraft.ai_interview_limit || 0),
        team_seat_limit: Number(planDraft.team_seat_limit || 0),
        candidate_cv_uploads_limit: Number(planDraft.candidate_cv_uploads_limit || 0),
        candidate_ai_analyses_limit: Number(planDraft.candidate_ai_analyses_limit || 0),
        candidate_pdf_downloads_limit: Number(planDraft.candidate_pdf_downloads_limit || 0),
        candidate_job_matches_limit: Number(planDraft.candidate_job_matches_limit || 0),
        features: planDraft.features || '[]',
        permissions_json: planDraft.permissions_json || '{}',
      };

      if (draftId) {
        await adminService.updatePlan(draftId, payload);
        customToast({ type: 'success', title: 'Plan updated', message: `${payload.name} was saved.` });
      } else {
        await adminService.createPlan(payload);
        customToast({ type: 'success', title: 'Plan created', message: `${payload.name} was created.` });
      }

      closePlanEditor();
      await refetch();
    } catch (err) {
      customToast({ type: 'error', title: 'Plan save failed', message: (err as Error).message || 'Could not save this plan.' });
    }
  };

  const archivePlan = async (plan: Plan) => {
    try {
      if (plan.is_active) {
        await adminService.archivePlan(plan.id);
      } else {
        await adminService.activatePlan(plan.id);
      }
      customToast({ type: 'success', title: 'Plan updated', message: `${plan.name} status changed.` });
      await refetch();
    } catch (err) {
      customToast({ type: 'error', title: 'Plan status failed', message: (err as Error).message || 'Could not change status.' });
    }
  };

  const duplicatePlan = async (plan: Plan) => {
    try {
      await adminService.duplicatePlan(plan.id, {
        name: `${plan.name} Copy`,
        slug: `${plan.slug}-copy-${Date.now().toString().slice(-6)}`,
      });
      customToast({ type: 'success', title: 'Plan duplicated', message: `${plan.name} was cloned.` });
      await refetch();
    } catch (err) {
      customToast({ type: 'error', title: 'Duplicate failed', message: (err as Error).message || 'Could not duplicate plan.' });
    }
  };

  const deletePlan = async (plan: Plan) => {
    try {
      await adminService.deletePlan(plan.id);
      customToast({ type: 'success', title: 'Plan deleted', message: `${plan.name} removed.` });
      await refetch();
    } catch (err) {
      customToast({ type: 'error', title: 'Delete failed', message: (err as Error).message || 'Could not delete this plan.' });
    }
  };

  const handleApprove = async (tx: PendingSub) => {
    setBusyId(tx.id);
    try {
      await adminService.approveSubscription(tx.id);
      customToast({ type: 'success', title: 'Approved', message: `Subscription for ${tx.user_email} approved.` });
      await refetch();
    } catch (err) {
      customToast({ type: 'error', title: 'Approval Failed', message: (err as Error).message || 'Could not approve.' });
    } finally {
      setBusyId(null);
    }
  };

  const handleReject = async (tx: PendingSub) => {
    setRejectTarget(tx);
    setRejectReason('');
    setRejectDialogOpen(true);
  };

  const confirmReject = async () => {
    if (!rejectTarget) return;
    setBusyId(rejectTarget.id);
    try {
      await adminService.rejectSubscription(rejectTarget.id, rejectReason.trim() || undefined);
      customToast({ type: 'info', title: 'Rejected', message: `Subscription for ${rejectTarget.user_email} rejected.` });
      setRejectDialogOpen(false);
      setRejectTarget(null);
      setRejectReason('');
      await refetch();
    } catch (err) {
      customToast({ type: 'error', title: 'Rejection Failed', message: (err as Error).message || 'Could not reject.' });
    } finally {
      setBusyId(null);
    }
  };

  const openAction = (sub: ActiveSub, kind: 'change' | 'extend' | 'trial') => {
    setActionUser(sub);
    setActionKind(kind);
    setSelectedPlanId('');
    setDays(kind === 'trial' ? '14' : '30');
    setDialogOpen(true);
  };

  const runAction = async () => {
    if (!actionUser || !actionKind) return;
    setBusyId(actionUser.id);
    try {
      const userId = actionUser.id;
      if (actionKind === 'change') {
        if (!selectedPlanId) throw new Error('Select a plan.');
        await adminService.changePlan(userId, Number(selectedPlanId));
        customToast({ type: 'success', title: 'Plan Changed', message: `Plan updated for ${actionUser.email}.` });
      } else if (actionKind === 'extend') {
        await adminService.extendSubscription(userId, Number(days) || 30);
        customToast({ type: 'success', title: 'Extended', message: `Subscription extended by ${days || 30} days.` });
      } else {
        if (!selectedPlanId) throw new Error('Select a plan.');
        await adminService.startTrial(userId, Number(selectedPlanId), Number(days) || 14);
        customToast({ type: 'success', title: 'Trial Started', message: `Trial started for ${actionUser.email}.` });
      }
      setDialogOpen(false);
      await refetch();
    } catch (err) {
      customToast({ type: 'error', title: 'Action Failed', message: (err as Error).message || 'Operation failed.' });
    } finally {
      setBusyId(null);
    }
  };

  const runQuick = async (sub: ActiveSub, kind: 'cancel' | 'expire' | 'reinstate') => {
    setBusyId(sub.id);
    try {
      if (kind === 'cancel') {
        await adminService.cancelSubscription(sub.id);
        customToast({ type: 'warning', title: 'Canceled', message: `Subscription canceled for ${sub.email}.` });
      } else if (kind === 'expire') {
        await adminService.expireSubscription(sub.id);
        customToast({ type: 'info', title: 'Expired', message: `Subscription expired for ${sub.email}.` });
      } else {
        await adminService.reinstateSubscription(sub.id);
        customToast({ type: 'success', title: 'Reinstated', message: `Subscription reinstated for ${sub.email}.` });
      }
      await refetch();
    } catch (err) {
      customToast({ type: 'error', title: 'Operation Failed', message: (err as Error).message || 'Could not perform action.' });
    } finally {
      setBusyId(null);
    }
  };

  const filteredPending = useMemo(() => pending.filter((p) => (
    (p.user_email || '').toLowerCase().includes(search.toLowerCase()) ||
    (p.user_name || '').toLowerCase().includes(search.toLowerCase())
  )), [pending, search]);

  const filteredActive = useMemo(() => active.filter((s) => (
    (s.email || '').toLowerCase().includes(search.toLowerCase()) ||
    (s.name || '').toLowerCase().includes(search.toLowerCase())
  )), [active, search]);

  const filteredPlans = useMemo(() => plans.filter((plan) => {
    const q = search.toLowerCase();
    return (
      (plan.name || '').toLowerCase().includes(q) ||
      (plan.slug || '').toLowerCase().includes(q) ||
      (plan.target_audience || '').toLowerCase().includes(q)
    );
  }), [plans, search]);

  const totalActive = active.filter((s) => s.status === 'active').length;
  const monthlyRevenue = plans.reduce((sum, plan) => sum + (plan.is_active ? Number(plan.price_monthly || 0) : 0), 0);
  const mrrValue = Number(financeOverview?.revenue?.mrr ?? 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-2xl font-black text-gray-900 dark:text-white">Subscriptions & Billing</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Approve manual bank-transfer payments, manage lifecycle operations, and maintain the live plan catalog.</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" leftIcon={<RefreshCw className="h-4 w-4" />} onClick={load}>Sync</Button>
          <Button variant="primary" leftIcon={<Plus className="h-4 w-4" />} onClick={() => openPlanEditor()}>New Plan</Button>
        </div>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center gap-3 py-24">
          <div className="h-10 w-10 animate-spin rounded-full border-2 border-purple-600 border-t-transparent" />
          <span className="text-sm text-gray-500">Loading subscriptions...</span>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-4">
            {[
              { label: 'Pending Approvals', value: String(pending.length), icon: Clock, color: 'bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400' },
              { label: 'Active', value: String(totalActive), icon: CreditCard, color: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400' },
              { label: 'Trialing', value: String(active.filter((s) => s.status === 'trialing').length), icon: Gift, color: 'bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400' },
              { label: 'Monthly revenue', value: fmtMoney(monthlyRevenue), icon: Wallet, color: 'bg-violet-50 text-violet-600 dark:bg-violet-500/10 dark:text-violet-400' },
              { label: 'MRR', value: fmtMoney(mrrValue), icon: TrendingUp, color: 'bg-rose-50 text-rose-600 dark:bg-rose-500/10 dark:text-rose-400' },
            ].map((stat) => (
              <div key={stat.label}>
                <Card className="glass-panel border-purple-200/50 dark:border-purple-500/20">
                  <CardContent className="p-5">
                    <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${stat.color}`}>
                      <stat.icon className="h-5 w-5" />
                    </div>
                    <div className="mt-3">
                      <div className="text-xl font-bold text-gray-900 dark:text-white">{stat.value}</div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">{stat.label}</div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            ))}
          </div>

          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList>
              <TabsTrigger value="pending">Pending Approvals</TabsTrigger>
              <TabsTrigger value="active">Active Subscriptions</TabsTrigger>
              <TabsTrigger value="plans">Plans</TabsTrigger>
            </TabsList>

            <TabsContent value="pending">
              <Card className="glass-panel border-purple-200/50">
                <CardHeader>
                  <div className="flex items-center justify-between w-full gap-3">
                    <div>
                      <CardTitle>Bank Transfer Approval Queue</CardTitle>
                      <CardDescription>Verify proofs then approve or reject. Approved payments activate the subscription and grant credits.</CardDescription>
                    </div>
                    <div className="flex items-center gap-2">
                      <Input placeholder="Search customer..." leftIcon={<Search className="h-4 w-4" />} value={search} onChange={(e) => setSearch(e.target.value)} wrapperClassName="w-64" />
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  {filteredPending.length === 0 ? (
                    <p className="py-8 text-center text-sm text-gray-500 dark:text-gray-400">No pending approvals. New bank transfers will appear here.</p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left">
                        <thead>
                          <tr className="border-b border-purple-100 dark:border-white/10">
                            <th className="py-3 text-xs font-bold text-gray-500 uppercase">Customer</th>
                            <th className="py-3 text-xs font-bold text-gray-500 uppercase">Amount</th>
                            <th className="py-3 text-xs font-bold text-gray-500 uppercase">Status</th>
                            <th className="py-3 text-xs font-bold text-gray-500 uppercase">Date</th>
                            <th className="py-3 text-xs font-bold text-gray-500 uppercase text-right">Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {filteredPending.map((tx) => (
                            <tr key={tx.id} className="border-b border-gray-50 dark:border-white/[0.02] hover:bg-purple-50/50 dark:hover:bg-white/[0.02] transition-colors">
                              <td className="py-3">
                                <div className="flex items-center gap-2">
                                  <Avatar name={tx.user_name || tx.user_email} size="sm" square />
                                  <div>
                                    <span className="block text-sm font-extrabold text-gray-900 dark:text-white">{tx.user_name || 'Unknown'}</span>
                                    <span className="block text-xs text-gray-500">{tx.user_email}</span>
                                  </div>
                                </div>
                              </td>
                              <td className="py-3">
                                <span className="text-sm font-bold text-gray-900 dark:text-white">{fmtMoney(tx.amount)}</span>
                                <span className="block text-xs text-gray-500">{tx.description || tx.type}</span>
                              </td>
                              <td className="py-3">
                                <Badge variant="warning" size="sm" dot>pending</Badge>
                              </td>
                              <td className="py-3 text-sm text-gray-500 font-medium">{fmtDate(tx.date)}</td>
                              <td className="py-3 text-right">
                                <div className="flex items-center justify-end gap-2">
                                  {tx.proof_url && (
                                    <Button
                                      variant="outline"
                                      size="sm"
                                      leftIcon={<Eye className="h-3.5 w-3.5 text-blue-500" />}
                                      onClick={() => setReceiptTarget(tx)}
                                    >
                                      Receipt
                                    </Button>
                                  )}
                                  <Button variant="success" size="sm" disabled={busyId === tx.id} leftIcon={<CheckCircle2 className="h-3.5 w-3.5" />} onClick={() => handleApprove(tx)}>
                                    Approve
                                  </Button>
                                  <Button variant="outline" size="sm" disabled={busyId === tx.id} leftIcon={<XCircle className="h-3.5 w-3.5 text-red-500" />} onClick={() => handleReject(tx)}>
                                    Reject
                                  </Button>
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
            </TabsContent>

            <TabsContent value="active">
              <Card className="glass-panel border-purple-200/50">
                <CardHeader>
                  <div className="flex items-center justify-between w-full gap-3">
                    <div>
                      <CardTitle>Active Subscriptions</CardTitle>
                      <CardDescription>{active.length} total · {totalActive} active · {active.filter((s) => s.status === 'trialing').length} trialing</CardDescription>
                    </div>
                    <Input placeholder="Search..." leftIcon={<Search className="h-4 w-4" />} value={search} onChange={(e) => setSearch(e.target.value)} wrapperClassName="w-64" />
                  </div>
                </CardHeader>
                <CardContent>
                  {filteredActive.length === 0 ? (
                    <p className="py-8 text-center text-sm text-gray-500 dark:text-gray-400">No active subscriptions found.</p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left">
                        <thead>
                          <tr className="border-b border-purple-100 dark:border-white/10">
                            <th className="py-3 text-xs font-bold text-gray-500 uppercase">Recruiter</th>
                            <th className="py-3 text-xs font-bold text-gray-500 uppercase">Status</th>
                            <th className="py-3 text-xs font-bold text-gray-500 uppercase">Ends</th>
                            <th className="py-3 text-xs font-bold text-gray-500 uppercase text-right">Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {filteredActive.map((sub) => (
                            <tr key={sub.id} className="border-b border-gray-50 dark:border-white/[0.02] hover:bg-purple-50/50 dark:hover:bg-white/[0.02] transition-colors">
                              <td className="py-3">
                                <div className="flex items-center gap-2">
                                  <Avatar name={sub.name || sub.email} size="sm" square />
                                  <div>
                                    <span className="block text-sm font-extrabold text-gray-900 dark:text-white">{sub.name || 'Unknown'}</span>
                                    <span className="block text-xs text-gray-500">{sub.email}</span>
                                  </div>
                                </div>
                              </td>
                              <td className="py-3">
                                <Badge variant={statusVariant[sub.status] || 'default'} size="sm" dot>{sub.status}</Badge>
                              </td>
                              <td className="py-3 text-sm text-gray-500 font-medium">{fmtDate(sub.subscription_end)}</td>
                              <td className="py-3 text-right">
                                <SimpleDropdown
                                  trigger={<button className="p-2 rounded-lg hover:bg-purple-100 dark:hover:bg-white/10 transition-colors"><MoreHorizontal className="h-4 w-4 text-gray-500" /></button>}
                                  items={[
                                    { label: 'Change Plan', icon: <RefreshCw className="h-4 w-4 text-amber-500" />, onClick: () => openAction(sub, 'change') },
                                    { label: 'Extend', icon: <CalendarPlus className="h-4 w-4 text-blue-500" />, onClick: () => openAction(sub, 'extend') },
                                    { label: 'Start Trial', icon: <Gift className="h-4 w-4 text-purple-500" />, onClick: () => openAction(sub, 'trial') },
                                    { label: 'Reinstate', icon: <RotateCcw className="h-4 w-4 text-emerald-500" />, onClick: () => runQuick(sub, 'reinstate') },
                                    { label: 'Expire', icon: <Ban className="h-4 w-4 text-amber-600" />, onClick: () => runQuick(sub, 'expire') },
                                    { label: 'Cancel', icon: <XCircle className="h-4 w-4 text-red-500" />, danger: true, onClick: () => runQuick(sub, 'cancel') },
                                  ]}
                                  align="end"
                                />
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="plans">
              <div className="space-y-4">
                <Card className="glass-panel border-purple-200/50">
                  <CardHeader>
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <CardTitle>Subscription Plans</CardTitle>
                        <CardDescription>CRUD, archive/activate, duplicate, version history, and production billing config.</CardDescription>
                      </div>
                      <div className="flex items-center gap-2">
                        <Input placeholder="Search plans" leftIcon={<Search className="h-4 w-4" />} value={search} onChange={(e) => setSearch(e.target.value)} wrapperClassName="w-64" />
                        <Button variant="primary" leftIcon={<Plus className="h-4 w-4" />} onClick={() => openPlanEditor()}>New Plan</Button>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    {filteredPlans.length === 0 ? (
                      <p className="py-8 text-center text-sm text-gray-500 dark:text-gray-400">No plans match the current search.</p>
                    ) : (
                      <div className="overflow-x-auto">
                        <table className="w-full text-left">
                          <thead>
                            <tr className="border-b border-purple-100 dark:border-white/10">
                              <th className="py-3 text-xs font-bold text-gray-500 uppercase">Plan</th>
                              <th className="py-3 text-xs font-bold text-gray-500 uppercase">Audience</th>
                              <th className="py-3 text-xs font-bold text-gray-500 uppercase">Monthly Price</th>
                              <th className="py-3 text-xs font-bold text-gray-500 uppercase">Credits</th>
                              <th className="py-3 text-xs font-bold text-gray-500 uppercase">Status</th>
                              <th className="py-3 text-xs font-bold text-gray-500 uppercase">Group</th>
                              <th className="py-3 text-xs font-bold text-gray-500 uppercase text-right">Actions</th>
                            </tr>
                          </thead>
                          <tbody>
                            {filteredPlans.map((plan) => (
                              <tr key={plan.id} className="border-b border-gray-50 dark:border-white/[0.02] hover:bg-purple-50/50 dark:hover:bg-white/[0.02] transition-colors">
                                <td className="py-3">
                                  <div className="font-extrabold text-gray-900 dark:text-white">{plan.name}</div>
                                  <div className="text-xs text-gray-500">{plan.slug}</div>
                                </td>
                                <td className="py-3">
                                  <Badge variant={plan.target_audience === 'candidate' ? 'info' : 'primary'} size="sm" className="uppercase text-[10px]">{plan.target_audience}</Badge>
                                </td>
                                <td className="py-3 text-sm font-bold text-gray-900 dark:text-white">{fmtMoney(plan.price_monthly)}</td>
                                <td className="py-3 text-sm text-gray-500 font-medium">{plan.credits_monthly}</td>
                                <td className="py-3">
                                  <Badge variant={plan.is_active ? 'success' : 'danger'} size="sm" dot>{plan.is_active ? 'active' : 'archived'}</Badge>
                                </td>
                                <td className="py-3 text-sm text-gray-500 font-medium">{plan.plan_group || 'standard'}</td>
                                <td className="py-3 text-right">
                                  <SimpleDropdown
                                    trigger={<button className="p-2 rounded-lg hover:bg-purple-100 dark:hover:bg-white/10 transition-colors"><MoreHorizontal className="h-4 w-4 text-gray-500" /></button>}
                                    items={[
                                      { label: 'Edit', icon: <Pencil className="h-4 w-4 text-amber-500" />, onClick: () => openPlanEditor(plan) },
                                      { label: 'Version history', icon: <Eye className="h-4 w-4 text-blue-500" />, onClick: () => openPlanHistory(plan) },
                                      { label: 'Duplicate', icon: <Copy className="h-4 w-4 text-purple-500" />, onClick: () => duplicatePlan(plan) },
                                      { label: plan.is_active ? 'Archive' : 'Activate', icon: <Archive className="h-4 w-4 text-amber-600" />, onClick: () => archivePlan(plan) },
                                      { label: 'Delete', icon: <XCircle className="h-4 w-4 text-red-500" />, danger: true, onClick: () => deletePlan(plan) },
                                    ]}
                                    align="end"
                                  />
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </CardContent>
                </Card>

                <Card className="glass-panel border-purple-200/50">
                  <CardHeader>
                    <CardTitle>Billing health</CardTitle>
                    <CardDescription>Latest finance overview and recent invoice activity</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="grid gap-3 md:grid-cols-3">
                      <div className="rounded-xl border border-purple-100 bg-purple-50/50 p-4">
                        <div className="text-xs uppercase text-gray-500">MRR</div>
                        <div className="mt-2 text-2xl font-black text-gray-900 dark:text-white">{fmtMoney(Number(financeOverview?.revenue?.mrr ?? 0))}</div>
                      </div>
                      <div className="rounded-xl border border-purple-100 bg-purple-50/50 p-4">
                        <div className="text-xs uppercase text-gray-500">ARR</div>
                        <div className="mt-2 text-2xl font-black text-gray-900 dark:text-white">{fmtMoney(Number(financeOverview?.revenue?.arr ?? 0))}</div>
                      </div>
                      <div className="rounded-xl border border-purple-100 bg-purple-50/50 p-4">
                        <div className="text-xs uppercase text-gray-500">Invoices</div>
                        <div className="mt-2 text-2xl font-black text-gray-900 dark:text-white">{invoices.length}</div>
                      </div>
                    </div>
                    <div className="mt-4 overflow-x-auto">
                      <table className="w-full text-left">
                        <thead>
                          <tr className="border-b border-purple-100 dark:border-white/10">
                            <th className="py-3 text-xs font-bold text-gray-500 uppercase">Invoice</th>
                            <th className="py-3 text-xs font-bold text-gray-500 uppercase">Customer</th>
                            <th className="py-3 text-xs font-bold text-gray-500 uppercase">Status</th>
                            <th className="py-3 text-xs font-bold text-gray-500 uppercase">Amount</th>
                          </tr>
                        </thead>
                        <tbody>
                          {invoices.length === 0 ? (
                            <tr>
                              <td colSpan={4} className="py-6 text-center text-sm text-gray-500">No recent invoices.</td>
                            </tr>
                          ) : (
                            invoices.slice(0, 5).map((invoice: any, index: number) => (
                              <tr key={invoice.id ?? index} className="border-b border-gray-50 dark:border-white/[0.02]">
                                <td className="py-3 text-sm font-medium text-gray-900 dark:text-white">#{invoice.id ?? index + 1}</td>
                                <td className="py-3 text-sm text-gray-500">{invoice.customer_name || invoice.user_name || 'Customer'}</td>
                                <td className="py-3"><Badge variant={invoice.status === 'paid' ? 'success' : invoice.status === 'pending' ? 'warning' : 'default'} size="sm">{invoice.status || 'pending'}</Badge></td>
                                <td className="py-3 text-sm font-bold text-gray-900 dark:text-white">{fmtMoney(Number(invoice.amount ?? 0), invoice.currency || 'TND')}</td>
                              </tr>
                            ))
                          )}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </TabsContent>
          </Tabs>
        </>
      )}

      <Dialog open={planDialogOpen} onOpenChange={setPlanDialogOpen}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>{draftId ? 'Edit plan' : 'Create plan'}</DialogTitle>
            <DialogDescription>Configure every supported plan field, including quotas, pricing, credits, and feature metadata.</DialogDescription>
          </DialogHeader>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Input label="Plan name" value={planDraft.name} onChange={(e) => setPlanDraft((prev) => ({ ...prev, name: e.target.value }))} />
            <Input label="Slug" value={planDraft.slug} onChange={(e) => setPlanDraft((prev) => ({ ...prev, slug: e.target.value }))} />
            <Input label="Monthly price" type="number" value={planDraft.price_monthly} onChange={(e) => setPlanDraft((prev) => ({ ...prev, price_monthly: e.target.value }))} />
            <Input label="Yearly price" type="number" value={planDraft.price_yearly} onChange={(e) => setPlanDraft((prev) => ({ ...prev, price_yearly: e.target.value }))} />
            <Input label="Currency" value={planDraft.currency} onChange={(e) => setPlanDraft((prev) => ({ ...prev, currency: e.target.value }))} />
            <Input label="Credits / month" type="number" value={planDraft.credits_monthly} onChange={(e) => setPlanDraft((prev) => ({ ...prev, credits_monthly: e.target.value }))} />
            <div>
              <label className="mb-2 block text-xs font-bold uppercase tracking-[0.2em] text-gray-500">Audience</label>
              <Select value={planDraft.target_audience} onValueChange={(value) => setPlanDraft((prev) => ({
                ...prev,
                target_audience: value,
                ...(value !== 'candidate' ? {
                  candidate_cv_uploads_limit: '0',
                  candidate_ai_analyses_limit: '0',
                  candidate_pdf_downloads_limit: '0',
                  candidate_job_matches_limit: '0',
                } : {}),
              }))}>
                <SelectTrigger>
                  <SelectValue placeholder="Audience" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="recruiter">Recruiter</SelectItem>
                  <SelectItem value="candidate">Candidate</SelectItem>
                  <SelectItem value="all">All</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="mb-2 block text-xs font-bold uppercase tracking-[0.2em] text-gray-500">Group</label>
              <Select value={planDraft.plan_group} onValueChange={(value) => setPlanDraft((prev) => ({ ...prev, plan_group: value }))}>
                <SelectTrigger>
                  <SelectValue placeholder="Group" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="free">Free</SelectItem>
                  <SelectItem value="standard">Standard</SelectItem>
                  <SelectItem value="pro">Pro</SelectItem>
                  <SelectItem value="enterprise">Enterprise</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Input label="Job limit" type="number" value={planDraft.job_limit} onChange={(e) => setPlanDraft((prev) => ({ ...prev, job_limit: e.target.value }))} />
            <Input label="CV limit" type="number" value={planDraft.cv_limit} onChange={(e) => setPlanDraft((prev) => ({ ...prev, cv_limit: e.target.value }))} />
            <Input label="AI interview limit" type="number" value={planDraft.ai_interview_limit} onChange={(e) => setPlanDraft((prev) => ({ ...prev, ai_interview_limit: e.target.value }))} />
            <Input label="Team seats" type="number" value={planDraft.team_seat_limit} onChange={(e) => setPlanDraft((prev) => ({ ...prev, team_seat_limit: e.target.value }))} />
            {planDraft.target_audience === 'candidate' && (
              <>
                <Input label="Candidate CV uploads" type="number" value={planDraft.candidate_cv_uploads_limit} onChange={(e) => setPlanDraft((prev) => ({ ...prev, candidate_cv_uploads_limit: e.target.value }))} />
                <Input label="Candidate AI analyses" type="number" value={planDraft.candidate_ai_analyses_limit} onChange={(e) => setPlanDraft((prev) => ({ ...prev, candidate_ai_analyses_limit: e.target.value }))} />
                <Input label="Candidate PDF downloads" type="number" value={planDraft.candidate_pdf_downloads_limit} onChange={(e) => setPlanDraft((prev) => ({ ...prev, candidate_pdf_downloads_limit: e.target.value }))} />
                <Input label="Candidate job matches" type="number" value={planDraft.candidate_job_matches_limit} onChange={(e) => setPlanDraft((prev) => ({ ...prev, candidate_job_matches_limit: e.target.value }))} />
              </>
            )}
            <div className="md:col-span-2">
              <label className="mb-2 block text-xs font-bold uppercase tracking-[0.2em] text-gray-500">Features JSON</label>
              <textarea className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700" rows={4} value={planDraft.features} onChange={(e) => setPlanDraft((prev) => ({ ...prev, features: e.target.value }))} />
            </div>
            <div className="md:col-span-2">
              <label className="mb-2 block text-xs font-bold uppercase tracking-[0.2em] text-gray-500">Permissions JSON</label>
              <textarea className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700" rows={4} value={planDraft.permissions_json} onChange={(e) => setPlanDraft((prev) => ({ ...prev, permissions_json: e.target.value }))} />
            </div>
            <div className="md:col-span-2 flex items-center gap-3">
              <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
                <input type="checkbox" checked={planDraft.is_active} onChange={(e) => setPlanDraft((prev) => ({ ...prev, is_active: e.target.checked }))} />
                Active
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
                <input type="checkbox" checked={planDraft.is_featured} onChange={(e) => setPlanDraft((prev) => ({ ...prev, is_featured: e.target.checked }))} />
                Featured
              </label>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={closePlanEditor}>Cancel</Button>
            <Button variant="primary" onClick={savePlan}>{draftId ? 'Save changes' : 'Create plan'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={historyDialogOpen} onOpenChange={setHistoryDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{historyPlanName} version history</DialogTitle>
            <DialogDescription>Immutable plan snapshots created when significant pricing or limit settings change.</DialogDescription>
          </DialogHeader>
          <div className="max-h-[420px] overflow-y-auto">
            {planVersions.length === 0 ? (
              <p className="py-8 text-center text-sm text-gray-500">No versions recorded for this plan yet.</p>
            ) : (
              <div className="space-y-3">
                {planVersions.map((version) => (
                  <div key={version.id} className="rounded-xl border border-purple-100 bg-purple-50/40 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-extrabold text-gray-900 dark:text-white">Version {version.version}</div>
                      <Badge variant="info" size="sm">{version.currency}</Badge>
                    </div>
                    <div className="mt-2 text-sm text-gray-600">Monthly: {fmtMoney(version.price_monthly, version.currency)} · Yearly: {fmtMoney(version.price_yearly, version.currency)}</div>
                    <div className="mt-2 text-xs text-gray-500">Created {fmtDate(version.created_at || version.valid_from)}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setHistoryDialogOpen(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {actionKind === 'change' ? 'Change Plan' : actionKind === 'extend' ? 'Extend Subscription' : 'Start Trial'}
            </DialogTitle>
            <DialogDescription>
              {actionUser ? `${actionUser.name || actionUser.email}` : ''}
            </DialogDescription>
          </DialogHeader>
          {actionKind && actionKind !== 'extend' && (
            <Select value={selectedPlanId} onValueChange={setSelectedPlanId}>
              <SelectTrigger><SelectValue placeholder="Select a plan..." /></SelectTrigger>
              <SelectContent>
                {plans.filter((p) => p.is_active).map((plan) => (
                  <SelectItem key={plan.id} value={String(plan.id)}>
                    {plan.name} — {fmtMoney(plan.price_monthly)} · {plan.credits_monthly} credits/mo
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          {actionKind === 'extend' && (
            <Input
              type="number"
              min={1}
              max={730}
              value={days}
              onChange={(e) => setDays(e.target.value)}
              placeholder="Days (1-730)"
            />
          )}
          {actionKind === 'trial' && (
            <Input
              type="number"
              min={1}
              max={90}
              value={days}
              onChange={(e) => setDays(e.target.value)}
              placeholder="Trial days (1-90)"
            />
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button variant="primary" disabled={busyId === actionUser?.id} onClick={runAction}>
              {busyId === actionUser?.id ? 'Working...' : 'Confirm'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={receiptTarget !== null} onOpenChange={(open) => { if (!open) setReceiptTarget(null); }}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Payment Receipt</DialogTitle>
            <DialogDescription>
              {receiptTarget ? `${receiptTarget.user_name} · ${receiptTarget.user_email} · ${fmtMoney(receiptTarget.amount)}` : ''}
            </DialogDescription>
          </DialogHeader>
          {receiptTarget?.proof_url ? (
            <div className="overflow-hidden rounded-xl border border-gray-200 dark:border-white/10">
              {receiptTarget.proof_url.match(/\.(png|jpe?g|gif|webp)(\?|$)/i) ? (
                <img
                  src={`/${receiptTarget.proof_url}`}
                  alt="Payment receipt"
                  className="max-h-[420px] w-full object-contain bg-white"
                />
              ) : (
                <iframe
                  src={`/${receiptTarget.proof_url}`}
                  title="Payment receipt"
                  className="h-[420px] w-full bg-white"
                />
              )}
            </div>
          ) : (
            <p className="py-6 text-center text-sm text-gray-500">No receipt was uploaded for this payment.</p>
          )}
          <DialogFooter className="flex items-center justify-between">
            {receiptTarget?.proof_url && (
              <Button variant="outline" size="sm" onClick={() => window.open(`/${receiptTarget.proof_url}`, '_blank')}>
                Open full size
              </Button>
            )}
            <div className="flex items-center gap-2">
              <Button variant="outline" onClick={() => setReceiptTarget(null)}>Close</Button>
              {receiptTarget && (
                <>
                  <Button
                    variant="success"
                    disabled={busyId === receiptTarget.id}
                    leftIcon={<CheckCircle2 className="h-3.5 w-3.5" />}
                    onClick={() => { const t = receiptTarget; setReceiptTarget(null); handleApprove(t); }}
                  >
                    Approve
                  </Button>
                  <Button
                    variant="outline"
                    disabled={busyId === receiptTarget.id}
                    leftIcon={<XCircle className="h-3.5 w-3.5 text-red-500" />}
                    onClick={() => { const t = receiptTarget; setReceiptTarget(null); handleReject(t); }}
                  >
                    Reject
                  </Button>
                </>
              )}
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={rejectDialogOpen} onOpenChange={setRejectDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reject payment request</DialogTitle>
            <DialogDescription>
              {rejectTarget ? `${rejectTarget.user_name} · ${rejectTarget.user_email} · ${fmtMoney(rejectTarget.amount)}` : ''}
            </DialogDescription>
          </DialogHeader>
          <label className="mb-2 block text-xs font-bold uppercase tracking-[0.2em] text-gray-500">
            Reason (sent to the user)
          </label>
          <textarea
            className="w-full rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 px-3 py-2 text-sm text-gray-700 dark:text-gray-200"
            rows={3}
            placeholder="e.g. Receipt illegible — please re-upload a clearer screenshot of the transfer."
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setRejectDialogOpen(false)}>Cancel</Button>
            <Button variant="danger" disabled={busyId === rejectTarget?.id} onClick={confirmReject}>
              {busyId === rejectTarget?.id ? 'Rejecting...' : 'Confirm Rejection'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
