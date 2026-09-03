import { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router';
import { useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Switch } from '@/shared/components/ui/switch';
import { Badge } from '@/shared/components/ui/badge';
import { Avatar } from '@/shared/components/ui/avatar';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/shared/components/ui/tabs';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/shared/components/ui/select';
import { useAuth } from '@/contexts/auth-context';
import { useTheme } from '@/contexts/theme-context';
import { useLanguage } from '@/contexts/language-context';
import { customToast } from '@/shared/components/ui/toast';
import apiClient from '@/lib/api-client';
import { adminService } from '@/services/admin.service';
import { settingsService, type RecruiterSettings, type SubscriptionStatus } from '@/services/settings.service';
import { subscriptionService } from '@/services/subscription.service';
import { cvReviewService, type CandidateUsage } from '@/services/cv-review.service';
import { candidateService } from '@/services/candidate.service';
import {
  User, Bell, Shield, Palette, CreditCard, Globe, Key, Mail, Camera, Save, Loader2, Crown, Sparkles, Zap, Play, CheckCircle, XCircle,
} from 'lucide-react';

export default function SettingsPage() {
  const { user } = useAuth();
  const { theme, setTheme } = useTheme();
  const { t } = useLanguage();
  const { tab } = useParams();
  const queryClient = useQueryClient();
  const isCandidate = user?.role === 'candidate';
  const isAdmin = user?.role === 'admin';
  const adminTabSet = ['profile', 'admin', 'security', 'appearance'];
  const userTabSet = ['profile', 'notifications', 'security', 'appearance', 'subscription', 'billing'];
  const [activeTab, setActiveTab] = useState(() =>
    tab && (isAdmin ? adminTabSet : userTabSet).includes(tab) ? tab : 'profile'
  );

  const [settings, setSettings] = useState<RecruiterSettings | null>(null);
  const [systemSettings, setSystemSettings] = useState<Record<string, unknown>>({});
  const [adminConfig, setAdminConfig] = useState<Record<string, any>>({
    maintenance_mode: false,
    free_trial: true,
    platform_fee_percent: 20,
    default_language: 'en',
    smtp_host: '',
    smtp_port: 587,
    smtp_username: '',
    smtp_password: '',
    groq_api_key: '',
    deepseek_api_key: '',
    gemini_api_key: '',
    ai_provider: 'groq',
    ai_model: 'groq/compound',
    ai_temperature: 0.5,
    use_local_llm: false,
    local_llm_url: 'http://127.0.0.1:11434',
    local_llm_model: 'llama3',
    bank_name: '',
    bank_account_name: '',
    bank_account_number: '',
    bank_iban: '',
    payment_instructions: '',
    automations_enabled: true,
    google_client_id: '',
    google_client_secret: '',
    google_enabled: false,
    ab_test_enabled: false,
    ab_test_bucket_size: 10,
  });
  const [subscription, setSubscription] = useState<SubscriptionStatus | null>(null);
  const [candidateUsage, setCandidateUsage] = useState<CandidateUsage | null>(null);
  const [candidatePlans, setCandidatePlans] = useState<any[]>([]);
  const [recruiterPlans, setRecruiterPlans] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testingModel, setTestingModel] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; model: string; response?: string; error?: string } | null>(null);

  const GROQ_MODELS = [
    { id: 'groq/compound', label: 'Groq Compound (Recommended)', description: 'Routes to best available model' },
    { id: 'groq/compound-mini', label: 'Groq Compound Mini', description: 'Lighter, faster compound routing' },
    { id: 'openai/gpt-oss-20b', label: 'OpenAI GPT-OSS 20B', description: 'Reasoning model on Groq' },
    { id: 'openai/gpt-oss-120b', label: 'OpenAI GPT-OSS 120B', description: 'Large reasoning model (no json_mode)' },
  ];
  const GEMINI_MODELS = [
    { id: 'gemini-3.6-flash', label: 'Gemini 3.6 Flash (Recommended)', description: 'Latest, fastest, multimodal' },
    { id: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash', description: 'Fast, multimodal' },
    { id: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash', description: 'Fast, cost-efficient' },
  ];
  const AVAILABLE_AI_MODELS = adminConfig.ai_provider === 'gemini' ? GEMINI_MODELS : GROQ_MODELS;

  const [form, setForm] = useState({ name: '', location: '', phone: '', bio: '', avatar: '' });
  const [passwordForm, setPasswordForm] = useState({ current: '', newPass: '', confirm: '' });
  const [notifications, setNotifications] = useState<Record<string, boolean>>(() => {
    try { return JSON.parse(localStorage.getItem('candidate_notifications') || '{}'); } catch { return {}; }
  });
  const [compactMode, setCompactMode] = useState(() => localStorage.getItem('compactMode') === 'true');
  const avatarInputRef = useRef<HTMLInputElement>(null);

  const normalizeAdminSettings = (response: Record<string, unknown> = {}) => ({
    maintenance_mode: Boolean(response.maintenance_mode),
    free_trial: Boolean(response.free_trial),
    platform_fee_percent: Number(response.platform_fee_percent ?? 20),
    default_language: String(response.default_language || 'en'),
    smtp_host: String(response.smtp_host || ''),
    smtp_port: Number(response.smtp_port ?? 587),
    smtp_username: String(response.smtp_username || ''),
    smtp_password: String(response.smtp_password || ''),
    groq_api_key: String(response.groq_api_key || ''),
    deepseek_api_key: String(response.deepseek_api_key || ''),
    gemini_api_key: String(response.gemini_api_key || ''),
    ai_provider: String(response.ai_provider || 'groq'),
    ai_model: String(response.ai_model || 'groq/compound'),
    ai_temperature: Number(response.ai_temperature ?? 0.5),
    use_local_llm: Boolean(response.use_local_llm),
    local_llm_url: String(response.local_llm_url || 'http://127.0.0.1:11434'),
    local_llm_model: String(response.local_llm_model || 'llama3'),
    bank_name: String(response.bank_name || ''),
    bank_account_name: String(response.bank_account_name || ''),
    bank_account_number: String(response.bank_account_number || ''),
    bank_iban: String(response.bank_iban || ''),
    payment_instructions: String(response.payment_instructions || ''),
    automations_enabled: response.automations_enabled !== false,
    google_client_id: String(response.google_client_id || ''),
    google_client_secret: String(response.google_client_secret || ''),
    google_enabled: Boolean(response.google_enabled),
    ab_test_enabled: Boolean(response.ab_test_enabled),
    ab_test_bucket_size: Number(response.ab_test_bucket_size ?? 10),
    ai_credit_gating_enabled: response.ai_credit_gating_enabled !== false,
    ai_credit_costs: (response.ai_credit_costs && typeof response.ai_credit_costs === 'object'
      ? { ...(response.ai_credit_costs as Record<string, unknown>) }
      : {}),
  });

  useEffect(() => {
    setLoading(true);

    if (isAdmin) {
      adminService.getSystemSettings()
        .then((response) => {
          const nextSettings = (response || {}) as Record<string, unknown>;
          setSystemSettings(nextSettings);
          setAdminConfig(normalizeAdminSettings(nextSettings));
        })
        .catch(() => {
          setSystemSettings({} as Record<string, unknown>);
          setAdminConfig({
            maintenance_mode: false,
            free_trial: true,
            platform_fee_percent: 20,
            default_language: 'en',
            smtp_host: '',
            smtp_port: 587,
            smtp_username: '',
            smtp_password: '',
            groq_api_key: '',
            deepseek_api_key: '',
            gemini_api_key: '',
            ai_provider: 'groq',
            ai_model: 'groq/compound',
            ai_temperature: 0.5,
            use_local_llm: false,
            local_llm_url: 'http://127.0.0.1:11434',
            local_llm_model: 'llama3',
            bank_name: '',
            bank_account_name: '',
            bank_account_number: '',
            bank_iban: '',
            payment_instructions: '',
            automations_enabled: true,
            google_client_id: '',
            google_client_secret: '',
            google_enabled: false,
            ab_test_enabled: false,
            ab_test_bucket_size: 10,
            ai_credit_gating_enabled: true,
            ai_credit_costs: {},
          });
        })
        .finally(() => setLoading(false));
      return;
    }

    const candidateLoad = Promise.all([
      candidateService.getProfile().catch(() => null),
      cvReviewService.getCandidateUsage().catch(() => null),
      cvReviewService.getCandidatePlans().catch(() => null),
    ]).then(([profile, candUsage, candPlans]) => {
      if (profile) {
        setForm(f => ({
          ...f,
          name: profile.name || f.name,
          location: profile.location || f.location,
          phone: profile.phone || f.phone,
          bio: profile.bio || f.bio,
          avatar: profile.avatar || profile.avatar_url || f.avatar,
        }));
      }
      if (candUsage) setCandidateUsage(candUsage);
      if (Array.isArray(candPlans)) setCandidatePlans(candPlans);
    });

    const recruiterLoad = Promise.all([
      settingsService.getRecruiterSettings().catch(() => null),
      settingsService.getSubscriptionStatus().catch(() => null),
      settingsService.getEmailSettings().catch(() => null),
      subscriptionService.getPlans().catch(() => []),
    ]).then(([s, sub, email, rPlans]) => {
      if (s) setSettings(s);
      if (sub) setSubscription(sub);
      if (email) setNotifications({ auto_email_enabled: email.auto_email_enabled });
      if (Array.isArray(rPlans)) setRecruiterPlans(rPlans);
    });

    (isCandidate ? candidateLoad : recruiterLoad).finally(() => setLoading(false));
  }, [isCandidate, isAdmin]);

  useEffect(() => {
    if (user) {
      setForm(f => ({
        ...f,
        name: f.name || [user.firstName, user.lastName].filter(Boolean).join(' ').trim(),
      }));
    }
  }, [user]);

  const handleSaveProfile = async () => {
    if (isAdmin) {
      customToast({ type: 'info', title: t('settings.adminSettings'), message: t('settings.adminSettingsMsg') });
      return;
    }

    setSaving(true);
    try {
      const body = {
        name: form.name.trim(),
        location: form.location,
        phone: form.phone,
        bio: form.bio,
      };
      if (isCandidate) {
        await candidateService.updateProfile(body);
      } else {
        await settingsService.updateRecruiterSettings({ company_name: settings?.company_name || '' });
      }
      await apiClient.put('/auth/me', body);
      customToast({ type: 'success', title: t('own.saved'), message: t('settings.profileUpdated') });
    } catch {
      customToast({ type: 'error', title: t('auth.errorTitle'), message: t('settings.profileSaveFailed') });
    } finally {
      setSaving(false);
    }
  };

  const handleSaveAdminSettings = async () => {
    const payload: Record<string, unknown> = {
      maintenance_mode: Boolean(adminConfig.maintenance_mode),
      free_trial: Boolean(adminConfig.free_trial),
      platform_fee_percent: Number(adminConfig.platform_fee_percent ?? 20),
      default_language: String(adminConfig.default_language || 'en'),
      smtp_host: String(adminConfig.smtp_host || ''),
      smtp_port: Number(adminConfig.smtp_port ?? 587),
      smtp_username: String(adminConfig.smtp_username || ''),
      ai_provider: String(adminConfig.ai_provider || 'groq'),
      ai_model: String(adminConfig.ai_model || 'groq/compound'),
      ai_temperature: Number(adminConfig.ai_temperature ?? 0.5),
      use_local_llm: Boolean(adminConfig.use_local_llm),
      local_llm_url: String(adminConfig.local_llm_url || 'http://127.0.0.1:11434'),
      local_llm_model: String(adminConfig.local_llm_model || 'llama3'),
      bank_name: String(adminConfig.bank_name || ''),
      bank_account_name: String(adminConfig.bank_account_name || ''),
      bank_account_number: String(adminConfig.bank_account_number || ''),
      bank_iban: String(adminConfig.bank_iban || ''),
      payment_instructions: String(adminConfig.payment_instructions || ''),
      automations_enabled: adminConfig.automations_enabled !== false,
      google_client_id: String(adminConfig.google_client_id || ''),
      google_enabled: Boolean(adminConfig.google_enabled),
      ab_test_enabled: Boolean(adminConfig.ab_test_enabled),
      ab_test_bucket_size: Number(adminConfig.ab_test_bucket_size ?? 10),
      ai_credit_gating_enabled: adminConfig.ai_credit_gating_enabled !== false,
      ai_credit_costs: adminConfig.ai_credit_costs && typeof adminConfig.ai_credit_costs === 'object'
        ? adminConfig.ai_credit_costs
        : {},
    };

    const secretKeys = ['smtp_password', 'groq_api_key', 'deepseek_api_key', 'gemini_api_key', 'google_client_secret'];
    for (const key of secretKeys) {
      const value = adminConfig[key];
      if (typeof value !== 'string') continue;
      if (!value || value.startsWith('*')) continue;
      payload[key] = value;
    }

    try {
      setSaving(true);
      await adminService.updateSystemSettings(payload);
      const refreshed = await adminService.getSystemSettings();
      setSystemSettings((refreshed || {}) as Record<string, unknown>);
      setAdminConfig(normalizeAdminSettings((refreshed || {}) as Record<string, unknown>));
      customToast({ type: 'success', title: t('own.saved'), message: t('settings.adminSettingsUpdated') });
    } catch (error: any) {
      customToast({ type: 'error', title: t('auth.errorTitle'), message: error?.message || t('settings.adminSettingsSaveFailed') });
    } finally {
      setSaving(false);
    }
  };

  const handleTestAIModel = async () => {
    const model = adminConfig.ai_model || 'groq/compound';
    const provider = adminConfig.ai_provider || 'groq';
    const apiKey = provider === 'gemini' ? adminConfig.gemini_api_key : adminConfig.groq_api_key;
    setTestingModel(true);
    setTestResult(null);
    try {
      const result = await apiClient.post('/admin/ai/test-model', {
        model,
        provider,
        api_key: (!apiKey || apiKey.startsWith('*')) ? undefined : apiKey,
      });
      setTestResult(result as any);
      if ((result as any)?.success) {
        customToast({ type: 'success', title: 'Model OK', message: `${model} responded successfully` });
      } else {
        customToast({ type: 'error', title: 'Model Failed', message: (result as any)?.error || 'Unknown error' });
      }
    } catch (error: any) {
      const msg = error?.response?.data?.error || error?.message || 'Connection failed';
      setTestResult({ success: false, model, error: msg });
      customToast({ type: 'error', title: 'Test Failed', message: msg });
    } finally {
      setTestingModel(false);
    }
  };

  const handleChangePassword = async () => {
    if (passwordForm.newPass !== passwordForm.confirm) {
      customToast({ type: 'error', title: t('auth.errorTitle'), message: t('settings.passwordsMismatch') });
      return;
    }
    if (passwordForm.newPass.length < 8) {
      customToast({ type: 'error', title: t('auth.errorTitle'), message: t('settings.passwordMinLength') });
      return;
    }
    try {
      await settingsService.changePassword({ current_password: passwordForm.current, new_password: passwordForm.newPass });
      customToast({ type: 'success', title: t('settings.passwordUpdated'), message: t('settings.passwordChanged') });
      setPasswordForm({ current: '', newPass: '', confirm: '' });
    } catch {
      customToast({ type: 'error', title: t('auth.errorTitle'), message: t('settings.passwordChangeFailed') });
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-purple-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{t('common.settings')}</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{t('settings.subtitle')}</p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="w-full justify-start overflow-x-auto">
          <TabsTrigger value="profile" className="gap-2"><User className="h-4 w-4" /> {t('settings.tabProfile')}</TabsTrigger>
          {isAdmin && <TabsTrigger value="admin" className="gap-2"><Shield className="h-4 w-4" /> {t('settings.tabPlatform')}</TabsTrigger>}
          {!isAdmin && <TabsTrigger value="notifications" className="gap-2"><Bell className="h-4 w-4" /> {t('settings.tabNotifications')}</TabsTrigger>}
          <TabsTrigger value="security" className="gap-2"><Shield className="h-4 w-4" /> {t('settings.tabSecurity')}</TabsTrigger>
          <TabsTrigger value="appearance" className="gap-2"><Palette className="h-4 w-4" /> {t('settings.tabAppearance')}</TabsTrigger>
          {!isAdmin && <TabsTrigger value="subscription" className="gap-2"><Crown className="h-4 w-4" /> {t('settings.tabSubscription')}</TabsTrigger>}
          {!isAdmin && <TabsTrigger value="billing" className="gap-2"><CreditCard className="h-4 w-4" /> {t('settings.tabBilling')}</TabsTrigger>}
        </TabsList>

        <TabsContent value="profile">
          <Card>
            <CardHeader>
              <CardTitle>{t('settings.profileInfo')}</CardTitle>
              <CardDescription>{t('settings.profileInfoDesc')}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                <div className="flex items-center gap-4">
                  <Avatar name={form.name} src={form.avatar} size="xl" />
                  <div>
                    <input ref={avatarInputRef} type="file" accept="image/*" className="hidden" onChange={async (e) => {
                      const file = e.target.files?.[0];
                      if (!file) return;
                      const formData = new FormData();
                      formData.append('file', file);
                      try {
                        const res = await candidateService.uploadAvatar(formData);
                        const url = res?.url;
                        if (url) setForm(f => ({ ...f, avatar: url }));
                        await queryClient.invalidateQueries({ queryKey: ['auth', 'profile'] });
                        customToast({ type: 'success', title: t('settings.avatarUpdated'), message: t('settings.avatarUpdatedMsg') });
                      } catch { customToast({ type: 'error', title: t('settings.uploadFailed'), message: t('settings.avatarUpdateFailed') }); }
                      e.target.value = '';
                    }} />
                    <Button variant="outline" size="sm" leftIcon={<Camera className="h-4 w-4" />} onClick={() => avatarInputRef.current?.click()}>{t('settings.changeAvatar')}</Button>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{t('settings.avatarHint')}</p>
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Input label={t('settings.fullName')} value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder={t('settings.fullNamePlaceholder')} />
                  <Input label={t('common.email')} defaultValue={user?.email} leftIcon={<Mail className="h-4 w-4" />} disabled />
                  <Input label={t('settings.roleLabel')} defaultValue={user?.role} disabled />
                  <Input label={t('common.location')} value={form.location} onChange={e => setForm(f => ({ ...f, location: e.target.value }))} placeholder={t('settings.locationPlaceholder')} leftIcon={<Globe className="h-4 w-4" />} />
                  <Input label={t('common.phone')} value={form.phone} onChange={e => setForm(f => ({ ...f, phone: e.target.value }))} placeholder={t('settings.phonePlaceholder')} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">{t('settings.bioLabel')}</label>
                  <textarea value={form.bio} onChange={e => setForm(f => ({ ...f, bio: e.target.value }))}
                    className="flex min-h-[100px] w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 dark:border-white/10 dark:bg-white/5 dark:text-white dark:placeholder:text-gray-500"
                    placeholder={t('settings.bioPlaceholder')} />
                </div>
                {!isAdmin && (
                  <div className="flex justify-end">
                    <Button variant="primary" leftIcon={<Save className="h-4 w-4" />} onClick={handleSaveProfile} disabled={saving}>
                      {saving ? t('settings.saving') : t('settings.saveChanges')}
                    </Button>
                  </div>
                )}

                {isAdmin && (
                  <>
                    <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
                      {t('settings.adminProfileNotice')}
                    </div>

                    {Object.keys(systemSettings).length > 0 && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {([
                          [t('settings.aiProvider'), systemSettings.ai_provider],
                          [t('settings.aiModel'), systemSettings.ai_model],
                          [t('settings.maintenanceMode'), systemSettings.maintenance_mode ? t('settings.enabled') : t('settings.disabled')],
                          [t('settings.defaultLanguage'), systemSettings.default_language],
                        ] as [string, unknown][]).map(([label, value]) => (
                          <div key={label} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                            <div className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">{label}</div>
                            <div className="mt-1 text-sm font-semibold text-slate-800">{String(value ?? '—')}</div>
                          </div>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {isAdmin && (
          <TabsContent value="admin">
            <Card>
              <CardHeader>
                <CardTitle>{t('settings.platformConfig')}</CardTitle>
                <CardDescription>{t('settings.platformConfigDesc')}</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-8">
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="text-sm font-semibold text-slate-900">{t('settings.emergencyMaintenance')}</div>
                        <div className="text-xs text-slate-500">{t('settings.emergencyMaintenanceDesc')}</div>
                      </div>
                      <Switch checked={Boolean(adminConfig.maintenance_mode)} onCheckedChange={(value) => setAdminConfig((prev) => ({ ...prev, maintenance_mode: value }))} />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <Input label={t('settings.platformCommission')} type="number" value={String(adminConfig.platform_fee_percent ?? 20)} onChange={(e) => setAdminConfig((prev) => ({ ...prev, platform_fee_percent: Number(e.target.value || 0) }))} />
                    <Input label={t('settings.trialDuration')} type="number" value={String(adminConfig.free_trial ? 14 : 0)} onChange={() => {}} disabled />
                    <Input label={t('settings.defaultLanguage')} value={String(adminConfig.default_language || 'en')} onChange={(e) => setAdminConfig((prev) => ({ ...prev, default_language: e.target.value }))} />
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">{t('settings.aiProvider')}</label>
                      <Select
                        value={adminConfig.ai_provider || 'groq'}
                        onValueChange={(value) => {
                          const defaultModel = value === 'gemini' ? 'gemini-3.6-flash' : 'groq/compound';
                          setAdminConfig((prev) => ({ ...prev, ai_provider: value, ai_model: defaultModel }));
                          setTestResult(null);
                        }}
                      >
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Select provider" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="groq">
                            <div className="flex flex-col">
                              <span>Groq</span>
                              <span className="text-xs text-gray-400">Fast inference, compound routing</span>
                            </div>
                          </SelectItem>
                          <SelectItem value="gemini">
                            <div className="flex flex-col">
                              <span>Google Gemini</span>
                              <span className="text-xs text-gray-400">Multimodal, large context window</span>
                            </div>
                          </SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">{t('settings.aiModel')}</label>
                      <Select value={adminConfig.ai_model || 'groq/compound'} onValueChange={(value) => setAdminConfig((prev) => ({ ...prev, ai_model: value }))}>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Select AI model" />
                        </SelectTrigger>
                        <SelectContent>
                          {AVAILABLE_AI_MODELS.map((m) => (
                            <SelectItem key={m.id} value={m.id}>
                              <div className="flex flex-col">
                                <span>{m.label}</span>
                                <span className="text-xs text-gray-400">{m.description}</span>
                              </div>
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <p className="mt-1 text-xs text-gray-400">Active: <code className="text-purple-600">{adminConfig.ai_model || 'groq/compound'}</code></p>
                    </div>
                    <Input label={t('settings.aiTemperature')} type="number" step="0.1" value={String(adminConfig.ai_temperature ?? 0.5)} onChange={(e) => setAdminConfig((prev) => ({ ...prev, ai_temperature: Number(e.target.value || 0) }))} />
                  </div>

                  <div className="flex items-center gap-3">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={handleTestAIModel}
                      disabled={testingModel}
                      className="gap-2"
                    >
                      {testingModel ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                      {testingModel ? 'Testing...' : 'Test Model'}
                    </Button>
                    {testResult && (
                      <div className="flex items-center gap-2 text-sm">
                        {testResult.success ? (
                          <>
                            <CheckCircle className="h-4 w-4 text-green-500" />
                            <span className="text-green-700">{testResult.model} OK</span>
                            {testResult.response && <span className="text-gray-400 truncate max-w-xs">— {testResult.response}</span>}
                          </>
                        ) : (
                          <>
                            <XCircle className="h-4 w-4 text-red-500" />
                            <span className="text-red-700">{testResult.error}</span>
                          </>
                        )}
                      </div>
                    )}
                  </div>

                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <div className="mb-4 text-sm font-semibold text-slate-900">{t('settings.aiCredentials')}</div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <Input label={t('settings.groqApiKey')} type="password" value={String(adminConfig.groq_api_key || '')} onChange={(e) => setAdminConfig((prev) => ({ ...prev, groq_api_key: e.target.value }))} />
                      <Input label={t('settings.deepseekApiKey')} type="password" value={String(adminConfig.deepseek_api_key || '')} onChange={(e) => setAdminConfig((prev) => ({ ...prev, deepseek_api_key: e.target.value }))} />
                      <Input label={t('settings.geminiApiKey')} type="password" value={String(adminConfig.gemini_api_key || '')} onChange={(e) => setAdminConfig((prev) => ({ ...prev, gemini_api_key: e.target.value }))} />
                      <Input label={t('settings.googleClientId')} value={String(adminConfig.google_client_id || '')} onChange={(e) => setAdminConfig((prev) => ({ ...prev, google_client_id: e.target.value }))} />
                    </div>
                  </div>

                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <div className="mb-4 text-sm font-semibold text-slate-900">{t('settings.smtpAutomation')}</div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <Input label={t('settings.smtpHost')} value={String(adminConfig.smtp_host || '')} onChange={(e) => setAdminConfig((prev) => ({ ...prev, smtp_host: e.target.value }))} />
                      <Input label={t('settings.smtpPort')} type="number" value={String(adminConfig.smtp_port ?? 587)} onChange={(e) => setAdminConfig((prev) => ({ ...prev, smtp_port: Number(e.target.value || 587) }))} />
                      <Input label={t('settings.smtpUsername')} value={String(adminConfig.smtp_username || '')} onChange={(e) => setAdminConfig((prev) => ({ ...prev, smtp_username: e.target.value }))} />
                      <Input label={t('settings.smtpPassword')} type="password" value={String(adminConfig.smtp_password || '')} onChange={(e) => setAdminConfig((prev) => ({ ...prev, smtp_password: e.target.value }))} />
                    </div>
                    <div className="mt-4 flex items-center justify-between rounded-xl border border-slate-200 bg-white p-3">
                      <div>
                        <div className="text-sm font-medium text-slate-900">{t('settings.automationEngine')}</div>
                        <div className="text-xs text-slate-500">{t('settings.automationEngineDesc')}</div>
                      </div>
                      <Switch checked={Boolean(adminConfig.automations_enabled)} onCheckedChange={(value) => setAdminConfig((prev) => ({ ...prev, automations_enabled: value }))} />
                    </div>
                  </div>

                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <div className="mb-4 text-sm font-semibold text-slate-900">{t('settings.manualPaymentDetails')}</div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <Input label={t('settings.bankName')} value={String(adminConfig.bank_name || '')} onChange={(e) => setAdminConfig((prev) => ({ ...prev, bank_name: e.target.value }))} />
                      <Input label={t('settings.accountHolder')} value={String(adminConfig.bank_account_name || '')} onChange={(e) => setAdminConfig((prev) => ({ ...prev, bank_account_name: e.target.value }))} />
                      <Input label={t('settings.accountNumber')} value={String(adminConfig.bank_account_number || '')} onChange={(e) => setAdminConfig((prev) => ({ ...prev, bank_account_number: e.target.value }))} />
                      <Input label={t('settings.iban')} value={String(adminConfig.bank_iban || '')} onChange={(e) => setAdminConfig((prev) => ({ ...prev, bank_iban: e.target.value }))} />
                    </div>
                    <div className="mt-4">
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">{t('settings.paymentInstructions')}</label>
                      <textarea value={String(adminConfig.payment_instructions || '')} onChange={(e) => setAdminConfig((prev) => ({ ...prev, payment_instructions: e.target.value }))}
                        className="flex min-h-[100px] w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 dark:border-white/10 dark:bg-white/5 dark:text-white dark:placeholder:text-gray-500" />
                    </div>
                  </div>

                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <div className="mb-4 text-sm font-semibold text-slate-900">{t('settings.aiCreditPricing')}</div>
                    <div className="mb-4 flex items-center justify-between rounded-xl border border-slate-200 bg-white p-3">
                      <div>
                        <div className="text-sm font-medium text-slate-900">{t('settings.creditGatingEnabled')}</div>
                        <div className="text-xs text-slate-500">{t('settings.creditGatingEnabledDesc')}</div>
                      </div>
                      <Switch checked={adminConfig.ai_credit_gating_enabled !== false} onCheckedChange={(value) => setAdminConfig((prev) => ({ ...prev, ai_credit_gating_enabled: value }))} />
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {[
                        ['cv_analysis', t('settings.creditCvAnalysis')],
                        ['ai_interview_evaluation', t('settings.creditAiInterviewEvaluation')],
                        ['interview_question_gen', t('settings.creditInterviewQuestionGen')],
                        ['ai_search', t('settings.creditAiSearch')],
                        ['career_roadmap', t('settings.creditCareerRoadmap')],
                        ['jd_writer', t('settings.creditJdWriter')],
                        ['copilot_chat', t('settings.creditCopilotChat')],
                        ['pdf_report', t('settings.creditPdfReport')],
                        ['ai_invitation', t('settings.creditAiInvitation')],
                        ['score_comparison', t('settings.creditScoreComparison')],
                        ['debrief_summary', t('settings.creditDebriefSummary')],
                        ['translation', t('settings.creditTranslation')],
                        ['career_chatbot', t('settings.creditCareerChatbot')],
                        ['wizard_suggest', t('settings.creditWizardSuggest')],
                        ['skill_tree_generate', t('settings.creditSkillTreeGenerate')],
                      ].map(([key, label]) => {
                        const costs = adminConfig.ai_credit_costs || {};
                        const current = typeof costs[key] === 'number' ? Number(costs[key]) : 1;
                        return (
                          <Input
                            key={key}
                            label={label}
                            type="number"
                            min={0}
                            value={String(current)}
                            onChange={(e) => {
                              const val = Math.max(0, Number(e.target.value || 0));
                              setAdminConfig((prev) => ({
                                ...prev,
                                ai_credit_costs: { ...(prev.ai_credit_costs || {}), [key]: val },
                              }));
                            }}
                          />
                        );
                      })}
                    </div>
                    <p className="mt-3 text-xs text-slate-500">{t('settings.creditPricingHint')}</p>
                  </div>

                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <div className="mb-4 text-sm font-semibold text-slate-900">{t('settings.localLlmOauth')}</div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-3 md:col-span-2">
                        <div>
                          <div className="text-sm font-medium text-slate-900">{t('settings.useLocalOllama')}</div>
                          <div className="text-xs text-slate-500">{t('settings.useLocalOllamaDesc')}</div>
                        </div>
                        <Switch checked={Boolean(adminConfig.use_local_llm)} onCheckedChange={(value) => setAdminConfig((prev) => ({ ...prev, use_local_llm: value }))} />
                      </div>
                      <Input label={t('settings.localLlmUrl')} value={String(adminConfig.local_llm_url || 'http://127.0.0.1:11434')} onChange={(e) => setAdminConfig((prev) => ({ ...prev, local_llm_url: e.target.value }))} />
                      <Input label={t('settings.localModel')} value={String(adminConfig.local_llm_model || 'llama3')} onChange={(e) => setAdminConfig((prev) => ({ ...prev, local_llm_model: e.target.value }))} />
                      <Input label={t('settings.googleClientSecret')} type="password" value={String(adminConfig.google_client_secret || '')} onChange={(e) => setAdminConfig((prev) => ({ ...prev, google_client_secret: e.target.value }))} />
                      <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-3">
                        <div>
                          <div className="text-sm font-medium text-slate-900">{t('settings.googleOauth')}</div>
                          <div className="text-xs text-slate-500">{t('settings.googleOauthDesc')}</div>
                        </div>
                        <Switch checked={Boolean(adminConfig.google_enabled)} onCheckedChange={(value) => setAdminConfig((prev) => ({ ...prev, google_enabled: value }))} />
                      </div>
                    </div>
                  </div>

                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <div className="mb-4 text-sm font-semibold text-slate-900">{t('settings.abTesting')}</div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-3">
                        <div>
                          <div className="text-sm font-medium text-slate-900">{t('settings.enableAbTesting')}</div>
                          <div className="text-xs text-slate-500">{t('settings.enableAbTestingDesc')}</div>
                        </div>
                        <Switch checked={Boolean(adminConfig.ab_test_enabled)} onCheckedChange={(value) => setAdminConfig((prev) => ({ ...prev, ab_test_enabled: value }))} />
                      </div>
                      <Input label={t('settings.bucketSize')} type="number" min={0} max={100} value={String(adminConfig.ab_test_bucket_size ?? 10)} onChange={(e) => setAdminConfig((prev) => ({ ...prev, ab_test_bucket_size: Number(e.target.value || 10) }))} />
                    </div>
                  </div>

                  <div className="flex justify-end">
                    <Button variant="primary" onClick={handleSaveAdminSettings} disabled={saving} leftIcon={saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}>
                      {saving ? t('settings.saving') : t('settings.savePlatformSettings')}
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        )}

        <TabsContent value="notifications">
          <Card>
            <CardHeader>
              <CardTitle>{t('settings.notificationPreferences')}</CardTitle>
              <CardDescription>{t('settings.notificationPreferencesDesc')}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                {[
                  { key: 'auto_email_enabled', title: t('settings.notifEmail'), description: t('settings.notifEmailDesc') },
                  { key: 'push', title: t('settings.notifPush'), description: t('settings.notifPushDesc') },
                  { key: 'applications', title: t('settings.notifApplications'), description: t('settings.notifApplicationsDesc') },
                  { key: 'interviews', title: t('settings.notifInterviews'), description: t('settings.notifInterviewsDesc') },
                  { key: 'digest', title: t('settings.notifDigest'), description: t('settings.notifDigestDesc') },
                  { key: 'marketing', title: t('settings.notifMarketing'), description: t('settings.notifMarketingDesc') },
                ].map((item) => (
                  <div key={item.key} className="flex items-center justify-between">
                    <div>
                      <div className="text-sm font-medium text-gray-900 dark:text-white">{item.title}</div>
                      <div className="text-sm text-gray-500 dark:text-gray-400">{item.description}</div>
                    </div>
                    <Switch
                      checked={notifications[item.key] ?? false}
                      onCheckedChange={(v) => {
                        const next = { ...notifications, [item.key]: v };
                        setNotifications(next);
                        if (item.key === 'auto_email_enabled' && !isCandidate) {
                          settingsService.updateEmailSettings({ auto_email_enabled: v }).catch(() => {});
                        }
                        if (isCandidate) {
                          localStorage.setItem('candidate_notifications', JSON.stringify(next));
                        }
                      }}
                    />
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="security">
          <Card>
            <CardHeader>
              <CardTitle>{t('settings.securitySettings')}</CardTitle>
              <CardDescription>{t('settings.securitySettingsDesc')}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                <div>
                  <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-4">{t('settings.changePassword')}</h3>
                  <div className="space-y-4 max-w-md">
                    <Input label={t('settings.currentPassword')} type="password" value={passwordForm.current} onChange={e => setPasswordForm(f => ({ ...f, current: e.target.value }))} leftIcon={<Key className="h-4 w-4" />} />
                    <Input label={t('auth.newPassword')} type="password" value={passwordForm.newPass} onChange={e => setPasswordForm(f => ({ ...f, newPass: e.target.value }))} leftIcon={<Key className="h-4 w-4" />} />
                    <Input label={t('auth.confirmPassword')} type="password" value={passwordForm.confirm} onChange={e => setPasswordForm(f => ({ ...f, confirm: e.target.value }))} leftIcon={<Key className="h-4 w-4" />} />
                    <Button variant="primary" size="sm" onClick={handleChangePassword}>{t('settings.updatePassword')}</Button>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="appearance">
          <Card>
            <CardHeader>
              <CardTitle>{t('settings.tabAppearance')}</CardTitle>
              <CardDescription>{t('settings.appearanceDesc')}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                <div>
                  <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-4">{t('common.theme')}</h3>
                  <div className="grid grid-cols-3 gap-3">
                    {[
                      { value: 'light', label: t('common.light'), icon: '☀️' },
                      { value: 'dark', label: t('common.dark'), icon: '🌙' },
                      { value: 'system', label: t('common.system'), icon: '💻' },
                    ].map((t) => (
                      <button key={t.value} onClick={() => setTheme(t.value as any)}
                        className={`flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all ${
                          theme === t.value
                            ? 'border-blue-600 bg-blue-50/50 dark:bg-blue-500/10 dark:border-blue-400'
                            : 'border-gray-200 hover:border-gray-300 dark:border-white/10 dark:hover:border-white/20'
                        }`}>
                        <span className="text-2xl">{t.icon}</span>
                        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">{t.label}</span>
                      </button>
                    ))}
                  </div>
                </div>
                <div className="border-t border-gray-100 dark:border-white/[0.06] pt-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm font-medium text-gray-900 dark:text-white">{t('settings.compactMode')}</div>
                      <div className="text-sm text-gray-500 dark:text-gray-400">{t('settings.compactModeDesc')}</div>
                    </div>
                    <Switch checked={compactMode} onCheckedChange={(v) => { setCompactMode(v); localStorage.setItem('compactMode', String(v)); customToast({ type: 'success', title: t('settings.preferenceSaved'), message: v ? t('settings.compactModeEnabled') : t('settings.compactModeDisabled') }); }} />
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="subscription">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Crown className="h-5 w-5 text-purple-600" />
                {t('settings.subscriptionPlanQuotas')}
              </CardTitle>
              <CardDescription>{t('settings.subscriptionDesc')}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                {/* Active Plan Card */}
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between p-5 rounded-2xl bg-gradient-to-r from-purple-500/10 via-indigo-500/10 to-transparent border border-purple-200 dark:border-purple-500/20 gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-lg font-bold text-gray-900 dark:text-white uppercase tracking-wider">
                        {candidateUsage?.tier || subscription?.plan_name || t('settings.freeTier')}
                      </span>
                      <Badge variant="success" size="sm">
                        {candidateUsage?.subscription_status || subscription?.status || t('common.active')}
                      </Badge>
                    </div>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      {t('settings.roleAccountLabel')} <strong className="capitalize">{user?.role || 'candidate'}</strong>
                    </p>
                  </div>
                  {user?.role === 'recruiter' || user?.role === 'admin' ? (
                    <Button variant="primary" size="sm" onClick={() => setActiveTab('billing')}>
                      {t('settings.manageBilling')} →
                    </Button>
                  ) : (
                    <Button variant="primary" size="sm" onClick={() => setActiveTab('subscription')}>
                      {t('settings.explorePlans')}
                    </Button>
                  )}
                </div>

                {/* Quotas & Usage Breakdown */}
                <div>
                  <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3">{t('settings.resourceUsage')}</h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* CV Uploads */}
                    <div className="p-4 rounded-xl border border-gray-100 dark:border-white/[0.06] bg-gray-50/50 dark:bg-white/[0.02]">
                      <div className="flex items-center justify-between text-xs font-bold mb-1">
                        <span className="text-gray-900 dark:text-white flex items-center gap-1.5">
                          <Zap className="h-3.5 w-3.5 text-purple-600" /> {t('settings.cvAnalyses')}
                        </span>
                        <span className="text-purple-600">
                          {candidateUsage?.cv_uploads_used ?? subscription?.usage?.cvs ?? 0} / {candidateUsage?.cv_uploads_limit === -1 ? '∞' : (candidateUsage?.cv_uploads_limit ?? subscription?.limits?.cv_limit ?? '∞')}
                        </span>
                      </div>
                      <div className="w-full bg-gray-200 dark:bg-gray-700 h-2 rounded-full overflow-hidden mt-2">
                        <div
                          className="bg-purple-600 h-full rounded-full transition-all"
                          style={{
                            width: candidateUsage?.cv_uploads_limit === -1 ? '10%' : `${Math.min(100, (((candidateUsage?.cv_uploads_used ?? 0) / (candidateUsage?.cv_uploads_limit || 1)) * 100))}%`
                          }}
                        />
                      </div>
                    </div>

                    {/* AI Interviews / Jobs */}
                    <div className="p-4 rounded-xl border border-gray-100 dark:border-white/[0.06] bg-gray-50/50 dark:bg-white/[0.02]">
                      <div className="flex items-center justify-between text-xs font-bold mb-1">
                        <span className="text-gray-900 dark:text-white flex items-center gap-1.5">
                          <Sparkles className="h-3.5 w-3.5 text-blue-600" /> {t('settings.aiInterviews')}
                        </span>
                        <span className="text-blue-600">
                          {candidateUsage?.ai_interviews_used ?? subscription?.usage?.ai_interviews ?? 0} / {candidateUsage?.ai_interviews_limit === -1 ? '∞' : (candidateUsage?.ai_interviews_limit ?? subscription?.limits?.ai_interview_limit ?? '∞')}
                        </span>
                      </div>
                      <div className="w-full bg-gray-200 dark:bg-gray-700 h-2 rounded-full overflow-hidden mt-2">
                        <div
                          className="bg-blue-600 h-full rounded-full transition-all"
                          style={{
                            width: candidateUsage?.ai_interviews_limit === -1 ? '10%' : `${Math.min(100, (((candidateUsage?.ai_interviews_used ?? 0) / (candidateUsage?.ai_interviews_limit || 1)) * 100))}%`
                          }}
                        />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Upgrade Plans — role-aware */}
                {isCandidate && candidatePlans.length > 0 && (
                  <div className="border-t pt-4">
                    <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3">{t('settings.availableUpgradePlans')}</h4>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                      {candidatePlans.map((p: any) => (
                        <div key={p.id || p.slug} className="p-4 rounded-xl border border-purple-200/60 dark:border-purple-500/20 bg-white dark:bg-white/[0.02] flex flex-col justify-between">
                          <div>
                            <span className="text-sm font-bold text-gray-900 dark:text-white">{p.name}</span>
                            <div className="text-lg font-black text-purple-600 dark:text-purple-400 mt-1">
                              ${p.price_monthly || p.price || 0}<span className="text-xs font-normal text-gray-500">{t('settings.perMonth')}</span>
                            </div>
                            <p className="text-xs text-gray-500 mt-2">{p.description || t('settings.planFallbackDesc')}</p>
                          </div>
                          <Button
                            variant="outline"
                            size="sm"
                            className="mt-4 w-full"
                            onClick={async () => {
                              try {
                                await cvReviewService.requestUpgrade(p.id);
                                customToast({ type: 'success', title: t('settings.requested'), message: t('settings.upgradeRequestSubmitted') });
                              } catch {
                                customToast({ type: 'error', title: t('auth.errorTitle'), message: t('settings.upgradeRequestFailed') });
                              }
                            }}
                          >
                            {t('settings.upgrade')}
                          </Button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {!isCandidate && recruiterPlans.length > 0 && (
                  <div className="border-t pt-4">
                    <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3">{t('settings.availableUpgradePlans')}</h4>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                      {recruiterPlans.filter((p: any) => p.price_monthly > 0).map((p: any) => (
                        <div key={p.id || p.slug} className="p-4 rounded-xl border border-purple-200/60 dark:border-purple-500/20 bg-white dark:bg-white/[0.02] flex flex-col justify-between">
                          <div>
                            <span className="text-sm font-bold text-gray-900 dark:text-white">{p.name}</span>
                            <div className="text-lg font-black text-purple-600 dark:text-purple-400 mt-1">
                              {p.price_monthly || 0} {p.currency || 'TND'}<span className="text-xs font-normal text-gray-500">{t('settings.perMonth')}</span>
                            </div>
                            <p className="text-xs text-gray-500 mt-2">{p.description || t('settings.recruiterPlanFallbackDesc')}</p>
                          </div>
                          <Button
                            variant="primary"
                            size="sm"
                            className="mt-4 w-full"
                            onClick={() => setActiveTab('billing')}
                          >
                            {t('settings.manageBilling')} →
                          </Button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="billing">
          <Card>
            <CardHeader>
              <CardTitle>{t('settings.subscriptionBilling')}</CardTitle>
              <CardDescription>{t('settings.subscriptionBillingDesc')}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                <div className="flex items-center justify-between p-4 rounded-xl bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/20">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-gray-900 dark:text-white">
                        {subscription?.plan_name || t('settings.loading')}
                      </span>
                      <Badge variant={subscription?.status === 'active' ? 'success' : 'warning'} size="sm">
                        {subscription?.status || t('settings.unknown')}
                      </Badge>
                    </div>
                    <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                      {subscription?.usage?.jobs ?? 0}/{subscription?.limits?.job_limit ?? '∞'} {t('settings.jobsUsed')} ·
                      {subscription?.usage?.cvs ?? 0}/{subscription?.limits?.cv_limit ?? '∞'} {t('settings.cvsUsed')}
                      {subscription?.expiry ? ` · ${t('settings.expires')} ${new Date(subscription.expiry).toLocaleDateString()}` : ''}
                    </p>
                  </div>
                  <Button variant="outline" size="sm">{t('settings.managePlan')}</Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}