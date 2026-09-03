// ============================================================
// Progress Component - Candway Design System
// ============================================================

import { type HTMLAttributes } from 'react';
import { cn } from '@/utils/cn';

interface ProgressProps extends HTMLAttributes<HTMLDivElement> {
  value: number;
  max?: number;
  size?: 'sm' | 'md' | 'lg';
  color?: 'default' | 'blue' | 'green' | 'amber' | 'red' | 'purple';
  showLabel?: boolean;
}

const colorStyles = {
  default: 'bg-gradient-to-r from-purple-600 to-violet-500',
  blue: 'bg-gradient-to-r from-blue-600 to-indigo-500',
  green: 'bg-emerald-600',
  amber: 'bg-amber-500',
  red: 'bg-red-500',
  purple: 'bg-gradient-to-r from-purple-600 to-fuchsia-500',
};

const sizeStyles = {
  sm: 'h-1',
  md: 'h-2',
  lg: 'h-3',
};

export function Progress({
  value,
  max = 100,
  size = 'md',
  color = 'default',
  showLabel = false,
  className,
  ...props
}: ProgressProps) {
  const percentage = Math.min(Math.max((value / max) * 100, 0), 100);

  return (
    <div className={cn('w-full', className)} {...props}>
      {showLabel && (
        <div className="flex justify-between items-center mb-1.5">
          <span className="text-xs text-gray-500 dark:text-gray-400">Progress</span>
          <span className="text-xs font-medium text-gray-700 dark:text-gray-300">{Math.round(percentage)}%</span>
        </div>
      )}
      <div className={cn('w-full rounded-full bg-purple-100/60 dark:bg-purple-500/10', sizeStyles[size])}>
        <div
          className={cn(
            'rounded-full transition-all duration-500 ease-out',
            sizeStyles[size],
            colorStyles[color]
          )}
          style={{ width: `${percentage}%` }}
          role="progressbar"
          aria-valuenow={value}
          aria-valuemin={0}
          aria-valuemax={max}
        />
      </div>
    </div>
  );
}
