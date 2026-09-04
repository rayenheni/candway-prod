// ============================================================
// Dashboard Topbar - Candway Platform With Workspace Switcher
// ============================================================

import { Link, useNavigate } from 'react-router';
import { useAuth } from '@/contexts/auth-context';
import { useTheme } from '@/contexts/theme-context';
import { useSidebar } from '@/contexts/sidebar-context';
import { useLanguage } from '@/contexts/language-context';
import { Avatar } from '@/shared/components/ui/avatar';
import { Badge } from '@/shared/components/ui/badge';
import { SimpleDropdown } from '@/shared/components/ui/dropdown-menu';
import { customToast } from '@/shared/components/ui/toast';
import { settingsService } from '@/services/settings.service';
import type { UserRole } from '@/types';
import {
  Bell,
  Moon,
  Sun,
  Monitor,
  Menu,
  Plus,
  Settings,
  LogOut,
  User,
  HelpCircle,
  MessageSquare,
  Briefcase,
  GraduationCap,
  Shield,
  BookOpen,
  ChevronDown,
  Coins,
} from 'lucide-react';
import { useEffect, useState } from 'react';

import { GBFlag, FRFlag } from '@/shared/components/ui/flags';

export function Topbar() {
  const { user, logout, switchRole, isDemoMode } = useAuth();
  const { setTheme, resolvedTheme } = useTheme();
  const { toggle } = useSidebar();
  const { t, language, setLanguage } = useLanguage();
  const navigate = useNavigate();
  const [creditBalance, setCreditBalance] = useState<number | null>(null);

  useEffect(() => {
    if (user?.role !== 'recruiter') {
      setCreditBalance(null);
      return;
    }
    let cancelled = false;
    settingsService
      .getSubscriptionStatus()
      .then((res) => {
        if (!cancelled && typeof res.credit_balance === 'number') setCreditBalance(res.credit_balance);
      })
      .catch(() => {
        // Non-critical: credits pill simply stays hidden when unavailable.
      });
    return () => {
      cancelled = true;
    };
  }, [user?.role]);

  const handleRoleSwitch = (newRole: UserRole) => {
    switchRole(newRole);
    navigate('/dashboard');
    customToast({
      type: 'success',
      title: `Workspace Changed`,
      message: `Switched to ${newRole.toUpperCase()} workspace. UI and navigation updated.`,
    });
  };

  const themeItems = [
    { label: 'Light', icon: <Sun className="h-4 w-4" />, onClick: () => setTheme('light') },
    { label: 'Dark', icon: <Moon className="h-4 w-4" />, onClick: () => setTheme('dark') },
    { label: 'System', icon: <Monitor className="h-4 w-4" />, onClick: () => setTheme('system') },
  ];

  const langItems = [
    { label: 'English', icon: <GBFlag className="w-4 h-3" />, onClick: () => setLanguage('en') },
    { label: 'Français', icon: <FRFlag className="w-4 h-3" />, onClick: () => setLanguage('fr') },
  ];

  const profileItems = [
    { label: t('topbar.profile'), icon: <User className="h-4 w-4" />, onClick: () => navigate('/settings/profile') },
    { label: t('topbar.settings'), icon: <Settings className="h-4 w-4" />, onClick: () => navigate('/settings') },
    { label: t('topbar.help'), icon: <HelpCircle className="h-4 w-4" />, onClick: () => navigate('/help') },
    { separator: true, label: '', onClick: () => {} },
    { label: t('topbar.sign_out'), icon: <LogOut className="h-4 w-4" />, onClick: () => logout(), danger: true },
  ];

  const getRoleBadge = (role: UserRole = 'recruiter') => {
    switch (role) {
      case 'recruiter':
        return <Badge variant="primary" className="bg-blue-600 text-white dark:bg-blue-500" size="sm">{t('role.recruiter')}</Badge>;
      case 'candidate':
        return <Badge variant="success" className="bg-emerald-600 text-white dark:bg-emerald-500" size="sm">{t('role.candidate')}</Badge>;
      case 'mentor':
        return <Badge variant="info" className="bg-violet-600 text-white dark:bg-violet-500" size="sm">{t('role.mentor')}</Badge>;
      case 'admin':
        return <Badge variant="warning" className="bg-amber-600 text-white dark:bg-amber-500" size="sm">{t('role.admin')}</Badge>;
    }
  };

  return (
    <header className="glass-strong h-16 border-b border-purple-100/70 dark:border-purple-500/15 sticky top-0 z-40">
      <div className="flex items-center justify-between h-full px-3 sm:px-6">
        {/* Left - Mobile Menu & Role Workspace Switcher */}
        <div className="flex items-center gap-4">
          <button
            onClick={toggle}
            className="lg:hidden flex items-center justify-center h-9 w-9 rounded-lg text-gray-500 hover:bg-gray-100 dark:hover:bg-white/5 transition-colors"
          >
            <Menu className="h-5 w-5" />
          </button>

          {/* Role switching is a demo-only capability and is never rendered in production. */}
          {isDemoMode && <SimpleDropdown
            trigger={
              <button className="flex items-center gap-2 px-3 py-1.5 rounded-xl border border-purple-200/60 bg-white/60 backdrop-blur-md hover:bg-purple-50/80 dark:border-purple-500/20 dark:bg-white/[0.04] dark:hover:bg-purple-500/10 transition-all shadow-sm shadow-purple-200/40 dark:shadow-none">
                <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 hidden sm:inline">{t('topbar.workspace')}</span>
                {getRoleBadge(user?.role || 'recruiter')}
                <ChevronDown className="h-3.5 w-3.5 text-gray-400" />
              </button>
            }
            label={t('sidebar.cycle_role')}
            items={[
              {
                label: t('role.recruiter_desc'),
                icon: <Briefcase className="h-4 w-4 text-blue-500" />,
                onClick: () => handleRoleSwitch('recruiter'),
              },
              {
                label: t('role.candidate_desc'),
                icon: <GraduationCap className="h-4 w-4 text-emerald-500" />,
                onClick: () => handleRoleSwitch('candidate'),
              },
              {
                label: t('role.mentor_desc'),
                icon: <BookOpen className="h-4 w-4 text-violet-500" />,
                onClick: () => handleRoleSwitch('mentor'),
              },
              {
                label: t('role.admin_desc'),
                icon: <Shield className="h-4 w-4 text-amber-500" />,
                onClick: () => handleRoleSwitch('admin'),
              },
            ]}
            align="start"
          />}
        </div>

        {/* Right - Actions */}
        <div className="flex items-center gap-1.5">
          {/* Credit Balance */}
          {user?.role === 'recruiter' && creditBalance !== null && (
            <Link
              to="/billing"
              title={t('topbar.credits') || 'Credits'}
              className="flex items-center gap-1.5 h-9 px-3 rounded-lg bg-white/60 backdrop-blur-md border border-purple-100/70 dark:border-purple-500/15 dark:bg-white/[0.04] text-sm text-gray-600 dark:text-gray-300 hover:bg-purple-50/70 dark:hover:bg-purple-500/10 transition-colors shadow-sm shadow-purple-100/50 dark:shadow-none"
            >
              <Coins className="h-3.5 w-3.5 text-amber-500" />
              <span className="font-bold tabular-nums">{creditBalance}</span>
            </Link>
          )}

          {/* Quick Create */}
          <SimpleDropdown
            trigger={
              <button className="flex items-center justify-center h-9 w-9 rounded-lg text-gray-500 hover:bg-gray-100 dark:hover:bg-white/5 transition-colors" title="Quick Actions">
                <Plus className="h-4 w-4" />
              </button>
            }
            items={[
              { label: t('topbar.new_job'), onClick: () => navigate('/jobs/new') },
              { label: t('topbar.add_candidate'), onClick: () => navigate('/candidates') },
              { label: t('topbar.schedule_interview'), onClick: () => navigate('/interviews/new') },
              { label: t('topbar.open_cv_builder'), onClick: () => navigate('/cv-builder') },
            ]}
            align="end"
          />

          {/* Messages */}
          <Link
            to="/messages"
            className="relative flex items-center justify-center h-9 w-9 rounded-lg text-gray-500 hover:bg-gray-100 dark:hover:bg-white/5 transition-colors"
            title="Messages"
          >
            <MessageSquare className="h-4 w-4" />
          </Link>

          {/* Notifications */}
          <button
            onClick={() => navigate('/settings/notifications')}
            className="relative flex items-center justify-center h-9 w-9 rounded-lg text-gray-500 hover:bg-gray-100 dark:hover:bg-white/5 transition-colors"
            title="Notifications"
          >
            <Bell className="h-4 w-4" />
          </button>

          {/* Lang Toggle */}
          <SimpleDropdown
            trigger={
              <button className="flex items-center gap-1.5 h-9 px-2.5 rounded-lg text-xs font-bold text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-white/5 transition-colors" title="Change Language">
                {language === 'fr' ? <FRFlag className="w-4 h-3" /> : <GBFlag className="w-4 h-3" />}
                <span>{language === 'fr' ? 'FR' : 'EN'}</span>
              </button>
            }
            items={langItems}
            align="end"
          />

          {/* Theme Toggle */}
          <SimpleDropdown
            trigger={
              <button className="flex items-center justify-center h-9 w-9 rounded-lg text-gray-500 hover:bg-gray-100 dark:hover:bg-white/5 transition-colors" title="Change Theme">
                {resolvedTheme === 'dark' ? <Moon className="h-4 w-4 text-blue-400" /> : <Sun className="h-4 w-4 text-amber-500" />}
              </button>
            }
            items={themeItems}
            align="end"
          />

          {/* Divider */}
          <div className="h-6 w-px bg-gray-200 dark:bg-white/10 mx-1.5" />

          {/* Profile */}
          <SimpleDropdown
            trigger={
              <button className="flex items-center gap-2.5 h-9 px-2 rounded-lg hover:bg-gray-100 dark:hover:bg-white/5 transition-colors">
                <Avatar
                  src={user?.avatar}
                  name={`${user?.firstName} ${user?.lastName}`}
                  size="sm"
                  status="online"
                />
                <div className="hidden sm:block text-left">
                  <div className="text-sm font-medium text-gray-900 dark:text-white leading-none">
                    {user?.firstName} {user?.lastName}
                  </div>
                  <div className="text-[11px] text-gray-500 dark:text-gray-400 capitalize mt-0.5 font-semibold">
                    {user?.role}
                  </div>
                </div>
              </button>
            }
            items={profileItems}
            align="end"
          />
        </div>
      </div>
    </header>
  );
}
