// ============================================================
// Role-Based Dashboard Switcher - Candway Platform
// ============================================================

import { useAuth } from '@/contexts/auth-context';
import RecruiterDashboard from '@/features/dashboard/pages/recruiter-dashboard';
import CandidateDashboard from '@/features/dashboard/pages/candidate-dashboard';
import AdminDashboard from '@/features/admin/pages/admin-dashboard';
import MentorDashboard from '@/features/dashboard/pages/mentor-dashboard';
import OrgDashboard from '@/features/org/pages/org-dashboard';

export default function RoleBasedDashboard() {
  const { user } = useAuth();
  const role = user?.role || 'recruiter';

  switch (role) {
    case 'candidate':
      return <CandidateDashboard />;
    case 'admin':
      return <AdminDashboard />;
    case 'mentor':
      return <MentorDashboard />;
    case 'company':
      return <OrgDashboard />;
    case 'recruiter':
    default:
      return <RecruiterDashboard />;
  }
}
