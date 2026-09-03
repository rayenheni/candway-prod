const STATUS_MAP = {
    'pending': { label: 'Pending', class: 'bg-slate-100 text-slate-700 border-slate-200' },
    'candidate_created': { label: 'Candidate Created', class: 'bg-blue-100 text-blue-700 border-blue-200' },
    'invited': { label: 'Invited', class: 'bg-indigo-100 text-indigo-700 border-indigo-200' },
    'pending_report': { label: 'Pending Report', class: 'bg-amber-100 text-amber-700 border-amber-200' },
    'report_ready': { label: 'Completed', class: 'bg-teal-100 text-teal-700 border-teal-200' },
    'clear': { label: 'Clear', class: 'bg-emerald-100 text-emerald-700 border-emerald-200' },
    'consider': { label: 'Consider', class: 'bg-orange-100 text-orange-700 border-orange-200' },
    'disputed': { label: 'Disputed', class: 'bg-purple-100 text-purple-700 border-purple-200' },
    'adverse_action': { label: 'Adverse Action', class: 'bg-red-100 text-red-700 border-red-200' },
    'suspended': { label: 'Suspended', class: 'bg-red-100 text-red-700 border-red-200' },
};

const VERDICT_MAP = {
    'clear': { label: 'Clear', class: 'bg-emerald-100 text-emerald-700 border-emerald-200' },
    'consider': { label: 'Consider', class: 'bg-orange-100 text-orange-700 border-orange-200' },
    'suspended': { label: 'Suspended', class: 'bg-red-100 text-red-700 border-red-200' },
};

async function loadStats() {
    try {
        const stats = await window.fetchAPI('/recruiter/background-checks/stats/summary');
        const totalEl = document.getElementById('stat-total');
        const pendingEl = document.getElementById('stat-pending');
        const clearEl = document.getElementById('stat-clear');
        const considerEl = document.getElementById('stat-consider');
        const clearRateEl = document.getElementById('stat-clear-rate');
        if (totalEl) totalEl.textContent = stats.total || 0;
        if (pendingEl) pendingEl.textContent = stats.pending || 0;
        if (clearEl) clearEl.textContent = stats.clear || 0;
        if (considerEl) considerEl.textContent = stats.consider || 0;
        if (clearRateEl) clearRateEl.textContent = (stats.clear_rate || 0) + '%';
    } catch (e) {
        console.error('Failed to load background check stats:', e);
    }
}

async function loadChecks() {
    const container = document.getElementById('checks-container');
    if (!container) return;

    const params = new URLSearchParams();
    const status = document.getElementById('filter-status')?.value;
    const dateFrom = document.getElementById('filter-date-from')?.value;
    const dateTo = document.getElementById('filter-date-to')?.value;

    if (status) params.set('status', status);
    if (dateFrom) params.set('date_from', dateFrom);
    if (dateTo) params.set('date_to', dateTo);

    try {
        const data = await window.fetchAPI(`/recruiter/background-checks?${params.toString()}`);
        const checks = data.results || [];

        if (checks.length === 0) {
            container.innerHTML = `
                <div class="text-center py-16">
                    <div class="w-16 h-16 mx-auto mb-4 rounded-2xl bg-slate-100 flex items-center justify-center">
                        <i class="fas fa-shield-alt text-slate-400 text-2xl"></i>
                    </div>
                    <p class="text-lg font-semibold text-slate-700">No background checks found</p>
                    <p class="text-slate-500 text-sm mt-1">Adjust filters to see more results</p>
                </div>
            `;
            return;
        }

        container.innerHTML = checks.map(check => {
            const statusInfo = STATUS_MAP[check.status] || STATUS_MAP.pending;
            const verdictInfo = check.verdict ? (VERDICT_MAP[check.verdict] || null) : null;
            const created = new Date(check.created_at).toLocaleDateString();
            const completed = check.completed_at ? new Date(check.completed_at).toLocaleDateString() : null;

            return `
                <div class="bg-white rounded-2xl p-6 border-2 border-slate-200 shadow-sm hover:shadow-md transition cursor-pointer" onclick="viewCheckDetail(${check.id})">
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-4">
                            <div class="w-12 h-12 rounded-xl bg-indigo-100 flex items-center justify-center">
                                <i class="fas fa-user text-indigo-600"></i>
                            </div>
                            <div>
                                <h3 class="text-lg font-bold text-slate-900">${SecurityUtils.escapeHTML(check.candidate_name || 'Unknown Candidate')}</h3>
                                <p class="text-sm text-slate-500">${SecurityUtils.escapeHTML(check.candidate_email || '')}</p>
                            </div>
                        </div>
                        <div class="flex items-center gap-3">
                            <span class="px-3 py-1 rounded-full text-xs font-bold border-2 ${statusInfo.class}">
                                ${statusInfo.label}
                            </span>
                            ${verdictInfo ? `<span class="px-3 py-1 rounded-full text-xs font-bold border-2 ${verdictInfo.class}">${verdictInfo.label}</span>` : ''}
                        </div>
                    </div>
                    <div class="flex items-center gap-6 mt-4 text-sm text-slate-500">
                        <span><i class="fas fa-calendar mr-1"></i> Created: ${created}</span>
                        ${completed ? `<span><i class="fas fa-check-circle mr-1"></i> Completed: ${completed}</span>` : ''}
                        <span><i class="fas fa-database mr-1"></i> ${check.provider || 'checkr'}</span>
                    </div>
                </div>
            `;
        }).join('');

    } catch (e) {
        console.error('Failed to load background checks:', e);
        container.innerHTML = `
            <div class="text-center py-16">
                <div class="w-16 h-16 mx-auto mb-4 rounded-2xl bg-red-100 flex items-center justify-center">
                    <i class="fas fa-exclamation-triangle text-red-500 text-2xl"></i>
                </div>
                <p class="text-lg font-semibold text-red-700">Failed to load background checks</p>
                <p class="text-slate-500 text-sm mt-1">Please try refreshing the page</p>
            </div>
        `;
    }
}

async function viewCheckDetail(checkId) {
    window.location.href = `/recruiter/background-check-detail?id=${checkId}`;
}

async function loadCheckDetail() {
    const container = document.getElementById('check-detail-container');
    if (!container) return;

    const params = new URLSearchParams(window.location.search);
    const backgroundCheckId = params.get('id');

    if (!backgroundCheckId) {
        container.innerHTML = `<p class="text-center text-red-500">No background check ID provided</p>`;
        return;
    }

    try {
        const checks = await window.fetchAPI(`/recruiter/background-checks?limit=1000`);
        const allChecks = checks.results || [];
        const check = allChecks.find(c => c.id === parseInt(backgroundCheckId));

        if (!check) {
            container.innerHTML = `<p class="text-center text-slate-500">Background check not found</p>`;
            return;
        }

        const detailed = await window.fetchAPI(`/recruiter/background-checks/${check.application_id}`);
        renderCheckDetail(detailed, container);

    } catch (e) {
        console.error('Failed to load check detail:', e);
        container.innerHTML = `
            <div class="text-center py-16">
                <p class="text-lg font-semibold text-red-700">Failed to load details</p>
            </div>
        `;
    }
}

function renderCheckDetail(check, container) {
    const statusInfo = STATUS_MAP[check.status] || STATUS_MAP.pending;
    const verdictInfo = check.verdict ? (VERDICT_MAP[check.verdict] || null) : null;
    const created = new Date(check.created_at).toLocaleDateString();
    const completed = check.completed_at ? new Date(check.completed_at).toLocaleDateString() : 'In Progress';

    const timeline = (check.status_log || []).map(log => `
        <div class="flex items-start gap-4">
            <div class="flex flex-col items-center">
                <div class="w-3 h-3 rounded-full bg-indigo-600 mt-1.5"></div>
                <div class="w-0.5 flex-1 bg-indigo-200 min-h-[24px]"></div>
            </div>
            <div class="flex-1 pb-6">
                <p class="font-semibold text-slate-900">${STATUS_MAP[log.to_status]?.label || log.to_status}</p>
                <p class="text-sm text-slate-500">${new Date(log.created_at).toLocaleString()}</p>
                ${log.details ? `<p class="text-sm text-slate-400 mt-1">${SecurityUtils.escapeHTML(log.details)}</p>` : ''}
            </div>
        </div>
    `).join('');

    const findingsHtml = (check.findings || []).map(f => {
        const adjColor = f.adjudication === 'clear' ? 'text-emerald-600' : f.adjudication === 'consider' ? 'text-orange-600' : 'text-slate-600';
        return `
            <div class="flex items-center justify-between p-3 bg-slate-50 rounded-xl">
                <div>
                    <p class="font-medium text-slate-900">${SecurityUtils.escapeHTML(f.name || 'Unknown')}</p>
                    <p class="text-sm text-slate-500">${SecurityUtils.escapeHTML(f.text || f.result || '')}</p>
                </div>
                <span class="text-sm font-bold ${adjColor}">${f.adjudication || 'pending'}</span>
            </div>
        `;
    }).join('');

    container.innerHTML = `
        <div class="glass-card p-8 mb-6">
            <div class="flex items-center justify-between mb-6">
                <div class="flex items-center gap-4">
                    <div class="w-16 h-16 rounded-2xl bg-indigo-100 flex items-center justify-center">
                        <i class="fas fa-user text-indigo-600 text-2xl"></i>
                    </div>
                    <div>
                        <h2 class="text-2xl font-extrabold text-slate-900">${SecurityUtils.escapeHTML(check.candidate_name || 'Unknown')}</h2>
                        <p class="text-slate-500">${SecurityUtils.escapeHTML(check.candidate_email || '')}</p>
                    </div>
                </div>
                <div class="flex items-center gap-3">
                    <span class="px-4 py-2 rounded-full text-sm font-bold border-2 ${statusInfo.class}">${statusInfo.label}</span>
                    ${verdictInfo ? `<span class="px-4 py-2 rounded-full text-sm font-bold border-2 ${verdictInfo.class}">${verdictInfo.label}</span>` : ''}
                </div>
            </div>

            <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <div class="bg-slate-50 rounded-xl p-4">
                    <p class="text-xs text-slate-500 font-semibold uppercase">Created</p>
                    <p class="text-lg font-bold text-slate-900">${created}</p>
                </div>
                <div class="bg-slate-50 rounded-xl p-4">
                    <p class="text-xs text-slate-500 font-semibold uppercase">Completed</p>
                    <p class="text-lg font-bold text-slate-900">${completed}</p>
                </div>
                <div class="bg-slate-50 rounded-xl p-4">
                    <p class="text-xs text-slate-500 font-semibold uppercase">Provider</p>
                    <p class="text-lg font-bold text-slate-900">${check.provider || 'Checkr'}</p>
                </div>
                <div class="bg-slate-50 rounded-xl p-4">
                    <p class="text-xs text-slate-500 font-semibold uppercase">Report ID</p>
                    <p class="text-lg font-bold text-slate-900 text-sm truncate">${check.provider_report_id ? SecurityUtils.escapeHTML(check.provider_report_id.substring(0, 12) + '...') : 'N/A'}</p>
                </div>
            </div>

            <div class="flex gap-3">
                ${check.status === 'report_ready' && check.verdict === 'consider' ? `
                    <button onclick="openAdverseModal(${check.id})" class="px-6 py-3 bg-amber-600 text-white font-bold rounded-xl hover:bg-amber-700 transition shadow-lg shadow-amber-500/30 flex items-center gap-2">
                        <i class="fas fa-exclamation-triangle"></i> Initiate Adverse Action
                    </button>
                ` : ''}
                ${check.status === 'pending' ? `
                    <button onclick="initiateCheck(${check.application_id})" class="px-6 py-3 bg-indigo-600 text-white font-bold rounded-xl hover:bg-indigo-700 transition shadow-lg shadow-indigo-500/30 flex items-center gap-2">
                        <i class="fas fa-play"></i> Initiate Check
                    </button>
                ` : ''}
                ${check.report_url ? `
                    <a href="${SecurityUtils.escapeHTML(check.report_url)}" target="_blank" class="px-6 py-3 bg-white border-2 border-slate-200 text-slate-700 font-bold rounded-xl hover:border-indigo-300 transition flex items-center gap-2">
                        <i class="fas fa-external-link-alt"></i> View Full Report
                    </a>
                ` : ''}
            </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div class="glass-card p-6">
                <h3 class="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
                    <i class="fas fa-clock text-indigo-600"></i> Status Timeline
                </h3>
                ${timeline || '<p class="text-slate-500 text-sm">No status changes yet</p>'}
            </div>

            <div class="glass-card p-6">
                <h3 class="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
                    <i class="fas fa-list text-indigo-600"></i> Report Findings
                </h3>
                ${findingsHtml || '<p class="text-slate-500 text-sm">No findings available yet</p>'}
            </div>
        </div>
    `;
}

async function initiateCheck(applicationId) {
    if (!confirm('Are you sure you want to initiate a background check for this candidate?')) return;

    try {
        const result = await window.fetchAPI(`/recruiter/background-checks/initiate/${applicationId}`, {
            method: 'POST',
        });
        Components.showSuccess('Background check initiated successfully');
        setTimeout(() => window.location.reload(), 1500);
    } catch (e) {
        Components.showError(e.detail || 'Failed to initiate background check');
    }
}

let currentBgCheckId = null;

function openAdverseModal(bgCheckId) {
    currentBgCheckId = bgCheckId;
    document.getElementById('adverse-action-modal')?.classList.remove('hidden');
}

function closeAdverseModal() {
    currentBgCheckId = null;
    document.getElementById('adverse-action-modal')?.classList.add('hidden');
}

async function sendAdverseAction(actionType) {
    if (!currentBgCheckId) return;

    if (!confirm(`Are you sure you want to send a ${actionType.replace('_', ' ')} notice?`)) return;

    try {
        const result = await window.fetchAPI(`/recruiter/background-checks/${currentBgCheckId}/adverse-action?action_type=${actionType}`, {
            method: 'POST',
        });
        Components.showSuccess('Adverse action notice sent successfully');
        closeAdverseModal();
        setTimeout(() => window.location.reload(), 1500);
    } catch (e) {
        Components.showError(e.detail || 'Failed to send adverse action notice');
    }
}
