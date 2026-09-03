class SourcingUI {
    constructor() {
        this.selectedJobId = null;
        this.selectedCandidates = new Set();
        this.currentResults = [];
        this.isProcessing = false;
        this.filters = { source: '', min_score: 0 };
        this.init();
    }

    init() {
        this.loadJobs();
        this.bindEvents();
    }

    async loadJobs() {
        try {
            const data = await window.fetchAPI('/recruiter/jobs/my?per_page=50');
            const jobs = data.jobs || data || [];
            const select = document.getElementById('job-select');
            if (!select) return;
            XSS.safeSetHTML(select, '<option value="">-- Select a job --</option>' +
                jobs.map(j => `<option value="${j.id}">${window.escapeHTML(j.title)}</option>`).join(''));
            if (jobs.length > 0) {
                select.value = jobs[0].id;
                this.selectedJobId = jobs[0].id;
                this.loadResults();
            }
        } catch (e) {
            console.error('Failed to load jobs:', e);
        }
    }

    bindEvents() {
        const jobSelect = document.getElementById('job-select');
        if (jobSelect) {
            jobSelect.addEventListener('change', (e) => {
                this.selectedJobId = e.target.value;
                this.selectedCandidates.clear();
                this.currentResults = [];
                if (this.selectedJobId) {
                    this.loadResults();
                } else {
                    this.renderResults([]);
                }
            });
        }

        const sourceFilter = document.getElementById('filter-source');
        if (sourceFilter) {
            sourceFilter.addEventListener('change', (e) => {
                this.filters.source = e.target.value;
                this.applyFilters();
            });
        }

        const scoreFilter = document.getElementById('filter-min-score');
        if (scoreFilter) {
            scoreFilter.addEventListener('input', (e) => {
                this.filters.min_score = parseInt(e.target.value) || 0;
                document.getElementById('score-label').textContent = this.filters.min_score;
                this.applyFilters();
            });
        }

        const sourceBtn = document.getElementById('btn-source');
        if (sourceBtn) {
            sourceBtn.addEventListener('click', () => this.triggerSourcing());
        }

        const bulkInviteBtn = document.getElementById('btn-bulk-invite');
        if (bulkInviteBtn) {
            bulkInviteBtn.addEventListener('click', () => this.bulkInvite());
        }

        const selectAllCheckbox = document.getElementById('select-all');
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', (e) => {
                const checked = e.target.checked;
                document.querySelectorAll('.candidate-select').forEach(cb => {
                    cb.checked = checked;
                    const id = parseInt(cb.dataset.candidateId);
                    if (checked) {
                        this.selectedCandidates.add(id);
                    } else {
                        this.selectedCandidates.delete(id);
                    }
                });
                this.updateBulkButton();
            });
        }
    }

    async triggerSourcing() {
        if (!this.selectedJobId) {
            Components.showToast('Please select a job first', 'warning');
            return;
        }
        if (this.isProcessing) return;

        this.isProcessing = true;
        const btn = document.getElementById('btn-source');
        const progress = document.getElementById('sourcing-progress');

        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Sourcing...';
        progress.classList.remove('hidden');

        try {
            const result = await window.fetchAPI(`/recruiter/sourcing/source/${this.selectedJobId}`, {
                method: 'POST'
            });
            Components.showToast(`Sourcing started for job ID ${this.selectedJobId}`, 'success');
            setTimeout(() => this.loadResults(), 2000);
        } catch (e) {
            Components.showToast(e.message || 'Sourcing failed', 'error');
        } finally {
            this.isProcessing = false;
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-robot"></i> Source Candidates';
            progress.classList.add('hidden');
        }
    }

    async loadResults() {
        if (!this.selectedJobId) return;

        const container = document.getElementById('results-container');
        container.innerHTML = '<div class="text-center py-10 text-slate-400"><i class="fas fa-spinner fa-spin text-2xl"></i><p class="mt-2">Loading results...</p></div>';

        try {
            const data = await window.fetchAPI(`/recruiter/sourcing/results/${this.selectedJobId}`);
            this.currentResults = data.candidates || [];
            this.renderResults(this.currentResults, data.meta);
        } catch (e) {
            container.innerHTML = '<div class="text-center py-10 text-slate-500">No results yet. Click "Source Candidates" to find candidates.</div>';
        }
    }

    applyFilters() {
        let filtered = [...this.currentResults];
        if (this.filters.source) {
            filtered = filtered.filter(c => c.source === this.filters.source);
        }
        if (this.filters.min_score > 0) {
            filtered = filtered.filter(c => (c.match_score || 0) >= this.filters.min_score);
        }
        this.renderResults(filtered);
    }

    renderResults(candidates, meta) {
        const container = document.getElementById('results-container');
        const metaEl = document.getElementById('results-meta');

        if (metaEl && meta) {
            metaEl.innerHTML = `
                <div class="flex flex-wrap gap-4 text-sm">
                    <span class="bg-indigo-50 text-indigo-700 px-3 py-1 rounded-lg font-medium">
                        <i class="fas fa-users mr-1"></i> ${meta.total_found || 0} found
                    </span>
                    <span class="bg-green-50 text-green-700 px-3 py-1 rounded-lg font-medium">
                        <i class="fas fa-star mr-1"></i> Avg: ${meta.avg_score || 0}%
                    </span>
                    <span class="bg-blue-50 text-blue-700 px-3 py-1 rounded-lg font-medium">
                        <i class="fas fa-database mr-1"></i> ${(meta.sources_used || []).join(', ')}
                    </span>
                </div>
            `;
        }

        if (!candidates || candidates.length === 0) {
            container.innerHTML = `
                <div class="col-span-full text-center py-16">
                    <div class="w-20 h-20 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
                        <i class="fas fa-search text-3xl text-slate-300"></i>
                    </div>
                    <h3 class="font-bold text-lg text-slate-600">No candidates found</h3>
                    <p class="text-sm text-slate-400 mt-1">Try sourcing candidates for this job first.</p>
                </div>
            `;
            return;
        }

        container.innerHTML = candidates.map((c, idx) => `
            <div class="candidate-card bg-white rounded-2xl border border-slate-100 p-5 hover:shadow-lg transition cursor-pointer ${c.match_score >= 80 ? 'border-l-4 border-l-green-500' : c.match_score >= 60 ? 'border-l-4 border-l-yellow-400' : ''}" data-candidate-id="${c.id}">
                <div class="flex items-start gap-4">
                    <div class="flex-shrink-0">
                        <input type="checkbox" class="candidate-select w-4 h-4 rounded border-slate-300 text-indigo-600 mt-1" data-candidate-id="${c.id}">
                    </div>
                    <div class="flex-shrink-0">
                        <div class="w-12 h-12 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-bold text-lg">
                            ${(c.name || '?').charAt(0)}
                        </div>
                    </div>
                    <div class="flex-1 min-w-0">
                        <div class="flex items-start justify-between">
                            <div>
                                <h4 class="font-bold text-slate-900 text-base">${window.escapeHTML(c.name)}</h4>
                                <p class="text-sm text-slate-500 mt-0.5 line-clamp-1">${window.escapeHTML(c.headline || '')}</p>
                            </div>
                            <div class="flex items-center gap-2 flex-shrink-0 ml-3">
                                <span class="source-badge source-${c.source} px-2.5 py-1 rounded-lg text-xs font-bold uppercase tracking-wider">
                                    ${c.source}
                                </span>
                                <div class="text-center">
                                    <div class="text-2xl font-black font-outfit ${c.match_score >= 80 ? 'text-green-600' : c.match_score >= 60 ? 'text-yellow-600' : 'text-slate-400'}">${c.match_score || 0}</div>
                                    <div class="text-[8px] uppercase tracking-widest font-bold text-slate-400">Match</div>
                                </div>
                            </div>
                        </div>
                        ${c.location ? `<p class="text-xs text-slate-400 mt-1"><i class="fas fa-map-marker-alt mr-1"></i>${window.escapeHTML(c.location)}</p>` : ''}
                        <div class="flex flex-wrap gap-1.5 mt-2">
                            ${(c.skills || []).slice(0, 5).map(s => `<span class="px-2 py-0.5 bg-slate-100 text-slate-600 text-xs rounded-lg">${window.escapeHTML(s)}</span>`).join('')}
                            ${(c.skills || []).length > 5 ? `<span class="px-2 py-0.5 bg-slate-50 text-slate-400 text-xs rounded-lg">+${c.skills.length - 5}</span>` : ''}
                        </div>
                        <div class="flex items-center gap-2 mt-3">
                            ${c.profile_url ? `<a href="${window.escapeHTML(c.profile_url)}" target="_blank" class="text-xs text-indigo-600 hover:text-indigo-800 font-medium"><i class="fas fa-external-link-alt mr-1"></i>Profile</a>` : ''}
                            <button onclick="sourcingUI.inviteCandidate(${c.id})" class="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-lg transition" ${c.invited_at ? 'disabled' : ''}>
                                ${c.invited_at ? '<i class="fas fa-check mr-1"></i>Invited' : '<i class="fas fa-envelope mr-1"></i>Invite'}
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `).join('');

        document.querySelectorAll('.candidate-select').forEach(cb => {
            cb.addEventListener('change', (e) => {
                const id = parseInt(e.target.dataset.candidateId);
                if (e.target.checked) {
                    this.selectedCandidates.add(id);
                } else {
                    this.selectedCandidates.delete(id);
                }
                this.updateBulkButton();
            });
        });
    }

    updateBulkButton() {
        const btn = document.getElementById('btn-bulk-invite');
        if (!btn) return;
        const count = this.selectedCandidates.size;
        if (count > 0) {
            btn.disabled = false;
            XSS.safeSetHTML(btn, `<i class="fas fa-envelope"></i> Invite ${count} Selected`);
            btn.classList.remove('opacity-50', 'cursor-not-allowed');
        } else {
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-envelope"></i> Bulk Invite';
            btn.classList.add('opacity-50', 'cursor-not-allowed');
        }
    }

    async inviteCandidate(candidateId) {
        try {
            const result = await window.fetchAPI(`/recruiter/sourcing/candidates/${candidateId}/invite`, {
                method: 'POST'
            });
            Components.showToast('Invitation sent!', 'success');
            this.loadResults();
        } catch (e) {
            Components.showToast(e.message || 'Failed to send invitation', 'error');
        }
    }

    async bulkInvite() {
        const ids = Array.from(this.selectedCandidates);
        if (ids.length === 0) {
            Components.showToast('Select candidates first', 'warning');
            return;
        }

        try {
            const result = await window.fetchAPI('/recruiter/sourcing/candidates/bulk-invite', {
                method: 'POST',
                body: JSON.stringify({ candidate_ids: ids })
            });
            Components.showToast(`Invited ${result.invited_count} candidates!`, 'success');
            this.selectedCandidates.clear();
            this.updateBulkButton();
            this.loadResults();
        } catch (e) {
            Components.showToast(e.message || 'Bulk invite failed', 'error');
        }
    }

    async loadStats() {
        try {
            const stats = await window.fetchAPI('/recruiter/sourcing/stats');
            const container = document.getElementById('stats-container');
            if (!container) return;
            container.innerHTML = `
                <div class="grid grid-cols-4 gap-4">
                    <div class="bg-white rounded-xl p-4 border border-slate-100 text-center">
                        <div class="text-2xl font-black text-indigo-600">${stats.total_sourced || 0}</div>
                        <div class="text-xs font-medium text-slate-500">Total Sourced</div>
                    </div>
                    <div class="bg-white rounded-xl p-4 border border-slate-100 text-center">
                        <div class="text-2xl font-black text-blue-600">${stats.total_invited || 0}</div>
                        <div class="text-xs font-medium text-slate-500">Invited</div>
                    </div>
                    <div class="bg-white rounded-xl p-4 border border-slate-100 text-center">
                        <div class="text-2xl font-black text-green-600">${stats.total_responded || 0}</div>
                        <div class="text-xs font-medium text-slate-500">Responded</div>
                    </div>
                    <div class="bg-white rounded-xl p-4 border border-slate-100 text-center">
                        <div class="text-2xl font-black text-amber-600">${stats.response_rate || 0}%</div>
                        <div class="text-xs font-medium text-slate-500">Response Rate</div>
                    </div>
                </div>
            `;
        } catch (e) {
            console.error('Failed to load stats:', e);
        }
    }
}

let sourcingUI;
document.addEventListener('DOMContentLoaded', () => {
    sourcingUI = new SourcingUI();
});
