// ============================================================
// Mentor Wallet / Earnings - Candway
// ============================================================

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { cn } from '@/utils/cn';
import { Wallet, TrendingUp, Award, Loader2 } from 'lucide-react';
import { mentorService, type MentorStats, type MentorEarningsChart } from '@/services/mentor.service';

function formatMoney(v: number | null | undefined): string {
  const n = Number(v || 0);
  return `${n.toLocaleString('en-US', { maximumFractionDigits: 2 })} TND`;
}

export default function MentorWalletPage() {
  const [stats, setStats] = useState<MentorStats | null>(null);
  const [chart, setChart] = useState<MentorEarningsChart | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      mentorService.getStats().catch(() => null),
      mentorService.getEarningsChart().catch(() => null),
    ])
      .then(([s, c]) => {
        setStats(s);
        setChart(c);
      })
      .finally(() => setLoading(false));
  }, []);

  const maxEarning = Math.max(1, ...(chart?.data || []));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">Wallet & Earnings</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Track your coaching revenue</p>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 text-purple-500 animate-spin" />
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Card className="p-5 bg-gradient-to-tr from-purple-50 to-indigo-50 dark:from-purple-950/30 dark:to-indigo-950/30 border-purple-200/60">
              <div className="flex items-center justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-600 text-white shadow-md"><Wallet className="h-5 w-5" /></div>
                <Badge variant="success" size="sm" dot>Active</Badge>
              </div>
              <div className="mt-4">
                <div className="text-2xl font-black text-gray-900 dark:text-white">{formatMoney(stats?.revenue)}</div>
                <div className="text-sm text-gray-500">Total Earned</div>
              </div>
            </Card>

            <Card className="p-5">
              <div className="flex items-center justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-100 dark:bg-emerald-500/20 text-emerald-600"><TrendingUp className="h-5 w-5" /></div>
              </div>
              <div className="mt-4">
                <div className="text-2xl font-black text-gray-900 dark:text-white">{stats?.total_students ?? 0}</div>
                <div className="text-sm text-gray-500">Enrolled Students</div>
              </div>
            </Card>

            <Card className="p-5">
              <div className="flex items-center justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-100 dark:bg-blue-500/20 text-blue-600"><Award className="h-5 w-5" /></div>
              </div>
              <div className="mt-4">
                <div className="text-2xl font-black text-gray-900 dark:text-white">{stats?.average_rating ?? '—'}</div>
                <div className="text-sm text-gray-500">Average Rating</div>
              </div>
            </Card>
          </div>

          <Card className="glass-panel border-purple-200/50">
            <CardHeader>
              <CardTitle>Earnings — Last 6 Months</CardTitle>
              <CardDescription>Monthly revenue from paid enrollments in your courses</CardDescription>
            </CardHeader>
            <CardContent>
              {chart && chart.data.some(v => v > 0) ? (
                <div className="flex items-end gap-3 h-48">
                  {chart.data.map((v, i) => (
                    <div key={i} className="flex-1 flex flex-col items-center gap-2 min-w-0">
                      <span className="text-[10px] font-bold text-gray-500 dark:text-gray-400 truncate max-w-full">{v > 0 ? `${Math.round(v)}` : ''}</span>
                      <div
                        className={cn(
                          'w-full rounded-t-lg transition-all duration-500',
                          v > 0 ? 'bg-gradient-to-t from-purple-600 to-indigo-500' : 'bg-gray-100 dark:bg-white/10',
                        )}
                        style={{ height: `${Math.max(4, (v / maxEarning) * 100)}%` }}
                      />
                      <span className="text-[10px] font-black text-gray-400 uppercase">{chart.labels[i]}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-16 text-sm text-gray-500 dark:text-gray-400">
                  No earnings recorded yet. Revenue appears here once students purchase your courses.
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="glass-panel border-purple-200/50">
            <CardHeader>
              <CardTitle>Payouts</CardTitle>
              <CardDescription>Payment history</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-start gap-3 rounded-xl border border-purple-200 bg-purple-50 dark:bg-purple-500/10 dark:border-purple-500/20 px-4 py-3">
                <Wallet className="h-5 w-5 text-purple-600 dark:text-purple-400 shrink-0 mt-0.5" />
                <p className="text-sm text-purple-900 dark:text-purple-200">
                  Payouts are processed monthly by the finance team. Your accumulated earnings are shown above.
                </p>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
