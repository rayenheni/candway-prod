import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Progress } from '@/shared/components/ui/progress';
import { customToast } from '@/shared/components/ui/toast';
import { Download } from 'lucide-react';
import { cn } from '@/utils/cn';
import apiClient from '@/lib/api-client';

interface Department {
  name: string;
  employees: number;
  responses: number;
  coverage: number;
  status: string;
}

type FilterStatus = 'all' | 'compliant' | 'partial';

interface CoverageStats {
  coverage_rate?: number;
  total_applicants_with_eeo?: number;
  total_applicants?: number;
  gender_balance_ratio?: number;
  adverse_impact_flags?: number;
}

interface ApiDepartment {
  job_title?: string;
  total_applicants?: number;
  eeo_provided?: number;
  coverage_rate?: number;
}

function toStatus(coverage: number): string {
  return coverage >= 85 ? 'compliant' : 'partial';
}

export default function EeoCoveragePage() {
  const [filter, setFilter] = useState<FilterStatus>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [departments, setDepartments] = useState<Department[]>([]);
  const [overallCoverage, setOverallCoverage] = useState(0);
  const [totalEmployees, setTotalEmployees] = useState(0);
  const [totalResponses, setTotalResponses] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchCoverage = async () => {
      try {
        setLoading(true);
        setError(null);
        const [rateData, detailData]: any = await Promise.all([
          apiClient.get('/recruiter/eeo/coverage-rate'),
          apiClient.get('/recruiter/eeo/coverage-detail'),
        ]);
        if (cancelled) return;

        const stats: CoverageStats = rateData?.coverage ?? {};
        const detail = detailData?.coverage ?? {};
        const raw: ApiDepartment[] = Array.isArray(detail) ? detail : detail?.by_job ?? [];

        const mapped: Department[] = raw.map((d) => {
          const name = d.job_title ?? 'Unknown';
          const employees = d.total_applicants ?? 0;
          const responses = d.eeo_provided ?? 0;
          const coverage = d.coverage_rate ?? 0;
          return { name, employees, responses, coverage, status: toStatus(coverage) };
        });

        setDepartments(mapped);
        setOverallCoverage(stats.coverage_rate ?? 0);
        setTotalEmployees(stats.total_applicants ?? mapped.reduce((acc, d) => acc + d.employees, 0));
        setTotalResponses(stats.total_applicants_with_eeo ?? mapped.reduce((acc, d) => acc + d.responses, 0));
      } catch (e: unknown) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load EEO coverage data.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchCoverage();
    return () => { cancelled = true; };
  }, []);

  const filtered = departments.filter(d => {
    if (filter !== 'all' && d.status !== filter) return false;
    if (searchQuery && !d.name.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  const [exporting, setExporting] = useState(false);

  const handleExport = async () => {
    try {
      setExporting(true);
      const blob = await apiClient.postBlob('/recruiter/eeo/export/csv?group_by=gender');
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const date = new Date().toISOString().slice(0, 10);
      a.download = `eeo_report_${date}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      customToast({ type: 'success', title: 'Coverage Report', message: 'EEO coverage report downloaded as CSV.' });
    } catch (err: any) {
      customToast({ type: 'error', title: 'Export Failed', message: err?.message || 'Could not export the coverage report.' });
    } finally {
      setExporting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-purple-200 border-t-purple-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-64 flex-col items-center justify-center space-y-4">
        <p className="text-sm text-red-500">{error}</p>
        <Button variant="outline" onClick={() => window.location.reload()}>Retry</Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">EEO Coverage Report</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Track EEO self-identification response rates across departments</p>
        </div>
        <Button variant="primary" leftIcon={<Download className="h-4 w-4" />} onClick={handleExport} disabled={exporting} className="font-bold shadow-md shadow-purple-500/25">{exporting ? 'Exporting...' : 'Export Coverage Data'}</Button>
      </div>

      <Card className="glass-panel border-purple-200/50">
        <CardContent className="p-6">
          <div className="flex flex-col items-center text-center mb-4">
            <div className="relative h-36 w-36 flex items-center justify-center mb-3">
              <svg className="h-full w-full -rotate-90" viewBox="0 0 36 36">
                <circle cx="18" cy="18" r="15.5" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-purple-100 dark:text-purple-500/20" />
                <circle
                  cx="18" cy="18" r="15.5" fill="none" stroke="currentColor" strokeWidth="2.5"
                  strokeDasharray="97.39"
                  strokeDashoffset={97.39 - (97.39 * overallCoverage) / 100}
                  className={cn(
                    overallCoverage >= 95 ? 'text-emerald-500' : overallCoverage >= 85 ? 'text-amber-500' : 'text-red-500'
                  )}
                  strokeLinecap="round"
                />
              </svg>
              <span className="absolute text-3xl font-extrabold text-gray-900 dark:text-white">{overallCoverage}%</span>
            </div>
            <h2 className="text-lg font-extrabold text-gray-900 dark:text-white">Overall Coverage Rate</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{totalResponses.toLocaleString()} of {totalEmployees.toLocaleString()} applicants have submitted EEO data</p>
          </div>
          <Progress value={overallCoverage} color={overallCoverage >= 95 ? 'green' : overallCoverage >= 85 ? 'amber' : 'red'} size="lg" showLabel />
        </CardContent>
      </Card>

      <Card className="glass-panel border-purple-200/50">
        <CardHeader>
          <div className="flex items-center justify-between w-full">
            <div>
              <CardTitle>Coverage by Job</CardTitle>
            </div>
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1 bg-purple-50/80 dark:bg-purple-500/10 rounded-lg p-1 border border-purple-200/40 dark:border-purple-500/15">
                {(['all', 'compliant', 'partial'] as const).map(s => (
                  <button
                    key={s}
                    onClick={() => setFilter(s)}
                    className={cn(
                      'px-3 py-1.5 text-xs font-medium rounded-md transition-all capitalize',
                      filter === s
                        ? 'bg-white dark:bg-purple-500/20 text-purple-800 dark:text-white shadow-sm'
                        : 'text-gray-500 dark:text-gray-400 hover:text-purple-700 dark:hover:text-purple-300'
                    )}
                  >
                    {s === 'all' ? 'All' : s}
                  </button>
                ))}
              </div>
              <input
                type="text"
                placeholder="Search jobs..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                className="h-8 w-44 rounded-lg border border-purple-200/60 dark:border-purple-500/20 bg-white/70 dark:bg-white/[0.04] px-3 text-xs font-medium text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-purple-100 dark:border-white/10">
                  <th className="text-left py-3 pr-4 font-extrabold text-gray-900 dark:text-white">Job</th>
                  <th className="text-right py-3 pr-4 font-extrabold text-gray-900 dark:text-white">Total Applicants</th>
                  <th className="text-right py-3 pr-4 font-extrabold text-gray-900 dark:text-white">EEO Responses</th>
                  <th className="text-right py-3 pr-4 font-extrabold text-gray-900 dark:text-white">Coverage %</th>
                  <th className="text-right py-3 font-extrabold text-gray-900 dark:text-white">Status</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(d => (
                  <tr key={d.name} className="border-b border-purple-50 dark:border-white/5 hover:bg-purple-50/50 dark:hover:bg-white/[0.02] transition-colors">
                    <td className="py-3 pr-4 font-bold text-gray-900 dark:text-white">{d.name}</td>
                    <td className="py-3 pr-4 text-right text-gray-700 dark:text-gray-300">{d.employees}</td>
                    <td className="py-3 pr-4 text-right text-gray-700 dark:text-gray-300">{d.responses}</td>
                    <td className="py-3 pr-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <span className="font-bold text-gray-900 dark:text-white">{d.coverage.toFixed(1)}%</span>
                        <Progress value={d.coverage} color={d.coverage >= 95 ? 'green' : d.coverage >= 85 ? 'amber' : 'red'} size="sm" className="w-20" />
                      </div>
                    </td>
                    <td className="py-3 text-right">
                      <Badge variant={d.status === 'compliant' ? 'success' : 'warning'} size="sm" dot>
                        {d.status === 'compliant' ? 'Compliant' : 'Partial'}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {filtered.length === 0 && (
            <div className="text-center py-8 text-sm text-gray-500 dark:text-gray-400">
              No jobs match the current filter.
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
