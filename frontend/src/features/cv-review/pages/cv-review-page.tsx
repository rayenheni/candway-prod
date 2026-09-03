// ============================================================
// Enriched CV Review Page - Candway Platform
// ============================================================

import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router';
import { motion, AnimatePresence } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { customToast } from '@/shared/components/ui/toast';
import { cn } from '@/utils/cn';
import { useLanguage } from '@/contexts/language-context';
import {
  cvReviewService,
  type CVReviewResult,
  type CandidateUsage,
} from '@/services/cv-review.service';
import { candidateService } from '@/services/candidate.service';
import {
  Upload,
  CheckCircle2,
  Zap,
  Loader2,
  RefreshCw,
  FileText,
  Sparkles,
  BookOpen,
  GitBranch,
  Crown,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';

export default function CVReviewPage() {
  const navigate = useNavigate();
  const { t } = useLanguage();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [review, setReview] = useState<CVReviewResult | null>(null);
  const [usage, setUsage] = useState<CandidateUsage | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [declaredRole, setDeclaredRole] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [showSpelling, setShowSpelling] = useState(false);
  const [activeTab, setActiveTab] = useState<'all' | 'rubric' | 'tree' | 'feedback'>('all');

  const loadData = async (force = false) => {
    setLoading(true);
    try {
      const [reviewRes, usageRes, profileRes] = await Promise.all([
        cvReviewService.getCvReviewEnriched(force).catch(() => null),
        cvReviewService.getCandidateUsage().catch(() => null),
        candidateService.getProfile().catch(() => null),
      ]);
      if (reviewRes) {
        setReview(reviewRes);
        if (reviewRes.declared_role) setDeclaredRole(reviewRes.declared_role);
      }
      if (usageRes) setUsage(usageRes);
      if (!declaredRole && profileRes?.headline) setDeclaredRole(profileRes.headline);
    } catch {
      // Fallback
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleUploadAndAnalyze = async () => {
    if (!selectedFile) {
      customToast({ type: 'error', title: t('cv.review.noFile'), message: t('cv.review.noFileMsg') });
      return;
    }

    setUploading(true);
    try {
      await cvReviewService.uploadCv(selectedFile, declaredRole);
      customToast({ type: 'success', title: t('cv.review.uploaded'), message: t('cv.review.uploadedMsg') });
      setSelectedFile(null);
      setAnalyzing(true);
      await loadData(true);
    } catch (err: any) {
      customToast({
        type: 'error',
        title: t('cv.review.uploadFailed'),
        message: err?.response?.data?.detail || t('cv.review.uploadFailedMsg'),
      });
    } finally {
      setUploading(false);
      setAnalyzing(false);
    }
  };

  const handleReanalyze = async () => {
    setAnalyzing(true);
    try {
      await loadData(true);
      customToast({ type: 'success', title: t('cv.review.refreshed'), message: t('cv.review.refreshedMsg') });
    } catch {
      customToast({ type: 'error', title: t('cv.review.error'), message: t('cv.review.refreshFailedMsg') });
    } finally {
      setAnalyzing(false);
    }
  };

  if (loading || analyzing) {
    return (
      <div className="flex flex-col items-center justify-center py-24 space-y-4">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400">
          <Loader2 className="h-8 w-8 animate-spin" />
        </div>
        <div className="text-center">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            {analyzing ? t('cv.review.analyzing') : t('cv.review.loadingPlatform')}
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {t('cv.review.analyzingDesc')}
          </p>
        </div>
      </div>
    );
  }

  const rubricScores = review?.rubric_dimension_scores || [];
  const treeCoverage = review?.skill_tree_coverage;
  const gapAnalysis = review?.gap_analysis || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">{t('cv.review.title')}</h1>
            <Badge variant="primary" size="sm"><Sparkles className="h-3 w-3 mr-1" />{t('cv.review.enrichedAi')}</Badge>
          </div>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            {t('cv.review.subtitle')}
          </p>
        </div>

        <div className="flex items-center gap-2">
          {review && (
            <Button
              variant="outline"
              size="sm"
              leftIcon={<RefreshCw className="h-4 w-4" />}
              onClick={handleReanalyze}
              disabled={analyzing}
            >
              {t('cv.review.reanalyze')}
            </Button>
          )}
          <Button
            variant="primary"
            size="sm"
            leftIcon={<Upload className="h-4 w-4" />}
            onClick={() => fileInputRef.current?.click()}
          >
            {t('cv.review.uploadNewCv')}
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.doc,.txt"
            className="hidden"
            onChange={handleFileSelect}
          />
        </div>
      </div>

      {/* Subscription Usage Banner */}
      {usage && (
        <Card className="glass-panel border-purple-200/50 dark:border-purple-500/20 bg-gradient-to-r from-purple-500/5 via-indigo-500/5 to-transparent">
          <CardContent className="p-4 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 shrink-0">
                <Crown className="h-5 w-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-gray-900 dark:text-white">{t('cv.review.planQuota')}: {usage.tier.toUpperCase()}</span>
                  <Badge variant={usage.cv_uploads_used >= usage.cv_uploads_limit && usage.cv_uploads_limit !== -1 ? 'danger' : 'success'} size="sm">
                    {usage.cv_uploads_used} / {usage.cv_uploads_limit === -1 ? '∞' : usage.cv_uploads_limit} {t('cv.review.used')}
                  </Badge>
                </div>
                <div className="w-48 bg-gray-200 dark:bg-gray-700 h-1.5 rounded-full mt-1.5 overflow-hidden">
                  <div
                    className="bg-purple-600 h-full rounded-full transition-all"
                    style={{
                      width: usage.cv_uploads_limit === -1 ? '10%' : `${Math.min(100, (usage.cv_uploads_used / usage.cv_uploads_limit) * 100)}%`,
                    }}
                  />
                </div>
              </div>
            </div>
            <Button variant="ghost" size="sm" className="text-purple-600 dark:text-purple-400 font-semibold" onClick={() => navigate('/settings')}>
              {t('cv.review.manageSubscription')} →
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Upload Box Modal or Selected File Indicator */}
      {selectedFile && (
        <Card className="border-purple-300 dark:border-purple-500/30 bg-purple-50/50 dark:bg-purple-950/10">
          <CardContent className="p-4 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <FileText className="h-8 w-8 text-purple-600 shrink-0" />
              <div>
                <p className="text-sm font-semibold text-gray-900 dark:text-white">{selectedFile.name}</p>
                <p className="text-xs text-gray-500">{(selectedFile.size / 1024 / 1024).toFixed(2)} MB</p>
              </div>
            </div>
            <div className="flex items-center gap-2 w-full sm:w-auto">
              <Input
                placeholder={t('cv.review.targetRole')}
                value={declaredRole}
                onChange={(e) => setDeclaredRole(e.target.value)}
                className="max-w-xs text-xs"
              />
              <Button variant="primary" size="sm" onClick={handleUploadAndAnalyze} disabled={uploading}>
                {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : t('cv.review.analyzeFile')}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {!review && !selectedFile && (
        <Card className="border-dashed border-2 border-purple-200 dark:border-purple-500/20 p-12 text-center">
          <CardContent className="flex flex-col items-center justify-center space-y-4">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-purple-50 dark:bg-purple-900/20 text-purple-600">
              <Upload className="h-8 w-8" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-gray-900 dark:text-white">{t('cv.review.noCvYet')}</h3>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                {t('cv.review.emptyDesc')}
              </p>
            </div>
            <Button variant="primary" onClick={() => fileInputRef.current?.click()} leftIcon={<Upload className="h-4 w-4" />}>
              {t('cv.review.selectCvFile')}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Main 3-Panel Enriched View */}
      {review && (
        <div className="space-y-6">
          {/* Top Grade Banner */}
          <Card className="glass-panel overflow-hidden border-purple-200/50 dark:border-purple-500/20">
            <CardContent className="p-6">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
                <div className="flex items-center gap-5">
                  <div className={cn(
                    'flex h-20 w-20 shrink-0 items-center justify-center rounded-2xl text-3xl font-black text-white shadow-lg',
                    review.overall_grade === 'A' ? 'bg-gradient-to-br from-emerald-500 to-teal-600 shadow-emerald-500/25' :
                    review.overall_grade === 'B' ? 'bg-gradient-to-br from-blue-500 to-indigo-600 shadow-blue-500/25' :
                    review.overall_grade === 'C' ? 'bg-gradient-to-br from-amber-500 to-orange-600 shadow-amber-500/25' :
                    'bg-gradient-to-br from-rose-500 to-red-600 shadow-rose-500/25'
                  )}>
                    {review.overall_grade}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" size="sm">{declaredRole}</Badge>
                      <span className="text-xs text-gray-400">{t('cv.review.cvLength')}: {review.cv_length || 0} {t('cv.review.chars')}</span>
                    </div>
                    <h2 className="text-xl font-bold text-gray-900 dark:text-white mt-1">
                      {review.grade_explanation}
                    </h2>
                    <p className="text-sm text-gray-600 dark:text-gray-400 mt-1 line-clamp-2">
                      {review.summary}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2 self-start md:self-center">
                  {(['all', 'rubric', 'tree', 'feedback'] as const).map((tab) => (
                    <Button
                      key={tab}
                      variant={activeTab === tab ? 'primary' : 'ghost'}
                      size="sm"
                      className="capitalize text-xs font-semibold"
                      onClick={() => setActiveTab(tab)}
                    >
                      {t(`cv.review.tab.${tab}`)}
                    </Button>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* 3 Columns Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Column 1: AI Feedback & Suggestions */}
            {(activeTab === 'all' || activeTab === 'feedback') && (
              <Card className="space-y-4">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Zap className="h-4 w-4 text-purple-600" />
                    {t('cv.review.aiNarrative')}
                  </CardTitle>
                  <CardDescription>{t('cv.review.aiNarrativeDesc')}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* Strengths */}
                  {review.strengths && review.strengths.length > 0 && (
                    <div>
                      <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">{t('ivan.strengths')}</h4>
                      <div className="space-y-1.5">
                        {review.strengths.map((s, i) => (
                          <div key={i} className="flex items-start gap-2 text-xs text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/20 p-2 rounded-lg">
                            <CheckCircle2 className="h-3.5 w-3.5 mt-0.5 shrink-0" />
                            <span>{s}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Suggestions */}
                  {review.improvement_suggestions && review.improvement_suggestions.length > 0 && (
                    <div>
                      <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">{t('cv.review.improvementSuggestions')}</h4>
                      <div className="space-y-2">
                        {review.improvement_suggestions.map((item, i) => (
                          <div key={i} className="p-3 rounded-xl border border-gray-100 dark:border-white/[0.06] bg-gray-50/50 dark:bg-white/[0.02]">
                            <div className="flex items-center justify-between">
                              <span className="text-xs font-bold text-gray-900 dark:text-white">{item.title}</span>
                              <Badge variant={item.priority === 'high' ? 'danger' : 'warning'} size="sm">
                                {item.priority}
                              </Badge>
                            </div>
                            <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">{item.description}</p>
                            {item.example_after && (
                              <div className="mt-2 text-[11px] bg-emerald-50 dark:bg-emerald-950/30 p-2 rounded border border-emerald-200/50 text-emerald-800 dark:text-emerald-300 font-mono">
                                <strong>{t('cv.review.try')}:</strong> "{item.example_after}"
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Spelling / Grammar Accordion */}
                  {((review.spelling_errors && review.spelling_errors.length > 0) || (review.grammar_issues && review.grammar_issues.length > 0)) && (
                    <div className="border-t pt-4">
                      <button
                        onClick={() => setShowSpelling(!showSpelling)}
                        className="flex items-center justify-between w-full text-xs font-bold text-gray-700 dark:text-gray-300"
                      >
                        <span>{t('cv.review.languageGrammar')} ({ (review.spelling_errors?.length || 0) + (review.grammar_issues?.length || 0) } {t('cv.review.issues')})</span>
                        {showSpelling ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                      </button>

                      <AnimatePresence>
                        {showSpelling && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            className="space-y-2 mt-2"
                          >
                            {review.spelling_errors?.map((err, i) => (
                              <div key={i} className="text-xs p-2 rounded bg-red-50 dark:bg-red-950/20 text-red-700 dark:text-red-300">
                                <span className="line-through">{err.original}</span> → <strong>{err.corrected}</strong>
                              </div>
                            ))}
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  )}

                  {/* Keyword Suggestions */}
                  {review.keyword_suggestions && review.keyword_suggestions.length > 0 && (
                    <div>
                      <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">{t('cv.review.recommendedKeywords')}</h4>
                      <div className="flex flex-wrap gap-1.5">
                        {review.keyword_suggestions.map((kw, i) => (
                          <span key={i} className="px-2 py-1 rounded-md bg-purple-50 dark:bg-purple-950/30 text-purple-700 dark:text-purple-300 text-xs border border-purple-200/50">
                            + {kw.keyword}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {/* Column 2: Rubric-Mapped Scorecard */}
            {(activeTab === 'all' || activeTab === 'rubric') && (
              <Card className="space-y-4">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <BookOpen className="h-4 w-4 text-blue-600" />
                    {t('cv.review.rubricScorecard')}
                  </CardTitle>
                  <CardDescription>{t('cv.review.rubricScorecardDesc')}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {rubricScores.length === 0 ? (
                    <div className="text-center py-8 text-xs text-gray-500">
                      <p>{t('cv.review.noRubricMatch')} "{declaredRole}".</p>
                      <p className="mt-1">{t('cv.review.baselineDistribution')}</p>
                    </div>
                  ) : (
                    rubricScores.map((dim, i) => (
                      <div key={i} className="space-y-1.5 p-3 rounded-xl border border-gray-100 dark:border-white/[0.06]">
                        <div className="flex items-center justify-between text-xs font-bold">
                          <span className="text-gray-900 dark:text-white">{dim.category}</span>
                          <Badge variant="primary" size="sm">{dim.level || t('cv.review.intermediate')}</Badge>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="flex-1 bg-gray-100 dark:bg-gray-800 h-2 rounded-full overflow-hidden">
                            <div
                              className="bg-blue-600 h-full rounded-full transition-all"
                              style={{ width: `${Math.min(100, dim.score || 70)}%` }}
                            />
                          </div>
                          <span className="text-xs font-mono font-bold text-blue-600 dark:text-blue-400">{dim.score}%</span>
                        </div>
                        {dim.evidence && (
                          <p className="text-[11px] text-gray-500 dark:text-gray-400 italic">
                            "{dim.evidence}"
                          </p>
                        )}
                      </div>
                    ))
                  )}
                </CardContent>
              </Card>
            )}

            {/* Column 3: Skill Tree & Progression Gaps */}
            {(activeTab === 'all' || activeTab === 'tree') && (
              <Card className="space-y-4">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <GitBranch className="h-4 w-4 text-emerald-600" />
                    {t('cv.review.skillTreeProgression')}
                  </CardTitle>
                  <CardDescription>{t('cv.review.skillTreeProgressionDesc')}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* Tree Covered / Missing Nodes */}
                  {treeCoverage && (
                    <div className="space-y-3">
                      <div className="text-xs font-bold text-gray-700 dark:text-gray-300">
                        {t('cv.review.skillTreeLabel')}: <span className="text-purple-600 font-semibold">{treeCoverage.tree_name || declaredRole}</span>
                      </div>

                      <div className="space-y-2">
                        <div className="text-[11px] font-bold text-emerald-600 uppercase">{t('cv.review.coveredSkills')} ({treeCoverage.covered?.length || 0})</div>
                        <div className="flex flex-wrap gap-1">
                          {treeCoverage.covered?.map((s, i) => (
                            <Badge key={i} variant="success" size="sm" className="text-[10px]">
                              ✓ {s}
                            </Badge>
                          ))}
                        </div>
                      </div>

                      <div className="space-y-2">
                        <div className="text-[11px] font-bold text-amber-600 uppercase">{t('cv.review.missingSkills')} ({treeCoverage.missing?.length || 0})</div>
                        <div className="flex flex-wrap gap-1">
                          {treeCoverage.missing?.map((s, i) => (
                            <Badge key={i} variant="warning" size="sm" className="text-[10px]">
                              ✗ {s}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Priority Gap Analysis */}
                  {gapAnalysis.length > 0 && (
                    <div className="border-t pt-4">
                      <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">{t('cv.review.priorityRoadmap')}</h4>
                      <div className="space-y-2">
                        {gapAnalysis.map((gap, i) => (
                          <div key={i} className="p-3 rounded-xl bg-amber-50/50 dark:bg-amber-950/20 border border-amber-200/50 text-xs">
                            <div className="flex items-center justify-between font-bold text-amber-900 dark:text-amber-300">
                              <span>{gap.skill}</span>
                              <Badge variant={gap.priority === 'Critical' ? 'danger' : 'warning'} size="sm">
                                {gap.priority}
                              </Badge>
                            </div>
                            <p className="text-gray-600 dark:text-gray-400 text-[11px] mt-1">{gap.recommendation}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
