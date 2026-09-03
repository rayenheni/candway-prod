// ============================================================
// Mentor Students Roster - Candway
// ============================================================

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Input } from '@/shared/components/ui/input';
import { Avatar } from '@/shared/components/ui/avatar';
import { Progress } from '@/shared/components/ui/progress';
import { customToast } from '@/shared/components/ui/toast';
import { Search, GraduationCap, Loader2 } from 'lucide-react';
import { mentorService, type MentorStudent } from '@/services/mentor.service';

export default function MentorStudentsPage() {
  const [students, setStudents] = useState<MentorStudent[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    mentorService
      .getStudents()
      .then(res => setStudents(res.students || []))
      .catch(() => {
        setStudents([]);
        customToast({ type: 'error', title: 'Failed to load mentees' });
      })
      .finally(() => setLoading(false));
  }, []);

  const filtered = students.filter(
    s =>
      !search.trim() ||
      s.name.toLowerCase().includes(search.toLowerCase()) ||
      (s.course_title || '').toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">My Mentees</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Track student progress across your active courses</p>
      </div>

      <Card className="glass-panel border-purple-200/50">
        <CardHeader>
          <div className="flex items-center justify-between w-full">
            <div>
              <CardTitle>Active Mentees ({students.length})</CardTitle>
              <CardDescription>Students enrolled in your courses</CardDescription>
            </div>
            <Input placeholder="Search mentees..." leftIcon={<Search className="h-4 w-4" />} value={search} onChange={(e) => setSearch(e.target.value)} wrapperClassName="w-64" />
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
            </div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-12">
              <GraduationCap className="mx-auto h-12 w-12 text-gray-300 dark:text-gray-600" />
              <p className="mt-3 text-sm text-gray-500 dark:text-gray-400">
                {students.length === 0 ? 'No students enrolled in your courses yet.' : 'No mentees match your search.'}
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {filtered.map(m => (
                <div key={`${m.student_id}-${m.course_id}`} className="flex flex-col sm:flex-row sm:items-center justify-between p-4 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10">
                  <div className="flex items-center gap-3 flex-1">
                    <Avatar name={m.name} size="md" className="ring-2 ring-purple-200/50" />
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-extrabold text-gray-900 dark:text-white">{m.name}</span>
                        <Badge variant={m.status === 'active' ? 'success' : 'default'} size="sm">{m.status}</Badge>
                      </div>
                      <p className="text-xs text-purple-600 font-medium mt-0.5">{m.course_title}</p>
                      <div className="flex items-center gap-3 mt-2">
                        <Progress value={m.progress} size="sm" color="purple" className="w-32" />
                        <span className="text-xs font-bold text-gray-700 dark:text-gray-300">{m.progress}% complete</span>
                        {m.enrolled_at && (
                          <span className="text-xs text-gray-400">Enrolled {new Date(m.enrolled_at).toLocaleDateString()}</span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
