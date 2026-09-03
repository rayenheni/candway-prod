import { useState, useEffect, useRef, type ReactNode } from 'react';
import { useLanguage } from '@/contexts/language-context';
import { Card } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, ConfirmDialog } from '@/shared/components/ui/dialog';
import { customToast } from '@/shared/components/ui/toast';
import { campaignsService } from '@/services/campaigns.service';
import { Search, Plus, Loader2, FileText, Pencil, Trash2, Eye, Check, Copy, Bold, Italic, Underline } from 'lucide-react';

const VARIABLES = [
  { key: '{{name}}', sample: 'Alex Rivera' },
  { key: '{{role}}', sample: 'Senior Frontend Engineer' },
  { key: '{{company}}', sample: 'Candway' },
  { key: '{{location}}', sample: 'Tunis, Tunisia' },
  { key: '{{details}}', sample: 'Attached you will find the full job description.' },
];

interface TemplateForm {
  name: string;
  role: string;
  description: string;
  subject_template: string;
  body_template: string;
}

const EMPTY_FORM: TemplateForm = {
  name: '',
  role: '',
  description: '',
  subject_template: '',
  body_template: '',
};

function substitute(text: string): string {
  let out = text || '';
  for (const v of VARIABLES) out = out.split(v.key).join(v.sample);
  return out;
}

function renderBody(text: string): ReactNode[] {
  const substituted = substitute(text);
  return substituted.split('\n').map((line, i) => {
    let key = 0;
    const nodes: ReactNode[] = [];
    const tokenRegex = /(\*\*.+?\*\*|\*.+?\*|__.+?__)/g;
    let last = 0;
    let m: RegExpExecArray | null;
    while ((m = tokenRegex.exec(line)) !== null) {
      if (m.index > last) nodes.push(<span key={key++}>{line.slice(last, m.index)}</span>);
      const token = m[1];
      if (token.startsWith('**')) {
        nodes.push(<strong key={key++} className="font-bold">{token.slice(2, -2)}</strong>);
      } else if (token.startsWith('__')) {
        nodes.push(<u key={key++}>{token.slice(2, -2)}</u>);
      } else {
        nodes.push(<em key={key++}>{token.slice(1, -1)}</em>);
      }
      last = m.index + token.length;
    }
    if (nodes.length === 0) {
      return <span key={`l${i}`}>{line}<br /></span>;
    }
    const rest = line.slice(last);
    if (rest) nodes.push(<span key={key++}>{rest}</span>);
    return <span key={`l${i}`}>{nodes}<br /></span>;
  });
}

function applyMarkup(textarea: HTMLTextAreaElement | null, form: TemplateForm, setForm: (f: TemplateForm) => void, before: string, after: string) {
  if (!textarea) {
    setForm({ ...form, body_template: `${form.body_template}${before}${after}` });
    return;
  }
  const start = textarea.selectionStart ?? form.body_template.length;
  const end = textarea.selectionEnd ?? start;
  const sel = form.body_template.slice(start, end) || 'text';
  const next = form.body_template.slice(0, start) + before + sel + after + form.body_template.slice(end);
  setForm({ ...form, body_template: next });
  requestAnimationFrame(() => {
    textarea.focus();
    textarea.selectionStart = start + before.length;
    textarea.selectionEnd = start + before.length + sel.length;
  });
}

function insertVariable(textarea: HTMLTextAreaElement | null, form: TemplateForm, setForm: (f: TemplateForm) => void, variable: string) {
  if (!textarea) {
    setForm({ ...form, body_template: `${form.body_template}${form.body_template ? ' ' : ''}${variable}` });
    return;
  }
  const start = textarea.selectionStart ?? form.body_template.length;
  const next = form.body_template.slice(0, start) + variable + form.body_template.slice(start);
  setForm({ ...form, body_template: next });
  requestAnimationFrame(() => {
    textarea.focus();
    textarea.selectionStart = textarea.selectionEnd = start + variable.length;
  });
}

export default function EmailTemplatesPage() {
  const { t } = useLanguage();
  const [templates, setTemplates] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<TemplateForm>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewTemplate, setPreviewTemplate] = useState<any>(null);
  const [deleteTarget, setDeleteTarget] = useState<any>(null);
  const [deleting, setDeleting] = useState(false);
  const bodyRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    loadTemplates();
  }, []);

  const loadTemplates = () => {
    setLoading(true);
    campaignsService.getTemplates()
      .then((data: any) => setTemplates(Array.isArray(data) ? data : data?.items || []))
      .catch(() => setTemplates([]))
      .finally(() => setLoading(false));
  };

  const openCreate = () => {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setEditorOpen(true);
  };

  const openEdit = (tmpl: any) => {
    setEditingId(tmpl.id);
    setForm({
      name: tmpl.name || '',
      role: tmpl.role || '',
      description: tmpl.description || '',
      subject_template: tmpl.subject_template || '',
      body_template: tmpl.body_template || '',
    });
    setEditorOpen(true);
  };

  const handleDuplicate = async (tmpl: any) => {
    try {
      await campaignsService.createTemplate({
        name: `${tmpl.name} (copy)`,
        role: tmpl.role || 'General',
        description: tmpl.description || '',
        subject_template: tmpl.subject_template || '',
        body_template: tmpl.body_template || '',
      });
      customToast({ type: 'success', title: t('recruiter.templates.duplicated'), message: t('recruiter.templates.duplicatedMsg') });
      loadTemplates();
    } catch {
      customToast({ type: 'error', title: t('recruiter.templates.error'), message: t('recruiter.templates.duplicateFailed') });
    }
  };

  const handleSave = async () => {
    if (!form.name.trim() || !form.subject_template.trim() || !form.body_template.trim()) {
      customToast({ type: 'error', title: t('recruiter.templates.missingFields'), message: t('recruiter.templates.missingFieldsMsg') });
      return;
    }
    setSaving(true);
    try {
      const payload: TemplateForm = {
        name: form.name.trim(),
        role: form.role.trim() || 'General',
        description: form.description.trim(),
        subject_template: form.subject_template.trim(),
        body_template: form.body_template.trim(),
      };
      if (editingId != null) {
        await campaignsService.updateTemplate(editingId, payload);
        customToast({ type: 'success', title: t('recruiter.templates.updated'), message: t('recruiter.templates.updatedMsg') });
      } else {
        await campaignsService.createTemplate(payload);
        customToast({ type: 'success', title: t('recruiter.templates.created'), message: t('recruiter.templates.createdMsg') });
      }
      setEditorOpen(false);
      loadTemplates();
    } catch {
      customToast({ type: 'error', title: t('recruiter.templates.error'), message: t('recruiter.templates.saveFailed') });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await campaignsService.deleteTemplate(deleteTarget.id);
      customToast({ type: 'success', title: t('recruiter.templates.deleted'), message: t('recruiter.templates.deletedMsg') });
      setDeleteTarget(null);
      loadTemplates();
    } catch {
      customToast({ type: 'error', title: t('recruiter.templates.error'), message: t('recruiter.templates.deleteFailed') });
    } finally {
      setDeleting(false);
    }
  };

  const filtered = templates.filter((tmpl: any) =>
    (tmpl.name || '').toLowerCase().includes(search.toLowerCase()) ||
    (tmpl.subject_template || tmpl.subject || '').toLowerCase().includes(search.toLowerCase()) ||
    (tmpl.role || '').toLowerCase().includes(search.toLowerCase())
  );

  const bodyCharCount = (form.body_template || '').length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">{t('recruiter.templates.title')}</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{t('recruiter.templates.subtitle')}</p>
        </div>
        <Button variant="primary" leftIcon={<Plus className="h-4 w-4" />} onClick={openCreate}>{t('recruiter.templates.create')}</Button>
      </div>

      <Input placeholder={t('recruiter.templates.search')} leftIcon={<Search className="h-4 w-4 text-purple-500" />} value={search} onChange={(e) => setSearch(e.target.value)} wrapperClassName="max-w-sm" />

      {loading ? (
        <div className="flex justify-center py-12"><Loader2 className="h-6 w-6 animate-spin text-purple-600" /></div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-12 text-gray-500">{t('common.noData')}</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filtered.map((tmpl: any) => (
            <Card key={tmpl.id} className="p-5 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Badge variant="primary" size="sm">{tmpl.role || tmpl.category || t('recruiter.templates.general')}</Badge>
                    {tmpl.is_default && <Badge size="sm">{t('recruiter.templates.system')}</Badge>}
                  </div>
                  <span className="text-xs font-medium text-gray-400">{tmpl.uses || 0} {t('recruiter.templates.uses')}</span>
                </div>
                <h3 className="text-base font-extrabold text-gray-900 dark:text-white mb-1">{tmpl.name}</h3>
                <p className="text-xs text-purple-600 dark:text-purple-400 font-medium line-clamp-1">{tmpl.subject_template || tmpl.subject}</p>
                {tmpl.description ? (
                  <p className="mt-2 text-xs text-gray-500 dark:text-gray-400 line-clamp-2">{tmpl.description}</p>
                ) : null}
              </div>
              <div className="flex gap-2 mt-4 flex-wrap">
                <Button variant="outline" size="sm" leftIcon={<Eye className="h-3 w-3" />} onClick={() => { setPreviewTemplate(tmpl); setPreviewOpen(true); }}>{t('recruiter.templates.preview')}</Button>
                <Button variant="outline" size="sm" leftIcon={<Pencil className="h-3 w-3" />} onClick={() => openEdit(tmpl)}>{t('common.edit')}</Button>
                <Button variant="outline" size="sm" leftIcon={<Copy className="h-3 w-3" />} onClick={() => handleDuplicate(tmpl)}>{t('recruiter.templates.duplicate')}</Button>
                {!tmpl.is_default && (
                  <Button variant="outline" size="sm" className="text-red-600 hover:bg-red-50 dark:hover:bg-red-500/10 border-red-200/60 dark:border-red-500/20" leftIcon={<Trash2 className="h-3 w-3" />} onClick={() => setDeleteTarget(tmpl)}>{t('common.delete')}</Button>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Create / Edit advanced editor */}
      <Dialog open={editorOpen} onOpenChange={setEditorOpen}>
        <DialogContent className="max-w-4xl max-h-[92vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editingId != null ? t('recruiter.templates.editTitle') : t('recruiter.templates.create')}</DialogTitle>
            <DialogDescription>{t('recruiter.templates.editorDesc')}</DialogDescription>
          </DialogHeader>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 my-4">
            {/* LEFT: form + editor */}
            <div className="space-y-4">
              <Input label={t('recruiter.templates.name')} value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder={t('recruiter.templates.namePlaceholder')} />
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Input label={t('recruiter.templates.role')} value={form.role} onChange={e => setForm({ ...form, role: e.target.value })} placeholder={t('recruiter.templates.rolePlaceholder')} />
                <Input label={t('common.description')} value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} placeholder={t('recruiter.templates.descriptionPlaceholder')} />
              </div>
              <Input label={t('recruiter.templates.subject')} value={form.subject_template} onChange={e => setForm({ ...form, subject_template: e.target.value })} placeholder={t('recruiter.templates.subjectPlaceholder')} />

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300">{t('recruiter.templates.bodyLabel')}</label>
                  <span className={`text-xs ${bodyCharCount > 2000 ? 'text-amber-600 dark:text-amber-400 font-bold' : 'text-gray-400'}`}>{bodyCharCount} {t('recruiter.templates.chars')}</span>
                </div>

                {/* Toolbar */}
                <div className="flex items-center gap-1 mb-1.5 rounded-lg border border-purple-200/60 dark:border-purple-500/20 bg-white/60 dark:bg-white/5 p-1 flex-wrap">
                  <button
                    type="button"
                    title={t('recruiter.templates.bold')}
                    onClick={() => applyMarkup(bodyRef.current, form, setForm, '**', '**')}
                    className="h-7 w-7 rounded-md flex items-center justify-center text-gray-600 dark:text-gray-300 hover:bg-purple-100 dark:hover:bg-purple-500/20 transition-colors"
                  >
                    <Bold className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    title={t('recruiter.templates.italic')}
                    onClick={() => applyMarkup(bodyRef.current, form, setForm, '*', '*')}
                    className="h-7 w-7 rounded-md flex items-center justify-center text-gray-600 dark:text-gray-300 hover:bg-purple-100 dark:hover:bg-purple-500/20 transition-colors"
                  >
                    <Italic className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    title={t('recruiter.templates.underline')}
                    onClick={() => applyMarkup(bodyRef.current, form, setForm, '__', '__')}
                    className="h-7 w-7 rounded-md flex items-center justify-center text-gray-600 dark:text-gray-300 hover:bg-purple-100 dark:hover:bg-purple-500/20 transition-colors"
                  >
                    <Underline className="h-3.5 w-3.5" />
                  </button>
                  <span className="mx-1 h-4 w-px bg-gray-200 dark:bg-white/10" />
                  {VARIABLES.map((v) => (
                    <button
                      key={v.key}
                      type="button"
                      title={`${t('recruiter.templates.insertVariable')} ${v.key} = ${v.sample}`}
                      onClick={() => insertVariable(bodyRef.current, form, setForm, v.key)}
                      className="px-2 py-1 rounded-md bg-purple-50 dark:bg-purple-500/10 text-[11px] font-bold text-purple-600 dark:text-purple-400 hover:bg-purple-100 dark:hover:bg-purple-500/20 transition-colors"
                    >
                      {v.key}
                    </button>
                  ))}
                </div>

                <textarea
                  ref={bodyRef}
                  value={form.body_template}
                  onChange={e => setForm({ ...form, body_template: e.target.value })}
                  rows={14}
                  placeholder={t('recruiter.templates.bodyPlaceholder')}
                  className="w-full rounded-lg border border-purple-200/60 bg-white/70 backdrop-blur-sm px-3 py-2 text-sm text-gray-900 dark:border-purple-500/20 dark:bg-white/5 dark:text-white placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 transition-colors font-mono"
                />
                <p className="mt-1 text-[11px] text-gray-400">{t('recruiter.templates.formatting')}</p>
              </div>
            </div>

            {/* RIGHT: live preview */}
            <div className="space-y-4">
              <div className="rounded-xl border border-violet-200/70 dark:border-violet-500/25 bg-violet-50/40 dark:bg-violet-500/5 p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Eye className="h-4 w-4 text-violet-500" />
                  <h4 className="text-sm font-extrabold uppercase tracking-wider text-violet-700 dark:text-violet-300">{t('recruiter.templates.livePreview')}</h4>
                  <span className="ml-auto text-[11px] text-gray-400">{t('recruiter.templates.sampleVars')}</span>
                </div>

                <div className="rounded-xl bg-white dark:bg-white/[0.04] border border-gray-100 dark:border-white/[0.06] shadow-sm overflow-hidden">
                  <div className="px-4 py-2 border-b border-gray-100 dark:border-white/[0.06] flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full bg-red-400" />
                    <span className="h-2 w-2 rounded-full bg-amber-400" />
                    <span className="h-2 w-2 rounded-full bg-emerald-400" />
                    <span className="ml-2 text-[11px] font-semibold text-gray-400">{t('recruiter.templates.emailPreview')}</span>
                  </div>
                  <div className="p-4">
                    <div className="text-sm text-gray-800 dark:text-gray-200">
                      <span className="font-semibold">{t('recruiter.templates.to')}</span> candidate@example.com
                    </div>
                    <div className="text-sm text-gray-800 dark:text-gray-200 mb-3">
                      <span className="font-semibold">{t('recruiter.templates.subjectColon')}</span>{' '}
                      <span className={substitute(form.subject_template).length > 60 ? 'text-amber-600 dark:text-amber-400' : ''}>
                        {substitute(form.subject_template) || '—'}
                      </span>
                      <span className="ml-2 text-[11px] text-gray-400">{substitute(form.subject_template).length} {t('recruiter.templates.chars')}</span>
                    </div>
                    <div className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed min-h-[200px]">
                      {form.body_template ? renderBody(form.body_template) : <span className="text-gray-400 italic">{t('recruiter.templates.bodyStart')}</span>}
                    </div>
                  </div>
                </div>

                <div className="mt-3 flex flex-wrap gap-1.5">
                  {VARIABLES.map((v) => (
                    <Badge key={v.key} size="sm" variant="outline">{v.key}</Badge>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="ghost" onClick={() => setEditorOpen(false)}>{t('common.cancel')}</Button>
            <Button variant="primary" loading={saving} onClick={handleSave} leftIcon={<Check className="h-4 w-4" />}>
              {editingId != null ? t('recruiter.templates.saveChanges') : t('common.confirm')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Preview dialog */}
      <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{previewTemplate?.name || t('recruiter.templates.preview')}</DialogTitle>
            <DialogDescription>{t('recruiter.templates.subjectColon')} {previewTemplate?.subject_template || previewTemplate?.subject || ''}</DialogDescription>
          </DialogHeader>
          <div className="my-4 rounded-xl border border-purple-100 dark:border-purple-500/20 bg-purple-50/40 dark:bg-purple-500/5 p-5">
            <div className="mb-3 flex items-center gap-2 text-xs font-bold text-gray-500 dark:text-gray-400">
              <FileText className="h-3.5 w-3.5" /> {t('recruiter.templates.body')}
            </div>
            <div className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-wrap">
              {renderBody(previewTemplate?.body_template || '')}
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setPreviewOpen(false)}>{t('common.close')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirm */}
      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
        title={t('recruiter.templates.deleteTitle')}
        description={t('recruiter.templates.deleteConfirm').replace('{name}', deleteTarget?.name || '')}
        confirmLabel={t('common.delete')}
        variant="danger"
        loading={deleting}
        onConfirm={handleDelete}
      />
    </div>
  );
}