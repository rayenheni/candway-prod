import { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate, useSearchParams, Link } from 'react-router';
import { motion, AnimatePresence } from 'framer-motion';
import { Card } from '@/shared/components/ui/card';
import { customToast } from '@/shared/components/ui/toast';
import { cn } from '@/utils/cn';
import {
  ArrowLeft,
  Share2,
  ChevronRight,
  Shield,
  CheckCircle2,
  Star,
  ArrowRight,
  MessageSquare,
  Sparkles,
  Award,
  AlertTriangle,
  Loader2,
  ArrowRightCircle,
  Calculator,
  X,
  FileText,
  Save,
  Eye,
} from 'lucide-react';
import { candidatesService } from '@/services/candidates.service';
import { CVEvaluation } from '@/shared/components/cv-evaluation';
import { useLanguage } from '@/contexts/language-context';

// ─── Types ────────────────────────────────────────────────────────────────────

type SecondaryTab = 'evidence' | 'cv' | 'integrity';
type SkillFilter = 'all' | 'interview' | 'cv' | 'missing';

interface SkillBreakdownItem {
  name: string;
  score: number;
  is_required: boolean;
  assessed: boolean;
  category?: string;
  explanation?: string;
  evidence?: string[];
  weight?: number | null;
  normalized_weight?: number | null;
  level?: string | null;
  evidence_quality?: string | null;
}

interface EvidenceItem {
  skill_name: string;
  turn_number: number;
  question: string;
  answer: string;
  explanation: string;
  final_score: number;
  overridden: boolean;
  weight?: number | null;
  evidence_quality?: string;
}

interface QuestionItem {
  id: number;
  title: string;
  category: string;
  duration: string;
  score: number;
  label: string;
  answer: string;
  justification?: string;
  evidence_quality?: string;
  target_skill?: string;
}

interface CVEvalSkillItem {
  name: string;
  score: number;
  weight?: number | null;
  normalized_weight?: number | null;
  level?: string | null;
  feedback?: string | null;
  category?: string | null;
}

interface CVEvalEvidenceItem {
  skill_name: string;
  score?: number | null;
  weight?: number | null;
  feedback?: string | null;
}

interface AIScoresResponse {
  overall_score?: number;
  cv_score?: number | null;
  rubric_score?: number | null;
  rubric_coverage_pct?: number | null;
  rubric_version?: number | null;
  rubric_available?: boolean;
  is_rubric_driven?: boolean;
  scoring_model?: string;
  status?: string;
  recommendation?: { label: string; status: string };
  trust?: { score: number; coverage: number; quality: number; count: number };
  skill_breakdown?: SkillBreakdownItem[];
  evidence?: EvidenceItem[];
  questions?: QuestionItem[];
  gaps?: string[];
  strengths?: string[];
  category_breakdown?: { name: string; score: number }[];
  cv_rubric_weighted?: boolean | null;
  cv_scoring_method?: string | null;
  cv_coverage_pct?: number | null;
  cv_skill_breakdown?: CVEvalSkillItem[];
  cv_evidence?: CVEvalEvidenceItem[];
  cv_missing_skills?: string[];
  fraud_risk_score?: number | null;
  integrity_score?: number | null;
  ai_confidence?: number | null;
  proctoring_summary?: {
    face_detection?: string;
    browser_switches?: string;
    plagiarism?: string;
  };
  penalty_breakdown?: {
    trust_score?: number;
    proctoring_violations_count?: number;
  };
  needs_review?: boolean;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function scoreColor(score: number) {
  if (score >= 80) return 'text-emerald-600 dark:text-emerald-400';
  if (score >= 65) return 'text-blue-600 dark:text-blue-400';
  if (score >= 40) return 'text-amber-500';
  return 'text-red-500';
}

function scoreBarColor(score: number) {
  if (score >= 80) return 'bg-emerald-500';
  if (score >= 65) return 'bg-blue-500';
  if (score >= 40) return 'bg-amber-400';
  return 'bg-red-400';
}

function weightAsDecimal(w?: number | null): number {
  if (w == null) return 0;
  return w > 1 ? w / 100 : w;
}

function fmtWeight(w?: number | null): string | null {
  if (w == null) return null;
  const pct = w > 1 ? w : w * 100;
  return `${Math.round(pct)}%`;
}

function EvidenceQualityPill({
  quality,
  size = 'sm',
}: {
  quality?: string | null;
  size?: 'xs' | 'sm';
}) {
  const q = (quality || '').toLowerCase();
  const base = size === 'xs'
    ? 'text-[10px] px-2 py-0.5 rounded'
    : 'text-xs px-2.5 py-0.5 rounded-md';
  const cls = cn('inline-flex items-center gap-1 font-bold border', base);

  if (q === 'strong' || q === 'high') {
    return (
      <span className={cn(cls, 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-500/20')}>
        <CheckCircle2 className="h-3 w-3 shrink-0" /> STRONG
      </span>
    );
  }
  if (q === 'medium' || q === 'moderate' || q === 'demonstrated') {
    return (
      <span className={cn(cls, 'bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-200 dark:border-blue-500/20')}>
        <Sparkles className="h-3 w-3 shrink-0" /> MODERATE
      </span>
    );
  }
  if (q === 'weak' || q === 'direct') {
    return (
      <span className={cn(cls, 'bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-200 dark:border-amber-500/20')}>
        <AlertTriangle className="h-3 w-3 shrink-0" /> WEAK
      </span>
    );
  }
  if (q) {
    return (
      <span className={cn(cls, 'bg-gray-50 dark:bg-white/5 text-gray-500 dark:text-gray-400 border-gray-200 dark:border-white/10')}>
        NO EVIDENCE
      </span>
    );
  }
  return null;
}

function SourceTypePill({ type }: { type: 'both' | 'interview' | 'cv' | 'missing' }) {
  const base = 'inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold border';
  if (type === 'both')
    return <span className={cn(base, 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-500/20')}>CV + INTERVIEW</span>;
  if (type === 'interview')
    return <span className={cn(base, 'bg-violet-50 dark:bg-violet-500/10 text-violet-700 dark:text-violet-400 border-violet-200 dark:border-violet-500/20')}>INTERVIEW VALIDATED</span>;
  if (type === 'cv')
    return <span className={cn(base, 'bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-200 dark:border-blue-500/20')}>CV DETECTED</span>;
  return <span className={cn(base, 'bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400 border-red-200 dark:border-red-500/20')}>MISSING</span>;
}

function RecommendationBadge({
  label,
  large = false,
}: {
  label?: string;
  large?: boolean;
}) {
  if (!label) return null;
  const l = label.toLowerCase();
  const cls = large
    ? 'px-4 py-2 text-sm font-extrabold rounded-xl'
    : 'px-3 py-1 text-xs font-bold rounded-lg';
  const base = cn('inline-flex items-center border', cls);
  if (l.includes('strong hire'))
    return <span className={cn(base, 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-500/30')}>{label}</span>;
  if (l.includes('hire'))
    return <span className={cn(base, 'bg-blue-100 dark:bg-blue-500/20 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-500/30')}>{label}</span>;
  if (l.includes('consider') || l.includes('review'))
    return <span className={cn(base, 'bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-500/30')}>{label}</span>;
  return <span className={cn(base, 'bg-red-100 dark:bg-red-500/20 text-red-700 dark:text-red-300 border-red-200 dark:border-red-500/30')}>{label}</span>;
}

// ─── Talent Radar Graph ───────────────────────────────────────────────────────

function TalentRadarGraph({ skills }: { skills: DrawerSkill[] }) {
  // Show active skills (up to 10 skills for comprehensive radar)
  const visibleSkills = useMemo(() => {
    const active = skills.filter((s) => s.source_type !== 'missing' || s.score > 0);
    const list = active.length >= 3 ? active : skills;
    return list.slice(0, 10);
  }, [skills]);

  const n = visibleSkills.length;
  if (n < 3) return null;

  // Expanded dimensions for enhanced size ("taille")
  const cx = 260;
  const cy = 220;
  const maxR = 145; // larger radar radius
  const rings = [25, 50, 75, 100];
  const labelOffset = 36; // generous offset for clean label placement

  const angle = (i: number) => (2 * Math.PI * i) / n - Math.PI / 2;

  const polarPoint = (r: number, i: number) => ({
    x: cx + r * Math.cos(angle(i)),
    y: cy + r * Math.sin(angle(i)),
  });

  const candidatePoints = visibleSkills
    .map((s, i) => polarPoint((s.score / 100) * maxR, i))
    .map((p) => `${p.x},${p.y}`)
    .join(' ');

  const fullPoints = visibleSkills
    .map((_, i) => polarPoint(maxR, i))
    .map((p) => `${p.x},${p.y}`)
    .join(' ');

  const textAnchor = (i: number) => {
    const a = angle(i);
    const cos = Math.cos(a);
    if (cos > 0.15) return 'start';
    if (cos < -0.15) return 'end';
    return 'middle';
  };

  const dotColor = (s: DrawerSkill) => {
    if (s.source_type === 'both' || s.source_type === 'interview') return '#10b981'; // emerald-500
    if (s.source_type === 'cv') return '#6366f1'; // indigo-500
    return '#f59e0b'; // amber-500
  };

  // Helper to split long skill names into 2 lines for clean SVG rendering without truncating
  const formatLabelLines = (name: string) => {
    if (name.length <= 18) return [name];
    const words = name.split(' ');
    if (words.length === 1) return [name.slice(0, 18) + '…'];
    const mid = Math.ceil(words.length / 2);
    return [words.slice(0, mid).join(' '), words.slice(mid).join(' ')];
  };

  return (
    <Card className="p-6 border border-violet-100/70 dark:border-white/[0.06] shadow-sm shadow-violet-500/5 bg-white dark:bg-white/[0.03] rounded-3xl overflow-hidden">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 pb-4 border-b border-gray-100 dark:border-white/5">
        <div>
          <h2 className="text-lg font-extrabold text-gray-900 dark:text-white flex items-center gap-2">
            <Award className="h-5 w-5 text-violet-600 dark:text-violet-400" />
            Talent Graph
          </h2>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
            Visual skill radar ground truth based on EvaluationConfigSnapshot
          </p>
        </div>
        {/* Platform Legend */}
        <div className="flex items-center gap-4 text-xs font-bold shrink-0 flex-wrap">
          <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-violet-50 dark:bg-violet-500/10 text-violet-700 dark:text-violet-300 border border-violet-200/60 dark:border-violet-500/20">
            <span className="h-2.5 w-2.5 rounded-full bg-violet-600 dark:bg-violet-400" />
            Candidate Profile
          </span>
          <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-gray-50 dark:bg-white/5 text-gray-600 dark:text-gray-400 border border-gray-200/60 dark:border-white/10">
            <span className="h-2.5 w-2.5 rounded-full bg-gray-300 dark:bg-white/30" />
            100% Target
          </span>
        </div>
      </div>

      <div className="flex flex-col lg:flex-row gap-8 items-center justify-between">
        {/* Enhanced SVG Radar Canvas */}
        <div className="flex-1 w-full max-w-[540px] flex justify-center items-center py-2">
          <svg
            viewBox="0 0 520 440"
            className="w-full h-auto max-h-[440px] overflow-visible select-none"
          >
            <defs>
              <linearGradient id="radarFill" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#8b5cf6" stopOpacity="0.35" />
                <stop offset="100%" stopColor="#6366f1" stopOpacity="0.12" />
              </linearGradient>
              <filter id="violetGlow" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feComposite in="SourceGraphic" in2="blur" operator="over" />
              </filter>
            </defs>

            {/* Concentric grid rings */}
            {rings.map((pct) => {
              const r = (pct / 100) * maxR;
              const pts = visibleSkills
                .map((_, i) => polarPoint(r, i))
                .map((p) => `${p.x},${p.y}`)
                .join(' ');
              return (
                <polygon
                  key={pct}
                  points={pts}
                  fill="none"
                  stroke="rgba(139, 92, 246, 0.12)"
                  strokeWidth={pct === 100 ? 1.5 : 1}
                  strokeDasharray={pct === 100 ? undefined : '4 4'}
                />
              );
            })}

            {/* Scale numbers (25 / 50 / 75 / 100) */}
            {rings.map((pct) => {
              const r = (pct / 100) * maxR;
              const p = polarPoint(r, 0);
              return (
                <text
                  key={`rl-${pct}`}
                  x={p.x + 5}
                  y={p.y - 3}
                  fontSize={9}
                  fill="#a7f3d0"
                  fontWeight={700}
                  className="fill-violet-400/60 dark:fill-violet-300/40"
                >
                  {pct}
                </text>
              );
            })}

            {/* Radial axis lines */}
            {visibleSkills.map((_, i) => {
              const outer = polarPoint(maxR, i);
              return (
                <line
                  key={`ax-${i}`}
                  x1={cx}
                  y1={cy}
                  x2={outer.x}
                  y2={outer.y}
                  stroke="rgba(139, 92, 246, 0.15)"
                  strokeWidth={1}
                />
              );
            })}

            {/* Full 100% target outer boundary */}
            <polygon
              points={fullPoints}
              fill="rgba(124,58,237,0.03)"
              stroke="rgba(124,58,237,0.20)"
              strokeWidth={1.5}
              strokeDasharray="4 4"
            />

            {/* Candidate evaluation polygon with violet gradient fill */}
            <polygon
              points={candidatePoints}
              fill="url(#radarFill)"
              stroke="#7c3aed"
              strokeWidth={2.5}
              strokeLinejoin="round"
              filter="url(#violetGlow)"
            />

            {/* Vertex points */}
            {visibleSkills.map((s, i) => {
              const p = polarPoint((s.score / 100) * maxR, i);
              return (
                <g key={`dot-grp-${i}`}>
                  <circle
                    cx={p.x}
                    cy={p.y}
                    r={5.5}
                    fill={dotColor(s)}
                    stroke="#ffffff"
                    strokeWidth={2}
                    className="shadow-md"
                  />
                </g>
              );
            })}

            {/* Multi-line formatted axis labels */}
            {visibleSkills.map((s, i) => {
              const lp = polarPoint(maxR + labelOffset, i);
              const ta = textAnchor(i);
              const lines = formatLabelLines(s.name);
              const isTop = Math.sin(angle(i)) < -0.5;

              return (
                <g key={`lbl-${i}`}>
                  {lines.map((lineText, lineIdx) => (
                    <text
                      key={lineIdx}
                      x={lp.x}
                      y={lp.y + (lineIdx - (lines.length - 1) / 2) * 12 - (isTop ? 6 : 0)}
                      textAnchor={ta}
                      fontSize={11}
                      fontWeight={700}
                      className="fill-gray-800 dark:fill-gray-100"
                    >
                      {lineText}
                    </text>
                  ))}
                  <text
                    x={lp.x}
                    y={lp.y + (lines.length / 2) * 12 + 6 - (isTop ? 6 : 0)}
                    textAnchor={ta}
                    fontSize={11}
                    fontWeight={800}
                    fill={
                      s.score >= 80
                        ? '#059669'
                        : s.score >= 65
                        ? '#2563eb'
                        : s.score >= 40
                        ? '#d97706'
                        : s.score === 0
                        ? '#ef4444'
                        : '#6b7280'
                    }
                  >
                    {s.score > 0 ? Math.round(s.score) : '—'}
                  </text>
                </g>
              );
            })}

            {/* Center origin pulse */}
            <circle cx={cx} cy={cy} r={3.5} fill="#7c3aed" />
          </svg>
        </div>

        {/* Legend sidebar showing detailed score breakdown */}
        <div className="w-full lg:w-64 shrink-0 space-y-2.5 p-4 rounded-2xl bg-gray-50/70 dark:bg-white/[0.02] border border-gray-100 dark:border-white/5">
          <div className="text-xs font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-2">
            Skill Performance Summary
          </div>
          {visibleSkills.map((s) => {
            const wt = weightAsDecimal(s.normalized_weight ?? s.weight);
            const weightLabel = fmtWeight(s.normalized_weight ?? s.weight);
            return (
              <div key={s.name} className="flex items-center gap-2 text-xs">
                <span
                  className="h-2.5 w-2.5 rounded-full shrink-0"
                  style={{ background: dotColor(s) }}
                />
                <span className="font-semibold text-gray-700 dark:text-gray-200 flex-1 truncate">
                  {s.name}
                </span>
                {weightLabel && (
                  <span className="text-[10px] font-medium text-gray-400 shrink-0">
                    {weightLabel}
                  </span>
                )}
                <div className="w-16 h-1.5 rounded-full bg-gray-200 dark:bg-white/10 overflow-hidden shrink-0">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${Math.min(s.score, 100)}%`,
                      background:
                        s.score >= 80
                          ? '#10b981'
                          : s.score >= 65
                          ? '#3b82f6'
                          : s.score >= 40
                          ? '#f59e0b'
                          : '#ef4444',
                    }}
                  />
                </div>
                <span
                  className={cn(
                    'font-extrabold w-6 text-right shrink-0',
                    s.score >= 80
                      ? 'text-emerald-600 dark:text-emerald-400'
                      : s.score >= 65
                      ? 'text-blue-600 dark:text-blue-400'
                      : s.score >= 40
                      ? 'text-amber-500'
                      : 'text-red-400',
                  )}
                >
                  {s.score > 0 ? Math.round(s.score) : '—'}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </Card>
  );
}

// ─── Skill Evidence Drawer ────────────────────────────────────────────────────

interface DrawerSkill extends SkillBreakdownItem {
  source_type: 'both' | 'interview' | 'cv' | 'missing';
}

function SkillDrawer({
  skill,
  evidenceList,
  onClose,
  onViewInQA,
}: {
  skill: DrawerSkill;
  evidenceList: EvidenceItem[];
  onClose: () => void;
  onViewInQA: (turn: number) => void;
}) {
  const skillEvidence = useMemo(
    () => evidenceList.filter((e) => e.skill_name.toLowerCase() === skill.name.toLowerCase()),
    [evidenceList, skill.name],
  );

  const wtDecimal = weightAsDecimal(skill.normalized_weight ?? skill.weight);
  const wtPercentLabel = fmtWeight(skill.normalized_weight ?? skill.weight) || 'Standard';
  const pointsContribution =
    skill.score > 0 && wtDecimal > 0
      ? (skill.score * wtDecimal).toFixed(1)
      : null;

  // Format explanation into checkmark key points
  const whyPoints = useMemo(() => {
    if (!skill.explanation) return [];
    // Split by periods or newlines to create checkmark bullets
    const sentences = skill.explanation
      .split(/(?<=\.)\s+|\n+/)
      .map((s) => s.trim())
      .filter((s) => s.length > 5);
    return sentences.length > 0 ? sentences : [skill.explanation];
  }, [skill.explanation]);

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div className="flex-1 bg-black/40 backdrop-blur-sm transition-opacity" onClick={onClose} />

      {/* Drawer panel */}
      <motion.div
        initial={{ x: '100%' }}
        animate={{ x: 0 }}
        exit={{ x: '100%' }}
        transition={{ type: 'spring', damping: 28, stiffness: 280 }}
        className="w-full max-w-[480px] bg-white dark:bg-gray-950 shadow-2xl overflow-y-auto flex flex-col border-l border-gray-100 dark:border-white/10"
      >
        {/* Drawer Sticky Header */}
        <div className="sticky top-0 z-10 bg-white/95 dark:bg-gray-950/95 backdrop-blur-md border-b border-gray-100 dark:border-white/10 px-6 py-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="text-xs font-extrabold uppercase tracking-widest text-violet-600 dark:text-violet-400">
              Skill Breakdown
            </span>
            {skill.is_required && (
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-200/60 dark:border-amber-500/20">
                Required
              </span>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-xl bg-gray-100 dark:bg-white/10 text-gray-500 hover:text-gray-900 dark:hover:text-white transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Drawer Body Content */}
        <div className="flex-1 p-6 space-y-6">

          {/* 1. Skill Title & Score */}
          <div className="space-y-1">
            <h2 className="text-xl font-black tracking-tight text-gray-900 dark:text-white uppercase">
              {skill.name}
            </h2>
            <div className="flex items-baseline gap-2">
              <span className={cn('text-4xl font-black leading-none', scoreColor(skill.score))}>
                {skill.score > 0 ? Math.round(skill.score) : '—'}
              </span>
              <span className="text-lg font-bold text-gray-400 dark:text-gray-500">/ 100</span>
            </div>
          </div>

          {/* 2. Metadata Key-Value List */}
          <div className="space-y-2.5 py-3 border-y border-gray-100 dark:border-white/10 text-sm">
            <div className="flex justify-between items-center">
              <span className="text-gray-500 dark:text-gray-400">Required weight</span>
              <span className="font-bold text-gray-900 dark:text-white">{wtPercentLabel}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-500 dark:text-gray-400">Expected level</span>
              <span className="font-bold text-gray-900 dark:text-white">
                {skill.is_required ? 'Advanced' : 'Proficient'}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-500 dark:text-gray-400">Evaluated level</span>
              <span className="font-bold text-emerald-600 dark:text-emerald-400 capitalize">
                {skill.level || (skill.score >= 80 ? 'Strong' : skill.score >= 60 ? 'Demonstrated' : 'Developing')}
              </span>
            </div>
          </div>

          {/* 3. WHY {SCORE}? */}
          <div className="space-y-3">
            <h3 className="text-xs font-extrabold uppercase tracking-widest text-violet-600 dark:text-violet-400">
              WHY {skill.score > 0 ? Math.round(skill.score) : 0}?
            </h3>
            {whyPoints.length > 0 ? (
              <div className="space-y-2">
                {whyPoints.map((pt, i) => (
                  <div key={i} className="flex items-start gap-2 text-sm text-gray-800 dark:text-gray-200">
                    <span className="text-emerald-500 font-extrabold shrink-0 mt-0.5">✓</span>
                    <span className="leading-relaxed">{pt}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-gray-400 italic">No specific justification text recorded.</p>
            )}
          </div>

          <hr className="border-gray-100 dark:border-white/10" />

          {/* 4. EVIDENCE */}
          <div className="space-y-4">
            <h3 className="text-xs font-extrabold uppercase tracking-widest text-violet-600 dark:text-violet-400">
              EVIDENCE
            </h3>

            {skillEvidence.length > 0 ? (
              <div className="space-y-5">
                {skillEvidence.map((ev) => (
                  <div key={ev.turn_number} className="space-y-3 p-4 rounded-2xl bg-gray-50/70 dark:bg-white/[0.02] border border-gray-100 dark:border-white/5">
                    {/* Q Header */}
                    <div className="text-sm font-bold text-gray-900 dark:text-white">
                      Q{ev.turn_number} — "{ev.question || 'Interview Question'}"
                    </div>

                    {/* Candidate answer */}
                    {ev.answer && (
                      <div className="space-y-1">
                        <div className="text-[11px] font-bold text-gray-400 uppercase tracking-wider">Candidate:</div>
                        <div className="text-xs text-gray-700 dark:text-gray-300 italic bg-white dark:bg-white/5 p-3 rounded-xl border border-gray-100 dark:border-white/5 leading-relaxed">
                          "{ev.answer}"
                        </div>
                      </div>
                    )}

                    {/* AI Assessment */}
                    {ev.explanation && (
                      <div className="space-y-1">
                        <div className="text-[11px] font-bold text-violet-600 dark:text-violet-400 uppercase tracking-wider">
                          AI assessment:
                        </div>
                        <div className="text-xs text-violet-900 dark:text-violet-200 bg-violet-50/60 dark:bg-violet-500/10 p-3 rounded-xl border border-violet-100 dark:border-violet-500/20 leading-relaxed">
                          {ev.explanation}
                        </div>
                      </div>
                    )}

                    {/* Evidence Quality */}
                    <div className="flex items-center justify-between pt-1">
                      <span className="text-xs font-bold text-gray-500 dark:text-gray-400">Evidence quality:</span>
                      <EvidenceQualityPill quality={ev.evidence_quality} size="xs" />
                    </div>

                    {/* View Question Button */}
                    <button
                      onClick={() => onViewInQA(ev.turn_number)}
                      className="w-full mt-2 py-2 rounded-xl bg-violet-600 hover:bg-violet-700 text-white text-xs font-bold transition-colors inline-flex items-center justify-center gap-1.5 shadow-sm shadow-violet-500/20"
                    >
                      <Eye className="h-3.5 w-3.5" />
                      View Question Q{ev.turn_number}
                    </button>
                  </div>
                ))}
              </div>
            ) : skill.evidence && skill.evidence.length > 0 ? (
              <div className="space-y-2">
                {skill.evidence.map((evText, i) => (
                  <div key={i} className="p-3 rounded-xl bg-gray-50 dark:bg-white/5 text-xs text-gray-700 dark:text-gray-300 italic border border-gray-100 dark:border-white/5">
                    "{evText}"
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-gray-400 italic">No direct verbatim evidence recorded for this skill.</p>
            )}
          </div>

          <hr className="border-gray-100 dark:border-white/10" />

          {/* 5. SCORE CONTRIBUTION */}
          <div className="space-y-2">
            <h3 className="text-xs font-extrabold uppercase tracking-widest text-violet-600 dark:text-violet-400">
              SCORE CONTRIBUTION
            </h3>
            {pointsContribution && wtDecimal > 0 ? (
              <div className="p-4 rounded-2xl bg-violet-50/70 dark:bg-violet-500/10 border border-violet-100 dark:border-violet-500/20 flex items-center justify-between">
                <span className="font-mono text-sm font-bold text-violet-900 dark:text-violet-200">
                  {Math.round(skill.score)} × {wtPercentLabel}
                </span>
                <span className="text-base font-black text-violet-700 dark:text-violet-300 font-mono">
                  = {pointsContribution} points
                </span>
              </div>
            ) : (
              <div className="text-xs text-gray-400 italic">Standard unweighted criterion</div>
            )}
          </div>

        </div>
      </motion.div>
    </div>
  );
}

// ─── Skill Row ────────────────────────────────────────────────────────────────

function SkillRow({
  skill,
  evidenceList,
  index,
  onInspect,
}: {
  skill: DrawerSkill;
  evidenceList: EvidenceItem[];
  index: number;
  onInspect: (s: DrawerSkill) => void;
}) {
  const isMissing = skill.source_type === 'missing';
  const isCvOnly = skill.source_type === 'cv';
  const wt = weightAsDecimal(skill.normalized_weight ?? skill.weight);
  const weightLabel = fmtWeight(skill.normalized_weight ?? skill.weight);
  const contribution =
    skill.score > 0 && wt > 0 ? (skill.score * wt).toFixed(1) : null;

  const sourceQs = useMemo(
    () =>
      evidenceList
        .filter((e) => e.skill_name.toLowerCase() === skill.name.toLowerCase())
        .map((e) => e.turn_number),
    [evidenceList, skill.name],
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.035 }}
      onClick={() => onInspect(skill)}
      className={cn(
        'group flex items-start gap-4 px-4 py-4 rounded-2xl border cursor-pointer transition-all',
        'hover:border-violet-200 dark:hover:border-violet-500/30 hover:bg-violet-50/20 dark:hover:bg-violet-500/5',
        isMissing
          ? 'border-l-4 border-l-red-400 border-red-100 dark:border-red-500/20 bg-red-50/20 dark:bg-red-500/5'
          : isCvOnly
          ? 'border-blue-100 dark:border-blue-500/15 bg-blue-50/10 dark:bg-blue-500/[0.03]'
          : 'border-gray-100 dark:border-white/[0.06] bg-white dark:bg-white/[0.02]',
      )}
    >
      {/* Left: all text content */}
      <div className="flex-1 min-w-0 space-y-2">
        {/* Name + badges */}
        <div className="flex items-center gap-2 flex-wrap">
          <span
            className={cn(
              'text-sm font-extrabold transition-colors',
              isMissing
                ? 'text-red-700 dark:text-red-400'
                : 'text-gray-900 dark:text-white group-hover:text-violet-700 dark:group-hover:text-violet-300',
            )}
          >
            {skill.name}
          </span>
          {skill.is_required && (
            <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-200 dark:border-amber-500/20">
              Required
            </span>
          )}
          <SourceTypePill type={skill.source_type} />
        </div>

        {/* Meta: weight · level · quality */}
        <div className="flex items-center gap-3 flex-wrap text-xs">
          {weightLabel && (
            <span className="text-gray-500 dark:text-gray-400">
              Weight:{' '}
              <span className="font-bold text-gray-700 dark:text-gray-200">{weightLabel}</span>
            </span>
          )}
          {skill.level && (
            <span className="text-gray-500 dark:text-gray-400">
              Level:{' '}
              <span className="font-bold text-gray-700 dark:text-gray-200 capitalize">
                {skill.level}
              </span>
            </span>
          )}
          <EvidenceQualityPill quality={skill.evidence_quality} size="xs" />
        </div>

        {/* Progress bar */}
        <div className="h-1.5 rounded-full bg-gray-100 dark:bg-white/10 overflow-hidden max-w-xs">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${Math.min(skill.score, 100)}%` }}
            transition={{ duration: 0.55, delay: index * 0.035 }}
            className={cn('h-full rounded-full', scoreBarColor(skill.score))}
          />
        </div>

        {/* Source questions + contribution math */}
        <div className="flex items-center gap-3 flex-wrap text-[10px]">
          {sourceQs.length > 0 && (
            <div className="flex items-center gap-1">
              <span className="text-gray-400 font-semibold">Sources:</span>
              {sourceQs.map((q) => (
                <span
                  key={q}
                  className="h-4 px-1.5 rounded bg-blue-100 dark:bg-blue-500/15 text-blue-600 dark:text-blue-400 font-bold inline-flex items-center"
                >
                  Q{q}
                </span>
              ))}
            </div>
          )}
          {contribution && weightLabel && (
            <span className="font-mono text-gray-400 dark:text-gray-500">
              {Math.round(skill.score)} × {weightLabel} ={' '}
              <span className="text-violet-600 dark:text-violet-400 font-bold">{contribution}</span>
            </span>
          )}
        </div>
      </div>

      {/* Right: score + inspect hint */}
      <div className="flex flex-col items-end gap-1.5 shrink-0">
        <div
          className={cn(
            'text-2xl font-extrabold',
            isMissing ? 'text-red-500' : scoreColor(skill.score),
          )}
        >
          {skill.score > 0 ? Math.round(skill.score) : '—'}
        </div>
        <span className="text-[10px] font-semibold text-violet-500 dark:text-violet-400 group-hover:underline inline-flex items-center gap-0.5">
          Inspect <ChevronRight className="h-3 w-3" />
        </span>
      </div>
    </motion.div>
  );
}

// ─── Question Row ─────────────────────────────────────────────────────────────

function QuestionRow({ q }: { q: QuestionItem }) {
  const { t } = useLanguage();
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded-2xl border border-gray-100 dark:border-white/[0.06] overflow-hidden bg-white dark:bg-white/[0.02]">
      <div
        className="flex items-start justify-between gap-4 p-5 cursor-pointer hover:bg-gray-50/50 dark:hover:bg-white/[0.02] transition-colors"
        onClick={() => setOpen(!open)}
      >
        <div className="flex items-start gap-3 min-w-0">
          <span className="h-8 w-8 rounded-xl bg-blue-100 dark:bg-blue-500/15 text-blue-600 dark:text-blue-400 text-sm font-bold flex items-center justify-center shrink-0">
            {q.id}
          </span>
          <div className="min-w-0">
            <div className="text-sm font-bold text-gray-900 dark:text-white leading-snug">
              {q.title}
            </div>
            <div className="flex items-center gap-2 mt-1.5 flex-wrap">
              {q.category && (
                <span className="px-2 py-0.5 rounded-lg bg-violet-50 dark:bg-violet-500/10 text-[11px] font-semibold text-violet-600 dark:text-violet-400">
                  {q.category}
                </span>
              )}
              <EvidenceQualityPill quality={q.evidence_quality} size="xs" />
            </div>
          </div>
        </div>
        <div className="text-right shrink-0 flex flex-col items-end gap-1">
          <div className={cn('text-xl font-extrabold', scoreColor(q.score))}>{q.score}</div>
          <div className="text-[10px] text-gray-400">{q.label}</div>
          <Eye className="h-3.5 w-3.5 text-gray-300 mt-0.5" />
        </div>
      </div>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden border-t border-gray-100 dark:border-white/[0.06]"
          >
            <div className="p-5 space-y-3">
              {q.answer ? (
                <div>
                  <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-1.5">
                    {t('recruiter.interviewAnalysis.candidateAnswer')}
                  </div>
                  <div className="p-3 rounded-xl bg-gray-50 dark:bg-white/[0.03] text-sm text-gray-700 dark:text-gray-300 leading-relaxed border border-gray-100 dark:border-white/[0.05]">
                    {q.answer}
                  </div>
                </div>
              ) : null}
              {q.justification ? (
                <div>
                  <div className="text-[10px] font-bold uppercase tracking-wider text-violet-500 mb-1.5 flex items-center gap-1">
                    <Sparkles className="h-3 w-3" /> AI Justification
                  </div>
                  <div className="p-3 rounded-xl bg-violet-50/60 dark:bg-violet-500/5 text-sm text-violet-800 dark:text-violet-200 leading-relaxed border border-violet-100 dark:border-violet-500/15">
                    {q.justification}
                  </div>
                </div>
              ) : null}
              {!q.answer && !q.justification && (
                <p className="text-xs text-gray-400 italic">
                  No recorded response for this question.
                </p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function RecruiterInterviewAnalysisPage() {
  const { t } = useLanguage();
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState<SecondaryTab>('evidence');
  const [skillFilter, setSkillFilter] = useState<SkillFilter>('all');
  const [drawerSkill, setDrawerSkill] = useState<DrawerSkill | null>(null);
  const [note, setNote] = useState('');
  const [savedNotes, setSavedNotes] = useState<string[]>([]);
  const [data, setData] = useState<AIScoresResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const appId = id || searchParams.get('id') || searchParams.get('application_id') || '';
  const candidateName = searchParams.get('name') || '';

  const NEXT_STAGE: Record<string, string> = {
    applied: 'screening',
    screening: 'interviewing',
    interviewing: 'offer',
    offer: 'hired',
    invited: 'screening',
    shortlisted: 'interviewing',
    pending: 'screening',
    interview: 'offer',
    active: 'hired',
  };
  const TERMINAL_STAGES = ['hired', 'rejected', 'archived'];

  const [appStatus, setAppStatus] = useState('');
  const [stageUpdating, setStageUpdating] = useState(false);
  const [appMeta, setAppMeta] = useState<{
    full_name?: string;
    email?: string;
    role?: string;
    created_at?: string;
    analysis?: Record<string, unknown>;
    interview_state?: string;
    cv_score?: number | null;
  } | null>(null);

  useEffect(() => {
    if (!appId) {
      setError(t('recruiter.interviewAnalysis.noAppId'));
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);

    candidatesService
      .getAIScore(appId)
      .then((res) => setData(res as unknown as AIScoresResponse))
      .catch((err) => setError(err?.message || t('recruiter.interviewAnalysis.loadFailed')))
      .finally(() => setLoading(false));

    candidatesService
      .getApplication(appId)
      .then((app: unknown) => {
        const a = app as Record<string, unknown>;
        if (!a) return;
        const cand = a.candidate as Record<string, unknown> | undefined;
        setAppMeta({
          full_name: (a.full_name as string) || (cand?.name as string) || '',
          email: (a.email as string) || (cand?.email as string) || '',
          role: (a.job_title as string) || '',
          created_at: (a.created_at as string) || undefined,
          analysis: (a.analysis as Record<string, unknown>) || undefined,
          interview_state: (a.interview_state as string) || undefined,
          cv_score: (a.cv_score as number) ?? undefined,
        });
        if (a.status) setAppStatus(a.status as string);
        if (typeof a.recruiter_notes === 'string' && a.recruiter_notes.trim()) {
          setSavedNotes(a.recruiter_notes.split('\n').filter(Boolean));
        }
      })
      .catch(() => {/* best-effort */});
  }, [appId, t]);

  // ── Derived ───────────────────────────────────────────────────────────────

  const displayName =
    candidateName || appMeta?.full_name || t('candidates.col.candidate');
  const displayEmail = appMeta?.email || '';
  const displayRole = appMeta?.role || '';

  const interviewDone =
    ['completed', 'flagged'].includes(appMeta?.interview_state ?? '') ||
    (data?.questions && data.questions.length > 0) ||
    (data?.evidence && data.evidence.length > 0);

  // ============================================================
  // CANONICAL SCORE CONTRACT
  // ============================================================
  // cv_score     = CV-only score
  // rubric_score = interview/rubric component
  // final_score  = ONLY canonical post-interview score
  //
  // Never derive final_score from overall_score/cv_score here.
  // ============================================================
  const cvScore = data?.cv_score ?? appMeta?.cv_score ?? null;
  const finalScore = data?.final_score ?? null;
  const rubricScore = data?.rubric_score ?? null;

  const overallScore = interviewDone
    ? finalScore
    : cvScore;

  const scoreLabel =
    overallScore == null
      ? ''
      : overallScore >= 85
      ? t('recruiter.interviewAnalysis.excellent')
      : overallScore >= 70
      ? t('recruiter.interviewAnalysis.strong')
      : overallScore >= 50
      ? t('recruiter.interviewAnalysis.fair')
      : t('recruiter.interviewAnalysis.needsWork');

  const cvAnalysis = (appMeta?.analysis as Record<string, unknown>) || {};

  const skillBreakdown = data?.skill_breakdown ?? [];
  const evidenceList = data?.evidence ?? [];
  const questionsList = data?.questions ?? [];
  const cvSkillBreakdown = data?.cv_skill_breakdown ?? [];
  const cvMissingSkills =
    data?.cv_missing_skills ??
    ((cvAnalysis.missing_skills as string[]) || []);
  const gaps = data?.gaps ?? [];

  const nextStage =
    appStatus && !TERMINAL_STAGES.includes(appStatus)
      ? (NEXT_STAGE[appStatus] ?? '')
      : '';
  const nextStageLabel =
    nextStage === 'screening'
      ? t('recruiter.interviewAnalysis.moveToScreening')
      : nextStage === 'interviewing'
      ? t('recruiter.interviewAnalysis.moveToInterview')
      : nextStage === 'offer'
      ? t('recruiter.interviewAnalysis.advanceToOffer')
      : nextStage === 'hired'
      ? t('recruiter.interviewAnalysis.markAsHired')
      : nextStage
      ? t('recruiter.interviewAnalysis.moveToNext')
      : '';

  // ── Unified skills (rubric-first) ─────────────────────────────────────────

  const unifiedSkills = useMemo<DrawerSkill[]>(() => {
    const list: DrawerSkill[] = [];
    const ivMap = new Map<string, SkillBreakdownItem>();
    skillBreakdown.forEach((s) => ivMap.set(s.name.toLowerCase(), s));
    const cvMap = new Map<string, CVEvalSkillItem>();
    cvSkillBreakdown.forEach((s) => cvMap.set(s.name.toLowerCase(), s));

    skillBreakdown.forEach((s) => {
      list.push({
        ...s,
        source_type: cvMap.has(s.name.toLowerCase()) ? 'both' : 'interview',
      });
    });

    cvSkillBreakdown.forEach((cvs) => {
      if (!ivMap.has(cvs.name.toLowerCase())) {
        list.push({
          name: cvs.name,
          score: cvs.score,
          is_required: false,
          assessed: false,
          category: cvs.category || 'CV Skill',
          explanation: cvs.feedback || undefined,
          evidence: [],
          weight: cvs.normalized_weight ?? cvs.weight,
          normalized_weight: cvs.normalized_weight,
          level: cvs.level || 'Mentioned',
          evidence_quality: 'no_evidence',
          source_type: 'cv',
        });
      }
    });

    const missingNames = Array.from(new Set([...cvMissingSkills, ...gaps]));
    missingNames.forEach((name) => {
      const lower = name.toLowerCase();
      if (!ivMap.has(lower) && !cvMap.has(lower)) {
        list.push({
          name,
          score: 0,
          is_required: true,
          assessed: false,
          category: 'Rubric Criterion',
          explanation: undefined,
          evidence: [],
          weight: null,
          normalized_weight: null,
          level: 'Missing',
          evidence_quality: 'no_evidence',
          source_type: 'missing',
        });
      }
    });

    return list;
  }, [skillBreakdown, cvSkillBreakdown, cvMissingSkills, gaps]);

  const filteredSkills = useMemo(() => {
    if (skillFilter === 'interview')
      return unifiedSkills.filter(
        (s) => s.source_type === 'interview' || s.source_type === 'both',
      );
    if (skillFilter === 'cv')
      return unifiedSkills.filter((s) => s.source_type === 'cv');
    if (skillFilter === 'missing')
      return unifiedSkills.filter((s) => s.source_type === 'missing');
    return unifiedSkills;
  }, [unifiedSkills, skillFilter]);

  const validatedCount = unifiedSkills.filter(
    (s) => s.source_type === 'interview' || s.source_type === 'both',
  ).length;
  const missingCount = unifiedSkills.filter((s) => s.source_type === 'missing').length;

  // Score math rows (interview skills with weight)
  const scoreMathRows = useMemo(
    () =>
      skillBreakdown
        .filter((s) => s.score > 0 && (s.normalized_weight ?? s.weight) != null)
        .map((s) => {
          const wt = weightAsDecimal(s.normalized_weight ?? s.weight);
          return {
            name: s.name,
            score: Math.round(s.score),
            weight: fmtWeight(s.normalized_weight ?? s.weight) ?? '—',
            contribution: (s.score * wt).toFixed(1),
          };
        }),
    [skillBreakdown],
  );

  // ── Handlers ──────────────────────────────────────────────────────────────

  const handleSaveNote = async () => {
    if (!note.trim()) {
      customToast({
        type: 'warning',
        title: t('recruiter.interviewAnalysis.emptyNote'),
        message: t('recruiter.interviewAnalysis.emptyNoteDesc'),
      });
      return;
    }
    if (!appId) return;
    const newNote = note.trim();
    try {
      const existing = (await candidatesService.getNotes(appId)) as {
        notes?: string;
      };
      const existingNotes =
        typeof existing?.notes === 'string' ? existing.notes : '';
      const lastLine = existingNotes.split('\n').filter(Boolean).pop();
      if (lastLine === newNote) {
        setNote('');
        return;
      }
      const combined =
        (existingNotes.trim() ? existingNotes.trim() + '\n' : '') + newNote;
      const res = (await candidatesService.addNote(appId, combined)) as {
        notes?: string;
      };
      if (typeof res?.notes === 'string')
        setSavedNotes(res.notes.split('\n').filter(Boolean));
      setNote('');
      customToast({
        type: 'success',
        title: t('recruiter.interviewAnalysis.noteSaved'),
        message: t('recruiter.interviewAnalysis.noteSavedDesc'),
      });
    } catch {
      customToast({
        type: 'error',
        title: t('recruiter.interviewAnalysis.saveFailed'),
        message: t('recruiter.interviewAnalysis.saveFailedDesc'),
      });
    }
  };

  const handleShare = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      customToast({
        type: 'success',
        title: t('recruiter.interviewAnalysis.shareSuccessTitle'),
        message: t('recruiter.interviewAnalysis.shareSuccessDesc'),
      });
    } catch {
      customToast({
        type: 'error',
        title: t('recruiter.interviewAnalysis.shareFailTitle'),
        message: t('recruiter.interviewAnalysis.shareFailDesc'),
      });
    }
  };

  const handleMoveToNextStage = async () => {
    if (!appId) return;
    if (TERMINAL_STAGES.includes(appStatus)) {
      customToast({
        type: 'warning',
        title: t('recruiter.interviewAnalysis.noNextStage'),
        message: t('recruiter.interviewAnalysis.noNextStageDesc').replace(
          '{status}',
          appStatus,
        ),
      });
      return;
    }
    const next = NEXT_STAGE[appStatus];
    if (!next) {
      customToast({
        type: 'warning',
        title: t('recruiter.interviewAnalysis.unknownStage'),
        message: t('recruiter.interviewAnalysis.unknownStageDesc'),
      });
      return;
    }
    setStageUpdating(true);
    try {
      await candidatesService.updateApplicationStatus(appId, next);
      setAppStatus(next);
      customToast({
        type: 'success',
        title: t('recruiter.interviewAnalysis.stageUpdated'),
        message: t('recruiter.interviewAnalysis.stageUpdatedDesc').replace(
          '{next}',
          next,
        ),
      });
    } catch (err) {
      customToast({
        type: 'error',
        title: t('recruiter.interviewAnalysis.updateFailed'),
        message:
          (err as { message?: string })?.message ||
          t('recruiter.interviewAnalysis.updateFailedDesc'),
      });
    } finally {
      setStageUpdating(false);
    }
  };

  const handleReject = async () => {
    if (!appId) return;
    try {
      await candidatesService.updateApplicationStatus(appId, 'rejected');
      setAppStatus('rejected');
      customToast({
        type: 'success',
        title: 'Application Rejected',
        message: 'Candidate moved to Rejected.',
      });
    } catch {
      customToast({ type: 'error', title: 'Failed', message: 'Could not reject.' });
    }
  };

  // ── Loading / Error ───────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 rounded-full border-2 border-violet-500 border-t-transparent animate-spin" />
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {t('recruiter.interviewAnalysis.loading')}
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <p className="text-red-500 font-semibold">{error}</p>
        <button
          onClick={() => navigate('/candidates')}
          className="px-4 py-2 rounded-2xl bg-violet-600 hover:bg-violet-700 text-white text-sm font-bold"
        >
          {t('recruiter.interviewAnalysis.backToCandidates')}
        </button>
      </div>
    );
  }

  const trustScore =
    data?.trust?.score ?? data?.penalty_breakdown?.trust_score ?? null;
  const trustCoverage =
    data?.trust?.coverage ??
    (data?.rubric_coverage_pct != null
      ? Math.round(data.rubric_coverage_pct)
      : null);

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-5 max-w-7xl mx-auto">

      {/* ── Breadcrumb bar ── */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2 text-sm">
          <button
            onClick={() => navigate(`/candidates/${appId}`)}
            className="inline-flex items-center gap-1.5 text-violet-600 dark:text-violet-400 hover:underline font-semibold"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <Link
            to="/candidates"
            className="font-semibold text-violet-600 dark:text-violet-400 hover:underline"
          >
            {t('recruiter.interviewAnalysis.candidates')}
          </Link>
          <ChevronRight className="h-4 w-4 text-gray-300" />
          <Link
            to={`/candidates/${appId}`}
            className="font-semibold text-violet-600 dark:text-violet-400 hover:underline truncate max-w-[140px]"
          >
            {displayName}
          </Link>
          <ChevronRight className="h-4 w-4 text-gray-300" />
          <span className="text-gray-500 dark:text-gray-400 text-sm">
            {t('recruiter.interviewAnalysis.title')}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {data?.rubric_version && (
            <span className="px-2.5 py-1 rounded-full bg-blue-50 dark:bg-blue-500/10 text-xs font-bold text-blue-600 dark:text-blue-400 border border-blue-100 dark:border-blue-500/20">
              Snapshot v{data.rubric_version}
            </span>
          )}
          {data?.is_rubric_driven && (
            <span className="px-2.5 py-1 rounded-full bg-violet-50 dark:bg-violet-500/10 text-xs font-bold text-violet-600 dark:text-violet-400">
              Rubric-Driven <Star className="h-3 w-3 inline fill-current" />
            </span>
          )}
          <button
            onClick={handleShare}
            className="px-3 py-1.5 rounded-xl bg-white dark:bg-white/[0.04] border border-gray-200 dark:border-white/10 text-sm font-bold text-gray-700 dark:text-gray-300 hover:border-violet-300 transition-all inline-flex items-center gap-1.5"
          >
            <Share2 className="h-3.5 w-3.5" />
            {t('recruiter.interviewAnalysis.share')}
          </button>
        </div>
      </div>

      {/* ── Hero card ── */}
      <Card className="p-6 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
        <div className="flex flex-col lg:flex-row lg:items-center gap-6">

          {/* Identity */}
          <div className="flex items-center gap-4 flex-1 min-w-0">
            <div className="h-14 w-14 rounded-2xl bg-violet-100 dark:bg-violet-500/15 flex items-center justify-center text-violet-600 dark:text-violet-400 text-xl font-extrabold shrink-0">
              {displayName
                .trim()
                .split(/\s+/)
                .map((w) => w[0])
                .join('')
                .slice(0, 2)
                .toUpperCase() || 'CA'}
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h1 className="text-xl font-extrabold text-gray-900 dark:text-white truncate">
                  {displayName}
                </h1>
                <span className="px-2.5 py-0.5 rounded-full bg-violet-50 dark:bg-violet-500/10 text-[11px] font-bold text-violet-600 dark:text-violet-400 shrink-0">
                  {data?.status || appStatus || t('recruiter.interviewAnalysis.pending')}
                </span>
              </div>
              {displayRole && (
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                  {displayRole}
                </p>
              )}
              {displayEmail && (
                <p className="text-xs text-gray-400 mt-0.5">{displayEmail}</p>
              )}
            </div>
          </div>

          {/* Overall Score */}
          <div className="text-center shrink-0 px-4 py-2">
            <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-1">
              {interviewDone
                ? t('recruiter.interviewAnalysis.overallScore')
                : t('recruiter.interviewAnalysis.cvMatch')}
            </div>
            <div
              className={cn(
                'text-5xl font-extrabold leading-none',
                overallScore != null ? scoreColor(overallScore) : 'text-gray-300',
              )}
            >
              {overallScore ?? '—'}
            </div>
            {overallScore != null && scoreLabel && (
              <div className={cn('text-sm font-bold mt-1', scoreColor(overallScore))}>
                {scoreLabel}
              </div>
            )}
          </div>

          {/* AI Recommendation */}
          <div className="shrink-0 text-center">
            <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-2">
              AI Recommendation
            </div>
            {data?.recommendation?.label ? (
              <>
                <RecommendationBadge label={data.recommendation.label} large />
                <p className="text-[10px] text-gray-400 mt-1.5">
                  Based on rubric evaluation
                </p>
              </>
            ) : overallScore != null ? (
              <>
                <RecommendationBadge
                  label={
                    overallScore >= 70
                      ? 'Hire'
                      : overallScore >= 50
                      ? 'Consider'
                      : 'Low Priority'
                  }
                  large
                />
                <p className="text-[10px] text-gray-400 mt-1.5">
                  Derived from score {overallScore}/100
                </p>
              </>
            ) : (
              <span className="text-xs text-gray-400 italic">—</span>
            )}
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-2 xl:grid-cols-4 gap-2 shrink-0">
            {[
              {
                label: 'Coverage',
                value:
                  trustCoverage != null ? `${Math.round(trustCoverage)}%` : '—',
                color: 'text-emerald-600 dark:text-emerald-400',
              },
              {
                label: 'Trust',
                value:
                  trustScore != null ? `${Math.round(trustScore)}` : '—',
                color: 'text-blue-600 dark:text-blue-400',
              },
              {
                label: 'Validated',
                value: validatedCount > 0 ? `${validatedCount}` : '—',
                color: 'text-violet-600 dark:text-violet-400',
              },
              {
                label: 'Gaps',
                value: missingCount > 0 ? `${missingCount}` : '0',
                color:
                  missingCount > 0
                    ? 'text-red-500'
                    : 'text-emerald-600 dark:text-emerald-400',
              },
            ].map((stat) => (
              <div
                key={stat.label}
                className="p-3 rounded-xl bg-gray-50 dark:bg-white/[0.03] border border-gray-100 dark:border-white/[0.06] text-center min-w-[64px]"
              >
                <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-0.5">
                  {stat.label}
                </div>
                <div className={cn('text-xl font-extrabold', stat.color)}>
                  {stat.value}
                </div>
              </div>
            ))}
          </div>
        </div>
      </Card>

      {/* ── Main layout ── */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_276px] gap-5 items-start">

        {/* ── Left column ── */}
        <div className="space-y-5">

          {/* ── Talent Radar Graph ── */}
          <TalentRadarGraph skills={unifiedSkills} />

          {/* ── Rubric Skills ── */}
          <Card className="p-6 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5">
              <div>
                <h2 className="text-lg font-extrabold text-gray-900 dark:text-white flex items-center gap-2">
                  <Award className="h-5 w-5 text-violet-500" />
                  Rubric Evaluation
                </h2>
                <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
                  Frozen EvaluationConfigSnapshot · Click any skill to inspect evidence
                </p>
              </div>

              {/* Filter */}
              <div className="flex items-center gap-1 p-1 rounded-xl bg-gray-100 dark:bg-white/5 border border-gray-200 dark:border-white/10 self-start sm:self-auto shrink-0">
                {(
                  [
                    { id: 'all', label: 'All' },
                    { id: 'interview', label: 'Interview' },
                    { id: 'cv', label: 'CV Only' },
                    { id: 'missing', label: 'Missing' },
                  ] as { id: SkillFilter; label: string }[]
                ).map((f) => (
                  <button
                    key={f.id}
                    onClick={() => setSkillFilter(f.id)}
                    className={cn(
                      'px-2.5 py-1 rounded-lg text-xs font-bold transition-all',
                      skillFilter === f.id
                        ? 'bg-white dark:bg-violet-600 text-violet-700 dark:text-white shadow-sm'
                        : 'text-gray-500 hover:text-gray-700 dark:text-gray-400',
                    )}
                  >
                    {f.label}
                    {f.id === 'missing' && missingCount > 0 && (
                      <span className="ml-1 px-1 rounded-full bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-400 text-[9px]">
                        {missingCount}
                      </span>
                    )}
                  </button>
                ))}
              </div>
            </div>

            {filteredSkills.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <Award className="h-10 w-10 text-gray-200 dark:text-gray-700 mb-3" />
                <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
                  {unifiedSkills.length === 0
                    ? 'No evaluation data available.'
                    : 'No skills match this filter.'}
                </p>
                {unifiedSkills.length === 0 && (
                  <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                    The AI interview may not have been completed yet, or no rubric was
                    attached to this job.
                  </p>
                )}
              </div>
            ) : (
              <div className="space-y-2.5">
                {filteredSkills.map((skill, i) => (
                  <SkillRow
                    key={skill.name}
                    skill={skill}
                    evidenceList={evidenceList}
                    index={i}
                    onInspect={setDrawerSkill}
                  />
                ))}
              </div>
            )}
          </Card>

          {/* ── Score math ── */}
          {scoreMathRows.length > 0 && (
            <Card className="p-6 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
              <h2 className="text-sm font-extrabold text-gray-900 dark:text-white flex items-center gap-2 mb-4">
                <Calculator className="h-4 w-4 text-violet-500" />
                Score Calculation
              </h2>
              <div className="space-y-1">
                {scoreMathRows.map((row) => (
                  <div
                    key={row.name}
                    className="flex items-center justify-between py-2 border-b border-gray-50 dark:border-white/[0.04] last:border-0"
                  >
                    <span className="text-sm text-gray-700 dark:text-gray-300 truncate max-w-[180px]">
                      {row.name}
                    </span>
                    <span className="text-sm font-mono text-gray-500 dark:text-gray-400 shrink-0">
                      {row.score} × {row.weight} ={' '}
                      <span className="font-bold text-violet-600 dark:text-violet-400">
                        {row.contribution}
                      </span>
                    </span>
                  </div>
                ))}
              </div>
              <div className="mt-4 pt-3 border-t-2 border-gray-200 dark:border-white/15 flex flex-wrap gap-6">
                {rubricScore != null && (
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-extrabold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                      Rubric Score
                    </span>
                    <span className={cn('text-xl font-extrabold', scoreColor(rubricScore))}>
                      {rubricScore}
                    </span>
                  </div>
                )}
                {cvScore != null && (
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-extrabold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                      CV Match
                    </span>
                    <span className={cn('text-xl font-extrabold', scoreColor(cvScore))}>
                      {Math.round(cvScore)}
                    </span>
                  </div>
                )}
                {overallScore != null && (
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-extrabold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                      Final
                    </span>
                    <span
                      className={cn('text-2xl font-extrabold', scoreColor(overallScore))}
                    >
                      {overallScore}
                    </span>
                  </div>
                )}
              </div>
            </Card>
          )}

          {/* ── Secondary tabs ── */}
          <div className="border-b border-gray-200 dark:border-white/[0.08]">
            <div className="flex items-center gap-6 overflow-x-auto scrollbar-none">
              {(
                [
                  {
                    id: 'evidence' as SecondaryTab,
                    icon: MessageSquare,
                    label: t('recruiter.interviewAnalysis.tab.evidence'),
                    badge: questionsList.length,
                  },
                  {
                    id: 'cv' as SecondaryTab,
                    icon: FileText,
                    label: t('recruiter.interviewAnalysis.tab.cv'),
                    badge: 0,
                  },
                  {
                    id: 'integrity' as SecondaryTab,
                    icon: Shield,
                    label: t('recruiter.interviewAnalysis.tab.integrity'),
                    badge: 0,
                  },
                ]
              ).map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    'pb-3 text-sm font-semibold whitespace-nowrap border-b-2 -mb-px transition-colors flex items-center gap-1.5',
                    activeTab === tab.id
                      ? 'border-violet-600 text-violet-600 dark:border-violet-400 dark:text-violet-400'
                      : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400',
                  )}
                >
                  <tab.icon className="h-3.5 w-3.5" />
                  {tab.label}
                  {tab.badge > 0 && (
                    <span className="px-1.5 rounded-full bg-violet-100 dark:bg-violet-500/20 text-violet-600 dark:text-violet-400 text-[10px] font-bold">
                      {tab.badge}
                    </span>
                  )}
                </button>
              ))}
            </div>
          </div>

          <AnimatePresence mode="wait">
            {/* Interview Evidence */}
            {activeTab === 'evidence' && (
              <motion.div
                key="ev"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="space-y-3"
              >
                {questionsList.length > 0 ? (
                  questionsList.map((q) => <QuestionRow key={q.id} q={q} />)
                ) : (
                  <Card className="p-10 border-0 shadow-sm bg-white dark:bg-white/[0.03] text-center">
                    <MessageSquare className="h-10 w-10 text-gray-200 dark:text-gray-700 mx-auto mb-3" />
                    <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
                      {t('recruiter.interviewAnalysis.noAnswers')}
                    </p>
                    <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                      {t('recruiter.interviewAnalysis.noAnswersDesc')}
                    </p>
                  </Card>
                )}
              </motion.div>
            )}

            {/* CV */}
            {activeTab === 'cv' && (
              <motion.div
                key="cv"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
              >
                <Card className="p-6 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
                  <CVEvaluation
                    cvScore={cvScore ?? undefined}
                    cvRubricWeighted={
                      data?.cv_rubric_weighted ??
                      (typeof cvAnalysis.cv_rubric_weighted === 'boolean'
                        ? cvAnalysis.cv_rubric_weighted
                        : undefined)
                    }
                    cvScoringMethod={
                      data?.cv_scoring_method ??
                      (cvAnalysis.scoring_method as string)
                    }
                    cvCoveragePct={
                      data?.cv_coverage_pct ?? (cvAnalysis.coverage_pct as number)
                    }
                    cvSkillBreakdown={
                      data?.cv_skill_breakdown ??
                      Object.entries(
                        (cvAnalysis.skill_scores as Record<string, unknown>) || {},
                      ).map(([name, details]) => {
                        const d = details as Record<string, unknown>;
                        return {
                          name,
                          score: (d?.score as number) ?? 0,
                          weight: d?.weight as number,
                          normalized_weight: d?.normalized_weight as number,
                          level: d?.level as string,
                          feedback: d?.feedback as string,
                          category: d?.category as string,
                        };
                      })
                    }
                    cvEvidence={
                      data?.cv_evidence ??
                      Object.entries(
                        (cvAnalysis.skill_scores as Record<string, unknown>) || {},
                      ).map(([name, details]) => {
                        const d = details as Record<string, unknown>;
                        return {
                          skill_name: name,
                          score: (d?.score as number) ?? 0,
                          weight: d?.normalized_weight as number,
                          feedback: d?.feedback as string,
                        };
                      })
                    }
                    cvMissingSkills={cvMissingSkills}
                  />
                </Card>
              </motion.div>
            )}

            {/* Integrity */}
            {activeTab === 'integrity' && (
              <motion.div
                key="int"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="space-y-5"
              >
                <Card className="p-6 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
                  <h2 className="text-base font-extrabold text-gray-900 dark:text-white flex items-center gap-2 mb-5">
                    <Shield className="h-5 w-5 text-emerald-500" />
                    {t('recruiter.interviewAnalysis.proctoringTitle')}
                  </h2>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    {[
                      {
                        label: t('recruiter.interviewAnalysis.fraudRiskScore'),
                        display: String(data?.fraud_risk_score ?? 0),
                        color: 'text-emerald-600 dark:text-emerald-400',
                        bg: 'bg-emerald-50/70 dark:bg-emerald-500/10 border-emerald-100 dark:border-emerald-500/20',
                      },
                      {
                        label: t('recruiter.interviewAnalysis.integrityScore'),
                        display:
                          data?.integrity_score != null
                            ? `${(data.integrity_score * 100).toFixed(0)}%`
                            : '—',
                        color: 'text-blue-600 dark:text-blue-400',
                        bg: 'bg-blue-50/70 dark:bg-blue-500/10 border-blue-100 dark:border-blue-500/20',
                      },
                      {
                        label: t('recruiter.interviewAnalysis.aiConfidence'),
                        display:
                          data?.ai_confidence != null
                            ? `${Math.round(data.ai_confidence * 100)}%`
                            : '—',
                        color: 'text-violet-600 dark:text-violet-400',
                        bg: 'bg-violet-50/70 dark:bg-violet-500/10 border-violet-100 dark:border-violet-500/20',
                      },
                    ].map((item) => (
                      <div
                        key={item.label}
                        className={cn('p-4 rounded-2xl border text-center', item.bg)}
                      >
                        <div className="text-[10px] font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-1">
                          {item.label}
                        </div>
                        <div className={cn('text-3xl font-extrabold', item.color)}>
                          {item.display}
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="mt-5 p-4 rounded-2xl border border-gray-100 dark:border-white/[0.06] space-y-1">
                    <h3 className="text-sm font-bold text-gray-900 dark:text-white mb-2">
                      {t('recruiter.interviewAnalysis.proctoringAuditSummary')}
                    </h3>
                    {[
                      {
                        label: t('recruiter.interviewAnalysis.faceDetection'),
                        value:
                          data?.proctoring_summary?.face_detection ||
                          'Passed (No Anomaly)',
                      },
                      {
                        label: t('recruiter.interviewAnalysis.browserSwitchCheck'),
                        value:
                          data?.proctoring_summary?.browser_switches ||
                          `${data?.penalty_breakdown?.proctoring_violations_count ?? 0} Switches`,
                      },
                      {
                        label: t('recruiter.interviewAnalysis.plagiarismCheck'),
                        value:
                          data?.proctoring_summary?.plagiarism ||
                          'Passed (Clean Verbatim)',
                      },
                    ].map((row) => (
                      <div
                        key={row.label}
                        className="flex items-center justify-between py-1.5 border-b border-gray-50 dark:border-white/[0.03] last:border-0 text-xs"
                      >
                        <span className="text-gray-600 dark:text-gray-300">
                          {row.label}
                        </span>
                        <span className="font-bold text-emerald-600 dark:text-emerald-400">
                          {row.value}
                        </span>
                      </div>
                    ))}
                  </div>
                </Card>

                <Card className="p-6 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
                  <h2 className="text-sm font-extrabold text-gray-900 dark:text-white flex items-center gap-2 mb-4">
                    <Shield className="h-4 w-4 text-violet-500" />
                    {t('recruiter.interviewAnalysis.specsTitle')}
                  </h2>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {[
                      {
                        label: t('recruiter.interviewAnalysis.candidateName'),
                        value: displayName,
                      },
                      {
                        label: t('recruiter.interviewAnalysis.candidateEmail'),
                        value: displayEmail || 'N/A',
                      },
                      {
                        label: t('recruiter.interviewAnalysis.appId'),
                        value: `APP-${String(appId).padStart(6, '0')}`,
                      },
                      {
                        label: t('recruiter.interviewAnalysis.interviewStatus'),
                        value: data?.status ?? appStatus ?? '—',
                      },
                      {
                        label: t('recruiter.interviewAnalysis.scoringModel'),
                        value: data?.scoring_model ?? 'Snapshot Deterministic',
                      },
                      {
                        label: t('recruiter.interviewAnalysis.rubricVersion'),
                        value:
                          data?.rubric_version != null
                            ? `v${data.rubric_version}`
                            : '—',
                      },
                      {
                        label: t('recruiter.interviewAnalysis.totalQuestions'),
                        value: String(questionsList.length),
                      },
                      {
                        label: t('recruiter.interviewAnalysis.evaluationDate'),
                        value: appMeta?.created_at ?? '—',
                      },
                    ].map((item, i) => (
                      <div
                        key={i}
                        className="p-3 rounded-xl bg-gray-50/70 dark:bg-white/[0.03] border border-gray-100 dark:border-white/[0.05]"
                      >
                        <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-0.5">
                          {item.label}
                        </div>
                        <div className="text-sm font-bold text-gray-900 dark:text-white">
                          {item.value}
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              </motion.div>
            )}
          </AnimatePresence>

          <p className="text-center text-xs text-gray-400 dark:text-gray-500 py-2">
            {t('recruiter.interviewAnalysis.disclaimer')}
          </p>
        </div>

        {/* ── Right sidebar ── */}
        <div className="space-y-4 lg:sticky lg:top-20">

          {/* Decision card */}
          <Card className="p-5 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
            <div className="flex items-center gap-2 mb-3">
              <Award className="h-4 w-4 text-amber-500" />
              <h3 className="text-sm font-bold text-gray-900 dark:text-white">
                {t('recruiter.interviewAnalysis.recommendation')}
              </h3>
            </div>

            {/* Recommendation pill */}
            {data?.recommendation?.label ? (
              <div className="mb-4">
                <RecommendationBadge label={data.recommendation.label} large />
                <p className="text-xs text-gray-400 dark:text-gray-500 mt-1.5">
                  {overallScore != null ? `Score ${overallScore}/100` : 'Rubric-based'}
                </p>
              </div>
            ) : overallScore != null ? (
              <div className="mb-4">
                <RecommendationBadge
                  label={
                    overallScore >= 70
                      ? 'Hire'
                      : overallScore >= 50
                      ? 'Consider'
                      : 'Low Priority'
                  }
                  large
                />
                <p className="text-xs text-gray-400 mt-1.5">
                  Score {overallScore}/100
                </p>
              </div>
            ) : (
              <div className="mb-4 p-3 rounded-xl bg-gray-50 dark:bg-white/[0.03] text-xs text-gray-400 italic">
                No recommendation available yet.
              </div>
            )}

            {/* Move to next stage */}
            <button
              onClick={handleMoveToNextStage}
              disabled={stageUpdating || loading || !nextStage}
              className="w-full py-3 rounded-2xl bg-violet-600 hover:bg-violet-700 text-white text-sm font-bold shadow-md shadow-violet-500/20 transition-colors inline-flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed mb-2"
            >
              {stageUpdating ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <ArrowRightCircle className="h-4 w-4" />
              )}
              {stageUpdating
                ? t('recruiter.interviewAnalysis.updating')
                : nextStageLabel || t('recruiter.interviewAnalysis.moveToNext')}
            </button>

            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={handleReject}
                className="py-2 rounded-xl border border-red-200 dark:border-red-500/20 text-red-600 dark:text-red-400 text-xs font-bold hover:bg-red-50 dark:hover:bg-red-500/5 transition-colors"
              >
                Reject
              </button>
              <button
                onClick={() => setActiveTab('evidence')}
                className="py-2 rounded-xl border border-gray-200 dark:border-white/10 text-gray-700 dark:text-gray-300 text-xs font-bold hover:bg-gray-50 dark:hover:bg-white/[0.03] transition-colors inline-flex items-center justify-center gap-1"
              >
                <MessageSquare className="h-3 w-3" /> Evidence
              </button>
            </div>
          </Card>

          {/* Trust metrics */}
          {data?.trust && (
            <Card className="p-5 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
              <div className="flex items-center gap-2 mb-3">
                <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                <h3 className="text-sm font-bold text-gray-900 dark:text-white">
                  {t('recruiter.interviewAnalysis.assessmentTrust')}
                </h3>
              </div>
              <div className="space-y-3">
                {[
                  {
                    label: 'Coverage',
                    value: `${data.trust.coverage ?? 0}%`,
                    pct: data.trust.coverage ?? 0,
                    color: 'bg-emerald-500',
                  },
                  {
                    label: 'Trust Score',
                    value: `${data.trust.score ?? 0}`,
                    pct: data.trust.score ?? 0,
                    color: 'bg-blue-500',
                  },
                  {
                    label: 'Evidence Items',
                    value: `${data.trust.count ?? 0}`,
                    pct: Math.min((data.trust.count ?? 0) * 10, 100),
                    color: 'bg-violet-500',
                  },
                ].map((r) => (
                  <div key={r.label}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-gray-600 dark:text-gray-300">
                        {r.label}
                      </span>
                      <span className="text-xs font-bold text-gray-900 dark:text-white">
                        {r.value}
                      </span>
                    </div>
                    <div className="h-1.5 rounded-full bg-gray-100 dark:bg-white/10">
                      <div
                        className={cn('h-full rounded-full', r.color)}
                        style={{ width: `${r.pct}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Recruiter notes */}
          <Card className="p-5 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
            <div className="flex items-center gap-2 mb-3">
              <MessageSquare className="h-4 w-4 text-violet-500" />
              <h3 className="text-sm font-bold text-gray-900 dark:text-white">
                {t('recruiter.interviewAnalysis.recruiterNotes')}
              </h3>
            </div>
            {savedNotes.length > 0 && (
              <div className="space-y-1.5 mb-3 max-h-28 overflow-y-auto">
                {savedNotes.map((n, i) => (
                  <div
                    key={i}
                    className="p-2.5 rounded-lg bg-gray-50 dark:bg-white/[0.03] text-xs text-gray-700 dark:text-gray-300 leading-relaxed"
                  >
                    {n}
                  </div>
                ))}
              </div>
            )}
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder={t('recruiter.interviewAnalysis.addNotePlaceholder')}
              rows={3}
              className="w-full p-3 rounded-xl bg-gray-50 dark:bg-white/[0.04] border border-gray-100 dark:border-white/[0.06] text-xs text-gray-900 dark:text-white placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-violet-500/20 focus:border-violet-400 transition-all resize-none"
            />
            <button
              onClick={handleSaveNote}
              className="mt-2 w-full py-2 rounded-xl bg-violet-600 hover:bg-violet-700 text-white text-xs font-bold transition-colors inline-flex items-center justify-center gap-1.5"
            >
              <Save className="h-3.5 w-3.5" />
              {t('recruiter.interviewAnalysis.saveNote')}
            </button>
          </Card>
        </div>
      </div>

      {/* ── Skill Evidence Drawer ── */}
      <AnimatePresence>
        {drawerSkill && (
          <SkillDrawer
            skill={drawerSkill}
            evidenceList={evidenceList}
            onClose={() => setDrawerSkill(null)}
            onViewInQA={(_turn) => {
              setDrawerSkill(null);
              setActiveTab('evidence');
            }}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
