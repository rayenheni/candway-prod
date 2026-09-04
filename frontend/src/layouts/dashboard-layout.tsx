// ============================================================
// Dashboard Layout - White Purple Glassmorphism Shell
// ============================================================

import { Outlet } from 'react-router';
import { Sidebar } from '@/layouts/dashboard/sidebar';
import { Topbar } from '@/layouts/dashboard/topbar';
import { SidebarProvider } from '@/contexts/sidebar-context';
import { OnboardingGuard } from '@/features/candidate/components/onboarding-guard';
import { InsufficientCreditsListener } from '@/components/insufficient-credits-listener';

export function DashboardLayout() {
  return (
    <SidebarProvider>
      <InsufficientCreditsListener />
      <div className="candway-page-bg flex h-screen overflow-hidden">
        {/* Floating decorative purple orbs */}
        <div className="candway-orb animate-float-slow h-72 w-72 bg-purple-300/40 top-[-80px] left-[30%]" />
        <div className="candway-orb h-80 w-80 bg-indigo-300/30 bottom-[-100px] right-[-60px]" />
        <div className="candway-orb h-56 w-56 bg-fuchsia-300/25 top-[40%] right-[25%]" />

        <Sidebar />
        <div className="relative flex-1 flex flex-col overflow-hidden z-10">
          <Topbar />
          <main className="flex-1 overflow-y-auto">
            <div className="mx-auto max-w-7xl px-3 sm:px-6 py-4 sm:py-6">
              <OnboardingGuard>
                <Outlet />
              </OnboardingGuard>
            </div>
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
}
