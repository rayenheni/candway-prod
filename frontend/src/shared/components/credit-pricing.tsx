import { Coins, Info } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { cn } from '@/utils/cn';

export type CreditPricingMap = Record<string, number>;

const FEATURE_LABELS: Record<string, string> = {
  cv_analysis: 'CV Analysis (apply + review)',
  interview_question_gen: 'AI Interview Question Generation',
  ai_interview_evaluation: 'AI Interview Final Evaluation',
  pdf_report: 'PDF Report Download',
  ai_invitation: 'AI Invitation',
  score_comparison: 'Score Comparison',
  debrief_summary: 'Debrief Summary',
  translation: 'Translation',
  career_chatbot: 'Career Chatbot',
  wizard_suggest: 'Job Wizard AI Suggest',
  skill_tree_generate: 'Rubric AI Generate',
  ai_search: 'Candidate AI Search',
  career_roadmap: 'Career Roadmap',
  copilot_chat: 'Copilot Chat',
  jd_writer: 'Job Description Writer',
};

const FEATURE_ORDER = [
  'cv_analysis',
  'ai_interview_evaluation',
  'interview_question_gen',
  'ai_search',
  'career_roadmap',
  'jd_writer',
  'copilot_chat',
  'pdf_report',
  'ai_invitation',
  'score_comparison',
  'debrief_summary',
  'translation',
  'career_chatbot',
  'wizard_suggest',
  'skill_tree_generate',
];

interface CreditPricingProps {
  pricing: CreditPricingMap | null | undefined;
  title?: string;
  description?: string;
  compact?: boolean;
}

export default function CreditPricing({
  pricing,
  title = 'AI Credit Pricing',
  description = 'Credits are consumed for AI actions. Prices are controlled by the platform admin and can change.',
  compact = false,
}: CreditPricingProps) {
  const entries = (FEATURE_ORDER as string[])
    .filter((key) => key in (pricing ?? {}))
    .map((key) => ({ key, cost: Number(pricing?.[key] ?? 0) }));

  if (!pricing || entries.length === 0) {
    return (
      <Card className="glass-panel border-gray-200/50 dark:border-white/10">
        <CardContent className="pt-6">
          <p className="text-sm text-gray-400">No credit pricing available.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="glass-panel border-purple-200/50 dark:border-purple-500/20">
      <CardHeader>
        <div className="flex items-center gap-2">
          <Coins className="h-5 w-5 text-purple-500" />
          <CardTitle className="text-base">{title}</CardTitle>
        </div>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className={cn('grid gap-2', compact ? 'grid-cols-1 sm:grid-cols-2' : 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3')}>
          {entries.map(({ key, cost }) => (
            <div
              key={key}
              className="flex items-center justify-between gap-3 rounded-xl border border-gray-100 dark:border-white/10 bg-white dark:bg-white/[0.02] px-3 py-2.5"
            >
              <span className="text-xs font-medium text-gray-700 dark:text-gray-300">
                {FEATURE_LABELS[key] ?? key}
              </span>
              <Badge
                variant={cost === 0 ? 'success' : 'primary'}
                size="sm"
                className="font-bold shrink-0"
              >
                {cost === 0 ? 'Free' : `${cost} credit${cost > 1 ? 's' : ''}`}
              </Badge>
            </div>
          ))}
        </div>
        <p className="mt-3 flex items-center gap-1.5 text-[11px] text-gray-400 dark:text-gray-500">
          <Info className="h-3.5 w-3.5" />
          Prices are set by the platform admin and apply to new credit usage. Free features consume no credits.
        </p>
      </CardContent>
    </Card>
  );
}