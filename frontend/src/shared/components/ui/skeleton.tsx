// ============================================================
// Skeleton Component - Candway Design System
// ============================================================

import { type HTMLAttributes } from 'react';
import { cn } from '@/utils/cn';

function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'animate-pulse rounded-lg bg-gray-100 dark:bg-white/[0.06]',
        className
      )}
      {...props}
    />
  );
}

// Pre-built skeleton patterns
function SkeletonText({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <div className={cn('space-y-2', className)}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          className={cn('h-4', i === lines - 1 ? 'w-3/4' : 'w-full')}
        />
      ))}
    </div>
  );
}

function SkeletonCircle({ size = 'md', className }: { size?: 'sm' | 'md' | 'lg'; className?: string }) {
  const sizeMap = { sm: 'h-8 w-8', md: 'h-10 w-10', lg: 'h-12 w-12' };
  return <Skeleton className={cn(sizeMap[size], 'rounded-full', className)} />;
}

function SkeletonCard({ className }: { className?: string }) {
  return (
    <div className={cn('space-y-3 p-6 rounded-xl border border-gray-200/60 dark:border-white/[0.06]', className)}>
      <Skeleton className="h-4 w-1/4" />
      <Skeleton className="h-8 w-1/2" />
      <SkeletonText lines={2} />
    </div>
  );
}

function SkeletonTable({ rows = 5, columns = 4 }: { rows?: number; columns?: number }) {
  return (
    <div className="space-y-3">
      <div className="flex gap-4">
        {Array.from({ length: columns }).map((_, i) => (
          <Skeleton key={i} className="h-4 flex-1" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-4">
          {Array.from({ length: columns }).map((_, j) => (
            <Skeleton key={j} className="h-8 flex-1" />
          ))}
        </div>
      ))}
    </div>
  );
}

export { Skeleton, SkeletonText, SkeletonCircle, SkeletonCard, SkeletonTable };
