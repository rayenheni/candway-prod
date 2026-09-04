// ============================================================
// Role-Based Dashboard Switcher - Candway Platform
// ============================================================

import { useEffect } from 'react';
import { useAuth } from '@/contexts/auth-context';
import { getCrossDomainDashboardRedirect } from '@/utils/domain-routing';
import RecruiterDashboard from '@/features/dashboard/pages/recruiter-dashboard';
import CandidateDashboard from '@/features/dashboard/pages/candidate-dashboard';
import AdminDashboard from '@/features/admin/pages/admin-dashboard';
import MentorDashboard from '@/features/dashboard/pages/mentor-dashboard';
import OrgDashboard from '@/features/org/pages/org-dashboard';

export default function RoleBasedDashboard() {
  const { user } = useAuth();
  const role = user?.role || 'recruiter';

  // Route each role to its domain after authentication. Candidates belong on
  // candway.com; recruiters/admins/company/mentors belong on app.candway.com.
  const crossDomainUrl = getCrossDomainDashboardRedirect(role);
  useEffect(() => {
    if (crossDomainUrl) {
      window.location.href = crossDomainUrl;
    }
  }, [crossDomainUrl]);

  if (crossDomainUrl) {
    return null;
  }

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
