// ============================================================
// Role-Based Interviews Switcher - Candway Platform
// ============================================================

import { useAuth } from '@/contexts/auth-context';
import InterviewsListPage from '@/features/interviews/pages/interviews-list';
import CandidateInterviewsPage from '@/features/candidate/pages/candidate-interviews';

export default function RoleBasedInterviews() {
  const { user } = useAuth();

  if (user?.role === 'candidate') {
    return <CandidateInterviewsPage />;
  }

  return <InterviewsListPage />;
}
