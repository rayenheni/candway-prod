import { useState, useEffect, useCallback, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Badge } from '@/shared/components/ui/badge';
import { Progress } from '@/shared/components/ui/progress';
import { customToast } from '@/shared/components/ui/toast';
import { candidateService } from '@/services/candidate.service';
import { useLanguage } from '@/contexts/language-context';
import {
  FileText, Download, Sparkles, Plus, Trash2, Save, Loader2,
} from 'lucide-react';

interface ExperienceItem {
  id: string; title: string; company: string; period: string; description: string;
}
interface EducationItem {
  id: string; degree: string; school: string; year: string;
}
interface BuilderData {
  summary?: string; skills?: string[]; experience?: ExperienceItem[]; education?: EducationItem[];
  name?: string; role?: string; email?: string; phone?: string; location?: string;
}

function calculateScore(data: BuilderData): number {
  let s = 0;
  if (data.name && data.role && data.email) s += 10;
  if ((data.summary?.length || 0) > 30) s += 10;
  else if ((data.summary?.length || 0) > 10) s += 5;
  const skillCount = data.skills?.length || 0;
  s += Math.min(skillCount * 3, 20);
  const expCount = data.experience?.length || 0;
  s += Math.min(expCount * 8, 24);
  if (data.experience?.some(e => /\d+/.test(e.description))) s += 6;
  const eduCount = data.education?.length || 0;
  s += Math.min(eduCount * 5, 15);
  if (data.location) s += 5;
  const total = Math.min(Math.round(s + (data.experience?.length || 0) > 0 ? 10 : 0), 100);
  return Math.max(total, 5);
}

function getScoreLabel(score: number) {
  if (score >= 85) return { label: 'Excellent', color: 'text-emerald-400' };
  if (score >= 70) return { label: 'Strong', color: 'text-blue-400' };
  if (score >= 50) return { label: 'Needs Work', color: 'text-amber-400' };
  return { label: 'Incomplete', color: 'text-red-400' };
}

export default function CVBuilderPage() {
  const { t } = useLanguage();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [optimizing, setOptimizing] = useState(false);
  const [dirty, setDirty] = useState(false);

  const [name, setName] = useState('');
  const [role, setRole] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [location, setLocation] = useState('');
  const [summary, setSummary] = useState('');
  const [skills, setSkills] = useState<string[]>([]);
  const [newSkill, setNewSkill] = useState('');
  const [experiences, setExperiences] = useState<ExperienceItem[]>([]);
  const [education, setEducation] = useState<EducationItem[]>([]);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const markDirty = useCallback(() => setDirty(true), []);

  const toBuilderData = useCallback((): BuilderData => ({
    name, role, email, phone, location, summary, skills,
    experience: experiences,
    education,
  }), [name, role, email, phone, location, summary, skills, experiences, education]);

  const score = calculateScore(toBuilderData());
  const { label: scoreLabel, color: scoreColor } = getScoreLabel(score);

  // Load from backend
  useEffect(() => {
    candidateService.getCvData()
      .then(res => {
        if (res.found && res.data) {
          const d = res.data;
          setName(d.name || ''); setRole(d.role || '');
          setEmail(d.email || ''); setPhone(d.phone || '');
          setLocation(d.location || ''); setSummary(d.summary || '');
          const rawSkills = d.skills;
          if (Array.isArray(rawSkills)) setSkills(rawSkills);
          else if (typeof rawSkills === 'string') setSkills(rawSkills.split(',').map((s: string) => s.trim()).filter(Boolean));
          if (Array.isArray(d.experience)) setExperiences(d.experience.map((e: any) => ({ ...e, id: e.id || `exp_${Date.now()}_${Math.random()}` })));
          if (Array.isArray(d.education)) setEducation(d.education.map((e: any) => ({ ...e, id: e.id || `edu_${Date.now()}_${Math.random()}` })));
        }
      })
      .catch(() => customToast({ type: 'error', title: t('cv.builder.loadFailed'), message: t('cv.builder.loadFailedMsg') }))
      .finally(() => setLoading(false));
  }, []);

  // Auto-save with debounce
  useEffect(() => {
    if (!dirty || loading) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      const sections: Record<string, any> = {};
      const d = toBuilderData();
      if (d.name || d.role || d.email || d.phone || d.location) sections.personal_info = { name: d.name, role: d.role, email: d.email, phone: d.phone, location: d.location };
      sections.summary = d.summary;
      sections.skills = d.skills;
      sections.experience = d.experience;
      sections.education = d.education;
      setSaving(true);
      Promise.all([
        candidateService.saveBuilderData(sections),
        candidateService.updateProfile({
          name: d.name, headline: d.role, phone: d.phone, location: d.location,
        }),
      ]).then(() => {
        setDirty(false);
      }).catch(() => customToast({ type: 'error', title: t('cv.builder.saveFailed'), message: t('cv.builder.saveFailedMsg') }))
        .finally(() => setSaving(false));
    }, 1500);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [dirty, loading, toBuilderData]);

  const saveNow = () => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    setDirty(true);
    const sections: Record<string, any> = {};
    const d = toBuilderData();
    if (d.name || d.role || d.email || d.phone || d.location) sections.personal_info = { name: d.name, role: d.role, email: d.email, phone: d.phone, location: d.location };
    sections.summary = d.summary;
    sections.skills = d.skills;
    sections.experience = d.experience;
    sections.education = d.education;
    setSaving(true);
    Promise.all([
      candidateService.saveBuilderData(sections),
      // Sync personal info to user profile (name→User, role→headline, phone, location)
      candidateService.updateProfile({
        name: d.name,
        headline: d.role,
        phone: d.phone,
        location: d.location,
      }),
    ]).then(() => {
      setDirty(false);
      customToast({ type: 'success', title: t('cv.builder.saved'), message: t('cv.builder.savedMsg') });
    }).catch(() => customToast({ type: 'error', title: t('cv.builder.saveFailed'), message: t('cv.builder.saveFailedMsg') }))
      .finally(() => setSaving(false));
  };

  const handleAiOptimize = async () => {
    setOptimizing(true);
    try {
      const resp = await candidateService.getCvReview(true);
      if (resp.improved_summary) {
        setSummary(resp.improved_summary);
        markDirty();
        customToast({ type: 'success', title: t('cv.builder.aiPolishComplete'), message: t('cv.builder.aiPolishMsg') });
      } else {
        customToast({ type: 'info', title: t('cv.builder.aiReview'), message: resp.feedback || resp.summary || t('cv.builder.suggestionsGenerated') });
      }
    } catch (e: any) {
      customToast({ type: 'error', title: t('cv.builder.aiUnavailable'), message: e?.message || t('cv.builder.aiUnavailableMsg') });
    }
    setOptimizing(false);
  };

  const handleExportPDF = () => {
    const contactLine = [email, phone, location].filter(Boolean).join(' · ');
    const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    const html = `<!doctype html>
<html>
<head><meta charset="utf-8"><title>${esc(name || 'CV')}</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', Arial, sans-serif; color: #111; background: #fff; padding: 40px 48px; max-width: 210mm; margin: 0 auto; }
  h1 { font-size: 22px; margin-bottom: 2px; }
  .role { color: #2563eb; font-size: 13px; font-weight: 600; margin-bottom: 6px; }
  .contact { color: #555; font-size: 11px; margin-bottom: 16px; }
  h3 { font-size: 10px; text-transform: uppercase; letter-spacing: .08em; color: #6b7280; border-bottom: 1px solid #e5e7eb; padding-bottom: 3px; margin: 14px 0 6px; }
  p, li { font-size: 12px; line-height: 1.5; color: #333; }
  .skills { display: flex; flex-wrap: wrap; gap: 4px; }
  .skill { font-size: 10px; background: #f3f4f6; padding: 2px 7px; border-radius: 999px; color: #333; }
  .exp, .edu { margin-bottom: 6px; }
  .exp .top, .edu .top { display: flex; justify-content: space-between; font-size: 12px; font-weight: 600; }
  .exp .company, .edu .school { font-weight: 400; color: #555; }
  .period, .year { font-size: 10px; color: #777; font-weight: 400; }
  .desc { font-size: 11px; color: #444; margin-top: 2px; }
  @media print { body { padding: 0; } }
</style></head>
<body>
  <h1>${esc(name || t('cv.builder.yourName'))}</h1>
  <div class="role">${esc(role || t('cv.builder.professionalTitle'))}</div>
  ${contactLine ? `<div class="contact">${esc(contactLine)}</div>` : ''}
  ${summary ? `<h3>${esc(t('cv.builder.profSummary'))}</h3><p>${esc(summary)}</p>` : ''}
  ${skills.length ? `<h3>${esc(t('cv.builder.coreCompetencies'))}</h3><div class="skills">${skills.map((s: string) => `<span class="skill">${esc(s)}</span>`).join('')}</div>` : ''}
  ${experiences.length ? `<h3>${esc(t('cv.builder.profExperience'))}</h3>${experiences.filter((e: any) => e.title || e.company).map((e: any) =>
    `<div class="exp"><div class="top"><span>${esc(e.title || t('cv.builder.untitled'))}${e.company ? ` <span class="company">${esc(t('cv.builder.at'))} ${esc(e.company)}</span>` : ''}</span>${e.period ? `<span class="period">${esc(e.period)}</span>` : ''}</div>${e.description ? `<div class="desc">${esc(e.description)}</div>` : ''}</div>`).join('')}` : ''}
  ${education.length ? `<h3>${esc(t('own.education'))}</h3>${education.filter((e: any) => e.degree || e.school).map((e: any) =>
    `<div class="edu"><div class="top"><span>${esc(e.degree || t('cv.builder.degree'))}${e.school ? ` <span class="school">&mdash; ${esc(e.school)}</span>` : ''}</span>${e.year ? `<span class="year">${esc(e.year)}</span>` : ''}</div></div>`).join('')}` : ''}
  <script>window.onload = function(){ setTimeout(function(){ window.focus(); window.print(); }, 150); };<\/script>
</body>
</html>`;
    const win = window.open('', '_blank', 'width=850,height=1100');
    if (!win) {
      customToast({ type: 'error', title: t('cv.builder.exportBlocked'), message: t('cv.builder.exportBlockedMsg') });
      return;
    }
    win.document.write(html);
    win.document.close();
  };

  const addSkill = () => {
    if (newSkill.trim() && !skills.includes(newSkill.trim())) {
      setSkills([...skills, newSkill.trim()]);
      setNewSkill('');
      markDirty();
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="flex flex-col items-center gap-3 text-gray-500">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
          <span className="text-sm font-medium">{t('cv.builder.loading')}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Badge variant="primary" className="bg-blue-600 text-white dark:bg-blue-500">{t('cv.builder.interactiveModule')}</Badge>
            <span className="text-sm font-semibold text-gray-700 dark:text-gray-300">{t('cv.builder.studio')}</span>
          </div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{t('cv.builder.title')}</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">{t('cv.builder.subtitle')}</p>
        </div>
        <div className="flex items-center gap-2">
          {saving && <span className="text-xs text-gray-400 flex items-center gap-1"><Loader2 className="h-3 w-3 animate-spin" /> {t('cv.builder.saving')}</span>}
          {dirty && !saving && <span className="text-xs text-amber-500">{t('cv.builder.unsavedChanges')}</span>}
          <Button variant="outline" onClick={handleAiOptimize} loading={optimizing} leftIcon={<Sparkles className="h-4 w-4 text-amber-500" />}
            className="border-amber-200 bg-amber-50/50 hover:bg-amber-100/60 text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300">
            {t('cv.builder.aiOptimize')}
          </Button>
          <Button variant="primary" onClick={saveNow} loading={saving} leftIcon={<Save className="h-4 w-4" />}>{t('common.save')}</Button>
          <Button variant="outline" onClick={handleExportPDF} leftIcon={<Download className="h-4 w-4" />}>PDF</Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Editor */}
        <div className="lg:col-span-7 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>{t('cv.builder.personalInfo')}</CardTitle>
              <CardDescription>{t('cv.builder.personalInfoDesc')}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Input label={t('recruiter.bgCheckDetail.fullName')} value={name} onChange={e => { setName(e.target.value); markDirty(); }} />
                <Input label={t('cv.builder.professionalTitle')} value={role} onChange={e => { setRole(e.target.value); markDirty(); }} />
                <Input label={t('cv.builder.emailAddress')} value={email} onChange={e => { setEmail(e.target.value); markDirty(); }} />
                <Input label={t('cv.builder.phoneNumber')} value={phone} onChange={e => { setPhone(e.target.value); markDirty(); }} />
                <Input label={t('common.location')} value={location} onChange={e => { setLocation(e.target.value); markDirty(); }} />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>{t('cv.builder.execSummary')}</CardTitle>
                  <CardDescription>{t('cv.builder.execSummaryDesc')}</CardDescription>
                </div>
                <Button variant="ghost" size="xs" onClick={handleAiOptimize} className="text-amber-600 dark:text-amber-400 font-medium">
                  <Sparkles className="h-3.5 w-3.5 mr-1" /> {t('cv.builder.polish')}
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <textarea rows={4} value={summary} onChange={e => { setSummary(e.target.value); markDirty(); }}
                className="w-full rounded-lg border border-gray-200 bg-white p-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 dark:border-white/10 dark:bg-white/5 dark:text-white resize-y" />
              <p className="text-xs text-gray-400 mt-1">{summary.split(/\s+/).filter(Boolean).length} {t('recruiter.jdEditor.words')}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t('cv.builder.skillsCompetencies')}</CardTitle>
              <CardDescription>{t('cv.builder.skillsDesc')}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex gap-2 mb-4">
                <Input placeholder={t('cv.builder.addSkillPlaceholder')} value={newSkill} onChange={e => setNewSkill(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && addSkill()} wrapperClassName="flex-1" />
                <Button variant="outline" onClick={addSkill} leftIcon={<Plus className="h-4 w-4" />}>{t('common.add')}</Button>
              </div>
              <div className="flex flex-wrap gap-2">
                {skills.map(s => (
                  <Badge key={s} variant="primary" size="lg"
                    className="pl-3 pr-2 py-1 flex items-center gap-1.5 bg-blue-50 text-blue-700 dark:bg-blue-500/10 dark:text-blue-300 border border-blue-200/60 dark:border-blue-500/20">
                    {s}
                    <button onClick={() => { setSkills(skills.filter(x => x !== s)); markDirty(); }} className="hover:text-red-500 p-0.5 rounded">&times;</button>
                  </Badge>
                ))}
                {skills.length === 0 && <span className="text-xs text-gray-400 italic">{t('cv.builder.noSkills')}</span>}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>{t('cv.builder.workExperience')}</CardTitle>
                  <CardDescription>{t('cv.builder.workExperienceDesc')}</CardDescription>
                </div>
                <Button variant="outline" size="sm" leftIcon={<Plus className="h-3.5 w-3.5" />}
                  onClick={() => { setExperiences([{ id: `exp_${Date.now()}`, title: '', company: '', period: '', description: '' }, ...experiences]); markDirty(); }}>
                  {t('cv.builder.addExperience')}
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {experiences.map((exp, idx) => (
                  <div key={exp.id} className="p-4 rounded-xl border border-gray-100 dark:border-white/[0.06] space-y-3 relative group">
                    <button onClick={() => { setExperiences(experiences.filter(x => x.id !== exp.id)); markDirty(); }}
                      className="absolute top-3 right-3 text-gray-400 hover:text-red-500 transition-colors" title={t('common.delete')}>
                      <Trash2 className="h-4 w-4" />
                    </button>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pr-6">
                      <Input label={t('jobs.col.jobTitle')} value={exp.title} onChange={e => { const u = [...experiences]; u[idx].title = e.target.value; setExperiences(u); markDirty(); }} />
                      <Input label={t('cv.builder.company')} value={exp.company} onChange={e => { const u = [...experiences]; u[idx].company = e.target.value; setExperiences(u); markDirty(); }} />
                      <Input label={t('cv.builder.period')} value={exp.period} onChange={e => { const u = [...experiences]; u[idx].period = e.target.value; setExperiences(u); markDirty(); }} />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{t('cv.builder.descAchievements')}</label>
                      <textarea rows={3} value={exp.description} onChange={e => { const u = [...experiences]; u[idx].description = e.target.value; setExperiences(u); markDirty(); }}
                        className="w-full rounded-lg border border-gray-200 bg-white p-2.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500/20 dark:border-white/10 dark:bg-white/5 dark:text-white resize-y" />
                    </div>
                  </div>
                ))}
                {experiences.length === 0 && <p className="text-xs text-gray-400 italic text-center py-4">{t('cv.builder.noExperienceMsg')}</p>}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>{t('own.education')}</CardTitle>
                  <CardDescription>{t('cv.builder.educationDesc')}</CardDescription>
                </div>
                <Button variant="outline" size="sm" leftIcon={<Plus className="h-3.5 w-3.5" />}
                  onClick={() => { setEducation([{ id: `edu_${Date.now()}`, degree: '', school: '', year: '' }, ...education]); markDirty(); }}>
                  {t('cv.builder.addEducation')}
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {education.map((edu, idx) => (
                  <div key={edu.id} className="p-3 rounded-xl border border-gray-100 dark:border-white/[0.06] space-y-3 relative group">
                    <button onClick={() => { setEducation(education.filter(x => x.id !== edu.id)); markDirty(); }}
                      className="absolute top-2 right-2 text-gray-400 hover:text-red-500 transition-colors" title={t('common.delete')}>
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pr-6">
                      <Input label={t('cv.builder.degree')} value={edu.degree} onChange={e => { const u = [...education]; u[idx].degree = e.target.value; setEducation(u); markDirty(); }} />
                      <Input label={t('cv.builder.school')} value={edu.school} onChange={e => { const u = [...education]; u[idx].school = e.target.value; setEducation(u); markDirty(); }} />
                      <Input label={t('cv.builder.year')} value={edu.year} onChange={e => { const u = [...education]; u[idx].year = e.target.value; setEducation(u); markDirty(); }} />
                    </div>
                  </div>
                ))}
                {education.length === 0 && <p className="text-xs text-gray-400 italic text-center py-4">{t('cv.builder.noEducationMsg')}</p>}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Panel */}
        <div className="lg:col-span-5 space-y-6">
          <Card variant="elevated" className="bg-gradient-to-br from-blue-900 via-indigo-900 to-slate-900 text-white border-none">
            <CardContent>
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-xs font-semibold uppercase tracking-wider text-blue-300">{t('cv.builder.completeness')}</span>
                  <div className="text-3xl font-extrabold mt-1 flex items-baseline gap-2">
                    {score}<span className="text-lg font-normal text-blue-300">/ 100</span>
                  </div>
                  <span className={`text-xs font-semibold ${scoreColor}`}>{scoreLabel}</span>
                </div>
                <div className="h-12 w-12 rounded-2xl bg-white/10 backdrop-blur-md flex items-center justify-center">
                  <Sparkles className="h-6 w-6 text-amber-300" />
                </div>
              </div>
              <Progress value={score} max={100} color="green" className="mt-4 bg-white/20" />
              <div className="mt-5 space-y-2 text-xs">
                {!name && <Suggestion text={t('cv.builder.suggName')} />}
                {!role && <Suggestion text={t('cv.builder.suggTitle')} />}
                {!summary && <Suggestion text={t('cv.builder.suggSummary')} />}
                {(skills.length || 0) < 5 && <Suggestion text={`${t('common.add')} ${5 - (skills.length || 0)} ${t('cv.builder.moreSkillsAts')}`} />}
                {(experiences.length || 0) === 0 && <Suggestion text={t('cv.builder.suggExperience')} />}
                {(education.length || 0) === 0 && <Suggestion text={t('cv.builder.suggEducation')} />}
                {score >= 70 && <div className="flex items-center gap-2 text-emerald-300 font-medium pt-1 border-t border-white/10"><CheckIcon /> {t('cv.builder.cvReady')}</div>}
              </div>
            </CardContent>
          </Card>

          <Card className="sticky top-20 border-2 border-gray-200 dark:border-white/10 bg-white dark:bg-[#0f172a] shadow-xl" id="cv-preview">
            <CardHeader className="border-b border-gray-100 dark:border-white/10 pb-3">
              <div className="flex items-center justify-between w-full">
                <div className="flex items-center gap-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                  <FileText className="h-4 w-4 text-blue-600" /> {t('cv.builder.livePreview')}
                </div>
                <Badge variant="outline" size="sm">{t('cv.builder.a4Standard')}</Badge>
              </div>
            </CardHeader>
            <CardContent className="p-6 text-gray-900 dark:text-gray-100 font-sans space-y-5 max-h-[600px] overflow-y-auto">
              <div className="border-b border-gray-200 dark:border-white/20 pb-4 text-center">
                <h2 className="text-xl font-bold tracking-tight text-gray-900 dark:text-white">{name || t('cv.builder.yourName')}</h2>
                <p className="text-sm font-medium text-blue-600 dark:text-blue-400 mt-0.5">{role || t('cv.builder.professionalTitle')}</p>
                <div className="flex flex-wrap justify-center gap-x-3 gap-y-1 text-xs text-gray-500 dark:text-gray-400 mt-2">
                  {email && <span>{email}</span>}
                  {email && phone && <span className="hidden sm:inline">&bull;</span>}
                  {phone && <span>{phone}</span>}
                  {location && <><span>&bull;</span><span>{location}</span></>}
                </div>
              </div>
              {summary && (
                <div>
                  <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400 dark:text-gray-500 mb-1">{t('cv.builder.profSummary')}</h3>
                  <p className="text-xs text-gray-600 dark:text-gray-300 leading-relaxed">{summary}</p>
                </div>
              )}
              {skills.length > 0 && (
                <div>
                  <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400 dark:text-gray-500 mb-1.5">{t('cv.builder.coreCompetencies')}</h3>
                  <div className="flex flex-wrap gap-1">{skills.map(s => (
                    <span key={s} className="text-[11px] font-medium bg-gray-100 dark:bg-white/10 px-2 py-0.5 rounded text-gray-700 dark:text-gray-300">{s}</span>
                  ))}</div>
                </div>
              )}
              {experiences.length > 0 && (
                <div className="space-y-3">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400 dark:text-gray-500 mb-1">{t('cv.builder.profExperience')}</h3>
                  {experiences.map(exp => exp.title || exp.company ? (
                    <div key={exp.id} className="space-y-1">
                      <div className="flex items-baseline justify-between text-xs font-semibold text-gray-900 dark:text-white">
                        <span>{exp.title || t('cv.builder.untitled')} {exp.company && <span className="font-normal text-gray-500">{t('cv.builder.at')} {exp.company}</span>}</span>
                        {exp.period && <span className="text-[10px] font-normal text-gray-400">{exp.period}</span>}
                      </div>
                      {exp.description && <p className="text-[11px] text-gray-600 dark:text-gray-300 leading-normal">{exp.description}</p>}
                    </div>
                  ) : null)}
                </div>
              )}
              {education.length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400 dark:text-gray-500 mb-1">{t('own.education')}</h3>
                  {education.map(edu => edu.degree || edu.school ? (
                    <div key={edu.id} className="flex items-baseline justify-between text-xs">
                      <span className="font-semibold text-gray-900 dark:text-white">{edu.degree || t('cv.builder.degree')}{edu.school ? <span className="font-normal text-gray-500"> — {edu.school}</span> : ''}</span>
                      {edu.year && <span className="text-[10px] text-gray-400">{edu.year}</span>}
                    </div>
                  ) : null)}
                </div>
              )}
              {!name && !role && !summary && skills.length === 0 && experiences.length === 0 && education.length === 0 && (
                <p className="text-xs text-gray-400 italic text-center py-8">{t('cv.builder.previewEmpty')}</p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function Suggestion({ text }: { text: string }) {
  return (
    <div className="flex items-center gap-2 text-amber-300 font-medium">
      <AlertIcon />
      <span>{text}</span>
    </div>
  );
}
function CheckIcon() {
  return (
    <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}
function AlertIcon() {
  return (
    <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
    </svg>
  );
}
