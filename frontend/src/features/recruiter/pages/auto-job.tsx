import { useState } from 'react';
import { useNavigate } from 'react-router';
import { motion, AnimatePresence } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { customToast } from '@/shared/components/ui/toast';
import { useLanguage } from '@/contexts/language-context';
import { cn } from '@/utils/cn';
import { Zap, FileText, Settings, CheckCircle2, Upload, Wand2, Sparkles, Loader2 } from 'lucide-react';
import { autoJobService } from '@/services/auto-job.service';

const generationSteps = [
  { id: 'analyze', label: 'Analyzing Company Profile', icon: FileText },
  { id: 'generate', label: 'Generating Job Description', icon: Zap },
  { id: 'requirements', label: 'Setting Requirements', icon: Settings },
  { id: 'questions', label: 'Creating Interview Questions', icon: Wand2 },
];

export default function AutoJobPage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [inputMode, setInputMode] = useState<'upload' | 'textarea'>('textarea');
  const [jobTitle, setJobTitle] = useState('');
  const [skillsInput, setSkillsInput] = useState('');
  const [companyText, setCompanyText] = useState('');
  const [fileName, setFileName] = useState('');
  const [generating, setGenerating] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [generated, setGenerated] = useState(false);
  const [createdJob, setCreatedJob] = useState<{ jobId: number; jobTitle: string; questionsCount: number } | null>(null);

  const handleUpload = () => {
    document.getElementById('doc-upload')?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setFileName(file.name);
      customToast({ type: 'success', title: t('common.status'), message: `${file.name} added.` });
    }
  };

  const handleGenerate = async () => {
    const title = jobTitle.trim();
    if (!title) {
      customToast({ type: 'warning', title: t('common.status'), message: 'Enter a job title.' });
      return;
    }
    if (inputMode === 'textarea' && !companyText.trim()) {
      customToast({ type: 'warning', title: t('common.status'), message: 'Provide company description.' });
      return;
    }
    if (inputMode === 'upload' && !fileName) {
      customToast({ type: 'warning', title: t('common.status'), message: 'Upload a document.' });
      return;
    }

    setGenerating(true);
    setCurrentStep(0);
    setGenerated(false);
    setCreatedJob(null);

    try {
      const res: any = await autoJobService.create({
        title,
        skills: skillsInput.split(',').map(s => s.trim()).filter(Boolean),
        seniority: 'mid',
        company: inputMode === 'textarea' ? companyText : fileName,
        location: '',
        type: 'Full-time',
      });

      if (res && res.job_id) {
        setCreatedJob({ jobId: res.job_id, jobTitle: res.job_title || title, questionsCount: res.questions_count ?? 0 });
        setGenerated(true);
        setCurrentStep(generationSteps.length);
        customToast({ type: 'success', title: t('common.status'), message: 'Job created successfully.' });
      } else {
        customToast({ type: 'error', title: t('common.status'), message: 'Failed to create job.' });
      }
    } catch (err: any) {
      const message = err?.response?.data?.detail || err?.message || 'Failed to generate job.';
      customToast({ type: 'error', title: t('common.status'), message });
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Zap className="h-5 w-5 text-purple-600" />
            <span className="text-xs font-extrabold uppercase tracking-wider text-purple-600">AI</span>
          </div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">{t('jobs.autoJob')}</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{t('jobs.subtitle')}</p>
        </div>
        <Badge variant="primary" size="lg" className="gap-1.5">
          <Sparkles className="h-3.5 w-3.5" />
          AI
        </Badge>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        <div className="lg:col-span-3 space-y-6">
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            <Card className="glass-panel border-purple-200/60 dark:border-purple-500/20">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg font-extrabold text-gray-900 dark:text-white">
                  <Upload className="h-5 w-5 text-purple-600" />
                  {t('jobs.title')}
                </CardTitle>
                <CardDescription>{t('common.description')}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs font-extrabold uppercase tracking-wider text-gray-400 mb-1.5">{t('jobs.col.jobTitle')} *</label>
                    <input
                      value={jobTitle}
                      onChange={(e) => setJobTitle(e.target.value)}
                      placeholder="e.g. Senior Frontend Engineer"
                      className="w-full rounded-xl border border-purple-200/60 dark:border-white/10 bg-white/70 dark:bg-white/5 px-4 py-2.5 text-sm focus:ring-2 focus:ring-purple-500/20 dark:text-white placeholder:text-gray-400"
                      disabled={generating}
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-extrabold uppercase tracking-wider text-gray-400 mb-1.5">{t('cprofile.skillsCompetencies')}</label>
                    <input
                      value={skillsInput}
                      onChange={(e) => setSkillsInput(e.target.value)}
                      placeholder="e.g. React, TypeScript, Node.js"
                      className="w-full rounded-xl border border-purple-200/60 dark:border-white/10 bg-white/70 dark:bg-white/5 px-4 py-2.5 text-sm focus:ring-2 focus:ring-purple-500/20 dark:text-white placeholder:text-gray-400"
                      disabled={generating}
                    />
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    variant={inputMode === 'textarea' ? 'primary' : 'outline'}
                    size="sm"
                    leftIcon={<FileText className="h-4 w-4" />}
                    onClick={() => setInputMode('textarea')}
                    className="font-bold"
                  >
                    {t('common.edit')}
                  </Button>
                  <Button
                    variant={inputMode === 'upload' ? 'primary' : 'outline'}
                    size="sm"
                    leftIcon={<Upload className="h-4 w-4" />}
                    onClick={() => setInputMode('upload')}
                    className="font-bold"
                  >
                    {t('common.upload')}
                  </Button>
                </div>

                {inputMode === 'textarea' ? (
                  <textarea
                    value={companyText}
                    onChange={(e) => setCompanyText(e.target.value)}
                    placeholder={t('common.description')}
                    className="w-full min-h-[200px] rounded-xl border border-purple-200/60 dark:border-white/10 bg-white/70 dark:bg-white/5 p-4 text-sm focus:ring-2 focus:ring-purple-500/20 dark:text-white resize-none placeholder:text-gray-400"
                    disabled={generating}
                  />
                ) : (
                  <div
                    onClick={handleUpload}
                    className="flex flex-col items-center justify-center min-h-[200px] rounded-xl border-2 border-dashed border-purple-200 dark:border-purple-500/30 bg-white/40 dark:bg-white/5 cursor-pointer hover:border-purple-400 dark:hover:border-purple-400 transition-colors"
                  >
                    <Upload className="h-10 w-10 text-purple-400 mb-3" />
                    <p className="text-sm font-bold text-gray-700 dark:text-gray-300">{t('common.upload')}</p>
                    <input
                      id="doc-upload"
                      type="file"
                      accept=".pdf,.docx,.doc,.txt"
                      className="hidden"
                      onChange={handleFileChange}
                    />
                    {fileName && (
                      <Badge variant="primary" size="sm" className="mt-3">
                        <FileText className="h-3 w-3 mr-1" />
                        {fileName}
                      </Badge>
                    )}
                  </div>
                )}

                <Button
                  variant="primary"
                  size="lg"
                  leftIcon={generating ? <Loader2 className="h-5 w-5 animate-spin" /> : <Wand2 className="h-5 w-5" />}
                  onClick={handleGenerate}
                  disabled={generating}
                  className="w-full font-bold shadow-lg shadow-purple-500/25"
                >
                  {generating ? '...' : t('jobs.newJob')}
                </Button>
              </CardContent>
            </Card>
          </motion.div>

          <AnimatePresence>
            {(generating || generated) && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}>
                <Card className="glass-panel border-purple-200/60 dark:border-purple-500/20">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-lg font-extrabold text-gray-900 dark:text-white">
                      <Settings className="h-5 w-5 text-purple-600" />
                      {t('common.status')}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {generationSteps.map((step, i) => {
                      const StepIcon = step.icon;
                      const isActive = generating && currentStep === i;
                      const isDone = currentStep > i;

                      return (
                        <div key={step.id} className="flex items-center gap-4">
                          <div className={cn(
                            "h-10 w-10 rounded-xl flex items-center justify-center shrink-0 transition-all",
                            isDone ? "bg-emerald-100 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400" :
                            isActive ? "bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 ring-2 ring-purple-500/30" :
                            "bg-gray-100 dark:bg-gray-800 text-gray-400"
                          )}>
                            {isDone ? (
                              <CheckCircle2 className="h-5 w-5" />
                            ) : (
                              <StepIcon className="h-5 w-5" />
                            )}
                          </div>
                          <div className="flex-1">
                            <p className={cn(
                              "text-sm font-bold",
                              isDone ? "text-emerald-600 dark:text-emerald-400" :
                              isActive ? "text-purple-600 dark:text-purple-400" :
                              "text-gray-400"
                            )}>
                              {step.label}
                            </p>
                          </div>
                          {isDone && (
                            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                          )}
                        </div>
                      );
                    })}
                  </CardContent>
                </Card>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <div className="lg:col-span-2">
          <AnimatePresence>
            {generated && createdJob && (
              <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }}>
                <Card className="glass-panel border-purple-200/60 dark:border-purple-500/20 h-full">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-lg font-extrabold text-gray-900 dark:text-white">
                      <CheckCircle2 className="h-5 w-5 text-emerald-500" />
                      {t('jobs.title')}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-5">
                    <div className="p-4 rounded-xl bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-500/30">
                      <p className="text-xs font-extrabold uppercase tracking-wider text-gray-400 mb-1">{t('jobs.col.jobTitle')}</p>
                      <h3 className="text-xl font-extrabold text-gray-900 dark:text-white">{createdJob.jobTitle}</h3>
                      <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 mt-2">
                        #{createdJob.jobId} · {createdJob.questionsCount} questions
                      </p>
                    </div>

                    <Button
                      variant="primary"
                      size="lg"
                      leftIcon={<Zap className="h-5 w-5" />}
                      onClick={() => navigate('/jobs')}
                      className="w-full font-bold shadow-lg shadow-purple-500/25"
                    >
                      {t('nav.jobs')}
                    </Button>
                  </CardContent>
                </Card>
              </motion.div>
            )}
          </AnimatePresence>

          {!generated && (
            <Card className="glass-panel border-purple-200/60 dark:border-purple-500/20 h-full">
              <CardContent className="flex items-center justify-center h-full min-h-[300px]">
                <div className="text-center">
                  <Wand2 className="h-12 w-12 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
                  <p className="text-sm font-bold text-gray-400">{t('common.noData')}</p>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
