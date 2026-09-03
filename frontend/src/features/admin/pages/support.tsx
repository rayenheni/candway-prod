// ============================================================
// Admin Support Inbox - Candway
// Real data from /admin/tickets, /admin/upgrade-requests APIs
// ============================================================

import { useCallback, useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/shared/components/ui/select';
import { customToast } from '@/shared/components/ui/toast';
import { cn } from '@/utils/cn';
import { MessageSquare, Search, Clock, AlertCircle, CheckCircle2, Send, Archive, RefreshCw, ChevronRight, User } from 'lucide-react';
import { adminService, SupportTicket } from '@/services/admin.service';

const statusConfig: Record<string, { label: string; variant: 'warning' | 'info' | 'success' | 'default' | 'danger' }> = {
  open: { label: 'Open', variant: 'warning' },
  in_progress: { label: 'In Progress', variant: 'info' },
  resolved: { label: 'Resolved', variant: 'success' },
  closed: { label: 'Closed', variant: 'default' },
};

const priorityConfig: Record<string, { label: string; variant: 'default' | 'warning' | 'danger' }> = {
  low: { label: 'Low', variant: 'default' },
  medium: { label: 'Medium', variant: 'warning' },
  high: { label: 'High', variant: 'danger' },
  critical: { label: 'Critical', variant: 'danger' },
};

export default function SupportPage() {
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [selectedTicket, setSelectedTicket] = useState<SupportTicket | null>(null);
  const [replyText, setReplyText] = useState('');
  const [loading, setLoading] = useState(true);

  const loadTickets = useCallback(async () => {
    setLoading(true);
    try {
      const [tRes, uRes] = await Promise.all([
        adminService.getTickets({ status: statusFilter, page: 1, per_page: 100 }),
        adminService.getUpgradeRequests({ status: statusFilter, page: 1, per_page: 100 }),
      ]);
      const allTickets = [
        ...(tRes.tickets || []).map(t => ({ ...t, category: 'Support' as const })),
        ...(uRes.upgrade_requests || []).map(r => ({
          id: r.id, user_id: r.user_id, subject: r.subject, message: r.description,
          priority: '', status: r.status, created_at: r.created_at,
          category: 'Upgrade Request' as const, user_name: r.user_name, user_email: r.user_email,
        })),
      ];
      setTickets(allTickets);
    } catch (err) {
      console.error('Support load error:', err);
      customToast({ type: 'error', title: 'Support', message: 'Failed to load tickets.' });
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { loadTickets(); }, [loadTickets]);

  const filteredTickets = tickets.filter(t => {
    const q = search.toLowerCase();
    return (t.subject || '').toLowerCase().includes(q) ||
      (t.message || '').toLowerCase().includes(q) ||
      String(t.id).toLowerCase().includes(q);
  });

  const keyOf = (t: { id: number; category?: string }) => `${t.category ?? 'Support'}-${t.id}`;

  const handleSendReply = async () => {
    if (!replyText.trim() || !selectedTicket) return;
    if ((selectedTicket as any).category === 'Upgrade Request') return;
    try {
      await adminService.replyTicket(selectedTicket.id, replyText, false);
      customToast({ type: 'success', title: 'Reply Sent', message: 'Your response has been added to the ticket thread.' });
      setReplyText('');
      loadTickets();
    } catch (err: any) {
      customToast({ type: 'error', title: 'Send Failed', message: err?.message || 'Could not send reply.' });
    }
  };

  const handleArchive = async () => {
    if (!selectedTicket) return;
    if ((selectedTicket as any).category === 'Upgrade Request') return;
    try {
      await adminService.replyTicket(selectedTicket.id, 'Ticket archived by admin.', true);
      customToast({ type: 'info', title: 'Archived', message: 'Ticket closed.' });
      loadTickets();
      setSelectedTicket(null);
    } catch (err: any) {
      customToast({ type: 'error', title: 'Failed', message: err?.message || 'Could not close ticket.' });
    }
  };

  const handleApproveUpgrade = async (id: number) => {
    try {
      await adminService.approveUpgradeRequest(id);
      customToast({ type: 'success', title: 'Upgrade Approved', message: 'User upgraded successfully.' });
      loadTickets();
    } catch (err: any) {
      customToast({ type: 'error', title: 'Failed', message: err?.message || 'Could not approve.' });
    }
  };

  const handleRejectUpgrade = async (id: number) => {
    try {
      await adminService.rejectUpgradeRequest(id, 'Request declined by admin.');
      customToast({ type: 'success', title: 'Upgrade Rejected', message: 'Request declined.' });
      loadTickets();
    } catch (err: any) {
      customToast({ type: 'error', title: 'Failed', message: err?.message || 'Could not reject.' });
    }
  };

  const stats = {
    open: tickets.filter(t => t.status === 'open').length,
    inProgress: tickets.filter(t => t.status === 'in_progress').length,
    resolved: tickets.filter(t => t.status === 'resolved').length,
    total: tickets.length,
  };

  const statCards = [
    { label: 'Open', value: stats.open, icon: AlertCircle, color: 'text-amber-600 bg-amber-50 dark:bg-amber-500/10' },
    { label: 'In Progress', value: stats.inProgress, icon: Clock, color: 'text-blue-600 bg-blue-50 dark:bg-blue-500/10' },
    { label: 'Resolved', value: stats.resolved, icon: CheckCircle2, color: 'text-emerald-600 bg-emerald-50 dark:bg-emerald-500/10' },
    { label: 'Total', value: stats.total, icon: MessageSquare, color: 'text-purple-600 bg-purple-50 dark:bg-purple-500/10' },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">Support Inbox</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Manage support tickets and upgrade requests from candidates and recruiters</p>
        </div>
        <Button variant="outline" size="sm" leftIcon={<RefreshCw className="h-4 w-4" />} onClick={loadTickets}>Refresh</Button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {statCards.map((stat) => (
          <Card key={stat.label} className="glass-panel border-purple-200/50">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className={cn('flex h-10 w-10 items-center justify-center rounded-xl', stat.color)}>
                  <stat.icon className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-2xl font-black text-gray-900 dark:text-white">{stat.value}</div>
                  <div className="text-xs font-medium text-gray-500">{stat.label}</div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-4">
          <Card className="glass-panel border-purple-200/50">
            <CardHeader>
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                <div>
                  <CardTitle>All Tickets & Upgrade Requests</CardTitle>
                  <CardDescription>{filteredTickets.length} items shown</CardDescription>
                </div>
                <div className="flex items-center gap-2 w-full sm:w-auto">
                  <Input placeholder="Search tickets..." leftIcon={<Search className="h-4 w-4" />} value={search} onChange={(e) => setSearch(e.target.value)} wrapperClassName="w-full sm:w-48" />
                  <Select value={statusFilter} onValueChange={setStatusFilter}>
                    <SelectTrigger className="w-36">
                      <SelectValue placeholder="Status" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All</SelectItem>
                      <SelectItem value="open">Open</SelectItem>
                      <SelectItem value="in_progress">In Progress</SelectItem>
                      <SelectItem value="resolved">Resolved</SelectItem>
                      <SelectItem value="closed">Closed</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <div className="divide-y divide-purple-50 dark:divide-white/[0.04] max-h-[600px] overflow-y-auto">
                {loading ? (
                  <div className="p-8 text-center text-gray-400">Loading tickets...</div>
                ) : filteredTickets.length === 0 ? (
                  <div className="p-8 text-center text-gray-400">No tickets match your filters.</div>
                ) : (
                  filteredTickets.map((ticket) => {
                    const sc = statusConfig[ticket.status] || { label: ticket.status, variant: 'default' as const };
                    const isUpgrade = (ticket as any).category === 'Upgrade Request';
                    const pc = priorityConfig[ticket.priority || 'medium'];
                    return (
                      <div
                        key={keyOf(ticket)}
                        className={cn(
                          'flex items-start gap-3 p-4 cursor-pointer transition-colors hover:bg-purple-50/50 dark:hover:bg-white/[0.02]',
                          selectedTicket && keyOf(selectedTicket) === keyOf(ticket) && 'bg-purple-50/80 dark:bg-purple-500/[0.04] border-l-2 border-l-purple-500'
                        )}
                        onClick={() => { setSelectedTicket(ticket); setReplyText(''); }}
                      >
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-xs font-bold text-purple-600 dark:text-purple-400">TKT-{ticket.id}</span>
                            {!isUpgrade && <Badge variant={pc.variant} size="sm" className="uppercase text-[10px] font-bold">{ticket.priority}</Badge>}
                            <Badge variant={sc.variant} size="sm" dot>{sc.label}</Badge>
                            {isUpgrade && <Badge variant="primary" size="sm" className="text-[9px]">Upgrade</Badge>}
                          </div>
                          <p className="text-sm font-bold text-gray-900 dark:text-white truncate">{ticket.subject}</p>
                          <div className="flex items-center gap-3 mt-1.5 text-xs text-gray-500">
                            <span className="flex items-center gap-1"><User className="h-3 w-3" />{(ticket as any).user_name || `User #${ticket.user_id}`}</span>
                            <span>{ticket.created_at ? new Date(ticket.created_at).toLocaleDateString() : '—'}</span>
                          </div>
                        </div>
                        <ChevronRight className="h-4 w-4 text-gray-400 shrink-0 mt-1" />
                      </div>
                    );
                  })
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        <div>
          {selectedTicket ? (
            <Card className="glass-panel border-purple-200/50 h-full">
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-bold text-purple-600 dark:text-purple-400">TKT-{selectedTicket.id}</span>
                      <Badge variant={(statusConfig[selectedTicket.status] || { variant: 'default' }).variant} size="sm" dot>{(statusConfig[selectedTicket.status] || { label: selectedTicket.status }).label}</Badge>
                      {(selectedTicket as any).category !== 'Upgrade Request' && <Badge variant={(priorityConfig[selectedTicket.priority || 'medium'] || { variant: 'default' }).variant} size="sm" className="uppercase text-[10px] font-bold">{selectedTicket.priority}</Badge>}
                      {(selectedTicket as any).category === 'Upgrade Request' && <Badge variant="primary" size="sm">Upgrade Request</Badge>}
                    </div>
                    <CardTitle className="text-base break-all">{selectedTicket.subject}</CardTitle>
                    <CardDescription>
                      {(selectedTicket as any).user_name || `User #${selectedTicket.user_id}`} &middot; {(selectedTicket as any).user_email || ''}
                    </CardDescription>
                  </div>
                  {(selectedTicket as any).category !== 'Upgrade Request' && (
                    <Button variant="ghost" size="xs" onClick={handleArchive} leftIcon={<Archive className="h-4 w-4 text-gray-400" />} />
                  )}
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-4 mb-6 max-h-[300px] overflow-y-auto">
                  <div className="p-4 rounded-xl bg-gray-50 dark:bg-white/[0.04] border border-purple-100 dark:border-white/10">
                    <p className="text-sm text-gray-900 dark:text-white leading-relaxed">{selectedTicket.message || 'No message content available.'}</p>
                  </div>
                </div>

                {(selectedTicket as any).category === 'Upgrade Request' ? (
                  <div className="flex gap-2 border-t border-purple-100 dark:border-white/10 pt-4">
                    <Button variant="primary" size="sm" leftIcon={<CheckCircle2 className="h-4 w-4" />} onClick={() => handleApproveUpgrade(selectedTicket.id)}>
                      Approve Upgrade
                    </Button>
                    <Button variant="outline" size="sm" leftIcon={<Archive className="h-4 w-4" />} onClick={() => handleRejectUpgrade(selectedTicket.id)}>
                      Reject
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-3 border-t border-purple-100 dark:border-white/10 pt-4">
                    <div className="flex gap-2">
                      <textarea
                        className="flex-1 rounded-xl border border-purple-200/60 bg-white/70 p-3 text-sm focus:ring-2 focus:ring-purple-500/20 dark:border-white/10 dark:bg-white/5 dark:text-white min-h-[80px]"
                        placeholder="Type your reply..."
                        value={replyText}
                        onChange={(e) => setReplyText(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendReply(); } }}
                      />
                      <Button variant="primary" leftIcon={<Send className="h-4 w-4" />} onClick={handleSendReply} className="self-end" />
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          ) : (
            <Card className="glass-panel border-purple-200/50 h-full">
              <CardContent>
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-purple-50 dark:bg-purple-900/30 mb-4">
                    <MessageSquare className="h-8 w-8 text-purple-400" />
                  </div>
                  <h3 className="text-lg font-bold text-gray-900 dark:text-white">Select a Ticket</h3>
                  <p className="text-sm text-gray-500 mt-1 max-w-xs">Choose a ticket from the list to view its conversation thread and respond.</p>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
