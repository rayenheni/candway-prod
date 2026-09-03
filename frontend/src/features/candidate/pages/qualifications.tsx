import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Card } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { customToast } from '@/shared/components/ui/toast';
import { candidateService } from '@/services/candidate.service';
import { Award, Upload, Plus, Trash2, Eye, Download, CheckCircle2, Clock, Loader2 } from 'lucide-react';
import { useLanguage } from '@/contexts/language-context';

export default function QualificationsPage() {
  const { t } = useLanguage();
  const [quals, setQuals] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ title: '', category: '' });
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  const fetchQualifications = async () => {
    setLoading(true); setError('');
    try {
      const res = await candidateService.getQualifications();
      setQuals(res.qualifications ?? []);
    } catch (err: any) {
      setError(err?.errors?.detail || err?.message || t('qualifications.loadFailed'));
    } finally { setLoading(false); }
  };

  useEffect(() => { fetchQualifications(); }, []);

  const handleUpload = async () => {
    if (!form.title || !file) { customToast({ type: 'error', title: t('qualifications.error'), message: t('qualifications.titleAndFileRequired') }); return; }
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('title', form.title);
      if (form.category) fd.append('category', form.category);
      await candidateService.uploadQualification(fd);
      customToast({ type: 'success', title: t('qualifications.uploaded'), message: t('qualifications.submittedForVerification') });
      setForm({ title: '', category: '' }); setFile(null); setShowForm(false);
      await fetchQualifications();
    } catch (err: any) {
      customToast({ type: 'error', title: t('own.uploadFailed'), message: err?.errors?.detail || err?.message || t('qualifications.uploadError') });
    } finally { setUploading(false); }
  };

  const handleDelete = async (id: string) => {
    try {
      await candidateService.deleteQualification(id);
      setQuals(quals.filter(q => q.id !== id));
      customToast({ type: 'info', title: t('qualifications.removed'), message: t('qualifications.deleted') });
    } catch (err: any) {
      customToast({ type: 'error', title: t('qualifications.error'), message: err?.errors?.detail || err?.message || t('qualifications.deleteFailed') });
    }
  };

  const statusIcon = (v: boolean) => v ? <CheckCircle2 className="h-4 w-4 text-emerald-500" /> : <Clock className="h-4 w-4 text-amber-500" />;

  if (loading) return <div className="flex justify-center py-20"><Loader2 className="h-8 w-8 animate-spin text-purple-600" /></div>;
  if (error) return <div className="text-center py-20 text-red-500">{error}</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">{t('qualifications.title')}</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{t('qualifications.subtitle')}</p>
        </div>
        <Button variant="primary" leftIcon={<Plus className="h-4 w-4" />} onClick={() => setShowForm(!showForm)}>{t('qualifications.uploadNew')}</Button>
      </div>
      {showForm && (
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="glass-panel border-purple-200/50 p-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              <Input placeholder={t('qualifications.titlePlaceholder')} value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} />
              <Select value={form.category || undefined} onValueChange={(v) => setForm({ ...form, category: v })}>
                <SelectTrigger>
                  <SelectValue placeholder={t('qualifications.categoryOptional')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="degree">{t('own.qualDegree')}</SelectItem>
                  <SelectItem value="certificate">{t('own.qualCertificate')}</SelectItem>
                  <SelectItem value="transcript">{t('own.qualTranscript')}</SelectItem>
                  <SelectItem value="license">{t('own.qualLicense')}</SelectItem>
                  <SelectItem value="other">{t('sources.other')}</SelectItem>
                </SelectContent>
              </Select>
              <Input type="file" onChange={e => setFile(e.target.files?.[0] ?? null)} />
            </div>
            <div className="flex items-center gap-2">
              <Button variant="primary" leftIcon={uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />} onClick={handleUpload} disabled={uploading}>{uploading ? t('own.uploading') : t('qualifications.uploadVerify')}</Button>
              <Button variant="ghost" onClick={() => setShowForm(false)}>{t('common.cancel')}</Button>
            </div>
          </Card>
        </motion.div>
      )}
      {quals.length === 0 ? (
        <div className="text-center py-16 text-gray-400"><Award className="h-12 w-12 mx-auto mb-3 opacity-40" /><p>{t('qualifications.empty')}</p></div>
      ) : (
        <div className="space-y-4">
          {quals.map((q, i) => (
            <motion.div key={q.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
              <Card hoverable className="p-5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-purple-100 dark:bg-purple-500/20">
                      <Award className="h-6 w-6 text-purple-600 dark:text-purple-400" />
                    </div>
                    <div>
                      <h3 className="font-bold text-gray-900 dark:text-white">{q.title}</h3>
                      <p className="text-sm text-gray-500">{q.category || t('qualifications.general')} · {new Date(q.uploaded_at).toLocaleDateString()}</p>
                      <p className="text-xs text-gray-400">{(q.file_size / 1024).toFixed(1)} KB</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge variant={q.verified ? 'success' : 'warning'} size="sm">
                      <span className="flex items-center gap-1">{statusIcon(q.verified)}{q.verified ? t('qualifications.verified') : t('common.pending')}</span>
                    </Badge>
                    {q.file_url && <Button variant="ghost" size="sm" onClick={() => window.open(q.file_url, '_blank')}><Eye className="h-4 w-4" /></Button>}
                    {q.file_url && <Button variant="ghost" size="sm" onClick={() => window.open(q.file_url, '_blank')}><Download className="h-4 w-4" /></Button>}
                    <Button variant="ghost" size="sm" onClick={() => handleDelete(q.id)}><Trash2 className="h-4 w-4 text-red-500" /></Button>
                  </div>
                </div>
              </Card>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}