import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Progress } from '@/shared/components/ui/progress';
import { cn } from '@/utils/cn';
import {
  Crosshair, Mic, Zap, Trophy, Handshake, Star,
  BookOpen, Briefcase, MessageSquare, Sparkles, Bird, Globe,
  Loader2,
} from 'lucide-react';
import { achievementsService, type Achievement } from '@/services/achievements.service';

const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  crosshair: Crosshair,
  mic: Mic,
  zap: Zap,
  trophy: Trophy,
  handshake: Handshake,
  star: Star,
  'book-open': BookOpen,
  briefcase: Briefcase,
  'message-square': MessageSquare,
  sparkles: Sparkles,
  bird: Bird,
  globe: Globe,
};

const categories = ['All', 'Applications', 'Interviews', 'Learning', 'Skills', 'Social', 'Profile', 'Engagement', 'Performance'];

export default function AchievementsPage() {
  const [achievements, setAchievements] = useState<Achievement[]>([]);
  const [stats, setStats] = useState<{ total: number; unlocked: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeCategory, setActiveCategory] = useState('All');

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [achRes, statsRes] = await Promise.all([
        achievementsService.list(),
        achievementsService.stats(),
      ]);
      const items = Array.isArray(achRes.data) ? achRes.data : [];
      setAchievements(items);
      setStats(statsRes);
    } catch {
      setAchievements([]);
      setStats(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const filtered = activeCategory === 'All'
    ? achievements
    : achievements.filter(a => a.category === activeCategory);

  const unlockedCount = stats?.unlocked ?? 0;
  const totalCount = stats?.total ?? achievements.length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Achievements</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Track your progress and unlock badges
        </p>
      </div>

      <Card variant="glass" className="border-blue-200/50 dark:border-blue-500/20">
        <CardContent>
          <div className="flex items-center justify-between">
            <div>
              <div className="text-3xl font-bold text-gray-900 dark:text-white">{unlockedCount}/{totalCount}</div>
              <div className="text-sm text-gray-500 dark:text-gray-400">Achievements Unlocked</div>
            </div>
            <div className="text-right">
              <div className="text-3xl font-bold text-blue-600 dark:text-blue-400">{unlockedCount * 100}</div>
              <div className="text-sm text-gray-500 dark:text-gray-400">Points Earned</div>
            </div>
          </div>
          <Progress value={unlockedCount} max={totalCount} size="md" color="blue" className="mt-4" />
        </CardContent>
      </Card>

      <div className="flex flex-wrap gap-2">
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setActiveCategory(cat)}
            className={cn(
              'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
              activeCategory === cat
                ? 'bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-300'
                : 'text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-white/5'
            )}
          >
            {cat}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((achievement, i) => {
            const IconComponent = ICON_MAP[achievement.icon_slug];
            return (
              <motion.div
                key={achievement.id}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.3, delay: i * 0.03 }}
              >
                <Card className={cn(
                  'h-full transition-all',
                  achievement.unlocked ? 'border-blue-200 dark:border-blue-500/20' : 'opacity-75'
                )}>
                  <CardContent>
                    <div className="flex items-start gap-4">
                      <div className={cn(
                        'flex h-14 w-14 items-center justify-center rounded-2xl',
                        achievement.unlocked ? 'bg-blue-50 dark:bg-blue-500/10' : 'bg-gray-100 dark:bg-white/[0.04] grayscale'
                      )}>
                        {IconComponent ? (
                          <IconComponent className={cn(
                            'w-7 h-7',
                            achievement.unlocked ? 'text-blue-600 dark:text-blue-400' : 'text-gray-400'
                          )} />
                        ) : (
                          <Trophy className={cn(
                            'w-7 h-7',
                            achievement.unlocked ? 'text-blue-600 dark:text-blue-400' : 'text-gray-400'
                          )} />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <h3 className="text-sm font-semibold text-gray-900 dark:text-white">{achievement.name}</h3>
                          {achievement.unlocked && <Badge variant="success" size="sm">Unlocked</Badge>}
                        </div>
                        {achievement.description && (
                          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{achievement.description}</p>
                        )}

                        {!achievement.unlocked && (
                          <div className="mt-3">
                            <div className="flex items-center justify-between text-xs mb-1">
                              <span className="text-gray-500 dark:text-gray-400">Progress</span>
                              <span className="font-medium text-gray-700 dark:text-gray-300">
                                {achievement.progress_current}/{achievement.progress_max}
                              </span>
                            </div>
                            <Progress
                              value={achievement.progress_current}
                              max={achievement.progress_max}
                              size="sm"
                              color="blue"
                            />
                          </div>
                        )}

                        {achievement.unlocked && achievement.unlocked_at && (
                          <p className="text-xs text-gray-400 mt-2">Unlocked {new Date(achievement.unlocked_at).toLocaleDateString()}</p>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}
