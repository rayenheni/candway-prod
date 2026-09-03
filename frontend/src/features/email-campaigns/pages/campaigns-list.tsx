import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, ConfirmDialog } from '@/shared/components/ui/dialog';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/shared/components/ui/select';
import { useLanguage } from '@/contexts/language-context';
import { cn } from '@/utils/cn';
import { customToast } from '@/shared/components/ui/toast';
import { campaignsService } from '@/services/campaigns.service';
import { Plus, Mail, Send, Eye, Loader2, Pencil, Trash2, Upload } from 'lucide-react';

const statusColors: Record<string, string> = {
  sent: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400',
  scheduled: 'bg-blue-100 text-blue-700 dark:bg-blue-500/10 dark:text-blue-400',
  draft: 'bg-gray-100 text-gray-700 dark:bg-white/10 dark:text-gray-400',
  active: 'bg-purple-100 text-purple-700 dark:bg-purple-500/10 dark:text-purple-400',
  completed: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400',
  paused: 'bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400',
  processing: 'bg-blue-100 text-blue-700 dark:bg-blue-500/10 dark:text-blue-400',
  pending: 'bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400',
  archived: 'bg-gray-100 text-gray-700 dark:bg-white/10 dark:text-gray-400',
};

const WORKER_STATUS_LABEL: Record<string, string> = {
  pending: 'Awaiting upload',
  processing: 'Analyzing CVs…',
  completed: 'Ready',
  failed: 'Failed',
};

export default function CampaignsListPage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const [editing, setEditing] = useState<any>(null);
  const [editTitle, setEditTitle] = useState('');
  const [editStatus, setEditStatus] = useState('active');
  const [editSaving, setEditSaving] = useState(false);

  const [deleting, setDeleting] = useState<any>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const fetchCampaigns = () => {
    setLoading(true);
    campaignsService.list({ per_page: 50 })
      .then((data: any) => {
        const items = Array.isArray(data) ? data : (data?.items || []);
        setCampaigns(items);
      })
      .catch(() => { customToast({ type: 'error', title: t('common.status'), message: t('recruiter.campaigns.loadFailed') }); setCampaigns([]); })
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchCampaigns(); }, []);

  const openEdit = (c: any) => {
    setEditing(c);
    setEditTitle(c.title || t('recruiter.campaigns.campaignId').replace('{id}', String(c.id)));
    setEditStatus(c.status || 'active');
  };

  const handleSaveEdit = async () => {
    if (!editTitle.trim()) { customToast({ type: 'warning', title: t('common.status'), message: t('recruiter.campaigns.titleRequired') }); return; }
    setEditSaving(true);
    try {
      const res: any = await campaignsService.update(String(editing.id), { title: editTitle.trim(), status: editStatus });
      customToast({ type: 'success', title: t('common.status'), message: res?.title ? t('recruiter.campaigns.renamed').replace('{title}', res.title) : t('recruiter.campaigns.updated') });
      setEditing(null);
      fetchCampaigns();
    } catch (e: any) {
      customToast({ type: 'error', title: t('common.status'), message: e?.message || t('recruiter.campaigns.updateFailed') });
    } finally {
      setEditSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleting) return;
    setDeleteLoading(true);
    try {
      const res: any = await campaignsService.delete(String(deleting.id));
      customToast({ type: 'success', title: t('common.status'), message: res?.success ? t('recruiter.campaigns.deleted') : t('recruiter.campaigns.deleted') });
      setDeleting(null);
      fetchCampaigns();
    } catch (e: any) {
      customToast({ type: 'error', title: t('common.status'), message: e?.message || t('recruiter.campaigns.deleteFailed') });
    } finally {
      setDeleteLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{t('campaign.title')}</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{t('campaign.subtitle')}</p>
        </div>
        <Button variant="primary" leftIcon={<Plus className="h-4 w-4" />} onClick={() => navigate('/campaigns/new')}>{t('campaign.newCampaign')}</Button>
      </div>

      {loading ? (
        <div className="flex justify-center py-16"><Loader2 className="h-8 w-8 animate-spin text-purple-600" /></div>
      ) : campaigns.length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center">
            <p className="text-gray-500">{t('common.noData')}</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4">
          {campaigns.map((c: any) => (
            <Card key={c.id} className="hover:shadow-md transition-shadow">
              <CardContent className="p-5">
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-4 min-w-0 flex-1 cursor-pointer" onClick={() => navigate(`/campaigns/${c.id}`)}>
                    <div className="h-10 w-10 rounded-xl bg-purple-100 dark:bg-purple-500/10 flex items-center justify-center text-purple-600 dark:text-purple-400 shrink-0">
                      <Mail className="h-5 w-5" />
                    </div>
                    <div className="min-w-0">
                      <h3 className="font-semibold text-gray-900 dark:text-white truncate">{c.title || t('recruiter.campaigns.campaignId').replace('{id}', String(c.id))}</h3>
                      <div className="flex items-center gap-3 mt-1 text-xs text-gray-400 flex-wrap">
                        <span className="inline-flex items-center gap-1"><Send className="h-3 w-3" /> {c.candidate_count ?? c.recipients ?? c.total_candidates ?? 0} {t('candidates.candidatesLabel')}</span>
                        {c.total_files !== undefined && c.total_files !== null && (
                          <span className="inline-flex items-center gap-1">
                            {c.worker_status === 'completed'
                              ? <><Eye className="h-3 w-3" /> {c.processed_files ?? 0}/{c.total_files}</>
                              : <><Loader2 className="h-3 w-3 animate-spin" /> {WORKER_STATUS_LABEL[c.worker_status] || c.worker_status}</>}
                          </span>
                        )}
                        {c.created_at && (
                          <span className="text-gray-400">{new Date(c.created_at).toLocaleDateString()}</span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {(() => {
                      if (c.worker_status === 'processing' || c.status === 'processing') {
                        return (
                          <Button variant="outline" size="sm" disabled className="pointer-events-none">
                            <Loader2 className="h-3.5 w-3.5 animate-spin" /> ...
                          </Button>
                        );
                      }
                      if (c.worker_status === 'pending' || c.status === 'pending' || c.status === 'draft') {
                        return <Button variant="primary" size="sm" onClick={() => navigate(`/campaigns/${c.id}`)}><Upload className="h-3.5 w-3.5" /> {t('common.upload')}</Button>;
                      }
                      if (c.worker_status === 'completed' || c.status === 'completed' || c.status === 'sent' || c.status === 'active') {
                        return <Button variant="outline" size="sm" onClick={() => navigate(`/campaigns/${c.id}`)}><Eye className="h-3.5 w-3.5" /> {t('common.view')}</Button>;
                      }
                      return <Button variant="outline" size="sm" onClick={() => navigate(`/campaigns/${c.id}`)}>{t('campaign.viewCampaign')}</Button>;
                    })()}
                    <Badge variant="primary" size="sm" className={cn(statusColors[c.status] || '')}>{c.status || 'draft'}</Badge>
                    <Button variant="ghost" size="sm" aria-label={t('common.edit')} onClick={() => openEdit(c)}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="sm" aria-label={t('common.delete')} className="text-red-600 hover:text-red-700 dark:hover:text-red-400" onClick={() => setDeleting(c)}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={!!editing} onOpenChange={(open) => !open && setEditing(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('common.edit')}</DialogTitle>
            <DialogDescription>{t('campaign.title')}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('campaign.col.campaignName')}</label>
              <Input value={editTitle} onChange={(e) => setEditTitle(e.target.value)} placeholder={t('campaign.col.campaignName')} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('common.status')}</label>
              <Select value={editStatus} onValueChange={setEditStatus}>
                <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">{t('common.active')}</SelectItem>
                  <SelectItem value="archived">{t('jobs.status.archived')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setEditing(null)}>{t('common.cancel')}</Button>
            <Button variant="primary" onClick={handleSaveEdit} disabled={editSaving} leftIcon={editSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : undefined}>
              {editSaving ? '...' : t('common.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(open) => !open && setDeleting(null)}
        title={t('common.delete')}
        description={deleting ? t('recruiter.campaigns.deleteConfirm').replace('{title}', deleting.title || t('recruiter.campaigns.campaignId').replace('{id}', String(deleting.id))) : ''}
        confirmLabel={t('common.delete')}
        cancelLabel={t('common.cancel')}
        variant="danger"
        loading={deleteLoading}
        onConfirm={handleDelete}
      />
    </div>
  );
}
