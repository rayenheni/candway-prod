// ============================================================
// Toast System - Candway Design System
// ============================================================

import { Toaster, toast } from 'react-hot-toast';
import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react';
import { cn } from '@/utils/cn';

function ToastProvider() {
  return (
    <Toaster
      position="top-right"
      gutter={8}
      toastOptions={{
        duration: 4000,
        style: {
          background: 'rgba(255, 255, 255, 0.85)',
          backdropFilter: 'blur(16px)',
          color: '#111827',
          borderRadius: '12px',
          padding: '12px 16px',
          boxShadow: '0 10px 30px -5px rgba(124, 58, 237, 0.2)',
          border: '1px solid rgba(233, 213, 255, 0.7)',
          fontSize: '14px',
          lineHeight: '1.5',
          maxWidth: '420px',
        },
        success: {
          iconTheme: {
            primary: '#10B981',
            secondary: 'white',
          },
        },
        error: {
          iconTheme: {
            primary: '#EF4444',
            secondary: 'white',
          },
        },
      }}
    />
  );
}

interface CustomToastProps {
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message?: string;
  duration?: number;
  actionLabel?: string;
  onAction?: () => void;
}

function customToast({ type, title, message, duration, actionLabel, onAction }: CustomToastProps) {
  const icons = {
    success: <CheckCircle className="h-5 w-5 text-emerald-500" />,
    error: <XCircle className="h-5 w-5 text-red-500" />,
    warning: <AlertTriangle className="h-5 w-5 text-amber-500" />,
    info: <Info className="h-5 w-5 text-blue-500" />,
  };

  const borderColors = {
    success: 'border-l-emerald-500',
    error: 'border-l-red-500',
    warning: 'border-l-amber-500',
    info: 'border-l-blue-500',
  };

  toast.custom(
    (t) => (
      <div
        className={cn(
          'flex items-start gap-3 p-4 bg-white rounded-xl shadow-lg border border-gray-200/60 border-l-4',
          'dark:bg-gray-900 dark:border-white/[0.08]',
          borderColors[type],
          t.visible ? 'animate-enter' : 'animate-leave'
        )}
      >
        {icons[type]}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-900 dark:text-white">{title}</p>
          {message && <p className="mt-0.5 text-sm text-gray-500 dark:text-gray-400">{message}</p>}
          {actionLabel && onAction && (
            <button
              onClick={() => {
                toast.dismiss(t.id);
                onAction();
              }}
              className="mt-2 inline-flex items-center gap-1.5 text-xs font-bold text-violet-600 dark:text-violet-400 hover:underline"
            >
              {actionLabel}
              <span aria-hidden="true">&rarr;</span>
            </button>
          )}
        </div>
        <button
          onClick={() => toast.dismiss(t.id)}
          className="shrink-0 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    ),
    { duration: duration ?? 4000 }
  );
}

export { ToastProvider, customToast };
