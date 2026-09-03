const ChatWidget = {
    chatHistory: [],

    init() {
        console.log("Initializing Recruiter Copilot...");
        this._injectHTML();
        this._attachListeners();
        this._checkGlobalQueue();
    },

    _injectHTML() {
        if (document.getElementById('global-chat-widget')) return;

        const html = `
        <button id="global-fab" onclick="ChatWidget.toggle()" class="fixed bottom-6 right-6 w-14 h-14 bg-indigo-600 text-white rounded-full shadow-2xl flex items-center justify-center hover:bg-indigo-700 transition-all z-50 group hover:scale-110 active:scale-95">
            <i class="fas fa-robot text-xl group-hover:animate-bounce"></i>
            <span class="absolute -top-1 -right-1 w-4 h-4 bg-red-500 rounded-full border-2 border-white hidden" id="chat-notification"></span>
        </button>

        <div id="global-chat-widget" class="fixed bottom-24 right-6 w-[420px] h-[600px] bg-white rounded-3xl shadow-2xl border border-slate-100 flex flex-col hidden z-[100] animate-fade-in-up overflow-hidden">
            <div class="p-5 bg-gradient-to-r from-indigo-600 to-purple-600 text-white flex justify-between items-center shrink-0">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center backdrop-blur-md">
                        <i class="fas fa-robot"></i>
                    </div>
                    <div>
                        <h3 class="font-bold text-sm tracking-wide">Recruiter Copilot</h3>
                        <div class="flex items-center gap-1.5">
                            <span class="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse"></span>
                            <span class="text-[10px] opacity-80 font-medium uppercase tracking-widest">AI Agent Online</span>
                        </div>
                    </div>
                </div>
                <button onclick="ChatWidget.toggle()" class="w-8 h-8 flex items-center justify-center hover:bg-white/20 rounded-lg transition-colors">
                    <i class="fas fa-times"></i>
                </button>
            </div>

            <div id="global-chat-actions" class="px-4 py-3 bg-slate-50 border-b border-slate-100 flex gap-2 overflow-x-auto shrink-0">
                <button onclick="ChatWidget._processMessage('Find me Python developers')" class="px-3 py-1.5 bg-white border border-slate-200 rounded-full text-xs font-bold text-indigo-600 hover:bg-indigo-50 hover:border-indigo-200 whitespace-nowrap transition">
                    <i class="fas fa-search mr-1"></i> Find Candidates
                </button>
                <button onclick="ChatWidget._processMessage('Compare top candidates')" class="px-3 py-1.5 bg-white border border-slate-200 rounded-full text-xs font-bold text-indigo-600 hover:bg-indigo-50 hover:border-indigo-200 whitespace-nowrap transition">
                    <i class="fas fa-scale-balanced mr-1"></i> Compare
                </button>
                <button onclick="ChatWidget._processMessage('Show me analytics')" class="px-3 py-1.5 bg-white border border-slate-200 rounded-full text-xs font-bold text-indigo-600 hover:bg-indigo-50 hover:border-indigo-200 whitespace-nowrap transition">
                    <i class="fas fa-chart-bar mr-1"></i> Analytics
                </button>
            </div>

            <div id="global-chat-messages" class="flex-1 overflow-y-auto p-5 space-y-4 custom-scrollbar bg-slate-50/50">
                <div class="flex justify-start">
                    <div class="p-3 text-sm rounded-2xl max-w-[85%] bg-white border border-slate-100 rounded-tl-none shadow-sm">
                        Hello! I'm your AI hiring assistant. How can I help you with your candidates or job postings today?
                    </div>
                </div>
            </div>

            <div id="global-suggested" class="px-4 pb-2 hidden">
                <div class="flex flex-wrap gap-1.5" id="suggested-actions"></div>
            </div>

            <form onsubmit="ChatWidget.sendMessage(event)" class="p-4 bg-white border-t border-slate-100 flex gap-2 items-center">
                <input type="text" id="global-chat-input" placeholder="Ask anything about your pipeline..."
                       class="flex-1 py-3 px-4 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/5 transition-all outline-none">
                <button type="submit" class="w-11 h-11 bg-indigo-600 text-white rounded-xl shadow-lg hover:bg-indigo-700 transition-all flex items-center justify-center">
                    <i class="fas fa-paper-plane text-sm"></i>
                </button>
            </form>
        </div>
        `;
        document.body.insertAdjacentHTML('beforeend', html);
    },

    _attachListeners() {
        window.addEventListener('storage', (e) => {
            if (e.key === 'candway_global_msg') {
                this._checkGlobalQueue();
            }
        });
    },

    _checkGlobalQueue() {
        const raw = localStorage.getItem('candway_global_msg');
        if (!raw) return;
        try {
            const data = JSON.parse(raw);
            if (Date.now() - data.timestamp > 2000) return;
            this.toggle(true);
            this._processMessage(data.message);
            localStorage.removeItem('candway_global_msg');
        } catch (e) {
            console.warn("Copilot failed to parse global message", e);
        }
    },

    toggle(forceOpen = false) {
        const widget = document.getElementById('global-chat-widget');
        const fab = document.getElementById('global-fab');

        if (forceOpen) widget.classList.remove('hidden');
        else widget.classList.toggle('hidden');

        fab.classList.toggle('hidden', !widget.classList.contains('hidden'));

        if (!widget.classList.contains('hidden')) {
            setTimeout(() => document.getElementById('global-chat-input').focus(), 300);
        }
    },

    async sendMessage(e) {
        if (e) e.preventDefault();
        const input = document.getElementById('global-chat-input');
        const msg = input.value.trim();
        if (!msg) return;
        this._processMessage(msg);
        input.value = '';
    },

    async _processMessage(msg) {
        this.addChatMessage('user', this._escapeHTML(msg));
        const loadingId = this.addChatMessage('ai', `<i class="fas fa-circle-notch fa-spin"></i> Thinking...`);

        try {
            const data = await window.fetchAPI('/hiring/chat', {
                method: 'POST',
                body: JSON.stringify({ question: msg, history: this.chatHistory })
            });

            document.getElementById(loadingId)?.remove();

            if (data) {
                this._typewriterReply(data.reply);

                if (data.candidates?.length > 0) {
                    this._renderCandidateCards(data.candidates);
                }

                if (data.suggested_actions?.length > 0) {
                    this._renderSuggestedActions(data.suggested_actions);
                }

                this.chatHistory.push(
                    { role: 'user', content: msg },
                    { role: 'assistant', content: data.reply }
                );
            }
        } catch (e) {
            document.getElementById(loadingId)?.remove();
            this.addChatMessage('ai', 'Connection error. Please try again.');
        }
    },

    _typewriterReply(text) {
        const id = 'msg-' + Math.random().toString(36).substr(2, 9);
        const container = document.getElementById('global-chat-messages');
        const wrapper = document.createElement('div');
        wrapper.className = 'flex w-full justify-start';
        const bubble = document.createElement('div');
        bubble.id = id;
        bubble.className = 'p-3 text-sm rounded-2xl max-w-[85%] bg-white border border-slate-100 shadow-sm rounded-tl-none';
        wrapper.appendChild(bubble);
        container.appendChild(wrapper);

        const el = document.getElementById(id);
        let i = 0;
        const speed = 20;
        function type() {
            if (i < text.length) {
                el.textContent += text.charAt(i);
                i++;
                container.scrollTop = container.scrollHeight;
                setTimeout(type, speed);
            }
        }
        type();

        // Also render markdown-style formatting
        setTimeout(() => {
            el.innerHTML = this._renderMarkdown(text);
        }, text.length * speed + 100);

        return id;
    },

    _renderMarkdown(text) {
        let html = this._escapeHTML(text);
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
        html = html.replace(/`(.*?)`/g, '<code class="bg-slate-100 px-1 rounded text-xs">$1</code>');
        html = html.replace(/\n/g, '<br>');
        html = html.replace(/- (.*?)(<br>|$)/g, '• $1<br>');
        return html;
    },

    _renderCandidateCards(candidates) {
        const cards = candidates.map(c => {
            const skills = c.skills?.length ? c.skills.slice(0, 3).map(s => `<span class="text-[9px] bg-indigo-50 text-indigo-600 px-1.5 py-0.5 rounded-full">${this._escapeHTML(s)}</span>`).join('') : '';
            const matchReason = c.match_reason ? `<p class="text-[10px] text-slate-500 mt-1 line-clamp-2">${this._escapeHTML(c.match_reason)}</p>` : '';
            return `
                <div class="p-3 bg-white border border-slate-100 rounded-xl mb-2 cursor-pointer hover:border-indigo-300 transition-all shadow-sm hover:shadow-md" onclick="window.location.href='/recruiter/candidate?id=${c.id}'">
                    <div class="flex items-start gap-3">
                        <div class="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-bold text-sm shrink-0">${this._escapeHTML((c.name||'C').charAt(0))}</div>
                        <div class="flex-1 min-w-0">
                            <div class="flex items-center justify-between">
                                <h4 class="font-bold text-sm truncate">${this._escapeHTML(c.name)}</h4>
                                <span class="text-xs font-bold ${c.score >= 75 ? 'text-emerald-600' : c.score >= 50 ? 'text-amber-600' : 'text-slate-400'}">${Math.round(c.score)}%</span>
                            </div>
                            <p class="text-[10px] text-slate-500 truncate">${this._escapeHTML(c.role)}</p>
                            ${skills ? `<div class="flex gap-1 mt-1.5 flex-wrap">${skills}</div>` : ''}
                            ${matchReason}
                            <p class="text-[9px] text-slate-400 mt-1">Status: <span class="font-medium capitalize">${c.status || 'pending'}</span></p>
                        </div>
                    </div>
                </div>`;
        }).join('');

        const container = document.getElementById('global-chat-messages');
        const wrapper = document.createElement('div');
        wrapper.className = 'flex w-full justify-start';
        wrapper.innerHTML = `<div class="p-3 text-sm rounded-2xl max-w-[95%] bg-indigo-50 border border-indigo-100 shadow-sm rounded-tl-none">
            <div class="text-xs font-bold text-indigo-600 mb-2 flex items-center gap-2">
                <i class="fas fa-users"></i> Top Matches (${candidates.length})
            </div>
            ${cards}
        </div>`;
        container.appendChild(wrapper);
        container.scrollTop = container.scrollHeight;
    },

    _renderSuggestedActions(actions) {
        const container = document.getElementById('global-suggested');
        const list = document.getElementById('suggested-actions');
        if (!container || !list) return;
        container.classList.remove('hidden');
        list.innerHTML = actions.map(a =>
            `<button onclick="ChatWidget._processMessage('${this._escapeHTML(a)}')" class="px-2.5 py-1 bg-white border border-slate-200 rounded-full text-[10px] font-medium text-slate-600 hover:bg-indigo-50 hover:border-indigo-200 hover:text-indigo-600 transition whitespace-nowrap">${this._escapeHTML(a)}</button>`
        ).join('');
    },

    addChatMessage(role, html) {
        const container = document.getElementById('global-chat-messages');
        const id = 'msg-' + Math.random().toString(36).substr(2, 9);
        const wrapper = document.createElement('div');
        wrapper.className = `flex w-full ${role === 'ai' ? 'justify-start' : 'justify-end'}`;
        const bubble = document.createElement('div');
        bubble.id = id;
        bubble.className = `p-3 text-sm rounded-2xl max-w-[85%] ${role === 'ai' ? 'bg-white border border-slate-100 shadow-sm rounded-tl-none' : 'bg-indigo-600 text-white rounded-tr-none'} animate-fade-in`;
        XSS.safeSetHTML(bubble, html);
        wrapper.appendChild(bubble);
        container.appendChild(wrapper);
        container.scrollTop = container.scrollHeight;
        return id;
    },

    _escapeHTML(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
};

window.sendGlobalMessage = (msg) => {
    localStorage.setItem('candway_global_msg', JSON.stringify({
        timestamp: Date.now(),
        message: msg
    }));
};
