import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import { cn } from '@/utils/cn';
import { Zap, Menu, X } from 'lucide-react';
import { appAuthUrl } from '../utils/auth-url';

const NAV_LINKS = [
  { label: 'Home', href: '/' },
  { label: 'How it works', href: '/#how' },
  { label: 'Blogs', href: '/blogs' },
  { label: 'Careers', href: '/careers' },
];

export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 40);
    window.addEventListener('scroll', handler, { passive: true });
    return () => window.removeEventListener('scroll', handler);
  }, []);

  return (
    <div className="candway-page-bg min-h-screen text-gray-900 dark:text-slate-100 relative overflow-x-hidden">
      <div className="fixed inset-0 pointer-events-none -z-10 overflow-hidden">
        <div className="absolute -top-[300px] -left-[200px] w-[900px] h-[900px] rounded-full bg-purple-600/20 dark:bg-purple-600/30 blur-[130px]" />
        <div className="absolute top-[25%] -right-[150px] w-[700px] h-[700px] rounded-full bg-indigo-500/15 dark:bg-indigo-600/20 blur-[140px]" />
        <div className="absolute bottom-[10%] left-[20%] w-[600px] h-[600px] rounded-full bg-cyan-500/15 dark:bg-cyan-600/20 blur-[120px]" />
      </div>

      <header className={cn(
        "fixed top-5 left-1/2 -translate-x-1/2 w-[calc(100%-2rem)] max-w-6xl z-50 transition-all duration-300",
        scrolled ? "top-3" : "top-5"
      )}>
        <div className={cn(
          "rounded-full px-4 py-2.5 flex items-center justify-between transition-all duration-300",
          "glass-strong border border-purple-200/50 dark:border-white/10 shadow-xl shadow-purple-500/5 backdrop-blur-2xl",
          scrolled && "bg-white/90 dark:bg-slate-950/90 shadow-2xl border-purple-300/60 dark:border-purple-500/20 py-2"
        )}>
          <Link to="/" className="flex items-center gap-2.5 pl-2 group">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-tr from-purple-600 via-indigo-600 to-cyan-500 shadow-md shadow-purple-500/20 text-white transition-transform duration-300 group-hover:scale-105 group-hover:rotate-[-6deg]">
              <Zap className="h-5 w-5 fill-current" />
            </div>
            <span className="text-xl font-black tracking-tight text-gray-950 dark:text-white">
              Candway<span className="text-purple-600 dark:text-purple-400">.ai</span>
            </span>
          </Link>

          <nav className="hidden md:flex items-center gap-7 text-sm font-semibold text-gray-600 dark:text-slate-300">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.label}
                to={link.href}
                className="hover:text-purple-600 dark:hover:text-purple-400 transition-colors"
              >
                {link.label}
              </Link>
            ))}
          </nav>

          <div className="hidden md:flex items-center gap-3">
            <a
              href={appAuthUrl("/auth/login")}
              className="text-xs font-semibold text-purple-600 dark:text-purple-400 hover:text-purple-700 hover:underline px-2 py-1"
            >
              For Employers
            </a>
            <Link to="/auth/login" className="text-sm font-semibold text-gray-700 dark:text-slate-200 hover:text-purple-600 transition-colors px-3 py-2">
              Sign in
            </Link>
            <Link
              to="/auth/register"
              className="rounded-full bg-gradient-to-r from-purple-600 to-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-purple-500/30 hover:shadow-purple-500/50 transition-all flex items-center gap-1.5"
            >
              Sign up
            </Link>
          </div>

          <button
            className="md:hidden flex h-10 w-10 items-center justify-center rounded-full text-gray-600 dark:text-slate-300"
            onClick={() => setMobileOpen(!mobileOpen)}
            aria-label="Toggle menu"
          >
            {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>

        {mobileOpen && (
          <div className="md:hidden mt-2 rounded-2xl glass-strong border border-purple-200/50 dark:border-white/10 shadow-2xl p-4">
            <nav className="flex flex-col gap-3 text-sm font-semibold text-gray-600 dark:text-slate-300">
              {NAV_LINKS.map((link) => (
                <Link
                  key={link.label}
                  to={link.href}
                  onClick={() => setMobileOpen(false)}
                  className="hover:text-purple-600 dark:hover:text-purple-400 transition-colors"
                >
                  {link.label}
                </Link>
              ))}
              <a
                href={appAuthUrl("/auth/login")}
                onClick={() => setMobileOpen(false)}
                className="text-xs font-semibold text-purple-600 dark:text-purple-400 hover:underline py-1"
              >
                For Employers →
              </a>
              <div className="flex gap-3 pt-2 border-t border-purple-200/40 dark:border-white/10">
                <Link to="/auth/login" onClick={() => setMobileOpen(false)} className="flex-1 rounded-full border border-purple-300/60 dark:border-white/15 px-4 py-2.5 text-center font-semibold text-purple-700 dark:text-purple-300">
                  Sign in
                </Link>
                <Link to="/auth/register" onClick={() => setMobileOpen(false)} className="flex-1 rounded-full bg-gradient-to-r from-purple-600 to-indigo-600 px-4 py-2.5 text-center font-semibold text-white">
                  Sign up
                </Link>
              </div>
            </nav>
          </div>
        )}
      </header>

      <main className="pt-28 pb-16 max-w-6xl mx-auto px-6">{children}</main>

      <footer className="border-t border-purple-200/40 dark:border-white/10 py-10">
        <div className="max-w-6xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-tr from-purple-600 via-indigo-600 to-cyan-500 text-white">
              <Zap className="h-4 w-4 fill-current" />
            </div>
            <span className="font-bold text-gray-950 dark:text-white">Candway.ai</span>
          </div>
          <nav className="flex flex-wrap items-center justify-center gap-6 text-sm text-gray-500 dark:text-slate-400">
            <Link to="/blogs" className="hover:text-purple-600 dark:hover:text-purple-400">Blog</Link>
            <Link to="/privacy" className="hover:text-purple-600 dark:hover:text-purple-400">Privacy Policy</Link>
            <Link to="/terms" className="hover:text-purple-600 dark:hover:text-purple-400">Terms of Service</Link>
          </nav>
          <div className="text-sm text-gray-400 dark:text-slate-500">© {new Date().getFullYear()} Candway. All rights reserved.</div>
        </div>
      </footer>
    </div>
  );
}
