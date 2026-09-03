// ============================================================
// Tabs Component - Candway Design System
// ============================================================

import { forwardRef, type ComponentPropsWithoutRef } from 'react';
import * as TabsPrimitive from '@radix-ui/react-tabs';
import { cn } from '@/utils/cn';

const Tabs = TabsPrimitive.Root;

const TabsList = forwardRef<
  React.ComponentRef<typeof TabsPrimitive.List>,
  ComponentPropsWithoutRef<typeof TabsPrimitive.List>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.List
    ref={ref}
    className={cn(
      'inline-flex items-center gap-0.5 rounded-xl bg-purple-100/50 backdrop-blur-md border border-purple-200/40 p-1 dark:bg-purple-500/10 dark:border-purple-500/15',
      className
    )}
    {...props}
  />
));
TabsList.displayName = 'TabsList';

const TabsTrigger = forwardRef<
  React.ComponentRef<typeof TabsPrimitive.Trigger>,
  ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Trigger
    ref={ref}
    className={cn(
      'inline-flex items-center justify-center whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium transition-all',
      'text-gray-600 hover:text-purple-800',
      'dark:text-gray-400 dark:hover:text-purple-200',
      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-500',
      'disabled:pointer-events-none disabled:opacity-50',
      'data-[state=active]:bg-white/90 data-[state=active]:text-purple-800 data-[state=active]:shadow-sm data-[state=active]:shadow-purple-200/50',
      'dark:data-[state=active]:bg-purple-500/20 dark:data-[state=active]:text-white',
      className
    )}
    {...props}
  />
));
TabsTrigger.displayName = 'TabsTrigger';

const TabsContent = forwardRef<
  React.ComponentRef<typeof TabsPrimitive.Content>,
  ComponentPropsWithoutRef<typeof TabsPrimitive.Content>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Content
    ref={ref}
    className={cn(
      'mt-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500',
      className
    )}
    {...props}
  />
));
TabsContent.displayName = 'TabsContent';

export { Tabs, TabsList, TabsTrigger, TabsContent };
