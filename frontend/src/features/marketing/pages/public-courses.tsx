import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import { motion } from 'framer-motion';
import { publicService, type PublicCourse } from '@/services/public.service';
import { BookOpen, Clock, Star, Search, GraduationCap } from 'lucide-react';
import { Input } from '@/shared/components/ui/input';
import { useLanguage } from '@/contexts/language-context';

export default function PublicCoursesPage() {
  const { t } = useLanguage();
  const [courses, setCourses] = useState<PublicCourse[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    document.title = t('marketing.courses.documentTitle');
    loadCourses();
  }, []);

  const loadCourses = (term?: string) => {
    setLoading(true);
    publicService
      .getCourses(term?.trim() ? { search: term.trim() } : undefined)
      .then(setCourses)
      .catch(() => setCourses([]))
      .finally(() => setLoading(false));
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    loadCourses(search);
  };

  return (
    <div>
      <div className="text-center mb-10">
        <h1 className="text-4xl md:text-5xl font-black tracking-tight text-gray-950 dark:text-white">
          {t('marketing.courses.title1')} <span className="bg-gradient-to-r from-purple-600 to-indigo-500 bg-clip-text text-transparent">{t('marketing.courses.title2')}</span>
        </h1>
        <p className="mt-4 text-lg text-gray-500 dark:text-slate-400 max-w-2xl mx-auto">
          {t('marketing.courses.subtitle')}
        </p>
      </div>

      <form onSubmit={handleSearch} className="max-w-xl mx-auto mb-10">
        <Input
          placeholder={t('marketing.courses.searchPlaceholder')}
          leftIcon={<Search className="h-4 w-4" />}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </form>

      {loading ? (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="rounded-3xl border border-purple-200/40 dark:border-white/10 bg-white/60 dark:bg-white/5 animate-pulse p-6">
              <div className="h-36 bg-gray-200 dark:bg-white/10 rounded-2xl mb-4" />
              <div className="h-5 w-2/3 bg-gray-200 dark:bg-white/10 rounded mb-3" />
              <div className="h-4 w-1/2 bg-gray-200 dark:bg-white/10 rounded" />
            </div>
          ))}
        </div>
      ) : courses.length === 0 ? (
        <div className="max-w-3xl mx-auto text-center py-16">
          <GraduationCap className="h-12 w-12 mx-auto text-gray-300 dark:text-white/20 mb-4" />
          <p className="text-lg text-gray-500 dark:text-slate-400">{t('marketing.courses.noCourses')}</p>
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {courses.map((course, idx) => (
            <motion.div
              key={course.id}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.35, delay: idx * 0.04 }}
            >
              <div className="group flex h-full flex-col overflow-hidden rounded-3xl border border-purple-200/50 dark:border-white/10 bg-white/70 dark:bg-white/5 backdrop-blur-sm transition-all hover:-translate-y-0.5 hover:shadow-xl hover:shadow-purple-500/10">
                {course.thumbnail_url ? (
                  <img src={course.thumbnail_url} alt={course.title} className="h-36 w-full object-cover" />
                ) : (
                  <div className="flex h-36 w-full items-center justify-center bg-gradient-to-tr from-purple-600/10 to-indigo-500/10">
                    <BookOpen className="h-10 w-10 text-purple-400" />
                  </div>
                )}
                <div className="flex flex-1 flex-col p-5">
                  <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-slate-400">
                    {course.category && (
                      <span className="rounded-full bg-purple-500/10 text-purple-600 dark:text-purple-300 px-2.5 py-0.5 font-semibold">
                        {course.category}
                      </span>
                    )}
                    {course.level && <span>{course.level}</span>}
                  </div>
                  <h2 className="mt-2 font-bold text-gray-900 dark:text-white">{course.title}</h2>
                  <p className="mt-1 text-sm text-gray-500 dark:text-slate-400 line-clamp-2">
                    {course.description}
                  </p>
                  <div className="mt-4 flex flex-wrap items-center gap-4 text-sm text-gray-500 dark:text-slate-400">
                    {course.mentor_name && <span className="flex items-center gap-1.5">{t('marketing.courses.mentor')}{course.mentor_name}</span>}
                    {course.duration && <span className="flex items-center gap-1.5"><Clock className="h-4 w-4" />{course.duration}</span>}
                    {course.rating > 0 && (
                      <span className="flex items-center gap-1"><Star className="h-4 w-4 fill-amber-400 text-amber-400" />{course.rating}</span>
                    )}
                  </div>
                  <div className="mt-auto pt-4 flex items-center justify-between">
                    <span className="font-bold text-gray-900 dark:text-white">
                      {course.price > 0 ? `${course.price} TND` : t('marketing.courses.free')}
                    </span>
                    <Link
                      to="/auth/register"
                      className="rounded-full bg-gradient-to-r from-purple-600 to-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-purple-500/30 hover:shadow-purple-500/50 transition-all"
                    >
                      {t('marketing.courses.enroll')}
                    </Link>
                  </div>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
