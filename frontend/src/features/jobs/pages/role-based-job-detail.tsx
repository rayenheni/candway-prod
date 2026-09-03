import { useAuth } from '@/contexts/auth-context';
import CandidateJobDetailPage from '@/features/candidate/pages/candidate-job-detail';
import JobWizardPage from '@/features/recruiter/pages/job-wizard';

export default function RoleBasedJobDetail() {
  const { user } = useAuth();

  if (user?.role === 'candidate') {
    return <CandidateJobDetailPage />;
  }

  return <JobWizardPage />;
}
