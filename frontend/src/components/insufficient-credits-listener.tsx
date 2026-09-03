// ============================================================
// Global 402 / insufficient-credits listener
// Shows a toast with an upgrade action when the API returns 402.
// ============================================================

import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router';
import { onInsufficientCredits } from '@/lib/api-client';
import { customToast } from '@/shared/components/ui/toast';

export function InsufficientCreditsListener() {
  const navigate = useNavigate();
  const navigateRef = useRef(navigate);
  navigateRef.current = navigate;

  useEffect(() => {
    onInsufficientCredits((payload) => {
      customToast({
        type: 'warning',
        title: 'Insufficient Credits',
        message: payload.message,
        actionLabel: 'Upgrade',
        onAction: () => navigateRef.current(payload.upgradeUrl || '/dashboard'),
      });
    });
    return () => onInsufficientCredits(null as never);
  }, []);

  return null;
}
