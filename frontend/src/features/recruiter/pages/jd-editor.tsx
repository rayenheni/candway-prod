import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { customToast } from '@/shared/components/ui/toast';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/shared/components/ui/tabs';
import { useLanguage } from '@/contexts/language-context';
import { FileText, Sparkles, AlertTriangle, RefreshCw, CheckCircle2, Copy, Download, Wand2 } from 'lucide-react';
import { jdBiasService } from '@/services/jd-bias.service';

const categoryColorMap: Record<string, string> = {
  'Gender-coded': 'bg-rose-500',
  'Age-coded': 'bg-amber-500',
  'Cultural': 'bg-blue-500',
};

const rewriteStyles = ['inclusive', 'neutral', 'professional'] as const;

function extractTitle(text: string): string {
  const lines = text.trim().split('\n');
  return lines[0] || 'Job Description';
}

interface BiasedPhrase {
  phrase: string;
  category: string;
  suggestion: string;
}

interface AnalysisResult {
  biasScore: number;
  biasedPhrases: BiasedPhrase[];
  suggestions: string[];
}

interface WordListCategory {
  category: string;
  words: string[];
}

export default function JDEditorPage() {
  const { t } = useLanguage();
  const [jdText, setJdText] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzed, setAnalyzed] = useState(false);
  const [rewriting, setRewriting] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [rewriteStyle, setRewriteStyle] = useState<string>('inclusive');
  const [wordLists, setWordLists] = useState<WordListCategory[]>([]);

  useEffect(() => {
    (async () => {
      try {
        const data = await jdBiasService.getWordLists();
        const lists: WordListCategory[] = Array.isArray(data)
          ? data as unknown as WordListCategory[]
          : data?.categories
            ? data.categories.map((c: any) => ({
                category: c.name || c.category || '',
                words: c.words || c.items?.map((i: any) => i.phrase || i.word) || [],
              }))
            : [];
        setWordLists(lists);
      } catch (e) {
        console.warn('Failed to load word lists:', e);
      }
    })();
  }, []);

  const handleAnalyze = async () => {
    if (!jdText.trim()) {
      customToast({ type: 'warning', title: t('common.status'), message: 'Enter a job description first.' });
      return;
    }
    setAnalyzing(true);
    setAnalyzed(false);
    setAnalysisResult(null);
    try {
      const result = await jdBiasService.analyzeJd({
        title: extractTitle(jdText),
        description: jdText,
        skills: [],
      });
      const biasedPhrases: BiasedPhrase[] = (result.categories || []).flatMap((c: any) =>
        (c.items || []).map((i: any) => ({
          phrase: i.phrase,
          category: i.category || c.name || '',
          suggestion: i.suggestion || '',
        }))
      );
      const suggestions: string[] = result.recommendations || [];
      setAnalysisResult({ biasScore: result.score, biasedPhrases, suggestions });
      setAnalyzed(true);
      customToast({ type: 'success', title: t('common.status'), message: `${result.score}% bias score detected.` });
    } catch (err: any) {
      customToast({ type: 'error', title: t('common.status'), message: err?.response?.data?.message || err?.message || 'Failed to analyze JD.' });
    } finally {
      setAnalyzing(false);
    }
  };

  const handleRewrite = async () => {
    if (!jdText.trim()) return;
    setRewriting(true);
    try {
      const result = await jdBiasService.rewriteJd({
        title: extractTitle(jdText),
        description: jdText,
        style: rewriteStyle,
      });
      setJdText(result.rewritten_description);
      customToast({ type: 'success', title: t('common.status'), message: 'JD rewritten.' });
    } catch (err: any) {
      customToast({ type: 'error', title: t('common.status'), message: err?.response?.data?.message || err?.message || 'Failed to rewrite JD.' });
    } finally {
      setRewriting(false);
    }
  };

  const handleReset = () => {
    setJdText('');
    setAnalyzed(false);
    setAnalysisResult(null);
  };

  const handleCopyAnalysis = () => {
    if (!analysisResult) return;
    navigator.clipboard.writeText(analysisResult.suggestions.join('\n'));
    customToast({ type: 'success', title: t('common.status'), message: 'Copied to clipboard.' });
  };

  const handleExport = () => {
    customToast({ type: 'info', title: t('common.status'), message: 'Exporting report...' });
  };

  const score = analysisResult?.biasScore ?? 0;
  const scoreContainerClass = score > 60
    ? 'bg-rose-100 dark:bg-rose-900/30'
    : score > 30
      ? 'bg-amber-100 dark:bg-amber-900/30'
      : 'bg-emerald-100 dark:bg-emerald-900/30';
  const scoreTextClass = score > 60
    ? 'text-rose-600 dark:text-rose-400'
    : score > 30
      ? 'text-amber-600 dark:text-amber-400'
      : 'text-emerald-600 dark:text-emerald-400';
  const ScoreIcon = score > 60 ? AlertTriangle : CheckCircle2;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Sparkles className="h-5 w-5 text-purple-600" />
            <span className="text-xs font-extrabold uppercase tracking-wider text-purple-600">AI</span>
          </div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">{t('jobs.jdEditor')}</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{t('jobs.subtitle')}</p>
        </div>
        <div className="flex items-center gap-2">
          {analyzed && (
            <>
              <Button variant="outline" size="sm" leftIcon={<Copy className="h-4 w-4" />} onClick={handleCopyAnalysis}>Copy</Button>
              <Button variant="outline" size="sm" leftIcon={<Download className="h-4 w-4" />} onClick={handleExport}>PDF</Button>
              <div className="flex items-center gap-1">
                <select
                  value={rewriteStyle}
                  onChange={(e) => setRewriteStyle(e.target.value)}
                  className="text-xs rounded-lg border border-purple-200/60 dark:border-white/10 bg-white/70 dark:bg-white/5 text-gray-700 dark:text-gray-300 px-2 py-1.5 focus:ring-2 focus:ring-purple-500/20 outline-none"
                >
                  {rewriteStyles.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
                <Button
                  variant="outline"
                  size="sm"
                  leftIcon={rewriting ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Wand2 className="h-4 w-4" />}
                  onClick={handleRewrite}
                  disabled={rewriting}
                >
                  {rewriting ? '...' : 'Rewrite'}
                </Button>
              </div>
              <Button variant="outline" size="sm" leftIcon={<RefreshCw className="h-4 w-4" />} onClick={handleReset}>{t('common.refresh')}</Button>
            </>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.3 }}>
          <Card className="glass-panel border-purple-200/60 dark:border-purple-500/20 h-full flex flex-col">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg font-extrabold text-gray-900 dark:text-white">
                <FileText className="h-5 w-5 text-purple-600" />
                {t('jobs.title')}
              </CardTitle>
              <CardDescription>{t('common.description')}</CardDescription>
            </CardHeader>
            <CardContent className="flex-1 flex flex-col gap-4">
              <textarea
                value={jdText}
                onChange={(e) => { setJdText(e.target.value); setAnalyzed(false); setAnalysisResult(null); }}
                placeholder={t('common.description')}
                className="flex-1 w-full min-h-[300px] rounded-xl border border-purple-200/60 dark:border-white/10 bg-white/70 dark:bg-white/5 p-4 text-sm focus:ring-2 focus:ring-purple-500/20 dark:text-white resize-none placeholder:text-gray-400"
              />
              <div className="flex items-center gap-3">
                <Button
                  variant="primary"
                  leftIcon={analyzing ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                  onClick={handleAnalyze}
                  disabled={analyzing}
                  className="flex-1 font-bold shadow-lg shadow-purple-500/25"
                >
                  {analyzing ? '...' : t('nav.analytics')}
                </Button>
                <Badge variant="default" size="sm" className="shrink-0">
                  {jdText.split(/\s+/).filter(Boolean).length} words
                </Badge>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.3, delay: 0.1 }}>
          <Card className="glass-panel border-purple-200/60 dark:border-purple-500/20 h-full flex flex-col">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg font-extrabold text-gray-900 dark:text-white">
                <AlertTriangle className={`h-5 w-5 ${analyzed ? 'text-rose-500' : 'text-gray-400'}`} />
                {t('nav.analytics')}
              </CardTitle>
              <CardDescription>
                {analyzed ? `${analysisResult?.biasedPhrases.length ?? 0} phrases` : t('common.noData')}
              </CardDescription>
            </CardHeader>
            <CardContent className="flex-1 flex flex-col">
              {!analyzed ? (
                <div className="flex-1 flex items-center justify-center">
                  <div className="text-center">
                    <FileText className="h-12 w-12 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
                    <p className="text-sm font-semibold text-gray-400">{t('common.noData')}</p>
                  </div>
                </div>
              ) : (
                <div className="flex-1 flex flex-col gap-4">
                  <div className="flex items-center justify-between p-4 rounded-xl bg-white/60 dark:bg-white/5 border border-purple-100 dark:border-white/10">
                    <div>
                      <p className="text-sm font-bold text-gray-500 dark:text-gray-400">{t('analytics.biasScore')}</p>
                      <div className="flex items-baseline gap-1">
                        <span className={`text-3xl font-black ${scoreTextClass}`}>{score}</span>
                        <span className="text-sm text-gray-400">/100</span>
                      </div>
                    </div>
                    <div className={`h-16 w-16 rounded-full flex items-center justify-center ${scoreContainerClass}`}>
                      <ScoreIcon className={`h-8 w-8 ${scoreTextClass}`} />
                    </div>
                  </div>

                  <div className="flex-1">
                    <Tabs defaultValue="phrases">
                      <TabsList className="w-full">
                        <TabsTrigger value="phrases" className="flex-1">Phrases</TabsTrigger>
                        <TabsTrigger value="suggestions" className="flex-1">Suggestions</TabsTrigger>
                        <TabsTrigger value="wordlists" className="flex-1">Lists</TabsTrigger>
                      </TabsList>

                      <TabsContent value="phrases" className="mt-3 space-y-2 max-h-[300px] overflow-y-auto">
                        {analysisResult?.biasedPhrases.map((item, i) => (
                          <motion.div
                            key={i}
                            initial={{ opacity: 0, y: 5 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: i * 0.03 }}
                            className="flex items-center justify-between p-3 rounded-xl bg-white/60 dark:bg-white/5 border border-purple-100 dark:border-white/10"
                          >
                            <div>
                              <span className="inline-flex items-center gap-1.5">
                                <span className="font-mono text-sm font-bold text-rose-600 dark:text-rose-400 line-through">{item.phrase}</span>
                                {item.suggestion && (
                                  <>
                                    <span className="text-gray-400 text-xs">→</span>
                                    <span className="font-mono text-sm font-bold text-emerald-600 dark:text-emerald-400">{item.suggestion}</span>
                                  </>
                                )}
                              </span>
                              <Badge variant="default" size="sm" className="ml-2">{item.category}</Badge>
                            </div>
                          </motion.div>
                        ))}
                      </TabsContent>

                      <TabsContent value="suggestions" className="mt-3 space-y-3 max-h-[300px] overflow-y-auto">
                        {analysisResult?.suggestions.map((s, i) => (
                          <motion.div
                            key={i}
                            initial={{ opacity: 0, y: 5 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: i * 0.05 }}
                            className="flex items-start gap-3 p-3 rounded-xl bg-white/60 dark:bg-white/5 border border-purple-100 dark:border-white/10"
                          >
                            <Sparkles className="h-4 w-4 text-purple-500 mt-0.5 shrink-0" />
                            <p className="text-sm font-semibold text-gray-700 dark:text-gray-300">{s}</p>
                          </motion.div>
                        ))}
                      </TabsContent>

                      <TabsContent value="wordlists" className="mt-3 space-y-4 max-h-[300px] overflow-y-auto">
                        {wordLists.length === 0 ? (
                          <div className="text-center py-8">
                            <p className="text-sm text-gray-400">{t('common.noData')}</p>
                          </div>
                        ) : (
                          wordLists.map((group) => (
                            <div key={group.category}>
                              <div className="flex items-center gap-2 mb-2">
                                <div className={`h-2 w-2 rounded-full ${categoryColorMap[group.category] || 'bg-gray-400'}`} />
                                <span className="text-xs font-extrabold uppercase tracking-wider text-gray-500 dark:text-gray-400">{group.category}</span>
                                <Badge variant="default" size="sm">{group.words.length} words</Badge>
                              </div>
                              <div className="flex flex-wrap gap-1.5">
                                {group.words.map((w) => (
                                  <Badge key={w} variant="default" size="sm" className="opacity-75">{w}</Badge>
                                ))}
                              </div>
                            </div>
                          ))
                        )}
                      </TabsContent>
                    </Tabs>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
