import { useCallback, useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { customToast } from '@/shared/components/ui/toast';
import { useLanguage } from '@/contexts/language-context';
import { Calendar, Link, Unlink, X, Loader2 } from 'lucide-react';
import { calendarService } from '@/services/calendar.service';
import { cn } from '@/utils/cn';

type ProviderStatus = {
  connected: boolean;
  syncing: boolean;
};

const initialStatus: Record<'google' | 'outlook', ProviderStatus> = {
  google: { connected: false, syncing: false },
  outlook: { connected: false, syncing: false },
};

export default function CalendarSettingsPage() {
  const { t } = useLanguage();
  const [status, setStatus] = useState(initialStatus);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState<'google' | 'outlook' | null>(null);
  const [authInput, setAuthInput] = useState('');

  const loadStatus = useCallback(async () => {
    try {
      const res = await calendarService.getCalendarStatus();
      const data = res as any;
      setStatus({
        google: { connected: Boolean(data?.google_connected), syncing: false },
        outlook: { connected: Boolean(data?.outlook_connected), syncing: false },
      });
    } catch {
      setStatus(initialStatus);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  const handleConnect = async (provider: 'google' | 'outlook') => {
    if (!authInput.trim()) {
      customToast({ type: 'error', title: t('common.status'), message: 'Paste authorization code.' });
      return;
    }
    setStatus((prev) => ({ ...prev, [provider]: { ...prev[provider], syncing: true } }));
    try {
      if (provider === 'google') {
        await calendarService.connectGoogle(authInput.trim());
      } else {
        await calendarService.connectOutlook(authInput.trim());
      }
      customToast({ type: 'success', title: t('common.status'), message: 'Calendar connected.' });
      setConnecting(null);
      setAuthInput('');
      await loadStatus();
    } catch (err: any) {
      customToast({ type: 'error', title: t('common.status'), message: err?.message || 'Connection failed.' });
    } finally {
      setStatus((prev) => ({ ...prev, [provider]: { ...prev[provider], syncing: false } }));
    }
  };

  const handleDisconnect = async (provider: 'google' | 'outlook') => {
    setStatus((prev) => ({ ...prev, [provider]: { ...prev[provider], syncing: true } }));
    try {
      await calendarService.disconnectCalendar(provider);
      customToast({ type: 'warning', title: t('common.status'), message: 'Calendar disconnected.' });
      await loadStatus();
    } catch (err: any) {
      customToast({ type: 'error', title: t('common.status'), message: err?.message || 'Failed.' });
    } finally {
      setStatus((prev) => ({ ...prev, [provider]: { ...prev[provider], syncing: false } }));
    }
  };

  const providers = [
    {
      id: 'google' as const,
      name: 'Google Calendar',
      icon: Calendar,
      color: 'from-blue-500 to-blue-600',
      hint: 'OAuth authorization code',
    },
    {
      id: 'outlook' as const,
      name: 'Outlook Calendar',
      icon: Calendar,
      color: 'from-orange-500 to-red-500',
      hint: 'Microsoft Graph token',
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">{t('nav.calendarSettings')}</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{t('iv.subtitle')}</p>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 py-10 justify-center text-sm text-gray-400">
          <Loader2 className="h-4 w-4 animate-spin" /> ...
        </div>
      ) : (
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }} className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {providers.map((cal, i) => {
            const Icon = cal.icon;
            const state = status[cal.id];
            return (
              <motion.div key={cal.id} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: 0.1 + i * 0.08 }}>
                <Card className="glass-panel border-purple-200/50 dark:border-purple-500/20 h-full">
                  <CardContent className="p-5">
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex items-center gap-3">
                        <div className={cn('flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br text-white shadow-md', cal.color)}>
                          <Icon className="h-5 w-5" />
                        </div>
                        <div>
                          <h3 className="text-base font-extrabold text-gray-900 dark:text-white">{cal.name}</h3>
                          <p className="text-xs text-gray-500">{state.connected ? t('common.status') : t('common.noData')}</p>
                        </div>
                      </div>
                      <Badge variant={state.connected ? 'success' : 'danger'} size="sm" dot>
                        {state.connected ? t('candidates.scheduled') : t('candidates.declined')}
                      </Badge>
                    </div>

                    {connecting === cal.id ? (
                      <div className="space-y-3">
                        <div>
                          <textarea
                            value={authInput}
                            onChange={(e) => setAuthInput(e.target.value)}
                            rows={2}
                            placeholder={cal.hint}
                            className="w-full rounded-xl border border-purple-200/60 bg-white/70 dark:bg-white/5 dark:border-white/10 dark:text-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-400 transition-all resize-none"
                          />
                        </div>
                        <div className="flex items-center gap-2">
                          <Button variant="primary" size="sm" className="flex-1" disabled={state.syncing} onClick={() => handleConnect(cal.id)} leftIcon={state.syncing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Link className="h-3.5 w-3.5" />}>
                            {state.syncing ? '...' : t('common.save')}
                          </Button>
                          <Button variant="ghost" size="sm" className="text-gray-400" onClick={() => { setConnecting(null); setAuthInput(''); }} leftIcon={<X className="h-3.5 w-3.5" />}>
                            {t('common.cancel')}
                          </Button>
                        </div>
                      </div>
                    ) : state.connected ? (
                      <Button variant="outline" size="sm" leftIcon={state.syncing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Unlink className="h-3.5 w-3.5" />} onClick={() => handleDisconnect(cal.id)} disabled={state.syncing} className="w-full text-red-500 border-red-200 hover:bg-red-50 dark:border-red-500/30 dark:hover:bg-red-500/10">
                        {state.syncing ? '...' : t('common.delete')}
                      </Button>
                    ) : (
                      <Button variant="primary" size="sm" leftIcon={<Link className="h-3.5 w-3.5" />} onClick={() => setConnecting(cal.id)} className="w-full">
                        {t('common.edit')}
                      </Button>
                    )}
                  </CardContent>
                </Card>
              </motion.div>
            );
          })}
        </motion.div>
      )}
    </div>
  );
}
