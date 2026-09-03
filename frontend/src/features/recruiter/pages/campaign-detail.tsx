import { useState, useEffect, Fragment, useRef } from 'react';
import { useParams, useNavigate } from 'react-router';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Progress } from '@/shared/components/ui/progress';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/shared/components/ui/table';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Checkbox } from '@/shared/components/ui/checkbox';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/shared/components/ui/select';
import { customToast } from '@/shared/components/ui/toast';
import { useLanguage } from '@/contexts/language-context';
import { CVEvaluation } from '@/shared/components/cv-evaluation';
import { campaignsService } from '@/services/campaigns.service';
import { Send, Eye, Loader2, TrendingUp, BarChart3, UserPlus, Pencil, ChevronDown, ChevronRight, ClipboardList, Upload, Star, Download, FileText, Bell, Users, Layers, AlertTriangle, CheckCircle, Shield } from 'lucide-react';

interface RubricSkill {
  name: string;
  category?: string;
}

interface RubricMatch {
  match_percentage: number;
  total_skills: number;
  matched_skills: RubricSkill[];
  missing_skills: RubricSkill[];
}

interface RubricInfo {
  id: number;
  title: string;
  category_count: number;
  skill_count: number;
  seniority?: string;
}

interface CampaignCandidate {
  id: number;
  full_name?: string;
  name?: string;
  email: string;
  status?: string;
  cv_score: number | null;
  interview_score: number;
  interview_state: string;
  interview_progress: number;
  is_registered: boolean;
  can_invite: boolean;
  rubric_match: RubricMatch | null;
  opened_at?: string | null;
  clicked_at?: string | null;
  cv_rubric_weighted?: boolean | null;
  cv_scoring_method?: string | null;
  cv_coverage_pct?: number | null;
  cv_skill_breakdown?: CVEvalSkill[];
  cv_evidence?: CVEvalEvidence[];
  cv_missing_skills?: string[];
}

interface CVEvalSkill {
  name: string;
  score: number;
  weight?: number | null;
  normalized_weight?: number | null;
  level?: string | null;
  feedback?: string | null;
  category?: string | null;
}

interface CVEvalEvidence {
  skill_name: string;
  score?: number | null;
  weight?: number | null;
  feedback?: string | null;
}

const statusBadge: Record<string, 'warning' | 'primary' | 'success' | 'danger'> = {
  draft: 'warning', active: 'primary', completed: 'success', paused: 'danger',
};

const DONE_STATES = ['completed', 'flagged'];

const matchVariant = (pct: number): 'success' | 'warning' | 'danger' =>
  pct >= 70 ? 'success' : pct >= 40 ? 'warning' : 'danger';

const isPlaceholderEmail = (c: CampaignCandidate) =>
  !c.can_invite && (c.email.toLowerCase().includes('no-email') || c.email.toLowerCase().endsWith('@import.local'));

const getErrorMessage = (e: unknown) => (e instanceof Error ? e.message : 'Please try again.');

export default function CampaignDetailPage() {
  const { t } = useLanguage();
  const { id } = useParams();
  const navigate = useNavigate();
  const [campaign, setCampaign] = useState<any>(null);
  const [candidates, setCandidates] = useState<CampaignCandidate[]>([]);
  const [analytics, setAnalytics] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [invitingId, setInvitingId] = useState<number | null>(null);
  const [bulkAction, setBulkAction] = useState<'selected' | 'all' | null>(null);
  const [editingEmailId, setEditingEmailId] = useState<number | null>(null);
  const [emailDraft, setEmailDraft] = useState('');
  const [savingEmailId, setSavingEmailId] = useState<number | null>(null);
  const [uploading, setUploading] = useState(false);
  const [consentConfirmed, setConsentConfirmed] = useState(false);

  // Pagination, filtering, sorting state
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [statusFilter, setStatusFilter] = useState('all');
  const [sortBy, setSortBy] = useState('cv_score');
  const [sortDir, setSortDir] = useState<'desc' | 'asc'>('desc');
  const [searchQuery, setSearchQuery] = useState('');
  const [totalCandidates, setTotalCandidates] = useState(0);
  const [totalPages, setTotalPages] = useState(1);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchCandidates = (
    p = page,
    ps = pageSize,
    st = statusFilter,
    sb = sortBy,
    sd = sortDir,
    sq = searchQuery
  ) => {
    if (!id) return;
    const params: any = {
      page: p,
      page_size: ps,
      status: st === 'all' ? undefined : st,
      sort_by: sb,
      sort_dir: sd,
      search: sq.trim() || undefined,
    };
    campaignsService
      .getCandidates(id, params)
      .then((res: any) => {
        if (res && Array.isArray(res.items)) {
          setCandidates(res.items);
          setTotalCandidates(res.total ?? res.items.length);
          setTotalPages(res.total_pages ?? 1);
        } else if (Array.isArray(res)) {
          setCandidates(res);
          setTotalCandidates(res.length);
          setTotalPages(1);
        } else {
          setCandidates([]);
          setTotalCandidates(0);
          setTotalPages(1);
        }
      })
      .catch(() => setCandidates([]));
  };

  const handleUploadCvs = async (files: FileList | null) => {
    if (!id || !files || files.length === 0) return;
    const jobId = campaign?.job_id;
    if (!jobId) {
      customToast({
        type: 'warning',
        title: 'No Job',
        message: 'This campaign has no linked job. Assign a job before uploading CVs.',
      });
      return;
    }
    if (!consentConfirmed) {
      customToast({
        type: 'warning',
        title: 'Consent Required',
        message: 'Please confirm candidate consent before uploading CVs.',
      });
      return;
    }
    setUploading(true);
    try {
      const formData = new FormData();
      Array.from(files).forEach((f) => formData.append('files', f));
      formData.append('job_id', String(jobId));
      formData.append('campaign_id', String(id));
      formData.append('consent_confirmed', 'true');
      const up = await campaignsService.uploadCvsToCampaign(formData);

      const uploadedCount = up?.uploaded ?? 0;
      const skippedDuplicates = up?.skipped_duplicates ?? 0;
      const failedCount = up?.failed ?? 0;
      const duplicateEmails: string[] = up?.duplicate_emails || [];

      if (uploadedCount > 0) {
        customToast({
          type: 'success',
          title: 'CVs Uploaded',
          message: `${uploadedCount} CV${uploadedCount === 1 ? '' : 's'} queued for analysis.`,
        });
      }

      if (skippedDuplicates > 0) {
        const dupsList = duplicateEmails.slice(0, 3).join(', ');
        customToast({
          type: 'warning',
          title: 'Duplicate CVs Skipped',
          message: `${skippedDuplicates} duplicate CV${skippedDuplicates === 1 ? '' : 's'} skipped${dupsList ? `: ${dupsList}` : ''}${duplicateEmails.length > 3 ? '…' : ''}`,
        });
      }

      if (failedCount > 0) {
        customToast({
          type: 'error',
          title: 'Upload Errors',
          message: `${failedCount} file${failedCount === 1 ? '' : 's'} failed processing.`,
        });
      }

      if (uploadedCount === 0 && skippedDuplicates === 0 && failedCount === 0) {
        customToast({
          type: 'warning',
          title: 'No CVs Uploaded',
          message: 'No valid PDFs were processed.',
        });
      }

      fetchCandidates();
    } catch (e) {
      customToast({ type: 'error', title: 'Upload failed', message: getErrorMessage(e) });
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // P2 features state
  const [activeTab, setActiveTab] = useState<'candidates' | 'team'>('candidates');
  const [staleInvites, setStaleInvites] = useState<any[]>([]);
  const [duplicateSummary, setDuplicateSummary] = useState<any>(null);
  const [teamMembers, setTeamMembers] = useState<any[]>([]);
  const [nudging, setNudging] = useState(false);
  const [addMemberEmail, setAddMemberEmail] = useState('');
  const [addMemberRole, setAddMemberRole] = useState('member');
  const [addingMember, setAddingMember] = useState(false);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    Promise.all([
      campaignsService.get(id).catch(() => null),
      campaignsService
        .getCandidates(id, { page: 1, page_size: pageSize, sort_by: sortBy, sort_dir: sortDir })
        .catch(() => null),
      campaignsService.getAnalytics(id).catch(() => null),
      campaignsService.getStaleInvites(id, 3).catch(() => []),
      campaignsService.getDuplicateSummary(id).catch(() => null),
      campaignsService.getTeam(id).catch(() => null),
    ])
      .then(([c, candsRes, analyticsData, staleRes, dupRes, teamRes]) => {
        setCampaign(c);
        const resData = candsRes as any;
        if (resData && Array.isArray(resData.items)) {
          setCandidates(resData.items);
          setTotalCandidates(resData.total ?? resData.items.length);
          setTotalPages(resData.total_pages ?? 1);
        } else if (Array.isArray(resData)) {
          setCandidates(resData);
          setTotalCandidates(resData.length);
          setTotalPages(1);
        } else {
          setCandidates([]);
        }
        setAnalytics(analyticsData);
        if (Array.isArray(staleRes)) setStaleInvites(staleRes);
        if (dupRes) setDuplicateSummary(dupRes);
        if (teamRes?.team) setTeamMembers(teamRes.team);
      })
      .finally(() => setLoading(false));
  }, [id]);

  const handleNudgeStale = async () => {
    if (!id || staleInvites.length === 0) return;
    setNudging(true);
    try {
      const res = await campaignsService.nudgeStaleCandidates(id);
      customToast({
        type: 'success',
        title: 'Nudge Sent',
        message: res?.message || `Sent reminder to ${staleInvites.length} stale candidate(s).`,
      });
      setStaleInvites([]);
    } catch (e) {
      customToast({ type: 'error', title: 'Nudge Failed', message: getErrorMessage(e) });
    } finally {
      setNudging(false);
    }
  };

  const handleAddTeamMember = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id || !addMemberEmail.trim()) return;
    setAddingMember(true);
    try {
      const res = await campaignsService.addTeamMember(id, addMemberEmail.trim(), addMemberRole);
      customToast({
        type: 'success',
        title: 'Team Member Updated',
        message: res?.message || `Added ${addMemberEmail} to campaign team.`,
      });
      setAddMemberEmail('');
      const updatedTeam = await campaignsService.getTeam(id);
      if (updatedTeam?.team) setTeamMembers(updatedTeam.team);
    } catch (e) {
      customToast({ type: 'error', title: 'Add Member Failed', message: getErrorMessage(e) });
    } finally {
      setAddingMember(false);
    }
  };

  useEffect(() => {
    if (loading) return;
    fetchCandidates(page, pageSize, statusFilter, sortBy, sortDir, searchQuery);
  }, [page, pageSize, statusFilter, sortBy, sortDir]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchCandidates(1, pageSize, statusFilter, sortBy, sortDir, searchQuery);
  };

  const invitableIds = candidates.filter((c) => c.can_invite && c.status !== 'invited').map((c) => c.id);
  const allInvitableSelected = invitableIds.length > 0 && invitableIds.every((appId) => selectedIds.includes(appId));

  const toggleSelect = (appId: number) => {
    setSelectedIds((prev) => (prev.includes(appId) ? prev.filter((x) => x !== appId) : [...prev, appId]));
  };

  const toggleSelectAll = () => {
    setSelectedIds((prev) =>
      allInvitableSelected
        ? prev.filter((x) => !invitableIds.includes(x))
        : Array.from(new Set([...prev, ...invitableIds]))
    );
  };

  const handleInvite = async (c: CampaignCandidate) => {
    if (!id) return;
    setInvitingId(c.id);
    try {
      const res = await campaignsService.inviteCandidate(id, c.id);
      customToast({
        type: 'success',
        title: 'Invitation sent',
        message: res?.message || `${c.full_name || c.name || c.email} was invited.`,
      });
      setCandidates((prev) => prev.map((x) => (x.id === c.id ? { ...x, status: 'invited' } : x)));
      fetchCandidates();
    } catch (e) {
      customToast({ type: 'error', title: 'Invite failed', message: getErrorMessage(e) });
    } finally {
      setInvitingId(null);
    }
  };

  const handleShortlist = async (c: CampaignCandidate) => {
    if (!id) return;
    try {
      await campaignsService.shortlistCandidate(id, c.id);
      customToast({
        type: 'success',
        title: 'Candidate Shortlisted',
        message: `${c.full_name || c.email} moved to shortlist.`,
      });
      setCandidates(prev =>
        prev.map(item => (item.id === c.id ? { ...item, status: 'shortlisted' } : item))
      );
    } catch (e) {
      customToast({ type: 'error', title: 'Shortlist failed', message: getErrorMessage(e) });
    }
  };

  const handleBulkInvite = async (appIds: number[], action: 'selected' | 'all') => {
    if (!id || appIds.length === 0) return;
    setBulkAction(action);
    try {
      const res = await campaignsService.inviteAll(id, appIds);
      const sentCount = res?.sent ?? appIds.length;
      const quotaMsg = res?.remaining_quota != null ? ` Remaining quota: ${res.remaining_quota}.` : '';
      customToast({
        type: 'success',
        title: 'Bulk Invite Summary',
        message: `Successfully invited ${sentCount} of ${appIds.length} candidate(s).${quotaMsg}`,
      });
      setSelectedIds([]);
      fetchCandidates();
    } catch (e) {
      customToast({ type: 'error', title: 'Bulk invite failed', message: getErrorMessage(e) });
    } finally {
      setBulkAction(null);
    }
  };

  const handleSaveEmail = async (c: CampaignCandidate) => {
    if (!id) return;
    const email = emailDraft.trim();
    if (!email) return;
    setSavingEmailId(c.id);
    try {
      await campaignsService.updateCandidateEmail(id, c.id, email);
      customToast({ type: 'success', title: 'Email updated', message: `${email} saved.` });
      setEditingEmailId(null);
      setEmailDraft('');
      fetchCandidates();
    } catch (e) {
      customToast({ type: 'error', title: 'Update failed', message: getErrorMessage(e) });
    } finally {
      setSavingEmailId(null);
    }
  };

  const cancelEditEmail = () => {
    setEditingEmailId(null);
    setEmailDraft('');
  };

  if (loading) {
    return <div className="flex justify-center py-16"><Loader2 className="h-8 w-8 animate-spin text-purple-600" /></div>;
  }
  if (!campaign) {
    return <div className="text-center py-16 text-gray-500">Campaign not found.</div>;
  }

  const detailStats = campaign.stats || {};
  const an = analytics || {};
  const rubric = (campaign.rubric as RubricInfo | null) ?? null;
  const sent = an.emails_sent ?? detailStats.total_candidates ?? campaign.candidate_count ?? 0;
  const opened = an.emails_opened ?? detailStats.opened ?? campaign.opened ?? 0;
  const clicked = an.emails_clicked ?? campaign.clicked_count ?? 0;
  const replied = an.responses_received ?? campaign.replied_count ?? 0;
  const openRate = an.open_rate ?? (sent ? Math.round((opened / sent) * 100) : 0);
  const clickRate = an.click_rate ?? (opened ? Math.round((clicked / opened) * 100) : 0);
  const avgCvScore = an.avg_cv_score ?? detailStats.avg_cv_score ?? null;
  const qualifiedCount = an.qualified_count ?? 0;
  const responseRate = an.response_rate != null ? `${an.response_rate}%` : '—';
  const isProcessing = campaign.processing_status === 'processing' || campaign.worker_status === 'processing';

  const stats = [
    { label: t('campaign.candidates'), value: detailStats.total_candidates ?? campaign.candidate_count ?? 0, icon: Send, color: 'text-purple-500', bg: 'bg-purple-100 dark:bg-purple-500/20' },
    { label: t('cprofile.matchScore'), value: avgCvScore != null ? `${avgCvScore}%` : '—', icon: TrendingUp, color: 'text-blue-500', bg: 'bg-blue-100 dark:bg-blue-500/20' },
    { label: `${t('candidates.shortlisted')} (70%+)`, value: qualifiedCount, icon: Star, color: 'text-amber-500', bg: 'bg-amber-100 dark:bg-amber-500/20' },
    { label: t('campaign.opened'), value: `${openRate}%`, icon: Eye, color: 'text-emerald-500', bg: 'bg-emerald-100 dark:bg-emerald-500/20' },
    { label: t('campaign.analytics'), value: responseRate, icon: BarChart3, color: 'text-rose-500', bg: 'bg-rose-100 dark:bg-rose-500/20' },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div>
            <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">{campaign.batch_name || campaign.title || `Campaign #${campaign.id}`}</h1>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Campaign #{id}</p>
          </div>
          <Badge variant={statusBadge[campaign.status] || 'warning'} size="md" className="capitalize">{campaign.status || 'draft'}</Badge>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-300 cursor-pointer select-none">
            <Checkbox
              checked={consentConfirmed}
              onCheckedChange={(checked) => setConsentConfirmed(Boolean(checked))}
            />
            <span>I confirm consent to process candidate CVs</span>
          </label>

          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            multiple
            className="hidden"
            onChange={(e) => handleUploadCvs(e.target.files)}
          />
          <Button
            variant="outline"
            leftIcon={uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
            onClick={() => {
              if (!consentConfirmed) {
                customToast({
                  type: 'warning',
                  title: t('common.status'),
                  message: 'Please check the consent confirmation box before uploading CVs.',
                });
                return;
              }
              fileInputRef.current?.click();
            }}
            disabled={uploading}
          >
            {uploading ? '...' : t('campaign.uploadCvs')}
          </Button>

          <Button
            variant="outline"
            leftIcon={<Download className="h-4 w-4" />}
            onClick={() => window.open(campaignsService.exportCSV(id, 'all'), '_blank')}
          >
            CSV
          </Button>

          <Button
            variant="outline"
            leftIcon={<FileText className="h-4 w-4 text-purple-600 dark:text-purple-400" />}
            onClick={() => window.open(campaignsService.exportPDF(id, 'shortlisted'), '_blank')}
          >
            PDF Shortlist
          </Button>

          <Button
            variant="outline"
            leftIcon={<FileText className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />}
            onClick={() => window.open(campaignsService.exportPDF(id, 'all', true), '_blank')}
          >
            Tiered PDF
          </Button>

          <Button
            variant="outline"
            leftIcon={<BarChart3 className="h-4 w-4 text-indigo-500" />}
            onClick={() => navigate(`/campaigns/compare?ids=${id}`)}
          >
            {t('compare.title')}
          </Button>
        </div>
      </div>

      {isProcessing && (
        <Card className="bg-purple-50 border-purple-200 dark:bg-purple-900/10 dark:border-purple-800 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Loader2 className="h-5 w-5 animate-spin text-purple-600 dark:text-purple-400" />
              <div>
                <p className="text-sm font-semibold text-purple-900 dark:text-purple-200">AI CV Screening in Progress</p>
                <p className="text-xs text-purple-700 dark:text-purple-300">
                  {campaign.processed_files ?? 0} of {campaign.total_files ?? 0} files screened.
                </p>
              </div>
            </div>
            <Button size="sm" variant="ghost" className="text-xs text-purple-700 dark:text-purple-300" onClick={() => fetchCandidates()}>
              {t('common.refresh')}
            </Button>
          </div>
        </Card>
      )}

      {rubric ? (
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-purple-100 text-purple-600 dark:bg-purple-500/20">
              <ClipboardList className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="truncate text-sm font-semibold text-gray-900 dark:text-white">{rubric.title}</span>
                <Badge variant="primary" size="sm">Rubric</Badge>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {rubric.category_count} categories · {rubric.skill_count} skills
                {rubric.seniority ? ` · ${rubric.seniority}` : ''}
              </p>
            </div>
          </div>
        </Card>
      ) : null}

      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {stats.map((stat) => (
          <Card key={stat.label} className="p-5">
            <div className="flex items-center gap-3">
              <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${stat.bg} ${stat.color}`}>
                <stat.icon className="h-5 w-5" />
              </div>
              <div>
                <div className="text-2xl font-extrabold text-gray-900 dark:text-white">{stat.value}</div>
                <div className="text-xs text-gray-500">{stat.label}</div>
              </div>
            </div>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader><CardTitle className="text-sm">{t('campaign.analytics')}</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div><div className="flex justify-between text-sm mb-1"><span>{t('campaign.opened')}</span><span className="font-bold">{openRate}%</span></div><Progress value={openRate} className="h-2" /></div>
            <div><div className="flex justify-between text-sm mb-1"><span>{t('campaign.clicked')}</span><span className="font-bold">{clickRate}%</span></div><Progress value={clickRate} className="h-2" /></div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-sm">{t('org.companyPipeline')}</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div><div className="flex justify-between text-sm mb-1"><span>{t('cprofile.matchScore')}</span><span className="font-bold">{detailStats.avg_cv_score ?? '—'}</span></div></div>
            <div><div className="flex justify-between text-sm mb-1"><span>{t('org.interview')}</span><span className="font-bold">{detailStats.interviewed ?? 0}</span></div></div>
            <div><div className="flex justify-between text-sm mb-1"><span>{t('campaign.sendInvites')}</span><span className="font-bold">{detailStats.invited ?? 0}</span></div></div>
          </CardContent>
        </Card>
      </div>

      {/* Stale Invites Re-engagement Banner */}
      {staleInvites.length > 0 && (
        <Card className="bg-amber-500/10 border-amber-500/30 p-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <AlertTriangle className="h-5 w-5 text-amber-500 shrink-0" />
              <div>
                <p className="text-sm font-semibold text-amber-900 dark:text-amber-200">
                  {staleInvites.length} Candidate(s) Invited &gt; 3 Days Ago Have Not Started
                </p>
                <p className="text-xs text-amber-700 dark:text-amber-300">
                  Send a friendly follow-up nudge email to encourage them to take their AI interview.
                </p>
              </div>
            </div>
            <Button
              size="sm"
              variant="outline"
              className="border-amber-500/50 text-amber-900 dark:text-amber-200 hover:bg-amber-500/20"
              leftIcon={nudging ? <Loader2 className="h-4 w-4 animate-spin" /> : <Bell className="h-4 w-4 text-amber-500" />}
              onClick={handleNudgeStale}
              disabled={nudging}
            >
              {nudging ? 'Sending Reminders…' : 'Send Nudge Reminders'}
            </Button>
          </div>
        </Card>
      )}

      {/* Duplicate Candidates Alert */}
      {duplicateSummary && duplicateSummary.duplicate_candidate_count > 0 && (
        <Card className="bg-blue-500/10 border-blue-500/30 p-4">
          <div className="flex items-center gap-3">
            <Layers className="h-5 w-5 text-blue-500 shrink-0" />
            <div>
              <p className="text-sm font-semibold text-blue-900 dark:text-blue-200">
                {duplicateSummary.duplicate_candidate_count} Candidate(s) Found in Other Campaigns
              </p>
              <p className="text-xs text-blue-700 dark:text-blue-300">
                These candidates also submitted applications to other active or past campaigns in your company.
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* Navigation Tabs */}
      <div className="flex items-center border-b border-gray-200 dark:border-gray-800 space-x-6">
        <button
          onClick={() => setActiveTab('candidates')}
          className={`pb-3 text-sm font-semibold border-b-2 transition flex items-center gap-2 ${
            activeTab === 'candidates'
              ? 'border-purple-600 text-purple-600 dark:text-purple-400'
              : 'border-transparent text-gray-500 hover:text-gray-900 dark:hover:text-white'
          }`}
        >
          <Users className="w-4 h-4" /> Candidates ({totalCandidates})
        </button>
        <button
          onClick={() => setActiveTab('team')}
          className={`pb-3 text-sm font-semibold border-b-2 transition flex items-center gap-2 ${
            activeTab === 'team'
              ? 'border-purple-600 text-purple-600 dark:text-purple-400'
              : 'border-transparent text-gray-500 hover:text-gray-900 dark:hover:text-white'
          }`}
        >
          <Shield className="w-4 h-4" /> Campaign Team ({teamMembers.length})
        </button>
      </div>

      {activeTab === 'team' && (
        <Card className="p-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
            <div>
              <h3 className="text-base font-bold text-gray-900 dark:text-white">Campaign Team Access</h3>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Company members assigned to manage this campaign.
              </p>
            </div>
            <form onSubmit={handleAddTeamMember} className="flex items-center gap-2">
              <Input
                type="email"
                placeholder="colleague@company.com"
                value={addMemberEmail}
                onChange={(e) => setAddMemberEmail(e.target.value)}
                className="h-9 w-64 text-xs"
                required
              />
              <Select value={addMemberRole} onValueChange={setAddMemberRole}>
                <SelectTrigger className="h-9 w-28 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="admin">Admin</SelectItem>
                  <SelectItem value="member">Member</SelectItem>
                  <SelectItem value="viewer">Viewer</SelectItem>
                </SelectContent>
              </Select>
              <Button type="submit" variant="primary" size="sm" loading={addingMember} className="h-9 text-xs">
                Add Member
              </Button>
            </form>
          </div>

          <div className="space-y-3">
            {teamMembers.length === 0 ? (
              <p className="text-xs text-gray-500 text-center py-8">No team members assigned yet.</p>
            ) : (
              teamMembers.map((m) => (
                <div key={m.id} className="flex items-center justify-between p-3.5 bg-gray-50 dark:bg-gray-800/50 rounded-xl border border-gray-100 dark:border-gray-800">
                  <div className="flex items-center gap-3">
                    <div className="h-9 w-9 rounded-full bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 flex items-center justify-center font-bold text-sm">
                      {m.name?.[0]?.toUpperCase() || 'U'}
                    </div>
                    <div>
                      <span className="text-sm font-semibold text-gray-900 dark:text-white block">{m.name}</span>
                      <span className="text-xs text-gray-500 dark:text-gray-400 block">{m.email}</span>
                    </div>
                  </div>
                  <Badge variant={m.role === 'admin' ? 'primary' : 'outline'} size="sm" className="capitalize">
                    {m.role}
                  </Badge>
                </div>
              ))
            )}
          </div>
        </Card>
      )}

      {activeTab === 'candidates' && (
        <Card>
        <CardHeader className="flex flex-col space-y-4 sm:flex-row sm:items-center sm:justify-between sm:space-y-0 pb-3">
          <CardTitle className="text-sm">Candidates ({totalCandidates})</CardTitle>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" loading={bulkAction === 'selected'} disabled={selectedIds.length === 0} onClick={() => handleBulkInvite(selectedIds, 'selected')}>
              <Send className="h-4 w-4" /> Invite Selected ({selectedIds.length})
            </Button>
            <Button variant="primary" size="sm" loading={bulkAction === 'all'} disabled={invitableIds.length === 0} onClick={() => handleBulkInvite(invitableIds, 'all')}>
              <UserPlus className="h-4 w-4" /> Invite All
            </Button>
          </div>
        </CardHeader>

        {/* Filter and Sort Toolbar */}
        <div className="px-6 pb-4 pt-1 flex flex-wrap items-center justify-between gap-3 border-b border-gray-100 dark:border-gray-800">
          <form onSubmit={handleSearchSubmit} className="flex items-center gap-2">
            <Input
              type="text"
              placeholder="Search candidate name or email..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-8 w-64 text-xs"
            />
            <Button type="submit" variant="ghost" size="sm" className="h-8 text-xs">Search</Button>
          </form>

          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-gray-500">Status:</span>
              <Select value={statusFilter} onValueChange={(val) => { setStatusFilter(val); setPage(1); }}>
                <SelectTrigger className="h-8 text-xs w-36">
                  <SelectValue placeholder="All Statuses" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Statuses</SelectItem>
                  <SelectItem value="screening">Screening</SelectItem>
                  <SelectItem value="invited">Invited</SelectItem>
                  <SelectItem value="interviewing">Interviewing</SelectItem>
                  <SelectItem value="shortlisted">Shortlisted</SelectItem>
                  <SelectItem value="rejected">Rejected</SelectItem>
                  <SelectItem value="failed">Failed</SelectItem>
                  <SelectItem value="pending">Pending</SelectItem>
                  <SelectItem value="analyzing">Analyzing</SelectItem>
                  <SelectItem value="analysis_failed">Analysis Failed</SelectItem>
                  <SelectItem value="reviewed">Reviewed</SelectItem>
                  <SelectItem value="hired">Hired</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center gap-1.5">
              <span className="text-xs text-gray-500">Sort by:</span>
              <Select value={sortBy} onValueChange={(val) => { setSortBy(val); setPage(1); }}>
                <SelectTrigger className="h-8 text-xs w-36">
                  <SelectValue placeholder="CV Match Score" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="cv_score">CV Match Score</SelectItem>
                  <SelectItem value="created_at">Date Created</SelectItem>
                  <SelectItem value="status">Status</SelectItem>
                  <SelectItem value="full_name">Candidate Name</SelectItem>
                  <SelectItem value="email">Email</SelectItem>
                </SelectContent>
              </Select>
              <Button
                variant="ghost"
                size="sm"
                className="h-8 px-2 text-xs font-semibold"
                onClick={() => { setSortDir(prev => prev === 'desc' ? 'asc' : 'desc'); setPage(1); }}
              >
                {sortDir.toUpperCase()}
              </Button>
            </div>

            <div className="flex items-center gap-1.5">
              <span className="text-xs text-gray-500">Per page:</span>
              <Select value={String(pageSize)} onValueChange={(val) => { setPageSize(Number(val)); setPage(1); }}>
                <SelectTrigger className="h-8 text-xs w-20">
                  <SelectValue placeholder="50" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="25">25</SelectItem>
                  <SelectItem value="50">50</SelectItem>
                  <SelectItem value="100">100</SelectItem>
                  <SelectItem value="200">200</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>

        <CardContent className="pt-4">
          {candidates.length === 0 ? (
            <div className="py-12 text-center">
              {statusFilter !== 'all' || searchQuery ? (
                <div className="space-y-3">
                  <p className="text-sm text-gray-500">No candidates match the selected filter.</p>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setStatusFilter('all');
                      setSearchQuery('');
                      setPage(1);
                    }}
                  >
                    Clear Filters
                  </Button>
                </div>
              ) : isProcessing ? (
                <div className="space-y-2">
                  <Loader2 className="h-6 w-6 animate-spin text-purple-600 mx-auto" />
                  <p className="text-sm text-gray-500 font-medium">CV screening in progress...</p>
                  <p className="text-xs text-gray-400">Candidates will appear here as soon as they are processed.</p>
                </div>
              ) : (
                <div className="space-y-2">
                  <p className="text-sm text-gray-500">No candidates in this campaign yet.</p>
                  <p className="text-xs text-gray-400">Click "Upload CVs" above to add candidates to this campaign.</p>
                </div>
              )}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>
                    <Checkbox
                      checked={allInvitableSelected}
                      disabled={invitableIds.length === 0}
                      onCheckedChange={toggleSelectAll}
                      aria-label="Select all invitable candidates"
                    />
                  </TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>CV Match</TableHead>
                  <TableHead>Interview</TableHead>
                  <TableHead>Opened</TableHead>
                  <TableHead>Clicked</TableHead>
                  <TableHead>Analysis</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {candidates.map((c) => {
                  const done = DONE_STATES.includes(c.interview_state);
                  const progress = done ? 100 : c.interview_progress ?? 0;
                  return (
                    <Fragment key={c.id}>
                      <TableRow className="cursor-pointer" onClick={() => setExpandedId(expandedId === c.id ? null : c.id)}>
                        <TableCell onClick={(e) => e.stopPropagation()}>
                          <Checkbox
                            checked={selectedIds.includes(c.id)}
                            disabled={!c.can_invite || c.status === 'invited'}
                            onCheckedChange={() => toggleSelect(c.id)}
                            aria-label={`Select ${c.full_name || c.name || c.email}`}
                          />
                        </TableCell>
                        <TableCell className="font-medium">
                          <span className="inline-flex items-center gap-1.5">
                            {expandedId === c.id ? <ChevronDown className="h-4 w-4 text-purple-500" /> : <ChevronRight className="h-4 w-4 text-gray-400" />}
                            {c.full_name || c.name}
                          </span>
                        </TableCell>
                        <TableCell>
                          {editingEmailId === c.id ? (
                            <div className="flex items-center gap-1.5">
                              <Input
                                type="email"
                                value={emailDraft}
                                onChange={(e) => setEmailDraft(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') handleSaveEmail(c);
                                  if (e.key === 'Escape') cancelEditEmail();
                                }}
                                className="h-7 w-52 text-xs"
                                autoFocus
                              />
                              <Button size="sm" variant="success" className="h-7 px-2.5 text-xs" loading={savingEmailId === c.id} onClick={(e) => { e.stopPropagation(); handleSaveEmail(c); }}>Save</Button>
                              <Button size="sm" variant="ghost" className="h-7 px-2.5 text-xs" onClick={(e) => { e.stopPropagation(); cancelEditEmail(); }}>Cancel</Button>
                            </div>
                          ) : (
                            <span className={isPlaceholderEmail(c) ? 'italic text-gray-400' : ''}>{c.email}</span>
                          )}
                        </TableCell>
                        <TableCell>
                          <Badge variant={c.status === 'invited' ? 'primary' : c.status === 'screening' ? 'success' : c.status === 'failed' ? 'danger' : 'warning'} size="sm" className="capitalize">
                            {c.status || 'pending'}
                          </Badge>
                        </TableCell>
                        <TableCell className="font-semibold">{c.cv_score != null ? `${c.cv_score}%` : '—'}</TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <Progress value={progress} className="h-1.5 w-16" />
                            <span className="text-xs text-gray-500">{done ? 'Done' : `${c.interview_state ?? 'not_started'}`}</span>
                          </div>
                        </TableCell>
                        <TableCell>{c.opened_at ? <span className="text-emerald-600">Yes</span> : <span className="text-gray-400">No</span>}</TableCell>
                        <TableCell>{c.clicked_at ? <span className="text-emerald-600">Yes</span> : <span className="text-gray-400">No</span>}</TableCell>
                        <TableCell>
                          {done ? (
                            <Button variant="outline" size="sm" onClick={(e) => { e.stopPropagation(); navigate(`/recruiter/interview-analysis?id=${c.id}`); }}>
                              View Analysis
                            </Button>
                          ) : (
                            <span className="text-xs text-gray-400">Not available</span>
                          )}
                        </TableCell>
                        <TableCell onClick={(e) => e.stopPropagation()}>
                          <div className="flex items-center gap-1.5">
                            {isPlaceholderEmail(c) ? (
                              <Button size="sm" variant="ghost" className="text-xs text-purple-600" onClick={() => { setEditingEmailId(c.id); setEmailDraft(c.email); }}>
                                <Pencil className="h-3.5 w-3.5" /> Edit Email
                              </Button>
                            ) : (
                              <>
                                <Button
                                  size="sm"
                                  variant={c.status === 'shortlisted' ? 'success' : 'outline'}
                                  className="text-xs"
                                  disabled={c.status === 'shortlisted'}
                                  onClick={() => handleShortlist(c)}
                                >
                                  <Star className={`h-3.5 w-3.5 ${c.status === 'shortlisted' ? 'fill-current' : ''}`} />
                                  {c.status === 'shortlisted' ? 'Shortlisted' : 'Shortlist'}
                                </Button>
                                <Button size="sm" variant="secondary" className="text-xs" disabled={!c.can_invite || c.status === 'invited'} loading={invitingId === c.id} onClick={() => handleInvite(c)}>
                                  <Send className="h-3.5 w-3.5" /> {c.status === 'invited' ? 'Invited' : 'Invite'}
                                </Button>
                              </>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                      {expandedId === c.id && (
                        <TableRow className="bg-purple-50/40 dark:bg-purple-500/5">
                          <TableCell colSpan={10}>
                            {c.rubric_match ? (
                              <div className="space-y-3 py-1">
                                <div className="flex flex-wrap items-center gap-3">
                                  <span className="text-sm font-semibold text-gray-900 dark:text-white">Rubric Match</span>
                                  <Badge variant={matchVariant(c.rubric_match.match_percentage)} size="md">
                                    {c.rubric_match.match_percentage}%
                                  </Badge>
                                  <span className="text-xs text-gray-500 dark:text-gray-400">
                                    {c.rubric_match.matched_skills.length} of {c.rubric_match.total_skills} skills matched
                                  </span>
                                </div>
                                <div className="flex flex-wrap gap-8">
                                  <div className="min-w-[200px]">
                                    <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-emerald-600">Matched Skills</div>
                                    <div className="flex flex-wrap gap-1.5">
                                      {c.rubric_match.matched_skills.length > 0 ? (
                                        c.rubric_match.matched_skills.map((s, i) => (
                                          <Badge key={`m-${i}`} variant="success" size="sm">{s.name}{s.category ? ` · ${s.category}` : ''}</Badge>
                                        ))
                                      ) : (
                                        <span className="text-xs text-gray-400">No matched skills</span>
                                      )}
                                    </div>
                                  </div>
                                  <div className="min-w-[200px]">
                                    <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-amber-600">Missing Skills</div>
                                    <div className="flex flex-wrap gap-1.5">
                                      {c.rubric_match.missing_skills.length > 0 ? (
                                        c.rubric_match.missing_skills.map((s, i) => (
                                          <Badge key={`x-${i}`} variant="warning" size="sm">{s.name}{s.category ? ` · ${s.category}` : ''}</Badge>
                                        ))
                                      ) : (
                                        <span className="text-xs text-gray-400">No missing skills</span>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              </div>
                            ) : (
                              <p className="text-sm text-gray-400">No rubric match available (no rubric linked).</p>
                            )}

                            <div className="mt-5 border-t border-gray-100 dark:border-white/[0.06] pt-5">
                              <div className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">CV Evaluation</div>
                              <CVEvaluation
                                cvScore={c.cv_score}
                                cvRubricWeighted={c.cv_rubric_weighted}
                                cvScoringMethod={c.cv_scoring_method}
                                cvCoveragePct={c.cv_coverage_pct}
                                cvSkillBreakdown={c.cv_skill_breakdown}
                                cvEvidence={c.cv_evidence}
                                cvMissingSkills={c.cv_missing_skills}
                                compact
                              />
                            </div>
                          </TableCell>
                        </TableRow>
                      )}
                    </Fragment>
                  );
                })}
              </TableBody>
            </Table>
          )}

          {/* Pagination Controls */}
          {totalCandidates > 0 && (
            <div className="mt-4 flex flex-col sm:flex-row items-center justify-between gap-4 pt-4 border-t border-gray-100 dark:border-gray-800">
              <div className="text-xs text-gray-500">
                Showing {Math.min((page - 1) * pageSize + 1, totalCandidates)} to {Math.min(page * pageSize, totalCandidates)} of {totalCandidates} candidates
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="text-xs h-8"
                >
                  Previous
                </Button>
                <span className="text-xs font-semibold px-2">
                  Page {page} of {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  className="text-xs h-8"
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
      )}
    </div>
  );
}
