import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence, Reorder } from 'framer-motion';
import { useSearchParams, useNavigate, useParams, useLocation } from 'react-router';
import { Card, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Badge } from '@/shared/components/ui/badge';
import { Switch } from '@/shared/components/ui/switch';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/shared/components/ui/select';
import { customToast } from '@/shared/components/ui/toast';
import { cn } from '@/utils/cn';
import { useLanguage } from '@/contexts/language-context';
import { jobsService } from '@/services/jobs.service';
import { campaignsService } from '@/services/campaigns.service';
import {
  Plus, Sparkles, CheckCircle2, ArrowLeft, ArrowRight, MapPin,
  Briefcase, Banknote, X, GripVertical, Users,
  ListChecks, Loader2, Trash2, Star, AlertTriangle,
  Settings2, RefreshCw, ChevronDown, ChevronUp, BookOpen, Search
} from 'lucide-react';

interface Category { id: number; name: string; description?: string | null; }
interface Recruiter { id: number; name: string; email: string; }
interface RoleOverviewItem { question_key: string; question: string; answer: string; }
interface SkillDef { id?: number; skill_name: string; required_level: string; weight: number; is_mandatory: boolean; notes?: string; sort_order: number; }
interface EvalCategory { name: string; weight: number; sort_order: number; }
interface AIConfigData { ai_scoring_enabled: boolean; minimum_recommended_score: number; auto_shortlist_threshold?: number | null; auto_reject_threshold?: number | null; explain_ai_decisions: boolean; evidence_based_scoring: boolean; ignore_missing_cv: boolean; prioritize_verified_skills: boolean; custom_instructions?: string | null; duration_minutes?: number | null; total_questions?: number | null; }
interface ScreeningQuestionDef { id?: number; question: string; type: string; options?: string[] | null; is_required: boolean; sort_order: number; }
interface PipelineStageDef { id?: number; name: string; slug: string; sort_order: number; color?: string; icon?: string; }

interface RubricOption { id: number; job_name?: string; skill_count?: number; category_count?: number; seniority?: string; }

const LEVELS = ['entry', 'intermediate', 'senior', 'lead', 'expert'] as const;
const QUESTION_TYPES = ['text', 'yes_no', 'multiple_choice', 'rating', 'behavioral', 'technical', 'general'] as const;
const EMPLOYMENT_TYPES = ['full-time', 'part-time', 'contract', 'freelance', 'internship'] as const;
const WORKPLACE_TYPES = ['remote', 'hybrid', 'on-site'] as const;
const PIPELINE_COLORS = ['#6366f1', '#f59e0b', '#3b82f6', '#10b981', '#059669', '#ef4444', '#8b5cf6', '#ec4899'];

function WeightBar({ weight, label }: { weight: number; label: string }) {
  const hue = Math.round(weight * 2.4);
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-gray-500 w-16 truncate">{label}</span>
      <div className="flex-1 h-2 bg-gray-100 dark:bg-white/5 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-300" style={{ width: `${weight}%`, backgroundColor: `hsl(${hue}, 70%, 55%)` }} />
      </div>
      <span className="text-xs font-bold text-gray-600 dark:text-gray-400 w-8 text-right">{weight}%</span>
    </div>
  );
}

export default function JobWizardPage() {
  const { t } = useLanguage();
  const [searchParams] = useSearchParams();
  const { pathname } = useLocation();
  const { id: routeId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const editId = routeId || searchParams.get('edit');

  const roleQuestions: { key: string; label: string }[] = [
    { key: 'responsibilities', label: t('wizard.roleQuestion.responsibilities') },
    { key: 'outcomes_90_days', label: t('wizard.roleQuestion.outcomes90Days') },
    { key: 'problems_solved', label: t('wizard.roleQuestion.problemsSolved') },
    { key: 'success_criteria', label: t('wizard.roleQuestion.successCriteria') },
  ];

  const defaultEvalCategories: EvalCategory[] = [
    { name: t('wizard.defaultEvalCat.technical'), weight: 50, sort_order: 0 },
    { name: t('wizard.defaultEvalCat.problemSolving'), weight: 20, sort_order: 1 },
    { name: t('wizard.defaultEvalCat.communication'), weight: 15, sort_order: 2 },
    { name: t('wizard.defaultEvalCat.portfolio'), weight: 15, sort_order: 3 },
  ];

  const defaultPipeline: PipelineStageDef[] = [
    { name: t('recruiter.dash.stage.applied'), slug: 'applied', sort_order: 0, color: '#6366f1', icon: 'file-text' },
    { name: t('recruiter.dash.stage.screening'), slug: 'screening', sort_order: 1, color: '#f59e0b', icon: 'search' },
    { name: t('recruiter.dash.stage.interview'), slug: 'interview', sort_order: 2, color: '#3b82f6', icon: 'users' },
    { name: t('recruiter.dash.stage.offer'), slug: 'offer', sort_order: 3, color: '#10b981', icon: 'check-circle' },
    { name: t('recruiter.dash.stage.hired'), slug: 'hired', sort_order: 4, color: '#059669', icon: 'user-check' },
  ];

  const employmentTypeLabels: Record<string, string> = {
    'full-time': t('wizard.employment.fullTime'),
    'part-time': t('wizard.employment.partTime'),
    contract: t('wizard.employment.contract'),
    freelance: t('wizard.employment.freelance'),
    internship: t('wizard.employment.internship'),
  };
  const workplaceTypeLabels: Record<string, string> = {
    remote: t('wizard.workplace.remote'),
    hybrid: t('wizard.workplace.hybrid'),
    'on-site': t('wizard.workplace.onSite'),
  };
  const levelLabels: Record<string, string> = {
    entry: t('wizard.level.entry'),
    intermediate: t('wizard.level.intermediate'),
    senior: t('wizard.level.senior'),
    lead: t('wizard.level.lead'),
    expert: t('wizard.level.expert'),
  };
  const qtypeLabels: Record<string, string> = {
    text: t('wizard.qtype.text'),
    yes_no: t('wizard.qtype.yesNo'),
    multiple_choice: t('wizard.qtype.multipleChoice'),
    rating: t('wizard.qtype.rating'),
    behavioral: t('wizard.qtype.behavioral'),
    technical: t('wizard.qtype.technical'),
    general: t('wizard.qtype.general'),
  };

  const [step, setStep] = useState(1);
  const [jobId, setJobId] = useState<number | null>(editId ? Number(editId) : null);
  const [completedSteps, setCompletedSteps] = useState<number[]>([]);
  const [isPublished, setIsPublished] = useState(false);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [loadingWizard, setLoadingWizard] = useState(!!editId);

  // Rubric picker (campaign-style) state
  const [rubricOption, setRubricOption] = useState<string>('inline');
  const [rubrics, setRubrics] = useState<RubricOption[]>([]);
  const [selectedTreeId, setSelectedTreeId] = useState<number | null>(null);
  const [rubricSearch, setRubricSearch] = useState('');

  const [categories, setCategories] = useState<Category[]>([]);
  const [recruiters, setRecruiters] = useState<Recruiter[]>([]);

  const [title, setTitle] = useState('');
  const [categoryId, setCategoryId] = useState<number | null>(null);
  const [employmentType, setEmploymentType] = useState('full-time');
  const [workplaceType, setWorkplaceType] = useState('hybrid');
  const [location, setLocation] = useState('');
  const [numOpenings, setNumOpenings] = useState(1);
  const [hiringManagerId, setHiringManagerId] = useState<number | null>(null);
  const [salaryMin, setSalaryMin] = useState<number | null>(null);
  const [salaryMax, setSalaryMax] = useState<number | null>(null);
  const [salaryCurrency, setSalaryCurrency] = useState('USD');
  const [internalReference, setInternalReference] = useState('');

  const [roleItems, setRoleItems] = useState<RoleOverviewItem[]>(
    roleQuestions.map(q => ({ question_key: q.key, question: q.label, answer: '' }))
  );
  const [roleSummary, setRoleSummary] = useState('');

  const [skills, setSkills] = useState<SkillDef[]>([]);
  const [newSkillName, setNewSkillName] = useState('');
  const [newSkillLevel, setNewSkillLevel] = useState<string>('intermediate');
  const [newSkillWeight, setNewSkillWeight] = useState(10);
  const [newSkillMandatory] = useState(true);

  const [evalCategories, setEvalCategories] = useState<EvalCategory[]>(defaultEvalCategories);
  const [aiConfig, setAIConfig] = useState<AIConfigData>({
    ai_scoring_enabled: true, minimum_recommended_score: 0, auto_shortlist_threshold: null,
    auto_reject_threshold: null, explain_ai_decisions: true, evidence_based_scoring: true,
    ignore_missing_cv: false, prioritize_verified_skills: true, custom_instructions: null,
    duration_minutes: 30, total_questions: 6,
  });

  const [screeningQuestions, setScreeningQuestions] = useState<ScreeningQuestionDef[]>([]);
  const [pipelineStages, setPipelineStages] = useState<PipelineStageDef[]>(defaultPipeline);
  const [newQuestionText, setNewQuestionText] = useState('');
  const [newQuestionType, setNewQuestionType] = useState<string>('text');

  const [aiLoading, setAILoading] = useState<string | null>(null);

  useEffect(() => {
    jobsService.getWizardCategories().then(setCategories).catch(() => {});
    jobsService.getWizardRecruiters().then(setRecruiters).catch(() => {});
  }, []);

  useEffect(() => {
    if (!editId) return;
    setLoadingWizard(true);
    jobsService.getWizard(editId).then(data => {
      const j = data.job || {};
      setTitle(j.title || '');
      setLocation(j.location || '');
      setCategoryId(j.category_id || null);
      setEmploymentType(j.employment_type || 'full-time');
      setIsPublished(j.is_active || false);
      if (j.rubric_id) {
        setSelectedTreeId(Number(j.rubric_id));
        setRubricOption('existing');
      }
      if (data.progress) {
        const remap = (s: number) => s <= 2 ? s : s === 5 ? 4 : s === 6 ? 5 : 3;
        setCompletedSteps((data.progress.completed_steps || []).map(remap));
        if (data.progress.current_step) setStep(remap(data.progress.current_step));
      }
      if (data.role_overviews) {
        setRoleItems(data.role_overviews.map((r: any) => ({ question_key: r.question_key, question: r.question, answer: r.answer || '' })));
      }
      if (data.skills) {
        setSkills(data.skills.map((s: any) => ({
          skill_name: s.skill_name, required_level: s.required_level || 'intermediate',
          weight: s.weight, is_mandatory: s.is_mandatory, notes: s.notes, sort_order: s.sort_order,
        })));
      }
      if (data.evaluation_framework) {
        setEvalCategories(data.evaluation_framework.categories || defaultEvalCategories);
      }
      if (data.ai_config) setAIConfig((prev: AIConfigData) => ({ ...prev, ...data.ai_config }));
      if (data.screening_questions) {
        setScreeningQuestions(data.screening_questions.map((q: any) => ({
          question: q.question, type: q.type, options: q.options,
          is_required: q.is_required, sort_order: q.sort_order,
        })));
      }
      if (data.pipeline_stages) {
        setPipelineStages(data.pipeline_stages.map((s: any) => ({
          name: s.name, slug: s.slug, sort_order: s.sort_order,
          color: s.color, icon: s.icon,
        })));
      }
    }).catch(() => {
      customToast({ type: 'error', title: t('recruiter.skillTreeCreate.loadFailedTitle'), message: t('wizard.loadFailedMsg') });
    }).finally(() => setLoadingWizard(false));
  }, [editId]);

  useEffect(() => {
    if (step === 3) {
      campaignsService.getRubrics().then((data: any) => {
        const list = data?.rubrics || data?.items || data?.skill_trees || [];
        if (Array.isArray(list)) {
          setRubrics(list.map((item: any) => ({
            id: item.id,
            job_name: item.job_name || item.title || `${t('wizard.rubricLabel')} #${item.id}`,
            skill_count: item.skill_count || 0,
            category_count: item.category_count || 0,
            seniority: item.seniority,
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
    setRubricOption('existing');
    navigate(pathname, { replace: true });
  }, [searchParams, navigate, pathname]);

  const step1Data = () => ({
    title, category_id: categoryId, employment_type: employmentType,
    workplace_type: workplaceType, location, num_openings: numOpenings,
    hiring_manager_id: hiringManagerId, salary_min: salaryMin, salary_max: salaryMax,
    salary_currency: salaryCurrency, internal_reference: internalReference || undefined,
  });

  const validateStep1 = () => {
    if (!title.trim()) { customToast({ type: 'warning', title: t('wizard.missingTitle'), message: t('wizard.titleRequired') }); return false; }
    return true;
  };

  const handleSaveStep1 = async () => {
    if (!validateStep1()) return;
    setSaving(true);
    try {
      if (!jobId) {
        const result = await jobsService.startWizard(step1Data());
        setJobId(result.job_id);
        setCompletedSteps(prev => prev.includes(1) ? prev : [...prev, 1]);
      } else {
        await jobsService.updateWizardStep1(String(jobId), step1Data());
        setCompletedSteps(prev => prev.includes(1) ? prev : [...prev, 1]);
      }
      setStep(2);
    } catch (e: any) {
      customToast({ type: 'error', title: t('camp.create.error'), message: e?.message || t('wizard.saveStep1Failed') });
    } finally {
      setSaving(false);
    }
  };

  const handleSaveStep2 = async () => {
    if (!jobId) { customToast({ type: 'error', title: t('wizard.noJob'), message: t('wizard.startStep1First') }); return; }
    setSaving(true);
    try {
      await jobsService.updateWizardStep2(String(jobId), { items: roleItems, role_summary: roleSummary || undefined });
      setCompletedSteps(prev => prev.includes(2) ? prev : [...prev, 2]);
      setStep(3);
    } catch (e: any) {
      customToast({ type: 'error', title: t('camp.create.error'), message: e?.message || t('wizard.saveStep2Failed') });
    } finally {
      setSaving(false);
    }
  };

  const handleSaveStep3 = async () => {
    if (!jobId) { customToast({ type: 'error', title: t('wizard.noJob'), message: t('wizard.startStep1First') }); return; }
    const usingLibrary = rubricOption === 'existing';
    if (!usingLibrary && skills.length === 0) { customToast({ type: 'warning', title: t('wizard.noSkills'), message: t('wizard.addSkillOrRubric') }); return; }
    if (!usingLibrary) {
      const total = skills.reduce((s, sk) => s + sk.weight, 0);
      if (total !== 100) { customToast({ type: 'warning', title: t('wizard.weightError'), message: t('wizard.skillWeightsSum').replace('{pct}', String(total)) }); return; }
    }
    const totalEval = evalCategories.reduce((s, c) => s + c.weight, 0);
    if (totalEval !== 100) { customToast({ type: 'warning', title: t('wizard.weightError'), message: t('wizard.categoryWeightsSum').replace('{pct}', String(totalEval)) }); return; }
    setSaving(true);
    try {
      await jobsService.updateWizardStep3(String(jobId), {
        skills: skills.map((s, i) => ({ ...s, sort_order: i })),
        skill_tree_id: usingLibrary && selectedTreeId ? selectedTreeId : null,
      });
      await jobsService.updateWizardStep4(String(jobId), {
        categories: evalCategories.map((c, i) => ({ ...c, sort_order: i })),
        ai_config: aiConfig,
      });
      setCompletedSteps(prev => prev.includes(3) ? prev : [...prev, 3]);
      setStep(4);
    } catch (e: any) {
      customToast({ type: 'error', title: t('camp.create.error'), message: e?.message || t('wizard.saveRubricFailed') });
    } finally {
      setSaving(false);
    }
  };

  const handleSaveStep4 = async () => {
    if (!jobId) { customToast({ type: 'error', title: t('wizard.noJob'), message: t('wizard.startStep1First') }); return; }
    setSaving(true);
    try {
      await jobsService.updateWizardStep5(String(jobId), {
        screening_questions: screeningQuestions.map((q, i) => ({ ...q, sort_order: i })),
        pipeline_stages: pipelineStages.map((s, i) => ({ ...s, sort_order: i })),
      });
      setCompletedSteps(prev => prev.includes(4) ? prev : [...prev, 4]);
      setStep(5);
    } catch (e: any) {
      customToast({ type: 'error', title: t('camp.create.error'), message: e?.message || t('wizard.saveStep5Failed') });
    } finally {
      setSaving(false);
    }
  };

  const handlePublish = async () => {
    if (!jobId) return;
    setPublishing(true);
    try {
      await jobsService.publishWizardJob(String(jobId));
      setIsPublished(true);
      customToast({ type: 'success', title: t('wizard.published'), message: `"${title}" ${t('wizard.isNowLive')}` });
      setTimeout(() => navigate('/jobs'), 1500);
    } catch (e: any) {
      customToast({ type: 'error', title: t('wizard.publishFailed'), message: e?.message || t('wizard.publishFailedMsg') });
    } finally {
      setPublishing(false);
    }
  };

  const addSkill = () => {
    if (!newSkillName.trim()) return;
    setSkills(prev => [...prev, { skill_name: newSkillName.trim(), required_level: newSkillLevel, weight: newSkillWeight, is_mandatory: newSkillMandatory, sort_order: prev.length }]);
    setNewSkillName('');
    setNewSkillWeight(10);
  };

  const removeSkill = (index: number) => {
    setSkills(prev => prev.filter((_, i) => i !== index));
  };

  const addScreeningQuestion = () => {
    if (!newQuestionText.trim()) return;
    setScreeningQuestions(prev => [...prev, { question: newQuestionText.trim(), type: newQuestionType, is_required: true, sort_order: prev.length }]);
    setNewQuestionText('');
  };

  const removeQuestion = (index: number) => {
    setScreeningQuestions(prev => prev.filter((_, i) => i !== index));
  };

  const handleAIAction = useCallback(async (action: string, fn: () => Promise<any>, successMsg: string) => {
    setAILoading(action);
    try {
      const result = await fn();
      customToast({ type: 'success', title: t('wizard.aiSuggestion'), message: successMsg });
      return result;
    } catch (e: any) {
      customToast({ type: 'error', title: t('wizard.aiFailed'), message: e?.message || t('wizard.aiUnavailable') });
      return null;
    } finally {
      setAILoading(null);
    }
  }, []);

  const aiSuggestSkills = async () => {
    if (!title.trim()) { customToast({ type: 'warning', title: t('wizard.enterTitle'), message: t('wizard.enterTitleMsg') }); return; }
    await handleAIAction('skills', async () => {
      const res = await jobsService.suggestSkills(title);
      const suggested: string[] = res?.suggestions || [];
      if (suggested.length === 0) return;
      const existing = new Set(skills.map(s => s.skill_name.toLowerCase()));
      const newSkills = suggested.filter(s => !existing.has(s.toLowerCase())).slice(0, 8);
      setSkills(prev => [...prev, ...newSkills.map((s, i) => ({
        skill_name: s, required_level: 'intermediate', weight: Math.round(100 / (prev.length + newSkills.length)),
        is_mandatory: true, sort_order: prev.length + i,
      }))]);
    }, t('wizard.skillsSuggested').replace('{n}', String(skills.length)));
  };

  const aiSuggestWeights = async () => {
    const names = skills.map(s => s.skill_name);
    if (names.length < 2) { customToast({ type: 'warning', title: t('wizard.addSkills'), message: t('wizard.addTwoSkillsFirst') }); return; }
    await handleAIAction('weights', async () => {
      const res = await jobsService.suggestWeights(names);
      const weights: { skill: string; weight: number }[] = res?.suggestions || [];
      if (weights.length === 0) return;
      setSkills(prev => prev.map(s => {
        const match = weights.find(w => w.skill.toLowerCase() === s.skill_name.toLowerCase());
        return match ? { ...s, weight: Math.max(1, match.weight) } : s;
      }));
    }, t('wizard.weightsRedistributed'));
  };

  const aiGenerateSummary = async () => {
    const filled = roleItems.filter(i => i.answer.trim());
    if (filled.length === 0) { customToast({ type: 'warning', title: t('wizard.fillQA'), message: t('wizard.answerOneQuestionFirst') }); return; }
    await handleAIAction('summary', async () => {
      const res = await jobsService.generateSummary(roleItems);
      const summary = res?.suggestions?.[0];
      if (summary) setRoleSummary(summary);
    }, t('wizard.roleSummaryGenerated'));
  };

  const aiSuggestCategories = async () => {
    const names = skills.map(s => s.skill_name);
    if (names.length < 2) { customToast({ type: 'warning', title: t('wizard.addSkills'), message: t('wizard.addTwoSkillsFirst') }); return; }
    await handleAIAction('categories', async () => {
      const res = await jobsService.suggestCategories(names);
      const cats: EvalCategory[] = res?.suggestions || [];
      if (cats.length >= 2) setEvalCategories(cats);
    }, t('wizard.evalCategoriesSuggested'));
  };

  const aiSuggestPipeline = async () => {
    await handleAIAction('pipeline', async () => {
      const res = await jobsService.suggestPipeline(employmentType);
      const stages: PipelineStageDef[] = res?.suggestions || [];
      if (stages.length >= 3) setPipelineStages(stages);
    }, t('wizard.pipelineStagesSuggested'));
  };

  const aiSuggestQuestions = async () => {
    const names = skills.map(s => s.skill_name);
    if (names.length === 0) { customToast({ type: 'warning', title: t('wizard.addSkills'), message: t('wizard.addSkillsFirst') }); return; }
    await handleAIAction('questions', async () => {
      const res = await jobsService.suggestQuestions(names);
      const qs: { question: string; type: string }[] = res?.suggestions || [];
      if (qs.length === 0) return;
      const existing = new Set(screeningQuestions.map(q => q.question.toLowerCase()));
      const newQs = qs.filter(q => !existing.has(q.question.toLowerCase()));
      setScreeningQuestions(prev => [...prev, ...newQs.map((q, i) => ({
        question: q.question, type: q.type || 'text', is_required: true, sort_order: prev.length + i,
      }))]);
    }, t('wizard.questionsSuggested').replace('{n}', String(screeningQuestions.length)));
  };

  const aiSuggestSalary = async () => {
    await handleAIAction('salary', async () => {
      const res = await jobsService.suggestSalary(title || 'Software Engineer', location || 'Remote');
      const ranges: { min: number; max: number; currency: string }[] = res?.suggestions || [];
      if (ranges.length > 0) {
        const mid = ranges[Math.min(1, ranges.length - 1)];
        setSalaryMin(mid.min);
        setSalaryMax(mid.max);
        setSalaryCurrency(mid.currency || 'USD');
      }
    }, t('wizard.salaryRangeSuggested'));
  };

  const totalSkillWeight = skills.reduce((s, sk) => s + sk.weight, 0);
  const totalEvalWeight = evalCategories.reduce((s, c) => s + c.weight, 0);

  if (loadingWizard) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-purple-600" />
      </div>
    );
  }

  if (isPublished) {
    return (
      <div className="max-w-2xl mx-auto text-center py-16 space-y-4">
        <CheckCircle2 className="h-16 w-16 text-green-500 mx-auto" />
        <h2 className="text-2xl font-bold">{t('wizard.jobPublished')}</h2>
        <p className="text-gray-500">"{title}" {t('wizard.isLiveAccepting')}</p>
        <Button variant="primary" onClick={() => navigate('/jobs')}>{t('wizard.viewAllJobs')}</Button>
      </div>
    );
  }

  const stepLabels = [t('wizard.step1Short'), t('wizard.step2Short'), t('wizard.step3Short'), t('wizard.pipeline'), t('wizard.step5Short')];

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <div className="flex items-center gap-2 mb-2">
          <Sparkles className="h-5 w-5 text-purple-600" />
          <span className="text-sm font-extrabold uppercase tracking-wider text-purple-600">{t('wizard.eyebrow')}</span>
          {jobId && <span className="text-xs text-gray-400 ml-2">{t('wizard.id')}: {jobId}</span>}
        </div>
        <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">
          {editId ? t('wizard.editTitle') : t('wizard.createTitle')}
        </h1>
      </div>

      <div className="flex items-center gap-0.5">
        {stepLabels.map((label, i) => {
          const s = i + 1;
          const isActive = s === step;
          const isDone = completedSteps.includes(s) || s < step;
          return (
            <div key={s} className="flex-1 flex flex-col items-center">
              <button
                type="button"
                onClick={() => { if (completedSteps.includes(s) || s < step) setStep(s); }}
                className={cn(
                  'w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all',
                  isDone && 'bg-purple-600 text-white cursor-pointer',
                  isActive && 'ring-2 ring-purple-600 ring-offset-2 dark:ring-offset-gray-900',
                  !isDone && !isActive && 'bg-gray-200 dark:bg-gray-800 text-gray-400 cursor-not-allowed',
                )}
              >
                {isDone ? <CheckCircle2 className="h-4 w-4" /> : s}
              </button>
              <span className={cn('text-[10px] mt-1 font-medium text-center', isActive ? 'text-purple-600' : 'text-gray-400')}>
                {label}
              </span>
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
                  <CardTitle className="text-xl font-black">{t('wizard.step1Title')}</CardTitle>
                  <CardDescription>{t('wizard.step1Desc')}</CardDescription>
                </CardHeader>

                <Input label={`${t('wizard.jobTitle')} *`} placeholder={t('wizard.titlePlaceholder')} value={title} onChange={e => setTitle(e.target.value)} leftIcon={<Briefcase className="h-4 w-4 text-purple-500" />} />

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('wizard.category')}</label>
                    <Select value={String(categoryId || '')} onValueChange={v => setCategoryId(v ? Number(v) : null)}>
                      <SelectTrigger><SelectValue placeholder={t('wizard.selectCategory')} /></SelectTrigger>
                      <SelectContent>
                        {categories.map(c => <SelectItem key={c.id} value={String(c.id)}>{c.name}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('wizard.hiringManager')}</label>
                    <Select value={String(hiringManagerId || '')} onValueChange={v => setHiringManagerId(v ? Number(v) : null)}>
                      <SelectTrigger><SelectValue placeholder={t('wizard.selectManager')} /></SelectTrigger>
                      <SelectContent>
                        {recruiters.map(r => <SelectItem key={r.id} value={String(r.id)}>{r.name} ({r.email})</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-4">
                  <div className="space-y-1.5">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('wizard.employmentType')}</label>
                    <Select value={employmentType} onValueChange={setEmploymentType}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {EMPLOYMENT_TYPES.map(et => <SelectItem key={et} value={et}>{employmentTypeLabels[et]}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('wizard.workplace')}</label>
                    <Select value={workplaceType} onValueChange={setWorkplaceType}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {WORKPLACE_TYPES.map(wt => <SelectItem key={wt} value={wt}>{workplaceTypeLabels[wt]}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <Input label={t('wizard.openings')} type="number" min={1} value={numOpenings} onChange={e => setNumOpenings(Math.max(1, Number(e.target.value)))} />
                </div>

                <Input label={t('common.location')} placeholder={t('wizard.locationPlaceholder')} value={location} onChange={e => setLocation(e.target.value)} leftIcon={<MapPin className="h-4 w-4 text-indigo-500" />} />

                <div className="grid grid-cols-3 gap-2 items-end">
                  <Input label={t('wizard.salaryMin')} type="number" value={salaryMin || ''} onChange={e => setSalaryMin(e.target.value ? Number(e.target.value) : null)} leftIcon={<Banknote className="h-4 w-4 text-emerald-500" />} />
                  <Input label={t('wizard.salaryMax')} type="number" value={salaryMax || ''} onChange={e => setSalaryMax(e.target.value ? Number(e.target.value) : null)} />
                  <div className="space-y-1.5">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">&nbsp;</label>
                    <Button variant="outline" size="sm" className="w-full" onClick={aiSuggestSalary} disabled={aiLoading === 'salary'}>
                      {aiLoading === 'salary' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5 text-amber-500" />}
                      {t('wizard.aiSuggest')}
                    </Button>
                  </div>
                </div>

                <Input label={t('wizard.internalReference')} placeholder={t('wizard.internalReferencePlaceholder')} value={internalReference} onChange={e => setInternalReference(e.target.value)} />
              </div>
            )}

            {step === 2 && (
              <div className="space-y-5">
                <CardHeader>
                  <CardTitle className="text-xl font-black">{t('wizard.step2Title')}</CardTitle>
                  <CardDescription>{t('wizard.step2Desc')}</CardDescription>
                </CardHeader>

                {roleItems.map((item, i) => (
                  <div key={item.question_key} className="space-y-1.5">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{item.question}</label>
                    <textarea
                      className="w-full rounded-xl border border-purple-200/60 bg-white/70 p-3 text-sm focus:ring-2 focus:ring-purple-500/20 dark:border-white/10 dark:bg-white/5 dark:text-white min-h-[80px]"
                      placeholder={`${t('wizard.describe')} ${item.question.toLowerCase()}...`}
                      value={item.answer}
                      onChange={e => {
                        const updated = [...roleItems];
                        updated[i] = { ...updated[i], answer: e.target.value };
                        setRoleItems(updated);
                      }}
                    />
                  </div>
                ))}

                <div className="flex items-center gap-2 pt-2">
                  <Button variant="outline" size="sm" onClick={aiGenerateSummary} disabled={aiLoading === 'summary'}>
                    {aiLoading === 'summary' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5 text-amber-500" />}
                    {t('wizard.generateRoleSummary')}
                  </Button>
                  {roleSummary && (
                    <Badge variant="success" size="sm">{t('wizard.aiSummaryReady')}</Badge>
                  )}
                </div>
                {roleSummary && (
                  <div className="p-3 rounded-xl bg-purple-50 dark:bg-purple-500/5 border border-purple-200/60">
                    <p className="text-sm text-gray-700 dark:text-gray-300">{roleSummary}</p>
                  </div>
                )}
              </div>
            )}

            {step === 3 && (
              <div className="space-y-5">
                <CardHeader>
                  <CardTitle className="text-xl font-black">{t('wizard.step3Title')}</CardTitle>
                  <CardDescription>{t('wizard.step3Desc')}</CardDescription>
                </CardHeader>

                <div className="flex items-center gap-3 p-4 rounded-xl bg-purple-50 dark:bg-purple-500/10 border border-purple-200/60">
                  <BookOpen className="h-5 w-5 text-purple-600 shrink-0" />
                  <div>
                    <div className="text-sm font-bold text-purple-800 dark:text-purple-300">{t('wizard.evaluationRubric')}</div>
                    <p className="text-xs text-purple-600 dark:text-purple-400">{t('wizard.rubricHint')}</p>
                  </div>
                </div>

                <div className="space-y-3">
                  {[
                    { value: 'existing', label: t('camp.create.useExistingRubric'), desc: t('camp.create.useExistingRubricDesc') },
                    { value: 'new', label: t('camp.create.createNewRubric'), desc: t('wizard.createNewRubricDesc') },
                    { value: 'inline', label: t('wizard.buildInline'), desc: t('wizard.buildInlineDesc') },
                  ].map(opt => (
                    <div key={opt.value}
                      className={cn('flex items-center gap-3 p-4 border-2 rounded-2xl cursor-pointer transition-all', rubricOption === opt.value ? 'border-purple-500 bg-purple-50 dark:bg-purple-500/10' : 'border-gray-200 dark:border-white/10 hover:border-purple-300')}
                      onClick={() => setRubricOption(opt.value)}
                    >
                      <div className={cn('w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0', rubricOption === opt.value ? 'border-purple-600 bg-purple-600' : 'border-gray-300')}>
                        {rubricOption === opt.value && <div className="w-2 h-2 rounded-full bg-white" />}
                      </div>
                      <div>
                        <div className="font-bold text-sm text-gray-800 dark:text-white">{opt.label}</div>
                        <div className="text-xs text-gray-500">{opt.desc}</div>
                      </div>
                    </div>
                  ))}
                </div>

                {rubricOption === 'existing' && (
                  <div className="pl-4 space-y-3">
                    <div className="relative">
                      <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                      <input className="w-full bg-white dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-xl pl-10 pr-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/20 dark:text-white" placeholder={t('wizard.searchRubrics')} value={rubricSearch} onChange={e => setRubricSearch(e.target.value)} />
                    </div>
                    <div className="space-y-2 max-h-60 overflow-y-auto">
                      {rubrics.filter(rb => !rubricSearch || (rb.job_name || '').toLowerCase().includes(rubricSearch.toLowerCase())).length === 0 ? (
                        <p className="text-center py-4 text-gray-400 text-xs">{t('camp.create.noRubricsFound')}</p>
                      ) : rubrics.filter(rb => !rubricSearch || (rb.job_name || '').toLowerCase().includes(rubricSearch.toLowerCase())).map(rb => (
                        <div key={rb.id}
                          className={cn('flex items-center gap-3 p-3 border rounded-xl cursor-pointer transition-all', selectedTreeId === rb.id ? 'border-purple-500 bg-purple-50 dark:bg-purple-500/10' : 'border-gray-200 dark:border-white/10 hover:border-purple-300')}
                          onClick={() => setSelectedTreeId(rb.id)}
                        >
                          <div className={cn('w-4 h-4 rounded-full border-2 flex items-center justify-center shrink-0', selectedTreeId === rb.id ? 'border-purple-600 bg-purple-600' : 'border-gray-300')}>
                            {selectedTreeId === rb.id && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-bold text-gray-800 dark:text-white truncate">{rb.job_name || t('wizard.untitled')}</div>
                            <div className="text-xs text-gray-500">{`${rb.skill_count || 0} ${t('camp.create.skillsLabel')} · ${rb.category_count || 0} ${t('camp.create.categoriesLabel')}`}{rb.seniority ? ` · ${rb.seniority}` : ''}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {rubricOption === 'new' && (
                  <div className="p-4 rounded-xl bg-purple-50/50 dark:bg-purple-500/5 border border-dashed border-purple-200/60 text-center space-y-3">
                    <p className="text-sm text-gray-500">{t('wizard.saveRubricToLibrary')}</p>
                    <Button variant="outline" onClick={() => navigate(`/skill-tree-create?return_to=/jobs/new${jobId ? `?edit=${jobId}` : ''}`)} leftIcon={<Plus className="h-4 w-4" />}>{t('camp.create.createNewRubric')}</Button>
                  </div>
                )}

                {rubricOption !== 'inline' && selectedTreeId && (
                  <div className="flex items-center gap-2 p-3 rounded-xl bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 text-sm">
                    <CheckCircle2 className="h-4 w-4 shrink-0" />
                    <span>{`${t('wizard.linkedRubric')}: ${rubrics.find(r => r.id === selectedTreeId)?.job_name || `${t('wizard.rubricLabel')} #${selectedTreeId}`}`}</span>
                  </div>
                )}

                {rubricOption === 'inline' && (
                  <div className="space-y-5">
                    <div className="border-b border-purple-100 dark:border-white/10 pb-4">
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="font-bold text-sm flex items-center gap-2"><ListChecks className="h-4 w-4" /> {t('wizard.rubricSkills')}</h4>
                    <div className="flex items-center gap-2 flex-wrap">
                      <Button variant="outline" size="sm" onClick={aiSuggestSkills} disabled={aiLoading === 'skills'}>
                        {aiLoading === 'skills' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5 text-amber-500" />}
                        {t('wizard.aiSuggestSkills')}
                      </Button>
                      <Button variant="outline" size="sm" onClick={aiSuggestWeights} disabled={skills.length < 2 || aiLoading === 'weights'}>
                        {aiLoading === 'weights' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                        {t('wizard.balanceWeights')}
                      </Button>
                    </div>
                  </div>

                  {totalSkillWeight !== 100 && skills.length > 0 && (
                    <div className={cn("flex items-center gap-2 text-xs font-semibold px-3 py-1.5 rounded-lg", totalSkillWeight > 100 ? "text-red-600 bg-red-50 dark:bg-red-500/10" : "text-amber-600 bg-amber-50 dark:bg-amber-500/10")}>
                      <AlertTriangle className="h-3 w-3" />
                      {t('wizard.skillWeightsWarning').replace('{pct}', String(totalSkillWeight))}
                    </div>
                  )}

                  <Reorder.Group axis="y" values={skills} onReorder={setSkills} className="space-y-2">
                    {skills.map((skill, i) => (
                      <Reorder.Item key={`skill-${i}`} value={skill} className="flex items-center gap-3 p-3 rounded-xl bg-white/50 dark:bg-white/5 border border-purple-100 dark:border-white/10 cursor-grab active:cursor-grabbing">
                        <GripVertical className="h-4 w-4 text-gray-400 shrink-0" />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-sm">{skill.skill_name}</span>
                            <Badge variant={skill.is_mandatory ? 'primary' : 'default'} size="sm">{levelLabels[skill.required_level] || skill.required_level}</Badge>
                            {skill.is_mandatory && <Star className="h-3 w-3 text-amber-500 fill-amber-500" />}
                          </div>
                          <WeightBar weight={skill.weight} label={skill.skill_name} />
                        </div>
                        <div className="flex items-center gap-1">
                          <div className="flex flex-col">
                            <button type="button" onClick={() => { const s = [...skills]; s[i] = { ...s[i], weight: Math.min(100, s[i].weight + 5) }; setSkills(s); }}><ChevronUp className="h-3 w-3 text-gray-400" /></button>
                            <button type="button" onClick={() => { const s = [...skills]; s[i] = { ...s[i], weight: Math.max(1, s[i].weight - 5) }; setSkills(s); }}><ChevronDown className="h-3 w-3 text-gray-400" /></button>
                          </div>
                          <button type="button" onClick={() => removeSkill(i)} className="p-1 hover:bg-red-50 dark:hover:bg-red-500/10 rounded"><X className="h-3.5 w-3.5 text-red-400" /></button>
                        </div>
                      </Reorder.Item>
                    ))}
                  </Reorder.Group>

                  <div className="grid grid-cols-5 gap-2 p-4 rounded-xl bg-purple-50/50 dark:bg-purple-500/5 border border-dashed border-purple-200/60">
                    <div className="col-span-2">
                      <label className="block text-xs font-medium text-gray-500 mb-1">{t('wizard.skillName')}</label>
                      <input className="w-full rounded-lg border border-purple-200/60 bg-white/70 px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/20 dark:border-white/10 dark:bg-white/5 dark:text-white" placeholder={t('wizard.skillNamePlaceholder')} value={newSkillName} onChange={e => setNewSkillName(e.target.value)} onKeyDown={e => e.key === 'Enter' && addSkill()} />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-500 mb-1">{t('wizard.level')}</label>
                      <select className="w-full rounded-lg border border-purple-200/60 bg-white/70 px-2.5 py-1.5 text-sm dark:border-white/10 dark:bg-white/5 dark:text-white" value={newSkillLevel} onChange={e => setNewSkillLevel(e.target.value)}>
                        {LEVELS.map(l => <option key={l} value={l}>{levelLabels[l]}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-500 mb-1">{t('wizard.weight')}</label>
                      <input className="w-full rounded-lg border border-purple-200/60 bg-white/70 px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/20 dark:border-white/10 dark:bg-white/5 dark:text-white" type="number" min={1} max={100} value={newSkillWeight} onChange={e => setNewSkillWeight(Math.max(1, Math.min(100, Number(e.target.value))))} />
                    </div>
                    <div className="flex items-end">
                      <Button variant="primary" size="sm" className="w-full" onClick={addSkill} leftIcon={<Plus className="h-3.5 w-3.5" />}>{t('common.add')}</Button>
                    </div>
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="font-bold text-sm flex items-center gap-2"><Settings2 className="h-4 w-4" /> {t('wizard.evalCategories')}</h4>
                    <Button variant="outline" size="sm" onClick={aiSuggestCategories} disabled={skills.length < 2 || aiLoading === 'categories'}>
                      {aiLoading === 'categories' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5 text-amber-500" />}
                      {t('wizard.aiSuggestCategories')}
                    </Button>
                  </div>

                  {totalEvalWeight !== 100 && (
                    <div className="flex items-center gap-2 text-xs font-semibold px-3 py-1.5 rounded-lg bg-amber-50 dark:bg-amber-500/10 text-amber-600 mb-3">
                      <AlertTriangle className="h-3 w-3" />
                      {t('wizard.catWeightsWarning').replace('{pct}', String(totalEvalWeight))}
                    </div>
                  )}

                  {evalCategories.map((cat, i) => (
                    <div key={i} className="flex items-center gap-3 p-3 rounded-xl bg-white/50 dark:bg-white/5 border border-purple-100 dark:border-white/10 mb-2">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <input className="font-semibold text-sm bg-transparent border-b border-transparent focus:border-purple-500 outline-none" value={cat.name} onChange={e => { const c = [...evalCategories]; c[i] = { ...c[i], name: e.target.value }; setEvalCategories(c); }} />
                        </div>
                        <WeightBar weight={cat.weight} label={cat.name} />
                      </div>
                      <div className="flex items-center gap-1">
                        <button type="button" onClick={() => { const c = [...evalCategories]; c[i] = { ...c[i], weight: Math.min(100, c[i].weight + 5) }; setEvalCategories(c); }}><ChevronUp className="h-3 w-3 text-gray-400" /></button>
                        <button type="button" onClick={() => { const c = [...evalCategories]; c[i] = { ...c[i], weight: Math.max(1, c[i].weight - 5) }; setEvalCategories(c); }}><ChevronDown className="h-3 w-3 text-gray-400" /></button>
                        <button type="button" onClick={() => setEvalCategories(prev => prev.filter((_, j) => j !== i))} className="p-1 hover:bg-red-50 dark:hover:bg-red-500/10 rounded"><X className="h-3.5 w-3.5 text-red-400" /></button>
                      </div>
                    </div>
                  ))}
                  <Button variant="outline" size="sm" onClick={() => setEvalCategories(prev => [...prev, { name: '', weight: 10, sort_order: prev.length }])} leftIcon={<Plus className="h-3.5 w-3.5" />}>{t('wizard.addCategory')}</Button>
                </div>
                  </div>
                )}

                <div className="border-t border-purple-100 dark:border-white/10 pt-4 space-y-4">
                  <h4 className="font-bold text-sm flex items-center gap-2"><Settings2 className="h-4 w-4" /> {t('wizard.aiScoringConfig')}</h4>
                  <div className="space-y-3">
                    {[
                      { key: 'ai_scoring_enabled', label: t('wizard.aiScoringEnabled'), desc: t('wizard.aiScoringEnabledDesc') },
                      { key: 'explain_ai_decisions', label: t('wizard.explainAiDecisions'), desc: t('wizard.explainAiDecisionsDesc') },
                      { key: 'evidence_based_scoring', label: t('wizard.evidenceBasedScoring'), desc: t('wizard.evidenceBasedScoringDesc') },
                      { key: 'prioritize_verified_skills', label: t('wizard.prioritizeVerifiedSkills'), desc: t('wizard.prioritizeVerifiedSkillsDesc') },
                      { key: 'ignore_missing_cv', label: t('wizard.ignoreMissingCv'), desc: t('wizard.ignoreMissingCvDesc') },
                    ].map(({ key, label, desc }) => (
                      <div key={key} className="flex items-center justify-between">
                        <div><span className="text-sm font-medium">{label}</span><p className="text-xs text-gray-400">{desc}</p></div>
                        <Switch checked={(aiConfig as any)[key]} onCheckedChange={v => setAIConfig(prev => ({ ...prev, [key]: v }))} />
                      </div>
                    ))}
                  </div>
                  <div className="grid grid-cols-3 gap-3 pt-2">
                    <Input label={t('wizard.minRecommendedScore')} type="number" min={0} max={100} value={aiConfig.minimum_recommended_score} onChange={e => setAIConfig(prev => ({ ...prev, minimum_recommended_score: Number(e.target.value) }))} />
                    <Input label={t('wizard.autoShortlist')} type="number" min={0} max={100} value={aiConfig.auto_shortlist_threshold ?? ''} onChange={e => setAIConfig(prev => ({ ...prev, auto_shortlist_threshold: e.target.value ? Number(e.target.value) : null }))} />
                    <Input label={t('wizard.autoReject')} type="number" min={0} max={100} value={aiConfig.auto_reject_threshold ?? ''} onChange={e => setAIConfig(prev => ({ ...prev, auto_reject_threshold: e.target.value ? Number(e.target.value) : null }))} />
                  </div>
                  <div className="grid grid-cols-2 gap-3 pt-2">
                    <Input label="Interview Duration (Minutes)" type="number" min={5} max={180} value={aiConfig.duration_minutes ?? 30} onChange={e => setAIConfig(prev => ({ ...prev, duration_minutes: e.target.value ? Number(e.target.value) : null }))} />
                    <Input label="Max Questions" type="number" min={1} max={30} value={aiConfig.total_questions ?? 6} onChange={e => setAIConfig(prev => ({ ...prev, total_questions: e.target.value ? Number(e.target.value) : null }))} />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{`${t('camp.create.customInstructions')} ${t('camp.create.optional')}`}</label>
                    <textarea className="w-full rounded-xl border border-purple-200/60 bg-white/70 p-3 text-sm focus:ring-2 focus:ring-purple-500/20 dark:border-white/10 dark:bg-white/5 dark:text-white min-h-[60px]" placeholder={t('wizard.aiInstructionsPlaceholder')} value={aiConfig.custom_instructions || ''} onChange={e => setAIConfig(prev => ({ ...prev, custom_instructions: e.target.value || null }))} />
                  </div>
                </div>
              </div>
            )}

            {step === 4 && (
              <div className="space-y-5">
                <CardHeader>
                  <CardTitle className="text-xl font-black">{t('wizard.step4Title')}</CardTitle>
                  <CardDescription>{t('wizard.step4Desc')}</CardDescription>
                </CardHeader>

                <div>
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="font-bold text-sm flex items-center gap-2"><Users className="h-4 w-4" /> {t('wizard.pipelineStages')}</h4>
                    <Button variant="outline" size="sm" onClick={aiSuggestPipeline} disabled={aiLoading === 'pipeline'}>
                      {aiLoading === 'pipeline' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5 text-amber-500" />}
                      {t('wizard.aiSuggest')}
                    </Button>
                  </div>
                  <Reorder.Group axis="y" values={pipelineStages} onReorder={setPipelineStages} className="space-y-2">
                    {pipelineStages.map((stage, i) => (
                      <Reorder.Item key={`stage-${i}`} value={stage} className="flex items-center gap-3 p-2.5 rounded-xl bg-white/50 dark:bg-white/5 border border-purple-100 dark:border-white/10 cursor-grab active:cursor-grabbing">
                        <GripVertical className="h-4 w-4 text-gray-400 shrink-0" />
                        <div className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: stage.color || '#6366f1' }} />
                        <div className="flex-1">
                          <input className="font-medium text-sm bg-transparent border-b border-transparent focus:border-purple-500 outline-none" value={stage.name} onChange={e => { const s = [...pipelineStages]; s[i] = { ...s[i], name: e.target.value, slug: e.target.value.toLowerCase().replace(/\s+/g, '-') }; setPipelineStages(s); }} />
                        </div>
                        <div className="flex items-center gap-1">
                          <input type="color" className="w-6 h-6 rounded cursor-pointer border-0" value={stage.color || '#6366f1'} onChange={e => { const s = [...pipelineStages]; s[i] = { ...s[i], color: e.target.value }; setPipelineStages(s); }} />
                          <button type="button" onClick={() => setPipelineStages(prev => prev.filter((_, j) => j !== i))} className="p-1 hover:bg-red-50 dark:hover:bg-red-500/10 rounded"><X className="h-3.5 w-3.5 text-red-400" /></button>
                        </div>
                      </Reorder.Item>
                    ))}
                  </Reorder.Group>
                  <Button variant="outline" size="sm" className="mt-2" onClick={() => setPipelineStages(prev => [...prev, { name: '', slug: '', sort_order: prev.length, color: PIPELINE_COLORS[prev.length % PIPELINE_COLORS.length], icon: 'circle' }])} leftIcon={<Plus className="h-3.5 w-3.5" />}>{t('wizard.addStage')}</Button>
                </div>

                <div className="border-t border-purple-100 dark:border-white/10 pt-4">
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="font-bold text-sm flex items-center gap-2"><ListChecks className="h-4 w-4" /> {t('wizard.screeningQuestions')}</h4>
                    <Button variant="outline" size="sm" onClick={aiSuggestQuestions} disabled={skills.length === 0 || aiLoading === 'questions'}>
                      {aiLoading === 'questions' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5 text-amber-500" />}
                      {t('wizard.aiGenerate')}
                    </Button>
                  </div>

                  {screeningQuestions.map((q, i) => (
                    <div key={i} className="flex items-center gap-2 p-2.5 mb-2 rounded-xl bg-white/50 dark:bg-white/5 border border-purple-100 dark:border-white/10">
                      <Badge variant="default" size="sm">{qtypeLabels[q.type] || q.type}</Badge>
                      <span className="flex-1 text-sm">{q.question}</span>
                      <button type="button" onClick={() => removeQuestion(i)} className="p-1 hover:bg-red-50 dark:hover:bg-red-500/10 rounded"><Trash2 className="h-3.5 w-3.5 text-red-400" /></button>
                    </div>
                  ))}

                  <div className="flex items-center gap-2 p-3 rounded-xl bg-purple-50/50 dark:bg-purple-500/5 border border-dashed border-purple-200/60">
                    <input className="flex-1 bg-transparent border-0 text-sm outline-none placeholder:text-gray-400" placeholder={t('wizard.addQuestionPlaceholder')} value={newQuestionText} onChange={e => setNewQuestionText(e.target.value)} onKeyDown={e => e.key === 'Enter' && addScreeningQuestion()} />
                    <select className="text-xs rounded-lg border border-purple-200/60 bg-white/70 px-2 py-1 dark:border-white/10 dark:bg-white/5 dark:text-white" value={newQuestionType} onChange={e => setNewQuestionType(e.target.value)}>
                      {QUESTION_TYPES.map(qt => <option key={qt} value={qt}>{qtypeLabels[qt]}</option>)}
                    </select>
                    <Button variant="primary" size="sm" onClick={addScreeningQuestion} leftIcon={<Plus className="h-3 w-3" />}>{t('common.add')}</Button>
                  </div>
                </div>
              </div>
            )}

            {step === 5 && (
              <div className="space-y-5">
                <CardHeader>
                  <CardTitle className="text-xl font-black">{t('wizard.step5Title')}</CardTitle>
                  <CardDescription>{t('wizard.step5Desc')}</CardDescription>
                </CardHeader>

                <div className="grid grid-cols-2 gap-4 p-4 rounded-xl bg-purple-50/50 dark:bg-purple-500/5">
                  <div><span className="text-xs text-gray-400">{t('wizard.title')}</span><p className="font-bold">{title}</p></div>
                  <div><span className="text-xs text-gray-400">{t('common.location')}</span><p className="font-bold">{location || t('wizard.notSet')}</p></div>
                  <div><span className="text-xs text-gray-400">{t('wizard.type')}</span><p className="font-bold capitalize">{employmentTypeLabels[employmentType] || employmentType}</p></div>
                  <div><span className="text-xs text-gray-400">{t('wizard.workplace')}</span><p className="font-bold capitalize">{workplaceTypeLabels[workplaceType] || workplaceType}</p></div>
                  <div><span className="text-xs text-gray-400">{t('wizard.salary')}</span><p className="font-bold">{salaryMin && salaryMax ? `${salaryMin}–${salaryMax} ${salaryCurrency}` : t('wizard.notSet')}</p></div>
                  <div><span className="text-xs text-gray-400">{t('wizard.openings')}</span><p className="font-bold">{numOpenings}</p></div>
                </div>

                <div className="space-y-2">
                  <h4 className="font-bold text-sm">{`${t('wizard.skills')} (${skills.length})`}</h4>
                  <div className="flex flex-wrap gap-1.5">
                    {skills.map((s, i) => (
                      <Badge key={i} variant="primary" size="sm" className="flex items-center gap-1">
                        {s.skill_name} <span className="text-[10px] opacity-70">({s.weight}%)</span>
                      </Badge>
                    ))}
                  </div>
                </div>

                <div className="space-y-2">
                  <h4 className="font-bold text-sm">{`${t('wizard.pipeline')} (${pipelineStages.length} ${t('wizard.stages')})`}</h4>
                  <div className="flex gap-2">
                    {pipelineStages.map((s, i) => (
                      <div key={i} className="flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg" style={{ backgroundColor: (s.color || '#6366f1') + '20', color: s.color || '#6366f1' }}>
                        <div className="w-2 h-2 rounded-full" style={{ backgroundColor: s.color || '#6366f1' }} />
                        {s.name}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-white/50 dark:bg-white/5 border border-gray-200 dark:border-white/10">
                  <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3">{t('wizard.evaluationRubric')}</h4>
                  <p className="text-sm text-gray-700 dark:text-gray-300">
                    {rubricOption === 'existing' && selectedTreeId
                      ? `${t('wizard.linkedRubric')}: ${rubrics.find(r => r.id === selectedTreeId)?.job_name || `${t('wizard.rubricLabel')} #${selectedTreeId}`}`
                      : rubricOption === 'new'
                        ? t('camp.create.newRubricWillBeCreated')
                        : t('wizard.builtInline')}
                  </p>
                </div>

                <div className="space-y-1">
                  <h4 className="font-bold text-sm">{t('wizard.evalCategories')}</h4>
                  {evalCategories.map((c, i) => <WeightBar key={i} weight={c.weight} label={c.name} />)}
                </div>

                <div className="flex items-center gap-2 p-3 rounded-xl bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-300 text-sm">
                  <AlertTriangle className="h-4 w-4 shrink-0" />
                  <span>{t('wizard.reviewWarning')}</span>
                </div>
              </div>
            )}

          </Card>
        </motion.div>
      </AnimatePresence>

      <div className="flex items-center justify-between">
        <div>
          {step > 1 && (
            <Button variant="ghost" onClick={() => setStep(step - 1)} leftIcon={<ArrowLeft className="h-4 w-4" />}>{t('common.back')}</Button>
          )}
        </div>
        <div className="flex items-center gap-2">
          {step < 5 ? (
            <Button
              variant="primary"
              size="lg"
              className="px-8 font-bold shadow-lg shadow-purple-500/25"
              onClick={() => {
                if (step === 1) handleSaveStep1();
                else if (step === 2) handleSaveStep2();
                else if (step === 3) handleSaveStep3();
                else if (step === 4) handleSaveStep4();
              }}
              disabled={saving}
              rightIcon={saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
            >
              {saving ? t('wizard.saving') : t('wizard.saveAndContinue')}
            </Button>
          ) : (
            <Button
              variant="primary"
              size="lg"
              className="px-8 font-bold shadow-lg shadow-green-500/25 bg-green-600 hover:bg-green-700"
              onClick={handlePublish}
              disabled={publishing}
              rightIcon={publishing ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
            >
              {publishing ? t('wizard.publishing') : t('wizard.publishJob')}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}