import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { BarChart3, PieChart, TrendingUp, Table2, Save, Download, Eye, Settings, X, Activity, Loader2 } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card'
import { Badge } from '@/shared/components/ui/badge'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { customToast } from '@/shared/components/ui/toast'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/shared/components/ui/select'
import { cn } from '@/utils/cn'
import { reportsService } from '@/services/reports.service'
import { useLanguage } from '@/contexts/language-context'
import { useSearchParams } from 'react-router'

type ReportType = 'recruiter_analytics' | 'pipeline' | 'eeo' | 'custom'

export default function ReportBuilder() {
  const { t } = useLanguage();
  const reportTypes: { value: ReportType; label: string; icon: typeof BarChart3 }[] = [
    { value: 'recruiter_analytics', label: t('reportBuilder.type.recruiterAnalytics'), icon: BarChart3 },
    { value: 'pipeline', label: t('reportBuilder.type.pipeline'), icon: TrendingUp },
    { value: 'eeo', label: t('reportBuilder.type.eeo'), icon: PieChart },
    { value: 'custom', label: t('reportBuilder.type.custom'), icon: Table2 },
  ]

  const fallbackMetrics = [
    { id: 'total_applications', label: t('reportBuilder.metric.totalApplications') },
    { id: 'applications_per_job', label: t('reportBuilder.metric.applicationsPerJob') },
    { id: 'screening_rate', label: t('reportBuilder.metric.screeningRate') },
    { id: 'interview_rate', label: t('reportBuilder.metric.interviewRate') },
    { id: 'offer_rate', label: t('reportBuilder.metric.offerRate') },
    { id: 'hire_rate', label: t('reportBuilder.metric.hireRate') },
    { id: 'avg_time_to_hire', label: t('reportBuilder.metric.avgTimeToHire') },
    { id: 'avg_time_to_interview', label: t('reportBuilder.metric.avgTimeToInterview') },
    { id: 'avg_cv_score', label: t('reportBuilder.metric.avgCvScore') },
    { id: 'avg_interview_score', label: t('reportBuilder.metric.avgInterviewScore') },
    { id: 'offer_acceptance_rate', label: t('reportBuilder.metric.offerAcceptanceRate') },
    { id: 'candidates_per_job', label: t('reportBuilder.metric.candidatesPerJob') },
    { id: 'source_effectiveness', label: t('reportBuilder.metric.sourceEffectiveness') },
    { id: 'pipeline_conversion', label: t('reportBuilder.metric.pipelineConversion') },
    { id: 'recruiter_activity', label: t('reportBuilder.metric.recruiterActivity') },
    { id: 'interviews_per_recruiter', label: t('reportBuilder.metric.interviewsPerRecruiter') },
    { id: 'applications_by_source', label: t('reportBuilder.metric.applicationsBySource') },
    { id: 'applications_by_status', label: t('reportBuilder.metric.applicationsByStatus') },
    { id: 'applications_over_time', label: t('reportBuilder.metric.applicationsOverTime') },
    { id: 'hires_over_time', label: t('reportBuilder.metric.hiresOverTime') },
  ]

  const [searchParams] = useSearchParams();
  const [name, setName] = useState('')
  const [type, setType] = useState<ReportType>('recruiter_analytics')
  const [dateRange, setDateRange] = useState('last_30_days')
  const [selectedMetrics, setSelectedMetrics] = useState<string[]>(['total_applications', 'interview_rate', 'hire_rate'])
  const [isSaving, setIsSaving] = useState(false)
  const [isBuilding, setIsBuilding] = useState(false)
  const [loadingReport, setLoadingReport] = useState(false)
  const [availableMetrics, setAvailableMetrics] = useState(fallbackMetrics)
  const [preview, setPreview] = useState<any>(null)
  const [previewError, setPreviewError] = useState<string | null>(null)

  useEffect(() => {
    const reportId = searchParams.get('report_id')
    if (!reportId) return
    setLoadingReport(true)
    reportsService.get(reportId)
      .then((data: any) => {
        if (data?.name) setName(data.name)
        if (data?.description) {
          const t = data.description as ReportType
          if (reportTypes.some(rt => rt.value === t)) setType(t)
        }
        if (data?.config) {
          const cfg = data.config
          if (Array.isArray(cfg?.metrics)) setSelectedMetrics(cfg.metrics)
          if (cfg?.filters?.date_range?.start || cfg?.filters?.date_range?.end) {
            const start = cfg.filters.date_range.start
            const end = cfg.filters.date_range.end
            if (start && end) {
              const now = new Date(end)
              const startDate = new Date(start)
              const diffDays = Math.max(0, Math.round((now.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24)))
              if (diffDays <= 7) setDateRange('last_7_days')
              else if (diffDays <= 30) setDateRange('last_30_days')
              else if (diffDays <= 90) setDateRange('last_90_days')
              else if (startDate.getMonth() % 3 === 0 && startDate.getDate() <= 3) setDateRange('this_quarter')
              else if (startDate.getMonth() === 0 && startDate.getDate() === 1) setDateRange('this_year')
              else setDateRange('custom')
            }
          }
        }
      })
      .catch(() => {
        customToast({ type: 'error', title: t('reportBuilder.loadFailed') })
      })
      .finally(() => {
        setLoadingReport(false)
      })
  }, [searchParams])

  useEffect(() => {
    reportsService.metrics()
      .then(res => {
        const list = Array.isArray(res)
          ? res
          : Array.isArray((res as any)?.metrics)
            ? (res as any).metrics.map((m: any) => ({ id: m.key, label: m.label }))
            : []
        if (list.length) {
          setAvailableMetrics(list)
        }
      })
      .catch(() => {
        setAvailableMetrics(fallbackMetrics)
      })
  }, [])

  const toggleMetric = (id: string) => {
    setSelectedMetrics(prev =>
      prev.includes(id) ? prev.filter(m => m !== id) : [...prev, id]
    )
  }

  const buildConfig = () => {
    const now = new Date();
    const toISO = (d: Date) => d.toISOString().split('T')[0];
    let startDate: string | null = null;
    let endDate = toISO(now);

    if (dateRange === 'last_7_days') {
      const d = new Date(now);
      d.setDate(d.getDate() - 7);
      startDate = toISO(d);
    } else if (dateRange === 'last_30_days') {
      const d = new Date(now);
      d.setDate(d.getDate() - 30);
      startDate = toISO(d);
    } else if (dateRange === 'last_90_days') {
      const d = new Date(now);
      d.setDate(d.getDate() - 90);
      startDate = toISO(d);
    } else if (dateRange === 'this_quarter') {
      const q = Math.floor(now.getMonth() / 3);
      startDate = toISO(new Date(now.getFullYear(), q * 3, 1));
    } else if (dateRange === 'this_year') {
      startDate = toISO(new Date(now.getFullYear(), 0, 1));
    }

    return {
      type,
      metrics: selectedMetrics,
      filters: {
        date_range: startDate ? { start: startDate, end: endDate } : {},
      },
    };
  }

  const handleSave = async () => {
    if (!name.trim()) {
      customToast({ type: 'error', title: t('reportBuilder.nameRequired') })
      return
    }
    setIsSaving(true)
    try {
      await reportsService.save({ name: name.trim(), description: type, config: buildConfig() })
      customToast({ type: 'success', title: t('reportBuilder.savedSuccess') })
    } catch {
      customToast({ type: 'error', title: t('reportBuilder.saveFailed') })
    } finally {
      setIsSaving(false)
    }
  }

  const handleGenerate = async () => {
    if (!selectedMetrics.length) {
      customToast({ type: 'error', title: t('reportBuilder.selectMetric') })
      return
    }
    setIsBuilding(true)
    setPreviewError(null)
    try {
      const result = await reportsService.build(buildConfig())
      setPreview(result)
      customToast({ type: 'success', title: t('reportBuilder.generatedSuccess') })
    } catch {
      setPreviewError(t('reportBuilder.generateFailedMsg'))
      customToast({ type: 'error', title: t('reportBuilder.generateFailed') })
    } finally {
      setIsBuilding(false)
    }
  }

  const reportData: Record<string, any> = preview?.report_data ?? {}
  const numberCards = Object.entries(reportData).filter(([, v]) => v?.type === 'number_card')
  const funnels = Object.entries(reportData).filter(([, v]) => v?.type === 'funnel')
  const lineCharts = Object.entries(reportData).filter(([, v]) => v?.type === 'line_chart')
  const barCharts = Object.entries(reportData).filter(([, v]) => v?.type === 'bar_chart')
  const pieCharts = Object.entries(reportData).filter(([, v]) => v?.type === 'pie_chart')
  const tables = Object.entries(reportData).filter(([, v]) => v?.type === 'table')

  const metricLabel = (id: string) =>
    availableMetrics.find(m => m.id === id)?.label ?? id.replace(/_/g, ' ')

  return (
    <div className="space-y-6 p-6">
      {loadingReport && (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-gray-500 dark:text-gray-400" />
        </div>
      )}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{t('reportBuilder.title')}</h1>
          <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">{t('reportBuilder.subtitle')}</p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" className="gap-2" onClick={handleSave} disabled={isSaving}>
            <Save className="w-4 h-4" />
            {isSaving ? t('reportBuilder.saving') : t('reportBuilder.saveReport')}
          </Button>
          <Button className="gap-2" onClick={handleGenerate} disabled={isBuilding}>
            <Download className="w-4 h-4" />
            {isBuilding ? t('reportBuilder.generating') : t('reportBuilder.generateReport')}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 space-y-6">
          <Card className="glass-card">
            <CardHeader>
              <CardTitle className="text-sm font-medium text-gray-900 dark:text-white flex items-center gap-2">
                <Settings className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                {t('reportBuilder.configuration')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm text-gray-700 dark:text-gray-300 mb-1.5 block">{t('reportBuilder.reportName')}</label>
                <Input
                  placeholder={t('reportBuilder.reportNamePlaceholder')}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </div>

              <div>
                <label className="text-sm text-gray-700 dark:text-gray-300 mb-1.5 block">{t('reportBuilder.reportType')}</label>
                <Select value={type} onValueChange={(v: ReportType) => setType(v)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {reportTypes.map(rt => (
                      <SelectItem key={rt.value} value={rt.value}>
                        <span className="flex items-center gap-2">
                          <rt.icon className="w-4 h-4 text-gray-500 dark:text-gray-400" />
                          {rt.label}
                        </span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-sm text-gray-700 dark:text-gray-300 mb-1.5 block">{t('reportBuilder.dateRange')}</label>
                <Select value={dateRange} onValueChange={setDateRange}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="last_7_days">{t('reportBuilder.date.last7Days')}</SelectItem>
                    <SelectItem value="last_30_days">{t('reportBuilder.date.last30Days')}</SelectItem>
                    <SelectItem value="last_90_days">{t('reportBuilder.date.last90Days')}</SelectItem>
                    <SelectItem value="this_quarter">{t('reportBuilder.date.thisQuarter')}</SelectItem>
                    <SelectItem value="this_year">{t('reportBuilder.date.thisYear')}</SelectItem>
                    <SelectItem value="custom">{t('reportBuilder.date.custom')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-sm text-gray-700 dark:text-gray-300 mb-1.5 block">{t('reportBuilder.metrics')}</label>
                <div className="space-y-1.5 max-h-64 overflow-y-auto pr-1">
                  {availableMetrics.map(metric => (
                    <label
                      key={metric.id}
                      className={cn(
                        'flex items-center gap-2.5 p-2 rounded-lg cursor-pointer transition-colors',
                        selectedMetrics.includes(metric.id)
                          ? 'bg-blue-500/10 text-blue-700 dark:text-blue-300'
                          : 'text-gray-500 dark:text-gray-400 hover:bg-purple-50 dark:hover:bg-white/5 hover:text-gray-700 dark:hover:text-gray-300'
                      )}
                    >
                      <input
                        type="checkbox"
                        checked={selectedMetrics.includes(metric.id)}
                        onChange={() => toggleMetric(metric.id)}
                        className="w-4 h-4 rounded border-gray-300 dark:border-gray-600 bg-white dark:bg-white/5 text-blue-500 focus:ring-blue-500/50"
                      />
                      <span className="text-sm">{metric.label}</span>
                    </label>
                  ))}
                </div>
                {selectedMetrics.length > 0 && (
                  <div className="flex items-center gap-1.5 mt-2 flex-wrap">
                    {selectedMetrics.map(id => {
                      const m = availableMetrics.find(mm => mm.id === id)
                      return (
                        <Badge key={id} variant="outline" className="text-xs bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-500/20 gap-1">
                          {m?.label}
                          <X
                            className="w-3 h-3 cursor-pointer hover:text-blue-600 dark:hover:text-blue-300"
                            onClick={() => toggleMetric(id)}
                          />
                        </Badge>
                      )
                    })}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="lg:col-span-2 space-y-6">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            <Card className="glass-card">
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-sm font-medium text-gray-900 dark:text-white flex items-center gap-2">
                    <Eye className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                    {t('reportBuilder.livePreview')}
                  </CardTitle>
                  <CardDescription className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                    {name || t('reportBuilder.untitledReport')} &middot; {reportTypes.find(t => t.value === type)?.label}
                  </CardDescription>
                </div>
                <Badge variant="outline" className="text-xs bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20 flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  {t('reportBuilder.live')}
                </Badge>
              </CardHeader>
              <CardContent className="space-y-4">
                {previewError ? (
                          <div className="text-sm text-red-600 dark:text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg p-4">
                    {previewError}
                  </div>
                ) : !preview ? (
                  <div className="flex flex-col items-center justify-center py-12 text-gray-500 dark:text-gray-400">
                    <Activity className="w-10 h-10 mb-3 text-gray-400 dark:text-gray-600" />
                    <p className="text-sm">{t('reportBuilder.noPreview')}</p>
                  </div>
                ) : (
                  <>
                    {numberCards.length > 0 && (
                      <div className="grid grid-cols-3 gap-3">
                        {numberCards.map(([id, v]) => (
                          <div key={id} className="glass-panel rounded-lg p-4 text-center">
                            <p className="text-2xl font-bold text-gray-900 dark:text-white">
                              {v.value != null ? `${Number(v.value).toLocaleString()}${v.suffix ?? ''}` : '—'}
                            </p>
                            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{metricLabel(id)}</p>
                          </div>
                        ))}
                      </div>
                    )}

                    {funnels.map(([id, v]) => (
                      <div key={id} className="glass-panel rounded-lg p-4">
                        <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 flex items-center gap-2 mb-3">
                          <BarChart3 className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                          {metricLabel(id)}
                        </h4>
                        <div className="overflow-x-auto">
                          <table className="w-full text-xs">
                            <thead>
                              <tr className="text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-white/5">
                                <th className="text-left py-1.5 font-medium">{t('reportBuilder.stage')}</th>
                                <th className="text-right py-1.5 font-medium">{t('reportBuilder.count')}</th>
                              </tr>
                            </thead>
                            <tbody>
                              {(v.stages ?? []).map((row: any, i: number) => (
                                <tr key={i} className="border-b border-gray-100 dark:border-white/5 last:border-0">
                                  <td className="py-1.5 text-gray-700 dark:text-gray-300">{row.stage ?? row.name}</td>
                                  <td className="py-1.5 text-right text-gray-900 dark:text-gray-200">{row.count ?? row.value ?? 0}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    ))}

                    {lineCharts.map(([id, v]) => (
                      <div key={id} className="glass-panel rounded-lg p-4">
                        <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 flex items-center gap-2 mb-3">
                          <TrendingUp className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                          {metricLabel(id)}
                        </h4>
                        {(v.labels ?? []).length > 0 ? (
                          <div className="h-40 flex items-end gap-2">
                            {(v.datasets?.[0]?.data ?? []).map((point: number, i: number) => (
                              <motion.div
                                key={i}
                                initial={{ height: 0 }}
                                animate={{ height: `${Math.max(4, Math.min(100, (point / Math.max(1, ...(v.datasets?.[0]?.data ?? [1]))) * 100))}%` }}
                                transition={{ delay: 0.2 + i * 0.03, duration: 0.5 }}
                                className="flex-1 bg-gradient-to-t from-emerald-500/50 to-emerald-400/30 rounded-t-sm"
                              />
                            ))}
                          </div>
                        ) : (
                          <p className="text-xs text-gray-500 dark:text-gray-400">{t('reportBuilder.noTimeSeriesData')}</p>
                        )}
                      </div>
                    ))}

                    {barCharts.map(([id, v]) => {
                      const data = v.data ?? {}
                      const entries = Object.entries(data)
                      return (
                        <div key={id} className="glass-panel rounded-lg p-4">
                          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 flex items-center gap-2 mb-3">
                            <BarChart3 className="w-4 h-4 text-purple-600 dark:text-purple-400" />
                            {metricLabel(id)}
                          </h4>
                          {entries.length > 0 ? (
                            <div className="space-y-2">
                              {entries.map(([label, val]) => {
                                const max = Math.max(1, ...entries.map(([, n]) => Number(n) || 0))
                                return (
                                  <div key={label}>
                                    <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400 mb-1">
                                      <span>{label}</span>
                                      <span>{Number(val).toLocaleString()}</span>
                                    </div>
                                    <div className="h-1.5 bg-gray-100 dark:bg-white/5 rounded-full overflow-hidden">
                                      <motion.div
                                        initial={{ width: 0 }}
                                        animate={{ width: `${(Number(val) / max) * 100}%` }}
                                        transition={{ delay: 0.3, duration: 0.5 }}
                                        className="h-full rounded-full bg-purple-500"
                                      />
                                    </div>
                                  </div>
                                )
                              })}
                            </div>
                          ) : (
                            <p className="text-xs text-gray-500 dark:text-gray-400">{t('reportBuilder.noData')}</p>
                          )}
                        </div>
                      )
                    })}

                    {pieCharts.map(([id, v]) => {
                      const data = v.data ?? {}
                      const entries = Object.entries(data)
                      const colors = ['bg-blue-500', 'bg-emerald-500', 'bg-purple-500', 'bg-amber-500', 'bg-rose-500', 'bg-cyan-500']
                      return (
                        <div key={id} className="glass-panel rounded-lg p-4">
                          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 flex items-center gap-2 mb-3">
                            <PieChart className="w-4 h-4 text-purple-600 dark:text-purple-400" />
                            {metricLabel(id)}
                          </h4>
                          {entries.length > 0 ? (
                            <div className="space-y-2">
                              {entries.map(([label, val], i) => {
                                const total = entries.reduce((acc, [, n]) => acc + (Number(n) || 0), 0)
                                const pct = total > 0 ? Math.round((Number(val) / total) * 100) : 0
                                return (
                                  <div key={label}>
                                    <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400 mb-1">
                                      <span>{label}</span>
                                      <span>{pct}%</span>
                                    </div>
                                    <div className="h-1.5 bg-gray-100 dark:bg-white/5 rounded-full overflow-hidden">
                                      <motion.div
                                        initial={{ width: 0 }}
                                        animate={{ width: `${pct}%` }}
                                        transition={{ delay: 0.4, duration: 0.5 }}
                                        className={cn('h-full rounded-full', colors[i % colors.length])}
                                      />
                                    </div>
                                  </div>
                                )
                              })}
                            </div>
                          ) : (
                            <p className="text-xs text-gray-500 dark:text-gray-400">{t('reportBuilder.noData')}</p>
                          )}
                        </div>
                      )
                    })}

                    {tables.map(([id, v]) => (
                      <div key={id} className="glass-panel rounded-lg p-4">
                        <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 flex items-center gap-2 mb-3">
                          <Table2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                          {metricLabel(id)}
                        </h4>
                        {Array.isArray(v.data) && v.data.length > 0 ? (
                          <div className="overflow-x-auto">
                            <table className="w-full text-xs">
                              <tbody>
                                {(v.data as any[]).slice(0, 10).map((row, i) => (
                                  <tr key={i} className="border-b border-gray-100 dark:border-white/5 last:border-0">
                                    {Object.values(row).map((cell, j) => (
                                      <td key={j} className="py-1.5 pr-3 text-gray-700 dark:text-gray-300">{String(cell)}</td>
                                    ))}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        ) : (
                          <p className="text-xs text-gray-500 dark:text-gray-400">{t('reportBuilder.noData')}</p>
                        )}
                      </div>
                    ))}

                    {(() => {
                      const errors = Object.entries(reportData)
                        .filter(([, v]) => v && typeof v === 'object' && v.error)
                        .map(([k, v]) => `${metricLabel(k)}: ${(v as any).error}`);

                      if (errors.length > 0) {
                        return (
                  <div className="text-sm text-red-600 dark:text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg p-4">
                            <p className="font-semibold mb-2">{t('reportBuilder.metricsFailed')}</p>
                            <ul className="list-disc pl-5 space-y-1">
                              {errors.map((e, i) => (
                                <li key={i}>{e}</li>
                              ))}
                            </ul>
                          </div>
                        );
                      }

                      if (numberCards.length === 0 && funnels.length === 0 && lineCharts.length === 0 && barCharts.length === 0 && pieCharts.length === 0 && tables.length === 0) {
                        return (
                          <div className="text-sm text-gray-500 dark:text-gray-400 text-center py-8">
                            {t('reportBuilder.noResults')}
                          </div>
                        );
                      }
                      return null;
                    })()}
                  </>
                )}
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </div>

      <div className="flex items-center justify-end gap-3 pt-2 border-t border-gray-200 dark:border-white/5">
        <Button variant="outline" className="gap-2" onClick={handleSave} disabled={isSaving}>
          <Save className="w-4 h-4" />
          {isSaving ? t('reportBuilder.saving') : t('reportBuilder.saveReport')}
        </Button>
        <Button className="gap-2" onClick={handleGenerate} disabled={isBuilding}>
          <Download className="w-4 h-4" />
          {isBuilding ? t('reportBuilder.generating') : t('reportBuilder.generateReport')}
        </Button>
      </div>
    </div>
  )
}
