// ============================================================
// Admin AI Sales Intelligence - Candway Tunisia
// Real data from /admin/ai/sales/leads API
// ============================================================

import { useCallback, useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/shared/components/ui/tabs';
import { customToast } from '@/shared/components/ui/toast';
import { TrendingUp, Users, Target, Zap, Play, Pause, Mail, RefreshCw, Search, CheckCircle2 } from 'lucide-react';
import { adminService, AISalesLead } from '@/services/admin.service';

const STATUS_VARIANT: Record<string, 'success' | 'info' | 'warning' | 'default'> = {
  qualified: 'success',
  contacted: 'info',
  interested: 'warning',
  converted: 'success',
  new: 'default',
  rejected: 'default',
};

const ACTION_TO_STATUS: Record<string, string> = {
  contact: 'contacted',
  qualify: 'qualified',
  convert: 'converted',
};

export default function AISalesPage() {
  const [leads, setLeads] = useState<AISalesLead[]>([]);
  const [search, setSearch] = useState('');
  const [autopilotRunning, setAutopilotRunning] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [launching, setLaunching] = useState(false);
  const [loading, setLoading] = useState(true);

  const loadLeads = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminService.getAIJobs();
      setLeads(data || []);
    } catch (err) {
      console.error('AI Sales load error:', err);
      customToast({ type: 'error', title: 'AI Sales', message: 'Failed to load leads.' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadLeads(); }, [loadLeads]);

  const filteredLeads = (leads || []).filter(l =>
    (l.name || '').toLowerCase().includes(search.toLowerCase()) ||
    (l.email || '').toLowerCase().includes(search.toLowerCase()) ||
    (l.company || '').toLowerCase().includes(search.toLowerCase())
  );

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'bg-emerald-500';
    if (score >= 60) return 'bg-blue-500';
    if (score >= 40) return 'bg-amber-500';
    return 'bg-red-500';
  };

  const handleLeadAction = async (id: number, action: string) => {
    const status = ACTION_TO_STATUS[action];
    setBusyId(id);
    try {
      await adminService.updateLeadStatus(String(id), status);
      setLeads(prev => prev.map(lead => lead.id === id ? { ...lead, status } : lead));
      customToast({ type: 'success', title: 'Lead Updated', message: `Lead marked as ${status}.` });
    } catch (err) {
      console.error('Lead action error:', err);
      customToast({ type: 'error', title: 'Lead Updated', message: 'Failed to update lead status.' });
    } finally {
      setBusyId(null);
    }
  };

  const toggleAutopilot = async () => {
    setLaunching(true);
    try {
      const res = await adminService.launchAIPipeline();
      setAutopilotRunning(true);
      customToast({ type: 'success', title: 'Autopilot Launched', message: (res as { message?: string })?.message || 'AI outreach engine activated.' });
    } catch (err) {
      console.error('Autopilot launch error:', err);
      customToast({ type: 'error', title: 'Autopilot', message: 'Failed to launch autopilot mission.' });
    } finally {
      setLaunching(false);
    }
  };

  const convertedCount = leads.filter(l => l.status === 'converted').length;
  const qualifiedCount = leads.filter(l => l.status === 'qualified').length;

  const statCards = [
    { label: 'Total Leads', value: String(leads.length || 0), icon: Users, color: 'text-purple-600 bg-purple-100 dark:bg-purple-900/30' },
    { label: 'Qualified', value: String(qualifiedCount), icon: Target, color: 'text-blue-600 bg-blue-100 dark:bg-blue-900/30' },
    { label: 'Converted', value: String(convertedCount), icon: TrendingUp, color: 'text-emerald-600 bg-emerald-100 dark:bg-emerald-900/30' },
    { label: 'Scored', value: String(leads.filter(l => (l.score ?? 0) > 0).length), icon: Zap, color: 'text-amber-600 bg-amber-100 dark:bg-amber-900/30' },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Badge variant="primary" className="bg-purple-600 text-white font-extrabold" size="sm">AI Sales Engine</Badge>
          </div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white mt-1">AI Sales Intelligence</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Lead qualification and outbound prospecting</p>
        </div>
        <Button variant="outline" size="sm" leftIcon={<RefreshCw className="h-4 w-4" />} onClick={loadLeads}>Refresh</Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((stat) => (
          <Card key={stat.label} className="glass-panel border-purple-200/50">
            <CardContent className="p-5">
              <div className="flex items-center gap-3 mb-3">
                <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${stat.color}`}>
                  <stat.icon className="h-5 w-5" />
                </div>
                <div className="text-xs font-black uppercase text-gray-400">{stat.label}</div>
              </div>
              <div className="text-3xl font-black text-gray-900 dark:text-white">{stat.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Tabs defaultValue="leads">
        <TabsList>
          <TabsTrigger value="leads">Lead Pipeline</TabsTrigger>
          <TabsTrigger value="engines">Outreach Engines</TabsTrigger>
        </TabsList>

        <TabsContent value="leads">
          <div className="flex items-center justify-between mb-4">
            <Input placeholder="Search leads..." leftIcon={<Search className="h-4 w-4" />} value={search} onChange={(e) => setSearch(e.target.value)} wrapperClassName="w-64" />
            <Button variant="outline" size="sm" leftIcon={autopilotRunning ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />} onClick={toggleAutopilot} disabled={launching}>
              {launching ? 'Launching...' : autopilotRunning ? 'Autopilot Running' : 'Start Autopilot'}
            </Button>
          </div>

          {loading ? (
            <div className="flex flex-col items-center justify-center gap-3 py-16">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-purple-600 border-t-transparent" />
              <span className="text-sm text-gray-500">Loading leads...</span>
            </div>
          ) : (
            <Card className="glass-panel border-purple-200/50">
              <CardHeader><CardTitle>Lead Pipeline</CardTitle><CardDescription>{filteredLeads.length} leads</CardDescription></CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-left">
                    <thead>
                      <tr className="border-b border-purple-100 dark:border-white/10">
                        <th className="py-3 text-xs font-bold text-gray-500 uppercase">Lead</th>
                        <th className="py-3 text-xs font-bold text-gray-500 uppercase">Company</th>
                        <th className="py-3 text-xs font-bold text-gray-500 uppercase">Score</th>
                        <th className="py-3 text-xs font-bold text-gray-500 uppercase">Status</th>
                        <th className="py-3 text-xs font-bold text-gray-500 uppercase">Source</th>
                        <th className="py-3 text-xs font-bold text-gray-500 uppercase text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredLeads.map(l => (
                        <tr key={l.id} className="border-b border-gray-50 dark:border-white/[0.02] hover:bg-purple-50/50 transition-colors">
                          <td className="py-3">
                            <div className="text-sm font-bold text-gray-900 dark:text-white">{l.name || l.email}</div>
                            <div className="text-xs text-gray-500">{l.email}</div>
                          </td>
                          <td className="py-3 text-sm font-medium text-gray-500">{l.company || 'N/A'}</td>
                          <td className="py-3">
                            <div className="flex items-center gap-2">
                              <div className={`w-2 h-2 rounded-full ${getScoreColor(l.score ?? 0)}`} />
                              <span className="text-sm font-bold text-gray-900 dark:text-white">{l.score ?? '—'}</span>
                            </div>
                          </td>
                          <td className="py-3">
                            <Badge variant={STATUS_VARIANT[l.status || 'new'] || 'default'} size="sm">{l.status || 'new'}</Badge>
                          </td>
                          <td className="py-3 text-sm font-medium text-gray-500">{l.source || 'N/A'}</td>
                          <td className="py-3 text-right">
                            <div className="flex items-center gap-1">
                              <Button variant="ghost" size="xs" disabled={busyId === l.id} leftIcon={<Mail className="h-3.5 w-3.5 text-indigo-500" />} onClick={() => handleLeadAction(l.id, 'contact')}>Contact</Button>
                              <Button variant="ghost" size="xs" disabled={busyId === l.id} leftIcon={<Zap className="h-3.5 w-3.5 text-amber-500" />} onClick={() => handleLeadAction(l.id, 'qualify')}>Qualify</Button>
                              <Button variant="ghost" size="xs" disabled={busyId === l.id} leftIcon={<CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />} onClick={() => handleLeadAction(l.id, 'convert')}>Convert</Button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="engines">
          <Card className="glass-panel border-purple-200/50">
            <CardHeader>
              <CardTitle>Outreach Engine Controls</CardTitle>
              <CardDescription>Launch an AI prospecting mission in the background</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10">
                  <div>
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Autonomous Prospecting</span>
                    <p className="text-xs text-gray-500">AI engine finds and scores leads from internal platform users</p>
                  </div>
                  <Button size="sm" leftIcon={<Play className="h-4 w-4" />} onClick={toggleAutopilot} disabled={launching}>
                    {launching ? 'Launching...' : 'Launch Mission'}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
