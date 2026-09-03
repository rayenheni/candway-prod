// ============================================================
// Courses List Page - Candway Platform
// ============================================================

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Progress } from '@/shared/components/ui/progress';
import { customToast } from '@/shared/components/ui/toast';
import { cn } from '@/utils/cn';
import {
  Search,
  Clock,
  BookOpen,
  Star,
  Award,
  Play,
  GraduationCap,
} from 'lucide-react';
import { publicService, type PublicCourse } from '@/services/public.service';
import { coursesService } from '@/services/courses.service';

interface Enrollment {
  id: number;
  course_id: number;
  course_title: string;
  progress: number;
  status: string;
}

const levelColors: Record<string, string> = {
  Beginner: 'success',
  Intermediate: 'warning',
  Advanced: 'danger',
};

function formatPrice(price: number): string {
  if (!price || price <= 0) return 'Free';
  return `${price} TND`;
}

export default function CoursesListPage() {
  const [courses, setCourses] = useState<PublicCourse[]>([]);
  const [enrollments, setEnrollments] = useState<Enrollment[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [enrolling, setEnrolling] = useState<number | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const [publicCourses, myEnrollments] = await Promise.all([
        publicService.getCourses(),
        coursesService.getMyEnrollments(),
      ]);
      setCourses(publicCourses);
      setEnrollments(myEnrollments);
    } catch (err) {
      console.warn('Failed to load courses', err);
      customToast({ type: 'error', title: 'Failed to load courses' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const enrollmentByCourse = (courseId: number): Enrollment | undefined =>
    enrollments.find(e => e.course_id === courseId);

  const enrolledCourses = courses.filter(c => enrollmentByCourse(c.id));
  const browseCourses = courses.filter(c => !enrollmentByCourse(c.id));

  const visibleBrowse = browseCourses.filter(
    c =>
      !search.trim() ||
      c.title.toLowerCase().includes(search.trim().toLowerCase()) ||
      (c.category || '').toLowerCase().includes(search.trim().toLowerCase()),
  );

  const handleEnroll = async (course: PublicCourse) => {
    setEnrolling(course.id);
    try {
      const res = await coursesService.enroll(String(course.id));
      customToast({
        type: 'success',
        title: 'Enrolled successfully',
        message: (res as any)?.payment_url ? 'Proceed to payment to activate your enrollment.' : undefined,
      });
      if ((res as any)?.payment_url) {
        window.open((res as any).payment_url, '_blank');
      }
      await loadData();
    } catch (err) {
      console.warn('Enroll failed', err);
      customToast({ type: 'error', title: 'Enrollment failed' });
    } finally {
      setEnrolling(null);
    }
  };

  const renderCourse = (course: PublicCourse, index: number) => {
    const enrollment = enrollmentByCourse(course.id);
    const isCompleted = enrollment?.progress === 100;
    return (
      <motion.div
        key={course.id}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: index * 0.05 }}
      >
        <Card hoverable className="cursor-pointer h-full">
          <div className="relative h-2 rounded-t-xl">
            {course.thumbnail_url ? (
              <img
                src={course.thumbnail_url}
                alt={course.title}
                className="h-24 w-full object-cover rounded-t-xl"
              />
            ) : (
              <div className={cn('h-24 w-full bg-gradient-to-r from-purple-500 to-indigo-500 flex items-center justify-center')}>
                <GraduationCap className="h-8 w-8 text-white" />
              </div>
            )}
          </div>
          <CardContent>
            <div className="flex items-center justify-between mb-3">
              <Badge variant={(levelColors[course.level] || 'success') as any} size="sm">
                {course.level || 'All Levels'}
              </Badge>
              {isCompleted && (
                <Badge variant="success" size="sm"><Award className="h-3 w-3 mr-1" />Completed</Badge>
              )}
            </div>
            <h3 className="text-base font-semibold text-gray-900 dark:text-white mb-1">{course.title}</h3>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-4 line-clamp-2">{course.description}</p>

            {enrollment ? (
              <>
                <Progress value={enrollment.progress} size="sm" color={isCompleted ? 'green' : 'blue'} />
                <div className="flex items-center justify-between mt-2">
                  <span className="text-xs text-gray-500 dark:text-gray-400">{enrollment.progress}% complete</span>
                  <Button variant={isCompleted ? 'outline' : 'primary'} size="xs">
                    {isCompleted ? 'Review' : 'Continue'}
                  </Button>
                </div>
              </>
            ) : (
              <>
                <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400 mb-4">
                  <span className="flex items-center gap-1"><BookOpen className="h-3 w-3" />{course.mentor_name || 'Candway Mentor'}</span>
                  <span className="flex items-center gap-1"><Star className="h-3 w-3 text-amber-400" fill="currentColor" />{course.rating ?? '—'}</span>
                  <span className="flex items-center gap-1"><Clock className="h-3 w-3" />{course.duration || 'Self-paced'}</span>
                </div>
                <div className="flex items-center gap-3">
                  <Button
                    variant="outline"
                    className="flex-1"
                    leftIcon={<Play className="h-4 w-4" />}
                    onClick={() => handleEnroll(course)}
                    disabled={enrolling === course.id}
                  >
                    {enrolling === course.id ? 'Enrolling...' : formatPrice(course.price)}
                  </Button>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </motion.div>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Courses</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Learn new skills and advance your career
          </p>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex-1">
          <Input
            placeholder="Search courses..."
            leftIcon={<Search className="h-4 w-4" />}
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
      </div>

      {loading && (
        <div className="py-16 text-center text-sm text-gray-500 dark:text-gray-400">
          Loading courses...
        </div>
      )}

      {!loading && enrolledCourses.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">My Learning</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {enrolledCourses.map((course, i) => renderCourse(course, i))}
          </div>
        </div>
      )}

      {!loading && (
        <div>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Browse Courses</h2>
          {visibleBrowse.length === 0 ? (
            <div className="py-16 text-center text-sm text-gray-500 dark:text-gray-400">
              {courses.length === 0
                ? 'No courses available yet.'
                : 'No courses match your search.'}
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {visibleBrowse.map((course, i) => renderCourse(course, i))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
