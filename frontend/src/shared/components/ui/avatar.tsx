// ============================================================
// Avatar Component - Candway Design System
// ============================================================

import { forwardRef, type HTMLAttributes } from 'react';
import { cn } from '@/utils/cn';

type AvatarSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl' | '2xl';

interface AvatarProps extends HTMLAttributes<HTMLDivElement> {
  src?: string | null;
  alt?: string;
  name?: string;
  size?: AvatarSize;
  status?: 'online' | 'offline' | 'away' | 'busy';
  square?: boolean;
}

const sizeStyles: Record<AvatarSize, string> = {
  xs: 'h-6 w-6 text-[10px]',
  sm: 'h-8 w-8 text-xs',
  md: 'h-10 w-10 text-sm',
  lg: 'h-12 w-12 text-base',
  xl: 'h-16 w-16 text-lg',
  '2xl': 'h-20 w-20 text-xl',
};

const statusSizeStyles: Record<AvatarSize, string> = {
  xs: 'h-1.5 w-1.5 border',
  sm: 'h-2 w-2 border-[1.5px]',
  md: 'h-2.5 w-2.5 border-2',
  lg: 'h-3 w-3 border-2',
  xl: 'h-4 w-4 border-2',
  '2xl': 'h-5 w-5 border-[3px]',
};

const statusColors = {
  online: 'bg-emerald-500',
  offline: 'bg-gray-400',
  away: 'bg-amber-500',
  busy: 'bg-red-500',
};

function getInitials(name: string): string {
  return name
    .split(' ')
    .map((n) => n[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();
}

const colors = [
  'bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-400',
  'bg-purple-100 text-purple-700 dark:bg-purple-500/20 dark:text-purple-400',
  'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-400',
  'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400',
  'bg-rose-100 text-rose-700 dark:bg-rose-500/20 dark:text-rose-400',
  'bg-cyan-100 text-cyan-700 dark:bg-cyan-500/20 dark:text-cyan-400',
];

function getColorForName(name: string): string {
  const index = name.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0) % colors.length;
  return colors[index];
}

const Avatar = forwardRef<HTMLDivElement, AvatarProps>(
  ({ src, alt, name, size = 'md', status, square = false, className, ...props }, ref) => {
    const initials = name ? getInitials(name) : '?';
    const colorClass = name ? getColorForName(name) : colors[0];

    return (
      <div ref={ref} className={cn('relative inline-flex shrink-0', className)} {...props}>
        {src ? (
          <img
            src={src}
            alt={alt || name || 'Avatar'}
            className={cn(
              'object-cover',
              sizeStyles[size],
              square ? 'rounded-lg' : 'rounded-full'
            )}
          />
        ) : (
          <div
            className={cn(
              'flex items-center justify-center font-medium',
              sizeStyles[size],
              square ? 'rounded-lg' : 'rounded-full',
              colorClass
            )}
          >
            {initials}
          </div>
        )}
        {status && (
          <span
            className={cn(
              'absolute bottom-0 right-0 rounded-full border-white dark:border-gray-900',
              statusSizeStyles[size],
              statusColors[status]
            )}
          />
        )}
      </div>
    );
  }
);

Avatar.displayName = 'Avatar';

// Avatar Group
interface AvatarGroupProps extends HTMLAttributes<HTMLDivElement> {
  max?: number;
  size?: AvatarSize;
  children: React.ReactNode;
}

function AvatarGroup({ max = 4, size = 'md', className, children, ...props }: AvatarGroupProps) {
  return (
    <div className={cn('flex -space-x-2', className)} {...props}>
      {children}
    </div>
  );
}

export { Avatar, AvatarGroup, type AvatarProps, type AvatarSize };
