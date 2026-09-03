import { useState } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { customToast } from '@/shared/components/ui/toast';
import { cn } from '@/utils/cn';
import { FileText, Plus, Save, Copy, Eye, Trash2, GripVertical, Star, Layers, Wand2, ChevronDown, ChevronUp } from 'lucide-react';
import { adminService } from '@/services/admin.service';

const levelTemplates = ['Unsatisfactory', 'Developing', 'Proficient', 'Distinguished'];

interface Level {
  name: string;
  description: string;
  points: number;
}

interface Criterion {
  id: string;
  name: string;
  weight: number;
  levels: Level[];
}

function createDefaultLevels(): Level[] {
  return levelTemplates.map((name, i) => ({
    name,
    description: '',
    points: (i + 1) * 25,
  }));
}

function createCriterion(): Criterion {
  return { id: crypto.randomUUID?.() ?? Math.random().toString(36).slice(2), name: '', weight: 25, levels: createDefaultLevels() };
}

export default function RubricBuilderPage() {
  const [rubricName, setRubricName] = useState('');
  const [rubricDescription, setRubricDescription] = useState('');
  const [criteria, setCriteria] = useState<Criterion[]>([createCriterion()]);
  const [showPreview, setShowPreview] = useState(false);
  const [collapsedCriteria, setCollapsedCriteria] = useState<Set<string>>(new Set());

  const totalWeight = criteria.reduce((s, c) => s + c.weight, 0);
  const weightValid = Math.abs(totalWeight - 100) < 0.01;

  const addCriterion = () => {
    setCriteria([...criteria, createCriterion()]);
  };

  const removeCriterion = (id: string) => {
    if (criteria.length <= 1) {
      customToast({ type: 'warning', title: 'Minimum Required', message: 'Rubric must have at least one criterion.' });
      return;
    }
    setCriteria(criteria.filter(c => c.id !== id));
  };

  const duplicateCriterion = (criterion: Criterion) => {
    const newCriterion: Criterion = {
      ...criterion,
      id: crypto.randomUUID?.() ?? Math.random().toString(36).slice(2),
      name: criterion.name + ' (Copy)',
    };
    setCriteria([...criteria, newCriterion]);
  };

  const updateCriterion = (id: string, field: keyof Criterion, value: string | number) => {
    setCriteria(criteria.map(c => c.id === id ? { ...c, [field]: value } : c));
  };

  const updateLevel = (criterionId: string, levelIndex: number, field: keyof Level, value: string | number) => {
    setCriteria(criteria.map(c => c.id === criterionId ? {
      ...c,
      levels: c.levels.map((l, i) => i === levelIndex ? { ...l, [field]: value } : l),
    } : c));
  };

  const toggleCollapse = (id: string) => {
    setCollapsedCriteria(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const handleSave = async () => {
    if (!rubricName.trim()) {
      customToast({ type: 'warning', title: 'Validation Error', message: 'Rubric name is required.' });
      return;
    }
    if (!weightValid) {
      customToast({ type: 'warning', title: 'Weight Error', message: `Total weight must equal 100% (currently ${totalWeight}%).` });
      return;
    }
    const rubricData = {
      title: rubricName,
      description: rubricDescription,
      criteria_json: JSON.stringify(criteria.map(c => ({
        name: c.name,
        weight: c.weight,
        levels: c.levels.map(l => ({ name: l.name, description: l.description, points: l.points })),
      }))),
    };
    try {
      await adminService.createRubric(rubricData);
      customToast({ type: 'success', title: 'Rubric Saved', message: 'Rubric has been saved successfully.' });
    } catch (err: any) {
      customToast({ type: 'error', title: 'Save Failed', message: err?.message || 'Could not save rubric.' });
    }
  };

  const maxPoints = criteria.reduce((max, c) => Math.max(max, ...c.levels.map(l => l.points)), 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-100 dark:bg-purple-900/50">
            <FileText className="h-5 w-5 text-purple-600 dark:text-purple-400" />
          </div>
          <div>
            <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">Rubric Builder</h1>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Design evaluation rubrics with scored criteria levels</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" leftIcon={<Eye className="h-4 w-4" />} onClick={() => setShowPreview(!showPreview)}>
            {showPreview ? 'Hide Preview' : 'Preview'}
          </Button>
          <Button variant="primary" leftIcon={<Save className="h-4 w-4" />} onClick={handleSave} className="font-bold shadow-md shadow-purple-500/25">
            Save Rubric
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className={cn("space-y-6", showPreview ? "xl:col-span-2" : "xl:col-span-3")}>
          <Card className="glass-panel border-purple-200/50">
            <CardHeader>
              <CardTitle>Rubric Details</CardTitle>
              <CardDescription>Name and describe your evaluation rubric</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Input label="Rubric Name" placeholder="e.g. Technical Interview Rubric - Full Stack" value={rubricName} onChange={(e) => setRubricName(e.target.value)} />
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Description</label>
                <textarea
                  className="w-full rounded-xl border border-purple-200/60 bg-white/70 p-3 text-sm min-h-[80px] focus:ring-2 focus:ring-purple-500/20 dark:border-white/10 dark:bg-white/5 dark:text-white"
                  placeholder="Describe what this rubric evaluates..."
                  value={rubricDescription}
                  onChange={(e) => setRubricDescription(e.target.value)}
                />
              </div>
            </CardContent>
          </Card>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Layers className="h-5 w-5 text-purple-500" />
              <h2 className="text-lg font-bold text-gray-900 dark:text-white">Criteria ({criteria.length})</h2>
            </div>
            <div className="flex items-center gap-3">
              <span className={cn("text-sm font-bold", weightValid ? "text-emerald-600" : "text-red-500")}>
                Weight: {totalWeight}%
              </span>
              <Button variant="primary" size="sm" leftIcon={<Plus className="h-4 w-4" />} onClick={addCriterion}>
                Add Criterion
              </Button>
            </div>
          </div>

          {criteria.map((criterion, i) => (
            <motion.div
              key={criterion.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25, delay: i * 0.03 }}
            >
              <Card className="glass-panel border-purple-200/50">
                <CardContent className="p-5">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <GripVertical className="h-4 w-4 text-gray-400 cursor-grab" />
                      <Badge variant="primary" className="bg-purple-600 text-white" size="sm">Criterion {i + 1}</Badge>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button variant="ghost" size="xs" onClick={() => toggleCollapse(criterion.id)}>
                        {collapsedCriteria.has(criterion.id) ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
                      </Button>
                      <Button variant="ghost" size="xs" onClick={() => duplicateCriterion(criterion)}>
                        <Copy className="h-3.5 w-3.5 text-purple-500" />
                      </Button>
                      <Button variant="ghost" size="xs" onClick={() => removeCriterion(criterion.id)}>
                        <Trash2 className="h-3.5 w-3.5 text-red-500" />
                      </Button>
                    </div>
                  </div>

                  {!collapsedCriteria.has(criterion.id) && (
                    <div className="space-y-4">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <Input label="Criterion Name" placeholder="e.g. Code Quality" value={criterion.name} onChange={(e) => updateCriterion(criterion.id, 'name', e.target.value)} />
                        <div>
                          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Weight: {criterion.weight}%</label>
                          <input
                            type="range"
                            min={0}
                            max={100}
                            step={5}
                            value={criterion.weight}
                            onChange={(e) => updateCriterion(criterion.id, 'weight', Number(e.target.value))}
                            className="w-full h-2 rounded-lg appearance-none cursor-pointer accent-purple-600 bg-purple-100 dark:bg-white/10"
                          />
                        </div>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                        {criterion.levels.map((level, li) => (
                          <div key={li} className="rounded-xl border border-purple-100 dark:border-white/10 bg-white/50 dark:bg-white/[0.02] p-3 space-y-2">
                            <div className="flex items-center justify-between">
                              <span className="text-xs font-bold text-gray-500 uppercase">{level.name}</span>
                              <div className="flex items-center gap-1">
                                <Star className="h-3 w-3 text-amber-500" />
                                <input
                                  type="number"
                                  min={0}
                                  max={100}
                                  value={level.points}
                                  onChange={(e) => updateLevel(criterion.id, li, 'points', Number(e.target.value))}
                                  className="w-12 text-xs font-bold text-center bg-transparent border-b border-purple-200 dark:border-white/20 outline-none dark:text-white"
                                />
                              </div>
                            </div>
                            <textarea
                              className="w-full rounded-lg border border-purple-100 bg-white/50 p-2 text-xs min-h-[60px] focus:ring-2 focus:ring-purple-500/20 dark:border-white/10 dark:bg-white/[0.03] dark:text-white"
                              placeholder={`Describe ${level.name}...`}
                              value={level.description}
                              onChange={(e) => updateLevel(criterion.id, li, 'description', e.target.value)}
                            />
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          ))}

          <Button variant="outline" leftIcon={<Plus className="h-4 w-4" />} onClick={addCriterion} className="w-full border-dashed border-purple-300 dark:border-purple-500/30">
            Add Criterion
          </Button>
        </div>

        {showPreview && (
          <div className="xl:col-span-1">
            <Card className="glass-panel border-purple-200/50 sticky top-6">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Eye className="h-4 w-4 text-purple-500" />
                  <CardTitle>Live Preview</CardTitle>
                </div>
                <CardDescription>{rubricName || 'Untitled Rubric'} &middot; {criteria.length} criteria</CardDescription>
              </CardHeader>
              <CardContent>
                {rubricDescription && (
                  <p className="text-xs text-gray-500 dark:text-gray-400 mb-4 pb-4 border-b border-purple-100 dark:border-white/10">{rubricDescription}</p>
                )}
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-purple-200 dark:border-white/20">
                        <th className="py-2 pr-3 font-bold text-gray-500 uppercase">Criterion</th>
                        <th className="py-2 pr-3 font-bold text-gray-500 uppercase">Weight</th>
                        {levelTemplates.map((lvl) => (
                          <th key={lvl} className="py-2 pr-2 font-bold text-gray-500 uppercase">{lvl}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {criteria.map((c) => (
                        <tr key={c.id} className="border-b border-purple-50 dark:border-white/[0.04]">
                          <td className="py-2 pr-3 font-bold text-gray-900 dark:text-white">{c.name || 'Unnamed'}</td>
                          <td className="py-2 pr-3 text-purple-600 font-bold">{c.weight}%</td>
                          {c.levels.map((l, li) => (
                            <td key={li} className="py-2 pr-2">
                              <div className="flex flex-col gap-0.5">
                                <span className="font-bold text-amber-600">{l.points}pts</span>
                                <span className="text-[10px] text-gray-500 leading-tight max-w-[120px] truncate">{l.description}</span>
                              </div>
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                    <tfoot>
                      <tr>
                        <td className="py-2 pr-3 font-bold text-gray-500">Total</td>
                        <td className="py-2 pr-3 font-bold text-purple-600">{totalWeight}%</td>
                        <td colSpan={4} className="py-2 text-right">
                          <Badge variant={weightValid ? 'success' : 'danger'} size="sm">
                            {weightValid ? `${maxPoints} max pts` : `${100 - totalWeight}% off`}
                          </Badge>
                        </td>
                      </tr>
                    </tfoot>
                  </table>
                </div>

                <div className="mt-4 p-3 rounded-xl bg-gradient-to-r from-purple-50 to-indigo-50/50 dark:from-purple-950/20 border border-purple-100 dark:border-white/10">
                  <div className="flex items-center gap-2">
                    <Wand2 className="h-4 w-4 text-purple-500" />
                    <span className="text-xs font-bold text-purple-700 dark:text-purple-300">AI Suggestions</span>
                  </div>
                  <p className="text-[11px] text-gray-600 dark:text-gray-400 mt-1">Add each criterion manually — AI-assisted generation is coming soon.</p>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
