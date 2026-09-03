// ============================================================
// Admin Finance Dashboard - Candway (Monetization S8)
// Real KPIs from /admin/finance/* + Recharts visualizations
// ============================================================

import { useCallback, useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/shared/components/ui/tabs';
import { customToast } from '@/shared/components/ui/toast';
import { cn } from '@/utils/cn';
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, LineChart, Line, PieChart, Pie, Cell,
} from 'recharts';
import { TrendingUp, TrendingDown, Wallet, Users, CreditCard, Download, RefreshCw, Coins, Activity, DollarSign } from 'lucide-react';
import { adminService } from '@/services/admin.service';

interface ByPlanRow { plan: string; revenue: number; count: number }
interface ByMonthRow { month: string; revenue: number }
interface ForecastRow { month: string; projected_revenue: number }
interface FeatureRow { resource: string; count: number; credits: number; cost_usd: number }

interface RevenueData {
  today: number; this_month: number; this_year: number; total: number;
  prev_month: number; month_over_month_growth?: number; mrr: number; arr: number;
  by_plan: ByPlanRow[]; by_month: ByMonthRow[];
}

interface CustomerData {
  total_users: number; recruiters: number; candidates: number; admins: number;
  subscriptions: Record<string, number>;
  payments: Record<string, number>;
  monthly_churn: number; arpu: number; arpcompany: number; ltv: number;
  lifecycle: Record<string, number>;
  top_payers: { user_id: number; email: string; revenue: number; transactions: number }[];
}

interface CreditsData {
  credits_granted: number; credits_consumed: number; active_balance: number; wallets: number;
  ai_cost_usd: number; gross_margin_pct: number; ai_profit_usd: number;
  features: FeatureRow[]; by_resource: { resource: string; credits: number }[];
}

interface ForecastData {
  based_on: ByMonthRow[]; projected: ForecastRow[]; next_12m_arr: number;
}

const PIE_COLORS = ['#7c3aed', '#6366f1', '#8b5cf6', '#a855f7', '#d946ef', '#ec4899', '#f59e0b', '#10b981', '#0ea5e9', '#f43f5e'];

function fmtMoney(v: number | null | undefined): string {
  const n = Number(v || 0);
  return n >= 1000 ? `$${(n / 1000).toFixed(1)}k` : `$${n.toFixed(0)}`;
}

function fmtNum(v: number | null | undefined): string {
  return Number(v || 0).toLocaleString('en-US');
}

export default function FinanceDashboardPage() {
  const [activeTab, setActiveTab] = useState('overview');
  const [revenue, setRevenue] = useState<RevenueData | null>(null);
  const [customers, setCustomers] = useState<CustomerData | null>(null);
  const [credits, setCredits] = useState<CreditsData | null>(null);
  const [forecast, setForecast] = useState<ForecastData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadAll = useCallback(async () => {
    try {
      const [rev, cust, cred, fc] = await Promise.all([
        adminService.getFinanceRevenue<RevenueData>(6),
        adminService.getFinanceCustomers<CustomerData>(),
        adminService.getFinanceCredits<CreditsData>(),
        adminService.getFinanceForecast<ForecastData>(3),
      ]);
      setRevenue(rev);
      setCustomers(cust);
      setCredits(cred);
      setForecast(fc);
    } catch (err) {
      customToast({ type: 'error', title: 'Finance Dashboard', message: 'Failed to load financial data.' });
      console.error('finance dashboard load error', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);

  const handleRefresh = () => {
    setRefreshing(true);
    loadAll();
  };

  const handleExport = (section: string, format: 'csv' | 'pdf') => {
    adminService.exportFinance(section, format)
      .then(() => customToast({ type: 'success', title: 'Export', message: `Finance ${section} exported as ${format.toUpperCase()}.` }))
      .catch(() => customToast({ type: 'error', title: 'Export', message: 'Export failed.' }));
  };

  const churnUp = (customers?.monthly_churn ?? 0) > 0;

  const kpis = [
    { label: 'Total Revenue (All Time)', value: fmtMoney(revenue?.total), icon: DollarSign, color: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400', change: revenue ? `MRR $${fmtMoney(revenue.mrr)}` : '—' },
    { label: 'Revenue This Month', value: fmtMoney(revenue?.this_month), icon: TrendingUp, color: 'bg-purple-50 text-purple-600 dark:bg-purple-500/10 dark:text-purple-400', change: revenue ? `${(revenue.month_over_month_growth ?? 0).toFixed(1)}% MoM` : '—' },
    { label: 'Active Subscriptions', value: customers ? String(customers.subscriptions?.active ?? 0) : '—', icon: CreditCard, color: 'bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400', change: `ARPU $${fmtMoney(customers?.arpu)}` },
    { label: 'AI Gross Margin', value: credits ? `${(credits.gross_margin_pct ?? 0).toFixed(1)}%` : '—', icon: Activity, color: 'bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400', change: credits ? `Profit $${fmtMoney(credits.ai_profit_usd)}` : '—' },
  ];

  const statCards = [
    { label: 'Total Users', value: fmtNum(customers?.total_users), icon: Users, color: 'bg-purple-50 text-purple-600 dark:bg-purple-500/10 dark:text-purple-400' },
    { label: 'Monthly Churn', value: customers ? `${((customers.monthly_churn ?? 0) * 100).toFixed(1)}%` : '—', icon: churnUp ? TrendingDown : TrendingUp, color: churnUp ? 'bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-400' : 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400' },
    { label: 'Customer LTV', value: `$${fmtMoney(customers?.ltv)}`, icon: Wallet, color: 'bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400' },
    { label: 'Credits in Wallets', value: fmtNum(credits?.active_balance), icon: Coins, color: 'bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400' },
  ];

  const revenueChart = (revenue?.by_month ?? []).map(m => ({ ...m, revenue: Number(m.revenue) }));
  const planChart = (revenue?.by_plan ?? []).map(p => ({ ...p, revenue: Number(p.revenue) }));
  const forecastData = [
    ...(forecast?.based_on ?? []).map(m => ({ ...m, projected_revenue: Number(m.revenue) })),
    ...(forecast?.projected ?? []).map(m => ({ ...m, projected_revenue: Number(m.projected_revenue) })),
  ];
  const resourceChart = (credits?.by_resource ?? []).slice(0, 8).map(r => ({ ...r, credits: Number(r.credits) }));
  const topPayers = customers?.top_payers ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Badge variant="success" size="sm" dot>Live Financial KPIs</Badge>
          </div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white mt-1">Finance Dashboard</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Revenue, MRR, credits & AI profitability (bank-transfer monetization)</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" leftIcon={<RefreshCw className={cn('h-4 w-4 text-purple-600', refreshing && 'animate-spin')} />} onClick={handleRefresh}>
            {refreshing ? 'Refreshing...' : 'Refresh'}
          </Button>
          <Button variant="outline" leftIcon={<Download className="h-4 w-4" />} onClick={() => handleExport('overview', 'csv')}>Export CSV</Button>
          <Button variant="primary" leftIcon={<Download className="h-4 w-4" />} onClick={() => handleExport('overview', 'pdf')}>Export PDF</Button>
        </div>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center gap-3 py-24">
          <div className="h-10 w-10 animate-spin rounded-full border-2 border-purple-600 border-t-transparent" />
          <span className="text-sm text-gray-500">Loading financial data...</span>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {kpis.map((stat, i) => (
              <motion.div key={stat.label} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: i * 0.05 }}>
                <Card className="glass-panel border-purple-200/50 dark:border-purple-500/20">
                  <CardContent className="p-5">
                    <div className="flex items-center justify-between">
                      <div className={cn('flex h-10 w-10 items-center justify-center rounded-xl', stat.color)}>
                        <stat.icon className="h-5 w-5" />
                      </div>
                      <span className="text-xs font-medium text-emerald-500">{stat.change}</span>
                    </div>
                    <div className="mt-3">
                      <p className="text-sm text-gray-500 dark:text-gray-400">{stat.label}</p>
                      <p className="mt-1 text-2xl font-extrabold text-gray-900 dark:text-white">{stat.value}</p>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>

          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList>
              <TabsTrigger value="overview">Revenue Overview</TabsTrigger>
              <TabsTrigger value="customers">Customers</TabsTrigger>
              <TabsTrigger value="credits">Credits & AI Cost</TabsTrigger>
              <TabsTrigger value="forecast">Forecast</TabsTrigger>
            </TabsList>

            <TabsContent value="overview" className="space-y-4 mt-4">
              <Card className="glass-panel border-purple-200/50 dark:border-purple-500/20">
                <CardHeader>
                  <CardTitle>Monthly Revenue (Last 6 Months)</CardTitle>
                  <CardDescription>Successful bank-transfer payments per month (TND → USD shown)</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="h-72">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={revenueChart} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                        <defs>
                          <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#7c3aed" stopOpacity={0.8} />
                            <stop offset="95%" stopColor="#7c3aed" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(124,58,237,0.1)" />
                        <XAxis dataKey="month" tick={{ fontSize: 12, fill: '#9ca3af' }} />
                        <YAxis tick={{ fontSize: 12, fill: '#9ca3af' }} tickFormatter={(v) => `$${v}`} />
                        <Tooltip formatter={(value) => [`$${Number(value).toFixed(2)}`, 'Revenue']} />
                        <Area type="monotone" dataKey="revenue" stroke="#7c3aed" strokeWidth={2} fill="url(#revGrad)" />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <Card className="glass-panel border-purple-200/50 dark:border-purple-500/20">
                  <CardHeader>
                    <CardTitle>Revenue by Plan</CardTitle>
                    <CardDescription>Bucketed from payment descriptions</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={planChart} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="rgba(124,58,237,0.1)" />
                          <XAxis dataKey="plan" tick={{ fontSize: 11, fill: '#9ca3af' }} interval={0} />
                          <YAxis tick={{ fontSize: 12, fill: '#9ca3af' }} tickFormatter={(v) => `$${v}`} />
                          <Tooltip formatter={(value) => [`$${Number(value).toFixed(2)}`, 'Revenue']} />
                          <Bar dataKey="revenue" fill="#8b5cf6" radius={[6, 6, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </CardContent>
                </Card>

                <Card className="glass-panel border-purple-200/50 dark:border-purple-500/20">
                  <CardHeader>
                    <CardTitle>Key Metrics</CardTitle>
                    <CardDescription>MRR, ARR and monthly growth</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 gap-4">
                      {[
                        { label: 'MRR', value: `$${fmtMoney(revenue?.mrr)}` },
                        { label: 'ARR', value: `$${fmtMoney(revenue?.arr)}` },
                        { label: 'This Year', value: `$${fmtMoney(revenue?.this_year)}` },
                        { label: 'Today', value: `$${fmtMoney(revenue?.today)}` },
                      ].map((m) => (
                        <div key={m.label} className="p-4 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10">
                          <p className="text-xs text-gray-500 dark:text-gray-400">{m.label}</p>
                          <p className="mt-1 text-xl font-extrabold text-gray-900 dark:text-white">{m.value}</p>
                        </div>
                      ))}
                    </div>
                    {planChart.length === 0 && (
                      <p className="mt-4 text-sm text-gray-500 dark:text-gray-400">No revenue by plan yet — appears once payments are approved.</p>
                    )}
                  </CardContent>
                </Card>
              </div>
            </TabsContent>

            <TabsContent value="customers" className="space-y-4 mt-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {statCards.map((stat, i) => (
                  <motion.div key={stat.label} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: i * 0.05 }}>
                    <Card className="glass-panel border-purple-200/50 dark:border-purple-500/20">
                      <CardContent className="p-5">
                        <div className="flex items-center justify-between">
                          <div className={cn('flex h-10 w-10 items-center justify-center rounded-xl', stat.color)}>
                            <stat.icon className="h-5 w-5" />
                          </div>
                        </div>
                        <div className="mt-3">
                          <p className="text-sm text-gray-500 dark:text-gray-400">{stat.label}</p>
                          <p className="mt-1 text-2xl font-extrabold text-gray-900 dark:text-white">{stat.value}</p>
                        </div>
                      </CardContent>
                    </Card>
                  </motion.div>
                ))}
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <Card className="glass-panel border-purple-200/50 dark:border-purple-500/20">
                  <CardHeader>
                    <CardTitle>Subscription Health</CardTitle>
                    <CardDescription>Distribution across lifecycle states</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-3 gap-3">
                      {Object.entries(customers?.subscriptions ?? {}).map(([key, value]) => (
                        <div key={key} className="p-3 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10 text-center">
                          <p className="text-xl font-extrabold text-gray-900 dark:text-white">{fmtNum(value as number)}</p>
                          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400 capitalize">{key.replace('_', ' ')}</p>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>

                <Card className="glass-panel border-purple-200/50 dark:border-purple-500/20">
                  <CardHeader>
                    <CardTitle>Top Payers</CardTitle>
                    <CardDescription>Highest lifetime revenue customers</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {topPayers.length === 0 ? (
                      <p className="text-sm text-gray-500 dark:text-gray-400">No successful payments yet.</p>
                    ) : (
                      <div className="space-y-2">
                        {topPayers.map((payer) => (
                          <div key={payer.user_id} className="flex items-center justify-between p-3 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10">
                            <div className="min-w-0">
                              <p className="text-sm font-semibold text-gray-900 dark:text-white truncate">{payer.email}</p>
                              <p className="text-xs text-gray-500 dark:text-gray-400">{payer.transactions} transaction(s)</p>
                            </div>
                            <Badge variant="success">${fmtMoney(payer.revenue)}</Badge>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>
            </TabsContent>

            <TabsContent value="credits" className="space-y-4 mt-4">
              <Card className="glass-panel border-purple-200/50 dark:border-purple-500/20">
                <CardHeader>
                  <CardTitle>Credits Economy</CardTitle>
                  <CardDescription>Granted vs consumed credits, AI cost & margin</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    {[
                      { label: 'Credits Granted', value: fmtNum(credits?.credits_granted) },
                      { label: 'Credits Consumed', value: fmtNum(credits?.credits_consumed) },
                      { label: 'AI Cost (USD)', value: `$${(credits?.ai_cost_usd ?? 0).toFixed(3)}` },
                      { label: 'Wallets', value: fmtNum(credits?.wallets) },
                    ].map((m) => (
                      <div key={m.label} className="p-4 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10">
                        <p className="text-xs text-gray-500 dark:text-gray-400">{m.label}</p>
                        <p className="mt-1 text-xl font-extrabold text-gray-900 dark:text-white">{m.value}</p>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <Card className="glass-panel border-purple-200/50 dark:border-purple-500/20">
                  <CardHeader>
                    <CardTitle>Credit Usage by AI Feature</CardTitle>
                    <CardDescription>Consumed credits per resource</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {resourceChart.length === 0 ? (
                      <p className="text-sm text-gray-500 dark:text-gray-400">No AI feature usage recorded yet.</p>
                    ) : (
                      <div className="h-64">
                        <ResponsiveContainer width="100%" height="100%">
                          <PieChart>
                            <Pie data={resourceChart} dataKey="credits" nameKey="resource" cx="50%" cy="50%" outerRadius={80} label>
                              {resourceChart.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                            </Pie>
                            <Tooltip formatter={(value) => [`${value} credits`, 'Used']} />
                            <Legend />
                          </PieChart>
                        </ResponsiveContainer>
                      </div>
                    )}
                  </CardContent>
                </Card>

                <Card className="glass-panel border-purple-200/50 dark:border-purple-500/20">
                  <CardHeader>
                    <CardTitle>Most Used Features</CardTitle>
                    <CardDescription>By credits consumed (usage_events)</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {(credits?.features ?? []).length === 0 ? (
                      <p className="text-sm text-gray-500 dark:text-gray-400">No usage events recorded yet.</p>
                    ) : (
                      <div className="space-y-2">
                        {(credits?.features ?? []).slice(0, 6).map((f: FeatureRow) => (
                          <div key={f.resource} className="flex items-center justify-between p-3 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10">
                            <div className="min-w-0">
                              <p className="text-sm font-semibold text-gray-900 dark:text-white capitalize">{f.resource.replace(/_/g, ' ')}</p>
                              <p className="text-xs text-gray-500 dark:text-gray-400">{f.count} calls</p>
                            </div>
                            <div className="text-right">
                              <p className="text-sm font-bold text-purple-600 dark:text-purple-400">{f.credits} credits</p>
                              <p className="text-xs text-gray-500">${(f.cost_usd ?? 0).toFixed(3)}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>
            </TabsContent>

            <TabsContent value="forecast" className="space-y-4 mt-4">
              <Card className="glass-panel border-purple-200/50 dark:border-purple-500/20">
                <CardHeader>
                  <CardTitle>Revenue Forecast (Next 3 Months)</CardTitle>
                  <CardDescription>Linear projection from the last 6 months — solid line = actual, dashed = projected</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="h-72">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={forecastData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(124,58,237,0.1)" />
                        <XAxis dataKey="month" tick={{ fontSize: 12, fill: '#9ca3af' }} />
                        <YAxis tick={{ fontSize: 12, fill: '#9ca3af' }} tickFormatter={(v) => `$${v}`} />
                        <Tooltip formatter={(value) => [`$${Number(value).toFixed(2)}`, 'Revenue']} />
                        <Legend />
                        <Line type="monotone" dataKey="revenue" name="Actual" stroke="#7c3aed" strokeWidth={2} dot={{ r: 3 }} />
                        <Line type="monotone" dataKey="projected_revenue" name="Projected" stroke="#10b981" strokeWidth={2} strokeDasharray="6 4" dot={{ r: 3 }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>

              <Card className="glass-panel border-purple-200/50 dark:border-purple-500/20">
                <CardHeader>
                  <CardTitle>Projected Next 12 Months ARR</CardTitle>
                  <CardDescription>Annualized from the linear forecast</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-4">
                    <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400">
                      <TrendingUp className="h-7 w-7" />
                    </div>
                    <div>
                      <p className="text-3xl font-extrabold text-gray-900 dark:text-white">${fmtMoney(forecast?.next_12m_arr)}</p>
                      <p className="text-sm text-gray-500 dark:text-gray-400">Projected ARR if current momentum holds</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  );
}
