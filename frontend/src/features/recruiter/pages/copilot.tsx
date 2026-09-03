import { useState } from 'react';
import { motion } from 'framer-motion';
import { Card } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Avatar } from '@/shared/components/ui/avatar';
import { useLanguage } from '@/contexts/language-context';
import { cn } from '@/utils/cn';
import { customToast } from '@/shared/components/ui/toast';
import { useRecruiterStats } from '@/shared/hooks';
import {
  Sparkles,
  Send,
  Bot,
  Search,
  Briefcase,
  FileText,
  ChevronRight,
  Zap,
  Loader2
} from 'lucide-react';
import apiClient from '@/lib/api-client';

interface CandidateCard {
  id: string | number;
  name?: string;
  role?: string;
  score?: number;
  match_reason?: string;
  skills?: string[];
  status?: string;
}

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  type?: 'text' | 'action_card';
  candidates?: CandidateCard[];
  actions?: { label: string; action?: () => void }[];
}

interface CopilotAction {
  label: string;
  action?: () => void;
}

interface CopilotResponse {
  reply?: string;
  message?: string;
  content?: string;
  type?: string;
  candidates?: CandidateCard[];
  actions?: CopilotAction[];
}

export default function RecruiterCopilotPage() {
  const { t } = useLanguage();
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: '1',
      role: 'assistant',
      content: 'Hello! I am your Candway AI Recruiting Copilot. How can I help you today?',
    }
  ]);
  const [isTyping, setIsTyping] = useState(false);
  const { data: stats } = useRecruiterStats();

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
    };

    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsTyping(true);

    try {
      const response = await apiClient.post<CopilotResponse>('/hiring/chat', { question: input });
      const replyContent = response.reply || response.message || response.content || 'I processed your request.';
      const aiResponse: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: replyContent,
        type: response.type === 'action_card' || (response.candidates && response.candidates.length > 0) ? 'action_card' : 'text',
        candidates: Array.isArray(response.candidates) ? response.candidates : [],
        actions: response.actions,
      };
      setMessages(prev => [...prev, aiResponse]);
    } catch (err: any) {
      customToast({ type: 'error', title: t('common.status'), message: err?.message || 'Failed to get response' });
      const fallbackResponse: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
      };
      setMessages(prev => [...prev, fallbackResponse]);
    } finally {
      setIsTyping(false);
    }
  };

  const suggestions = [
    "Find candidates for open roles",
    "Draft an interview invitation email",
    "Summarize top applicant strengths",
  ];

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-6">
      {/* Sidebar Context Panel */}
      <div className="hidden lg:flex w-80 flex-col gap-6">
        <Card className="glass-panel p-5 border-purple-200/50 dark:border-purple-500/20">
          <div className="flex items-center gap-2 mb-4">
            <Sparkles className="h-5 w-5 text-purple-600 dark:text-purple-400" />
            <h3 className="font-bold text-gray-900 dark:text-white">{t('nav.copilot')}</h3>
          </div>
          <div className="space-y-3">
            <div className="flex items-center gap-3 p-2 rounded-lg hover:bg-white/50 dark:hover:bg-white/5 transition-colors cursor-pointer border border-transparent hover:border-purple-200 dark:hover:border-white/10">
              <div className="h-8 w-8 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center text-blue-600 dark:text-blue-400"><Briefcase className="h-4 w-4" /></div>
              <div className="text-xs font-bold text-gray-700 dark:text-gray-300">{stats?.active_jobs_count ?? '—'} {t('nav.jobs')}</div>
            </div>
            <div className="flex items-center gap-3 p-2 rounded-lg hover:bg-white/50 dark:hover:bg-white/5 transition-colors cursor-pointer border border-transparent hover:border-purple-200 dark:hover:border-white/10">
              <div className="h-8 w-8 rounded-lg bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center text-emerald-600 dark:text-emerald-400"><Search className="h-4 w-4" /></div>
              <div className="text-xs font-bold text-gray-700 dark:text-gray-300">{stats?.total_applications ?? '—'} {t('candidates.candidatesLabel')}</div>
            </div>
            <div className="flex items-center gap-3 p-2 rounded-lg hover:bg-white/50 dark:hover:bg-white/5 transition-colors cursor-pointer border border-transparent hover:border-purple-200 dark:hover:border-white/10">
              <div className="h-8 w-8 rounded-lg bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center text-amber-600 dark:text-amber-400"><FileText className="h-4 w-4" /></div>
              <div className="text-xs font-bold text-gray-700 dark:text-gray-300">{stats?.scheduled_interviews ?? stats?.interviewing ?? '—'} {t('nav.interviews')}</div>
            </div>
          </div>
        </Card>

        <Card className="glass-panel p-5 border-purple-200/50 dark:border-purple-500/20 flex-1 flex flex-col">
          <div className="flex items-center gap-2 mb-4">
            <Zap className="h-5 w-5 text-purple-600 dark:text-purple-400" />
            <h3 className="font-bold text-gray-900 dark:text-white">{t('common.actions')}</h3>
          </div>
          <div className="flex flex-col gap-2">
            {suggestions.map((s, i) => (
              <button 
                key={i}
                onClick={() => setInput(s)}
                className="text-left text-xs font-semibold text-purple-700 dark:text-purple-300 p-2.5 rounded-lg bg-purple-50 dark:bg-purple-900/20 hover:bg-purple-100 dark:hover:bg-purple-800/40 border border-purple-100 dark:border-purple-700/30 transition-colors"
              >
                {s}
              </button>
            ))}
          </div>
        </Card>
      </div>

      {/* Main Chat Interface */}
      <Card className="glass-panel flex-1 flex flex-col border-purple-200/60 dark:border-purple-500/20 overflow-hidden shadow-xl shadow-purple-500/5">
        {/* Header */}
        <div className="p-4 border-b border-purple-100 dark:border-white/10 bg-white/40 dark:bg-white/5 backdrop-blur-md flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-purple-600 to-indigo-600 flex items-center justify-center shadow-md">
            <Bot className="h-5 w-5 text-white" />
          </div>
          <div>
            <h2 className="font-bold text-gray-900 dark:text-white">{t('nav.copilot')}</h2>
            <p className="text-xs font-semibold text-purple-600 dark:text-purple-400">AI</p>
          </div>
        </div>

        {/* Chat Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className={cn("flex gap-4 max-w-[85%]", msg.role === 'user' ? "ml-auto flex-row-reverse" : "mr-auto")}
            >
              <div className="shrink-0">
                {msg.role === 'user' ? (
                  <Avatar name="You" size="sm" className="ring-2 ring-purple-200 dark:ring-purple-900" />
                ) : (
                  <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-purple-500 to-indigo-500 flex items-center justify-center shadow-sm">
                    <Sparkles className="h-4 w-4 text-white" />
                  </div>
                )}
              </div>
              
              <div className="space-y-3">
                <div className={cn(
                  "p-4 rounded-2xl text-sm font-medium shadow-sm leading-relaxed whitespace-pre-wrap",
                  msg.role === 'user' 
                    ? "bg-purple-600 text-white rounded-tr-none" 
                    : "bg-white/80 dark:bg-white/10 border border-purple-100 dark:border-white/10 text-gray-800 dark:text-gray-200 rounded-tl-none backdrop-blur-md"
                )}>
                  {msg.content}
                </div>

                {/* AI Action Cards */}
                {msg.type === 'action_card' && msg.role === 'assistant' && msg.candidates && msg.candidates.length > 0 && (
                  <div className="grid grid-cols-1 gap-2 mt-2">
                    {msg.candidates.map((cand, i) => (
                      <div key={cand.id ?? i} className="flex items-center justify-between p-3 bg-white/60 dark:bg-gray-800/60 backdrop-blur-sm border border-purple-100 dark:border-gray-700 rounded-xl hover:border-purple-300 transition-colors cursor-pointer">
                        <div>
                          <div className="text-sm font-bold text-gray-900 dark:text-white">{cand.name || t('role.candidate')}</div>
                          <div className="text-xs text-gray-500">{cand.role || t('role.candidate')}</div>
                          {cand.match_reason && <div className="text-xs text-gray-500 mt-1 line-clamp-2">{cand.match_reason}</div>}
                        </div>
                        {cand.score != null && (
                          <div className="text-xs font-black bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300 px-2 py-1 rounded-md">
                            {cand.score}% Match
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {/* AI Action Buttons */}
                {msg.actions && (
                  <div className="flex flex-wrap gap-2 pt-1">
                    {msg.actions.map((act, i) => (
                      <Button key={i} variant="outline" size="sm" onClick={act.action} className="text-xs font-bold border-purple-200 text-purple-700 dark:text-purple-300 bg-white/50 dark:bg-white/5 hover:bg-purple-50">
                        {act.label} <ChevronRight className="h-3 w-3 ml-1" />
                      </Button>
                    ))}
                  </div>
                )}
              </div>
            </motion.div>
          ))}
          
          {isTyping && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex gap-4">
               <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-purple-500 to-indigo-500 flex items-center justify-center shadow-sm">
                  <Sparkles className="h-4 w-4 text-white" />
                </div>
                <div className="bg-white/80 dark:bg-white/10 border border-purple-100 dark:border-white/10 rounded-2xl rounded-tl-none p-4 flex items-center gap-1.5">
                  <div className="h-2 w-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <div className="h-2 w-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <div className="h-2 w-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
            </motion.div>
          )}
        </div>

        {/* Input Area */}
        <div className="p-4 bg-white/40 dark:bg-white/5 backdrop-blur-md border-t border-purple-100 dark:border-white/10">
          <div className="relative flex items-center">
            <Input
              placeholder={t('common.search')}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              wrapperClassName="flex-1"
              className="pr-12 py-6 rounded-2xl text-base shadow-inner bg-white/80 dark:bg-black/20 focus:ring-purple-500/30"
            />
            <Button 
              variant="primary" 
              className="absolute right-2 h-10 w-10 p-0 rounded-xl bg-purple-600 hover:bg-purple-700 shadow-md flex items-center justify-center"
              onClick={handleSend}
              disabled={!input.trim() || isTyping}
            >
              {isTyping ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4 -ml-0.5" />}
            </Button>
          </div>
        </div>

      </Card>
    </div>
  );
}
