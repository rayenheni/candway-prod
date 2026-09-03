const ChatbotLeads = {
    currentPage: 1,
    pageSize: 20,
    filters: { stage: '', role: '', days: 30 },

    async init() {
        await this.loadLeads();
        this._attachFilters();
    },

    _attachFilters() {
        const stageEl = document.getElementById('filter-stage');
        const roleEl = document.getElementById('filter-role');
        const daysEl = document.getElementById('filter-days');

        if (stageEl) stageEl.addEventListener('change', () => { this.filters.stage = stageEl.value; this.loadLeads(); });
        if (roleEl) roleEl.addEventListener('input', () => { this.filters.role = roleEl.value; this.loadLeads(); });
        if (daysEl) daysEl.addEventListener('change', () => { this.filters.days = parseInt(daysEl.value); this.loadLeads(); });
    },

    async loadLeads() {
        const container = document.getElementById('leads-container');
        if (!container) return;
        container.innerHTML = '<div class="flex justify-center py-12"><div class="w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin"></div></div>';

        try {
            const params = new URLSearchParams({
                limit: this.pageSize,
                offset: (this.currentPage - 1) * this.pageSize,
                days: this.filters.days,
            });
            if (this.filters.stage) params.set('stage', this.filters.stage);
            if (this.filters.role) params.set('role', this.filters.role);

            const res = await fetch(`/api/v1/chatbot/leads?${params}`);
            if (!res.ok) throw new Error('Failed to load leads');
            const data = await res.json();

            this._renderLeads(data.leads, data.total);
        } catch (e) {
            XSS.safeSetHTML(container, `<div class="text-center py-12 text-red-500">Error loading leads: ${XSS.escapeHTML(e.message)}</div>`);
        }
    },

    _renderLeads(leads, total) {
        const container = document.getElementById('leads-container');
        if (!leads.length) {
            container.innerHTML = '<div class="text-center py-12 text-slate-500"><i class="fas fa-inbox text-4xl mb-4 opacity-30"></i><p>No leads found matching your filters.</p></div>';
            return;
        }

        XSS.safeSetHTML(container, `<div class="text-sm text-slate-500 mb-4">${total} lead${total !== 1 ? 's' : ''} found</div>` +
            leads.map(l => this._leadCard(l)).join(''));
    },

    _leadCard(lead) {
        const stageColors = { greeting: 'bg-slate-100 text-slate-600', exploring: 'bg-blue-100 text-blue-600', screening: 'bg-amber-100 text-amber-600', capturing: 'bg-purple-100 text-purple-600', scheduling: 'bg-green-100 text-green-600', complete: 'bg-slate-100 text-slate-500' };
        const stageColor = stageColors[lead.stage] || 'bg-slate-100 text-slate-600';
        const hasInfo = lead.name || lead.email || lead.phone;
        const lastMessages = (lead.message_history || []).slice(-3).map(m => `<div class="text-xs ${m.role === 'user' ? 'text-indigo-600' : 'text-slate-600'}"><span class="font-medium">${m.role === 'user' ? 'You' : 'AI'}:</span> ${this._escapeHTML(m.content?.substring(0, 80))}${m.content?.length > 80 ? '...' : ''}</div>`).join('');

        return `
            <div class="bg-white border border-slate-200 rounded-xl p-5 hover:shadow-md transition-shadow">
                <div class="flex items-start justify-between mb-3">
                    <div class="flex items-center gap-3">
                        <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-bold text-sm">
                            ${(lead.name || '?').charAt(0).toUpperCase()}
                        </div>
                        <div>
                            <h3 class="font-semibold text-sm">${this._escapeHTML(lead.name || 'Anonymous')}</h3>
                            <p class="text-xs text-slate-500">${lead.role_interest ? this._escapeHTML(lead.role_interest) : 'No role specified'}</p>
                        </div>
                    </div>
                    <span class="text-xs font-medium px-2.5 py-1 rounded-full ${stageColor}">${lead.stage}</span>
                </div>

                <div class="grid grid-cols-2 gap-2 mb-3 text-xs">
                    ${lead.email ? `<div class="flex items-center gap-1.5 text-slate-600"><i class="fas fa-envelope text-slate-400 w-3.5"></i>${this._escapeHTML(lead.email)}</div>` : ''}
                    ${lead.phone ? `<div class="flex items-center gap-1.5 text-slate-600"><i class="fas fa-phone text-slate-400 w-3.5"></i>${this._escapeHTML(lead.phone)}</div>` : ''}
                    ${lead.experience_level ? `<div class="flex items-center gap-1.5 text-slate-600"><i class="fas fa-chart-line text-slate-400 w-3.5"></i>${this._escapeHTML(lead.experience_level)}</div>` : ''}
                    ${lead.skills ? `<div class="flex items-center gap-1.5 text-slate-600"><i class="fas fa-code text-slate-400 w-3.5"></i>${this._escapeHTML(lead.skills)}</div>` : ''}
                </div>

                ${lead.message_history?.length ? `<div class="bg-slate-50 rounded-lg p-3 mb-3 space-y-1">${lastMessages}</div>` : ''}

                <div class="flex items-center justify-between text-xs text-slate-400">
                    <span><i class="far fa-clock mr-1"></i>${lead.created_at ? new Date(lead.created_at).toLocaleDateString() : ''}</span>
                    <div class="flex gap-2">
                        ${!lead.contacted_at ? `<button onclick="ChatbotLeads.markContacted(${lead.id})" class="text-indigo-600 hover:text-indigo-800 font-medium">Mark Contacted</button>` : `<span class="text-emerald-600">✓ Contacted</span>`}
                        ${lead.email ? `<a href="mailto:${this._escapeHTML(lead.email)}?subject=Following up from Candway chat" class="text-indigo-600 hover:text-indigo-800 font-medium"><i class="fas fa-reply mr-1"></i>Contact</a>` : ''}
                    </div>
                </div>
            </div>
        `;
    },

    async markContacted(leadId) {
        try {
            const res = await fetch(`/api/v1/chatbot/leads/${leadId}/contacted`, { method: 'POST' });
            if (res.ok) this.loadLeads();
        } catch (e) {
            console.error('Failed to mark contacted:', e);
        }
    },

    _escapeHTML(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
};

document.addEventListener('DOMContentLoaded', () => ChatbotLeads.init());
