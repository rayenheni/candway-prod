import { useCallback, useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { useLanguage } from '@/contexts/language-context';
import { cn } from '@/utils/cn';
import { Loader2, UserPlus, RotateCcw, UserCheck, UserX, Coins } from 'lucide-react';
import { orgService, type OrgMember } from '@/services/org.service';
import { customToast } from '@/shared/components/ui/toast';
import { Users as UsersIcon } from 'lucide-react';

const ROLE_BADGES: Record<string, string> = {
  owner: 'bg-purple-100 text-purple-700 dark:bg-purple-500/20 dark:text-purple-300',
  admin: 'bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-300',
  recruiter: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300',
  member: 'bg-gray-100 text-gray-700 dark:bg-gray-500/20 dark:text-gray-300',
};

export default function OrgMembersPage() {
  const { t } = useLanguage();
  const [members, setMembers] = useState<OrgMember[]>([]);
  const [seats, setSeats] = useState<{ limit: number; used: number; available: number } | null>(null);
  const [companyBalance, setCompanyBalance] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ name: '', email: '', password: '', role: 'recruiter' });
  const [grantFor, setGrantFor] = useState<OrgMember | null>(null);
  const [grantAmount, setGrantAmount] = useState<string>('');
  const [grantNote, setGrantNote] = useState<string>('');
  const [granting, setGranting] = useState(false);

  const load = useCallback(() => {
    Promise.all([orgService.listMembers(), orgService.getBillingSummary()])
      .then(([res, billing]) => {
        setMembers(res.members);
        setSeats(billing.seats);
        setCompanyBalance(billing.company_credit_balance ?? 0);
      })
      .catch(() => customToast({ type: 'error', title: t('common.status') }))
      .finally(() => setLoading(false));
  }, [t]);

  useEffect(load, [load]);

  const createMember = async () => {
    if (!form.name.trim() || !form.email.trim()) {
      customToast({ type: 'error', title: t('common.status'), message: 'Name and email are required' });
      return;
    }
    setCreating(true);
    try {
      const res = await orgService.createMember({
        name: form.name.trim(),
        email: form.email.trim(),
        password: form.password || undefined,
        role: form.role,
      });
      if (res.password) {
        customToast({ type: 'success', title: t('common.status'), message: `Password: ${res.password}` });
      } else {
        customToast({ type: 'success', title: t('common.status'), message: 'Member created' });
      }
      setShowCreate(false);
      setForm({ name: '', email: '', password: '', role: 'recruiter' });
      load();
    } catch (e) {
      customToast({ type: 'error', title: (e as Error).message });
    } finally {
      setCreating(false);
    }
  };

  const toggleActive = async (m: OrgMember) => {
    try {
      if (m.is_active) await orgService.deactivateMember(m.user_id);
      else await orgService.activateMember(m.user_id);
      load();
    } catch (e) {
      customToast({ type: 'error', title: (e as Error).message });
    }
  };

  const resetUsage = async (m: OrgMember) => {
    try {
      await orgService.resetMemberUsage(m.user_id);
      customToast({ type: 'success', title: t('common.status'), message: `Reset for ${m.name || m.email}` });
      load();
    } catch (e) {
      customToast({ type: 'error', title: (e as Error).message });
    }
  };

  const grantCredits = async () => {
    if (!grantFor) return;
    const amount = Number(grantAmount);
    if (!Number.isInteger(amount) || amount <= 0) {
      customToast({ type: 'error', title: t('common.status'), message: 'Enter a valid number' });
      return;
    }
    setGranting(true);
    try {
      const res = await orgService.grantMemberCredits(grantFor.user_id, amount, grantNote.trim() || undefined);
      customToast({ type: 'success', title: t('common.status'), message: `Granted ${res.credits} credits` });
      setGrantFor(null);
      setGrantAmount('');
      setGrantNote('');
      load();
    } catch (e) {
      customToast({ type: 'error', title: (e as Error).message });
    } finally {
      setGranting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{t('org.members')}</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{t('org.membersSubtitle')}</p>
        </div>
        <Button id="org-create-member-btn" variant="primary" leftIcon={<UserPlus className="h-4 w-4" />} onClick={() => setShowCreate((v) => !v)}>
          {t('org.addMember')}
        </Button>
      </div>

      {seats && (
        <div className="flex items-center gap-3 rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 px-4 py-3">
          <UsersIcon className="h-5 w-5 text-purple-600 dark:text-purple-400" />
          <div className="text-sm">
            <span className="font-semibold text-gray-900 dark:text-white">
              {seats.used} / {seats.limit}
            </span>
            <span className="text-gray-500 dark:text-gray-400"> {t('org.members')}</span>
          </div>
          <div className="flex-1 h-2 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden">
            <div
              className={cn(
                'h-full rounded-full',
                seats.available <= 0 ? 'bg-red-500' : seats.available <= 2 ? 'bg-amber-500' : 'bg-emerald-500'
              )}
              style={{ width: `${seats.limit ? Math.min(100, (seats.used / seats.limit) * 100) : 0}%` }}
            />
          </div>
        </div>
      )}

      <div className="flex items-center gap-3 rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 px-4 py-3">
        <Coins className="h-5 w-5 text-amber-600 dark:text-amber-400" />
        <div className="text-sm">
          <span className="font-semibold text-gray-900 dark:text-white">{companyBalance}</span>
          <span className="text-gray-500 dark:text-gray-400"> {t('billing.credits')}</span>
        </div>
        <div className="flex-1" />
      </div>

      {grantFor && (
        <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
          <Card>
            <CardContent>
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h3 className="text-sm font-semibold text-gray-900 dark:text-white">{t('org.grantCredits')}: {grantFor.name || grantFor.email}</h3>
                  <p className="text-xs text-gray-500 dark:text-gray-400">{t('billing.credits')}: {grantFor.credit_balance ?? 0}</p>
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <input
                  value={grantAmount}
                  onChange={(e) => setGrantAmount(e.target.value)}
                  placeholder={t('billing.credits')}
                  type="number"
                  min={1}
                  className="rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
                />
                <input
                  value={grantNote}
                  onChange={(e) => setGrantNote(e.target.value)}
                  placeholder={t('common.description')}
                  className="rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
                />
              </div>
              <div className="mt-3 flex gap-2">
                <Button id="org-grant-submit" variant="primary" onClick={grantCredits} disabled={granting}>
                  {granting ? <Loader2 className="h-4 w-4 animate-spin" /> : null} {t('org.grantCredits')}
                </Button>
                <Button variant="ghost" onClick={() => { setGrantFor(null); setGrantAmount(''); setGrantNote(''); }}>{t('common.cancel')}</Button>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}

      {showCreate && (
        <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
          <Card>
            <CardContent>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                <input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="Full name"
                  className="rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
                />
                <input
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  placeholder="Email"
                  type="email"
                  className="rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
                />
                <input
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  placeholder="Password"
                  className="rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
                />
                <select
                  value={form.role}
                  onChange={(e) => setForm({ ...form, role: e.target.value })}
                  className="rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
                >
                  <option value="recruiter">{t('role.recruiter')}</option>
                  <option value="member">Member</option>
                </select>
              </div>
              <div className="mt-3 flex gap-2">
                <Button id="org-create-submit" variant="primary" onClick={createMember} disabled={creating}>
                  {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : null} {t('org.addMember')}
                </Button>
                <Button variant="ghost" onClick={() => setShowCreate(false)}>{t('common.cancel')}</Button>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-12"><Loader2 className="h-8 w-8 animate-spin text-purple-600" /></div>
      ) : (
        <Card>
          <CardContent>
            {!members.length ? (
              <p className="text-sm text-gray-500 dark:text-gray-400 py-8 text-center">{t('common.noData')}</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                      <th className="py-2 font-medium">{t('org.members')}</th>
                      <th className="py-2 font-medium">{t('role.role')}</th>
                      <th className="py-2 font-medium text-right">{t('billing.credits')}</th>
                      <th className="py-2 font-medium text-right">{t('nav.jobs')}</th>
                      <th className="py-2 font-medium text-right">CVs</th>
                      <th className="py-2 font-medium text-right">{t('nav.interviews')}</th>
                      <th className="py-2 font-medium">{t('common.status')}</th>
                      <th className="py-2 font-medium text-right">{t('common.actions')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {members.map((m) => (
                      <tr key={m.user_id} className="border-b border-gray-100 dark:border-gray-800">
                        <td className="py-3">
                          <div className="font-medium text-gray-900 dark:text-white">{m.name || '—'}</div>
                          <div className="text-xs text-gray-400">{m.email}</div>
                        </td>
                        <td className="py-3">
                          <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium capitalize', ROLE_BADGES[m.role] || ROLE_BADGES.member)}>{m.role}</span>
                        </td>
                        <td className="py-3 text-right">
                          <span className="inline-flex items-center gap-1 font-medium text-gray-900 dark:text-white">
                            <Coins className="h-3.5 w-3.5 text-amber-500" />
                            {m.credit_balance ?? 0}
                          </span>
                        </td>
                        <td className="py-3 text-right">{m.usage?.jobs ?? 0}</td>
                        <td className="py-3 text-right">{m.usage?.cvs ?? 0}</td>
                        <td className="py-3 text-right">{m.usage?.ai_interviews ?? 0}</td>
                        <td className="py-3">
                          <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', m.is_active ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300' : 'bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-300')}>
                            {m.is_active ? t('common.status') : '—'}
                          </span>
                        </td>
                        <td className="py-3">
                          <div className="flex items-center justify-end gap-1">
                            {m.role !== 'owner' && (
                              <>
                                <button title={t('org.grantCredits')} onClick={() => { setGrantFor(m); setGrantAmount(''); setGrantNote(''); }} className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-amber-600 dark:text-amber-400">
                                  <Coins className="h-4 w-4" />
                                </button>
                                <button title="Toggle" onClick={() => toggleActive(m)} className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500">
                                  {m.is_active ? <UserX className="h-4 w-4" /> : <UserCheck className="h-4 w-4" />}
                                </button>
                                <button title={t('common.refresh')} onClick={() => resetUsage(m)} className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500">
                                  <RotateCcw className="h-4 w-4" />
                                </button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
