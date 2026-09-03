import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { customToast } from '@/shared/components/ui/toast';
import { useLanguage } from '@/contexts/language-context';
import { publicService, type PublicCourse } from '@/services/public.service';
import { coursesService } from '@/services/courses.service';
import { cn } from '@/utils/cn';
import { ShoppingBag, Search, SlidersHorizontal, Star, Clock, BookOpen, Users, TrendingUp, Grid3X3, List, Loader2 } from 'lucide-react';

const CATEGORIES = ['All', 'Development', 'AI', 'Design', 'Marketing', 'Business', 'Data Science', 'Cloud'];

interface CourseItem {
  id: string;
  title: string;
  provider: string;
  rating: number;
  reviews: number;
  price: string;
  category: string;
  duration: string;
  students: number;
  trending: boolean;
}

function toCourseItem(c: PublicCourse): CourseItem {
  return {
    id: String(c.id),
    title: c.title,
    provider: c.mentor_name || 'Candway',
    rating: c.rating || 0,
    reviews: 0,
    price: c.price && c.price > 0 ? 'Paid' : 'Free',
    category: c.category || 'Other',
    duration: c.duration || '—',
    students: 0,
    trending: false,
  };
}

export default function MarketplacePage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [searchTerm, setSearchTerm] = useState('');
  const [activeCategory, setActiveCategory] = useState('All');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [courses, setCourses] = useState<CourseItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    publicService.getCourses()
      .then(res => {
        setCourses((Array.isArray(res) ? res : []).map(toCourseItem));
      })
      .catch(() => setCourses([]))
      .finally(() => setLoading(false));
  }, []);

  const filtered = courses.filter(item => {
    const matchesSearch = item.title.toLowerCase().includes(searchTerm.toLowerCase()) || item.provider.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCategory = activeCategory === 'All' || item.category === activeCategory;
    return matchesSearch && matchesCategory;
  });

  const handleEnroll = async (courseId: string, title: string) => {
    try {
      await coursesService.enroll(courseId);
      customToast({ type: 'success', title: t('marketplace.enrolled'), message: `${t('marketplace.enrolledMsg')} "${title}".` });
    } catch {
      customToast({ type: 'error', title: t('cand.interviews.error'), message: t('marketplace.enrollFailedMsg') });
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 text-violet-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white flex items-center gap-2">
          <ShoppingBag className="h-6 w-6 text-purple-500" />
          {t('marketplace.title')}
        </h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{t('marketplace.subtitle')}</p>
      </div>

      <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
        <div className="relative w-full sm:w-80">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input
            placeholder={t('marketplace.searchPlaceholder')}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            wrapperClassName="w-full"
            className="pl-9"
          />
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" leftIcon={<SlidersHorizontal className="h-3.5 w-3.5" />}>
            {t('common.filters')}
          </Button>
          <div className="flex items-center border border-purple-200/60 dark:border-purple-500/20 rounded-lg overflow-hidden">
            <button
              onClick={() => setViewMode('grid')}
              className={cn('p-2 transition-colors', viewMode === 'grid' ? 'bg-purple-100 dark:bg-purple-500/20 text-purple-700 dark:text-purple-300' : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300')}
            >
              <Grid3X3 className="h-4 w-4" />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={cn('p-2 transition-colors', viewMode === 'list' ? 'bg-purple-100 dark:bg-purple-500/20 text-purple-700 dark:text-purple-300' : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300')}
            >
              <List className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {CATEGORIES.map(cat => (
          <button
            key={cat}
            onClick={() => setActiveCategory(cat)}
            className={cn(
              'px-3.5 py-1.5 text-sm font-medium rounded-full border transition-all',
              activeCategory === cat
                ? 'bg-purple-600 text-white border-purple-600 shadow-sm shadow-purple-500/25'
                : 'bg-white/50 dark:bg-white/[0.03] text-gray-600 dark:text-gray-400 border-purple-200/50 dark:border-purple-500/20 hover:border-purple-400/60 dark:hover:border-purple-400/30'
            )}
          >
            {cat}
          </button>
        ))}
      </div>

      <motion.div
        key={viewMode + activeCategory + searchTerm}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className={cn(
          viewMode === 'grid'
            ? 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4'
            : 'space-y-3'
        )}
      >
        {filtered.map((item) => (
          <Card
            key={item.id}
            hoverable
            className={viewMode === 'list' ? 'p-4' : 'p-5'}
          >
            <CardContent className={cn('h-full flex flex-col', viewMode === 'list' && 'flex-row gap-4 items-center')}>
              <div className={cn('flex-1', viewMode === 'list' && 'flex items-center gap-4')}>
                {viewMode === 'list' ? (
                  <>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="text-base font-bold text-gray-900 dark:text-white truncate">{item.title}</h3>
                        {item.trending && <TrendingUp className="h-4 w-4 text-amber-500 shrink-0" />}
                      </div>
                      <p className="text-sm text-purple-600 dark:text-purple-400 font-medium">{item.provider}</p>
                      <div className="flex flex-wrap items-center gap-3 mt-2 text-xs text-gray-500">
                        <span className="flex items-center gap-1"><Star className="h-3 w-3 text-amber-500 fill-amber-500" />{item.rating > 0 ? `${item.rating} (${item.reviews})` : t('marketplace.notRated')}</span>
                        <span className="flex items-center gap-1"><Clock className="h-3 w-3 text-indigo-500" />{item.duration}</span>
                        <span className="flex items-center gap-1"><Users className="h-3 w-3 text-emerald-500" />{item.students > 0 ? item.students.toLocaleString() : '—'}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
            <Badge variant={item.price === 'Free' ? 'success' : 'primary'} size="sm">{item.price}</Badge>
            <Button variant="outline" size="xs" onClick={() => navigate('/courses')}>{t('marketplace.viewCourse')}</Button>
            <Button variant="primary" size="xs" onClick={() => handleEnroll(item.id, item.title)}>{t('marketplace.enroll')}</Button>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="flex items-start justify-between mb-3">
                      <Badge variant={item.price === 'Free' ? 'success' : 'primary'} size="sm">{item.price}</Badge>
                      {item.trending && <TrendingUp className="h-4 w-4 text-amber-500" />}
                    </div>
                    <h3 className="text-base font-bold text-gray-900 dark:text-white mb-1">{item.title}</h3>
                    <p className="text-sm text-purple-600 dark:text-purple-400 font-medium mb-3">{item.provider}</p>
                    <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500 mb-4">
                      <span className="flex items-center gap-1"><Star className="h-3 w-3 text-amber-500 fill-amber-500" />{item.rating > 0 ? `${item.rating} (${item.reviews})` : t('marketplace.notRated')}</span>
                      <span className="flex items-center gap-1"><Clock className="h-3 w-3 text-indigo-500" />{item.duration}</span>
                      <span className="flex items-center gap-1"><Users className="h-3 w-3 text-emerald-500" />{item.students > 0 ? item.students.toLocaleString() : '—'}</span>
                    </div>
                    <div className="mt-auto flex items-center gap-2 pt-3 border-t border-purple-100/60 dark:border-purple-500/10">
                      <Button variant="outline" size="sm" leftIcon={<BookOpen className="h-3.5 w-3.5" />} onClick={() => navigate('/courses')} className="flex-1">
                        {t('marketplace.viewCourse')}
                      </Button>
                      <Button variant="primary" size="sm" leftIcon={<ShoppingBag className="h-3.5 w-3.5" />} onClick={() => handleEnroll(item.id, item.title)} className="flex-1">
                        {t('marketplace.enroll')}
                      </Button>
                    </div>
                  </>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </motion.div>

      {filtered.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <Search className="h-10 w-10 text-gray-300 dark:text-gray-600 mb-3" />
          <p className="text-base font-medium text-gray-500 dark:text-gray-400">{t('marketplace.noCourses')}</p>
          <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">{t('marketplace.tryAdjusting')}</p>
        </div>
      )}
    </div>
  );
}
