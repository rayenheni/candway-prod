// ============================================================
// Domain-aware routing between the candidate domain
// (candway.com) and the recruiter/employer/admin domain
// (app.candway.com).
//
// The platform is a single SPA served from both hosts, with a
// relative `/api/v1` API base so each host talks to its own
// same-origin backend and uses host-only auth cookies. Sessions
// are intentionally NOT shared across hosts. After authentication,
// the caller routes the user to the domain their role belongs on.
// ============================================================

export type DomainFamily = 'candidate' | 'app';

export function isKnownProductionDomain(): boolean {
  if (typeof window === 'undefined') return false;
  const hostname = window.location.hostname;
  return (
    hostname === 'app.candway.com' ||
    hostname === 'candway.com' ||
    hostname === 'www.candway.com'
  );
}

export function getCurrentDomainFamily(): DomainFamily {
  const hostname = typeof window !== 'undefined' ? window.location.hostname : '';
  if (hostname === 'app.candway.com') return 'app';
  // candway.com, www.candway.com and unknown/dev hosts default to candidate.
  return 'candidate';
}

export function getRoleDomainFamily(role: string | undefined): DomainFamily {
  // Only candidates live on the candidate domain. Recruiters, admins,
  // company admins and mentors belong on the app (recruiter/employer) domain.
  if (role === 'candidate') return 'candidate';
  return 'app';
}

export function getDashboardUrlForFamily(family: DomainFamily): string {
  return family === 'candidate'
    ? 'https://candway.com/dashboard'
    : 'https://app.candway.com/dashboard';
}

/**
 * Returns the cross-domain dashboard URL the user should be redirected to, or
 * null when they are already on the correct domain (or the current host is not
 * a known production domain, e.g. localhost).
 */
export function getCrossDomainDashboardRedirect(role: string | undefined): string | null {
  if (typeof window === 'undefined') return null;
  if (!isKnownProductionDomain()) return null;
  const currentFamily = getCurrentDomainFamily();
  const roleFamily = getRoleDomainFamily(role);
  if (currentFamily === roleFamily) return null;
  return getDashboardUrlForFamily(roleFamily);
}
