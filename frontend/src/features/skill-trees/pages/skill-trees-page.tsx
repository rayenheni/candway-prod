import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/utils/cn';
import { Loader2, Zap, Plus, Trash2 } from 'lucide-react';
import { skillTreesService } from '@/services/skill-trees.service';

const TREE_COLORS = [
  'from-blue-500 to-cyan-500',
  'from-purple-500 to-pink-500',
  'from-emerald-500 to-teal-500',
  'from-amber-500 to-orange-500',
  'from-rose-500 to-red-500',
  'from-indigo-500 to-violet-500',
];

const NODE_X = [10, 30, 20, 40, 30, 50];
const NODE_Y = [20, 20, 40, 40, 60, 60];

interface TreeCard {
  id: number;
  name: string;
  description: string;
  skills: number;
  candidates: number;
  color: string;
}

interface SkillNode {
  id: string;
  name: string;
  level: number;
  category: string;
  x: number;
  y: number;
}

export default function SkillTreesPage() {
  const navigate = useNavigate();
  const [trees, setTrees] = useState<TreeCard[]>([]);
  const [nodes, setNodes] = useState<SkillNode[]>([]);
  const [selectedTreeName, setSelectedTreeName] = useState('Skill Tree');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<number | null>(null);

  const loadTreeDetail = useCallback(async (id: number, name?: string) => {
    try {
      const detail = await skillTreesService.get(id);
      setSelectedTreeName(name ?? 'Skill Tree');
      const rawCats = detail?.categories;
      const cats = Array.isArray(rawCats) ? (rawCats as Record<string, unknown>[]) : [];
      if (cats.length > 0) {
        setNodes(
          cats.map((c, i) => ({
            id: String(c.id ?? `cat-${i}`),
            name: (c.name as string) || `Category ${i + 1}`,
            level: (c.level as number) || (i % 3) + 1,
            category: (c.category as string) || (c.name as string) || '',
            x: NODE_X[i % NODE_X.length],
            y: NODE_Y[i % NODE_Y.length],
          }))
        );
        return;
      }
      const rawSkills = detail?.skills ?? detail?.nodes;
      const skills = Array.isArray(rawSkills) ? (rawSkills as Record<string, unknown>[]) : [];
      if (skills.length > 0) {
        setNodes(
          skills.map((s, i) => ({
            id: String(s.id ?? `skill-${i}`),
            name: (s.name as string) || '',
            level: (s.level as number) || (i % 3) + 1,
            category: (s.category as string) || '',
            x: NODE_X[i % NODE_X.length],
            y: NODE_Y[i % NODE_Y.length],
          }))
        );
        return;
      }
      setNodes([]);
    } catch {
      setNodes([]);
    }
  }, []);

  const fetchTrees = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { skill_trees } = await skillTreesService.list();
      const mapped: TreeCard[] = (skill_trees || []).map((t, i) => ({
        id: t.id as number,
        name: (t.name as string) || (t.title as string) || '',
        description: (t.description as string) || '',
        skills: (t.skill_count as number) || 0,
        candidates: 0,
        color: TREE_COLORS[i % TREE_COLORS.length],
      }));
      setTrees(mapped);
      if (mapped.length > 0) {
        loadTreeDetail(mapped[0].id, mapped[0].name);
      }
    } catch {
      setError('Failed to load skill trees');
    } finally {
      setLoading(false);
    }
  }, [loadTreeDetail]);

  useEffect(() => {
    fetchTrees();
  }, [fetchTrees]);

  const handleDelete = useCallback(async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    setDeleting(id);
    try {
      await skillTreesService.delete(id);
      setTrees(prev => prev.filter(t => t.id !== id));
    } catch {
      setError('Failed to delete skill tree');
    } finally {
      setDeleting(null);
    }
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <p className="text-red-500">{error}</p>
        <Button variant="outline" onClick={fetchTrees}>Retry</Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Skill Trees</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Visualize skill progression paths and requirements
          </p>
        </div>
        <Button variant="primary" leftIcon={<Plus className="h-4 w-4" />} onClick={() => navigate('/skill-tree-create')}>Create Skill Tree</Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {trees.map((tree, i) => (
          <motion.div
            key={tree.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: i * 0.05 }}
          >
            <Card hoverable className="cursor-pointer h-full">
              <div className={cn('h-2 rounded-t-xl bg-gradient-to-r', tree.color)} />
              <CardContent>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-1">{tree.name}</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">{tree.description}</p>
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-1.5 text-sm text-gray-600 dark:text-gray-400">
                    <Zap className="h-4 w-4" />
                    {tree.skills} skills
                  </div>
                  <div className="flex items-center gap-1.5 text-sm text-gray-600 dark:text-gray-400">
                    {tree.candidates} candidates
                  </div>
                  <div className="ml-auto">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => handleDelete(tree.id, e)}
                      disabled={deleting === tree.id}
                    >
                      {deleting === tree.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Trash2 className="h-4 w-4 text-red-500" />
                      )}
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{selectedTreeName} Tree</CardTitle>
          <CardDescription>Skill progression visualization</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="relative h-[400px] bg-gray-50 dark:bg-white/[0.02] rounded-xl overflow-hidden">
            {nodes.length > 1 && (
              <svg className="absolute inset-0 w-full h-full">
                {nodes.slice(0, -1).map((n, i) => {
                  const next = nodes[i + 1];
                  return (
                    <line
                      key={`${n.id}-${next.id}`}
                      x1={`${n.x}%`}
                      y1={`${n.y + 8}%`}
                      x2={`${next.x}%`}
                      y2={`${next.y - 8}%`}
                      className="stroke-gray-200 dark:stroke-white/10"
                      strokeWidth="2"
                    />
                  );
                })}
              </svg>
            )}

            {nodes.map((node, i) => (
              <motion.div
                key={node.id}
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.3, delay: i * 0.1 }}
                className="absolute"
                style={{ left: `${node.x}%`, top: `${node.y}%`, transform: 'translate(-50%, -50%)' }}
              >
                <div className={cn(
                  'flex flex-col items-center gap-1 p-3 rounded-xl shadow-sm border cursor-pointer transition-all hover:shadow-md',
                  node.level === 1
                    ? 'bg-white dark:bg-white/[0.04] border-gray-200 dark:border-white/10'
                    : node.level === 2
                      ? 'bg-blue-50 dark:bg-blue-500/10 border-blue-200 dark:border-blue-500/20'
                      : 'bg-purple-50 dark:bg-purple-500/10 border-purple-200 dark:border-purple-500/20'
                )}>
                  <div className="text-sm font-medium text-gray-900 dark:text-white">{node.name}</div>
                  <Badge variant={node.level === 1 ? 'default' : node.level === 2 ? 'primary' : 'info'} size="sm">
                    Level {node.level}
                  </Badge>
                </div>
              </motion.div>
            ))}

            {nodes.length === 0 && (
              <div className="flex items-center justify-center h-full text-sm text-gray-400">
                No nodes available for this skill tree
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
