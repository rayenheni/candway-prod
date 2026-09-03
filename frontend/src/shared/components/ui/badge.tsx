// ============================================================
// Badge Component - Candway Design System
// ============================================================

import { forwardRef, type HTMLAttributes } from 'react';
import { cn } from '@/utils/cn';

type BadgeVariant = 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'outline';
type BadgeSize = 'sm' | 'md' | 'lg';

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  size?: BadgeSize;
  dot?: boolean;
}

const variantStyles: Record<BadgeVariant, string> = {
  default: 'bg-purple-50/80 text-purple-700 border border-purple-100/60 dark:bg-purple-500/10 dark:text-purple-300 dark:border-purple-500/10',
  primary: 'bg-purple-100/80 text-purple-800 border border-purple-200/60 dark:bg-purple-500/15 dark:text-purple-300 dark:border-purple-500/20',
  success: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400',
  warning: 'bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400',
  danger: 'bg-red-50 text-red-700 dark:bg-red-500/10 dark:text-red-400',
  info: 'bg-sky-50 text-sky-700 dark:bg-sky-500/10 dark:text-sky-400',
  outline: 'border border-gray-200 text-gray-600 dark:border-white/10 dark:text-gray-400',
};

const sizeStyles: Record<BadgeSize, string> = {
  sm: 'px-1.5 py-0.5 text-[10px]',
  md: 'px-2 py-0.5 text-xs',
  lg: 'px-2.5 py-1 text-xs',
};

const dotVariantColors: Record<BadgeVariant, string> = {
  default: 'bg-gray-500',
  primary: 'bg-blue-500',
  success: 'bg-emerald-500',
  warning: 'bg-amber-500',
  danger: 'bg-red-500',
  info: 'bg-sky-500',
  outline: 'bg-gray-400',
};

const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ variant = 'default', size = 'md', dot = false, className, children, ...props }, ref) => (
    <span
      ref={ref}
      className={cn(
        'inline-flex items-center gap-1.5 font-medium rounded-full whitespace-nowrap',
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
      {...props}
    >
      {dot && <span className={cn('h-1.5 w-1.5 rounded-full', dotVariantColors[variant])} />}
      {children}
    </span>
  )
);

Badge.displayName = 'Badge';

export { Badge, type BadgeProps, type BadgeVariant };
