// ============================================================
// Admin Treasury & Payments - Candway (Monetization S8)
// Real data from /admin/finance/* endpoints
// ============================================================

import { useCallback, useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/shared/components/ui/tabs';
import { customToast } from '@/shared/components/ui/toast';
import { cn } from '@/utils/cn';
import {
  TrendingUp, TrendingDown, DollarSign, CreditCard, Download, RefreshCw,
  Search, Receipt,
} from 'lucide-react';
import { adminService } from '@/services/admin.service';

interface ByMonthRow { month: string; revenue: number }

interface RevenueData {
  today: number; this_month: number; this_year: number; total: number;
  prev_month: number; month_over_month_growth: number; mrr: number; arr: number;
  by_plan: { plan: string; revenue: number; count: number }[]; by_month: ByMonthRow[];
}

interface CustomerData {
  total_users: number; recruiters: number; candidates: number; admins: number;
  subscriptions: Record<string, number>;
  payments: Record<string, number>;
  monthly_churn: number; arpu: number; arpcompany: number; ltv: number;
  lifecycle: Record<string, number>;
  top_payers: { user_id: number; email: string; revenue: number; transactions: number }[];
}

function fmtMoney(v: number | null | undefined): string {
  const n = Number(v || 0);
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k TND` : `${n.toFixed(0)} TND`;
}

export default function PaymentsPage() {
  const [activeTab, setActiveTab] = useState('transactions');
  const [search, setSearch] = useState('');
  const [revenue, setRevenue] = useState<RevenueData | null>(null);
  const [customers, setCustomers] = useState<CustomerData | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const [rev, cust] = await Promise.all([
        adminService.getFinanceRevenue<RevenueData>(6),
        adminService.getFinanceCustomers<CustomerData>(),
      ]);
      setRevenue(rev);
      setCustomers(cust);
    } catch (err) {
      customToast({ type: 'error', title: 'Treasury & Payments', message: 'Failed to load payment data.' });
      console.error('payments load error', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const payers = customers?.top_payers ?? [];
  const filteredPayers = payers.filter(p =>
    p.email.toLowerCase().includes(search.toLowerCase()) ||
    String(p.user_id).toLowerCase().includes(search.toLowerCase())
  );

  const payments = customers?.payments ?? {};
  const successful = payments.approved ?? 0;
  const pending = payments.pending ?? 0;
  const rejected = payments.rejected ?? 0;
  const totalTx = successful + pending + rejected;
  const successRate = totalTx > 0 ? ((successful / totalTx) * 100).toFixed(1) : '0.0';

  const maxRev = Math.max(0, ...(revenue?.by_month ?? []).map(m => m.revenue));

  const handleExportCSV = () => {
    adminService.exportFinance('overview', 'csv')
      .then(() => customToast({ type: 'success', title: 'CSV Export', message: 'Finance overview exported as CSV.' }))
      .catch(() => customToast({ type: 'error', title: 'CSV Export', message: 'Export failed.' }));
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Treasury & Payments</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Monitor revenue, approved payments, and top payers</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" leftIcon={<RefreshCw className="h-4 w-4" />} onClick={load}>Sync</Button>
          <Button variant="primary" leftIcon={<Download className="h-4 w-4" />} onClick={handleExportCSV}>Export CSV</Button>
        </div>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center gap-3 py-24">
          <div className="h-10 w-10 animate-spin rounded-full border-2 border-purple-600 border-t-transparent" />
          <span className="text-sm text-gray-500">Loading payment data...</span>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { label: 'Total Revenue', value: fmtMoney(revenue?.total), icon: TrendingUp, change: revenue ? `${revenue.month_over_month_growth.toFixed(1)}% MoM` : '—', color: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400' },
              { label: 'Approved Payments', value: String(successful), icon: CreditCard, change: `${successRate}% rate`, color: 'bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400' },
              { label: 'Pending Approval', value: String(pending), icon: DollarSign, change: 'manual review', color: 'bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400' },
              { label: 'Rejected Payments', value: String(rejected), icon: TrendingDown, change: 'reviewed', color: 'bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-400' },
            ].map((stat, i) => (
              <motion.div key={stat.label} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: i * 0.05 }}>
                <Card className="glass-panel border-purple-200/50 dark:border-purple-500/20">
                  <CardContent className="p-5">
                    <div className="flex items-center justify-between">
                      <div className={cn('flex h-10 w-10 items-center justify-center rounded-xl', stat.color)}>
                        <stat.icon className="h-5 w-5" />
                      </div>
                      <span className={cn('text-xs font-medium', stat.label === 'Rejected Payments' ? 'text-red-500' : 'text-emerald-500')}>
                        {stat.change}
                      </span>
                    </div>
                    <div className="mt-3">
                      <div className="text-2xl font-bold text-gray-900 dark:text-white">{stat.value}</div>
                      <div className="text-sm text-gray-500 dark:text-gray-400">{stat.label}</div>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>

          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList>
              <TabsTrigger value="transactions">Top Payers</TabsTrigger>
              <TabsTrigger value="payouts">Subscription Health</TabsTrigger>
              <TabsTrigger value="overview">Overview</TabsTrigger>
            </TabsList>

            <TabsContent value="transactions">
              <Card className="glass-panel border-purple-200/50 dark:border-purple-500/20">
                <CardHeader>
                  <div className="flex items-center justify-between w-full">
                    <div>
                      <CardTitle>Top Paying Customers</CardTitle>
                      <CardDescription>Highest lifetime revenue from approved bank transfers</CardDescription>
                    </div>
                    <div className="flex items-center gap-2">
                      <Input placeholder="Search payers..." leftIcon={<Search className="h-4 w-4" />} value={search} onChange={(e) => setSearch(e.target.value)} wrapperClassName="w-56" />
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  {filteredPayers.length === 0 ? (
                    <p className="py-8 text-center text-sm text-gray-500 dark:text-gray-400">
                      {search ? 'No payers match your search.' : 'No approved payments yet.'}
                    </p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left">
                        <thead>
                          <tr className="border-b border-purple-100 dark:border-white/10">
                            <th className="py-3 text-xs font-bold text-gray-500 uppercase">Customer</th>
                            <th className="py-3 text-xs font-bold text-gray-500 uppercase">Amount</th>
                            <th className="py-3 text-xs font-bold text-gray-500 uppercase">Transactions</th>
                            <th className="py-3 text-xs font-bold text-gray-500 uppercase">Status</th>
                            <th className="py-3 text-xs font-bold text-gray-500 uppercase text-right">Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {filteredPayers.map((p, i) => (
                            <motion.tr key={p.user_id} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.2, delay: i * 0.02 }}
                              className="border-b border-gray-50 dark:border-white/[0.02] hover:bg-purple-50/50 dark:hover:bg-white/[0.02] transition-colors">
                              <td className="py-3 text-sm font-bold text-gray-900 dark:text-white">{p.email}</td>
                              <td className="py-3 text-sm font-bold text-emerald-600 dark:text-emerald-400">{p.revenue.toFixed(2)} TND</td>
                              <td className="py-3 text-sm text-gray-500">{p.transactions}</td>
                              <td className="py-3">
                                <Badge variant="success" size="sm" dot>approved</Badge>
                              </td>
                              <td className="py-3 text-right">
                                <Button variant="ghost" size="xs" onClick={() => customToast({ type: 'info', title: 'Payer', message: `Viewing ${p.email}` })}>
                                  <Receipt className="h-3.5 w-3.5 text-purple-500" />
                                </Button>
                              </td>
                            </motion.tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="payouts">
              <Card className="glass-panel border-purple-200/50 dark:border-purple-500/20">
                <CardHeader>
                  <CardTitle>Subscription Lifecycle</CardTitle>
                  <CardDescription>Active subscribers and renewal/upgrade/downgrade rates</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {Object.entries(customers?.subscriptions ?? {}).map(([key, value]) => (
                      <div key={key} className="p-4 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10 text-center">
                        <p className="text-2xl font-bold text-gray-900 dark:text-white">{value}</p>
                        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400 capitalize">{key.replace('_', ' ')}</p>
                      </div>
                    ))}
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
                    {[
                      { label: 'Renewal Rate', value: customers?.lifecycle?.renewal_rate ?? 0 },
                      { label: 'Upgrade Rate', value: customers?.lifecycle?.upgrade_rate ?? 0 },
                      { label: 'Downgrade Rate', value: customers?.lifecycle?.downgrade_rate ?? 0 },
                    ].map((m) => (
                      <div key={m.label} className="p-4 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10 text-center">
                        <p className="text-2xl font-bold text-purple-600 dark:text-purple-400">{m.value}%</p>
                        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{m.label}</p>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="overview">
              <Card className="glass-panel border-purple-200/50 dark:border-purple-500/20">
                <CardHeader>
                  <CardTitle>Monthly Revenue Overview</CardTitle>
                  <CardDescription>Approved bank-transfer revenue for the last 6 months</CardDescription>
                </CardHeader>
                <CardContent>
                  {revenue && revenue.by_month.length > 0 ? (
                    <>
                      <div className="flex items-end justify-between gap-3 h-48 px-2">
                        {(revenue.by_month ?? []).map((m) => (
                          <div key={m.month} className="flex-1 flex flex-col items-center gap-1 h-full justify-end">
                            <div className="w-full flex flex-col items-center gap-0.5">
                              <div
                                className="w-full rounded-t-md bg-gradient-to-t from-purple-600 to-violet-500 transition-all duration-500 hover:from-purple-500 hover:to-violet-400"
                                style={{ height: `${maxRev > 0 ? (m.revenue / maxRev) * 100 : 0}%` }}
                              />
                            </div>
                            <span className="text-xs font-medium text-gray-500 dark:text-gray-400 mt-1">{m.month}</span>
                          </div>
                        ))}
                      </div>
                      <div className="flex items-center justify-center gap-6 mt-6 pt-4 border-t border-gray-100 dark:border-white/10">
                        <div className="flex items-center gap-2">
                          <div className="h-3 w-3 rounded-sm bg-gradient-to-t from-purple-600 to-violet-500" />
                          <span className="text-xs text-gray-600 dark:text-gray-400">Revenue</span>
                        </div>
                      </div>
                    </>
                  ) : (
                    <p className="py-8 text-center text-sm text-gray-500 dark:text-gray-400">No revenue recorded in the last 6 months.</p>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  );
}
