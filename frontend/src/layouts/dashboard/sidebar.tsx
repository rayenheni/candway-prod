// ============================================================
// Dashboard Sidebar - Purple Glassmorphism - Candway Platform
// ============================================================

import { useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@/utils/cn';
import { useAuth } from '@/contexts/auth-context';
import { useSidebar } from '@/contexts/sidebar-context';
import { useLanguage } from '@/contexts/language-context';
import { customToast } from '@/shared/components/ui/toast';
import type { UserRole } from '@/types';
import {
  LayoutDashboard,
  Briefcase,
  Users,
  Calendar,
  BarChart3,
  MessageSquare,
  Settings,
  ChevronLeft,
  ChevronRight,
  FileText,
  GitBranch,
  Award,
  BookOpen,
  Target,
  Shield,
  Activity,
  Zap,
  Star,
  Wallet,
  Trophy,
  Mail,
  Sparkles,
  FolderTree,
  Beaker,
  CreditCard,
  Receipt,
  Megaphone,
  Headphones,
  TrendingUp,
  ListChecks,
  Gauge,
  Terminal,
  Volume2,
  FileCheck2,
  X,
  type LucideIcon,
} from 'lucide-react';

interface NavItem {
  label: string;
  icon: LucideIcon;
  href: string;
  badge?: string | number;
  highlight?: boolean;
}

interface NavSection {
  title?: string;
  items: NavItem[];
}

// Nav labels use translation keys via t()
const recruiterNav: NavSection[] = [
  {
    items: [
      { label: 'nav.dashboard', icon: LayoutDashboard, href: '/dashboard' },
      { label: 'nav.pipeline', icon: GitBranch, href: '/pipeline', badge: 'nav.badge.active' },
    ],
  },
  {
    title: 'nav.section.recruitment',
    items: [
      { label: 'nav.jobs', icon: Briefcase, href: '/jobs' },
      { label: 'nav.campaigns', icon: Mail, href: '/campaigns' },
      { label: 'nav.candidates', icon: Users, href: '/candidates' },
      { label: 'nav.recruiter_applications', icon: FileText, href: '/recruiter/applications' },
      { label: 'nav.interviews', icon: Calendar, href: '/interviews' },
    ],
  },
  {
    title: 'nav.section.intelligence',
    items: [
      { label: 'nav.analytics', icon: BarChart3, href: '/analytics' },
      { label: 'nav.reports', icon: Target, href: '/reports' },
      { label: 'nav.rubrics', icon: Award, href: '/rubrics' },
      { label: 'nav.email_templates', icon: FileText, href: '/email-templates' },
    ],
  },
  {
    title: 'nav.section.operations',
    items: [
      { label: 'nav.billing', icon: CreditCard, href: '/billing' },
    ],
  },
  {
    items: [
      { label: 'nav.settings', icon: Settings, href: '/settings' },
    ],
  },
];

const candidateNav: NavSection[] = [
  {
    title: 'nav.section.overview',
    items: [
      { label: 'nav.dashboard', icon: LayoutDashboard, href: '/dashboard' },
      { label: 'topbar.profile', icon: Users, href: '/profile' },
      { label: 'dash.learning', icon: BookOpen, href: '/courses' },
    ],
  },
  {
    title: 'nav.section.pipeline',
    items: [
      { label: 'jobs.title', icon: Briefcase, href: '/jobs' },
      { label: 'nav.cv_studio', icon: FileText, href: '/cv-builder', highlight: true },
      { label: 'nav.cv_review', icon: Sparkles, href: '/cv-review', highlight: true },
    ],
  },
  {
    title: 'nav.section.tracking',
    items: [
      { label: 'nav.applications', icon: FileText, href: '/applications' },
      { label: 'iv.title', icon: Calendar, href: '/interviews' },
      { label: 'msg.title', icon: MessageSquare, href: '/messages' },
    ],
  },
  {
    title: 'nav.section.account',
    items: [

      { label: 'nav.achievements', icon: Trophy, href: '/achievements' },
      { label: 'nav.skill_progress', icon: Target, href: '/skill-progress' },
      { label: 'common.settings', icon: Settings, href: '/settings' },
    ],
  },
];

const mentorNav: NavSection[] = [
  {
    items: [
      { label: 'nav.mentor_dashboard', icon: LayoutDashboard, href: '/dashboard' },
      { label: 'nav.mentees', icon: Users, href: '/candidates' },
      { label: 'nav.coaching', icon: Calendar, href: '/interviews', badge: 'nav.badge.today' },
    ],
  },
  {
    title: 'nav.section.review',
    items: [
      { label: 'nav.cv_code_reviews', icon: FileText, href: '/mentor/reviews' },
      { label: 'nav.rubric_scorecards', icon: Award, href: '/rubrics' },
      { label: 'nav.skill_progression', icon: Sparkles, href: '/skill-trees' },
      { label: 'nav.course_library', icon: BookOpen, href: '/courses' },
    ],
  },
  {
    title: 'nav.section.communication',
    items: [
      { label: 'nav.mentee_messages', icon: MessageSquare, href: '/messages' },
      { label: 'nav.schedule_calendar', icon: Calendar, href: '/calendar' },
    ],
  },
  {
    items: [
      { label: 'nav.mentor_settings', icon: Settings, href: '/settings' },
    ],
  },
];

const adminNav: NavSection[] = [
  {
    items: [
      { label: 'nav.global_dashboard', icon: LayoutDashboard, href: '/dashboard' },
      { label: 'nav.system_health', icon: Activity, href: '/admin/logs', highlight: true },
      { label: 'nav.ai_monitoring', icon: Zap, href: '/admin/ai-monitoring' },
    ],
  },
  {
    title: 'nav.section.platform',
    items: [
      { label: 'nav.users', icon: Users, href: '/admin/users' },
      { label: 'nav.orgs', icon: Briefcase, href: '/admin/organizations' },
      { label: 'nav.admin_jobs', icon: Briefcase, href: '/admin/jobs' },
      { label: 'nav.subscriptions', icon: Star, href: '/admin/subscriptions' },
      { label: 'nav.finance_dashboard', icon: Wallet, href: '/admin/finance' },
      { label: 'nav.payments', icon: CreditCard, href: '/admin/payments' },
      { label: 'nav.payment_proofs', icon: FileCheck2, href: '/admin/payment-proofs' },
      { label: 'nav.invoices', icon: Receipt, href: '/admin/invoices' },
      { label: 'nav.moderation', icon: Shield, href: '/admin/moderation' },
      { label: 'nav.kyb', icon: FileCheck2, href: '/admin/kyb' },
      { label: 'nav.rubrics', icon: FileText, href: '/admin/rubrics' },
      { label: 'nav.rubric_builder', icon: ListChecks, href: '/admin/rubric-builder' },
      { label: 'nav.categories', icon: FolderTree, href: '/admin/categories' },
      { label: 'nav.content', icon: BookOpen, href: '/admin/content' },
      { label: 'nav.admin_courses', icon: BookOpen, href: '/admin/courses' },
      { label: 'nav.opportunities', icon: Target, href: '/admin/opportunities' },
      { label: 'nav.marketing', icon: Megaphone, href: '/admin/marketing' },
      { label: 'nav.announcements', icon: Volume2, href: '/admin/announcements' },
      { label: 'nav.recruiter_usage', icon: Gauge, href: '/admin/recruiter-usage' },
      { label: 'nav.support_inbox', icon: Headphones, href: '/admin/support' },
    ],
  },
  {
    title: 'nav.section.ai_infra',
    items: [
      { label: 'nav.platform_analytics', icon: BarChart3, href: '/admin/analytics' },
      { label: 'nav.permissions', icon: Shield, href: '/admin/permissions' },
      { label: 'nav.ab_testing', icon: Beaker, href: '/admin/ab-testing' },
      { label: 'nav.prompt_management', icon: Terminal, href: '/admin/prompt-management' },
      { label: 'nav.ai_sales', icon: TrendingUp, href: '/admin/ai-sales' },
    ],
  },
  {
    items: [
      { label: 'nav.admin_settings', icon: Settings, href: '/admin/settings' },
    ],
  },
];

const orgNav: NavSection[] = [
  {
    items: [
      { label: 'nav.org_dashboard', icon: LayoutDashboard, href: '/org' },
    ],
  },
  {
    title: 'nav.section.org_management',
    items: [
      { label: 'nav.org_members', icon: Users, href: '/org/members' },
      { label: 'nav.org_analytics', icon: BarChart3, href: '/org/analytics' },
    ],
  },
  {
    title: 'nav.section.org_billing',
    items: [
      { label: 'nav.org_billing', icon: CreditCard, href: '/org/billing' },
    ],
  },
];

const roleNavMap: Record<UserRole, NavSection[]> = {
  recruiter: recruiterNav,
  candidate: candidateNav,
  mentor: mentorNav,
  admin: adminNav,
  company: orgNav,
};

export function Sidebar() {
  const { user, switchRole, isDemoMode } = useAuth();
  const { isOpen, isCollapsed, collapse, expand, close } = useSidebar();
  const { t } = useLanguage();
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    close();
  }, [location.pathname, close]);

  const currentRole: UserRole = user?.role || 'recruiter';
  const navSections = roleNavMap[currentRole] || recruiterNav;
  const roleLabel = t(`role.${currentRole}`);

  const cycleNextRole = () => {
    const roles: UserRole[] = ['recruiter', 'candidate', 'mentor', 'admin', 'company'];
    const nextIdx = (roles.indexOf(currentRole) + 1) % roles.length;
    const nextRole = roles[nextIdx];
    switchRole(nextRole);
    navigate('/dashboard');
    customToast({
      type: 'info',
      title: 'Workspace Changed',
      message: `Now viewing Candway as ${nextRole.toUpperCase()}`,
    });
  };

  return (
    <>
      {/* Desktop Sidebar */}
      <motion.aside
        initial={false}
        animate={{ width: isCollapsed ? 72 : 260 }}
        transition={{ duration: 0.2, ease: 'easeInOut' }}
        className="glass-sidebar relative hidden lg:flex flex-col h-screen shrink-0 overflow-hidden z-30"
      >
        {/* Decorative glass shine */}
        <div className="pointer-events-none absolute inset-x-0 top-0 h-40 bg-gradient-to-b from-white/30 dark:from-white/10 to-transparent" />
        <div className="pointer-events-none absolute -top-20 -right-20 h-56 w-56 rounded-full bg-fuchsia-400/30 dark:bg-fuchsia-400/20 blur-3xl" />
        <div className="pointer-events-none absolute bottom-10 -left-24 h-64 w-64 rounded-full bg-indigo-400/30 dark:bg-indigo-400/20 blur-3xl" />

        {/* Header & Logo */}
        <div className="relative flex items-center h-16 px-4 border-b border-purple-100 dark:border-white/10">
          <Link to="/dashboard" className="flex items-center gap-3 min-w-0">
            <img
              src="/candway_logo.png"
              alt="Candway"
              className="h-8 w-8 shrink-0 rounded-lg object-contain"
            />
            <AnimatePresence mode="wait">
              {!isCollapsed && (
                <motion.div
                  initial={{ opacity: 0, width: 0 }}
                  animate={{ opacity: 1, width: 'auto' }}
                  exit={{ opacity: 0, width: 0 }}
                  className="flex flex-col whitespace-nowrap"
                >
                  <span className="text-lg font-bold text-gray-900 dark:text-white tracking-tight leading-none">
                    Candway
                  </span>
                  <span className="text-[10px] font-semibold mt-0.5 uppercase tracking-wider text-purple-600 dark:text-purple-200">
                    {roleLabel} Studio
                  </span>
                </motion.div>
              )}
            </AnimatePresence>
          </Link>
        </div>

        {/* Navigation */}
        <nav className="relative flex-1 overflow-y-auto py-3 px-3 space-y-1">
          {navSections.map((section, i) => (
            <div key={i}>
              {section.title && !isCollapsed && (
                <div className="px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-purple-500 dark:text-purple-200/70">
                  {t(section.title)}
                </div>
              )}
              <div className="space-y-0.5">
                {section.items.map((item) => (
                  <SidebarNavItem
                    key={item.href + item.label}
                    item={item}
                    isActive={location.pathname === item.href || (item.href !== '/dashboard' && location.pathname.startsWith(item.href))}
                    isCollapsed={isCollapsed}
                    t={t}
                  />
                ))}
              </div>
              {i < navSections.length - 1 && <div className="my-2 mx-3 h-px bg-purple-100/80 dark:bg-white/10" />}
            </div>
          ))}
        </nav>

        {/* Role Workspace Banner / Quick Switcher */}
        <AnimatePresence mode="wait">
          {isDemoMode && !isCollapsed && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="glass-sidebar-item relative p-3 mx-3 mb-2 rounded-xl"
            >
              <div className="flex items-center justify-between text-xs font-semibold text-purple-900 dark:text-white">
                <span>{t('sidebar.active_workspace')}</span>
                <span className="px-1.5 py-0.5 rounded font-bold text-[10px] bg-purple-200/60 text-purple-900 border border-purple-300/50 dark:bg-white/20 dark:text-white dark:border-white/20">
                  {roleLabel}
                </span>
              </div>
              <p className="text-[11px] text-purple-700/80 mt-1 leading-normal dark:text-purple-200/80">
                {t('sidebar.viewing_as')} {roleLabel}.
              </p>
              <button
                onClick={cycleNextRole}
                className="mt-2 w-full text-center py-1.5 text-xs font-semibold rounded-lg bg-white/90 text-purple-800 hover:bg-white transition-all shadow-md shadow-purple-950/20"
              >
                {t('sidebar.cycle_role')} &rarr;
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Collapse Toggle */}
        <div className="relative border-t border-purple-100 dark:border-white/10 p-3">
          <button
            onClick={isCollapsed ? expand : collapse}
            className="glass-sidebar-item flex items-center justify-center w-full h-8 rounded-lg text-purple-700 hover:text-purple-900 dark:text-purple-100 dark:hover:text-white transition-colors"
            title={isCollapsed ? t('sidebar.expand') : t('sidebar.collapse')}
          >
            {isCollapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          </button>
        </div>
      </motion.aside>

      {/* Mobile Drawer */}
      <AnimatePresence>
        {isOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={close}
              className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm lg:hidden"
            />
            <motion.aside
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              transition={{ type: 'spring', damping: 25, stiffness: 200 }}
              className="fixed inset-y-0 left-0 z-50 w-72 glass-sidebar flex flex-col h-full lg:hidden overflow-hidden shadow-2xl"
            >
              {/* Header & Logo */}
              <div className="relative flex items-center justify-between h-16 px-4 border-b border-purple-100 dark:border-white/10">
                <Link to="/dashboard" onClick={close} className="flex items-center gap-3 min-w-0">
                  <img
                    src="/candway_logo.png"
                    alt="Candway"
                    className="h-8 w-8 shrink-0 rounded-lg object-contain"
                  />
                  <div className="flex flex-col whitespace-nowrap">
                    <span className="text-lg font-bold text-gray-900 dark:text-white tracking-tight leading-none">
                      Candway
                    </span>
                    <span className="text-[10px] font-semibold mt-0.5 uppercase tracking-wider text-purple-600 dark:text-purple-200">
                      {roleLabel} Studio
                    </span>
                  </div>
                </Link>
                <button
                  onClick={close}
                  className="p-1.5 rounded-lg text-purple-700 hover:text-purple-900 dark:text-purple-200 hover:bg-purple-100/50 dark:hover:bg-white/10 transition-colors"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              {/* Mobile Navigation */}
              <nav className="relative flex-1 overflow-y-auto py-3 px-3 space-y-1">
                {navSections.map((section, i) => (
                  <div key={i}>
                    {section.title && (
                      <div className="px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-purple-500 dark:text-purple-200/70">
                        {t(section.title)}
                      </div>
                    )}
                    <div className="space-y-0.5">
                      {section.items.map((item) => (
                        <SidebarNavItem
                          key={item.href + item.label}
                          item={item}
                          isActive={location.pathname === item.href || (item.href !== '/dashboard' && location.pathname.startsWith(item.href))}
                          isCollapsed={false}
                          t={t}
                          onClick={close}
                        />
                      ))}
                    </div>
                    {i < navSections.length - 1 && <div className="my-2 mx-3 h-px bg-purple-100/80 dark:bg-white/10" />}
                  </div>
                ))}
              </nav>
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}

function SidebarNavItem({
  item,
  isActive,
  isCollapsed,
  t,
  onClick,
}: {
  item: NavItem;
  isActive: boolean;
  isCollapsed: boolean;
  t: (key: string) => string;
  onClick?: () => void;
}) {
  const label = t(item.label);
  const badge = typeof item.badge === 'string' ? t(item.badge) : item.badge;

  return (
    <Link
      to={item.href}
      onClick={onClick}
      className={cn(
        'group flex items-center gap-3 h-9 rounded-lg px-3 text-sm font-medium transition-all duration-150 relative',
        isActive
          ? 'glass-sidebar-active text-purple-800 dark:text-white font-bold'
          : 'text-gray-600 hover:bg-purple-100/50 hover:text-purple-900 dark:text-purple-100/85 dark:hover:bg-white/10 dark:hover:text-white',
        item.highlight && !isActive && 'text-fuchsia-600 dark:text-fuchsia-200 font-bold',
        isCollapsed && 'justify-center px-0'
      )}
      title={isCollapsed ? label : undefined}
    >
      <item.icon className={cn(
        'h-4 w-4 shrink-0 transition-colors relative z-[1]',
        isActive ? 'text-purple-700 dark:text-white' : item.highlight ? 'text-fuchsia-500 dark:text-fuchsia-300' : 'text-gray-400 group-hover:text-purple-700 dark:text-purple-200/70 dark:group-hover:text-white'
      )} />
      <AnimatePresence mode="wait">
        {!isCollapsed && (
          <motion.div
            initial={{ opacity: 0, width: 0 }}
            animate={{ opacity: 1, width: 'auto' }}
            exit={{ opacity: 0, width: 0 }}
            className="flex items-center justify-between flex-1 min-w-0 relative z-[1]"
          >
            <span className="truncate">{label}</span>
            {badge !== undefined && badge !== null && badge !== '' && (
              <span className={cn(
                'ml-auto text-[10px] font-bold px-1.5 py-0.5 rounded-full min-w-[18px] text-center shrink-0',
                isActive
                  ? 'bg-purple-200/50 text-purple-900 border border-purple-300/50 dark:bg-white/25 dark:text-white dark:border-white/20'
                  : 'bg-purple-50 text-purple-700 border border-purple-200 dark:bg-white/12 dark:text-purple-100 dark:border-white/10'
              )}>
                {badge}
              </span>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </Link>
  );
}
