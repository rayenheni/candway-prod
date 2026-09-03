const CareerChatWidget = {
    conversationId: localStorage.getItem('career_chat_conv_id') || null,
    messageCount: 0,
    isOpen: false,

    init() {
        this._injectStyles();
        this._injectHTML();
        this._attachListeners();
        this._restoreSession();

        if (window.location.pathname.includes('job-details') || window.location.pathname.includes('/jobs')) {
            setTimeout(() => {
                const jobTitle = document.getElementById('job-title')?.textContent || '';
                const ctx = { page: window.location.pathname.includes('job-details') ? 'job_details' : 'jobs' };
                const jobId = new URLSearchParams(window.location.search).get('id');
                if (jobId) ctx.job_id = parseInt(jobId);
                if (jobTitle) ctx.job_title = jobTitle;
                this.context = ctx;
                this.open();
                if (jobTitle) {
                    this._addMessage('ai', `Hi! I see you're looking at the <strong>${this._escapeHTML(jobTitle)}</strong> position. Would you like to learn more or apply?`);
                }
            }, 2000);
        }
    },

    _injectStyles() {
        if (document.getElementById('career-chat-styles')) return;
        const style = document.createElement('style');
        style.id = 'career-chat-styles';
        style.textContent = `
            .ccw-fab {
                position: fixed; bottom: 24px; right: 24px; width: 56px; height: 56px;
                background: linear-gradient(135deg, #6366f1, #8b5cf6); color: white;
                border-radius: 50%; border: none; cursor: pointer; z-index: 9999;
                box-shadow: 0 4px 20px rgba(99,102,241,0.4); transition: all 0.3s ease;
                display: flex; align-items: center; justify-content: center;
            }
            .ccw-fab:hover { transform: scale(1.1); box-shadow: 0 6px 28px rgba(99,102,241,0.5); }
            .ccw-fab svg { width: 24px; height: 24px; }
            .ccw-fab-badge {
                position: absolute; top: -4px; right: -4px; width: 20px; height: 20px;
                background: #ef4444; border-radius: 50%; font-size: 10px;
                display: flex; align-items: center; justify-content: center;
                color: white; font-weight: 700; border: 2px solid white;
            }
            .ccw-panel {
                position: fixed; bottom: 90px; right: 24px; width: 380px; height: 560px;
                background: white; border-radius: 16px; z-index: 9998;
                box-shadow: 0 8px 40px rgba(0,0,0,0.15); display: none;
                flex-direction: column; overflow: hidden; border: 1px solid #e2e8f0;
                transition: all 0.3s ease; max-width: calc(100vw - 48px);
                font-family: 'Instrument Sans', -apple-system, sans-serif;
            }
            .ccw-panel.open { display: flex; animation: ccwFadeIn 0.3s ease; }
            @keyframes ccwFadeIn { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
            .ccw-header {
                padding: 16px 20px; background: linear-gradient(135deg, #6366f1, #8b5cf6);
                color: white; display: flex; align-items: center; justify-content: space-between;
                flex-shrink: 0;
            }
            .ccw-header-left { display: flex; align-items: center; gap: 12px; }
            .ccw-avatar {
                width: 36px; height: 36px; background: rgba(255,255,255,0.2); border-radius: 10px;
                display: flex; align-items: center; justify-content: center;
            }
            .ccw-avatar svg { width: 18px; height: 18px; }
            .ccw-header h3 { margin: 0; font-size: 14px; font-weight: 700; }
            .ccw-status { display: flex; align-items: center; gap: 6px; font-size: 11px; opacity: 0.8; }
            .ccw-status-dot { width: 6px; height: 6px; background: #34d399; border-radius: 50%; animation: ccwPulse 2s infinite; }
            @keyframes ccwPulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
            .ccw-close { background: none; border: none; color: white; cursor: pointer; padding: 4px; opacity: 0.7; }
            .ccw-close:hover { opacity: 1; }
            .ccw-messages { flex: 1; overflow-y: auto; padding: 16px; background: #f8fafc; display: flex; flex-direction: column; gap: 12px; }
            .ccw-msg { max-width: 85%; padding: 10px 14px; border-radius: 14px; font-size: 13px; line-height: 1.5; animation: ccwMsgIn 0.3s ease; word-wrap: break-word; }
            @keyframes ccwMsgIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
            .ccw-msg.ai { background: white; border: 1px solid #e2e8f0; align-self: flex-start; border-bottom-left-radius: 4px; color: #1e293b; }
            .ccw-msg.user { background: #6366f1; color: white; align-self: flex-end; border-bottom-right-radius: 4px; }
            .ccw-msg.system { background: transparent; align-self: center; font-size: 11px; color: #94a3b8; text-align: center; max-width: 100%; }
            .ccw-typing { display: flex; align-items: center; gap: 4px; padding: 10px 14px; background: white; border: 1px solid #e2e8f0; border-radius: 14px; align-self: flex-start; border-bottom-left-radius: 4px; }
            .ccw-typing span { width: 6px; height: 6px; background: #94a3b8; border-radius: 50%; animation: ccwTyping 1.4s infinite; }
            .ccw-typing span:nth-child(2) { animation-delay: 0.2s; }
            .ccw-typing span:nth-child(3) { animation-delay: 0.4s; }
            @keyframes ccwTyping { 0%, 60%, 100% { transform: translateY(0); } 30% { transform: translateY(-6px); } }
            .ccw-quick-replies { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
            .ccw-qr-btn {
                padding: 6px 14px; background: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 20px;
                font-size: 12px; cursor: pointer; color: #475569; transition: all 0.2s; white-space: nowrap;
            }
            .ccw-qr-btn:hover { background: #6366f1; color: white; border-color: #6366f1; }
            .ccw-job-card {
                display: block; padding: 12px; background: white; border: 1px solid #e2e8f0;
                border-radius: 10px; margin-top: 8px; cursor: pointer; transition: all 0.2s;
                text-decoration: none; color: inherit;
            }
            .ccw-job-card:hover { border-color: #6366f1; box-shadow: 0 2px 8px rgba(99,102,241,0.1); }
            .ccw-job-card h4 { margin: 0 0 4px; font-size: 14px; font-weight: 600; color: #1e293b; }
            .ccw-job-card p { margin: 0; font-size: 12px; color: #64748b; }
            .ccw-job-skills { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px; }
            .ccw-job-skills span { padding: 2px 8px; background: #f1f5f9; border-radius: 10px; font-size: 10px; color: #6366f1; }
            .ccw-input-area { padding: 12px 16px; border-top: 1px solid #e2e8f0; background: white; display: flex; gap: 8px; align-items: center; flex-shrink: 0; }
            .ccw-input { flex: 1; padding: 10px 14px; border: 1px solid #e2e8f0; border-radius: 10px; font-size: 13px; outline: none; font-family: inherit; }
            .ccw-input:focus { border-color: #6366f1; box-shadow: 0 0 0 3px rgba(99,102,241,0.1); }
            .ccw-send {
                width: 38px; height: 38px; background: #6366f1; color: white; border: none;
                border-radius: 10px; cursor: pointer; display: flex; align-items: center; justify-content: center;
                transition: all 0.2s; flex-shrink: 0;
            }
            .ccw-send:hover { background: #4f46e5; }
            .ccw-send:disabled { opacity: 0.5; cursor: not-allowed; }
            .ccw-error { color: #ef4444; font-size: 12px; text-align: center; padding: 8px; }
            @media (max-width: 640px) {
                .ccw-panel { right: 8px; bottom: 80px; width: calc(100vw - 16px); height: 480px; }
                .ccw-fab { bottom: 16px; right: 16px; width: 48px; height: 48px; }
            }
            @media (prefers-color-scheme: dark) {
                .ccw-panel { background: #1e293b; border-color: #334155; }
                .ccw-messages { background: #0f172a; }
                .ccw-msg.ai { background: #1e293b; border-color: #334155; color: #e2e8f0; }
                .ccw-header { background: linear-gradient(135deg, #4f46e5, #7c3aed); }
                .ccw-input-area { background: #1e293b; border-color: #334155; }
                .ccw-input { background: #0f172a; border-color: #334155; color: #e2e8f0; }
                .ccw-input:focus { border-color: #6366f1; }
                .ccw-qr-btn { background: #334155; border-color: #475569; color: #cbd5e1; }
                .ccw-qr-btn:hover { background: #6366f1; color: white; }
                .ccw-job-card { background: #1e293b; border-color: #334155; }
                .ccw-job-card h4 { color: #e2e8f0; }
                .ccw-job-skills span { background: #334155; color: #a5b4fc; }
                .ccw-typing { background: #1e293b; border-color: #334155; }
            }
        `;
        document.head.appendChild(style);
    },

    _injectHTML() {
        if (document.getElementById('career-chatbot-root')) return;
        const root = document.createElement('div');
        root.id = 'career-chatbot-root';
        root.innerHTML = `
            <button class="ccw-fab" id="ccw-fab" onclick="CareerChatWidget.toggle()" aria-label="Open chat">
                <svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"/></svg>
            </button>
            <div class="ccw-panel" id="ccw-panel">
                <div class="ccw-header">
                    <div class="ccw-header-left">
                        <div class="ccw-avatar">
                            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
                        </div>
                        <div>
                            <h3>Candway AI</h3>
                            <div class="ccw-status"><span class="ccw-status-dot"></span> Online</div>
                        </div>
                    </div>
                    <button class="ccw-close" onclick="CareerChatWidget.toggle()" aria-label="Close">
                        <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                    </button>
                </div>
                <div class="ccw-messages" id="ccw-messages"></div>
                <div class="ccw-input-area">
                    <input class="ccw-input" id="ccw-input" placeholder="Type your message..." autocomplete="off">
                    <button class="ccw-send" id="ccw-send" onclick="CareerChatWidget.send()" aria-label="Send">
                        <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/></svg>
                    </button>
                </div>
            </div>
        `;
        document.body.appendChild(root);
    },

    _attachListeners() {
        document.getElementById('ccw-input').addEventListener('keydown', (e) => {
            if (e.key === 'Enter') this.send();
        });
    },

    toggle() {
        const panel = document.getElementById('ccw-panel');
        const fab = document.getElementById('ccw-fab');
        this.isOpen = !this.isOpen;
        panel.classList.toggle('open', this.isOpen);
        fab.style.display = this.isOpen ? 'none' : 'flex';
        if (this.isOpen) {
            const msgs = document.getElementById('ccw-messages');
            if (!msgs.children.length) {
                this._addMessage('ai', 'Hi! I\'m Candway AI, your career assistant. I can help you find jobs, answer questions about the company, or even help you apply. What are you looking for?');
                this._addQuickReplies(['Show me open positions', 'Tell me about the company', 'I want to apply']);
            }
            setTimeout(() => document.getElementById('ccw-input').focus(), 300);
        }
    },

    open() {
        if (!this.isOpen) this.toggle();
    },

    close() {
        if (this.isOpen) this.toggle();
    },

    async send() {
        const input = document.getElementById('ccw-input');
        const msg = input.value.trim();
        if (!msg) return;
        input.value = '';
        this._addMessage('user', this._escapeHTML(msg));
        this._showTyping();
        this._clearQuickReplies();

        try {
            const payload = { message: msg };
            if (this.conversationId) payload.conversation_id = this.conversationId;
            if (this.context) payload.context = this.context;

            const res = await fetch('/api/v1/chatbot/message', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]')?.content || '' },
                body: JSON.stringify(payload),
            });

            this._hideTyping();

            if (!res.ok) {
                this._addMessage('ai', 'Sorry, I\'m having trouble connecting. Please try again.');
                return;
            }

            const data = await res.json();
            this.conversationId = data.conversation_id;
            localStorage.setItem('career_chat_conv_id', this.conversationId);

            this._addMessage('ai', data.reply);

            if (data.suggested_jobs && data.suggested_jobs.length) {
                this._renderJobCards(data.suggested_jobs);
            }

            if (data.actions && data.actions.length) {
                this._addQuickReplies(data.actions);
            }

            if (data.captured?.email) {
                this._addMessage('system', '✓ Your information has been saved. A recruiter may reach out.');
            }

        } catch (e) {
            this._hideTyping();
            this._addMessage('ai', 'Connection error. Please try again later.');
        }
    },

    _addMessage(role, html) {
        const container = document.getElementById('ccw-messages');
        const div = document.createElement('div');
        div.className = `ccw-msg ${role}`;
        div.innerHTML = html;
        container.appendChild(div);
        container.scrollTop = container.scrollHeight;
        return div;
    },

    _showTyping() {
        const container = document.getElementById('ccw-messages');
        const div = document.createElement('div');
        div.className = 'ccw-typing';
        div.id = 'ccw-typing-indicator';
        div.innerHTML = '<span></span><span></span><span></span>';
        container.appendChild(div);
        container.scrollTop = container.scrollHeight;
    },

    _hideTyping() {
        const el = document.getElementById('ccw-typing-indicator');
        if (el) el.remove();
    },

    _addQuickReplies(actions) {
        const container = document.getElementById('ccw-messages');
        let wrapper = document.getElementById('ccw-last-qr');
        if (wrapper) wrapper.remove();
        wrapper = document.createElement('div');
        wrapper.id = 'ccw-last-qr';
        wrapper.className = 'ccw-quick-replies';
        actions.forEach(a => {
            const btn = document.createElement('button');
            btn.className = 'ccw-qr-btn';
            btn.textContent = a;
            btn.onclick = () => {
                const input = document.getElementById('ccw-input');
                input.value = a;
                this.send();
            };
            wrapper.appendChild(btn);
        });
        container.appendChild(wrapper);
        container.scrollTop = container.scrollHeight;
    },

    _clearQuickReplies() {
        const el = document.getElementById('ccw-last-qr');
        if (el) el.remove();
    },

    _renderJobCards(jobs) {
        const container = document.getElementById('ccw-messages');
        const wrapper = document.createElement('div');
        wrapper.className = 'ccw-msg ai';
        wrapper.style.maxWidth = '95%';
        XSS.safeSetHTML(wrapper, `<div style="font-size:12px;font-weight:600;color:#6366f1;margin-bottom:8px;">Matching Positions (${jobs.length})</div>`);
        jobs.forEach(j => {
            const skills = j.required_skills ? j.required_skills.split(',').slice(0, 3) : [];
            const card = document.createElement('a');
            card.className = 'ccw-job-card';
            card.href = `/job-details.html?id=${j.id}`;
            card.innerHTML = `
                <h4>${this._escapeHTML(j.title)}</h4>
                <p>${this._escapeHTML(j.company)} · ${this._escapeHTML(j.location || 'Remote')}</p>
                ${skills.length ? `<div class="ccw-job-skills">${skills.map(s => `<span>${this._escapeHTML(s.trim())}</span>`).join('')}</div>` : ''}
                <p style="margin-top:6px;font-size:11px;color:#6366f1;">Click to view details →</p>
            `;
            wrapper.appendChild(card);
        });
        container.appendChild(wrapper);
        container.scrollTop = container.scrollHeight;
    },

    _restoreSession() {
        if (!this.conversationId) {
            this.conversationId = Math.random().toString(36).substr(2, 16);
            localStorage.setItem('career_chat_conv_id', this.conversationId);
        }
        this.context = {};
    },

    _escapeHTML(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
};
window.CareerChatWidget = CareerChatWidget;

document.addEventListener('DOMContentLoaded', () => CareerChatWidget.init());
