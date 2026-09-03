let currentPage = 1;
let currentView = 'grid';
let searchTimer = null;
let selectedIds = new Set();
let allResults = [];

function debounceSearch() {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => loadResults(1), 300);
}

async function loadFacets() {
    try {
        const facets = await window.fetchAPI('/recruiter/candidates/search/facets');

        const renderFacet = (id, data, field, clickHandler) => {
            const container = document.getElementById(id);
            if (!container) return;
            const entries = Object.entries(data).sort((a, b) => b[1] - a[1]).slice(0, 10);
            if (entries.length === 0) {
                container.innerHTML = '<p class="text-xs text-slate-400">No data</p>';
                return;
            }
            container.innerHTML = entries.map(([key, count]) => `
                <label class="flex items-center gap-2 cursor-pointer group">
                    <input type="${field === 'radio' ? 'radio' : 'checkbox'}" name="facet-${id}" value="${key}"
                        onchange="${clickHandler || 'debounceSearch()'}"
                        class="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500">
                    <span class="text-xs font-medium text-slate-600 group-hover:text-indigo-600">${key}</span>
                    <span class="text-[10px] text-slate-400 ml-auto">${count}</span>
                </label>
            `).join('');
        };

        renderFacet('filter-status', facets.status, 'checkbox');
        renderFacet('filter-source', facets.source, 'checkbox');
        if (document.getElementById('filter-score-range')) {
            const scoreRanges = facets.score_range || {};
            document.getElementById('filter-score-range').innerHTML = Object.entries(scoreRanges)
                .filter(([_, c]) => c > 0)
                .map(([range, count]) => `
                    <button onclick="setScoreRange('${range}')" class="text-[10px] font-bold px-2 py-1 rounded-lg border border-slate-200 hover:border-indigo-300 hover:text-indigo-600 transition">
                        ${range} <span class="text-slate-400">(${count})</span>
                    </button>
                `).join('');
        }
    } catch (e) {
        console.warn('Failed to load facets:', e);
    }
}

function setScoreRange(range) {
    const [min, max] = range.split('-').map(Number);
    const minEl = document.getElementById('filter-min-score');
    const maxEl = document.getElementById('filter-max-score');
    if (minEl) minEl.value = min;
    if (maxEl) maxEl.value = max;
    loadResults(1);
}

function getFilters() {
    const qEl = document.getElementById('search-q');
    const skillsEl = document.getElementById('filter-skills');
    const minScoreEl = document.getElementById('filter-min-score');
    const maxScoreEl = document.getElementById('filter-max-score');
    const roleEl = document.getElementById('filter-role');
    const locationEl = document.getElementById('filter-location');
    const sortByEl = document.getElementById('sort-by');
    const sortOrderEl = document.getElementById('sort-order');
    const perPageEl = document.getElementById('per-page');

    const q = qEl ? qEl.value.trim() : '';
    const skills = skillsEl ? skillsEl.value.trim() : '';
    const minScore = minScoreEl ? minScoreEl.value : '';
    const maxScore = maxScoreEl ? maxScoreEl.value : '';
    const role = roleEl ? roleEl.value.trim() : '';
    const location = locationEl ? locationEl.value.trim() : '';

    const checkedStatus = [...document.querySelectorAll('#filter-status input:checked')].map(cb => cb.value);
    const checkedSource = [...document.querySelectorAll('#filter-source input:checked')].map(cb => cb.value);

    const params = new URLSearchParams();
    if (q) params.set('q', q);
    if (skills) params.set('skills', skills);
    if (minScore) params.set('min_score', minScore);
    if (maxScore) params.set('max_score', maxScore);
    if (role) params.set('role', role);
    if (location) params.set('location', location);
    if (checkedStatus.length) params.set('status', checkedStatus.join(','));
    if (checkedSource.length) params.set('source', checkedSource.join(','));

    params.set('sort_by', sortByEl ? sortByEl.value : 'overall_score');
    params.set('sort_order', sortOrderEl ? sortOrderEl.value : 'desc');
    params.set('per_page', perPageEl ? perPageEl.value : '20');

    return params;
}

async function loadResults(page) {
    const container = document.getElementById('results-container');
    if (!container) return;
    currentPage = page || 1;
    container.innerHTML = '<div class="col-span-full text-center py-20 text-slate-400"><i class="fas fa-circle-notch fa-spin text-3xl mb-4"></i><p class="font-medium">Searching...</p></div>';

    try {
        const params = getFilters();
        params.set('page', currentPage);
        const data = await window.fetchAPI(`/recruiter/candidates/talent-pool?${params.toString()}`);
        allResults = data.items || [];
        renderResults(allResults);
        renderPagination(data.pagination);
        document.getElementById('results-count').textContent = data.pagination?.total || allResults.length;
    } catch (e) {
        XSS.safeSetHTML(container, '<div class="col-span-full text-center py-20 text-red-500"><i class="fas fa-exclamation-triangle text-3xl mb-4"></i><p class="font-medium">Failed to load results</p><p class="text-sm text-slate-400 mt-1">' + XSS.escapeHTML(e.message || '') + '</p></div>');
    }
}

function renderResults(items) {
    const container = document.getElementById('results-container');
    if (!items.length) {
        container.innerHTML = '<div class="col-span-full text-center py-20 text-slate-400"><i class="fas fa-users-slash text-3xl mb-4"></i><p class="font-medium">No candidates found</p><p class="text-sm text-slate-400 mt-1">Try adjusting your filters</p></div>';
        return;
    }

    const isGridView = currentView === 'grid';
    if (isGridView) {
        container.className = 'grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4';
    } else {
        container.className = 'space-y-3';
    }

    XSS.setHTML(container, items.map(c => {
        const score = Math.round(c.score_entity?.final_score ?? c.overall_score ?? c.score ?? 0);
        const scoreClass = score >= 75 ? 'score-high' : score >= 40 ? 'score-mid' : 'score-low';
        const initials = (c.full_name || '?').split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
        const selected = selectedIds.has(c.id) ? 'selected' : '';
        const skillsList = (c.skills || []).slice(0, 4);
        const cvSnippet = c.cv_snippet ? `<p class="text-xs text-slate-500 mt-2 italic line-clamp-2">"${escapeHtml(c.cv_snippet)}"</p>` : '';
        const statusBadge = c.status ? `<span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 uppercase">${escapeHtml(c.status)}</span>` : '';

        const cardHtml = `
            <div class="talent-card glass-card p-4 cursor-pointer ${selected}" data-id="${escapeHtml(String(c.id))}" data-action="toggle">
                <div class="flex items-start gap-3 mb-3">
                    <div class="w-10 h-10 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 font-bold text-sm shrink-0">${initials}</div>
                    <div class="flex-1 min-w-0">
                        <div class="flex items-center gap-2">
                            <h4 class="font-bold text-slate-900 text-sm truncate">${escapeHtml(c.full_name || 'Unknown')}</h4>
                            <span class="score-badge ${scoreClass}">${score}%</span>
                        </div>
                        <p class="text-xs text-slate-500 truncate">${escapeHtml(c.declared_role || '')}${c.detected_role ? ' · ' + escapeHtml(c.detected_role) : ''}</p>
                    </div>
                </div>

                <div class="flex items-center gap-2 mb-2">
                    ${statusBadge}
                    ${c.source ? `<span class="text-[10px] text-slate-400">${escapeHtml(c.source)}</span>` : ''}
                    ${c.location ? `<span class="text-[10px] text-slate-400"><i class="fas fa-map-marker-alt mr-0.5"></i>${escapeHtml(c.location)}</span>` : ''}
                </div>

                ${skillsList.length ? `
                <div class="flex flex-wrap gap-1 mb-2">
                    ${skillsList.map(s => `<span class="px-1.5 py-0.5 bg-indigo-50 text-indigo-600 rounded text-[9px] font-bold">${escapeHtml(s)}</span>`).join('')}
                    ${c.skills.length > 4 ? `<span class="text-[9px] text-slate-400 font-bold">+${c.skills.length - 4}</span>` : ''}
                </div>` : ''}

                ${cvSnippet}

                <div class="flex items-center justify-between mt-3 pt-2 border-t border-slate-100">
                    <div class="flex items-center gap-1">
                        <button data-action="add-to-list" data-id="${escapeHtml(String(c.id))}" class="text-[10px] font-bold text-indigo-600 hover:text-indigo-800 px-2 py-1 rounded hover:bg-indigo-50 transition" title="Add to list">
                            <i class="fas fa-list mr-0.5"></i> List
                        </button>
                        <button data-action="send-message" data-user-id="${escapeHtml(String(c.user_id || ''))}" data-id="${escapeHtml(String(c.id))}" class="text-[10px] font-bold text-indigo-600 hover:text-indigo-800 px-2 py-1 rounded hover:bg-indigo-50 transition" title="Send message">
                            <i class="fas fa-comment mr-0.5"></i> Message
                        </button>
                        <button data-action="compare" data-id="${escapeHtml(String(c.id))}" class="text-[10px] font-bold text-indigo-600 hover:text-indigo-800 px-2 py-1 rounded hover:bg-indigo-50 transition" title="Compare">
                            <i class="fas fa-scale-balanced mr-0.5"></i> Compare
                        </button>
                    </div>
                    <a href="/recruiter/candidate?id=${escapeHtml(String(c.id))}" class="text-xs text-slate-400 hover:text-indigo-600" title="View profile">
                        <i class="fas fa-arrow-right"></i>
                    </a>
                </div>
            </div>
        `;

        if (!isGridView) {
            // List view compact
            return `
            <div class="talent-card glass-card p-3 cursor-pointer flex items-center gap-4 ${selected}" data-id="${escapeHtml(String(c.id))}" data-action="toggle">
                <input type="checkbox" ${selectedIds.has(c.id) ? 'checked' : ''} class="rounded border-slate-300 text-indigo-600" data-action="toggle-check" data-id="${escapeHtml(String(c.id))}">
                <div class="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 font-bold text-xs shrink-0">${initials}</div>
                <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2">
                        <span class="font-bold text-sm text-slate-900">${escapeHtml(c.full_name || 'Unknown')}</span>
                        <span class="score-badge ${scoreClass}">${score}%</span>
                        ${statusBadge}
                    </div>
                    <p class="text-xs text-slate-500">${escapeHtml(c.declared_role || '')}${c.location ? ' · ' + escapeHtml(c.location) : ''}</p>
                </div>
                <div class="flex items-center gap-2">
                    <button data-action="add-to-list" data-id="${escapeHtml(String(c.id))}" class="text-xs text-slate-400 hover:text-indigo-600 p-1" title="Add to list"><i class="fas fa-list"></i></button>
                    <button data-action="send-message" data-user-id="${escapeHtml(String(c.user_id || ''))}" data-id="${escapeHtml(String(c.id))}" class="text-xs text-slate-400 hover:text-indigo-600 p-1" title="Message"><i class="fas fa-comment"></i></button>
                    <a href="/recruiter/candidate?id=${escapeHtml(String(c.id))}" class="text-xs text-slate-400 hover:text-indigo-600 p-1"><i class="fas fa-arrow-right"></i></a>
                </div>
            </div>`;
        }
        return cardHtml;
    }).join(''));

    container.addEventListener('click', function(e) {
        const target = e.target.closest('[data-action]');
        if (!target) return;
        const action = target.getAttribute('data-action');
        const id = parseInt(target.getAttribute('data-id'));
        if (action === 'toggle') { toggleSelect(id); return; }
        if (action === 'toggle-check') { toggleSelect(id); return; }
        if (action === 'add-to-list') { e.stopPropagation(); addToList(id); return; }
        if (action === 'send-message') { e.stopPropagation(); const uid = parseInt(target.getAttribute('data-user-id')); sendMessage(uid, id); return; }
        if (action === 'compare') { e.stopPropagation(); compareCandidate(id); return; }
    });
}

function renderPagination(pagination) {
    const container = document.getElementById('pagination-container');
    if (!pagination || pagination.total_pages <= 1) {
        container.innerHTML = '';
        return;
    }
    const { page, total_pages, has_prev, has_next } = pagination;
    let html = `
    <div class="flex items-center justify-between gap-4 bg-white p-4 rounded-2xl border border-slate-100 shadow-lg">
        <div class="text-sm text-slate-600 font-medium">
            Page <span class="font-bold text-slate-900">${page}</span> of <span class="font-bold text-slate-900">${total_pages}</span>
        </div>
        <div class="flex items-center gap-2">
            <button onclick="loadResults(${page - 1})" ${!!has_prev ? '' : 'disabled'}
                class="px-4 py-2 rounded-xl font-bold text-sm transition ${has_prev ? 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-50' : 'bg-slate-50 text-slate-300 cursor-not-allowed'}">
                <i class="fas fa-chevron-left text-xs mr-1"></i> Prev
            </button>`;
    const maxPages = 5;
    let startPage = Math.max(1, page - Math.floor(maxPages / 2));
    let endPage = Math.min(total_pages, startPage + maxPages - 1);
    if (endPage - startPage < maxPages - 1) startPage = Math.max(1, endPage - maxPages + 1);
    if (startPage > 1) {
        html += `<button onclick="loadResults(1)" class="w-10 h-10 rounded-xl font-bold text-sm bg-white border border-slate-200 text-slate-700 hover:bg-slate-50">1</button>`;
        if (startPage > 2) html += `<span class="px-1 text-slate-400">...</span>`;
    }
    for (let i = startPage; i <= endPage; i++) {
        html += `<button onclick="loadResults(${i})" class="w-10 h-10 rounded-xl font-bold text-sm transition ${i === page ? 'bg-indigo-600 text-white shadow-lg' : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-50'}">${i}</button>`;
    }
    if (endPage < total_pages) {
        if (endPage < total_pages - 1) html += `<span class="px-1 text-slate-400">...</span>`;
        html += `<button onclick="loadResults(${total_pages})" class="w-10 h-10 rounded-xl font-bold text-sm bg-white border border-slate-200 text-slate-700 hover:bg-slate-50">${total_pages}</button>`;
    }
    html += `
            <button onclick="loadResults(${page + 1})" ${!!has_next ? '' : 'disabled'}
                class="px-4 py-2 rounded-xl font-bold text-sm transition ${has_next ? 'bg-indigo-600 text-white hover:bg-indigo-700 shadow-lg' : 'bg-slate-50 text-slate-300 cursor-not-allowed'}">
                Next <i class="fas fa-chevron-right text-xs ml-1"></i>
            </button>
        </div>
    </div>`;
    container.innerHTML = html;
}

function toggleSelect(id) {
    if (selectedIds.has(id)) selectedIds.delete(id);
    else selectedIds.add(id);
    const card = document.querySelector(`.talent-card[data-id="${id}"]`);
    if (card) card.classList.toggle('selected');
    const cb = card?.querySelector('input[type="checkbox"]');
    if (cb) cb.checked = selectedIds.has(id);
}

function toggleView() {
    currentView = currentView === 'grid' ? 'list' : 'grid';
    const btn = document.getElementById('view-toggle');
    btn.innerHTML = currentView === 'grid' ? '<i class="fas fa-list"></i> List' : '<i class="fas fa-th-large"></i> Grid';
    renderResults(allResults);
}

function resetFilters() {
    document.querySelectorAll('#filter-status input, #filter-source input').forEach(cb => cb.checked = false);
    ['search-q', 'filter-skills', 'filter-role', 'filter-location'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
    const minScoreEl = document.getElementById('filter-min-score');
    const maxScoreEl = document.getElementById('filter-max-score');
    const sortByEl = document.getElementById('sort-by');
    const sortOrderEl = document.getElementById('sort-order');
    if (minScoreEl) minScoreEl.value = '';
    if (maxScoreEl) maxScoreEl.value = '';
    if (sortByEl) sortByEl.value = 'overall_score';
    if (sortOrderEl) sortOrderEl.value = 'desc';
    loadResults(1);
}

async function exportCSV() {
    try {
        const params = getFilters();
        const url = `/recruiter/candidates/search/export?${params.toString()}`;
        const response = await fetch(url, { credentials: 'same-origin' });
        const blob = await response.blob();
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `candidates_export_${new Date().toISOString().split('T')[0]}.csv`;
        a.click();
        URL.revokeObjectURL(a.href);
        Components.showToast?.('CSV exported successfully', 'success');
    } catch (e) {
        Components.showToast?.('Failed to export CSV', 'error');
    }
}

function addToList(id) {
    Components.showToast?.('Add to list feature coming soon', 'info');
}

async function sendMessage(userId, appId) {
    if (!userId) {
        Components.showToast?.('Candidate has no account yet', 'warning');
        return;
    }
    try {
        const resp = await window.fetchAPI('/messages/conversations/with-candidate/' + userId, { method: 'POST' });
        if (resp?.conversation_id) {
            window.location.href = '/recruiter/messages';
        }
    } catch (e) {
        Components.showToast?.('Failed to start conversation', 'error');
    }
}

function compareCandidate(id) {
    if (!selectedIds.has(id)) toggleSelect(id);
    const selected = allResults.filter(c => selectedIds.has(c.id));
    if (selected.length < 2) {
        Components.showToast?.('Select at least 2 candidates to compare', 'info');
        return;
    }
    if (selected.length > 4) {
        Components.showToast?.('Maximum 4 candidates can be compared', 'warning');
        return;
    }
    const modal = document.getElementById('compare-modal');
    const content = document.getElementById('compare-content');
    content.innerHTML = `
    <div class="overflow-x-auto">
        <table class="w-full text-left text-sm">
            <thead>
                <tr class="border-b border-slate-200">
                    <th class="p-3 font-bold text-slate-500 text-xs uppercase">Field</th>
                    ${selected.map(c => `<th class="p-3 font-bold text-slate-800">${escapeHtml(c.full_name || 'Unknown')}</th>`).join('')}
                </tr>
            </thead>
            <tbody>
                <tr class="border-b border-slate-100"><td class="p-3 font-semibold text-slate-500">Score</td>
                    ${selected.map(c => { const _s = c.score_entity?.final_score ?? c.overall_score ?? 0; return `<td class="p-3"><span class="score-badge ${_s >= 75 ? 'score-high' : _s >= 40 ? 'score-mid' : 'score-low'}">${Math.round(_s)}%</span></td>`; }).join('')}
                </tr>
                <tr class="border-b border-slate-100"><td class="p-3 font-semibold text-slate-500">Role</td>
                    ${selected.map(c => `<td class="p-3">${escapeHtml(c.declared_role || '-')}</td>`).join('')}
                </tr>
                <tr class="border-b border-slate-100"><td class="p-3 font-semibold text-slate-500">Status</td>
                    ${selected.map(c => `<td class="p-3">${escapeHtml(c.status || '-')}</td>`).join('')}
                </tr>
                <tr class="border-b border-slate-100"><td class="p-3 font-semibold text-slate-500">Location</td>
                    ${selected.map(c => `<td class="p-3">${escapeHtml(c.location || '-')}</td>`).join('')}
                </tr>
                <tr class="border-b border-slate-100"><td class="p-3 font-semibold text-slate-500">Source</td>
                    ${selected.map(c => `<td class="p-3">${escapeHtml(c.source || '-')}</td>`).join('')}
                </tr>
                <tr><td class="p-3 font-semibold text-slate-500">Skills</td>
                    ${selected.map(c => `<td class="p-3">${(c.skills || []).slice(0, 8).map(s => `<span class="inline-block px-1.5 py-0.5 bg-indigo-50 text-indigo-600 rounded text-[9px] font-bold mr-1">${escapeHtml(s)}</span>`).join('')}</td>`).join('')}
                </tr>
            </tbody>
        </table>
    </div>`;
    modal.classList.remove('hidden');
}

function closeCompareModal() {
    document.getElementById('compare-modal').classList.add('hidden');
}

function escapeHtml(text) {
    if (!text) return '';
    const d = document.createElement('div');
    d.textContent = text;
    return d.innerHTML;
}

document.addEventListener('DOMContentLoaded', () => {
    Components.init('nav_talent_pool');
    loadFacets();
    loadResults(1);
});
