// ============================================================
// Candidate Own Profile View - Matches Candway Production UI
// ============================================================

import { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router';
import { motion } from 'framer-motion';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { candidateService, type CandidateComprehensiveProfile } from '@/services/candidate.service';
import { Card } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/shared/components/ui/dialog';
import { customToast } from '@/shared/components/ui/toast';
import { cn } from '@/utils/cn';
import { useLanguage } from '@/contexts/language-context';
import {
  ArrowLeft,
  Share2,
  Upload,
  MapPin,
  Mail,
  Phone,
  CheckCircle2,
  Edit3,
  Plus,
  Mic,
  Shield,
  Info,
  Sparkles,
  Settings,
  Briefcase,
  GraduationCap,
  Wrench,
  Activity,
  User,
  FileUp,
} from 'lucide-react';

type ProfileTab = 'overview' | 'experience' | 'education' | 'skills' | 'assessments' | 'activity' | 'qualifications';

const TABS: { id: ProfileTab; label: string; icon: React.ElementType }[] = [
  { id: 'overview', label: 'Overview', icon: User },
  { id: 'experience', label: 'Experience', icon: Briefcase },
  { id: 'education', label: 'Education', icon: GraduationCap },
  { id: 'skills', label: 'Skills', icon: Wrench },
  { id: 'assessments', label: 'Assessments', icon: Mic },
  { id: 'activity', label: 'Activity', icon: Activity },
  { id: 'qualifications', label: 'Qualifications', icon: Shield },
];

export default function CandidateOwnProfilePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { t } = useLanguage();
  const [activeTab, setActiveTab] = useState<ProfileTab>('overview');
  const [editAboutOpen, setEditAboutOpen] = useState(false);
  const [editSkillsOpen, setEditSkillsOpen] = useState(false);
  const [editExperienceOpen, setEditExperienceOpen] = useState(false);
  const [editEducationOpen, setEditEducationOpen] = useState(false);
  const [editingExperience, setEditingExperience] = useState<any | null>(null);
  const [editingEducation, setEditingEducation] = useState<any | null>(null);
  const [qualificationUploading, setQualificationUploading] = useState(false);
  const [qualDialogOpen, setQualDialogOpen] = useState(false);
  const [qualFile, setQualFile] = useState<File | null>(null);
  const [qualTitle, setQualTitle] = useState('');
  const [qualCategory, setQualCategory] = useState('certificate');

  const [editPrefsOpen, setEditPrefsOpen] = useState(false);
  const [prefAvailability, setPrefAvailability] = useState('');
  const [prefWorkTypes, setPrefWorkTypes] = useState<string[]>([]);
  const [prefLanguages, setPrefLanguages] = useState('');
  const [prefSalaryMin, setPrefSalaryMin] = useState('');
  const [prefSalaryMax, setPrefSalaryMax] = useState('');
  const [prefRelocation, setPrefRelocation] = useState(false);

  const qualFileInputRef = useRef<HTMLInputElement>(null);

  const availabilityLabels: Record<string, string> = {
    'Immediately': t('own.avail.immediately'),
    '2 weeks': t('own.avail.twoWeeks'),
    '1 month': t('own.avail.oneMonth'),
    '3+ months': t('own.avail.threeMonthsPlus'),
  };

  const workTypeLabels: Record<string, string> = {
    'Full-Time': t('own.workType.fullTime'),
    'Part-Time': t('own.workType.partTime'),
    Contract: t('own.workType.contract'),
    Freelance: t('own.workType.freelance'),
    Internship: t('own.workType.internship'),
    Remote: t('jobs.remote'),
  };

  const handleQualificationUpload = async (file: File) => {
    setQualFile(file);
    setQualTitle(file.name.replace(/\.[^.]+$/, ''));
    setQualCategory('certificate');
    setQualDialogOpen(true);
  };

  const submitQualification = async () => {
    if (!qualFile || !qualTitle.trim() || qualTitle.trim().length < 3) return;
    const formData = new FormData();
    formData.append('file', qualFile);
    formData.append('title', qualTitle.trim());
    formData.append('category', qualCategory);
    setQualDialogOpen(false);
    setQualificationUploading(true);
    try {
      await candidateService.uploadQualification(formData);
      customToast({ type: 'success', title: t('own.documentUploaded'), message: `${qualTitle.trim()} ${t('own.documentUploadedMsg')}` });
      await queryClient.invalidateQueries({ queryKey: ['candidate-comprehensive-profile'] });
    } catch (e: any) {
      customToast({ type: 'error', title: t('own.uploadFailed'), message: e?.detail || e?.message || t('own.uploadFailedMsg') });
    } finally {
      setQualificationUploading(false);
    }
  };
  
  const { data: profileResponse, isLoading, isError } = useQuery({
    queryKey: ['candidate-comprehensive-profile'],
    queryFn: async () => {
      const res = await candidateService.getComprehensiveProfile();
      return res;
    },
  });

  const { data: rawProfile } = useQuery({
    queryKey: ['candidate-profile-raw'],
    queryFn: () => candidateService.getProfile(),
  });

  useEffect(() => {
    setPrefAvailability(rawProfile?.availability || '');
    setPrefWorkTypes((rawProfile?.work_preference || '').split(',').map((s: string) => s.trim()).filter(Boolean));
    setPrefLanguages(rawProfile?.languages || '');
    setPrefSalaryMin(rawProfile?.salary_expectation_min ? String(rawProfile.salary_expectation_min) : '');
    setPrefSalaryMax(rawProfile?.salary_expectation_max ? String(rawProfile.salary_expectation_max) : '');
    setPrefRelocation(!!rawProfile?.relocation_willing);
  }, [rawProfile?.availability, rawProfile?.work_preference, rawProfile?.languages, rawProfile?.salary_expectation_min, rawProfile?.salary_expectation_max, rawProfile?.relocation_willing]);

  const profile = profileResponse;
  const analysis: CandidateComprehensiveProfile['analysis'] = profile?.analysis || {
    experience: [], education: [], skills: [], summary: '', detected_role: '', seniority_level: '',
  };
  const initialAboutText = analysis.summary || `${profile?.name || t('own.candidate')} ${t('own.professionalBlurb')} ${profile?.application?.score || 0}.`;

  const normalizeSkills = (raw: any[]): any[] =>
    (raw || []).map((s) =>
      typeof s === 'string' ? { name: s, level: 70 } : s
    );

  const [aboutText, setAboutText] = useState(initialAboutText);
  const [skills, setSkills] = useState<any[]>(normalizeSkills(analysis.skills));
  useEffect(() => {
    setSkills(normalizeSkills(analysis.skills));
  }, [analysis.skills]);
  
  const [newSkill, setNewSkill] = useState('');
  const [newSkillLevel, setNewSkillLevel] = useState(70);

  const [experiences, setExperiences] = useState<any[]>([]);
  const [education, setEducation] = useState<any[]>([]);

  useEffect(() => {
    const mapExp = (e: any) => ({
      id: e.id || `exp_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      title: e.title || e.role || '',
      company: e.company || e.organization || '',
      period: e.period || e.duration || '',
      description: e.description || e.achievements || '',
    });
    const mapEdu = (e: any) => ({
      id: e.id || `edu_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      degree: e.degree || e.field || '',
      school: e.school || e.institution || '',
      year: e.year || '',
    });
    setExperiences((analysis.experience || []).map(mapExp));
    setEducation((analysis.education || []).map(mapEdu));
  }, [analysis.experience, analysis.education]);

  const professionalScore = profile?.application?.score || 0;
  const profileCompleteness = (() => {
    let score = 0;
    if (profile?.name) score += 20;
    if (profile?.email) score += 10;
    if (profile?.phone) score += 10;
    if (profile?.location) score += 10;
    if (analysis.skills?.length) score += 20;
    if (analysis.experience?.length) score += 15;
    if (analysis.education?.length) score += 10;
    if (profile?.bio) score += 5;
    return Math.min(score, 100);
  })();

  const refreshProfile = () => {
    queryClient.invalidateQueries({ queryKey: ['candidate-comprehensive-profile'] });
  };

  const handleShare = () => {
    const url = `${window.location.origin}/profile-view?user_id=${(profile as any)?.user_id ?? ''}`;
    navigator.clipboard.writeText(url).then(
      () => customToast({ type: 'success', title: t('toast.linkCopied'), message: t('own.linkCopiedMsg') }),
      () => customToast({ type: 'error', title: t('own.copyFailed'), message: t('own.copyFailedMsg') }),
    );
  };

  const handleImportCV = () => {
    customToast({ type: 'info', title: t('own.importCV'), message: t('own.openingCvUpload') });
    navigate('/cv-builder');
  };

  const handleAddSkill = async () => {
    if (!newSkill.trim()) return;
    const next = [...skills, { name: newSkill.trim(), level: newSkillLevel }];
    setSkills(next);
    setNewSkill('');
    setNewSkillLevel(70);
    setEditSkillsOpen(false);
    try {
      await candidateService.updateProfile({ skills: next });
      customToast({ type: 'success', title: t('own.skillAdded'), message: `"${newSkill}" ${t('own.skillAddedMsg')}` });
    } catch {
      customToast({ type: 'error', title: t('own.saveFailed'), message: t('own.skillSaveFailedMsg') });
    }
  };

  const handleSaveAbout = async () => {
    setEditAboutOpen(false);
    try {
      await candidateService.updateProfile({ bio: aboutText });
      refreshProfile();
      customToast({ type: 'success', title: t('own.saved'), message: t('own.savedAbout') });
    } catch {
      customToast({ type: 'error', title: t('own.saveFailed'), message: t('own.aboutSaveFailedMsg') });
    }
  };

  const togglePrefWorkType = (t: string) => {
    setPrefWorkTypes(prev => prev.includes(t) ? prev.filter(x => x !== t) : [...prev, t]);
  };

  const handleSavePrefs = async () => {
    setEditPrefsOpen(false);
    try {
      await candidateService.updateProfile({
        availability: prefAvailability,
        work_preference: prefWorkTypes.join(', '),
        languages: prefLanguages,
        salary_expectation_min: prefSalaryMin ? parseInt(prefSalaryMin) : null,
        salary_expectation_max: prefSalaryMax ? parseInt(prefSalaryMax) : null,
        relocation_willing: prefRelocation,
      });
      refreshProfile();
      queryClient.invalidateQueries({ queryKey: ['candidate-profile-raw'] });
      customToast({ type: 'success', title: t('own.saved'), message: t('own.prefsUpdated') });
    } catch {
      customToast({ type: 'error', title: t('own.saveFailed'), message: t('own.prefsSaveFailedMsg') });
    }
  };

  const persistExperience = async (next: any[]) => {
    setExperiences(next);
    try {
      await candidateService.saveBuilderData({ experience: next });
      refreshProfile();
      customToast({ type: 'success', title: t('own.saved'), message: t('own.experienceUpdated') });
    } catch {
      customToast({ type: 'error', title: t('own.saveFailed'), message: t('own.experienceSaveFailedMsg') });
    }
  };

  const persistEducation = async (next: any[]) => {
    setEducation(next);
    try {
      await candidateService.saveBuilderData({ education: next });
      refreshProfile();
      customToast({ type: 'success', title: t('own.saved'), message: t('own.educationUpdated') });
    } catch {
      customToast({ type: 'error', title: t('own.saveFailed'), message: t('own.educationSaveFailedMsg') });
    }
  };

  const handleAddExperience = () => {
    setEditingExperience({ id: `exp_${Date.now()}`, title: '', company: '', period: '', description: '' });
    setEditExperienceOpen(true);
  };

  const handleEditExperience = (item: any) => {
    setEditingExperience({ ...item });
    setEditExperienceOpen(true);
  };

  const handleSaveExperience = async () => {
    if (!editingExperience) return;
    const exists = experiences.some(e => e.id === editingExperience.id);
    const next = exists
      ? experiences.map(e => e.id === editingExperience.id ? editingExperience : e)
      : [editingExperience, ...experiences];
    setEditExperienceOpen(false);
    await persistExperience(next);
  };

  const handleDeleteExperience = async (id: string) => {
    await persistExperience(experiences.filter(e => e.id !== id));
  };

  const handleAddEducation = () => {
    setEditingEducation({ id: `edu_${Date.now()}`, degree: '', school: '', year: '' });
    setEditEducationOpen(true);
  };

  const handleEditEducation = (item: any) => {
    setEditingEducation({ ...item });
    setEditEducationOpen(true);
  };

  const handleSaveEducation = async () => {
    if (!editingEducation) return;
    const exists = education.some(e => e.id === editingEducation.id);
    const next = exists
      ? education.map(e => e.id === editingEducation.id ? editingEducation : e)
      : [editingEducation, ...education];
    setEditEducationOpen(false);
    await persistEducation(next);
  };

  const handleDeleteEducation = async (id: string) => {
    await persistEducation(education.filter(e => e.id !== id));
  };

  const scoreLabel = professionalScore >= 80 ? t('own.strongMatch') : professionalScore >= 50 ? t('own.goodMatch') : professionalScore > 0 ? t('own.fairMatch') : t('own.fairMatch');

  if (isLoading) {
    return <div className="flex justify-center items-center py-20 text-gray-500">{t('own.loadingProfile')}</div>;
  }

  if (isError || !profile) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-gray-500">
        <User className="w-16 h-16 mb-4 text-gray-300" />
        <p className="text-lg font-medium">{t('own.loadProfileFailed')}</p>
        <p className="text-sm mt-1">{t('own.refreshPageHint')}</p>
      </div>
    );
  }

  return (
    <div className="space-y-5 max-w-6xl mx-auto">
      {/* Top actions row */}
      <div className="flex items-center justify-between">
        <Link
          to="/dashboard"
          className="inline-flex items-center gap-1.5 text-sm font-medium text-gray-500 hover:text-purple-600 dark:text-gray-400 dark:hover:text-purple-400 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          {t('own.backToDashboard')}
        </Link>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" leftIcon={<Share2 className="h-3.5 w-3.5" />} onClick={handleShare}>
            {t('own.share')}
          </Button>
          <Button variant="primary" size="sm" leftIcon={<Upload className="h-3.5 w-3.5" />} onClick={handleImportCV} className="font-semibold shadow-md shadow-purple-500/20">
            {t('own.importCV')}
          </Button>
        </div>
      </div>

      {/* Profile Header Card */}
      <Card className="p-6 md:p-8 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
        <div className="flex flex-col lg:flex-row lg:items-start gap-6 lg:gap-10">
          {/* Left: Avatar + Identity */}
          <div className="flex flex-col sm:flex-row items-start gap-5 flex-1">
            {/* Avatar */}
            <div className="relative shrink-0">
              <div className="h-24 w-24 md:h-28 md:w-28 rounded-full bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center text-white text-3xl md:text-4xl font-bold shadow-lg shadow-purple-500/25 overflow-hidden">
                {profile?.avatar ? <img src={profile.avatar} alt={profile.name} className="h-full w-full object-cover" /> : profile?.name?.substring(0, 2).toUpperCase() || 'C'}
              </div>
              <span className="absolute bottom-1 right-1 h-4 w-4 rounded-full bg-emerald-400 border-[3px] border-white dark:border-gray-900" />
            </div>

            {/* Name + Meta */}
            <div className="space-y-2.5 min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="text-2xl md:text-[1.75rem] font-bold text-gray-900 dark:text-white tracking-tight">
                  {profile?.name || t('own.candidate')}
                </h1>
                <CheckCircle2 className="h-5 w-5 text-violet-500 fill-violet-500 text-white shrink-0" />
              </div>

              <p className="text-base font-medium text-violet-600 dark:text-violet-400">
                {profile?.headline || analysis.detected_role || t('own.professional')}
              </p>

              <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-sm text-gray-500 dark:text-gray-400">
                <span className="inline-flex items-center gap-1.5">
                  <MapPin className="h-3.5 w-3.5 text-gray-400" />
                  {profile?.location || t('own.notSpecified')}
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <Mail className="h-3.5 w-3.5 text-gray-400" />
                  {profile?.email || 'N/A'}
                </span>
                {profile?.phone && (
                  <span className="inline-flex items-center gap-1.5">
                    <Phone className="h-3.5 w-3.5 text-gray-400" />
                    {profile.phone}
                  </span>
                )}
              </div>

              <div className="flex flex-wrap gap-2 pt-1">
                {profile?.availability ? (
                  <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200/80 dark:bg-emerald-500/10 dark:text-emerald-400 dark:border-emerald-500/20">
                    {profile.availability === 'immediately'
                      ? t('own.availableImmediately')
                      : profile.availability === 'notice_period'
                        ? t('own.availableAfterNotice')
                        : profile.availability === 'not_available'
                          ? t('own.notAvailable')
                          : profile.availability}
                  </span>
                ) : (
                  <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200/80 dark:bg-emerald-500/10 dark:text-emerald-400 dark:border-emerald-500/20">
                    {t('own.availableImmediately')}
                  </span>
                )}
                {analysis.seniority_level ? (
                  <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-sky-50 text-sky-700 border border-sky-200/80 dark:bg-sky-500/10 dark:text-sky-400 dark:border-sky-500/20">
                    {analysis.seniority_level}
                  </span>
                ) : (
                  <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-sky-50 text-sky-700 border border-sky-200/80 dark:bg-sky-500/10 dark:text-sky-400 dark:border-sky-500/20">
                    {t('own.entryLevel')}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Right: Professional Score Card */}
          <div className="w-full lg:w-[320px] shrink-0 rounded-2xl bg-gradient-to-br from-violet-50/90 to-indigo-50/70 dark:from-violet-500/10 dark:to-indigo-500/5 border border-violet-100/80 dark:border-violet-500/15 p-5">
            <div className="flex items-start gap-4">
              {/* Circular score */}
              <div className="relative h-16 w-16 shrink-0">
                <svg className="h-16 w-16 -rotate-90" viewBox="0 0 64 64">
                  <circle cx="32" cy="32" r="28" fill="none" stroke="currentColor" strokeWidth="5" className="text-violet-100 dark:text-violet-900/40" />
                  <circle
                    cx="32" cy="32" r="28" fill="none" stroke="currentColor" strokeWidth="5"
                    strokeDasharray={`${(professionalScore / 100) * 176} 176`}
                    strokeLinecap="round"
                    className="text-violet-500"
                  />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="text-sm font-bold text-gray-700 dark:text-gray-200">{professionalScore}%</span>
                </div>
              </div>

              <div className="min-w-0 space-y-1">
                <div className="flex items-center gap-1.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-violet-500" />
                  <span className="text-[10px] font-bold uppercase tracking-wider text-violet-600 dark:text-violet-400">
                    {t('own.professionalScore')}
                  </span>
                </div>
                <p className="text-base font-bold text-gray-900 dark:text-white">{scoreLabel}</p>
                <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
                  {t('own.scoreExplain')}
                </p>
                <button className="text-xs font-semibold text-violet-600 dark:text-violet-400 hover:underline inline-flex items-center gap-0.5 pt-0.5">
                  {t('own.howCalculated')}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="mt-7 border-b border-gray-100 dark:border-white/[0.06] -mx-6 md:-mx-8 px-6 md:px-8">
          <div className="flex items-center gap-1 overflow-x-auto pb-0 scrollbar-none">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  'inline-flex items-center gap-1.5 px-3.5 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 transition-colors -mb-px',
                  activeTab === tab.id
                    ? 'border-violet-600 text-violet-600 dark:border-violet-400 dark:text-violet-400'
                    : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
                )}
              >
                <tab.icon className="h-3.5 w-3.5" />
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </Card>

      {/* Tab Content */}
      {activeTab === 'overview' && (
        <motion.div
          key="overview"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25 }}
          className="space-y-5"
        >
          {/* Three cards row */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* About */}
            <Card className="p-5 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-base font-bold text-gray-900 dark:text-white">{t('own.about')}</h3>
                <button
                  onClick={() => setEditAboutOpen(true)}
                  className="inline-flex items-center gap-1 text-xs font-semibold text-violet-600 dark:text-violet-400 hover:text-violet-700"
                >
                  <Edit3 className="h-3 w-3" /> {t('common.edit')}
                </button>
              </div>
              <p className="text-sm text-gray-600 dark:text-gray-300 leading-relaxed mb-5">
                {aboutText}
              </p>
              <div className="rounded-xl bg-gray-50 dark:bg-white/[0.03] border border-gray-100 dark:border-white/[0.06] p-3.5">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">{t('own.profileCompleteness')}</span>
                  <span className="text-sm font-bold text-gray-700 dark:text-gray-200">{profileCompleteness}%</span>
                </div>
                <div className="h-2 rounded-full bg-gray-200 dark:bg-white/10 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-violet-500 to-purple-500 transition-all duration-500"
                    style={{ width: `${profileCompleteness}%` }}
                  />
                </div>
              </div>
            </Card>

            {/* Skills */}
            <Card className="p-5 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-base font-bold text-gray-900 dark:text-white">{t('own.skills')}</h3>
                <button
                  onClick={() => setEditSkillsOpen(true)}
                  className="inline-flex items-center gap-1 text-xs font-semibold text-violet-600 dark:text-violet-400 hover:text-violet-700"
                >
                  <Plus className="h-3 w-3" /> {t('common.edit')}
                </button>
              </div>
              <div className="space-y-4">
                {skills.map((skill) => (
                  <div key={skill.name}>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-sm text-gray-700 dark:text-gray-300">{skill.name}</span>
                      <span className="text-sm font-semibold text-gray-500">{skill.level}%</span>
                    </div>
                    <div className="h-2 rounded-full bg-gray-100 dark:bg-white/10 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-violet-500 to-indigo-500"
                        style={{ width: `${skill.level}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </Card>

            {/* Experience */}
            <Card className="p-5 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-base font-bold text-gray-900 dark:text-white">{t('own.experience')}</h3>
                <button onClick={handleAddExperience} className="inline-flex items-center gap-1 text-xs font-semibold text-violet-600 dark:text-violet-400 hover:text-violet-700">
                  <Plus className="h-3 w-3" /> {t('common.add')}
                </button>
              </div>
              {experiences.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-10 text-center">
                  <Info className="h-5 w-5 text-gray-300 dark:text-gray-600 mb-2" />
                  <p className="text-sm text-gray-400 dark:text-gray-500">{t('own.noExperienceYet')}</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {experiences.map((exp) => (
                    <div key={exp.id}>
                      <div className="text-sm font-bold text-gray-900 dark:text-white">{exp.title || t('own.untitledRole')}</div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">
                        {[exp.company, exp.period].filter(Boolean).join(' · ') || t('own.noDetails')}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>

          {/* Second row: Assessments, Education, Qualifications */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Assessments */}
            <Card className="p-5 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-base font-bold text-gray-900 dark:text-white">{t('own.assessments')}</h3>
                <button
                  onClick={() => navigate('/cv-builder')}
                  className="inline-flex items-center gap-1 text-xs font-semibold text-violet-600 dark:text-violet-400 hover:text-violet-700"
                >
                  <Mic className="h-3 w-3" /> {t('own.takeAssessment')}
                </button>
              </div>
              <div className="flex flex-col items-center justify-center py-10 text-center">
                <p className="text-sm text-gray-400 dark:text-gray-500 italic">{t('own.noAssessments')}</p>
              </div>
            </Card>

            {/* Education */}
            <Card className="p-5 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-base font-bold text-gray-900 dark:text-white">{t('own.education')}</h3>
                <button onClick={handleAddEducation} className="inline-flex items-center gap-1 text-xs font-semibold text-violet-600 dark:text-violet-400 hover:text-violet-700">
                  <Plus className="h-3 w-3" /> {t('common.add')}
                </button>
              </div>
              {education.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-10 text-center">
                  <Info className="h-5 w-5 text-gray-300 dark:text-gray-600 mb-2" />
                  <p className="text-sm text-gray-400 dark:text-gray-500">{t('own.noEducationYet')}</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {education.map((edu) => (
                    <div key={edu.id}>
                      <div className="text-sm font-bold text-gray-900 dark:text-white">{edu.degree || t('own.untitledDegree')}</div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">
                        {[edu.school, edu.year].filter(Boolean).join(' · ') || t('own.noDetails')}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            {/* Qualifications */}
            <Card className="p-5 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-base font-bold text-gray-900 dark:text-white">{t('own.qualifications')}</h3>
                <button onClick={() => qualFileInputRef.current?.click()} className="inline-flex items-center gap-1 text-xs font-semibold text-violet-600 dark:text-violet-400 hover:text-violet-700">
                  <FileUp className="h-3 w-3" /> {t('common.upload')}
                </button>
              </div>
              <div className="flex flex-col items-center justify-center py-6 text-center space-y-3">
                <div className="h-14 w-14 rounded-2xl bg-violet-50 dark:bg-violet-500/10 flex items-center justify-center">
                  <Shield className="h-7 w-7 text-violet-400" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-gray-700 dark:text-gray-300">{t('own.proveQualifications')}</p>
                  <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">{t('own.uploadDocs')}</p>
                </div>
                <Button variant="primary" size="sm" leftIcon={<Upload className="h-3.5 w-3.5" />} className="font-semibold" onClick={() => qualFileInputRef.current?.click()} disabled={qualificationUploading}>
                  {qualificationUploading ? t('own.uploading') : t('own.uploadDocument')}
                </Button>
                <button
                  onClick={() => navigate('/cv-builder')}
                  className="text-xs font-semibold text-violet-600 dark:text-violet-400 hover:underline inline-flex items-center gap-1 pt-1"
                >
                  <Sparkles className="h-3 w-3" /> {t('own.buildFullProfile')}
                </button>
              </div>
            </Card>
          </div>

          {/* Job Preferences */}
          <Card className="p-5 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-bold text-gray-900 dark:text-white">{t('own.jobPreferences')}</h3>
              <button
                onClick={() => setEditPrefsOpen(true)}
                className="inline-flex items-center gap-1 text-xs font-semibold text-violet-600 dark:text-violet-400 hover:text-violet-700"
              >
                <Edit3 className="h-3 w-3" /> {t('common.edit')}
              </button>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-1">{t('own.availability')}</div>
                <div className="text-sm font-semibold text-gray-800 dark:text-gray-200">{availabilityLabels[prefAvailability] || prefAvailability || '—'}</div>
              </div>
              <div>
                <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-1">{t('own.workType')}</div>
                <div className="text-sm font-semibold text-gray-800 dark:text-gray-200">{prefWorkTypes.map(w => workTypeLabels[w] || w).join(', ') || '—'}</div>
              </div>
              <div>
                <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-1">{t('own.languages')}</div>
                <div className="text-sm font-semibold text-gray-800 dark:text-gray-200">{prefLanguages || '—'}</div>
              </div>
              <div>
                <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-1">{t('own.salaryTnd')}</div>
                <div className="text-sm font-semibold text-gray-800 dark:text-gray-200">
                  {prefSalaryMin || prefSalaryMax ? `${prefSalaryMin || '0'} - ${prefSalaryMax || '∞'} TND` : '—'}
                </div>
              </div>
              <div>
                <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-1">{t('cprofile.field.relocation')}</div>
                <div className="text-sm font-semibold text-gray-800 dark:text-gray-200">{prefRelocation ? t('own.willing') : t('own.notWilling')}</div>
              </div>
            </div>
          </Card>

          {/* Bottom CTA bar */}
          <Card className="p-5 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h3 className="text-base font-bold text-gray-900 dark:text-white">{t('own.completeWithAI')}</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                  {t('own.completeWithAIDesc')}
                </p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <Button
                  variant="primary"
                  size="sm"
                  leftIcon={<Sparkles className="h-3.5 w-3.5" />}
                  onClick={() => navigate('/cv-builder')}
                  className="font-semibold shadow-md shadow-purple-500/20"
                >
                  {t('own.aiProfileBuilder')}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  leftIcon={<Settings className="h-3.5 w-3.5" />}
                  onClick={() => navigate('/settings')}
                >
                  {t('own.settings')}
                </Button>
              </div>
            </div>
          </Card>
        </motion.div>
      )}

      {/* Experience Tab */}
      {activeTab === 'experience' && (
        <Card className="p-6 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-bold text-gray-900 dark:text-white">{t('own.workExperience')}</h3>
            <Button variant="primary" size="sm" leftIcon={<Plus className="h-3.5 w-3.5" />} onClick={handleAddExperience}>
              {t('own.addExperience')}
            </Button>
          </div>
          {experiences.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 text-center space-y-3">
              <Briefcase className="h-10 w-10 text-gray-300 dark:text-gray-600" />
              <p className="text-sm text-gray-500 dark:text-gray-400">{t('own.noExperienceHint')}</p>
              <Button variant="primary" size="sm" leftIcon={<Plus className="h-3.5 w-3.5" />} onClick={handleAddExperience} className="mt-1 font-semibold">
                {t('own.addExperience')}
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              {experiences.map((exp) => (
                <div key={exp.id} className="p-4 rounded-xl border border-gray-100 dark:border-white/[0.06] bg-gray-50/50 dark:bg-white/[0.02]">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-sm font-bold text-gray-900 dark:text-white">
                        {exp.title || t('own.untitledRole')}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                        {[exp.company, exp.period].filter(Boolean).join(' · ') || t('own.noDetails')}
                      </div>
                      {exp.description && (
                        <p className="text-xs text-gray-600 dark:text-gray-400 mt-2 whitespace-pre-wrap">{exp.description}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <Button variant="ghost" size="sm" className="h-7 px-2 text-gray-500" onClick={() => handleEditExperience(exp)}>
                        <Edit3 className="h-3.5 w-3.5" />
                      </Button>
                      <Button variant="ghost" size="sm" className="h-7 px-2 text-rose-500" onClick={() => handleDeleteExperience(exp.id)}>
                        <span className="text-lg leading-none">×</span>
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* Education Tab */}
      {activeTab === 'education' && (
        <Card className="p-6 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-bold text-gray-900 dark:text-white">{t('own.education')}</h3>
            <Button variant="primary" size="sm" leftIcon={<Plus className="h-3.5 w-3.5" />} onClick={handleAddEducation}>
              {t('own.addEducation')}
            </Button>
          </div>
          {education.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 text-center space-y-3">
              <GraduationCap className="h-10 w-10 text-gray-300 dark:text-gray-600" />
              <p className="text-sm text-gray-500 dark:text-gray-400">{t('own.noEducationHint')}</p>
              <Button variant="primary" size="sm" leftIcon={<Plus className="h-3.5 w-3.5" />} onClick={handleAddEducation} className="mt-1 font-semibold">
                {t('own.addEducation')}
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              {education.map((edu) => (
                <div key={edu.id} className="p-4 rounded-xl border border-gray-100 dark:border-white/[0.06] bg-gray-50/50 dark:bg-white/[0.02]">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-sm font-bold text-gray-900 dark:text-white">
                        {edu.degree || t('own.untitledDegree')}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                        {[edu.school, edu.year].filter(Boolean).join(' · ') || t('own.noDetails')}
                      </div>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <Button variant="ghost" size="sm" className="h-7 px-2 text-gray-500" onClick={() => handleEditEducation(edu)}>
                        <Edit3 className="h-3.5 w-3.5" />
                      </Button>
                      <Button variant="ghost" size="sm" className="h-7 px-2 text-rose-500" onClick={() => handleDeleteEducation(edu.id)}>
                        <span className="text-lg leading-none">×</span>
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* Skills Tab */}
      {activeTab === 'skills' && (
        <Card className="p-6 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-bold text-gray-900 dark:text-white">{t('own.allSkills')}</h3>
            <Button variant="primary" size="sm" leftIcon={<Plus className="h-3.5 w-3.5" />} onClick={() => setEditSkillsOpen(true)}>
              {t('own.addSkill')}
            </Button>
          </div>
          <div className="space-y-5 max-w-lg">
            {skills.map((skill) => (
              <div key={skill.name}>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300">{skill.name}</span>
                  <span className="text-sm font-bold text-violet-600 dark:text-violet-400">{skill.level}%</span>
                </div>
                <div className="h-2.5 rounded-full bg-gray-100 dark:bg-white/10 overflow-hidden">
                  <div className="h-full rounded-full bg-gradient-to-r from-violet-500 to-indigo-500" style={{ width: `${skill.level}%` }} />
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Assessments Tab */}
      {activeTab === 'assessments' && (
        <TabEmpty
          title={t('own.assessments')}
          description={t('own.assessmentsEmpty')}
          actionLabel={t('own.takeAssessment')}
          onAction={() => navigate('/cv-builder')}
          icon={<Mic className="h-8 w-8 text-violet-400" />}
        />
      )}

      {/* Activity Tab */}
      {activeTab === 'activity' && (
        <TabEmpty
          title={t('own.recentActivity')}
          description={t('own.activityEmpty')}
          actionLabel={t('candidate.jobs.browseTitle')}
          onAction={() => navigate('/jobs')}
        />
      )}

      {/* Qualifications Tab */}
      {activeTab === 'qualifications' && (
        <Card className="p-8 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
          <div className="flex flex-col items-center justify-center py-10 text-center space-y-4 max-w-sm mx-auto">
            <div className="h-16 w-16 rounded-2xl bg-violet-50 dark:bg-violet-500/10 flex items-center justify-center">
              <Shield className="h-8 w-8 text-violet-400" />
            </div>
            <h3 className="text-lg font-bold text-gray-900 dark:text-white">{t('own.proveQualifications')}</h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {t('own.uploadDocsVerify')}
            </p>
            <Button variant="primary" leftIcon={<Upload className="h-4 w-4" />} className="font-semibold" onClick={() => qualFileInputRef.current?.click()} disabled={qualificationUploading}>
              {qualificationUploading ? t('own.uploading') : t('own.uploadDocument')}
            </Button>
            <input
              ref={qualFileInputRef}
              type="file"
              accept=".pdf,.png,.jpg,.jpeg"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleQualificationUpload(file);
                e.target.value = '';
              }}
            />
          </div>
        </Card>
      )}

      {/* Edit About Dialog */}
      <Dialog open={editAboutOpen} onOpenChange={setEditAboutOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('own.editAbout')}</DialogTitle>
            <DialogDescription>{t('own.editAboutDesc')}</DialogDescription>
          </DialogHeader>
          <textarea
            className="w-full rounded-xl border border-violet-200/60 bg-white p-3 text-sm min-h-[120px] focus:outline-none focus:ring-2 focus:ring-violet-500/20 dark:border-white/10 dark:bg-white/5 dark:text-white"
            value={aboutText}
            onChange={(e) => setAboutText(e.target.value)}
          />
          <DialogFooter>
            <Button variant="ghost" onClick={() => setEditAboutOpen(false)}>{t('common.cancel')}</Button>
            <Button variant="primary" onClick={handleSaveAbout}>
              {t('common.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Skills Dialog */}
      <Dialog open={editSkillsOpen} onOpenChange={setEditSkillsOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('own.addSkill')}</DialogTitle>
            <DialogDescription>{t('own.addSkillDesc')}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 my-2">
            <Input label={t('own.skillName')} placeholder={t('own.skillNamePlaceholder')} value={newSkill} onChange={(e) => setNewSkill(e.target.value)} />
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                {t('own.proficiency')}: {newSkillLevel}%
              </label>
              <input
                type="range"
                min={10}
                max={100}
                value={newSkillLevel}
                onChange={(e) => setNewSkillLevel(Number(e.target.value))}
                className="w-full accent-violet-600"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setEditSkillsOpen(false)}>{t('common.cancel')}</Button>
            <Button variant="primary" onClick={handleAddSkill}>{t('own.addSkill')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Job Preferences Dialog */}
      <Dialog open={editPrefsOpen} onOpenChange={setEditPrefsOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('own.editJobPreferences')}</DialogTitle>
            <DialogDescription>{t('own.editJobPrefsDesc')}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 my-2">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('own.availability')}</label>
              <div className="flex flex-wrap gap-2">
                {['Immediately', '2 weeks', '1 month', '3+ months'].map((a) => (
                  <button
                    key={a}
                    onClick={() => setPrefAvailability(prefAvailability === a ? '' : a)}
                    className={cn(
                      'px-3 py-1.5 text-sm font-medium rounded-lg border transition-all',
                      prefAvailability === a
                        ? 'bg-violet-600 text-white border-violet-600'
                        : 'bg-white/50 dark:bg-white/[0.03] text-gray-600 dark:text-gray-400 border-gray-200 dark:border-white/10 hover:border-violet-400/60'
                    )}
                  >
                    {availabilityLabels[a] || a}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('own.workType')}</label>
              <div className="flex flex-wrap gap-2">
                {['Full-Time', 'Part-Time', 'Contract', 'Freelance', 'Internship', 'Remote'].map((wt) => (
                  <button
                    key={wt}
                    onClick={() => togglePrefWorkType(wt)}
                    className={cn(
                      'px-3 py-1.5 text-sm font-medium rounded-lg border transition-all',
                      prefWorkTypes.includes(wt)
                        ? 'bg-violet-600 text-white border-violet-600'
                        : 'bg-white/50 dark:bg-white/[0.03] text-gray-600 dark:text-gray-400 border-gray-200 dark:border-white/10 hover:border-violet-400/60'
                    )}
                  >
                    {workTypeLabels[wt] || wt}
                  </button>
                ))}
              </div>
            </div>
            <Input label={t('own.languages')} placeholder={t('own.languagesPlaceholder')} value={prefLanguages} onChange={(e) => setPrefLanguages(e.target.value)} />
            <div className="grid grid-cols-2 gap-4">
              <Input label={t('own.salaryMin')} placeholder={t('own.min')} type="number" value={prefSalaryMin} onChange={(e) => setPrefSalaryMin(e.target.value)} />
              <Input label={t('own.salaryMax')} placeholder={t('own.max')} type="number" value={prefSalaryMax} onChange={(e) => setPrefSalaryMax(e.target.value)} />
            </div>
            <label className="flex items-center gap-2.5 cursor-pointer select-none pt-1">
              <input
                type="checkbox"
                checked={prefRelocation}
                onChange={(e) => setPrefRelocation(e.target.checked)}
                className="h-4 w-4 rounded border-violet-300 text-violet-600 focus:ring-violet-500"
              />
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">{t('own.willingToRelocate')}</span>
            </label>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setEditPrefsOpen(false)}>{t('common.cancel')}</Button>
            <Button variant="primary" onClick={handleSavePrefs}>{t('common.save')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Experience Dialog */}
      <Dialog open={editExperienceOpen} onOpenChange={setEditExperienceOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{experiences.some(e => e.id === editingExperience?.id) ? t('own.editExperience') : t('own.addExperience')}</DialogTitle>
            <DialogDescription>{t('own.editExperienceDesc')}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 my-2">
            <Input label={t('own.jobTitle')} placeholder={t('own.jobTitlePlaceholder')} value={editingExperience?.title || ''} onChange={(e) => setEditingExperience((x: any) => ({ ...x, title: e.target.value }))} />
            <Input label={t('own.company')} placeholder={t('own.companyPlaceholder')} value={editingExperience?.company || ''} onChange={(e) => setEditingExperience((x: any) => ({ ...x, company: e.target.value }))} />
            <Input label={t('own.period')} placeholder={t('own.periodPlaceholder')} value={editingExperience?.period || ''} onChange={(e) => setEditingExperience((x: any) => ({ ...x, period: e.target.value }))} />
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">{t('common.description')}</label>
              <textarea
                className="flex min-h-[90px] w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 dark:border-white/10 dark:bg-white/5 dark:text-white dark:placeholder:text-gray-500"
                placeholder={t('own.responsibilitiesPlaceholder')}
                value={editingExperience?.description || ''}
                onChange={(e) => setEditingExperience((x: any) => ({ ...x, description: e.target.value }))}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setEditExperienceOpen(false)}>{t('common.cancel')}</Button>
            <Button variant="primary" onClick={handleSaveExperience}>{t('common.save')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Education Dialog */}
      <Dialog open={editEducationOpen} onOpenChange={setEditEducationOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{education.some(e => e.id === editingEducation?.id) ? t('own.editEducation') : t('own.addEducation')}</DialogTitle>
            <DialogDescription>{t('own.editEducationDesc')}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 my-2">
            <Input label={t('own.degree')} placeholder={t('own.degreePlaceholder')} value={editingEducation?.degree || ''} onChange={(e) => setEditingEducation((x: any) => ({ ...x, degree: e.target.value }))} />
            <Input label={t('own.school')} placeholder={t('own.schoolPlaceholder')} value={editingEducation?.school || ''} onChange={(e) => setEditingEducation((x: any) => ({ ...x, school: e.target.value }))} />
            <Input label={t('own.year')} placeholder={t('own.yearPlaceholder')} value={editingEducation?.year || ''} onChange={(e) => setEditingEducation((x: any) => ({ ...x, year: e.target.value }))} />
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setEditEducationOpen(false)}>{t('common.cancel')}</Button>
            <Button variant="primary" onClick={handleSaveEducation}>{t('common.save')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={qualDialogOpen} onOpenChange={setQualDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('own.uploadDocument')}</DialogTitle>
            <DialogDescription>{t('own.qualTitleDesc')}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 my-2">
            <Input label={t('own.documentTitle')} placeholder={t('own.documentTitlePlaceholder')} value={qualTitle} onChange={(e) => setQualTitle(e.target.value)} />
            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('own.category')}</label>
              <select
                value={qualCategory}
                onChange={(e) => setQualCategory(e.target.value)}
                className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm dark:border-white/10 dark:bg-white/5 dark:text-white"
              >
                <option value="degree">{t('own.qualDegree')}</option>
                <option value="certificate">{t('own.qualCertificate')}</option>
                <option value="transcript">{t('own.qualTranscript')}</option>
                <option value="license">{t('own.qualLicense')}</option>
                <option value="other">{t('sources.other')}</option>
              </select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setQualDialogOpen(false)}>{t('common.cancel')}</Button>
            <Button variant="primary" onClick={submitQualification} disabled={!qualTitle.trim() || qualTitle.trim().length < 3}>{t('common.upload')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function TabEmpty({
  title,
  description,
  actionLabel,
  onAction,
  icon,
}: {
  title: string;
  description: string;
  actionLabel: string;
  onAction: () => void;
  icon?: React.ReactNode;
}) {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
      <Card className="p-10 border-0 shadow-sm bg-white dark:bg-white/[0.03]">
        <div className="flex flex-col items-center justify-center py-8 text-center space-y-3 max-w-sm mx-auto">
          {icon && <div className="mb-2">{icon}</div>}
          <h3 className="text-lg font-bold text-gray-900 dark:text-white">{title}</h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">{description}</p>
          <Button variant="primary" size="sm" leftIcon={<Plus className="h-3.5 w-3.5" />} onClick={onAction} className="mt-2 font-semibold">
            {actionLabel}
          </Button>
        </div>
      </Card>
    </motion.div>
  );
}
