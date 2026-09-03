// ============================================================
// Sidebar Context
// ============================================================

import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';

interface SidebarContextValue {
  isOpen: boolean;
  isCollapsed: boolean;
  toggle: () => void;
  collapse: () => void;
  expand: () => void;
  close: () => void;
}

const SidebarContext = createContext<SidebarContextValue | null>(null);

export function SidebarProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(true);
  const [isCollapsed, setIsCollapsed] = useState(false);

  const toggle = useCallback(() => setIsOpen(prev => !prev), []);
  const collapse = useCallback(() => setIsCollapsed(true), []);
  const expand = useCallback(() => setIsCollapsed(false), []);
  const close = useCallback(() => setIsOpen(false), []);

  return (
    <SidebarContext.Provider value={{ isOpen, isCollapsed, toggle, collapse, expand, close }}>
      {children}
    </SidebarContext.Provider>
  );
}

export function useSidebar() {
  const context = useContext(SidebarContext);
  if (!context) {
    throw new Error('useSidebar must be used within a SidebarProvider');
  }
  return context;
}
