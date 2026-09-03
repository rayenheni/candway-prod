import { useState, useEffect } from 'react';
import { useLanguage } from '@/contexts/language-context';
import { useNavigate, useSearchParams } from 'react-router';
import { motion } from 'framer-motion';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { customToast } from '@/shared/components/ui/toast';
import { cn } from '@/utils/cn';
import { skillTreesService } from '@/services/skill-trees.service';
import { TreePine, Plus, Save, X, Layers, Eye, Wand2, Loader2 } from 'lucide-react';

interface SkillNode {
  id: string;
  name: string;
  level: 'beginner' | 'intermediate' | 'advanced' | 'expert';
  weight: number;
  children: SkillNode[];
}

const levelOptions = ['beginner', 'intermediate', 'advanced', 'expert'] as const;

const levelColors: Record<string, string> = {
  beginner: 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-700',
  intermediate: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-700',
  advanced: 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-700',
  expert: 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-700',
};

let nodeIdCounter = 0;
const newNode = (): SkillNode => ({ id: `node_${++nodeIdCounter}`, name: '', level: 'intermediate', weight: 100, children: [] });

// The backend rubric schema is: categories[] -> { name, weight, subcategories[] -> { name, skills[] -> { name, level, weight, required } } }.
// This maps the UI tree (category node -> skill children) into that shape so skills are NOT dropped and weights ARE preserved.
const skillNodeToCategory = (node: SkillNode): Record<string, unknown> => ({
  name: node.name,
  weight: node.weight || 1,
  skills: node.children
    .filter((child) => child.name.trim())
    .map((child) => ({ name: child.name, level: child.level, weight: child.weight || 1, required: false, keywords: [] })),
});

// Build the UI tree from a backend rubric_json.categories[] payload.
function categoriesToTree(categories: Record<string, unknown>[]): SkillNode {
  const root = newNode();
  root.name = '';
  root.children = (categories || []).map((c) => {
    const catNode = newNode();
    catNode.name = String(c.name ?? '');
    catNode.weight = Number(c.weight ?? 100) || 100;
    const subs = Array.isArray(c.subcategories) ? c.subcategories : [];
    const skills = subs.flatMap((s: Record<string, unknown>) =>
      Array.isArray(s.skills) ? s.skills : [],
    );
    catNode.children = skills
      .map((s: Record<string, unknown>) => {
        const skillNode = newNode();
        skillNode.name = String(s.name ?? '');
        skillNode.level = (['beginner', 'intermediate', 'advanced', 'expert'].includes(String(s.level)) ? String(s.level) : 'intermediate') as SkillNode['level'];
        skillNode.weight = Number(s.weight ?? 1) || 1;
        return skillNode;
      });
    return catNode;
  });
  return root;
}

export default function SkillTreeCreatePage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const editId = searchParams.get('edit') ? Number(searchParams.get('edit')) : null;
  const returnTo = searchParams.get('return_to') || null;

  const [treeName, setTreeName] = useState('');
  const [description, setDescription] = useState('');
  const [root, setRoot] = useState<SkillNode>(newNode());
  const [preview, setPreview] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isLoading, setIsLoading] = useState(Boolean(editId));

  useEffect(() => {
    if (!editId) return;
    (async () => {
      try {
        const data = await skillTreesService.get(editId);
        const rubricJson = (data.rubric_json ?? {}) as { categories?: Record<string, unknown>[] };
        const categories = rubricJson.categories ?? [];
        const parsed = categoriesToTree(categories);
        setRoot(parsed);
        setTreeName(String(data.job_name ?? data.title ?? ''));
        setDescription(String(data.description ?? ''));
      } catch {
        customToast({ type: 'error', title: t('recruiter.skillTreeCreate.loadFailedTitle'), message: t('recruiter.skillTreeCreate.loadFailedMessage') });
      } finally {
        setIsLoading(false);
      }
    })();
  }, [editId]);

  const updateNode = (nodeId: string, updater: (n: SkillNode) => SkillNode, node: SkillNode = root): SkillNode => {
    if (node.id === nodeId) return updater(node);
    return { ...node, children: node.children.map(c => updateNode(nodeId, updater, c)) };
  };

  const addChild = (parentId: string) => {
    setRoot(prev => updateNode(parentId, n => ({ ...n, children: [...n.children, newNode()] }), prev));
  };

  const removeNode = (nodeId: string) => {
    const removeFrom = (node: SkillNode): SkillNode | null => {
      if (node.id === nodeId) return null;
      return { ...node, children: node.children.map(c => removeFrom(c)).filter(Boolean) as SkillNode[] };
    };
    const result = removeFrom(root);
    if (result) setRoot(result);
  };

  const renderNode = (node: SkillNode, depth: number = 0) => (
    <motion.div key={node.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className={cn('relative rounded-xl', depth === 0 && 'space-y-3', depth > 0 && 'ml-6 pl-4 border-l-2 border-purple-200 dark:border-purple-700')}>
      <div className={cn('flex items-center gap-2 p-2.5 rounded-xl', depth === 1 ? 'bg-purple-50/70 dark:bg-purple-500/10 border border-purple-200/70 dark:border-purple-500/25' : 'hover:bg-gray-50 dark:hover:bg-white/[0.03]')}>
        <GripIcon />
        {depth === 1 && (
          <span className="text-[10px] font-bold uppercase tracking-wider text-purple-500 shrink-0 w-16">Category</span>
        )}
        {depth === 2 && (
          <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 shrink-0 w-16">Skill</span>
        )}
        <Input
          value={node.name}
          onChange={(e) => setRoot(prev => updateNode(node.id, n => ({ ...n, name: e.target.value }), prev))}
          placeholder={depth === 0 ? t('recruiter.skillTreeCreate.rubricRootPlaceholder') : depth === 1 ? t('recruiter.skillTreeCreate.categoryNamePlaceholder') : t('recruiter.skillTreeCreate.skillNamePlaceholder')}
          className="flex-1 border-purple-100 dark:border-white/10 font-medium"
        />
        {depth >= 1 && (
          <div className="flex items-center gap-1.5 shrink-0">
            <span className="text-[10px] font-bold text-gray-400 uppercase">Wt</span>
            <Input
              type="number"
              min={0}
              value={node.weight ?? 1}
              onChange={(e) => setRoot(prev => updateNode(node.id, n => ({ ...n, weight: Number(e.target.value) || 1 }), prev))}
              className="w-16 border-purple-100 dark:border-white/10 text-center"
            />
          </div>
        )}
        {depth === 2 && (
          <div className="flex items-center gap-1 shrink-0">
            <select
              value={node.level}
              onChange={(e) => setRoot(prev => updateNode(node.id, n => ({ ...n, level: e.target.value as SkillNode['level'] }), prev))}
              className={cn('h-9 rounded-lg border px-2 text-sm font-medium', levelColors[node.level])}
            >
              {levelOptions.map(l => <option key={l} value={l}>{l}</option>)}
            </select>
          </div>
        )}
        {depth > 0 && (
          <Button variant="ghost" size="sm" leftIcon={<X className="h-3.5 w-3.5" />} onClick={() => removeNode(node.id)} className="shrink-0 text-red-500 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20" />
        )}
      </div>
      {depth === 0 && (
        <div className="flex items-center gap-2 pl-1">
          <Button variant="outline" size="sm" leftIcon={<Plus className="h-3.5 w-3.5" />} onClick={() => addChild(root.id)} className="font-medium">{t('recruiter.skillTreeCreate.addCategory')}</Button>
        </div>
      )}
      {depth === 1 && node.children.length === 0 && (
        <div className="ml-6 pl-4 border-l-2 border-purple-200 dark:border-purple-700">
          <Button variant="ghost" size="sm" leftIcon={<Plus className="h-3.5 w-3.5" />} onClick={() => addChild(node.id)} className="text-purple-500 font-medium">{t('recruiter.skillTreeCreate.addSkill')}</Button>
        </div>
      )}
      {node.children.map(c => renderNode(c, depth + 1))}
      {depth === 1 && (
        <div className="ml-6 pl-4 border-l-2 border-purple-200 dark:border-purple-700 mt-2">
          <Button variant="ghost" size="sm" leftIcon={<Plus className="h-3.5 w-3.5" />} onClick={() => addChild(node.id)} className="text-purple-500 font-medium">{t('recruiter.skillTreeCreate.addSkill')}</Button>
        </div>
      )}
    </motion.div>
  );

  const GripIcon = () => <div className="h-4 w-4 shrink-0 text-gray-300 dark:text-gray-600">⁞</div>;

  const renderPreviewNode = (node: SkillNode, depth: number = 0) => (
    <div key={node.id} className={cn('relative', depth > 0 && 'ml-6 pl-4 border-l-2 border-purple-200 dark:border-purple-700')}>
      <div className="flex items-center gap-2 py-1.5">
        <div className={cn('h-2 w-2 rounded-full', node.level === 'beginner' ? 'bg-emerald-400' : node.level === 'intermediate' ? 'bg-blue-400' : node.level === 'advanced' ? 'bg-purple-400' : 'bg-amber-400')} />
        <span className="text-sm font-bold text-gray-800 dark:text-gray-200">{node.name || t('recruiter.skillTreeCreate.unnamedSkill')}</span>
        {depth >= 1 && <Badge size="sm" variant="default">{node.weight ?? 1}%</Badge>}
        {depth >= 2 && <Badge variant={node.level === 'expert' ? 'warning' : node.level === 'advanced' ? 'primary' : node.level === 'intermediate' ? 'success' : 'default'} size="sm">{node.level}</Badge>}
      </div>
      {node.children.map(c => renderPreviewNode(c, depth + 1))}
    </div>
  );

  const handleGenerateAI = async () => {
    if (!treeName.trim()) {
      customToast({ type: 'warning', title: t('recruiter.skillTreeCreate.nameRequiredTitle'), message: t('recruiter.skillTreeCreate.nameRequiredMessage') });
      return;
    }
    setIsGenerating(true);
    try {
      const response = await skillTreesService.generate({ title: treeName.trim(), description: description.trim() || undefined });
      const categories = response.categories ?? [];
      if (categories.length > 0) {
        setRoot(categoriesToTree(categories));
        customToast({ type: 'success', title: t('recruiter.skillTreeCreate.generatedTitle'), message: `${t('recruiter.skillTreeCreate.aiBuilt')} ${categories.length} ${t('recruiter.skillTreeCreate.categoriesReview')}` });
      } else {
        customToast({ type: 'error', title: t('recruiter.skillTreeCreate.emptyResultTitle'), message: t('recruiter.skillTreeCreate.emptyResultMessage') });
      }
    } catch {
      customToast({ type: 'error', title: t('recruiter.skillTreeCreate.generationFailedTitle'), message: t('recruiter.skillTreeCreate.generationFailedMessage') });
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSave = async () => {
    if (!treeName.trim()) {
      customToast({ type: 'error', title: t('recruiter.skillTreeCreate.missingNameTitle'), message: t('recruiter.skillTreeCreate.missingNameMessage') });
      return;
    }
    if (root.children.length === 0) {
      customToast({ type: 'error', title: t('recruiter.skillTreeCreate.noCategoriesTitle'), message: t('recruiter.skillTreeCreate.noCategoriesMessage') });
      return;
    }
    setIsSaving(true);
    try {
      const categories = root.children
        .map(skillNodeToCategory)
        .filter((c) => (c.name as string).trim());
      const skillCount = categories.reduce(
        (acc: number, c: Record<string, unknown>) =>
          acc + ((c.skills as unknown[])?.length || 0),
        0,
      );
      if (skillCount === 0) {
        customToast({ type: 'error', title: t('recruiter.skillTreeCreate.noSkillsTitle'), message: t('recruiter.skillTreeCreate.noSkillsMessage') });
        setIsSaving(false);
        return;
      }

      if (editId) {
        const response = await skillTreesService.update(editId, {
          rubric: { categories },
          seniority: 'mid',
        });
        if (response.success) {
          customToast({ type: 'success', title: t('recruiter.skillTreeCreate.updatedTitle'), message: `${t('recruiter.skillTreeCreate.rubricUpdated')} (v${response.version}).` });
          navigate(`/skill-tree/${response.id}`);
          return;
        }
      } else {
        const response = await skillTreesService.createStandalone({
          name: treeName.trim(),
          description: description.trim() || undefined,
          categories,
          skill_count: skillCount,
        });
        if (response.success) {
          customToast({ type: 'success', title: t('recruiter.skillTreeCreate.savedTitle'), message: `${t('recruiter.skillTreeCreate.evalRubricSaved')} "${treeName}" ${t('recruiter.skillTreeCreate.savedToLibrary')}` });
          if (returnTo) {
            navigate(`${returnTo}${returnTo.includes('?') ? '&' : '?'}rubric_id=${response.id}`);
          } else {
            navigate(`/skill-tree/${response.id}`);
          }
          return;
        }
      }
      customToast({ type: 'error', title: t('recruiter.skillTreeCreate.saveFailedTitle'), message: t('recruiter.skillTreeCreate.saveFailedMessage') });
    } catch {
      customToast({ type: 'error', title: t('recruiter.skillTreeCreate.errorTitle'), message: t('recruiter.skillTreeCreate.errorMessage') });
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-8 w-8 animate-spin text-purple-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">{editId ? t('recruiter.skillTreeCreate.editTitle') : t('recruiter.skillTreeCreate.createTitle')}</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{t('recruiter.skillTreeCreate.subtitle')}</p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="ghost" leftIcon={<Eye className="h-4 w-4" />} onClick={() => setPreview(!preview)} className="font-medium">
            {preview ? t('recruiter.skillTreeCreate.editMode') : t('recruiter.skillTreeCreate.preview')}
          </Button>
          <Button variant="outline" leftIcon={isGenerating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wand2 className="h-4 w-4" />} onClick={handleGenerateAI} disabled={isGenerating} className="font-medium">
            {isGenerating ? t('recruiter.skillTreeCreate.generating') : t('recruiter.skillTreeCreate.aiGenerate')}
          </Button>
          <Button variant="primary" leftIcon={isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} onClick={handleSave} disabled={isSaving} className="font-bold shadow-md shadow-purple-500/25">
            {isSaving ? t('recruiter.skillTreeCreate.saving') : editId ? t('recruiter.skillTreeCreate.saveChanges') : t('recruiter.skillTreeCreate.saveRubric')}
          </Button>
        </div>
      </div>

      <Card className="glass-panel border-purple-200/50">
        <CardContent className="p-5">
          <div className="flex items-center gap-4 mb-6">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-100 dark:bg-purple-500/20 text-purple-600 dark:text-purple-400">
              <TreePine className="h-5 w-5" />
            </div>
            <Input
              placeholder={t('recruiter.skillTreeCreate.rubricNamePlaceholder')}
              value={treeName}
              onChange={(e) => setTreeName(e.target.value)}
              className="flex-1 text-lg font-bold border-purple-200 dark:border-purple-700"
            />
          </div>

          <div className="mb-5">
            <Input
              placeholder={t('recruiter.skillTreeCreate.descriptionPlaceholder')}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="border-purple-200 dark:border-purple-700"
            />
          </div>

          {preview ? (
            <div className="p-6 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10">
              <h3 className="text-lg font-extrabold text-gray-900 dark:text-white mb-4">{treeName || t('recruiter.skillTreeCreate.rubricPreview')}</h3>
              {root.children.length > 0 ? (
                <div className="space-y-4">{root.children.map(c => renderPreviewNode(c))}</div>
              ) : (
                <p className="text-sm text-gray-400 dark:text-gray-500 italic">{t('recruiter.skillTreeCreate.noCategoriesAdded')}</p>
              )}
            </div>
          ) : (
            <div className="p-6 rounded-xl bg-white/60 dark:bg-white/[0.02] border border-purple-100 dark:border-white/10">
              <div className="flex items-center gap-3 mb-6">
                <Layers className="h-5 w-5 text-purple-500" />
                <span className="text-sm font-bold text-gray-700 dark:text-gray-300">{t('recruiter.skillTreeCreate.rubricBuilder')}</span>
                <span className="text-xs text-gray-400">{t('recruiter.skillTreeCreate.rubricBuilderDesc')}</span>
              </div>
              {renderNode(root)}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
