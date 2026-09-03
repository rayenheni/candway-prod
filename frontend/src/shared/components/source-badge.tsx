import { cn } from '@/utils/cn';
import { useLanguage } from '@/contexts/language-context';

const SOURCE_STYLES: Record<string, string> = {
  direct: 'bg-gray-100 text-gray-600 dark:bg-white/10 dark:text-gray-400',
  linkedin: 'bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400',
  social_media: 'bg-sky-50 text-sky-600 dark:bg-sky-500/10 dark:text-sky-400',
  website: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400',
  referral: 'bg-violet-50 text-violet-600 dark:bg-violet-500/10 dark:text-violet-400',
  other: 'bg-gray-50 text-gray-600 dark:bg-white/5 dark:text-gray-500',
  campaign: 'bg-indigo-50 text-indigo-600 dark:bg-indigo-500/10 dark:text-indigo-400',
  import: 'bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400',
  upload: 'bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400',
  ats: 'bg-purple-50 text-purple-600 dark:bg-purple-500/10 dark:text-purple-400',
  manual: 'bg-gray-100 text-gray-600 dark:bg-white/10 dark:text-gray-400',
};

const LABEL_KEY: Record<string, string> = {
  direct: 'sources.direct',
  linkedin: 'sources.linkedin',
  social_media: 'sources.socialMedia',
  website: 'sources.website',
  referral: 'sources.referral',
  other: 'sources.other',
  campaign: 'sources.campaign',
  import: 'sources.import',
  upload: 'sources.upload',
  ats: 'sources.ats',
  manual: 'sources.manual',
};

export function SourceBadge({ source }: { source?: string | null }) {
  const { t } = useLanguage();
  const key = (source || 'direct').toLowerCase();
  const style = SOURCE_STYLES[key] || SOURCE_STYLES.direct;
  const labelKey = LABEL_KEY[key] || 'sources.unknown';
  return (
    <span className={cn('inline-flex px-2 py-0.5 rounded-full text-[11px] font-semibold', style)}>
      {t(labelKey)}
    </span>
  );
}
