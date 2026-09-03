import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { useLanguage } from '@/contexts/language-context';
import { cn } from '@/utils/cn';
import {
  Download,
  Calendar,
  FileText,
  Filter,
  Loader2,
  Search,
} from 'lucide-react';
import { reportsService } from '@/services/reports.service';
import { useNavigate } from 'react-router';

const typeColors: Record<string, string> = {
  Hiring: 'primary',
  Analytics: 'info',
  Compliance: 'success',
  Performance: 'warning',
};

function getReportType(report: any): string {
  return report.config?.type || 'Custom';
}

function getReportStatus(report: any): string {
  return report.status || (report.last_generated_at ? 'ready' : 'draft');
}

function formatDate(report: any): string {
  const date = report.created_at || report.updated_at;
  if (!date) return '-';
  return new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

export default function ReportsDashboard() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [reports, setReports] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [exportingId, setExportingId] = useState<number | null>(null);

  useEffect(() => {
    reportsService.list({ per_page: 50 })
      .then((res) => {
        setReports(res.reports || []);
        setTotal(res.total || 0);
      })
      .catch(() => {
        setReports([]);
        setTotal(0);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  const scheduledCount = reports.filter(r => r.is_scheduled === true).length;
  const quickStats = [
    { label: t('nav.reports'), value: String(total), icon: FileText, color: 'bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400' },
    { label: t('candidates.scheduled'), value: String(scheduledCount), icon: Calendar, color: 'bg-purple-50 text-purple-600 dark:bg-purple-500/10 dark:text-purple-400' },
  ];

  const filtered = reports.filter((r: any) =>
    (r.name || '').toLowerCase().includes(search.toLowerCase())
  );

  const handleGenerate = () => {
    navigate('/report-builder');
  };

  const handleExport = async (reportId: number, format: 'csv' | 'pdf') => {
    setExportingId(reportId);
    try {
      await reportsService.export(String(reportId), format);
    } catch {
      // export handled by browser download
    } finally {
      setExportingId(null);
    }
  };

  const handleRowClick = (reportId: number) => {
    navigate(`/report-builder?report_id=${reportId}`);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{t('nav.reports')}</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            {t('nav.analytics')}
          </p>
        </div>
        <Button variant="primary" leftIcon={<FileText className="h-4 w-4" />} onClick={handleGenerate}>{t('nav.reports')}</Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {quickStats.map((stat, i) => (
          <motion.div key={stat.label} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: i * 0.05 }}>
            <Card>
              <CardContent>
                <div className="flex items-center gap-3">
                  <div className={cn('flex h-10 w-10 items-center justify-center rounded-xl', stat.color)}>
                    <stat.icon className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-gray-900 dark:text-white">{stat.value}</div>
                    <div className="text-sm text-gray-500 dark:text-gray-400">{stat.label}</div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between w-full">
            <div>
              <CardTitle>{t('reports.recentTitle')}</CardTitle>
              <CardDescription>{t('reports.recentDesc')}</CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                <input
                  type="text"
                  placeholder={t('reports.filterPlaceholder')}
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="pl-9 pr-4 py-2 text-sm rounded-lg border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 text-gray-900 dark:text-white placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-violet-500/20 focus:border-violet-400"
                />
              </div>
              <Button variant="outline" size="sm" leftIcon={<Filter className="h-4 w-4" />} onClick={() => {}}>{t('common.filter')}</Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
            </div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-12">
              <FileText className="mx-auto h-12 w-12 text-gray-300 dark:text-gray-600" />
              <p className="mt-3 text-sm text-gray-500 dark:text-gray-400">{t('reports.empty')}</p>
            </div>
          ) : (
            <div className="space-y-3">
              {filtered.map((report, i) => (
                <motion.div
                  key={report.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3, delay: i * 0.05 }}
                  onClick={() => handleRowClick(report.id)}
                  className="flex items-center justify-between p-4 rounded-xl border border-gray-100 dark:border-white/[0.04] hover:border-gray-200 dark:hover:border-white/[0.08] transition-colors cursor-pointer"
                >
                  <div className="flex items-center gap-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gray-100 dark:bg-white/[0.06]">
                      <FileText className="h-5 w-5 text-gray-600 dark:text-gray-400" />
                    </div>
                    <div>
                      <h3 className="text-sm font-medium text-gray-900 dark:text-white">{report.name}</h3>
                      <p className="text-xs text-gray-500 dark:text-gray-400">{report.description}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <Badge variant={typeColors[getReportType(report)] as any} size="sm">{getReportType(report)}</Badge>
                    <Badge variant={report.status === 'ready' ? 'success' : 'default'} size="sm">{getReportStatus(report)}</Badge>
                    <span className="text-xs text-gray-500 dark:text-gray-400">{formatDate(report)}</span>
                    {report.status === 'ready' && (
                      <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                        <Button
                          variant="ghost"
                          size="sm"
                          leftIcon={exportingId === report.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleExport(report.id, 'csv');
                          }}
                        >
                          CSV
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          leftIcon={exportingId === report.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleExport(report.id, 'pdf');
                          }}
                        >
                          PDF
                        </Button>
                      </div>
                    )}
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
