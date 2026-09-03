import { useState, useEffect } from 'react';
import { useLanguage } from '@/contexts/language-context';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Progress } from '@/shared/components/ui/progress';
import { BarChart3, AlertTriangle, TrendingUp, Shield, Calendar, RefreshCw, Loader2 } from 'lucide-react';
import { cn } from '@/utils/cn';
import apiClient from '@/lib/api-client';

function getSeverity(score: number): 'low' | 'medium' | 'high' {
  if (score >= 80) return 'low';
  if (score >= 70) return 'medium';
  return 'high';
}

function getChange(monthly: number[]): string {
  if (monthly.length < 2) return '-';
  const diff = monthly[monthly.length - 1] - monthly[0];
  return diff >= 0 ? `+${diff}` : `${diff}`;
}

export default function BiasAnalyticsPage() {
  const { t } = useLanguage();
  const [dateRange, setDateRange] = useState(t('recruiter.biasAnalytics.last6Months'));
  const [showDateDropdown, setShowDateDropdown] = useState(false);
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const dateRanges = [
    t('recruiter.biasAnalytics.last3Months'),
    t('recruiter.biasAnalytics.last6Months'),
    t('recruiter.biasAnalytics.thisYear'),
    t('recruiter.biasAnalytics.allTime'),
  ];

  const daysForRange: Record<string, number> = {
    [t('recruiter.biasAnalytics.last3Months')]: 90,
    [t('recruiter.biasAnalytics.last6Months')]: 180,
    [t('recruiter.biasAnalytics.thisYear')]: 365,
    [t('recruiter.biasAnalytics.allTime')]: 9999,
  };

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res: any = await apiClient.get('/recruiter/enhancements/analytics/jd-bias', { days: daysForRange[dateRange] });
      setData(res);
    } catch (e: any) {
      setError(e?.message || t('recruiter.biasAnalytics.loadFailed'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [dateRange]);

  const maxTrendValue = data?.monthly_trends?.length
    ? Math.max(...data.monthly_trends.flatMap((m: any) => [m.overall ?? 0, m.gender ?? 0, m.culture ?? 0, m.age ?? 0]))
    : 100;

  const stats = data
    ? [
        {
          label: t('recruiter.biasAnalytics.overallBiasScore'),
          value: `${data.overall_score ?? '-'}/100`,
          change: data.monthly_trends?.length ? getChange(data.monthly_trends.map((m: any) => m.overall)) : '-',
          status: (data.overall_score ?? 0) >= 80 ? t('recruiter.biasAnalytics.good') : (data.overall_score ?? 0) >= 70 ? t('recruiter.biasAnalytics.fair') : t('recruiter.biasAnalytics.needsWork'),
          color: 'from-emerald-500 to-teal-500',
          icon: Shield,
        },
        {
          label: t('recruiter.biasAnalytics.genderBalance'),
          value: data.gender_balance != null ? `${Math.round(data.gender_balance)}/${100 - Math.round(data.gender_balance)}` : 'N/A',
          change: data.monthly_trends?.length ? getChange(data.monthly_trends.map((m: any) => m.gender)) : '-',
          status: data.gender_balance != null && Math.abs(data.gender_balance - 50) <= 15 ? t('recruiter.biasAnalytics.balanced') : t('recruiter.biasAnalytics.imbalanced'),
          color: 'from-blue-600 to-indigo-500',
          icon: BarChart3,
        },
        {
          label: t('recruiter.biasAnalytics.culturalDiversity'),
          value: data.cultural_diversity != null ? `${Math.round(data.cultural_diversity)}%` : 'N/A',
          change: data.monthly_trends?.length ? `${getChange(data.monthly_trends.map((m: any) => m.culture))}%` : '-',
          status: (data.cultural_diversity ?? 0) >= 75 ? t('recruiter.biasAnalytics.improving') : t('recruiter.biasAnalytics.needsFocus'),
          color: 'from-purple-600 to-fuchsia-500',
          icon: TrendingUp,
        },
        {
          label: t('recruiter.biasAnalytics.ageDistribution'),
          value: data.age_distribution != null ? data.age_distribution.toString() : 'N/A',
          change: t('recruiter.biasAnalytics.stable'),
          status: t('recruiter.biasAnalytics.healthy'),
          color: 'from-amber-500 to-orange-500',
          icon: AlertTriangle,
        },
      ]
    : [];

  const monthlyTrends = data?.monthly_trends ?? [];

  const categories = (data?.categories ?? []).map((cat: any) => ({
    name: cat.name,
    score: cat.score,
    severity: getSeverity(cat.score),
    desc: cat.description || `${t('recruiter.biasAnalytics.biasScoreOf')} ${cat.score}% — ${getSeverity(cat.score) === 'low' ? t('recruiter.biasAnalytics.goodFairnessLevel') : getSeverity(cat.score) === 'medium' ? t('recruiter.biasAnalytics.moderateBiasDetected') : t('recruiter.biasAnalytics.needsImmediateAttention')}`,
  }));

  const recommendations = data?.recommendations ?? [];

  if (error) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center space-y-3">
          <AlertTriangle className="h-10 w-10 text-red-400 mx-auto" />
          <p className="text-sm font-medium text-gray-600 dark:text-gray-400">{error}</p>
          <Button variant="outline" onClick={fetchData}>{t('recruiter.biasAnalytics.retry')}</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">{t('recruiter.biasAnalytics.title')}</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{t('recruiter.biasAnalytics.subtitle')}</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Button variant="outline" leftIcon={<Calendar className="h-4 w-4" />} onClick={() => setShowDateDropdown(!showDateDropdown)} className="font-medium">
              {dateRange}
            </Button>
            {showDateDropdown && (
              <div className="absolute right-0 mt-2 w-44 rounded-xl border border-purple-100 dark:border-white/10 bg-white dark:bg-gray-900 shadow-xl z-50 overflow-hidden">
                {dateRanges.map(d => (
                  <button key={d} className={cn('w-full px-4 py-2 text-left text-sm hover:bg-purple-50 dark:hover:bg-purple-500/10 transition-colors', dateRange === d && 'bg-purple-50 dark:bg-purple-500/10 font-bold text-purple-700 dark:text-purple-300')} onClick={() => { setDateRange(d); setShowDateDropdown(false); }}>
                    {d}
                  </button>
                ))}
              </div>
            )}
          </div>
          <Button variant="outline" leftIcon={loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />} onClick={fetchData} disabled={loading}>{t('recruiter.biasAnalytics.refresh')}</Button>
        </div>
      </div>

      {loading && !data ? (
        <div className="flex items-center justify-center h-96">
          <Loader2 className="h-8 w-8 animate-spin text-purple-500" />
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {stats.map((stat, i) => (
              <motion.div key={stat.label} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.08 }}>
                <Card className="glass-panel border-purple-200/50">
                  <CardContent className="p-5">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">{stat.label}</span>
                      <div className={cn('h-8 w-8 rounded-lg bg-gradient-to-br flex items-center justify-center text-white', stat.color)}>
                        <stat.icon className="h-4 w-4" />
                      </div>
                    </div>
                    <div className="flex items-end justify-between">
                      <span className="text-2xl font-extrabold text-gray-900 dark:text-white">{stat.value}</span>
                      <Badge variant={stat.status === t('recruiter.biasAnalytics.good') || stat.status === t('recruiter.biasAnalytics.healthy') || stat.status === t('recruiter.biasAnalytics.balanced') ? 'success' : 'primary'} size="sm">{stat.change}</Badge>
                    </div>
                    <span className="text-xs font-medium text-gray-500 dark:text-gray-400 mt-1 block">{stat.status}</span>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>

          <Card className="glass-panel border-purple-200/50">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-purple-500" />
                {t('recruiter.biasAnalytics.biasTrendAnalysis')}
              </CardTitle>
              <CardDescription>{t('recruiter.biasAnalytics.monthlyBiasScores')}</CardDescription>
            </CardHeader>
            <CardContent>
              {monthlyTrends.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-8">{t('recruiter.biasAnalytics.noTrendData')}</p>
              ) : (
                <>
                  <div className="flex items-end gap-3 h-52">
                    {monthlyTrends.map((m: any) => (
                      <div key={m.month} className="flex-1 flex flex-col items-center justify-end h-full">
                        <div className="w-full flex flex-col items-center gap-0.5">
                          <div className="w-full rounded-t-md bg-gradient-to-t from-emerald-500 to-emerald-400" style={{ height: `${((m.overall ?? 0) / maxTrendValue) * 180}px`, opacity: 0.9 }} title={`Overall: ${m.overall}`} />
                          <div className="w-full rounded-t-md bg-gradient-to-t from-blue-500 to-indigo-400" style={{ height: `${((m.gender ?? 0) / maxTrendValue) * 130}px` }} title={`Gender: ${m.gender}`} />
                          <div className="w-full rounded-t-md bg-gradient-to-t from-purple-500 to-fuchsia-400" style={{ height: `${((m.culture ?? 0) / maxTrendValue) * 100}px` }} title={`Culture: ${m.culture}`} />
                          <div className="w-full rounded-t-md bg-gradient-to-t from-amber-500 to-orange-400" style={{ height: `${((m.age ?? 0) / maxTrendValue) * 80}px` }} title={`Age: ${m.age}`} />
                        </div>
                        <span className="text-[10px] font-bold text-gray-500 dark:text-gray-400 mt-1">{m.month}</span>
                      </div>
                    ))}
                  </div>
                  <div className="flex items-center gap-6 mt-4 justify-center">
                    {[
                      { label: t('recruiter.biasAnalytics.overall'), color: 'bg-emerald-400' },
                      { label: t('recruiter.biasAnalytics.gender'), color: 'bg-blue-500' },
                      { label: t('recruiter.biasAnalytics.culture'), color: 'bg-purple-500' },
                      { label: t('recruiter.biasAnalytics.age'), color: 'bg-amber-500' },
                    ].map(leg => (
                      <div key={leg.label} className="flex items-center gap-2">
                        <span className={cn('h-3 w-3 rounded-sm', leg.color)} />
                        <span className="text-xs text-gray-500 dark:text-gray-400">{leg.label}</span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          <Card className="glass-panel border-purple-200/50">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-purple-500" />
                {t('recruiter.biasAnalytics.categoryBreakdown')}
              </CardTitle>
              <CardDescription>{t('recruiter.biasAnalytics.detailedBiasScores')}</CardDescription>
            </CardHeader>
            <CardContent>
              {categories.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-8">{t('recruiter.biasAnalytics.noCategoryData')}</p>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {categories.map((cat: any, i: number) => (
                    <motion.div key={cat.name} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.08 }}>
                      <Card variant="outlined" padding="md" className={cn('h-full', cat.severity === 'high' && 'border-red-200/70 dark:border-red-500/30')}>
                        <div className="flex items-start justify-between mb-2">
                          <div>
                            <h3 className="text-sm font-extrabold text-gray-900 dark:text-white">{cat.name}</h3>
                            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{cat.desc}</p>
                          </div>
                          <Badge variant={cat.severity === 'low' ? 'success' : cat.severity === 'medium' ? 'warning' : 'danger'} size="sm" dot>{cat.severity}</Badge>
                        </div>
                        <div className="flex items-center gap-3 mt-2">
                          <div className="flex-1">
                            <Progress value={cat.score} color={cat.score >= 80 ? 'green' : cat.score >= 70 ? 'default' : 'amber'} size="md" />
                          </div>
                          <span className={cn('text-sm font-extrabold', cat.score >= 80 ? 'text-emerald-600 dark:text-emerald-400' : cat.score >= 70 ? 'text-purple-600 dark:text-purple-400' : 'text-amber-600 dark:text-amber-400')}>
                            {cat.score}%
                          </span>
                        </div>
                      </Card>
                    </motion.div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="glass-panel border-purple-200/50">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Shield className="h-5 w-5 text-purple-500" />
                {t('recruiter.biasAnalytics.recommendations')}
              </CardTitle>
              <CardDescription>{t('recruiter.biasAnalytics.aiGeneratedSuggestions')}</CardDescription>
            </CardHeader>
            <CardContent>
              {recommendations.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-8">{t('recruiter.biasAnalytics.noRecommendations')}</p>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {recommendations.map((rec: string, i: number) => (
                    <motion.div key={i} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.06 }} className="flex items-start gap-3 p-3 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10 hover:bg-purple-50/50 dark:hover:bg-purple-500/5 transition-colors">
                      <div className="h-6 w-6 rounded-full bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center shrink-0 mt-0.5">
                        <span className="text-[10px] font-black text-purple-700 dark:text-purple-300">{i + 1}</span>
                      </div>
                      <p className="text-sm font-medium text-gray-700 dark:text-gray-300">{rec}</p>
                    </motion.div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
