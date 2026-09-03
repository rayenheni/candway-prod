import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router';
import { motion } from 'framer-motion';
import { customToast } from '@/shared/components/ui/toast';
import { cn } from '@/utils/cn';
import apiClient from '@/lib/api-client';
import { Bot, User, Send, Pause, Play, ArrowLeft, Loader2, CheckCircle, BarChart3 } from 'lucide-react';

interface Message {
  id: string;
  sender: 'ai' | 'user';
  text: string;
  score?: number;
}

interface ChatResponse {
  reply: string;
  type: 'question' | 'complete' | 'wait' | 'duplicate' | 'warning';
  current_score?: number;
  current_question?: number;
  time_left?: number;
  progress?: { current: number; total: number; percentage: number };
  is_complete?: boolean;
  skills?: Record<string, number>;
  feedback?: string;
  score_label?: string;
}

function formatTimeLeft(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}`;
}

function hasGuestSession(): boolean {
  return document.cookie.split(';').some(c => c.trim().startsWith('logged_in=true'));
}

export default function InterviewRoomPage() {
  const navigate = useNavigate();
  const { sessionId } = useParams();
  const appId = sessionId || localStorage.getItem('active_app_id') || '';
  const isGuest = hasGuestSession();

  // Guests cannot access /interviews (role-guarded) — always take them to the
  // (now guest-allowed) analysis page, or to login when there is no app.
  const goPostInterview = useCallback((targetId?: string) => {
    const target = targetId || appId;
    if (target) {
      navigate(`/interviews/${target}/analysis`);
    } else {
      navigate(isGuest ? '/auth/login' : '/interviews');
    }
  }, [appId, isGuest, navigate]);

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [progress, setProgress] = useState({ current: 0, total: 15, percentage: 0 });
  const [currentScore, setCurrentScore] = useState<number | null>(null);
  const [timeLeft, setTimeLeft] = useState<number | null>(null);
  const [isComplete, setIsComplete] = useState(false);
  const [showStats, setShowStats] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const didAutoStart = useRef(false);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (timeLeft == null || timeLeft <= 0 || isComplete || isPaused) return;
    const t = setInterval(() => {
      setTimeLeft(prev => {
        if (prev == null || prev <= 0) return prev;
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(t);
  }, [timeLeft, isComplete, isPaused]);

  useEffect(() => {
    if (timeLeft != null && timeLeft <= 0 && !isComplete) {
      // Notify the backend so the session is marked expired instead of
      // staying in_progress forever.
      apiClient.post<any>('/ai/interview/end', { application_id: parseInt(appId), reason: 'timeout' })
        .catch(() => {});
      customToast({ type: 'error', title: 'Interview Expired', message: 'Time ran out. Redirecting...' });
      goPostInterview();
    }
  }, [timeLeft, isComplete, appId, isGuest, goPostInterview]);

  const sendMessage = useCallback(async (text: string) => {
    if (!appId) {
      customToast({ type: 'error', title: 'Error', message: 'No active interview session.' });
      goPostInterview();
      return;
    }
    setIsProcessing(true);
    try {
      const res = await apiClient.post<ChatResponse>('/ai/interview/chat', {
        candidate_id: parseInt(appId),
        message: text,
        language: 'English',
        session_id: sessionId ? parseInt(sessionId) : undefined,
      });
      if (res.feedback) {
        customToast({ type: 'info', title: 'Feedback', message: res.feedback, duration: 7500 });
      }
      if (res.type === 'complete') {
        setIsComplete(true);
        localStorage.removeItem('active_app_id');
        localStorage.removeItem('active_session_id');
      }
      if (res.progress) {
        setProgress(res.progress);
      }
      if (res.current_score != null) {
        setCurrentScore(res.current_score);
      }
      if (res.time_left != null) {
        setTimeLeft(res.time_left);
      }
      setMessages(prev => [...prev, { id: `ai-${Date.now()}`, sender: 'ai', text: res.reply, score: res.current_score }]);
      return res;
    } catch (err: any) {
      const detail = err?.message || 'Failed to communicate with AI.';
      if (err?.status === 410) {
        customToast({ type: 'error', title: 'Interview Expired', message: 'Time ran out. Redirecting...' });
        goPostInterview();
      } else if (err?.status === 409) {
        customToast({ type: 'info', title: 'Already Completed', message: 'This interview is already finished.' });
        navigate(`/interviews/${appId}/analysis`);
      } else {
        customToast({ type: 'error', title: 'Error', message: detail });
      }
    } finally {
      setIsProcessing(false);
    }
  }, [appId, navigate, sessionId, isGuest, goPostInterview]);

  useEffect(() => {
    if (!appId) {
      customToast({ type: 'error', title: 'Error', message: 'No interview session found.' });
      goPostInterview();
      return;
    }
    apiClient.post<{
      can_resume: boolean;
      history?: Array<{role: string; content: string}>;
      current_score?: number | null;
      progress?: number;
      total_questions?: number;
      time_left?: number;
    }>('/ai/interview/resume', { application_id: parseInt(appId) })
      .then(data => {
        if (data.time_left != null) setTimeLeft(data.time_left);
        if (data.can_resume && data.history?.length) {
          const restored: Message[] = data.history.map((h, i) => ({
            id: `hist-${i}`,
            sender: h.role === 'assistant' ? 'ai' : 'user',
            text: h.content,
          }));
          setMessages(restored);
          if (data.current_score != null) setCurrentScore(data.current_score);
          if (data.progress != null && data.total_questions) {
            setProgress({
              current: data.progress,
              total: data.total_questions,
              percentage: Math.round((data.progress / data.total_questions) * 100),
            });
          }
        }
      })
      .catch(() => {
        customToast({ type: 'warning', title: 'Resume Failed', message: 'Could not restore previous session. Starting fresh.' });
      })
      .finally(() => {
        setIsLoading(false);
        if (!didAutoStart.current) {
          didAutoStart.current = true;
          sendMessage('ready');
        }
      });
  }, [appId, sendMessage, navigate]);

  const handleSend = () => {
    if (!input.trim() || isProcessing || isComplete || isPaused) return;
    const text = input.trim();
    setMessages(prev => [...prev, { id: `user-${Date.now()}`, sender: 'user', text }]);
    setInput('');
    sendMessage(text);
  };

  const togglePause = useCallback(async () => {
    if (!appId) return;
    const appIdNum = parseInt(appId);
    if (!isPaused) {
      // Pause: persist the remaining time so the backend countdown is frozen.
      const snapshot = timeLeft ?? 1800;
      try {
        await apiClient.post<any>('/ai/interview/pause', { application_id: appIdNum, time_left: snapshot });
      } catch (e) {
        console.warn('Failed to persist pause state to server:', e);
      }
      setIsPaused(true);
      customToast({ type: 'info', title: 'Interview Paused', message: 'Timer stopped. Click play to resume.' });
    } else {
      // Resume: reopen the session on the backend (resets the countdown clock).
      try {
        await apiClient.post<any>('/ai/interview/resume', { application_id: appIdNum });
      } catch (e) {
        console.warn('Failed to persist resume state to server:', e);
      }
      setIsPaused(false);
      customToast({ type: 'info', title: 'Interview Resumed', message: 'Timer resumed. Good luck!' });
    }
  }, [appId, isPaused, timeLeft]);

  const handleEnd = useCallback(async () => {
    const appIdNum = parseInt(appId);
    if (!isComplete && appIdNum) {
      try {
        await apiClient.post<any>('/ai/interview/end', { application_id: appIdNum, reason: 'candidate_ended' });
      } catch (err: any) {
        if (err?.status === 409) {
          // already completed — fine
        }
      }
    }
    localStorage.removeItem('active_app_id');
    localStorage.removeItem('active_session_id');
    navigate(`/interviews/${appId}/analysis`);
  }, [appId, isComplete, navigate]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-dvh bg-white dark:bg-[#0D0A1A]">
        <Loader2 className="h-8 w-8 text-violet-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-dvh w-full overflow-hidden bg-white dark:bg-[#0D0A1A] safe-area-bottom">
      <header className="flex items-center justify-between gap-2 px-3 sm:px-6 py-2.5 sm:py-3 border-b border-gray-100 dark:border-white/[0.06] bg-white dark:bg-[#0D0A1A] shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <button onClick={() => goPostInterview()} className="h-9 w-9 rounded-xl bg-gray-100 dark:bg-white/[0.06] flex items-center justify-center text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-white/[0.1] transition-colors shrink-0 md:hidden">
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div className="flex items-center gap-1.5">
            <span className="text-lg sm:text-xl font-extrabold text-gray-900 dark:text-white tracking-tight">Candway</span>
            <span className="h-2 w-2 rounded-full bg-violet-600 hidden sm:inline-block" />
          </div>
          <div className="hidden sm:flex items-center gap-1.5 ml-1">
            <span className="text-sm font-medium text-gray-400">/</span>
            <button onClick={() => goPostInterview()} className="text-sm font-medium text-violet-600 dark:text-violet-400 hover:underline">Interviews</button>
            <span className="text-sm font-medium text-gray-400">/</span>
            <span className="text-sm font-semibold text-gray-900 dark:text-white truncate max-w-[120px] sm:max-w-[200px]">AI Interview</span>
          </div>
        </div>

        <button onClick={() => setShowStats(s => !s)} className="h-9 w-9 rounded-xl bg-gray-100 dark:bg-white/[0.06] flex items-center justify-center text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-white/[0.1] transition-colors sm:hidden shrink-0">
          <BarChart3 className="h-4 w-4" />
        </button>

        <div className="hidden sm:flex items-center gap-0 rounded-2xl bg-gray-50 dark:bg-white/[0.04] px-1 py-2 shrink-0">
          <div className="px-4 lg:px-5 text-center">
            <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400">Question</div>
            <div className="text-lg lg:text-xl font-extrabold text-gray-900 dark:text-white">
              {String(progress.current).padStart(2, '0')}
              <span className="text-xs lg:text-sm font-semibold text-gray-400"> /{progress.total}</span>
            </div>
          </div>
          <div className="h-8 w-px bg-gray-200 dark:bg-white/10" />
          <div className="px-4 lg:px-5 text-center">
            <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400">Score</div>
            <div className={cn('text-lg lg:text-xl font-extrabold', currentScore != null ? 'text-violet-600' : 'text-gray-400')}>
              {currentScore != null ? Math.round(currentScore) : '--'}
            </div>
          </div>
          <div className="h-8 w-px bg-gray-200 dark:bg-white/10" />
          <div className="px-4 lg:px-5 text-center">
            <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400">Time Left</div>
            <div className={cn('text-lg lg:text-xl font-extrabold tabular-nums', timeLeft != null && timeLeft <= 300 ? 'text-red-500' : 'text-gray-900 dark:text-white')}>
              {timeLeft != null ? formatTimeLeft(timeLeft) : '--:--'}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <span className="hidden sm:inline text-xs font-medium text-gray-400">
            {progress.current}/{progress.total}
          </span>
          <button onClick={togglePause}
            className="h-9 w-9 sm:h-10 sm:w-10 rounded-xl bg-violet-600 hover:bg-violet-700 flex items-center justify-center text-white shadow-md shadow-violet-500/25 transition-colors">
            {isPaused ? <Play className="h-4 w-4 fill-current ml-0.5" /> : <Pause className="h-4 w-4 fill-current" />}
          </button>
          <button onClick={handleEnd}
            className={cn(
              'h-9 sm:h-10 rounded-xl text-white text-xs sm:text-sm font-bold transition-colors px-3 sm:px-4',
              isComplete ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-red-500 hover:bg-red-600'
            )}>
            {isComplete ? 'Analysis' : 'End'}
          </button>
        </div>
      </header>

      {showStats && (
        <div className="flex sm:hidden items-center justify-around gap-2 px-3 py-2 border-b border-gray-100 dark:border-white/[0.06] bg-gray-50 dark:bg-white/[0.02]">
          <div className="text-center">
            <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400">Question</div>
            <div className="text-lg font-extrabold text-gray-900 dark:text-white">
              {String(progress.current).padStart(2, '0')}
              <span className="text-xs font-semibold text-gray-400"> /{progress.total}</span>
            </div>
          </div>
          <div className="h-6 w-px bg-gray-200 dark:bg-white/10" />
          <div className="text-center">
            <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400">Score</div>
            <div className={cn('text-lg font-extrabold', currentScore != null ? 'text-violet-600' : 'text-gray-400')}>
              {currentScore != null ? Math.round(currentScore) : '--'}
            </div>
          </div>
          <div className="h-6 w-px bg-gray-200 dark:bg-white/10" />
          <div className="text-center">
            <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400">Time Left</div>
            <div className={cn('text-lg font-extrabold tabular-nums', timeLeft != null && timeLeft <= 300 ? 'text-red-500' : 'text-gray-900 dark:text-white')}>
              {timeLeft != null ? formatTimeLeft(timeLeft) : '--:--'}
            </div>
          </div>
          <div className="h-6 w-px bg-gray-200 dark:bg-white/10" />
          <div className="text-center">
            <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400">Progress</div>
            <div className="w-24 h-2 bg-gray-200 dark:bg-white/10 rounded-full mt-1 overflow-hidden mx-auto">
              <div className="h-full bg-violet-600 rounded-full transition-all duration-500" style={{ width: `${progress.percentage}%` }} />
            </div>
          </div>
        </div>
      )}

      <div className="flex-1 flex overflow-hidden">
        <div className="flex-1 flex flex-col">
          <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 sm:px-6 py-4 sm:py-6 space-y-3 sm:space-y-4">
            {messages.length === 0 && (
              <div className="flex items-center justify-center h-full">
                <div className="text-center">
                  <Bot className="h-10 w-10 sm:h-12 sm:w-12 text-violet-600 mx-auto mb-3 sm:mb-4" />
                  <h2 className="text-lg sm:text-xl font-bold text-gray-900 dark:text-white mb-1 sm:mb-2">AI Interview Ready</h2>
                  <p className="text-sm sm:text-base text-gray-500">Your first question is loading...</p>
                </div>
              </div>
            )}
            {messages.map((msg) => (
              <motion.div key={msg.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                className={cn('flex gap-2 sm:gap-3', msg.sender === 'user' ? 'justify-end' : 'justify-start')}>
                {msg.sender === 'ai' && (
                  <div className="h-7 w-7 sm:h-8 sm:w-8 rounded-full bg-violet-100 dark:bg-violet-500/20 flex items-center justify-center shrink-0 mt-1">
                    <Bot className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-violet-600" />
                  </div>
                )}
                <div className={cn('rounded-2xl px-3 sm:px-4 py-2 sm:py-2.5',
                  msg.sender === 'user'
                    ? 'bg-violet-600 text-white max-w-[85%] sm:max-w-[70%]'
                    : 'bg-gray-100 dark:bg-white/[0.06] text-gray-900 dark:text-white max-w-[90%] sm:max-w-[75%]'
                )}>
                  <p className="text-sm sm:text-[15px] whitespace-pre-wrap leading-relaxed">{msg.text}</p>
                  {msg.score != null && (
                    <p className="text-xs mt-1 opacity-60">Score: {Math.round(msg.score)}</p>
                  )}
                </div>
                {msg.sender === 'user' && (
                  <div className="h-7 w-7 sm:h-8 sm:w-8 rounded-full bg-gray-200 dark:bg-white/10 flex items-center justify-center shrink-0 mt-1">
                    <User className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-gray-600" />
                  </div>
                )}
              </motion.div>
            ))}
            {isProcessing && (
              <div className="flex gap-2 sm:gap-3">
                <div className="h-7 w-7 sm:h-8 sm:w-8 rounded-full bg-violet-100 dark:bg-violet-500/20 flex items-center justify-center shrink-0">
                  <Bot className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-violet-600" />
                </div>
                <div className="bg-gray-100 dark:bg-white/[0.06] rounded-2xl px-4 py-3">
                  <div className="flex gap-1">
                    <span className="h-2 w-2 rounded-full bg-gray-400 animate-bounce" />
                    <span className="h-2 w-2 rounded-full bg-gray-400 animate-bounce delay-100" />
                    <span className="h-2 w-2 rounded-full bg-gray-400 animate-bounce delay-200" />
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="border-t border-gray-100 dark:border-white/[0.06] bg-white dark:bg-[#0D0A1A] p-3 sm:p-4">
            <div className="flex items-center gap-2 sm:gap-3 max-w-4xl mx-auto">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
                placeholder={isComplete ? 'Interview complete!' : isPaused ? 'Interview paused' : 'Type your response...'}
                disabled={isProcessing || isComplete || isPaused}
                className="flex-1 px-3 sm:px-4 py-2.5 sm:py-3 rounded-xl sm:rounded-2xl bg-gray-50 dark:bg-white/[0.04] border border-gray-200 dark:border-white/10 text-sm sm:text-[15px] text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-violet-500/30 transition-all disabled:opacity-50 min-h-[42px] sm:min-h-[48px]"
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || isProcessing || isComplete}
                className="h-[42px] w-[42px] sm:h-11 sm:w-11 rounded-xl bg-violet-600 hover:bg-violet-700 flex items-center justify-center text-white disabled:opacity-50 transition-colors shrink-0"
              >
                {isComplete ? <CheckCircle className="h-4 w-4" /> : <Send className="h-4 w-4" />}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
