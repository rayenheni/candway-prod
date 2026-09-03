import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { customToast } from '@/shared/components/ui/toast';
import { useLanguage } from '@/contexts/language-context';
import { FileText, Printer, Shield, User, Briefcase, GraduationCap, Loader2, CheckCircle2, AlertTriangle } from 'lucide-react';
import { cn } from '@/utils/cn';
import { candidatesService } from '@/services/candidates.service';

interface GhostReport {
  id: number;
  ghost_name?: string;
  role?: string;
  job_title?: string;
  summary?: string;
  strengths?: string[];
  weaknesses?: string[];
  experience?: { title?: string; duration?: string; description?: string }[];
  interview_highlights?: string[];
  metrics?: Record<string, number>;
  scores?: { cv?: number; interview?: number };
  prepared_by?: string;
  agency?: string;
  methodology?: string;
  generated_at?: string;
}

export default function GhostReportPage() {
  const { t } = useLanguage();
  const [candidateList, setCandidateList] = useState<any[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showDropdown, setShowDropdown] = useState(false);
  const [report, setReport] = useState<GhostReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingReport, setLoadingReport] = useState(false);

  useEffect(() => {
    const fetchCandidates = async () => {
      try {
        setLoading(true);
        const data = await candidatesService.getCandidates({ per_page: 50 });
        const items: any[] = data?.items ?? [];
        setCandidateList(items);
        if (items.length > 0) {
          setSelectedId(String(items[0].id ?? items[0].userId));
        }
      } catch (err: any) {
        customToast({ type: 'error', title: t('common.status'), message: err?.message || 'Failed to load candidates' });
      } finally {
        setLoading(false);
      }
    };
    fetchCandidates();
  }, [t]);

  const fetchGhostData = useCallback(async () => {
    if (!selectedId) return;
    try {
      setLoadingReport(true);
      const data = await candidatesService.getGhostData(selectedId);
      setReport(data);
    } catch (err: any) {
      customToast({ type: 'error', title: t('common.status'), message: err?.message || 'Failed to load ghost data' });
      setReport(null);
    } finally {
      setLoadingReport(false);
    }
  }, [selectedId, t]);

  useEffect(() => {
    if (selectedId) fetchGhostData();
  }, [selectedId, fetchGhostData]);

  const getCandidateName = (c: any) => c.name || `${c.user?.firstName || ''} ${c.user?.lastName || ''}`.trim() || c.id || '';

  const handlePrint = () => {
    window.print();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 text-violet-500 animate-spin" />
      </div>
    );
  }

  const metrics = Object.entries(report?.metrics ?? {});
  const strengths = report?.strengths ?? [];
  const weaknesses = report?.weaknesses ?? [];
  const experience = report?.experience ?? [];
  const highlights = report?.interview_highlights ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">{t('recruiter.ghostReport.title')}</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{t('recruiter.ghostReport.subtitle')}</p>
        </div>
        <div className="relative">
          <Button variant="outline" onClick={() => setShowDropdown(!showDropdown)} className="font-medium min-w-[200px] justify-between">
            <User className="h-4 w-4 mr-2 text-purple-500" />
            {selectedId ? (candidateList.find(c => String(c.id ?? c.userId) === selectedId)?.name || t('role.candidate')) : t('recruiter.ghostReport.selectCandidate')}
          </Button>
          {showDropdown && (
            <div className="absolute right-0 mt-2 w-64 rounded-xl border border-purple-100 dark:border-white/10 bg-white dark:bg-gray-900 shadow-xl z-50 overflow-hidden">
              {candidateList.map(c => (
                <button key={c.id} className={cn('w-full px-4 py-2.5 text-left text-sm hover:bg-purple-50 dark:hover:bg-purple-500/10 transition-colors', String(c.id ?? c.userId) === selectedId && 'bg-purple-50 dark:bg-purple-500/10 font-bold text-purple-700 dark:text-purple-300')} onClick={() => { setSelectedId(String(c.id ?? c.userId)); setShowDropdown(false); }}>
                  {getCandidateName(c)}
                </button>
              ))}
              {candidateList.length === 0 && (
                <div className="px-4 py-3 text-sm text-gray-400">{t('common.noData')}</div>
              )}
            </div>
          )}
        </div>
      </div>

      <Card className="glass-panel border-purple-200/50">
        <CardHeader>
          <div className="flex items-center justify-between w-full">
            <div>
              <CardTitle>{t('recruiter.ghostReport.preview')}</CardTitle>
              <CardDescription>{t('recruiter.ghostReport.previewDesc')}</CardDescription>
            </div>
            <Badge variant="success" size="sm" dot className="font-bold">
              <Shield className="h-3 w-3 mr-1" /> {t('recruiter.ghostReport.piiProtected')}
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          {loadingReport ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 text-violet-500 animate-spin" />
            </div>
          ) : !report ? (
            <div className="flex flex-col items-center justify-center py-12 text-gray-500">
              <p className="text-lg font-semibold">{t('recruiter.ghostReport.noData')}</p>
              <p className="text-sm">{t('recruiter.ghostReport.noDataDesc')}</p>
            </div>
          ) : (
            <div className="space-y-5">
              {report.job_title && (
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm text-gray-500 dark:text-gray-400">{t('jobs.title')}:</span>
                  <Badge variant="info" size="sm">{report.job_title}</Badge>
                  {report.ghost_name && <Badge variant="default" size="sm">{report.ghost_name}</Badge>}
                </div>
              )}

              {(report.scores?.cv != null || report.scores?.interview != null) && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {report.scores.cv != null && (
                    <div className="p-3 rounded-lg bg-purple-50/50 dark:bg-purple-950/20 border border-purple-100 dark:border-white/10">
                      <p className="text-xs text-gray-500 dark:text-gray-400">{t('recruiter.ghostReport.cvScore')}</p>
                      <p className="text-2xl font-extrabold text-gray-900 dark:text-white">{report.scores.cv}%</p>
                    </div>
                  )}
                  {report.scores.interview != null && (
                    <div className="p-3 rounded-lg bg-purple-50/50 dark:bg-purple-950/20 border border-purple-100 dark:border-white/10">
                      <p className="text-xs text-gray-500 dark:text-gray-400">{t('recruiter.ghostReport.interviewScore')}</p>
                      <p className="text-2xl font-extrabold text-gray-900 dark:text-white">{report.scores.interview}%</p>
                    </div>
                  )}
                </div>
              )}

              {report.summary && (
                <div className="p-3 rounded-lg bg-purple-50/50 dark:bg-purple-950/20 border border-purple-100 dark:border-white/10">
                  <p className="text-xs font-bold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider mb-1">{t('recruiter.ghostReport.summary')}</p>
                  <p className="text-sm text-gray-800 dark:text-gray-200">{report.summary}</p>
                </div>
              )}

              {metrics.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{t('analytics.metrics')}</p>
                  {metrics.map(([key, value]) => (
                    <div key={key} className="flex items-center gap-3">
                      <span className="text-sm text-gray-600 dark:text-gray-400 w-32 shrink-0">{key}</span>
                      <div className="flex-1 h-2 bg-gray-100 dark:bg-white/5 rounded-full overflow-hidden">
                        <div className="h-full rounded-full bg-emerald-500" style={{ width: `${Math.min(100, Math.max(0, value))}%` }} />
                      </div>
                      <span className="text-sm font-medium text-gray-700 dark:text-gray-300 w-10 text-right">{Math.round(value)}</span>
                    </div>
                  ))}
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {strengths.length > 0 && (
                  <div>
                    <p className="text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">{t('recruiter.ghostReport.strengths')}</p>
                    <div className="space-y-1.5">
                      {strengths.map((s, i) => (
                        <div key={i} className="flex items-start gap-2 text-sm text-gray-800 dark:text-gray-200">
                          <CheckCircle2 className="h-4 w-4 text-emerald-500 mt-0.5 shrink-0" />
                          {s}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {weaknesses.length > 0 && (
                  <div>
                    <p className="text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">{t('recruiter.ghostReport.growthAreas')}</p>
                    <div className="space-y-1.5">
                      {weaknesses.map((s, i) => (
                        <div key={i} className="flex items-start gap-2 text-sm text-gray-800 dark:text-gray-200">
                          <AlertTriangle className="h-4 w-4 text-amber-500 mt-0.5 shrink-0" />
                          {s}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {experience.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{t('recruiter.ghostReport.experience')}</p>
                  {experience.map((exp, i) => (
                    <div key={i} className="p-3 rounded-lg bg-purple-50/50 dark:bg-purple-950/20 border border-purple-100 dark:border-white/10">
                      <div className="flex items-center gap-2">
                        <Briefcase className="h-4 w-4 text-purple-500 shrink-0" />
                        <span className="text-sm font-bold text-gray-900 dark:text-white">{exp.title || t('recruiter.ghostReport.experience')}</span>
                        {exp.duration && <span className="text-xs text-gray-500 dark:text-gray-400">{exp.duration}</span>}
                      </div>
                      {exp.description && <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">{exp.description}</p>}
                    </div>
                  ))}
                </div>
              )}

              {highlights.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{t('recruiter.ghostReport.interviewHighlights')}</p>
                  {highlights.map((h, i) => (
                    <div key={i} className="flex items-start gap-2 text-sm text-gray-800 dark:text-gray-200">
                      <GraduationCap className="h-4 w-4 text-purple-500 mt-0.5 shrink-0" />
                      {h}
                    </div>
                  ))}
                </div>
              )}

              {(report.prepared_by || report.agency) && (
                <p className="text-xs text-gray-400 dark:text-gray-500">
                  {report.agency ? `Prepared by ${report.agency}` : ''}
                  {report.prepared_by ? `${report.agency ? ' · ' : 'Prepared by '}${report.prepared_by}` : ''}
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="glass-panel border-purple-200/50">
        <CardHeader>
          <CardTitle>{t('recruiter.ghostReport.actions')}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-3">
            <Button variant="outline" leftIcon={<Printer className="h-4 w-4" />} onClick={handlePrint} disabled={!report}>
              {t('recruiter.ghostReport.print')}
            </Button>
            <Button variant="outline" leftIcon={<FileText className="h-4 w-4" />} onClick={fetchGhostData} disabled={!selectedId || loadingReport}>
              {t('recruiter.ghostReport.regenerate')}
            </Button>
          </div>
          <div className="mt-3 p-3 rounded-lg bg-purple-50/80 dark:bg-purple-950/20 border border-purple-200/60 dark:border-purple-500/20">
            <p className="text-xs text-gray-600 dark:text-gray-400 flex items-center gap-1.5">
              <Shield className="h-3.5 w-3.5 text-emerald-500" />
              {t('recruiter.ghostReport.privacyNotice')}
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
