// ============================================================
// CVEvaluation - recruiter-facing CV scoring breakdown
//
// Explains WHY a CV scored as it did. Three states driven by
// cv_rubric_weighted:
//   true  -> rubric-weighted deterministic score (per-skill evidence)
//   false -> generic CV analysis (rubric attached, scoring fell back)
//   null  -> no rubric attached (pure AI semantic analysis)
// ============================================================

import { FileText, Sparkles, AlertTriangle, Scale, Crosshair } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import { cn } from '@/utils/cn';

export interface CVEvalSkill {
  name: string;
  score: number;
  weight?: number | null;
  normalized_weight?: number | null;
  level?: string | null;
  feedback?: string | null;
  category?: string | null;
}

export interface CVEvalEvidence {
  skill_name: string;
  score?: number | null;
  weight?: number | null;
  feedback?: string | null;
}

export interface CVEvaluationProps {
  cvScore?: number | null;
  cvRubricWeighted?: boolean | null;
  cvScoringMethod?: string | null;
  cvCoveragePct?: number | null;
  cvSkillBreakdown?: CVEvalSkill[];
  cvEvidence?: CVEvalEvidence[];
  cvMissingSkills?: string[];
  compact?: boolean;
}

function scoreColor(score: number) {
  if (score >= 80) return 'text-emerald-600 dark:text-emerald-400';
  if (score >= 65) return 'text-blue-600 dark:text-blue-400';
  if (score >= 25) return 'text-amber-500';
  return 'text-gray-400';
}

function scoreBarColor(score: number) {
  if (score >= 80) return 'bg-emerald-500';
  if (score >= 65) return 'bg-blue-500';
  if (score >= 25) return 'bg-amber-500';
  return 'bg-gray-300 dark:bg-gray-600';
}

function evidenceLabel(score?: number | null) {
  if (score == null) return '—';
  if (score >= 80) return 'Strong';
  if (score >= 60) return 'Demonstrated';
  if (score >= 40) return 'Direct';
  if (score >= 20) return 'Weak';
  return 'No evidence';
}

export function CVEvaluation({
  cvScore,
  cvRubricWeighted,
  cvScoringMethod,
  cvCoveragePct,
  cvSkillBreakdown = [],
  cvEvidence = [],
  cvMissingSkills = [],
  compact = false,
}: CVEvaluationProps) {
  const skills = cvSkillBreakdown || [];
  const evidence = cvEvidence || [];
  const missing = cvMissingSkills || [];

  const hasAnyBreakdown = skills.length > 0 || evidence.length > 0;
  const hasScore = cvScore != null;

  const badge =
    cvRubricWeighted === true ? (
      <Badge variant="success" size="sm" dot>
        Rubric Weighted
      </Badge>
    ) : cvRubricWeighted === false ? (
      <Badge variant="warning" size="sm" dot>
        Generic CV Analysis
      </Badge>
    ) : (
      <Badge variant="outline" size="sm" dot>
        No Rubric Attached
      </Badge>
    );

  // Evidence keyed by skill, with feedback preferred from the evidence
  // rows then falling back to the per-skill breakdown.
  const evidenceBySkill = new Map<string, CVEvalEvidence[]>();
  (evidence.length ? evidence : skills).forEach((ev) => {
    const name = (ev as CVEvalEvidence).skill_name ?? (ev as CVEvalSkill).name;
    if (!name) return;
    const list = evidenceBySkill.get(name) || [];
    list.push(ev as CVEvalEvidence);
    evidenceBySkill.set(name, list);
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-violet-100 dark:bg-violet-500/15 flex items-center justify-center text-violet-600 dark:text-violet-400 shrink-0">
            <FileText className="h-5 w-5" />
          </div>
          <div>
            <div className="text-sm font-bold text-gray-900 dark:text-white flex items-center gap-2">
              CV Score
              {badge}
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">
              {cvRubricWeighted === true
                ? 'Deterministic rubric-weighted score — each skill scored against evidence in the CV.'
                : cvRubricWeighted === false
                  ? 'Rubric attached but scoring fell back to generic keyword analysis.'
                  : 'No evaluation rubric was linked — score is a generic AI CV analysis.'}
            </div>
          </div>
        </div>

        <div className="ml-auto flex items-center gap-3 shrink-0">
          <div className="rounded-2xl bg-violet-50/70 dark:bg-violet-500/10 border border-violet-100 dark:border-violet-500/20 px-5 py-3 text-center">
            <div className="text-[11px] font-bold uppercase tracking-wider text-violet-500 mb-0.5">CV Score</div>
            <div className={cn('text-2xl font-extrabold', hasScore ? 'text-violet-600 dark:text-violet-400' : 'text-gray-400')}>
              {hasScore ? cvScore : '—'}
            </div>
          </div>
          {cvCoveragePct != null && (
            <div className="rounded-2xl bg-emerald-50/70 dark:bg-emerald-500/10 border border-emerald-100 dark:border-emerald-500/20 px-5 py-3 text-center">
              <div className="text-[11px] font-bold uppercase tracking-wider text-emerald-500 mb-0.5">Coverage</div>
              <div className="text-2xl font-extrabold text-emerald-600 dark:text-emerald-400">{cvCoveragePct}%</div>
            </div>
          )}
          {cvScoringMethod && (
            <div className="rounded-2xl bg-sky-50/70 dark:bg-sky-500/10 border border-sky-100 dark:border-sky-500/20 px-5 py-3 text-center">
              <div className="text-[11px] font-bold uppercase tracking-wider text-sky-500 mb-0.5">Method</div>
              <div className="text-sm font-bold text-sky-600 dark:text-sky-400 capitalize">
                {cvScoringMethod.replace(/_/g, ' ')}
              </div>
            </div>
          )}
        </div>
      </div>

      {!hasScore && !hasAnyBreakdown ? (
        <div className="flex flex-col items-center justify-center py-10 text-center">
          <FileText className="h-10 w-10 text-gray-300 dark:text-gray-600 mb-3" />
          <p className="text-base font-medium text-gray-500 dark:text-gray-400">No CV evaluation available</p>
          <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">This candidate has not had their CV scored yet.</p>
        </div>
      ) : !hasAnyBreakdown ? (
        <div className="flex flex-col items-center justify-center py-10 text-center">
          <Scale className="h-10 w-10 text-gray-300 dark:text-gray-600 mb-3" />
          <p className="text-base font-medium text-gray-500 dark:text-gray-400">No CV evidence found</p>
          <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">The CV was scored but no per-skill evidence is available.</p>
        </div>
      ) : (
        <>
          <div>
            <h4 className="text-base font-extrabold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
              <Crosshair className="h-4 w-4 text-violet-500" /> Skill Scores &amp; Evidence
            </h4>
            <div className="space-y-3">
              {skills.map((s) => {
                const evRows = evidenceBySkill.get(s.name) || [];
                return (
                  <div key={s.name} className="rounded-2xl border border-gray-100 dark:border-white/[0.06] p-5">
                    <div className="flex items-center justify-between gap-4 mb-3">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="text-sm font-bold text-gray-900 dark:text-white truncate">{s.name}</span>
                        {s.category && (
                          <span className="px-2 py-0.5 rounded-md bg-gray-50 dark:bg-white/[0.04] text-[10px] font-semibold text-gray-500">
                            {s.category}
                          </span>
                        )}
                        {s.level && (
                          <span className="px-2 py-0.5 rounded-md bg-amber-50 dark:bg-amber-500/10 text-[10px] font-bold text-amber-600 dark:text-amber-400 capitalize">
                            {s.level}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        {s.normalized_weight != null && (
                          <span className="text-xs font-semibold text-gray-400">
                            {Math.round(s.normalized_weight * 100)}% wt
                          </span>
                        )}
                        <div className="h-2 w-28 rounded-full bg-gray-100 dark:bg-white/10 overflow-hidden">
                          <div className={cn('h-full rounded-full', scoreBarColor(s.score))} style={{ width: `${s.score}%` }} />
                        </div>
                        <span className={cn('text-lg font-extrabold', scoreColor(s.score))}>{Math.round(s.score)}</span>
                      </div>
                    </div>

                    {evRows.length > 0 && (
                      <div className="space-y-2">
                        {evRows.map((ev, i) => (
                          <div key={i} className="p-3.5 rounded-xl bg-violet-50/60 dark:bg-violet-500/5 border border-violet-100 dark:border-violet-500/15 text-sm text-violet-800 dark:text-violet-200 leading-relaxed">
                            <div className="flex items-center gap-1.5 font-bold mb-1">
                              <Sparkles className="h-3.5 w-3.5 text-violet-500" />
                              {evidenceLabel(ev.score ?? s.score)}
                            </div>
                            {ev.feedback || s.feedback}
                          </div>
                        ))}
                      </div>
                    )}

                    {!compact && s.feedback && evRows.length === 0 && (
                      <div className="p-3.5 rounded-xl bg-violet-50/60 dark:bg-violet-500/5 border border-violet-100 dark:border-violet-500/15 text-sm text-violet-800 dark:text-violet-200 leading-relaxed">
                        <div className="flex items-center gap-1.5 font-bold mb-1">
                          <Sparkles className="h-3.5 w-3.5 text-violet-500" /> {evidenceLabel(s.score)}
                        </div>
                        {s.feedback}
                      </div>
                    )}
                  </div>
                );
              })}

              {skills.length === 0 && evidence.length > 0 && (
                <p className="text-sm text-gray-400 dark:text-gray-500 italic">
                  {evidence.length} evidence row{evidence.length === 1 ? '' : 's'} recorded for this CV.
                </p>
              )}
            </div>
          </div>

          {missing.length > 0 && (
            <div>
              <h4 className="text-base font-extrabold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-red-500" /> Missing Skills
              </h4>
              <div className="flex flex-wrap gap-2">
                {missing.map((m) => (
                  <span key={m} className="px-3 py-1 rounded-full bg-red-50 dark:bg-red-500/10 text-xs font-semibold text-red-600 dark:text-red-400 border border-red-100 dark:border-red-500/20">
                    {m}
                  </span>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
