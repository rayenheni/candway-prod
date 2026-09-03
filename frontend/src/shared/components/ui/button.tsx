// ============================================================
// Button Component - Candway Design System
// ============================================================

import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cn } from '@/utils/cn';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'outline' | 'danger' | 'success' | 'link';
export type ButtonSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
  asChild?: boolean;
}

const variantStyles: Record<ButtonVariant, string> = {
  primary:
    'bg-gradient-to-r from-purple-600 to-violet-600 text-white hover:from-purple-700 hover:to-violet-700 active:from-purple-800 active:to-violet-800 shadow-md shadow-purple-500/25 hover:shadow-lg hover:shadow-purple-500/35 disabled:shadow-none',
  secondary:
    'bg-purple-50/80 backdrop-blur-sm text-purple-800 border border-purple-200/60 hover:bg-purple-100/80 active:bg-purple-200/70 dark:bg-purple-500/10 dark:text-purple-200 dark:border-purple-500/20 dark:hover:bg-purple-500/20',
  ghost:
    'text-gray-700 hover:bg-purple-50/70 active:bg-purple-100/70 dark:text-gray-300 dark:hover:bg-purple-500/10',
  outline:
    'border border-purple-200/70 bg-white/50 backdrop-blur-sm text-gray-700 hover:bg-purple-50/70 hover:border-purple-300/70 dark:border-purple-500/20 dark:bg-white/[0.03] dark:text-gray-300 dark:hover:bg-purple-500/10',
  danger:
    'bg-red-600 text-white hover:bg-red-700 active:bg-red-800 shadow-sm shadow-red-600/25',
  success:
    'bg-emerald-600 text-white hover:bg-emerald-700 active:bg-emerald-800 shadow-sm shadow-emerald-600/25',
  link:
    'text-purple-600 hover:text-purple-700 hover:underline dark:text-purple-400',
};

const sizeStyles: Record<ButtonSize, string> = {
  xs: 'h-7 px-2.5 text-xs gap-1 rounded-md',
  sm: 'h-8 px-3 text-sm gap-1.5 rounded-lg',
  md: 'h-9 px-4 text-sm gap-2 rounded-lg',
  lg: 'h-10 px-5 text-sm gap-2 rounded-xl',
  xl: 'h-12 px-6 text-base gap-2.5 rounded-xl',
};

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = 'primary',
      size = 'md',
      loading = false,
      leftIcon,
      rightIcon,
      asChild = false,
      className,
      children,
      disabled,
      ...props
    },
    ref
  ) => {
    const Comp = asChild ? Slot : 'button';
    const isDisabled = disabled || loading;

    return (
      <Comp
        ref={ref}
        disabled={isDisabled}
        className={cn(
          'inline-flex items-center justify-center font-medium transition-all duration-150 ease-out',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-gray-900',
          'disabled:pointer-events-none disabled:opacity-50',
          'select-none',
          variantStyles[variant],
          sizeStyles[size],
          className
        )}
        {...props}
      >
        {loading && (
          <svg
            className="animate-spin -ml-0.5 h-4 w-4"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        )}
        {!loading && leftIcon}
        {children}
        {rightIcon}
      </Comp>
    );
  }
);

Button.displayName = 'Button';

export { Button, type ButtonProps };
