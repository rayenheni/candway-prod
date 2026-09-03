import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Progress } from '@/shared/components/ui/progress';
import { customToast } from '@/shared/components/ui/toast';
import { useLanguage } from '@/contexts/language-context';
import { Sparkles, Star, RefreshCw, Loader2, AlertCircle, Inbox } from 'lucide-react';
import { candidatesService } from '@/services/candidates.service';

interface Criterion {
  name: string;
  score: number;
  weight: number;
  note: string;
}

export default function ScoringPreviewPage() {
  const { t } = useLanguage();
  const [searchParams] = useSearchParams();
  const appId = searchParams.get('id') || '';

  const [criteria, setCriteria] = useState<Criterion[]>([]);
  const [overallScore, setOverallScore] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchScore = async (id: string) => {
    try {
      setLoading(true);
      setError(null);
      const res = await candidatesService.getAIScore(id);
      const data = res ?? {};
      setOverallScore(data.score ?? 0);
      const parsed = parseAnalysis(data.analysis);
      setCriteria(parsed.length > 0 ? parsed : [{ name: 'Overall AI Score', score: data.score ?? 0, weight: 100, note: 'Aggregated evaluation score.' }]);
    } catch (err: any) {
      setError(err?.message || 'Failed to load AI score');
      setCriteria([]);
      setOverallScore(0);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (appId) fetchScore(appId);
  }, [appId]);

  const handleRefresh = () => {
    if (!appId) return;
    fetchScore(appId);
    customToast({ type: 'info', title: t('common.status'), message: 'Candidate has been re-evaluated with latest rubrics.' });
  };

  if (!appId) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">{t('recruiter.scoringPreview.title')}</h1>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{t('recruiter.scoringPreview.subtitle')}</p>
          </div>
        </div>
        <Card className="glass-panel border-purple-200/50">
          <CardContent>
            <div className="flex flex-col items-center justify-center py-16 text-gray-500">
              <Inbox className="h-12 w-12 mb-4 text-purple-300" />
              <p className="text-lg font-semibold text-gray-700 dark:text-gray-300">{t('recruiter.scoringPreview.noApp')}</p>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{t('recruiter.scoringPreview.noAppDesc')}</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (loading && criteria.length === 0) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">{t('recruiter.scoringPreview.title')}</h1>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{t('recruiter.scoringPreview.subtitle')}</p>
          </div>
        </div>
        <Card className="glass-panel border-purple-200/50">
          <CardContent>
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-8 w-8 text-violet-500 animate-spin" />
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error && criteria.length === 0) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">{t('recruiter.scoringPreview.title')}</h1>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{t('recruiter.scoringPreview.subtitle')}</p>
          </div>
        </div>
        <Card className="glass-panel border-purple-200/50">
          <CardContent>
            <div className="flex flex-col items-center justify-center py-16 text-gray-500">
              <AlertCircle className="h-12 w-12 mb-4 text-red-400" />
              <p className="text-lg font-semibold text-gray-700 dark:text-gray-300">{t('common.status')}</p>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{error}</p>
              <Button variant="outline" className="mt-4" onClick={() => fetchScore(appId)} leftIcon={<RefreshCw className="h-4 w-4" />}>{t('common.retry')}</Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">{t('recruiter.scoringPreview.title')}</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{t('recruiter.scoringPreview.subtitle')}</p>
        </div>
        <Button variant="outline" onClick={handleRefresh} leftIcon={<RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />}>{loading ? '...' : t('recruiter.scoringPreview.rescore')}</Button>
      </div>

      <Card className="glass-panel border-purple-200/50">
        <CardHeader>
          <div className="flex items-center justify-between w-full">
            <div>
              <CardTitle>{t('recruiter.scoringPreview.scorecard')}</CardTitle>
              <CardDescription>{t('recruiter.scoringPreview.scorecardDesc')}</CardDescription>
            </div>
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-tr from-purple-600 to-violet-600 text-white shadow-lg">
              <div className="text-center">
                <div className="text-xl font-black leading-none">{Math.round(overallScore)}</div>
                <div className="text-[10px] font-bold opacity-80">/ 100</div>
              </div>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-5">
            {criteria.map(c => (
              <div key={c.name} className="p-4 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10">
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <span className="text-sm font-extrabold text-gray-900 dark:text-white">{c.name}</span>
                    <span className="text-xs text-gray-500 ml-2">{t('recruiter.scoringPreview.weight')}: {c.weight}%</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={c.score >= 90 ? 'success' : c.score >= 80 ? 'primary' : 'warning'} size="sm">{c.score}%</Badge>
                    <Star className="h-4 w-4 text-amber-400 fill-current" />
                  </div>
                </div>
                <Progress value={c.score} size="md" color={c.score >= 90 ? 'green' : c.score >= 80 ? 'purple' : 'blue'} />
                <p className="text-xs text-gray-500 mt-2 italic flex items-center gap-1">
                  <Sparkles className="h-3 w-3 text-amber-500" />
                  {c.note}
                </p>
              </div>
            ))}
          </div>
          <div className="mt-6 p-4 rounded-xl bg-purple-50/80 dark:bg-purple-950/20 border border-purple-200/60 dark:border-purple-500/20">
            <h3 className="text-sm font-extrabold text-purple-800 dark:text-purple-300 flex items-center gap-1.5">
              <Sparkles className="h-4 w-4 text-amber-500" /> {t('recruiter.scoringPreview.aiRecommendation')}
            </h3>
            <p className="text-sm text-gray-700 dark:text-gray-300 mt-1 leading-relaxed">
              &ldquo;This candidate scores {Math.round(overallScore)}/100 overall based on the rubric evaluation.&rdquo;
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function parseAnalysis(analysis: string): Criterion[] {
  if (!analysis) return [];
  try {
    const parsed = JSON.parse(analysis);
    if (Array.isArray(parsed)) {
      return parsed.map((item: any, i: number) => ({
        name: item.category || item.name || item.criterion || item.criteria || `Criterion ${i + 1}`,
        score: typeof item.score === 'number' ? item.score : 0,
        weight: typeof item.weight === 'number' ? item.weight : 0,
        note: item.evidence || item.note || item.notes || item.comment || item.description || '',
      }));
    }
    if (typeof parsed === 'object' && parsed !== null) {
      if (parsed.categories && Array.isArray(parsed.categories)) {
        return parsed.categories.map((item: any, i: number) => ({
          name: item.category || item.name || item.criterion || `Category ${i + 1}`,
          score: typeof item.score === 'number' ? item.score : 0,
          weight: typeof item.weight === 'number' ? item.weight : 0,
          note: item.evidence || item.note || item.notes || item.comment || '',
        }));
      }
    }
  } catch (e) {
    console.warn('Failed to parse scoring analysis:', e);
  }
  return [];
}
