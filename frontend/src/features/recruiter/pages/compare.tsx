import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Progress } from '@/shared/components/ui/progress';
import { customToast } from '@/shared/components/ui/toast';
import { Users, ArrowRight, CheckCircle2, TrendingUp, Star, Loader2 } from 'lucide-react';
import { cn } from '@/utils/cn';
import { candidatesService } from '@/services/candidates.service';
import { useLanguage } from '@/contexts/language-context';

interface ComparisonCandidate {
  id: string;
  name: string;
  score: number;
  skills: string[];
  exp: number;
  edu: string;
  strengths: string[];
  weaknesses: string[];
  cultureFit: number;
}

const comparisonRows = ['Overall Score', 'Skills', 'Experience', 'Education', 'Strengths', 'Weaknesses', 'Culture Fit'];

export default function ComparePage() {
  const { t } = useLanguage();
  const [searchParams] = useSearchParams();
  const [idsInput, setIdsInput] = useState('');
  const [candidates, setCandidates] = useState<ComparisonCandidate[]>([]);
  const [candidateA, setCandidateA] = useState<ComparisonCandidate | null>(null);
  const [candidateB, setCandidateB] = useState<ComparisonCandidate | null>(null);
  const [dropdownFor, setDropdownFor] = useState<'A' | 'B' | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const fetchComparison = async (ids: string[]) => {
    setLoading(true);
    setError('');
    setCandidates([]);
    setCandidateA(null);
    setCandidateB(null);
    try {
      const res = await candidatesService.compareCandidates(ids);
      const data = (res as any).data ?? (res as any);
      const list: ComparisonCandidate[] = Array.isArray(data) ? data : Array.isArray(data?.candidates) ? data.candidates : [];
      setCandidates(list);
      if (list.length >= 2) {
        setCandidateA(list[0]);
        setCandidateB(list[1]);
      }
    } catch {
      setError('Failed to load comparison data. Please check the application IDs and try again.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const urlIds = (searchParams.get('ids') || '')
      .split(',')
      .map(s => s.trim())
      .filter(Boolean);
    const defaultIds = urlIds.length > 0 ? urlIds : ['1', '2', '3', '4', '5'];
    setIdsInput(defaultIds.join(','));
    fetchComparison(defaultIds);
  }, []);

  const handleCompare = () => {
    const ids = idsInput.split(',').map(s => s.trim()).filter(Boolean);
    if (ids.length < 2) {
      customToast({ type: 'error', title: 'Input Error', message: 'Please enter at least 2 application IDs.' });
      return;
    }
    if (ids.length > 5) {
      customToast({ type: 'error', title: 'Input Error', message: 'Please enter at most 5 application IDs.' });
      return;
    }
    fetchComparison(ids);
  };

  const getWinner = (row: string): 'A' | 'B' | 'tie' => {
    if (!candidateA || !candidateB) return 'tie';
    switch (row) {
      case 'Overall Score': return candidateA.score > candidateB.score ? 'A' : candidateB.score > candidateA.score ? 'B' : 'tie';
      case 'Skills': return (candidateA.skills?.length ?? 0) > (candidateB.skills?.length ?? 0) ? 'A' : (candidateB.skills?.length ?? 0) > (candidateA.skills?.length ?? 0) ? 'B' : 'tie';
      case 'Experience': return candidateA.exp > candidateB.exp ? 'A' : candidateB.exp > candidateA.exp ? 'B' : 'tie';
      case 'Culture Fit': return candidateA.cultureFit > candidateB.cultureFit ? 'A' : candidateB.cultureFit > candidateA.cultureFit ? 'B' : 'tie';
      default: return 'tie';
    }
  };

  const renderCell = (row: string) => {
    if (!candidateA || !candidateB) return null;
    const winner = getWinner(row);
    switch (row) {
      case 'Overall Score':
        return (
          <>
            <td className={cn('p-4 text-center', winner === 'A' && 'bg-emerald-50/80 dark:bg-emerald-500/5')}>
              <div className="flex flex-col items-center gap-2">
                <span className="text-2xl font-black text-gray-900 dark:text-white">{candidateA.score}</span>
                <Progress value={candidateA.score} size="sm" color={candidateA.score >= 90 ? 'green' : candidateA.score >= 80 ? 'default' : 'amber'} className="w-24" />
              </div>
            </td>
            <td className={cn('p-4 text-center', winner === 'B' && 'bg-emerald-50/80 dark:bg-emerald-500/5')}>
              <div className="flex flex-col items-center gap-2">
                <span className="text-2xl font-black text-gray-900 dark:text-white">{candidateB.score}</span>
                <Progress value={candidateB.score} size="sm" color={candidateB.score >= 90 ? 'green' : candidateB.score >= 80 ? 'default' : 'amber'} className="w-24" />
              </div>
            </td>
          </>
        );
      case 'Skills':
        return (
          <>
            <td className={cn('p-4', winner === 'A' && 'bg-emerald-50/80 dark:bg-emerald-500/5')}>
              <div className="flex flex-wrap gap-1 justify-center">{(candidateA.skills || []).map(s => <Badge key={s} variant={(candidateB.skills || []).includes(s) ? 'default' : 'primary'} size="sm">{s} {(candidateB.skills || []).includes(s) ? <CheckCircle2 className="h-3 w-3 ml-1 text-emerald-500" /> : <ArrowRight className="h-3 w-3 ml-1 text-purple-500" />}</Badge>)}</div>
            </td>
            <td className={cn('p-4', winner === 'B' && 'bg-emerald-50/80 dark:bg-emerald-500/5')}>
              <div className="flex flex-wrap gap-1 justify-center">{(candidateB.skills || []).map(s => <Badge key={s} variant={(candidateA.skills || []).includes(s) ? 'default' : 'primary'} size="sm">{s} {(candidateA.skills || []).includes(s) ? <CheckCircle2 className="h-3 w-3 ml-1 text-emerald-500" /> : <ArrowRight className="h-3 w-3 ml-1 text-purple-500" />}</Badge>)}</div>
            </td>
          </>
        );
      case 'Experience':
        return (
          <>
            <td className={cn('p-4 text-center', winner === 'A' && 'bg-emerald-50/80 dark:bg-emerald-500/5')}>
              <span className="text-lg font-black text-gray-900 dark:text-white">{candidateA.exp} {t('recruiter.compare.years')}</span>
            </td>
            <td className={cn('p-4 text-center', winner === 'B' && 'bg-emerald-50/80 dark:bg-emerald-500/5')}>
              <span className="text-lg font-black text-gray-900 dark:text-white">{candidateB.exp} {t('recruiter.compare.years')}</span>
            </td>
          </>
        );
      case 'Education':
        return (
          <>
            <td className={cn('p-4 text-center', winner === 'A' && 'bg-emerald-50/80 dark:bg-emerald-500/5')}>
              <span className="text-sm font-bold text-gray-900 dark:text-white">{candidateA.edu}</span>
            </td>
            <td className={cn('p-4 text-center', winner === 'B' && 'bg-emerald-50/80 dark:bg-emerald-500/5')}>
              <span className="text-sm font-bold text-gray-900 dark:text-white">{candidateB.edu}</span>
            </td>
          </>
        );
      case 'Strengths':
        return (
          <>
            <td className="p-4">
              <div className="flex flex-col gap-1 items-center">{(candidateA.strengths || []).map(s => <Badge key={s} variant="success" size="sm" dot>{s}</Badge>)}</div>
            </td>
            <td className="p-4">
              <div className="flex flex-col gap-1 items-center">{(candidateB.strengths || []).map(s => <Badge key={s} variant="success" size="sm" dot>{s}</Badge>)}</div>
            </td>
          </>
        );
      case 'Weaknesses':
        return (
          <>
            <td className="p-4">
              <div className="flex flex-col gap-1 items-center">{(candidateA.weaknesses || []).map(s => <Badge key={s} variant="warning" size="sm">{s}</Badge>)}</div>
            </td>
            <td className="p-4">
              <div className="flex flex-col gap-1 items-center">{(candidateB.weaknesses || []).map(s => <Badge key={s} variant="warning" size="sm">{s}</Badge>)}</div>
            </td>
          </>
        );
      case 'Culture Fit':
        return (
          <>
            <td className={cn('p-4 text-center', winner === 'A' && 'bg-emerald-50/80 dark:bg-emerald-500/5')}>
              <div className="flex flex-col items-center gap-1">
                <span className="text-lg font-black text-gray-900 dark:text-white">{candidateA.cultureFit}%</span>
                <Progress value={candidateA.cultureFit} size="sm" color={candidateA.cultureFit >= 90 ? 'green' : candidateA.cultureFit >= 80 ? 'default' : 'amber'} className="w-24" />
              </div>
            </td>
            <td className={cn('p-4 text-center', winner === 'B' && 'bg-emerald-50/80 dark:bg-emerald-500/5')}>
              <div className="flex flex-col items-center gap-1">
                <span className="text-lg font-black text-gray-900 dark:text-white">{candidateB.cultureFit}%</span>
                <Progress value={candidateB.cultureFit} size="sm" color={candidateB.cultureFit >= 90 ? 'green' : candidateB.cultureFit >= 80 ? 'default' : 'amber'} className="w-24" />
              </div>
            </td>
          </>
        );
      default:
        return <td className="p-4 text-center">—</td>;
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">{t('recruiter.compare.title')}</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{t('recruiter.compare.subtitle')}</p>
        </div>
      </div>

      <Card className="glass-panel border-purple-200/50">
        <CardContent className="p-4">
          <div className="flex items-end gap-3">
            <div className="flex-1">
              <label className="block text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1.5">{t('recruiter.compare.applicationIds')}</label>
              <input
                type="text"
                value={idsInput}
                onChange={e => setIdsInput(e.target.value)}
                placeholder={t('recruiter.compare.idsPlaceholder')}
                className="w-full px-3 py-2 rounded-xl border border-purple-200/60 dark:border-white/10 bg-white dark:bg-gray-900 text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500/40"
              />
            </div>
            <Button variant="primary" onClick={handleCompare} disabled={loading}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <TrendingUp className="h-4 w-4" />}
              <span className="ml-1.5">{loading ? t('recruiter.compare.loading') : t('recruiter.compare.compare')}</span>
            </Button>
          </div>
          {error && (
            <p className="mt-2 text-sm text-red-600 dark:text-red-400">{error}</p>
          )}
        </CardContent>
      </Card>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="h-10 w-10 animate-spin text-purple-500" />
            <p className="text-sm text-gray-500 dark:text-gray-400">{t('recruiter.compare.loadingData')}</p>
          </div>
        </div>
      ) : !candidateA || !candidateB ? (
        <Card className="glass-panel border-purple-200/50">
          <CardContent className="p-12 text-center">
            <Users className="h-12 w-12 mx-auto text-gray-300 dark:text-gray-600 mb-3" />
            <p className="text-gray-500 dark:text-gray-400">{t('recruiter.compare.enterIdsToCompare')}</p>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {(['A', 'B'] as const).map(side => {
              const cand = side === 'A' ? candidateA : candidateB;
              const setCand = side === 'A' ? setCandidateA : setCandidateB;
              return (
                <Card key={side} className="glass-panel border-purple-200/50">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-sm font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{side === 'A' ? t('recruiter.compare.candidateA') : t('recruiter.compare.candidateB')}</h3>
                      <div className="relative">
                        <Button variant="outline" size="sm" onClick={() => setDropdownFor(dropdownFor === side ? null : side)} className="font-medium text-xs">
                          {cand.name} <Users className="h-3 w-3 ml-1" />
                        </Button>
                        {dropdownFor === side && (
                          <div className="absolute right-0 mt-2 w-52 rounded-xl border border-purple-100 dark:border-white/10 bg-white dark:bg-gray-900 shadow-xl z-50 overflow-hidden">
                            {candidates.filter(c => c.id !== (side === 'A' ? candidateB.id : candidateA.id)).map(c => (
                              <button key={c.id} className={cn('w-full px-4 py-2 text-left text-sm hover:bg-purple-50 dark:hover:bg-purple-500/10 transition-colors', cand.id === c.id && 'bg-purple-50 dark:bg-purple-500/10 font-bold')} onClick={() => { setCand(c); setDropdownFor(null); }}>
                                {c.name} <span className="text-xs text-gray-400">({c.score}%)</span>
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center justify-center h-20 rounded-xl bg-gradient-to-br from-purple-50 to-indigo-50 dark:from-purple-950/20 dark:to-indigo-950/20 border border-purple-100 dark:border-white/10">
                      <div className="text-center">
                        <span className="text-3xl font-black text-gray-900 dark:text-white">{cand.score}</span>
                        <span className="text-xs font-bold text-gray-500 dark:text-gray-400 block">{t('recruiter.compare.overallScore')}</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>

          <Card className="glass-panel border-purple-200/50 overflow-hidden">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-purple-500" />
                {t('recruiter.compare.comparisonBreakdown')}
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-purple-100 dark:border-white/10 text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    <th className="px-4 py-3 text-left w-32">{t('recruiter.compare.criteria')}</th>
                    <th className={cn('px-4 py-3 text-center', candidateA.score > candidateB.score && 'text-emerald-600 dark:text-emerald-400')}>
                      <div className="flex items-center justify-center gap-1">{candidateA.name} {candidateA.score > candidateB.score && <Star className="h-3 w-3 fill-current" />}</div>
                    </th>
                    <th className={cn('px-4 py-3 text-center', candidateB.score > candidateA.score && 'text-emerald-600 dark:text-emerald-400')}>
                      <div className="flex items-center justify-center gap-1">{candidateB.name} {candidateB.score > candidateA.score && <Star className="h-3 w-3 fill-current" />}</div>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {comparisonRows.map((row, i) => {
                    const rowKey = row.charAt(0).toLowerCase() + row.slice(1).replace(' ', '');
                    return (
                      <motion.tr key={row} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.05 }} className={cn('border-b border-purple-50 dark:border-white/5 hover:bg-purple-50/30 dark:hover:bg-white/[0.02] transition-colors', getWinner(row) !== 'tie' && 'bg-gradient-to-r from-transparent via-emerald-50/30 to-transparent dark:via-emerald-500/5')}>
                        <td className="p-4 font-extrabold text-sm text-gray-900 dark:text-white">{t(`recruiter.compare.row.${rowKey}`)}</td>
                        {renderCell(row)}
                      </motion.tr>
                    );
                  })}
                </tbody>
              </table>
            </CardContent>
          </Card>

          <Card className="glass-panel border-purple-200/50">
            <CardHeader>
              <CardTitle>{t('recruiter.compare.summary')}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="p-4 rounded-xl bg-purple-50/80 dark:bg-purple-950/20 border border-purple-200/60 dark:border-purple-500/20">
                <p className="text-sm text-gray-700 dark:text-gray-300">
                  <strong className="text-purple-800 dark:text-purple-300">{t('recruiter.compare.aiVerdict')}</strong>{' '}
                  {candidateA.score > candidateB.score
                    ? t('recruiter.compare.verdictA').replace('{candA}', candidateA.name).replace('{scoreA}', candidateA.score.toString()).replace('{candB}', candidateB.name).replace('{scoreB}', candidateB.score.toString())
                    : candidateB.score > candidateA.score
                      ? t('recruiter.compare.verdictB').replace('{candB}', candidateB.name).replace('{scoreB}', candidateB.score.toString()).replace('{candA}', candidateA.name).replace('{scoreA}', candidateA.score.toString())
                      : t('recruiter.compare.verdictTie').replace('{candA}', candidateA.name).replace('{candB}', candidateB.name).replace('{scoreA}', candidateA.score.toString())}
                </p>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
