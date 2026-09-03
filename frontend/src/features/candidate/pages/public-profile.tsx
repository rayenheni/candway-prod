import { useState, useEffect } from 'react';
import { useParams } from 'react-router';
import { motion } from 'framer-motion';
import { Card, CardTitle } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Progress } from '@/shared/components/ui/progress';
import { candidateService } from '@/services/candidate.service';
import { MapPin, GraduationCap, Mail, ExternalLink, Link as LinkIcon, Loader2 } from 'lucide-react';
import { useLanguage } from '@/contexts/language-context';

export default function PublicProfilePage() {
  const { userId } = useParams();
  const { t } = useLanguage();
  const [profile, setProfile] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showContact, setShowContact] = useState(false);

  useEffect(() => {
    if (!userId) { setLoading(false); setError(t('profile.public.noUserId')); return; }
    setLoading(true); setError('');
    candidateService.getPublicProfile(Number(userId))
      .then(setProfile)
      .catch(err => setError(err?.errors?.detail || err?.message || t('profile.public.loadFailed')))
      .finally(() => setLoading(false));
  }, [userId]);

  if (loading) return <div className="flex justify-center py-20"><Loader2 className="h-8 w-8 animate-spin text-purple-600" /></div>;
  if (error) return <div className="text-center py-20 text-red-500">{error}</div>;
  if (!profile) return <div className="text-center py-20 text-gray-400">{t('profile.public.notFound')}</div>;

  const { cv } = profile;
  const skills = cv?.skills ?? [];
  const experience = cv?.experience ?? [];
  const education = cv?.education ?? [];

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
        <Card className="glass-panel border-purple-200/50 p-8">
          <div className="flex flex-col md:flex-row items-center md:items-start gap-6">
            <div className="h-24 w-24 rounded-2xl bg-gradient-to-br from-purple-500 to-violet-600 flex items-center justify-center text-white text-3xl font-bold shadow-lg">
              {profile.name?.split(' ').map((n: string) => n[0]).join('').slice(0, 2) || '?'}
            </div>
            <div className="flex-1 text-center md:text-left">
              <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">{profile.name}</h1>
              <p className="text-purple-600 dark:text-purple-400 font-medium">{profile.headline}</p>
              <div className="flex flex-wrap items-center justify-center md:justify-start gap-3 mt-2 text-sm text-gray-500">
                {profile.location && <span className="flex items-center gap-1"><MapPin className="h-4 w-4" /> {profile.location}</span>}
                <span className="flex items-center gap-1"><GraduationCap className="h-4 w-4" /></span>
              </div>
              <p className="mt-3 text-gray-600 dark:text-gray-300">{profile.bio}</p>
              {skills.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-4">
                  {skills.map((s: any, i: number) => (
                    <Badge key={i} variant="default" size="sm">{s.name || s}</Badge>
                  ))}
                </div>
              )}
              <div className="flex items-center gap-2 mt-4">
                {profile.email && !showContact ? (
                  <Button variant="primary" onClick={() => setShowContact(true)} leftIcon={<Mail className="h-4 w-4" />}>{t('profile.public.showContact')}</Button>
                ) : profile.email && showContact ? (
                  <div className="flex items-center gap-2 p-2 rounded-lg bg-white/50 dark:bg-white/[0.02]">
                    <Mail className="h-4 w-4 text-purple-500" /><span className="text-sm font-medium">{profile.email}</span>
                  </div>
                ) : null}
                {profile.links?.linkedin && <Button variant="outline" size="sm" onClick={() => window.open(profile.links.linkedin, '_blank')}><LinkIcon className="h-4 w-4" /> {t('profile.public.linkedin')}</Button>}
                {profile.links?.portfolio && <Button variant="outline" size="sm" onClick={() => window.open(profile.links.portfolio, '_blank')}><ExternalLink className="h-4 w-4" /> {t('profile.public.portfolio')}</Button>}
              </div>
            </div>
          </div>
        </Card>
      </motion.div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="glass-panel border-purple-200/50 p-5 md:col-span-2">
          <CardTitle className="mb-4">{t('own.experience')}</CardTitle>
          {experience.length === 0 ? <p className="text-sm text-gray-400">{t('profile.public.noExperience')}</p> : (
            <div className="space-y-4">
              {experience.map((exp: any, i: number) => (
                <motion.div key={i} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.1 }} className="p-4 rounded-xl bg-white/50 dark:bg-white/[0.02] border border-purple-100/60">
                  <div className="flex items-center justify-between"><h3 className="font-bold text-gray-900 dark:text-white">{exp.title || exp.role}</h3><span className="text-xs text-gray-400">{exp.period || exp.duration}</span></div>
                  <p className="text-sm text-purple-600 dark:text-purple-400">{exp.company || exp.organization}</p>
                  <p className="text-sm text-gray-500 mt-1">{exp.description}</p>
                </motion.div>
              ))}
            </div>
          )}
        </Card>
        <div className="space-y-6">
          <Card className="glass-panel border-purple-200/50 p-5">
            <CardTitle className="mb-3">{t('own.education')}</CardTitle>
            {education.length === 0 ? <p className="text-sm text-gray-400">{t('profile.public.noEducation')}</p> : (
              <div className="space-y-3">
                {education.map((edu: any, i: number) => (
                  <div key={i} className="p-3 rounded-lg bg-white/50 dark:bg-white/[0.02]">
                    <p className="font-semibold text-sm text-gray-900 dark:text-white">{edu.degree}</p>
                    <p className="text-xs text-gray-500">{edu.school || edu.institution}{edu.year ? ` · ${edu.year}` : ''}</p>
                  </div>
                ))}
              </div>
            )}
          </Card>
          {skills.length > 0 && (
            <Card className="glass-panel border-purple-200/50 p-5">
              <CardTitle className="mb-3">{t('own.skills')}</CardTitle>
              <div className="space-y-2">
                {(Array.isArray(skills) ? skills : []).map((s: any, i: number) => (
                  <div key={i} className="flex items-center justify-between">
                    <span className="text-sm text-gray-700 dark:text-gray-300">{s.name || s}</span>
                    {s.level && <Progress value={s.level} className="w-1/2" />}
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}