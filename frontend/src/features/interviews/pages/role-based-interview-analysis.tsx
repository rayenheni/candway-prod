// ============================================================
// Role-Based Interview Analysis Switcher
// Recruiters see recruiter view; candidates see candidate view.
// ============================================================

import { useAuth } from '@/contexts/auth-context';
import CandidateInterviewAnalysis from '@/features/candidate/pages/interview-analysis';
import RecruiterInterviewAnalysis from '@/features/recruiter/pages/recruiter-interview-analysis';

export default function RoleBasedInterviewAnalysis() {
  const { user, isLoading } = useAuth();
  // Guests (invited candidates who completed via /auth/interview-access) have
  // no auth-context user but own a valid interview token. They are treated as
  // candidates so they can view their own analysis.
  if (isLoading) return null;
  if (!user) return <CandidateInterviewAnalysis />;
  if (user.role === 'candidate') return <CandidateInterviewAnalysis />;
  return <RecruiterInterviewAnalysis />;
}
