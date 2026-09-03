// ============================================================
// Card Component - Candway Design System
// ============================================================

import { forwardRef, type HTMLAttributes, type ReactNode } from 'react';
import { cn } from '@/utils/cn';

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'elevated' | 'outlined' | 'glass';
  padding?: 'none' | 'sm' | 'md' | 'lg';
  hoverable?: boolean;
}

const variantStyles = {
  default: 'glass-card',
  elevated: 'glass-card shadow-lg shadow-purple-200/30 dark:shadow-none',
  outlined: 'bg-white/40 backdrop-blur-md border-2 border-purple-200/60 dark:bg-white/[0.03] dark:border-purple-500/20',
  glass: 'glass-panel',
};

const paddingStyles = {
  none: '',
  sm: 'p-4',
  md: 'p-6',
  lg: 'p-8',
};

const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ variant = 'default', padding = 'md', hoverable = false, className, children, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'rounded-xl transition-all duration-200',
        variantStyles[variant],
        paddingStyles[padding],
        hoverable && 'hover:shadow-lg hover:shadow-purple-200/40 hover:border-purple-300/50 cursor-pointer dark:hover:border-purple-500/30 dark:hover:shadow-none',
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
);

Card.displayName = 'Card';

interface CardHeaderProps extends HTMLAttributes<HTMLDivElement> {
  action?: ReactNode;
}

const CardHeader = forwardRef<HTMLDivElement, CardHeaderProps>(
  ({ className, action, children, ...props }, ref) => (
    <div ref={ref} className={cn('flex items-center justify-between mb-4', className)} {...props}>
      <div className="space-y-1">{children}</div>
      {action}
    </div>
  )
);

CardHeader.displayName = 'CardHeader';

const CardTitle = forwardRef<HTMLHeadingElement, HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h3 ref={ref} className={cn('text-lg font-semibold text-gray-900 dark:text-white', className)} {...props} />
  )
);

CardTitle.displayName = 'CardTitle';

const CardDescription = forwardRef<HTMLParagraphElement, HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => (
    <p ref={ref} className={cn('text-sm text-gray-500 dark:text-gray-400', className)} {...props} />
  )
);

CardDescription.displayName = 'CardDescription';

const CardContent = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn('', className)} {...props} />
  )
);

CardContent.displayName = 'CardContent';

const CardFooter = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn('flex items-center pt-4 mt-4 border-t border-gray-100 dark:border-white/[0.06]', className)} {...props} />
  )
);

CardFooter.displayName = 'CardFooter';

export { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter, type CardProps };
