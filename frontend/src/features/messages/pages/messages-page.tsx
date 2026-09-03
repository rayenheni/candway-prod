import { useState, useEffect, useRef } from 'react';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Avatar } from '@/shared/components/ui/avatar';
import { cn } from '@/utils/cn';
import { customToast } from '@/shared/components/ui/toast';
import { useLanguage } from '@/contexts/language-context';
import { messagesService } from '@/services/messages.service';
import {
  Search, Send, MoreHorizontal, Phone, Video, Loader2,
} from 'lucide-react';

/* eslint-disable @typescript-eslint/no-explicit-any */

interface ConvData {
  id: number;
  subject?: string;
  type: string;
  last_message_preview?: string;
  last_message_at: string;
  unread_count: number;
  participant: { id?: number; name: string; role: string; avatar_url?: string };
}
interface MsgData {
  id: number;
  sender_id: number;
  sender_name: string;
  content: string;
  created_at: string;
}

export default function MessagesPage() {
  const { t } = useLanguage();
  const [conversations, setConversations] = useState<ConvData[]>([]);
  const [selectedConv, setSelectedConv] = useState<number | null>(null);
  const [messages, setMessages] = useState<MsgData[]>([]);
  const [loadingConv, setLoadingConv] = useState(true);
  const [loadingMsg, setLoadingMsg] = useState(false);
  const [search, setSearch] = useState('');
  const [newMsg, setNewMsg] = useState('');
  const [sending, setSending] = useState(false);
  const msgEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setLoadingConv(true);
    messagesService.getConversations().then((data: any) => {
      setConversations(Array.isArray(data) ? data : []);
    }).catch(() => {
      setConversations([]);
    }).finally(() => setLoadingConv(false));
  }, []);

  useEffect(() => {
    if (!selectedConv) return;
    setLoadingMsg(true);
    Promise.all([
      messagesService.getMessages(String(selectedConv)),
      messagesService.markAsRead(String(selectedConv)),
    ]).then(([msgs]: [any, any]) => {
      setMessages(Array.isArray(msgs) ? msgs : []);
      setConversations(prev => prev.map(c => c.id === selectedConv ? { ...c, unread_count: 0 } : c));
    }).catch(() => setMessages([]))
      .finally(() => setLoadingMsg(false));
  }, [selectedConv]);

  useEffect(() => {
    msgEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!newMsg.trim() || !selectedConv) return;
    setSending(true);
    try {
      const sent: any = await messagesService.sendMessage(String(selectedConv), newMsg.trim());
      setMessages(prev => [...prev, sent as MsgData]);
      setNewMsg('');
    } catch {
      customToast({ type: 'error', title: t('msg.error'), message: t('msg.sendFailed') });
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const filtered = conversations.filter(c =>
    c.participant.name.toLowerCase().includes(search.toLowerCase())
  );

  const selectedConvData = conversations.find(c => c.id === selectedConv);

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-0 rounded-xl overflow-hidden border border-gray-200 dark:border-white/10 bg-white dark:bg-[#0B1120]">
      {/* Sidebar */}
      <div className="w-80 border-r border-gray-200 dark:border-white/10 flex flex-col shrink-0">
        <div className="p-4 border-b border-gray-200 dark:border-white/10">
          <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-3">{t('msg.title')}</h2>
          <Input placeholder={t('msg.searchConversations')} leftIcon={<Search className="h-4 w-4" />} value={search} onChange={e => setSearch(e.target.value)} />
        </div>
        <div className="flex-1 overflow-y-auto">
          {loadingConv ? (
            <div className="flex justify-center py-8"><Loader2 className="h-5 w-5 animate-spin text-purple-600" /></div>
          ) : filtered.length === 0 ? (
            <p className="text-center text-gray-500 text-sm py-8">{t('msg.noConversations')}</p>
          ) : (
            filtered.map(conv => (
              <button key={conv.id} onClick={() => setSelectedConv(conv.id)}
                className={cn('w-full flex items-center gap-3 p-4 hover:bg-gray-50 dark:hover:bg-white/[0.02] transition-colors text-left border-b border-gray-100 dark:border-white/[0.04]',
                  selectedConv === conv.id && 'bg-blue-50 dark:bg-blue-500/5'
                )}>
                <Avatar name={conv.participant.name} size="md" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-gray-900 dark:text-white truncate">{conv.participant.name}</span>
                    <span className="text-xs text-gray-500 shrink-0">{new Date(conv.last_message_at).toLocaleDateString()}</span>
                  </div>
                  <p className="text-xs text-gray-500 truncate mt-0.5">{conv.last_message_preview || t('msg.noMessagesYet')}</p>
                </div>
                {conv.unread_count > 0 && (
                  <Badge variant="primary" size="sm" className="shrink-0">{conv.unread_count}</Badge>
                )}
              </button>
            ))
          )}
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 flex flex-col">
        {!selectedConv ? (
          <div className="flex-1 flex items-center justify-center text-gray-500">
            <div className="text-center">
              <div className="text-4xl mb-4">💬</div>
              <p className="font-medium">{t('msg.selectConversation')}</p>
              <p className="text-sm">{t('msg.selectConversationHint')}</p>
            </div>
          </div>
        ) : (
          <>
            {/* Chat Header */}
            <div className="p-4 border-b border-gray-200 dark:border-white/10 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Avatar name={selectedConvData?.participant.name || ''} size="md" />
                <div>
                  <div className="text-sm font-semibold text-gray-900 dark:text-white">{selectedConvData?.participant.name}</div>
                  <Badge variant="primary" size="sm">{selectedConvData?.participant.role}</Badge>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button variant="ghost" size="sm"><Phone className="h-4 w-4" /></Button>
                <Button variant="ghost" size="sm"><Video className="h-4 w-4" /></Button>
                <Button variant="ghost" size="sm"><MoreHorizontal className="h-4 w-4" /></Button>
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {loadingMsg ? (
                <div className="flex justify-center py-8"><Loader2 className="h-5 w-5 animate-spin text-purple-600" /></div>
              ) : messages.length === 0 ? (
                <p className="text-center text-gray-500 text-sm py-8">{t('msg.noMessagesStart')}</p>
              ) : (
                messages.map(msg => (
                  <div key={msg.id} className={cn('flex', msg.sender_name === 'You' ? 'justify-end' : 'justify-start')}>
                    <div className={cn('max-w-[70%] p-3 rounded-2xl', msg.sender_name === 'You'
                      ? 'bg-blue-600 text-white rounded-br-md'
                      : 'bg-gray-100 dark:bg-white/10 text-gray-900 dark:text-white rounded-bl-md'
                    )}>
                      <p className="text-sm">{msg.content}</p>
                      <p className={cn('text-[10px] mt-1', msg.sender_name === 'You' ? 'text-blue-200' : 'text-gray-400')}>
                        {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </p>
                    </div>
                  </div>
                ))
              )}
              <div ref={msgEndRef} />
            </div>

            {/* Input */}
            <div className="p-4 border-t border-gray-200 dark:border-white/10">
              <div className="flex items-center gap-2">
                <Input value={newMsg} onChange={e => setNewMsg(e.target.value)} onKeyDown={handleKeyDown}
                  placeholder={t('msg.typeMessage')} wrapperClassName="flex-1" />
                <Button variant="primary" size="sm" onClick={handleSend} disabled={sending || !newMsg.trim()}>
                  {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                </Button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
