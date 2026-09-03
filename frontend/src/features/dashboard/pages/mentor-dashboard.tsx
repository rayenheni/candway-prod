// ============================================================
// Mentor Dashboard - Candway Platform
// ============================================================

import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import { motion } from 'framer-motion';
import { useAuth } from '@/contexts/auth-context';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Avatar } from '@/shared/components/ui/avatar';
import { cn } from '@/utils/cn';
import {
  Users,
  Star,
  GraduationCap,
  Wallet,
  ArrowUpRight,
  ChevronRight,
  FileText,
  Loader2,
  BookOpen,
} from 'lucide-react';
import { mentorService, type MentorStats, type MentorStudent } from '@/services/mentor.service';

export default function MentorDashboard() {
  const { user } = useAuth();
  const [stats, setStats] = useState<MentorStats | null>(null);
  const [students, setStudents] = useState<MentorStudent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      mentorService.getStats().catch(() => null),
      mentorService.getStudents().catch(() => ({ students: [], total: 0 })),
    ])
      .then(([s, st]) => {
        setStats(s);
        setStudents(st?.students ?? []);
      })
      .finally(() => setLoading(false));
  }, []);

  const recentStudents = students.slice(0, 5);

  const statCards = [
    {
      label: 'Active Students',
      value: stats?.total_students ?? 0,
      icon: Users,
      color: 'bg-violet-50 text-violet-600 dark:bg-violet-500/10 dark:text-violet-400',
      to: '/mentor/students',
    },
    {
      label: 'Courses',
      value: stats?.total_courses ?? 0,
      icon: BookOpen,
      color: 'bg-cyan-50 text-cyan-600 dark:bg-cyan-500/10 dark:text-cyan-400',
      to: '/mentor/students',
    },
    {
      label: 'Average Rating',
      value: stats?.average_rating ? Number(stats.average_rating).toFixed(1) : '—',
      icon: Star,
      color: 'bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400',
      to: '/mentor/students',
    },
    {
      label: 'Total Revenue',
      value: stats?.revenue != null ? `${Number(stats.revenue).toFixed(0)} TND` : '—',
      icon: Wallet,
      color: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400',
      to: '/mentor/wallet',
    },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 text-violet-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Badge variant="info" size="sm" className="bg-violet-100 text-violet-800 dark:bg-violet-500/20 dark:text-violet-300">
              Mentor Workspace
            </Badge>
          </div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
            Welcome, {user?.firstName || user?.email || 'Mentor'} 👋
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Manage your students, courses, and earnings.
          </p>
        </div>
        <div className="flex gap-2">
          <Link to="/mentor/students">
            <Button variant="outline" leftIcon={<GraduationCap className="h-4 w-4" />}>
              My Students
            </Button>
          </Link>
          <Link to="/mentor/wallet">
            <Button variant="primary" className="bg-violet-600 hover:bg-violet-700" leftIcon={<Wallet className="h-4 w-4" />}>
              Earnings
            </Button>
          </Link>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((stat, i) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: i * 0.05 }}
          >
            <Link to={stat.to}>
              <Card hoverable className="border-violet-100/50 dark:border-violet-500/10">
                <CardContent>
                  <div className="flex items-center justify-between">
                    <div className={cn('flex h-10 w-10 items-center justify-center rounded-xl', stat.color)}>
                      <stat.icon className="h-5 w-5" />
                    </div>
                    <ArrowUpRight className="h-4 w-4 text-gray-300 dark:text-gray-600" />
                  </div>
                  <div className="mt-4">
                    <div className="text-2xl font-bold text-gray-900 dark:text-white">{stat.value}</div>
                    <div className="text-sm text-gray-500 dark:text-gray-400">{stat.label}</div>
                  </div>
                </CardContent>
              </Card>
            </Link>
          </motion.div>
        ))}
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Students */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.2 }}
          className="lg:col-span-2"
        >
          <Card className="h-full">
            <CardHeader
              action={
                <Link to="/mentor/students">
                  <Button variant="ghost" size="sm" rightIcon={<ChevronRight className="h-4 w-4" />}>
                    View All
                  </Button>
                </Link>
              }
            >
              <CardTitle>Recent Students</CardTitle>
              <CardDescription>Enrolled students across your courses</CardDescription>
            </CardHeader>
            <CardContent>
              {recentStudents.length === 0 ? (
                <p className="py-10 text-center text-sm text-gray-500 dark:text-gray-400">
                  No students yet. Students appear here once they enroll in your courses.
                </p>
              ) : (
                <div className="space-y-3">
                  {recentStudents.map((student) => (
                    <div
                      key={student.student_id}
                      className="flex items-center justify-between p-4 rounded-xl border border-gray-100 dark:border-white/[0.06] hover:border-gray-300 dark:hover:border-white/10 transition-all"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <Avatar name={student.name} size="md" />
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-semibold text-gray-900 dark:text-white truncate">{student.name}</span>
                            <Badge variant={student.status === 'active' ? 'success' : 'default'} size="sm">
                              {student.status}
                            </Badge>
                          </div>
                          <p className="text-xs text-gray-600 dark:text-gray-300 font-medium mt-0.5 truncate">{student.course_title}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <div className="w-24">
                          <div className="h-1.5 bg-gray-100 dark:bg-white/10 rounded-full overflow-hidden">
                            <div className="h-full rounded-full bg-violet-500" style={{ width: `${Math.min(100, student.progress)}%` }} />
                          </div>
                          <p className="text-[11px] text-gray-400 mt-1 text-right">{student.progress}%</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* Reviews & Earnings */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.3 }}
        >
          <Card className="h-full">
            <CardHeader
              action={
                <Link to="/mentor/wallet">
                  <Badge variant="primary" size="sm">Wallet</Badge>
                </Link>
              }
            >
              <CardTitle>Earnings Overview</CardTitle>
              <CardDescription>Revenue from your published courses</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="rounded-xl border border-violet-100 dark:border-violet-500/20 bg-violet-50/60 dark:bg-violet-500/10 p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-600 dark:text-gray-300">Total Revenue</span>
                    <span className="text-2xl font-black text-gray-900 dark:text-white">
                      {stats?.revenue != null ? `${Number(stats.revenue).toFixed(0)} TND` : '—'}
                    </span>
                  </div>
                  <div className="mt-3 flex items-center justify-between">
                    <span className="text-sm text-gray-600 dark:text-gray-300">Students</span>
                    <span className="text-lg font-bold text-gray-900 dark:text-white">{stats?.total_students ?? 0}</span>
                  </div>
                  <div className="mt-2 flex items-center justify-between">
                    <span className="text-sm text-gray-600 dark:text-gray-300">Average Rating</span>
                    <span className="text-lg font-bold text-gray-900 dark:text-white">
                      {stats?.average_rating ? Number(stats.average_rating).toFixed(1) : '—'}
                    </span>
                  </div>
                </div>

                <Link to="/mentor/wallet">
                  <Button variant="outline" className="w-full" rightIcon={<ChevronRight className="h-4 w-4" />}>
                    View Earnings Detail
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* Resources Banner */}
      <Card variant="glass" className="border-violet-200/60 dark:border-violet-500/20 bg-gradient-to-r from-violet-50/50 to-cyan-50/50 dark:from-violet-950/20 dark:to-cyan-950/20">
        <CardContent>
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-600 text-white shadow-lg shadow-violet-500/30 shrink-0">
                <FileText className="h-6 w-6" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                  Review CVs and Code
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-0.5">
                  Provide AI-assisted feedback on your mentees' CVs and coding submissions.
                </p>
              </div>
            </div>
            <Link to="/mentor/reviews">
              <Button variant="primary" size="sm" className="bg-violet-600 hover:bg-violet-700">
                Go to Reviews
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
