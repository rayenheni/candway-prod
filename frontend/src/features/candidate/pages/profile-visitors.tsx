// ============================================================
// Candidate Profile Visitors - Candway Tunisia
// ============================================================

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Avatar } from '@/shared/components/ui/avatar';
import { Clock, Eye, Users, Loader2, UserX } from 'lucide-react';
import { candidateService } from '@/services/candidate.service';
import { useLanguage } from '@/contexts/language-context';

interface Visitor {
  id: number;
  name: string;
  company: string;
  avatar: string | null;
  visited_at: string;
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

export default function ProfileVisitorsPage() {
  const { t } = useLanguage();
  const { data: visitors, isLoading, isError } = useQuery({
    queryKey: ['candidate-profile-visitors'],
    queryFn: () => candidateService.getProfileVisitors(),
  });

  const { data: dashboard } = useQuery({
    queryKey: ['candidate-dashboard-summary'],
    queryFn: () => candidateService.getDashboard().catch(() => null),
  });

  const totalViews = dashboard?.profile_views ?? (visitors ?? []).length;
  const uniqueRecruiters = new Set((visitors ?? []).map((v: Visitor) => v.id)).size;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">{t('profile.visitors.title')}</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{t('profile.visitors.subtitle')}</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
        <Card className="p-5">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-100 dark:bg-purple-500/20 text-purple-600">
              <Eye className="h-5 w-5" />
            </div>
            <div>
              <div className="text-2xl font-black text-gray-900 dark:text-white">{totalViews}</div>
              <div className="text-sm text-gray-500">Total Profile Views</div>
            </div>
          </div>
        </Card>
        <Card className="p-5">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-100 dark:bg-emerald-500/20 text-emerald-600">
              <Users className="h-5 w-5" />
            </div>
            <div>
              <div className="text-2xl font-black text-gray-900 dark:text-white">{uniqueRecruiters}</div>
              <div className="text-sm text-gray-500">Unique Recruiters</div>
            </div>
          </div>
        </Card>
      </div>

      <Card className="glass-panel border-purple-200/50">
        <CardHeader>
          <CardTitle>Recent Visitors</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex justify-center py-10 text-gray-400">
              <Loader2 className="h-6 w-6 animate-spin" />
            </div>
          ) : isError || !visitors || visitors.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center space-y-3">
              <div className="h-14 w-14 rounded-2xl bg-purple-50 dark:bg-purple-500/10 flex items-center justify-center">
                <UserX className="h-7 w-7 text-purple-400" />
              </div>
              <p className="text-sm font-semibold text-gray-700 dark:text-gray-300">No visitors yet</p>
              <p className="text-xs text-gray-500 dark:text-gray-400 max-w-xs">
                When recruiters view your profile, they will appear here.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {(visitors as Visitor[]).map(v => (
                <div key={v.id} className="flex items-center justify-between p-4 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100">
                  <div className="flex items-center gap-3">
                    <Avatar name={v.name} src={v.avatar ?? undefined} size="md" square className="ring-2 ring-purple-200/50" />
                    <div>
                      <div className="text-sm font-extrabold text-gray-900 dark:text-white">{v.name}</div>
                      <div className="text-xs text-purple-600 font-medium mt-0.5">{v.company}</div>
                    </div>
                  </div>
                  <div className="text-xs text-gray-500 flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {formatDate(v.visited_at)}
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
