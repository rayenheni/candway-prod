import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { useLanguage } from '@/contexts/language-context';
import { jobsService } from '@/services/jobs.service';
import { candidatesService } from '@/services/candidates.service';
import { Award, TrendingUp, Search, Star, ChevronDown, Eye, GitCompare } from 'lucide-react';
import { cn } from '@/utils/cn';

const tierConfig: Record<string, { label: string; class: string }> = {
  A: { label: 'Platinum', class: 'bg-purple-100 text-purple-700 dark:bg-purple-500/20 dark:text-purple-300' },
  B: { label: 'Gold', class: 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300' },
  C: { label: 'Silver', class: 'bg-slate-100 text-slate-700 dark:bg-slate-500/20 dark:text-slate-300' },
};

export default function CandidateRankingPage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [jobsList, setJobsList] = useState<any[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<any[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [search, setSearch] = useState('');
  const [loadingJobs, setLoadingJobs] = useState(true);
  const [loadingCandidates, setLoadingCandidates] = useState(false);
  void loadingJobs;
  void loadingCandidates;

  useEffect(() => {
    jobsService.getJobs({ per_page: 50 })
      .then(res => {
        const items = res?.items ?? [];
        setJobsList(items);
        if (items.length > 0) {
          setSelectedJobId(String(items[0].id));
        }
      })
      .catch(() => setJobsList([]))
      .finally(() => setLoadingJobs(false));
  }, []);

  useEffect(() => {
    if (!selectedJobId) return;
    setLoadingCandidates(true);
    candidatesService.getRankedCandidates(selectedJobId)
      .then(res => {
        const data = Array.isArray(res) ? res : (res?.candidates ?? []);
        setCandidates(data.map((c: any, i: number) => {
          // CANONICAL SCORE: ranking uses final_score when available.
          // score/overall_score are legacy compatibility fields only.
          const score = c.final_score ?? c.score ?? c.overall_score ?? 0;
          return {
            rank: c.rank ?? i + 1,
            name: c.name ?? c.full_name ?? c.candidate_name ?? 'Unknown',
            score,
            tier: score >= 85 ? 'A' : score >= 70 ? 'B' : 'C',
            skills: c.skills ?? [],
            role: c.role ?? '',
            email: c.email ?? '',
            id: c.id ?? c.application_id,
          };
        }));
      })
      .catch(() => setCandidates([]))
      .finally(() => setLoadingCandidates(false));
  }, [selectedJobId]);

  const filtered = candidates.filter(c => c.name.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">{t('nav.ranking')}</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{t('candidates.subtitle')}</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Button variant="outline" rightIcon={<ChevronDown className="h-4 w-4" />} onClick={() => setShowDropdown(!showDropdown)} className="font-medium">
              <Award className="h-4 w-4 mr-2 text-purple-500" />
              {jobsList.find(j => String(j.id) === selectedJobId)?.title || t('candidates.allJobs')}
            </Button>
            {showDropdown && (
              <div className="absolute right-0 mt-2 w-72 rounded-xl border border-purple-100 dark:border-white/10 bg-white dark:bg-gray-900 shadow-xl z-50 overflow-hidden">
                {jobsList.map(job => (
                  <button key={job.id} className={cn('w-full px-4 py-2.5 text-left text-sm hover:bg-purple-50 dark:hover:bg-purple-500/10 transition-colors', String(job.id) === selectedJobId && 'bg-purple-50 dark:bg-purple-500/10 font-bold text-purple-700 dark:text-purple-300')} onClick={() => { setSelectedJobId(String(job.id)); setShowDropdown(false); }}>
                    {job.title}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <Input placeholder={t('common.search')} leftIcon={<Search className="h-4 w-4 text-purple-500" />} value={search} onChange={(e) => setSearch(e.target.value)} />

      <Card className="glass-panel border-purple-200/50 overflow-hidden">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-purple-500" />
              {jobsList.find(j => String(j.id) === selectedJobId)?.title || t('jobs.title')}
            </CardTitle>
            <Badge variant="primary" size="sm">{filtered.length} {t('candidates.candidatesLabel')}</Badge>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-purple-100 dark:border-white/10 text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  <th className="px-6 py-3 text-left">#</th>
                  <th className="px-6 py-3 text-left">{t('candidates.col.name')}</th>
                  <th className="px-6 py-3 text-left">{t('recruiter.interviewAnalysis.overallScore')}</th>
                  <th className="px-6 py-3 text-left">{t('candidates.col.tier')}</th>
                  <th className="px-6 py-3 text-left">{t('cprofile.skillsCompetencies')}</th>
                  <th className="px-6 py-3 text-right">{t('common.actions')}</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((c, i) => (
                  <motion.tr key={c.email} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.25, delay: i * 0.04 }} className={cn('border-b border-purple-50 dark:border-white/5 hover:bg-purple-50/50 dark:hover:bg-purple-500/5 transition-colors', i < 3 && 'bg-gradient-to-r from-purple-50/40 to-transparent dark:from-purple-500/5')}>
                    <td className="px-6 py-4">
                      <div className={cn('flex items-center justify-center h-8 w-8 rounded-lg font-black text-sm', c.rank === 1 ? 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300' : c.rank === 2 ? 'bg-slate-100 text-slate-600 dark:bg-slate-500/20 dark:text-slate-300' : c.rank === 3 ? 'bg-orange-100 text-orange-700 dark:bg-orange-500/20 dark:text-orange-300' : 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400')}>
                        {c.rank}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-gray-900 dark:text-white">{c.name}</span>
                        {c.rank === 1 && <Star className="h-4 w-4 text-amber-400 fill-current" />}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <div className="h-2 w-16 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden">
                          <div className={cn('h-full rounded-full', c.score >= 90 ? 'bg-gradient-to-r from-purple-500 to-violet-500' : c.score >= 80 ? 'bg-purple-500' : c.score >= 70 ? 'bg-amber-500' : 'bg-slate-400')} style={{ width: `${c.score}%` }} />
                        </div>
                        <span className={cn('text-sm font-extrabold', c.score >= 90 ? 'text-purple-700 dark:text-purple-300' : c.score >= 80 ? 'text-purple-600 dark:text-purple-400' : c.score >= 70 ? 'text-amber-600 dark:text-amber-400' : 'text-slate-500')}>
                          {c.score}%
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <Badge className={cn('font-bold', tierConfig[c.tier].class)} size="sm">
                        {c.tier} — {tierConfig[c.tier].label}
                      </Badge>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex flex-wrap gap-1">
                        {c.skills.length > 0
                          ? c.skills.map((s: string) => <Badge key={s} variant="default" size="sm">{s}</Badge>)
                          : c.role
                            ? <Badge variant="default" size="sm">{c.role}</Badge>
                            : <span className="text-gray-400">—</span>}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button variant="ghost" size="sm" leftIcon={<Eye className="h-3.5 w-3.5" />} onClick={() => navigate(`/candidates/${c.id}`)}>{t('common.view')}</Button>
                        <Button variant="ghost" size="sm" leftIcon={<GitCompare className="h-3.5 w-3.5" />} onClick={() => navigate(`/compare?ids=${c.id}`)}>{t('compare.title')}</Button>
                      </div>
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
