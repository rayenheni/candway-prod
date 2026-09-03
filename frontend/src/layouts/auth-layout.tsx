// ============================================================
// Auth Layout - Login/Register Pages
// ============================================================

import { Outlet } from 'react-router';
import { motion } from 'framer-motion';

export function AuthLayout() {
  return (
    <div className="flex min-h-screen">
      {/* Left Panel - Branding */}
      <div className="hidden lg:flex lg:w-1/2 relative bg-gradient-to-br from-purple-700 via-violet-700 to-indigo-900">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_rgba(255,255,255,0.12),_transparent_50%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_left,_rgba(192,132,252,0.35),_transparent_50%)]" />
        
        <div className="relative flex flex-col justify-between w-full p-12">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <img
              src="/candway_logo.png"
              alt="Candway"
              className="h-10 w-10 rounded-xl object-contain"
            />
            <span className="text-xl font-semibold text-white tracking-tight">Candway</span>
          </div>

          {/* Content */}
          <div className="max-w-md">
            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
              className="text-4xl font-bold text-white leading-tight"
            >
              Intelligence Platform
            </motion.h1>
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.1 }}
              className="mt-4 text-lg text-purple-100 leading-relaxed"
            >
              AI-powered recruitment that transforms how you discover, evaluate, and hire exceptional talent.
            </motion.p>

            {/* Value Props */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.2 }}
              className="mt-10 grid grid-cols-3 gap-6"
            >
              {[
                { label: 'AI Screening' },
                { label: 'Adaptive Interviews' },
                { label: 'Bias Reduction' },
              ].map((item) => (
                <div key={item.label}>
                  <div className="text-sm font-bold text-white">{item.label}</div>
                </div>
              ))}
            </motion.div>
          </div>

          {/* Bottom */}
          <div className="text-sm text-purple-200">
            © {new Date().getFullYear()} Candway. All rights reserved.
          </div>
        </div>
      </div>

      {/* Right Panel - Form */}
      <div className="candway-page-bg flex-1 flex items-center justify-center p-8">
        <div className="glass-panel w-full max-w-[440px] rounded-3xl p-8 relative z-10">
          {/* Mobile Logo */}
          <div className="flex items-center gap-3 mb-8 lg:hidden">
            <img
              src="/candway_logo.png"
              alt="Candway"
              className="h-10 w-10 rounded-xl object-contain"
            />
            <span className="text-xl font-bold text-gray-900 dark:text-white tracking-tight">Candway</span>
          </div>

          <Outlet />
        </div>
      </div>
    </div>
  );
}
