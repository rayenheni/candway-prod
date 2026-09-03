import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Progress } from '@/shared/components/ui/progress';
import { cn } from '@/utils/cn';
import {
  TrendingUp, Award, Target, Zap, Loader2,
} from 'lucide-react';
import { skillProgressService, type SkillCategory } from '@/services/skill-progress.service';

function getLevelLabel(level: number) {
  if (level >= 90) return { label: 'Expert', color: 'success' };
  if (level >= 75) return { label: 'Advanced', color: 'primary' };
  if (level >= 60) return { label: 'Intermediate', color: 'warning' };
  return { label: 'Beginner', color: 'default' };
}

export default function SkillProgressPage() {
  const [categories, setCategories] = useState<SkillCategory[]>([]);
  const [stats, setStats] = useState({ total_skills: 0, avg_level: 0, verified_count: 0, improving_count: 0 });
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await skillProgressService.get();
      setCategories(res.categories ?? []);
      setStats(res.stats ?? { total_skills: 0, avg_level: 0, verified_count: 0, improving_count: 0 });
    } catch {
      setCategories([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const statCards = [
    { label: 'Total Skills', value: stats.total_skills, icon: Target, color: 'bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400' },
    { label: 'Avg Level', value: `${stats.avg_level}%`, icon: TrendingUp, color: 'bg-purple-50 text-purple-600 dark:bg-purple-500/10 dark:text-purple-400' },
    { label: 'Verified', value: stats.verified_count, icon: Award, color: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400' },
    { label: 'Improving', value: stats.improving_count, icon: Zap, color: 'bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400' },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Skill Progress</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Track your skill development and proficiency levels
        </p>
      </div>

       {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
        </div>
      ) : categories.length === 0 ? (
        <Card className="py-12">
          <CardContent className="flex flex-col items-center text-center">
            <Award className="w-16 h-16 text-gray-300 dark:text-gray-600 mb-4" />
            <h2 className="text-xl font-semibold text-gray-700 dark:text-gray-300">No skills yet</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-2 max-w-md">
              Skills are extracted from your CV and profile. Upload your CV or update your profile to see your skills here.
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
            {statCards.map((stat, i) => (
              <motion.div key={stat.label} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: i * 0.05 }}>
                <Card>
                  <CardContent>
                    <div className="flex items-center gap-3">
                      <div className={cn('flex h-10 w-10 items-center justify-center rounded-xl', stat.color)}>
                        <stat.icon className="h-5 w-5" />
                      </div>
                      <div>
                        <div className="text-2xl font-bold text-gray-900 dark:text-white">{stat.value}</div>
                        <div className="text-sm text-gray-500 dark:text-gray-400">{stat.label}</div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {categories.map((category, ci) => (
              <motion.div
                key={category.name}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: ci * 0.1 }}
              >
                <Card className="h-full">
                  <CardHeader>
                    <CardTitle>{category.name}</CardTitle>
                    <CardDescription>{category.skills.length} skills</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {category.skills.map((skill) => {
                        const levelInfo = getLevelLabel(skill.level);
                        return (
                          <div key={skill.name} className="p-3 rounded-xl bg-gray-50 dark:bg-white/[0.02]">
                            <div className="flex items-center justify-between mb-2">
                              <div className="flex items-center gap-2">
                                <span className="text-sm font-medium text-gray-900 dark:text-white">{skill.name}</span>
                                {skill.verified && <Badge variant="success" size="sm">Verified</Badge>}
                              </div>
                              <div className="flex items-center gap-2">
                                <span className={cn(
                                  'text-xs font-medium px-2 py-0.5 rounded-full',
                                  levelInfo.color === 'success' ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400' :
                                  levelInfo.color === 'primary' ? 'bg-blue-50 text-blue-700 dark:bg-blue-500/10 dark:text-blue-400' :
                                  levelInfo.color === 'warning' ? 'bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400' :
                                  'bg-gray-100 text-gray-700 dark:bg-white/[0.06] dark:text-gray-400'
                                )}>
                                  {levelInfo.label}
                                </span>
                                <span className="text-sm font-bold text-gray-700 dark:text-gray-300">{skill.level}%</span>
                              </div>
                            </div>
                            <div className="flex items-center gap-2">
                              <Progress
                                value={skill.level}
                                size="sm"
                                color={skill.level >= 90 ? 'green' : skill.level >= 75 ? 'blue' : skill.level >= 60 ? 'amber' : 'default'}
                              />
                              <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400 shrink-0">
                                <TrendingUp className="h-3 w-3 inline mr-0.5" />
                                {skill.trend}
                              </span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
