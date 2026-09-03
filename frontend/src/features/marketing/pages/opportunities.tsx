import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { publicService, type PublicOpportunity } from '@/services/public.service';
import { CalendarDays, ArrowUpRight, Sparkles } from 'lucide-react';
import { useLanguage } from '@/contexts/language-context';

export default function OpportunitiesPage() {
  const { t } = useLanguage();
  const [items, setItems] = useState<PublicOpportunity[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    document.title = t('marketing.opportunities.documentTitle');
    publicService
      .getOpportunities()
      .then(setItems)
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="text-center mb-12">
        <div className="inline-flex items-center gap-2 rounded-full bg-purple-500/10 border border-purple-500/20 px-4 py-1.5 text-xs font-semibold text-purple-600 dark:text-purple-300 mb-6">
          <Sparkles className="h-3.5 w-3.5" /> {t('marketing.opportunities.badge')}
        </div>
        <h1 className="text-4xl md:text-5xl font-black tracking-tight text-gray-950 dark:text-white">
          {t('marketing.opportunities.title1')} <span className="bg-gradient-to-r from-purple-600 to-indigo-500 bg-clip-text text-transparent">{t('marketing.opportunities.title2')}</span>
        </h1>
        <p className="mt-4 text-lg text-gray-500 dark:text-slate-400 max-w-2xl mx-auto">
          {t('marketing.opportunities.subtitle')}
        </p>
      </div>

      {loading ? (
        <div className="grid md:grid-cols-2 gap-6">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="rounded-3xl border border-purple-200/40 dark:border-white/10 bg-white/60 dark:bg-white/5 animate-pulse p-6">
              <div className="h-5 w-1/3 bg-gray-200 dark:bg-white/10 rounded mb-3" />
              <div className="h-4 w-2/3 bg-gray-200 dark:bg-white/10 rounded mb-2" />
              <div className="h-3 w-1/2 bg-gray-200 dark:bg-white/10 rounded" />
            </div>
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-16 text-gray-500 dark:text-slate-400">
          {t('marketing.opportunities.empty')}
        </div>
      ) : (
        <div className="grid md:grid-cols-2 gap-6">
          {items.map((item, idx) => (
            <motion.a
              key={item.id}
              href={item.link || '#'}
              target={item.link ? '_blank' : undefined}
              rel={item.link ? 'noopener noreferrer' : undefined}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: idx * 0.06 }}
              className="group block rounded-3xl border border-purple-200/50 dark:border-white/10 bg-white/70 dark:bg-white/5 backdrop-blur-sm p-6 transition-all hover:-translate-y-1 hover:shadow-xl hover:shadow-purple-500/10"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <span className="inline-block rounded-full bg-purple-500/10 text-purple-600 dark:text-purple-300 px-3 py-1 text-xs font-semibold mb-3">
                    {item.type}
                  </span>
                  <h2 className="text-lg font-bold text-gray-900 dark:text-white group-hover:text-purple-600 dark:group-hover:text-purple-400 transition-colors">
                    {item.title}
                  </h2>
                </div>
                {item.link && (
                  <span className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-purple-300/50 dark:border-white/15 text-purple-600 dark:text-purple-300 transition-all group-hover:bg-purple-600 group-hover:text-white">
                    <ArrowUpRight className="h-4 w-4" />
                  </span>
                )}
              </div>
              <p className="mt-3 text-sm text-gray-500 dark:text-slate-400 line-clamp-3">{item.description}</p>
              <div className="mt-4 flex items-center gap-1.5 text-xs text-gray-400 dark:text-slate-500">
                <CalendarDays className="h-3.5 w-3.5" /> {item.date}
              </div>
            </motion.a>
          ))}
        </div>
      )}
    </div>
  );
}
