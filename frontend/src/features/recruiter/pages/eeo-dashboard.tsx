import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Progress } from '@/shared/components/ui/progress';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/shared/components/ui/tabs';
import { customToast } from '@/shared/components/ui/toast';
import { eeoService } from '@/services/eeo.service';
import { Users, PieChart, Download, BarChart3, Shield, Loader2 } from 'lucide-react';
import { cn } from '@/utils/cn';

export default function EeoDashboardPage() {
  const [activeTab, setActiveTab] = useState('pipeline');
  const [loading, setLoading] = useState(true);
  const [dashboard, setDashboard] = useState<any>(null);
  const [pipeline, setPipeline] = useState<any[]>([]);
  const [trends, setTrends] = useState<any[]>([]);
  const [compliance, setCompliance] = useState<any>(null);

  useEffect(() => {
    Promise.all([
      eeoService.getDashboard(),
      eeoService.getPipelineDiversity(),
      eeoService.getTrends(),
      eeoService.getComplianceSummary(),
    ]).then(([dashRes, pipeRes, trendsRes, compRes]) => {
      setDashboard(dashRes);
      setPipeline(pipeRes ?? []);
      setTrends(trendsRes ?? []);
      setCompliance(compRes);
    }).catch(() => {
      // fallback
    }).finally(() => setLoading(false));
  }, []);

  const stats = dashboard ? [
    { label: 'Total Applicants', value: String(dashboard.total_applicants ?? '—'), change: dashboard.applicant_change ?? '', icon: Users, color: 'from-purple-600 to-fuchsia-500' },
    { label: 'Diversity Rate', value: dashboard.diversity_rate ? `${dashboard.diversity_rate}%` : '—', change: dashboard.diversity_change ?? '', icon: PieChart, color: 'from-emerald-500 to-teal-500' },
    { label: 'Compliance Score', value: compliance?.score ? `${compliance.score}/100` : '—', change: compliance?.grade ?? '', icon: Shield, color: 'from-blue-600 to-indigo-500' },
    { label: 'At-Risk Openings', value: String(dashboard.at_risk_openings ?? '—'), change: dashboard.at_risk_change ?? '', icon: BarChart3, color: 'from-amber-500 to-orange-500' },
  ] : [
    { label: 'Total Applicants', value: '—', change: '', icon: Users, color: 'from-purple-600 to-fuchsia-500' },
    { label: 'Diversity Rate', value: '—', change: '', icon: PieChart, color: 'from-emerald-500 to-teal-500' },
    { label: 'Compliance Score', value: '—', change: '', icon: Shield, color: 'from-blue-600 to-indigo-500' },
    { label: 'At-Risk Openings', value: '—', change: '', icon: BarChart3, color: 'from-amber-500 to-orange-500' },
  ];

  const demographics = dashboard?.demographics ?? [];
  const genderData = dashboard?.gender_breakdown ?? [];
  const pipelineStages = pipeline.length > 0 ? pipeline : [];
  const monthlyTrends = trends.length > 0 ? trends : [];

  const totalHired = demographics.reduce((acc: number, x: any) => acc + (x.hired ?? 0), 0);
  const totalCount = demographics.reduce((acc: number, x: any) => acc + (x.count ?? 0), 0);

  const handleExport = () => {
    eeoService.exportReport('csv')
      .then(() => customToast({ type: 'success', title: 'EEO-1 Export', message: 'Your EEO-1 report is being generated and will download shortly.' }))
      .catch(() => customToast({ type: 'error', title: 'Error', message: 'Failed to export report.' }));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 text-violet-500 animate-spin" />
      </div>
    );
  }

  const maxPipelineValue = pipelineStages.length > 0 ? Math.max(...pipelineStages.flatMap(s => [s.white ?? 0, s.black ?? 0, s.hispanic ?? 0, s.asian ?? 0, s.other ?? 0])) : 1;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">EEO Compliance Dashboard</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Monitor diversity, equity & inclusion metrics across your hiring pipeline</p>
        </div>
        <Button variant="primary" leftIcon={<Download className="h-4 w-4" />} onClick={handleExport} className="font-bold shadow-md shadow-purple-500/25">Export EEO-1 Report</Button>
      </div>

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
                  <span className={cn('text-xs font-bold', stat.change.startsWith('+') ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400')}>{stat.change}</span>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      <Card className="glass-panel border-purple-200/50">
        <CardHeader>
          <CardTitle>EEO Analytics</CardTitle>
        </CardHeader>
        <CardContent>
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList>
              <TabsTrigger value="pipeline">Pipeline Diversity</TabsTrigger>
              <TabsTrigger value="selection">Selection Rates</TabsTrigger>
              <TabsTrigger value="trends">Trends</TabsTrigger>
              <TabsTrigger value="report">EEO-1 Report</TabsTrigger>
            </TabsList>

            <TabsContent value="pipeline">
              <div className="space-y-6 mt-2">
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                  {genderData.map((g: any) => (
                    <div key={g.label} className="p-4 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-bold text-gray-900 dark:text-white">{g.label}</span>
                        <Badge variant="primary" size="sm">{g.value}%</Badge>
                      </div>
                      <Progress value={g.value} color={g.label === 'Male' ? 'blue' : g.label === 'Female' ? 'default' : 'purple'} size="lg" />
                    </div>
                  ))}
                </div>

                <div className="p-4 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10">
                  <h3 className="text-sm font-extrabold text-gray-900 dark:text-white mb-4">Pipeline Funnel by Ethnicity</h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-purple-100 dark:border-white/10">
                          <th className="text-left py-2 pr-4 font-extrabold text-gray-900 dark:text-white">Stage</th>
                          <th className="text-left py-2 pr-4 font-semibold text-gray-700 dark:text-gray-300">
                            <span className="inline-block h-3 w-3 rounded-sm bg-blue-500 mr-1 align-middle" /> White
                          </th>
                          <th className="text-left py-2 pr-4 font-semibold text-gray-700 dark:text-gray-300">
                            <span className="inline-block h-3 w-3 rounded-sm bg-emerald-600 mr-1 align-middle" /> Black
                          </th>
                          <th className="text-left py-2 pr-4 font-semibold text-gray-700 dark:text-gray-300">
                            <span className="inline-block h-3 w-3 rounded-sm bg-amber-500 mr-1 align-middle" /> Hispanic
                          </th>
                          <th className="text-left py-2 pr-4 font-semibold text-gray-700 dark:text-gray-300">
                            <span className="inline-block h-3 w-3 rounded-sm bg-red-500 mr-1 align-middle" /> Asian
                          </th>
                          <th className="text-left py-2 font-semibold text-gray-700 dark:text-gray-300">
                            <span className="inline-block h-3 w-3 rounded-sm bg-purple-400 mr-1 align-middle" /> Other
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {pipelineStages.map((s: any) => (
                            <tr key={s.stage} className="border-b border-purple-50 dark:border-white/5">
                              <td className="py-3 pr-4 font-bold text-gray-900 dark:text-white">{s.stage}</td>
                              <td className="py-3 pr-4">
                                <div className="flex items-center gap-2">
                                  <div className="h-6 rounded bg-blue-500/80" style={{ width: `${(s.white / maxPipelineValue) * 100}%`, minWidth: s.white > 0 ? '4px' : 0 }} />
                                  <span className="text-xs text-gray-500">{s.white}</span>
                                </div>
                              </td>
                              <td className="py-3 pr-4">
                                <div className="flex items-center gap-2">
                                  <div className="h-6 rounded bg-emerald-600/80" style={{ width: `${(s.black / maxPipelineValue) * 100}%`, minWidth: s.black > 0 ? '4px' : 0 }} />
                                  <span className="text-xs text-gray-500">{s.black}</span>
                                </div>
                              </td>
                              <td className="py-3 pr-4">
                                <div className="flex items-center gap-2">
                                  <div className="h-6 rounded bg-amber-500/80" style={{ width: `${(s.hispanic / maxPipelineValue) * 100}%`, minWidth: s.hispanic > 0 ? '4px' : 0 }} />
                                  <span className="text-xs text-gray-500">{s.hispanic}</span>
                                </div>
                              </td>
                              <td className="py-3 pr-4">
                                <div className="flex items-center gap-2">
                                  <div className="h-6 rounded bg-red-500/80" style={{ width: `${(s.asian / maxPipelineValue) * 100}%`, minWidth: s.asian > 0 ? '4px' : 0 }} />
                                  <span className="text-xs text-gray-500">{s.asian}</span>
                                </div>
                              </td>
                              <td className="py-3">
                                <div className="flex items-center gap-2">
                                  <div className="h-6 rounded bg-purple-400/80" style={{ width: `${(s.other / maxPipelineValue) * 100}%`, minWidth: s.other > 0 ? '4px' : 0 }} />
                                  <span className="text-xs text-gray-500">{s.other}</span>
                                </div>
                              </td>
                            </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </TabsContent>

            <TabsContent value="selection">
              <div className="overflow-x-auto mt-2">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-purple-100 dark:border-white/10">
                      <th className="text-left py-3 pr-4 font-extrabold text-gray-900 dark:text-white">Demographic Group</th>
                      <th className="text-right py-3 pr-4 font-extrabold text-gray-900 dark:text-white">Applicants</th>
                      <th className="text-right py-3 pr-4 font-extrabold text-gray-900 dark:text-white">% of Total</th>
                      <th className="text-right py-3 pr-4 font-extrabold text-gray-900 dark:text-white">Hired</th>
                      <th className="text-right py-3 font-extrabold text-gray-900 dark:text-white">Hire Rate</th>
                      <th className="text-right py-3 pl-4 font-extrabold text-gray-900 dark:text-white">Impact Ratio</th>
                    </tr>
                  </thead>
                  <tbody>
                    {demographics.map((d: any) => {
                      const overallRate = totalCount > 0 ? (totalHired / totalCount) * 100 : 0;
                      const impactRatio = overallRate > 0 ? (d.hireRate / overallRate).toFixed(2) : '0.00';
                      return (
                        <tr key={d.group} className="border-b border-purple-50 dark:border-white/5 hover:bg-purple-50/50 dark:hover:bg-white/[0.02] transition-colors">
                          <td className="py-3 pr-4 font-bold text-gray-900 dark:text-white">{d.group}</td>
                          <td className="py-3 pr-4 text-right text-gray-700 dark:text-gray-300">{d.count.toLocaleString()}</td>
                          <td className="py-3 pr-4 text-right text-gray-700 dark:text-gray-300">{d.pct}%</td>
                          <td className="py-3 pr-4 text-right text-gray-700 dark:text-gray-300">{d.hired}</td>
                          <td className="py-3 pr-4 text-right">
                            <Badge variant={d.hireRate >= 5 ? 'success' : d.hireRate >= 4.5 ? 'primary' : 'warning'} size="sm">{d.hireRate}%</Badge>
                          </td>
                          <td className="py-3 pl-4 text-right">
                            <span className={cn('font-bold', Number(impactRatio) >= 1 ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600 dark:text-amber-400')}>{impactRatio}</span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <div className="mt-4 p-4 rounded-xl bg-purple-50/80 dark:bg-purple-950/20 border border-purple-200/60 dark:border-purple-500/20">
                <p className="text-sm text-gray-700 dark:text-gray-300">
                  <strong className="text-purple-800 dark:text-purple-300">Overall Selection Rate:</strong>{' '}
                  {totalCount > 0 ? ((totalHired / totalCount) * 100).toFixed(1) : '0.0'}% |{' '}
                  <strong className="text-purple-800 dark:text-purple-300">Impact Ratio:</strong> Values above 1.0 indicate favorable selection for the group
                </p>
              </div>
            </TabsContent>

            <TabsContent value="trends">
              <div className="space-y-4 mt-2">
                <div className="p-4 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10">
                  <h3 className="text-sm font-extrabold text-gray-900 dark:text-white mb-4">Monthly Diversity & Applicant Trends</h3>
                  <div className="flex items-end gap-3 h-48">
                    {monthlyTrends.map((m: any) => (
                      <div key={m.month} className="flex-1 flex flex-col items-center justify-end h-full">
                        <div className="w-full flex flex-col items-center gap-0.5">
                          <div
                            className="w-full rounded-t-md bg-gradient-to-t from-emerald-500 to-emerald-400"
                            style={{ height: `${(m.diversity / 50) * 180}px`, opacity: 0.85 }}
                            title={`Diversity: ${m.diversity}%`}
                          />
                          <div
                            className="w-full rounded-t-md bg-gradient-to-t from-purple-600 to-fuchsia-500"
                            style={{ height: `${(m.applicants / 500) * 140}px` }}
                            title={`Applicants: ${m.applicants}`}
                          />
                        </div>
                        <span className="text-[10px] font-bold text-gray-500 dark:text-gray-400 mt-1">{m.month}</span>
                      </div>
                    ))}
                  </div>
                  <div className="flex items-center gap-6 mt-3 justify-center">
                    <div className="flex items-center gap-2">
                      <span className="h-3 w-3 rounded-sm bg-emerald-400" />
                      <span className="text-xs text-gray-500 dark:text-gray-400">Diversity %</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="h-3 w-3 rounded-sm bg-purple-600" />
                      <span className="text-xs text-gray-500 dark:text-gray-400">Applicants</span>
                    </div>
                  </div>
                </div>
              </div>
            </TabsContent>

            <TabsContent value="report">
              <div className="space-y-4 mt-2">
                <div className="p-4 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10">
                  <h3 className="text-sm font-extrabold text-gray-900 dark:text-white mb-3">EEO-1 Component Summary</h3>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div className="p-3 rounded-lg bg-purple-50/50 dark:bg-purple-950/20 border border-purple-100 dark:border-white/10">
                      <span className="text-xs text-gray-500 dark:text-gray-400">Report Period</span>
                      <p className="text-sm font-bold text-gray-900 dark:text-white">{compliance?.report_period || 'Jan 1 - Dec 31, 2026'}</p>
                    </div>
                    <div className="p-3 rounded-lg bg-purple-50/50 dark:bg-purple-950/20 border border-purple-100 dark:border-white/10">
                      <span className="text-xs text-gray-500 dark:text-gray-400">Establishment</span>
                      <p className="text-sm font-bold text-gray-900 dark:text-white">{compliance?.establishment || 'Tunisia Operations (Primary)'}</p>
                    </div>
                    <div className="p-3 rounded-lg bg-purple-50/50 dark:bg-purple-950/20 border border-purple-100 dark:border-white/10">
                      <span className="text-xs text-gray-500 dark:text-gray-400">Total Employees</span>
                      <p className="text-sm font-bold text-gray-900 dark:text-white">{compliance?.total_employees ? `${compliance.total_employees} (Full-Time Equivalent)` : '342 (Full-Time Equivalent)'}</p>
                    </div>
                    <div className="p-3 rounded-lg bg-purple-50/50 dark:bg-purple-950/20 border border-purple-100 dark:border-white/10">
                      <span className="text-xs text-gray-500 dark:text-gray-400">Job Categories</span>
                      <p className="text-sm font-bold text-gray-900 dark:text-white">{compliance?.job_categories ? `${compliance.job_categories} (EEO-1 Standard)` : '10 (EEO-1 Standard)'}</p>
                    </div>
                  </div>
                </div>
                <div className="flex justify-end">
                  <Button variant="primary" leftIcon={<Download className="h-4 w-4" />} onClick={handleExport} className="font-bold shadow-md shadow-purple-500/25">Download Full EEO-1 Report (PDF)</Button>
                </div>
              </div>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      <Card className="glass-panel border-purple-200/50">
        <CardHeader>
          <CardTitle>Compliance Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="p-4 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10 md:col-span-1 flex flex-col items-center justify-center">
              <div className="relative h-28 w-28 flex items-center justify-center">
                <svg className="h-full w-full -rotate-90" viewBox="0 0 36 36">
                  <circle cx="18" cy="18" r="15.5" fill="none" stroke="currentColor" strokeWidth="2" className="text-purple-100 dark:text-purple-500/20" />
                  <circle cx="18" cy="18" r="15.5" fill="none" stroke="currentColor" strokeWidth="2" strokeDasharray={`${(compliance?.score || 87) * 1.12}`} strokeDashoffset={`${112 - (compliance?.score || 87) * 1.12}`} className="text-emerald-500" />
                </svg>
                <span className="absolute text-2xl font-extrabold text-gray-900 dark:text-white">{compliance?.score ?? 87}</span>
              </div>
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400 mt-1">Overall Score</span>
            </div>
            <div className="md:col-span-3 space-y-3">
              {(compliance?.sub_scores && Array.isArray(compliance.sub_scores) ? compliance.sub_scores : [
                { label: 'Data Completeness', score: 94, status: 'Excellent' },
                { label: 'Demographic Reporting', score: 88, status: 'Good' },
                { label: 'Policy Adherence', score: 92, status: 'Excellent' },
                { label: 'Hiring Equity', score: 78, status: 'Needs Improvement' },
              ]).map((item: any) => (
                <div key={item.label} className="flex items-center gap-4">
                  <span className="text-sm font-bold text-gray-900 dark:text-white w-40">{item.label}</span>
                  <div className="flex-1">
                    <Progress value={item.score} color={item.score >= 90 ? 'green' : item.score >= 80 ? 'default' : 'amber'} size="md" />
                  </div>
                  <Badge variant={item.score >= 90 ? 'success' : item.score >= 80 ? 'primary' : 'warning'} size="sm">{item.score}%</Badge>
                </div>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
