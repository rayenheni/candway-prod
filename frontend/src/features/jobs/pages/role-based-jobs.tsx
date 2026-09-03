import { useAuth } from '@/contexts/auth-context';
import JobsListPage from '@/features/jobs/pages/jobs-list';
import CandidateJobsPage from '@/features/candidate/pages/candidate-jobs';

export default function RoleBasedJobs() {
  const { user } = useAuth();

  if (user?.role === 'candidate') {
    return <CandidateJobsPage />;
  }

  return <JobsListPage />;
}
