import { useState, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams, useLocation } from 'react-router';
import { motion, AnimatePresence } from 'framer-motion';
import { Card, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/shared/components/ui/select';
import { customToast } from '@/shared/components/ui/toast';
import { useLanguage } from '@/contexts/language-context';
import { cn } from '@/utils/cn';
import { campaignsService } from '@/services/campaigns.service';
import {
  Plus, CheckCircle2, ArrowLeft, ArrowRight, MapPin,
  Briefcase, X, Users, Loader2, AlertTriangle,
  Settings2, Upload, FileText, BookOpen,
  BarChart3, Download, Search
} from 'lucide-react';

interface Job { id: number; title: string; }
interface SkillTree { id: number; job_name?: string; skill_count?: number; category_count?: number; seniority?: string; }
interface Template { id: number; name: string; role?: string; }

const stepLabels = ['Job Info', 'Rubric', 'Candidates', 'Interview', 'Review'];

const DIFFICULTY_LEVELS = ['easy', 'medium', 'hard', 'adaptive'] as const;
const LANGUAGES = ['English', 'French', 'Arabic', 'Spanish', 'German'] as const;
const DURATIONS = [15, 30, 45, 60] as const;

export default function CampaignCreatePage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [searchParams] = useSearchParams();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [step, setStep] = useState(1);
  const [saving, setSaving] = useState(false);
  const [publishing] = useState(false);

  // Step 1 state
  const [name, setName] = useState('');
  const [jobId, setJobId] = useState<number | null>(null);
  const [targetRole, setTargetRole] = useState('');
  const [location, setLocation] = useState('');
  const [description, setDescription] = useState('');
  const [jobs, setJobs] = useState<Job[]>([]);

  // Step 2 state
  const [skillTrees, setSkillTrees] = useState<SkillTree[]>([]);
  const [skillOption, setSkillOption] = useState<string>('existing');
  const [selectedTreeId, setSelectedTreeId] = useState<number | null>(null);
  const [treeSearch, setTreeSearch] = useState('');

  // Step 3 state
  const [source, setSource] = useState<string>('upload');
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const [matchResult, setMatchResult] = useState<any>(null);
  const [matchLoading, setMatchLoading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [consentConfirmed, setConsentConfirmed] = useState(false);

  // Step 4 state
  const [interviewLang, setInterviewLang] = useState('English');
  const [interviewDuration, setInterviewDuration] = useState(45);
  const [difficulty, setDifficulty] = useState('medium');
  const [interviewInstructions, setInterviewInstructions] = useState('');
  const [templateId, setTemplateId] = useState<number | null>(null);
  const [templates, setTemplates] = useState<Template[]>([]);

  useEffect(() => {
    campaignsService.getJobs({ per_page: 100 }).then((data: any) => {
      const items = data?.items || data?.jobs || data || [];
      setJobs(Array.isArray(items) ? items : []);
    }).catch(() => {});

    campaignsService.getTemplates().then((data: any) => {
      const list = Array.isArray(data) ? data : data?.items || [];
      setTemplates(list);
    }).catch(() => {});

    campaignsService.seedDefaults().catch(() => {});
  }, []);

  useEffect(() => {
    if (step === 2 || step === 5) {
      campaignsService.getJobs({ per_page: 100 }).then((data: any) => {
        const items = data?.items || data?.jobs || data || [];
        setJobs(Array.isArray(items) ? items : []);
      }).catch(() => {});

      const trees = campaignsService.getRubrics();
      trees.then((data: any) => {
        const list = data?.rubrics || data?.items || data?.skill_trees || [];
        if (Array.isArray(list)) {
          setSkillTrees(list.map((t: any) => ({
            id: t.id,
            job_name: t.job_name || t.title || `Rubric #${t.id}`,
            skill_count: t.skill_count || 0,
            category_count: t.category_count || 0,
            seniority: t.seniority,
          })));
        }
      }).catch(() => {});
    }
  }, [step]);

  useEffect(() => {
    const rubricParam = searchParams.get('rubric_id');
    if (!rubricParam) return;
    const id = Number(rubricParam);
    if (!id) return;
    setSelectedTreeId(id);
    setSkillOption('existing');
    navigate(pathname, { replace: true });
  }, [searchParams, navigate]);

  const handleCreate = async () => {
    if (!name.trim()) { customToast({ type: 'warning', title: t('camp.create.missingName'), message: t('camp.create.nameRequired') }); return; }
    setSaving(true);
    try {
      const res = await campaignsService.createFull({
        title: name.trim(),
        job_id: jobId,
        target_role: targetRole || null,
        description: description || null,
        skill_tree_id: selectedTreeId,
        rubric_id: selectedTreeId,
        skill_option: skillOption,
        language: interviewLang,
        duration_minutes: interviewDuration,
        difficulty,
        interview_instructions: interviewInstructions || null,
        template_id: templateId,
        candidate_source: source,
        location: location || null,
        consent_confirmed: consentConfirmed,
      });
      let uploadNote: string | null = null;
      if (uploadedFiles.length > 0 && res?.id) {
        if (!jobId) {
          uploadNote = t('camp.create.noJobSelected');
        } else if (!consentConfirmed) {
          uploadNote = t('camp.create.consentNotConfirmed');
        } else {
          const formData = new FormData();
          uploadedFiles.forEach(f => formData.append('files', f));
          formData.append('job_id', String(jobId));
          formData.append('campaign_id', String(res.id));
          formData.append('campaign_name', name.trim());
          formData.append('target_role', targetRole || '');
          formData.append('interview_instructions', interviewInstructions || '');
          formData.append('interview_language', interviewLang);
          formData.append('consent_confirmed', 'true');
          try {
            const up = await campaignsService.uploadCvsToCampaign(formData);
            const details: Array<{ filename: string; status: string; reason?: string }> = up?.details || [];
            const queued = details.filter((d) => d.status === 'queued').length;
            const skipped = details.filter((d) => d.status === 'skipped' || d.status === 'failed');
            if (queued > 0) {
              customToast({ type: 'success', title: t('camp.create.cvsUploaded'), message: `${queued} CV${queued === 1 ? '' : 's'} ${t('camp.create.queuedForAnalysis')}` });
            }
            if (skipped.length > 0) {
              const reasons = skipped.map((d) => `${d.filename}: ${d.reason || d.status}`).slice(0, 3).join('; ');
              uploadNote = (skipped.length === 1 ? t('camp.create.cvSkippedOne') : t('camp.create.cvSkippedMany')).replace('{reasons}', reasons) + (skipped.length > 3 ? '…' : '');
            } else if (queued === 0) {
              uploadNote = t('camp.create.noCvsUploaded');
            }
          } catch (err: any) {
            uploadNote = err?.message || t('camp.create.uploadFailed');
          }
        }
      }

      if (res?.id) {
        customToast({ type: uploadNote ? 'warning' : 'success', title: t('camp.create.campaignCreated'), message: uploadNote || undefined });
        setTimeout(() => navigate(`/campaigns/${res.id}`), 1500);
      } else {
        customToast({ type: 'success', title: t('camp.create.campaignCreated'), message: t('camp.create.redirecting') });
        setTimeout(() => navigate('/campaigns'), 1500);
      }
    } catch (e: any) {
      customToast({ type: 'error', title: t('camp.create.error'), message: e?.message || t('camp.create.createFailed') });
    } finally {
      setSaving(false);
    }
  };

  const handleFiles = (files: FileList) => {
    setUploadedFiles(prev => [...prev, ...Array.from(files)]);
  };

  const removeFile = (idx: number) => {
    setUploadedFiles(prev => prev.filter((_, i) => i !== idx));
    setMatchResult(null);
  };

  const previewMatch = async () => {
    if (uploadedFiles.length === 0 || !selectedTreeId) {
      customToast({ type: 'warning', title: t('camp.create.missing'), message: t('camp.create.uploadCvFirst') });
      return;
    }
    setMatchLoading(true);
    setMatchResult(null);
    try {
      const fd = new FormData();
      fd.append('file', uploadedFiles[0]);
      fd.append('rubric_id', String(selectedTreeId));
      const res = await campaignsService.previewMatch(fd);
      setMatchResult(res);
    } catch (e: any) {
      customToast({ type: 'error', title: t('camp.create.previewFailed'), message: e?.message || t('camp.create.couldNotAnalyze') });
    } finally {
      setMatchLoading(false);
    }
  };

  const filteredTrees = skillTrees.filter(t => {
    const q = treeSearch.toLowerCase();
    return !q || (t.job_name || '').toLowerCase().includes(q);
  });

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={() => navigate('/email-campaigns')} leftIcon={<ArrowLeft className="h-4 w-4" />}>{t('common.back')}</Button>
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">{t('campaign.newCampaign')}</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">{t('camp.create.subtitle')}</p>
        </div>
      </div>

      <div className="flex items-center gap-0.5">
        {stepLabels.map((label, i) => {
          const s = i + 1;
          return (
            <div key={s} className="flex-1 flex flex-col items-center">
              <div className={cn(
                'w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all',
                s < step && 'bg-purple-600 text-white',
                s === step && 'bg-purple-600 text-white ring-2 ring-purple-600 ring-offset-2 dark:ring-offset-gray-900',
                s > step && 'bg-gray-200 dark:bg-gray-800 text-gray-400',
              )}>
                {s < step ? <CheckCircle2 className="h-4 w-4" /> : s}
              </div>
              <span className={cn('text-[10px] mt-1 font-medium text-center', s === step ? 'text-purple-600' : 'text-gray-400')}>{label}</span>
            </div>
          );
        })}
      </div>

      <AnimatePresence mode="wait">
        <motion.div key={step} initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} transition={{ duration: 0.2 }}>
          <Card className="glass-panel border-purple-200/60 dark:border-purple-500/20 p-6">

            {step === 1 && (
              <div className="space-y-5">
                <CardHeader>
                  <CardTitle className="text-xl font-black">{t('camp.create.step1Title')}</CardTitle>
                  <CardDescription>{t('camp.create.step1Desc')}</CardDescription>
                </CardHeader>

                <Input label={`${t('campaign.col.campaignName')} *`} placeholder={t('camp.create.namePlaceholder')} value={name} onChange={e => setName(e.target.value)} leftIcon={<Briefcase className="h-4 w-4 text-purple-500" />} />

                <div className="space-y-1.5">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('camp.create.linkJob')} <span className="text-gray-400 font-normal">({t('camp.create.optional')})</span></label>
                  <Select value={String(jobId || '')} onValueChange={v => setJobId(v ? Number(v) : null)}>
                    <SelectTrigger><SelectValue placeholder={t('camp.create.noJobLinkedPlaceholder')} /></SelectTrigger>
                    <SelectContent>
                      {jobs.map(j => <SelectItem key={j.id} value={String(j.id)}>{j.title}</SelectItem>)}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-gray-400">{t('camp.create.linkJobHint')}</p>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <Input label={t('camp.create.targetRole')} placeholder={t('camp.create.targetRolePlaceholder')} value={targetRole} onChange={e => setTargetRole(e.target.value)} />
                  <Input label={t('common.location')} placeholder={t('camp.create.locationPlaceholder')} value={location} onChange={e => setLocation(e.target.value)} leftIcon={<MapPin className="h-4 w-4 text-indigo-500" />} />
                </div>

                <div className="space-y-1.5">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('common.description')}</label>
                  <textarea className="w-full rounded-xl border border-purple-200/60 bg-white/70 p-3 text-sm focus:ring-2 focus:ring-purple-500/20 dark:border-white/10 dark:bg-white/5 dark:text-white min-h-[80px]" placeholder={t('camp.create.descriptionPlaceholder')} value={description} onChange={e => setDescription(e.target.value)} />
                </div>
              </div>
            )}

            {step === 2 && (
              <div className="space-y-5">
                <CardHeader>
                  <CardTitle className="text-xl font-black">{t('camp.create.step2Title')}</CardTitle>
                  <CardDescription>{t('camp.create.step2Desc')}</CardDescription>
                </CardHeader>

                <div className="flex items-center gap-3 p-4 rounded-xl bg-purple-50 dark:bg-purple-500/10 border border-purple-200/60">
                  <BookOpen className="h-5 w-5 text-purple-600 shrink-0" />
                  <div>
                    <div className="text-sm font-bold text-purple-800 dark:text-purple-300">{t('camp.create.rubricLibrary')}</div>
                    <p className="text-xs text-purple-600 dark:text-purple-400">{t('camp.create.rubricLibraryHint')}</p>
                  </div>
                </div>

                <div className="space-y-3">
                  {[
                    { value: 'existing', label: t('camp.create.useExistingRubric'), desc: t('camp.create.useExistingRubricDesc') },
                    { value: 'new', label: t('camp.create.createNewRubric'), desc: t('camp.create.createNewRubricDesc') },
                    { value: 'inherit', label: t('camp.create.inheritFromJob'), desc: t('camp.create.inheritFromJobDesc') },
                  ].map(opt => (
                    <div key={opt.value}
                      className={cn('flex items-center gap-3 p-4 border-2 rounded-2xl cursor-pointer transition-all', skillOption === opt.value ? 'border-purple-500 bg-purple-50 dark:bg-purple-500/10' : 'border-gray-200 dark:border-white/10 hover:border-purple-300')}
                      onClick={() => setSkillOption(opt.value)}
                    >
                      <div className={cn('w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0', skillOption === opt.value ? 'border-purple-600 bg-purple-600' : 'border-gray-300')}>
                        {skillOption === opt.value && <div className="w-2 h-2 rounded-full bg-white" />}
                      </div>
                      <div>
                        <div className="font-bold text-sm text-gray-800 dark:text-white">{opt.label}</div>
                        <div className="text-xs text-gray-500">{opt.desc}</div>
                      </div>
                    </div>
                  ))}
                </div>

                {skillOption === 'existing' && (
                  <div className="pl-4 space-y-3">
                    <div className="relative">
                      <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                      <input className="w-full bg-white dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-xl pl-10 pr-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/20 dark:text-white" placeholder={t('recruiter.skillTreeLib.searchRubrics')} value={treeSearch} onChange={e => setTreeSearch(e.target.value)} />
                    </div>
                    <div className="space-y-2 max-h-60 overflow-y-auto">
                      {filteredTrees.length === 0 ? (
                        <p className="text-center py-4 text-gray-400 text-xs">{t('camp.create.noRubricsFound')}</p>
                      ) : filteredTrees.map(tree => (
                        <div key={tree.id}
                          className={cn('flex items-center gap-3 p-3 border rounded-xl cursor-pointer transition-all', selectedTreeId === tree.id ? 'border-purple-500 bg-purple-50 dark:bg-purple-500/10' : 'border-gray-200 dark:border-white/10 hover:border-purple-300')}
                          onClick={() => setSelectedTreeId(tree.id)}
                        >
                          <div className={cn('w-4 h-4 rounded-full border-2 flex items-center justify-center shrink-0', selectedTreeId === tree.id ? 'border-purple-600 bg-purple-600' : 'border-gray-300')}>
                            {selectedTreeId === tree.id && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-bold text-gray-800 dark:text-white truncate">{tree.job_name || t('cv.builder.untitled')}</div>
                            <div className="text-xs text-gray-500">{tree.skill_count || 0} {t('camp.create.skillsLabel')} · {tree.category_count || 0} {t('camp.create.categoriesLabel')}{tree.seniority ? ` · ${tree.seniority}` : ''}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {skillOption === 'new' && (
                  <div className="p-4 rounded-xl bg-purple-50/50 dark:bg-purple-500/5 border border-dashed border-purple-200/60 text-center space-y-3">
                    <p className="text-sm text-gray-500">{t('camp.create.saveRubricAfter')}</p>
                    <Button variant="outline" onClick={() => navigate('/skill-tree-create?return_to=/campaigns/new')} leftIcon={<Plus className="h-4 w-4" />}>{t('camp.create.createNewRubric')}</Button>
                  </div>
                )}

                {skillOption === 'inherit' && (
                  <div className="p-4 rounded-xl bg-amber-50 dark:bg-amber-500/10 border border-amber-200/60">
                    <p className="text-sm text-amber-700 dark:text-amber-300 flex items-center gap-2">
                      <AlertTriangle className="h-4 w-4" />
                      {t('camp.create.willInherit')}
                    </p>
                  </div>
                )}
              </div>
            )}

            {step === 3 && (
              <div className="space-y-5">
                <CardHeader>
                  <CardTitle className="text-xl font-black">{t('camp.create.step3Title')}</CardTitle>
                  <CardDescription>{t('camp.create.step3Desc')}</CardDescription>
                </CardHeader>

                {[
                  { value: 'upload', label: t('campaign.uploadCvs'), desc: t('camp.create.uploadCvsDesc'), icon: Upload },
                  { value: 'manual', label: t('camp.create.addCandidatesManually'), desc: t('camp.create.addCandidatesManuallyDesc'), icon: Users },
                  { value: 'import', label: t('camp.create.importFromJobApplications'), desc: t('camp.create.importFromJobApplicationsDesc'), icon: Download },
                ].map(opt => (
                  <div key={opt.value}
                    className={cn('flex items-center gap-3 p-4 border-2 rounded-2xl cursor-pointer transition-all', source === opt.value ? 'border-purple-500 bg-purple-50 dark:bg-purple-500/10' : 'border-gray-200 dark:border-white/10 hover:border-purple-300')}
                    onClick={() => setSource(opt.value)}
                  >
                    <div className={cn('w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0', source === opt.value ? 'border-purple-600 bg-purple-600' : 'border-gray-300')}>
                      {source === opt.value && <div className="w-2 h-2 rounded-full bg-white" />}
                    </div>
                    <opt.icon className={cn('h-5 w-5', source === opt.value ? 'text-purple-600' : 'text-gray-400')} />
                    <div>
                      <div className="font-bold text-sm text-gray-800 dark:text-white">{opt.label}</div>
                      <div className="text-xs text-gray-500">{opt.desc}</div>
                    </div>
                  </div>
                ))}

                {source === 'upload' && (
                  <div className="space-y-4">
                    <div
                      className={cn('border-2 border-dashed rounded-2xl p-8 text-center transition-all cursor-pointer', dragOver ? 'border-purple-500 bg-purple-50 dark:bg-purple-500/10' : 'border-gray-300 dark:border-white/10 hover:border-purple-400', uploadedFiles.length > 0 && 'border-emerald-400 bg-emerald-50/50 dark:bg-emerald-500/5')}
                      onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                      onDragLeave={() => setDragOver(false)}
                      onDrop={e => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files); }}
                      onClick={() => fileInputRef.current?.click()}
                    >
                      <Upload className="h-10 w-10 text-gray-300 mx-auto mb-3" />
                      <h4 className="font-bold text-sm text-gray-700 dark:text-gray-300 mb-1">{t('camp.create.dropCvsHere')}</h4>
                      <p className="text-xs text-gray-400">{t('camp.create.uploadFormats')}</p>
                      <input ref={fileInputRef} type="file" multiple accept=".pdf,.docx" className="hidden" onChange={e => e.target.files && handleFiles(e.target.files)} />
                    </div>

                    {uploadedFiles.length > 0 && (
                      <div className="space-y-2">
                        <h4 className="text-xs font-bold text-gray-600 dark:text-gray-400">{t('camp.create.uploadedFiles').replace('{count}', String(uploadedFiles.length))}</h4>
                        {uploadedFiles.map((f, i) => (
                          <div key={i} className="flex items-center gap-2 p-2 bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 rounded-lg text-xs">
                            <FileText className="h-4 w-4 text-red-400 shrink-0" />
                            <span className="flex-1 font-medium text-gray-700 dark:text-gray-300 truncate">{f.name}</span>
                            <span className="text-gray-400 shrink-0">{(f.size / 1024).toFixed(0)} KB</span>
                            <button onClick={() => removeFile(i)} className="text-gray-300 hover:text-red-500"><X className="h-3.5 w-3.5" /></button>
                          </div>
                        ))}
                        {selectedTreeId && uploadedFiles.length > 0 && (
                          <Button variant="outline" size="sm" onClick={previewMatch} disabled={matchLoading} leftIcon={matchLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <BarChart3 className="h-3.5 w-3.5" />}>
                            {t('camp.create.previewSkillMatch')}
                          </Button>
                        )}
                      </div>
                    )}

                    {matchResult && (
                      <div className="p-4 rounded-xl bg-white dark:bg-white/5 border border-gray-200 dark:border-white/10 space-y-3">
                        <div className="text-center">
                          <div className={cn('inline-flex items-center justify-center w-16 h-16 rounded-full mb-2', matchResult.match_percentage >= 70 ? 'bg-emerald-50' : matchResult.match_percentage >= 40 ? 'bg-amber-50' : 'bg-red-50')}>
                            <span className={cn('text-xl font-black', matchResult.match_percentage >= 70 ? 'text-emerald-600' : matchResult.match_percentage >= 40 ? 'text-amber-600' : 'text-red-500')}>{matchResult.match_percentage || 0}%</span>
                          </div>
                          <div className="text-sm font-bold">{t('cprofile.matchScore')}</div>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                          <div className="bg-emerald-50 dark:bg-emerald-500/10 rounded-xl p-3 text-center">
                            <div className="text-lg font-black text-emerald-600">{(matchResult.matched_skills || []).length}</div>
                            <div className="text-[10px] font-bold text-emerald-700 uppercase">{t('camp.create.matched')}</div>
                          </div>
                          <div className="bg-red-50 dark:bg-red-500/10 rounded-xl p-3 text-center">
                            <div className="text-lg font-black text-red-500">{(matchResult.missing_skills || []).length}</div>
                            <div className="text-[10px] font-bold text-red-600 uppercase">{t('camp.create.missingSkills')}</div>
                          </div>
                        </div>
                      </div>
                    )}

                    <div className="flex items-center gap-2 text-xs text-gray-400">
                      <AlertTriangle className="h-3 w-3 text-purple-400" />
                      <span>{t('camp.create.aiExtract')}</span>
                    </div>

                    <label className={`flex items-start gap-3 p-3 rounded-xl border-2 cursor-pointer transition-all ${consentConfirmed ? 'border-purple-400 bg-purple-50 dark:bg-purple-500/10' : 'border-gray-200 dark:border-white/10 hover:border-purple-300'}`}>
                      <input
                        type="checkbox"
                        checked={consentConfirmed}
                        onChange={(e) => setConsentConfirmed(e.target.checked)}
                        className="mt-0.5 h-4 w-4 rounded accent-purple-600"
                      />
                      <div>
                        <div className="text-xs font-semibold text-gray-700 dark:text-gray-200">{t('camp.create.consentTitle')}</div>
                        <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                          {t('camp.create.consentText')}
                        </div>
                      </div>
                    </label>
                  </div>
                )}

                {source === 'manual' && (
                  <div className="p-8 text-center text-gray-400 text-sm border border-dashed border-gray-200 dark:border-white/10 rounded-2xl">
                    <Users className="h-8 w-8 mx-auto mb-2 text-gray-300" />
                    <p>{t('camp.create.manualComingSoon')}</p>
                  </div>
                )}

                {source === 'import' && (
                  <div className="p-8 text-center text-gray-400 text-sm border border-dashed border-gray-200 dark:border-white/10 rounded-2xl">
                    <Download className="h-8 w-8 mx-auto mb-2 text-gray-300" />
                    <p>{t('camp.create.importRequiresJob')}</p>
                  </div>
                )}
              </div>
            )}

            {step === 4 && (
              <div className="space-y-5">
                <CardHeader>
                  <CardTitle className="text-xl font-black">{t('camp.create.step4Title')}</CardTitle>
                  <CardDescription>{t('camp.create.step4Desc')}</CardDescription>
                </CardHeader>

                <div className="flex items-center gap-3 p-4 rounded-xl bg-purple-50 dark:bg-purple-500/10 border border-purple-200/60">
                  <Settings2 className="h-5 w-5 text-purple-600 shrink-0" />
                  <div>
                    <div className="text-sm font-bold text-purple-800 dark:text-purple-300">{t('camp.create.aiInterviewSettings')}</div>
                    <p className="text-xs text-purple-600 dark:text-purple-400">{t('camp.create.aiInterviewSettingsHint')}</p>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('camp.create.interviewLanguage')}</label>
                    <Select value={interviewLang} onValueChange={setInterviewLang}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {LANGUAGES.map(l => <SelectItem key={l} value={l}>{l}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('camp.create.interviewDuration')}</label>
                    <Select value={String(interviewDuration)} onValueChange={v => setInterviewDuration(Number(v))}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {DURATIONS.map(d => <SelectItem key={d} value={String(d)}>{d} {t('camp.create.minutes')}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('camp.create.interviewDifficulty')}</label>
                  <div className="flex gap-2">
                    {DIFFICULTY_LEVELS.map(level => (
                      <button key={level} type="button"
                        className={cn('flex-1 px-3 py-2.5 text-xs font-bold rounded-xl border-2 transition-all capitalize', difficulty === level ? 'bg-purple-600 text-white border-purple-600 shadow-sm' : 'bg-white dark:bg-white/5 text-gray-600 dark:text-gray-400 border-gray-200 dark:border-white/10 hover:border-purple-300')}
                        onClick={() => setDifficulty(level)}
                      >
                        {level === 'adaptive' ? t('camp.create.aiAdaptive') : t('camp.create.difficulty.' + level)}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('camp.create.customInstructions')} <span className="text-gray-400 font-normal">({t('camp.create.optional')})</span></label>
                  <textarea className="w-full rounded-xl border border-purple-200/60 bg-white/70 p-3 text-sm focus:ring-2 focus:ring-purple-500/20 dark:border-white/10 dark:bg-white/5 dark:text-white min-h-[100px]" placeholder={t('camp.create.instructionsPlaceholder')} value={interviewInstructions} onChange={e => setInterviewInstructions(e.target.value)} />
                </div>

                <div className="space-y-1.5">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('camp.create.emailTemplate')} <span className="text-gray-400 font-normal">({t('camp.create.optional')})</span></label>
                  <Select value={String(templateId || '')} onValueChange={v => setTemplateId(v ? Number(v) : null)}>
                    <SelectTrigger><SelectValue placeholder={t('camp.create.defaultTemplate')} /></SelectTrigger>
                    <SelectContent>
                      {templates.map(t => <SelectItem key={t.id} value={String(t.id)}>{t.name}{t.role ? ` (${t.role})` : ''}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            )}

            {step === 5 && (
              <div className="space-y-5">
                <CardHeader>
                  <CardTitle className="text-xl font-black">{t('camp.create.step5Title')}</CardTitle>
                  <CardDescription>{t('camp.create.step5Desc')}</CardDescription>
                </CardHeader>

                <div className="grid grid-cols-2 gap-4 p-4 rounded-xl bg-purple-50/50 dark:bg-purple-500/5">
                  <div><span className="text-xs text-gray-400">{t('common.name')}</span><p className="font-bold">{name || t('cv.builder.untitled')}</p></div>
                  <div><span className="text-xs text-gray-400">{t('camp.create.linkedJob')}</span><p className="font-bold">{jobId ? jobs.find(j => j.id === jobId)?.title || t('camp.create.jobId').replace('{id}', String(jobId)) : t('camp.create.noJobLinked')}</p></div>
                  <div><span className="text-xs text-gray-400">{t('camp.create.targetRole')}</span><p className="font-bold">{targetRole || '—'}</p></div>
                  <div><span className="text-xs text-gray-400">{t('common.location')}</span><p className="font-bold">{location || '—'}</p></div>
                </div>

                <div className="p-4 rounded-xl bg-white/50 dark:bg-white/5 border border-gray-200 dark:border-white/10">
                  <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3">{t('camp.create.evaluation')}</h4>
                  <p className="text-sm text-gray-700 dark:text-gray-300">
                    {selectedTreeId ? t('camp.create.usingRubric').replace('{name}', skillTrees.find(t => t.id === selectedTreeId)?.job_name || t('camp.create.rubricId').replace('{id}', String(selectedTreeId))) : skillOption === 'new' ? t('camp.create.newRubricWillBeCreated') : t('camp.create.noRubricSelected')}
                  </p>
                </div>

                <div className="p-4 rounded-xl bg-white/50 dark:bg-white/5 border border-gray-200 dark:border-white/10">
                  <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3">{t('camp.create.candidateSource')}</h4>
                  <p className="text-sm text-gray-700 dark:text-gray-300 capitalize">{source === 'upload' ? t('camp.create.uploadCvsCount').replace('{count}', String(uploadedFiles.length)) : source === 'manual' ? t('camp.create.addManually') : t('camp.create.importFromJob')}</p>
                </div>

                <div className="p-4 rounded-xl bg-white/50 dark:bg-white/5 border border-gray-200 dark:border-white/10">
                  <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3">{t('camp.create.interviewSettings')}</h4>
                  <div className="grid grid-cols-3 gap-3 text-sm">
                    <div><span className="text-xs text-gray-400 block">{t('camp.create.interviewLanguage')}</span><span className="font-bold">{interviewLang}</span></div>
                    <div><span className="text-xs text-gray-400 block">{t('camp.create.interviewDuration')}</span><span className="font-bold">{interviewDuration} {t('camp.create.min')}</span></div>
                    <div><span className="text-xs text-gray-400 block">{t('camp.create.interviewDifficulty')}</span><span className="font-bold capitalize">{t('camp.create.difficulty.' + difficulty)}</span></div>
                  </div>
                </div>

                <div className="flex items-center gap-2 p-3 rounded-xl bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 text-sm">
                  <CheckCircle2 className="h-4 w-4 shrink-0" />
                  <span>{t('camp.create.publishNote')}</span>
                </div>
              </div>
            )}

          </Card>
        </motion.div>
      </AnimatePresence>

      <div className="flex items-center justify-between">
        <div>
          {step > 1 && (
            <Button variant="ghost" onClick={() => setStep(step - 1)} leftIcon={<ArrowLeft className="h-4 w-4" />}>{t('common.cancel')}</Button>
          )}
        </div>
        <div className="flex items-center gap-2">
          {step < 5 ? (
            <Button variant="primary" size="lg" className="px-8 font-bold shadow-lg shadow-purple-500/25" onClick={() => {
              if (step === 1 && !name.trim()) { customToast({ type: 'warning', title: t('common.status'), message: t('camp.create.nameRequiredShort') }); return; }
              setStep(step + 1);
            }} rightIcon={<ArrowRight className="h-4 w-4" />}>
              {t('common.next')}
            </Button>
          ) : (
            <Button variant="primary" size="lg" className="px-8 font-bold shadow-lg shadow-green-500/25 bg-green-600 hover:bg-green-700" onClick={handleCreate} disabled={saving} rightIcon={saving || publishing ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}>
              {saving ? '...' : t('campaign.newCampaign')}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
