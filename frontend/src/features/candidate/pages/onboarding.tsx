import { useState } from 'react';
import { useNavigate } from 'react-router';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Progress } from '@/shared/components/ui/progress';
import { customToast } from '@/shared/components/ui/toast';
import { candidateService } from '@/services/candidate.service';
import { cn } from '@/utils/cn';
import { useLanguage } from '@/contexts/language-context';
import { User, Upload, FileText, CheckCircle2, ArrowRight, ArrowLeft, Briefcase, GraduationCap, Star, Sparkles, Save, Loader2 } from 'lucide-react';

const STEPS = ['Profile', 'CV Upload', 'Skills & Experience', 'Preferences'];
const JOB_TYPES = ['Full-Time', 'Part-Time', 'Contract', 'Freelance', 'Internship', 'Remote'];
const AVAILABILITY = ['Immediately', '2 weeks', '1 month', '3+ months'];

export default function OnboardingPage() {
  const navigate = useNavigate();
  const { t } = useLanguage();
  const [step, setStep] = useState(1);
  const [saving, setSaving] = useState(false);

  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [location, setLocation] = useState('');
  const [headline, setHeadline] = useState('');
  const [bio, setBio] = useState('');

  const [cvFile, setCvFile] = useState<File | null>(null);
  const [cvDragOver, setCvDragOver] = useState(false);

  const [skillInput, setSkillInput] = useState('');
  const [skills, setSkills] = useState<string[]>([]);
  const [experience, setExperience] = useState('');

  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
  const [prefLocation, setPrefLocation] = useState('');
  const [salaryMin, setSalaryMin] = useState('');
  const [salaryMax, setSalaryMax] = useState('');
  const [availability, setAvailability] = useState('');
  const [relocationWilling, setRelocationWilling] = useState(false);

  const progress = (step / STEPS.length) * 100;

  const addSkill = () => {
    const s = skillInput.trim();
    if (s && !skills.includes(s)) {
      setSkills([...skills, s]);
      setSkillInput('');
    }
  };

  const removeSkill = (s: string) => setSkills(skills.filter(x => x !== s));

  const toggleJobType = (t: string) => {
    setSelectedTypes(prev => prev.includes(t) ? prev.filter(x => x !== t) : [...prev, t]);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setCvDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file && (file.type === 'application/pdf' || file.name.endsWith('.doc') || file.name.endsWith('.docx'))) {
      setCvFile(file);
    }
  };

  const handleNext = async () => {
    setSaving(true);
    try {
      const profileData: Record<string, any> = {};
      if (step === 1) {
        profileData.name = name;
        profileData.phone = phone;
        profileData.location = location;
        profileData.headline = headline;
        profileData.bio = bio;
      } else if (step === 3) {
        profileData.skills = skills.join(', ');
        profileData.experience = experience;
      } else if (step === 4) {
        profileData.work_preference = selectedTypes.join(', ');
        profileData.preferred_location = prefLocation;
        profileData.salary_expectation_min = salaryMin ? parseInt(salaryMin) : null;
        profileData.salary_expectation_max = salaryMax ? parseInt(salaryMax) : null;
        if (availability) profileData.availability = availability;
        profileData.relocation_willing = relocationWilling;
      }
      if (Object.keys(profileData).length > 0) {
        await candidateService.updateProfile(profileData);
      }
      setStep(step + 1);
    } catch {
      customToast({ type: 'error', title: t('onboarding.errorTitle'), message: t('onboarding.saveFailedMsg') });
    } finally {
      setSaving(false);
    }
  };

  const handlePrev = () => {
    if (step > 1) setStep(step - 1);
  };

  const handleComplete = async () => {
    setSaving(true);
    try {
      if (cvFile) {
        const formData = new FormData();
        formData.append('file', cvFile);
        await candidateService.uploadCv(formData);
      }
      await candidateService.updateProfile({
        skills: skills.join(', '),
        experience,
        work_preference: selectedTypes.join(', '),
        preferred_location: prefLocation,
        salary_expectation_min: salaryMin ? parseInt(salaryMin) : null,
        salary_expectation_max: salaryMax ? parseInt(salaryMax) : null,
        ...(availability ? { availability } : {}),
        relocation_willing: relocationWilling,
      });
      customToast({ type: 'success', title: t('onboarding.completeTitle'), message: t('onboarding.completeMsg') });
      navigate('/dashboard');
    } catch {
      customToast({ type: 'error', title: t('onboarding.errorTitle'), message: t('onboarding.completeFailedMsg') });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white flex items-center gap-2">
          <Sparkles className="h-6 w-6 text-purple-500" />
          {t('onboarding.title')}
        </h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{t('onboarding.subtitle')}</p>
      </div>

      <div className="space-y-2">
        <Progress value={progress} size="lg" showLabel />
        <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400">
          {STEPS.map((label, idx) => (
            <span key={label} className={cn('font-medium transition-colors', idx + 1 <= step ? 'text-purple-600 dark:text-purple-400' : '')}>
              {label}
            </span>
          ))}
        </div>
      </div>

      <motion.div
        key={step}
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.25 }}
      >
        <Card className="p-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {step === 1 && <User className="h-5 w-5 text-purple-500" />}
              {step === 2 && <Upload className="h-5 w-5 text-purple-500" />}
              {step === 3 && <Star className="h-5 w-5 text-purple-500" />}
              {step === 4 && <Briefcase className="h-5 w-5 text-purple-500" />}
              Step {step}/{STEPS.length} — {STEPS[step - 1]}
            </CardTitle>
            <CardDescription>
              {step === 1 && t('onboarding.step1Desc')}
              {step === 2 && t('onboarding.step2Desc')}
              {step === 3 && t('onboarding.step3Desc')}
              {step === 4 && t('onboarding.step4Desc')}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {step === 1 && (
              <>
                <Input label={t('onboarding.fullName')} placeholder={t('onboarding.fullNamePlaceholder')} value={name} onChange={(e) => setName(e.target.value)} leftIcon={<User className="h-4 w-4" />} />
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <Input label={t('onboarding.phone')} placeholder="+216 XX XXX XXX" value={phone} onChange={(e) => setPhone(e.target.value)} />
                  <Input label={t('onboarding.location')} placeholder={t('onboarding.locationPlaceholder')} value={location} onChange={(e) => setLocation(e.target.value)} leftIcon={<GraduationCap className="h-4 w-4" />} />
                </div>
                <Input label={t('onboarding.headline')} placeholder={t('onboarding.headlinePlaceholder')} value={headline} onChange={(e) => setHeadline(e.target.value)} />
                <div className="space-y-1.5">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('onboarding.bio')}</label>
                  <textarea
                    placeholder={t('onboarding.bioPlaceholder')}
                    value={bio}
                    onChange={(e) => setBio(e.target.value)}
                    rows={4}
                    className="w-full rounded-lg border border-purple-200/60 bg-white/70 backdrop-blur-sm px-3 py-2 text-sm placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 dark:border-purple-500/20 dark:bg-white/5 dark:text-white dark:placeholder:text-gray-500 transition-colors"
                  />
                </div>
              </>
            )}

            {step === 2 && (
              <>
                <div
                  onDragOver={(e) => { e.preventDefault(); setCvDragOver(true); }}
                  onDragLeave={() => setCvDragOver(false)}
                  onDrop={handleDrop}
                  className={cn(
                    'border-2 border-dashed rounded-xl p-10 text-center transition-all cursor-pointer',
                    cvDragOver ? 'border-purple-500 bg-purple-50/60 dark:bg-purple-500/10' : 'border-purple-200/60 dark:border-purple-500/20 hover:border-purple-400/60 dark:hover:border-purple-400/30'
                  )}
                  onClick={() => document.getElementById('cv-input')?.click()}
                >
                  <input
                    id="cv-input"
                    type="file"
                    accept=".pdf,.doc,.docx"
                    className="hidden"
                    onChange={(e) => { const f = e.target.files?.[0]; if (f) setCvFile(f); }}
                  />
                  <Upload className="h-10 w-10 text-purple-400 mx-auto mb-3" />
                  <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    {cvFile ? cvFile.name : t('onboarding.dropCvHere')}
                  </p>
                  <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                    {t('onboarding.cvFormats')}
                  </p>
                  {cvFile && (
                    <div className="mt-4 inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 text-sm font-medium">
                      <FileText className="h-4 w-4" />
                      {cvFile.name}
                      <CheckCircle2 className="h-4 w-4" />
                    </div>
                  )}
                </div>
                <p className="text-center text-xs text-gray-400 dark:text-gray-500">{t('onboarding.cvLaterHint')}</p>
              </>
            )}

            {step === 3 && (
              <>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">{t('onboarding.skills')}</label>
                  <div className="flex gap-2 mb-2">
                    <Input
                      placeholder={t('onboarding.skillsPlaceholder')}
                      value={skillInput}
                      onChange={(e) => setSkillInput(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addSkill(); } }}
                      wrapperClassName="flex-1"
                    />
                    <Button variant="outline" size="sm" onClick={addSkill} className="shrink-0">{t('onboarding.add')}</Button>
                  </div>
                  <div className="flex flex-wrap gap-2 min-h-[40px]">
                    {skills.map((s) => (
                      <Badge key={s} variant="primary" size="md" className="cursor-pointer hover:bg-red-50 dark:hover:bg-red-500/10" onClick={() => removeSkill(s)}>
                        {s} ✕
                      </Badge>
                    ))}
                  </div>
                </div>
                <div className="space-y-1.5">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('onboarding.experienceSummary')}</label>
                  <textarea
                    placeholder={t('onboarding.experiencePlaceholder')}
                    value={experience}
                    onChange={(e) => setExperience(e.target.value)}
                    rows={5}
                    className="w-full rounded-lg border border-purple-200/60 bg-white/70 backdrop-blur-sm px-3 py-2 text-sm placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 dark:border-purple-500/20 dark:bg-white/5 dark:text-white dark:placeholder:text-gray-500 transition-colors"
                  />
                </div>
              </>
            )}

            {step === 4 && (
              <>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('onboarding.preferredJobTypes')}</label>
                  <div className="flex flex-wrap gap-2">
                    {JOB_TYPES.map((t) => (
                      <button
                        key={t}
                        onClick={() => toggleJobType(t)}
                        className={cn(
                          'px-3 py-1.5 text-sm font-medium rounded-lg border transition-all',
                          selectedTypes.includes(t)
                            ? 'bg-purple-600 text-white border-purple-600 shadow-sm shadow-purple-500/25'
                            : 'bg-white/50 dark:bg-white/[0.03] text-gray-600 dark:text-gray-400 border-purple-200/50 dark:border-purple-500/20 hover:border-purple-400/60'
                        )}
                      >
                        {t}
                      </button>
                    ))}
                  </div>
                </div>
                <Input label={t('onboarding.preferredLocation')} placeholder={t('onboarding.preferredLocationPlaceholder')} value={prefLocation} onChange={(e) => setPrefLocation(e.target.value)} leftIcon={<Briefcase className="h-4 w-4" />} />
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{t('onboarding.availability')}</label>
                  <div className="flex flex-wrap gap-2">
                    {AVAILABILITY.map((a) => (
                      <button
                        key={a}
                        onClick={() => setAvailability(availability === a ? '' : a)}
                        className={cn(
                          'px-3 py-1.5 text-sm font-medium rounded-lg border transition-all',
                          availability === a
                            ? 'bg-purple-600 text-white border-purple-600 shadow-sm shadow-purple-500/25'
                            : 'bg-white/50 dark:bg-white/[0.03] text-gray-600 dark:text-gray-400 border-purple-200/50 dark:border-purple-500/20 hover:border-purple-400/60'
                        )}
                      >
                        {a}
                      </button>
                    ))}
                  </div>
                </div>
                <label className="flex items-center gap-2.5 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={relocationWilling}
                    onChange={(e) => setRelocationWilling(e.target.checked)}
                    className="h-4 w-4 rounded border-purple-300 text-purple-600 focus:ring-purple-500"
                  />
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300">{t('onboarding.willingToRelocate')}</span>
                </label>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">{t('onboarding.salaryRange')}</label>
                  <div className="grid grid-cols-2 gap-4">
                    <Input placeholder={t('onboarding.min')} value={salaryMin} onChange={(e) => setSalaryMin(e.target.value)} />
                    <Input placeholder={t('onboarding.max')} value={salaryMax} onChange={(e) => setSalaryMax(e.target.value)} />
                  </div>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </motion.div>

      <div className="flex items-center justify-between">
        <Button variant="ghost" size="md" onClick={handlePrev} disabled={step === 1 || saving} leftIcon={<ArrowLeft className="h-4 w-4" />}>
          {t('onboarding.previous')}
        </Button>
        {step < STEPS.length ? (
          <Button variant="primary" size="md" onClick={handleNext} disabled={saving} rightIcon={saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}>
            {saving ? t('onboarding.saving') : t('onboarding.next')}
          </Button>
        ) : (
          <Button variant="primary" size="md" onClick={handleComplete} disabled={saving} leftIcon={saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}>
            {saving ? t('onboarding.saving') : t('onboarding.saveGoDashboard')}
          </Button>
        )}
      </div>
    </div>
  );
}