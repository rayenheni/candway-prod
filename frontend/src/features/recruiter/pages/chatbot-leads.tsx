import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { customToast } from '@/shared/components/ui/toast';
import { MessageSquare, UserPlus, Phone, Mail, CheckCircle2, XCircle, Clock, Search, Loader2 } from 'lucide-react';
import { cn } from '@/utils/cn';
import apiClient from '@/lib/api-client';
import { useAuth } from '@/contexts/auth-context';

const statusConfig: Record<string, { label: string; icon: any; class: string }> = {
  new: { label: 'New', icon: Clock, class: 'bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-300' },
  contacted: { label: 'Contacted', icon: Phone, class: 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300' },
  converted: { label: 'Converted', icon: CheckCircle2, class: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300' },
  dismissed: { label: 'Dismissed', icon: XCircle, class: 'bg-slate-100 text-slate-700 dark:bg-slate-500/20 dark:text-slate-300' },
};

const leadStatus = (l: any) => l.stage || (l.contacted_at ? 'contacted' : 'new');

export default function ChatbotLeadsPage() {
  const { user } = useAuth();
  const [leads, setLeads] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | string | null>(null);

  const fetchLeads = async () => {
    try {
      setLoading(true);
      const data = await apiClient.get<any>('/chatbot/leads');
      setLeads(Array.isArray(data) ? data : (data?.leads ?? []));
      setError(null);
    } catch (err: any) {
      const msg = err?.message || 'Failed to load leads';
      setError(msg);
      customToast({ type: 'error', title: 'Error', message: msg });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLeads();
  }, []);

  const handleContact = async (id: number | string) => {
    setBusyId(id);
    try {
      await apiClient.post(`/chatbot/leads/${id}/contacted`);
      customToast({ type: 'success', title: 'Contacted', message: 'Lead marked as contacted.' });
      await fetchLeads();
    } catch (err: any) {
      customToast({ type: 'error', title: 'Failed', message: err?.message || 'Could not update lead.' });
    } finally {
      setBusyId(null);
    }
  };

  const handleAssign = async (id: number | string) => {
    if (!user?.id) {
      customToast({ type: 'warning', title: 'Not Signed In', message: 'You must be signed in to assign leads.' });
      return;
    }
    setBusyId(id);
    try {
      await apiClient.post(`/chatbot/leads/${id}/assign?recruiter_id=${Number(user.id)}`);
      customToast({ type: 'success', title: 'Assigned', message: 'Lead assigned to you.' });
      await fetchLeads();
    } catch (err: any) {
      customToast({ type: 'error', title: 'Failed', message: err?.message || 'Could not assign lead.' });
    } finally {
      setBusyId(null);
    }
  };

  const filtered = leads.filter(l =>
    l.name?.toLowerCase().includes(search.toLowerCase()) ||
    l.email?.toLowerCase().includes(search.toLowerCase())
  );

  const totalLeads = leads.length;
  const contactedCount = leads.filter(l => leadStatus(l) === 'contacted').length;
  const convertedCount = leads.filter(l => leadStatus(l) === 'converted').length;
  const newCount = leads.filter(l => leadStatus(l) === 'new').length;

  const stats = [
    { label: 'Total Leads', value: totalLeads, icon: MessageSquare, color: 'text-purple-600 dark:text-purple-400', bg: 'bg-purple-100 dark:bg-purple-500/20' },
    { label: 'Contacted', value: contactedCount, icon: Phone, color: 'text-amber-600 dark:text-amber-400', bg: 'bg-amber-100 dark:bg-amber-500/20' },
    { label: 'Converted', value: convertedCount, icon: CheckCircle2, color: 'text-emerald-600 dark:text-emerald-400', bg: 'bg-emerald-100 dark:bg-emerald-500/20' },
    { label: 'New', value: newCount, icon: Clock, color: 'text-blue-600 dark:text-blue-400', bg: 'bg-blue-100 dark:bg-blue-500/20' },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 text-violet-500 animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] text-gray-500">
        <p className="text-lg font-semibold">Failed to load leads</p>
        <p className="text-sm">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">Chatbot Leads</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Capture and manage leads from your chatbot conversations</p>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {stats.map((s, i) => (
          <motion.div key={s.label} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: i * 0.05 }}>
            <Card className="glass-card p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{s.label}</p>
                  <p className="text-2xl font-black text-gray-900 dark:text-white mt-0.5">{s.value}</p>
                </div>
                <div className={cn('flex h-10 w-10 items-center justify-center rounded-xl', s.bg)}>
                  <s.icon className={cn('h-5 w-5', s.color)} />
                </div>
              </div>
            </Card>
          </motion.div>
        ))}
      </div>

      <Input placeholder="Search by name or email..." leftIcon={<Search className="h-4 w-4 text-purple-500" />} value={search} onChange={(e) => setSearch(e.target.value)} />

      <Card className="glass-panel border-purple-200/50 overflow-hidden">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg flex items-center gap-2">
              <MessageSquare className="h-5 w-5 text-purple-500" />
              Lead List
            </CardTitle>
            <Badge variant="primary" size="sm">{filtered.length} Leads</Badge>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-purple-100 dark:border-white/10 text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  <th className="px-6 py-3 text-left">Name</th>
                  <th className="px-6 py-3 text-left">Email</th>
                  <th className="px-6 py-3 text-left">Source</th>
                  <th className="px-6 py-3 text-left">Status</th>
                  <th className="px-6 py-3 text-left">Last Contact</th>
                  <th className="px-6 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((l, i) => {
                  const cfg = statusConfig[leadStatus(l)] || statusConfig.new;
                  const StatusIcon = cfg.icon;
                  const isBusy = busyId === l.id;
                  return (
                    <motion.tr key={l.id} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.25, delay: i * 0.03 }} className="border-b border-purple-50 dark:border-white/5 hover:bg-purple-50/50 dark:hover:bg-purple-500/5 transition-colors">
                      <td className="px-6 py-4">
                        <span className="font-bold text-gray-900 dark:text-white">{l.name}</span>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600 dark:text-gray-400">{l.email}</td>
                      <td className="px-6 py-4">
                        <Badge variant="default" size="sm">{l.source || l.role_interest || 'Chatbot'}</Badge>
                      </td>
                      <td className="px-6 py-4">
                        <Badge className={cn('font-semibold flex items-center gap-1 w-fit', cfg.class)} size="sm">
                          <StatusIcon className="h-3 w-3" />
                          {cfg.label}
                        </Badge>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">{l.contacted_at || l.lastContact || l.last_contact || '—'}</td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Button variant="ghost" size="sm" loading={isBusy} disabled={isBusy || leadStatus(l) === 'contacted'} leftIcon={<Mail className="h-3.5 w-3.5" />} onClick={() => handleContact(l.id)}>Contact</Button>
                          <Button variant="ghost" size="sm" loading={isBusy} disabled={isBusy || !!l.assigned_recruiter_id} leftIcon={<UserPlus className="h-3.5 w-3.5" />} onClick={() => handleAssign(l.id)}>Assign</Button>
                        </div>
                      </td>
                    </motion.tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}