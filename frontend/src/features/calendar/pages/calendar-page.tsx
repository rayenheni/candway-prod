import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { cn } from '@/utils/cn';
import apiClient from '@/lib/api-client';
import {
  Plus, ChevronLeft, ChevronRight, Calendar as CalendarIcon, Clock, Loader2,
} from 'lucide-react';

const daysOfWeek = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

const typeColors: Record<string, string> = {
  phone: 'bg-blue-500',
  video: 'bg-purple-500',
  onsite: 'bg-amber-500',
  technical: 'bg-emerald-500',
  behavioral: 'bg-pink-500',
  panel: 'bg-red-500',
};

function getDaysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate();
}
function getFirstDayOfMonth(year: number, month: number) {
  return new Date(year, month, 1).getDay();
}

interface InterviewEvent {
  id: number;
  candidate_name: string;
  job_title: string;
  scheduled_time: string;
  duration_minutes: number;
  type: string;
  meeting_link: string | null;
  status: string;
}

export default function CalendarPage() {
  const [interviews, setInterviews] = useState<InterviewEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const now = new Date();
  const [currentDate, setCurrentDate] = useState(new Date(now.getFullYear(), now.getMonth(), 1));

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();
  const daysInMonth = getDaysInMonth(year, month);
  const firstDay = getFirstDayOfMonth(year, month);
  const today = now.getDate();

  useEffect(() => {
    setLoading(true);
    apiClient.get<InterviewEvent[]>('/recruiter/interviews/upcoming', { limit: 100 })
      .then(setInterviews)
      .catch(() => setInterviews([]))
      .finally(() => setLoading(false));
  }, []);

  const prevMonth = () => setCurrentDate(new Date(year, month - 1, 1));
  const nextMonth = () => setCurrentDate(new Date(year, month + 1, 1));
  const goToday = () => setCurrentDate(new Date(now.getFullYear(), now.getMonth(), 1));

  const monthNames = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

  const eventsByDay: Record<number, InterviewEvent[]> = {};
  interviews.forEach(iv => {
    const d = new Date(iv.scheduled_time);
    if (d.getMonth() === month && d.getFullYear() === year) {
      const day = d.getDate();
      if (!eventsByDay[day]) eventsByDay[day] = [];
      eventsByDay[day].push(iv);
    }
  });

  const todayEvents = interviews.filter(iv => {
    const d = new Date(iv.scheduled_time);
    return d.toDateString() === now.toDateString();
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Calendar</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Manage your interviews and events</p>
        </div>
        <Button variant="primary" leftIcon={<Plus className="h-4 w-4" />}>New Event</Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <Card className="lg:col-span-3">
          <CardHeader>
            <div className="flex items-center justify-between w-full">
              <div className="flex items-center gap-3">
                <Button variant="ghost" size="sm" onClick={prevMonth}><ChevronLeft className="h-4 w-4" /></Button>
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">{monthNames[month]} {year}</h2>
                <Button variant="ghost" size="sm" onClick={nextMonth}><ChevronRight className="h-4 w-4" /></Button>
              </div>
              <Button variant="outline" size="sm" onClick={goToday}>Today</Button>
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex justify-center py-12"><Loader2 className="h-6 w-6 animate-spin text-purple-600" /></div>
            ) : (
              <div className="grid grid-cols-7 gap-px bg-gray-200 dark:bg-white/[0.06] rounded-xl overflow-hidden">
                {daysOfWeek.map((day) => (
                  <div key={day} className="bg-gray-50 dark:bg-white/[0.02] px-2 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-400">{day}</div>
                ))}
                {Array.from({ length: 42 }).map((_, i) => {
                  const dayNum = i - firstDay + 1;
                  const isValid = dayNum > 0 && dayNum <= daysInMonth;
                  const isToday = dayNum === today && month === now.getMonth() && year === now.getFullYear();
                  const dayEvents = eventsByDay[dayNum] || [];

                  return (
                    <div key={i} className={cn('bg-white dark:bg-[#0B1120] min-h-[80px] p-2 cursor-pointer hover:bg-gray-50 dark:hover:bg-white/[0.02] transition-colors', !isValid && 'opacity-30')}>
                      {isValid && (
                        <>
                          <div className={cn('inline-flex items-center justify-center h-7 w-7 rounded-full text-sm font-medium', isToday ? 'bg-blue-600 text-white' : 'text-gray-700 dark:text-gray-300')}>
                            {dayNum}
                          </div>
                          {dayEvents.length > 0 && (
                            <div className="mt-1 space-y-0.5">
                              {dayEvents.slice(0, 2).map(ev => (
                                <div key={ev.id} className="text-[10px] bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400 rounded px-1 py-0.5 truncate">
                                  {ev.candidate_name}
                                </div>
                              ))}
                              {dayEvents.length > 2 && (
                                <div className="text-[10px] text-gray-400 px-1">+{dayEvents.length - 2} more</div>
                              )}
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="h-fit">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><CalendarIcon className="h-4 w-4" /> Today's Schedule</CardTitle>
          </CardHeader>
          <CardContent>
            {todayEvents.length === 0 ? (
              <p className="text-sm text-gray-500 py-4 text-center">No interviews scheduled for today.</p>
            ) : (
              <div className="space-y-3">
                {todayEvents.map((event) => (
                  <div key={event.id} className="flex items-start gap-3 p-3 rounded-xl bg-gray-50 dark:bg-white/[0.02]">
                    <div className={cn('w-1 h-full rounded-full shrink-0 min-h-[40px]', typeColors[event.type] || 'bg-gray-400')} />
                    <div>
                      <div className="text-sm font-medium text-gray-900 dark:text-white">{event.candidate_name}</div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">{event.job_title}</div>
                      <div className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400 mt-1">
                        <Clock className="h-3 w-3" />
                        {new Date(event.scheduled_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} · {event.duration_minutes}min
                      </div>
                      <Badge variant="primary" size="sm" className="mt-1">{event.type}</Badge>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
