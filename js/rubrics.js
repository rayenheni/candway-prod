(function () {
    'use strict';

    const $ = (s) => document.querySelector(s);
    const $$ = (s) => Array.from(document.querySelectorAll(s));
    const esc = (s) => String(s == null ? '' : s)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');

    const state = {
        data: { rows: [], drafts: [], stats: {} },
        filter: 'all',
        search: '',
    };

    async function load() {
        await fetch('/api/v1/categories/job', { credentials: 'include' });
        const csrf = getCookie('csrf_token');

        const r = await fetch('/api/v1/rubric/management', { credentials: 'include' });
        if (!r.ok) {
            renderError(`Failed to load (HTTP ${r.status})`);
            return;
        }
        state.data = await r.json();
        renderStats();
        renderTable();
    }

    function getCookie(name) {
        const m = document.cookie.match(new RegExp('(^|; )' + name + '=([^;]*)'));
        return m ? m[2] : '';
    }

    function renderStats() {
        const s = state.data.stats || {};
        $('#rb-stat-total').textContent = s.total_jobs ?? 0;
        $('#rb-stat-with').textContent = s.with_rubric ?? 0;
        $('#rb-stat-without').textContent = s.without_rubric ?? 0;
        $('#rb-stat-drafts').textContent = s.drafts ?? 0;
    }

    function renderTable() {
        const tbody = $('#rb-table-body');
        const rows = filteredRows();

        if (!rows.length) {
            tbody.innerHTML = '';
            $('#rb-empty-state').classList.remove('hidden');
            return;
        }
        $('#rb-empty-state').classList.add('hidden');

        tbody.innerHTML = rows.map(row => {
            const r = row.rubric;
            const status = r
                ? `<span class="cw-badge cw-badge--success">
                       <span class="cw-badge__dot"></span> Published
                   </span>`
                : (row.has_draft
                    ? `<span class="cw-badge cw-badge--accent">
                           <span class="cw-badge__dot"></span> Draft
                       </span>`
                    : `<span class="cw-badge cw-badge--neutral">
                           <span class="cw-badge__dot"></span> No rubric
                       </span>`);

            const version = r ? `v${r.version}` : '—';
            const skills = r ? `${r.skill_count} <span class="text-slate-400 text-[10px]">(${r.category_count} cat)</span>` : '—';
            const updated = r?.created_at ? timeAgo(r.created_at) : '—';

            return `
                <tr class="cw-tr" data-job-id="${row.job_id}">
                    <td class="cw-td">
                        <div class="cw-cell-identity">
                            <div class="cw-avatar ${r ? '' : 'cw-avatar--neutral'}">
                                <i class="fas ${r ? 'fa-file-check' : 'fa-briefcase'}"></i>
                            </div>
                            <div class="cw-cell-stack">
                                <div class="cw-cell-stack__title">${esc(row.job_title)}</div>
                                <div class="cw-cell-stack__sub">${esc(row.type || '—')} · ${esc(row.location || '—')}</div>
                            </div>
                        </div>
                    </td>
                    <td class="cw-td">${status}</td>
                    <td class="cw-td"><span class="cw-td--mono">${version}</span></td>
                    <td class="cw-td"><span class="text-sm text-slate-700">${skills}</span></td>
                    <td class="cw-td"><span class="text-sm font-mono text-slate-700">${row.application_count || 0}</span></td>
                    <td class="cw-td"><span class="text-[11px] text-slate-500">${updated}</span></td>
                    <td class="cw-td cw-td--right">
                        <div class="cw-actions">
                            ${r ? `
                                <a href="/admin/rubric-builder?job_id=${row.job_id}" class="cw-action-btn cw-action-btn--edit" title="Edit rubric">
                                    <i class="fas fa-pen"></i>
                                </a>
                                <button class="cw-action-btn cw-action-btn--edit rb-action-duplicate" data-job-id="${row.job_id}" title="Duplicate as draft">
                                    <i class="fas fa-copy"></i>
                                </button>
                                <a href="/recruiter/scoring-preview?job_id=${row.job_id}" target="_blank" class="cw-action-btn cw-action-btn--edit" title="Test scoring">
                                    <i class="fas fa-vial"></i>
                                </a>
                            ` : `
                                <a href="/admin/rubric-builder?job_id=${row.job_id}" class="cw-action-btn cw-action-btn--primary">
                                    Create
                                </a>
                            `}
                        </div>
                    </td>
                </tr>
            `;
        }).join('');

        $$('.rb-action-duplicate').forEach(btn => {
            btn.addEventListener('click', () => onDuplicate(parseInt(btn.dataset.jobId, 10)));
        });
    }

    function filteredRows() {
        let rows = state.data.rows || [];
        const q = state.search.toLowerCase().trim();

        if (state.filter === 'with') rows = rows.filter(r => r.rubric);
        else if (state.filter === 'without') rows = rows.filter(r => !r.rubric);
        else if (state.filter === 'drafts') rows = rows.filter(r => r.has_draft);

        if (q) rows = rows.filter(r => (r.job_title || '').toLowerCase().includes(q));
        return rows;
    }

    function renderError(msg) {
        $('#rb-table-body').innerHTML = `
            <tr><td colspan="7" class="cw-empty">
                <div class="rb-empty-icon w-12 h-12 mx-auto mb-3 rounded-xl flex items-center justify-center">
                    <i class="fas fa-exclamation-triangle text-amber-500"></i>
                </div>
                <p class="text-sm text-rose-600 font-bold">${esc(msg)}</p>
                <button onclick="location.reload()" class="mt-2 text-xs font-bold text-indigo-600 hover:text-indigo-800">Retry</button>
            </td></tr>`;
    }

    async function onDuplicate(jobId) {
        await fetch('/api/v1/categories/job', { credentials: 'include' });
        const csrf = getCookie('csrf_token');
        try {
            const r = await fetch(`/api/v1/rubric/duplicate/${jobId}`, {
                method: 'POST',
                credentials: 'include',
                headers: { 'X-CSRF-Token': csrf },
            });
            if (!r.ok) {
                const err = await r.json().catch(() => ({}));
                throw new Error(err.detail || `HTTP ${r.status}`);
            }
            const data = await r.json();
            toast('Draft created');
            setTimeout(() => {
                window.location.href = `/admin/rubric-builder?job_id=${jobId}&draft_id=${data.id}`;
            }, 600);
        } catch (e) {
            toast('Failed: ' + e.message, 'error');
        }
    }

    function bindFilters() {
        $$('.rb-filter').forEach(btn => {
            btn.addEventListener('click', () => {
                state.filter = btn.dataset.filter;
                $$('.rb-filter').forEach(b => {
                    const active = b === btn;
                    b.classList.toggle('bg-white', active);
                    b.classList.toggle('text-indigo-600', active);
                    b.classList.toggle('shadow-sm', active);
                    b.classList.toggle('text-slate-600', !active);
                    b.classList.toggle('hover:text-slate-900', !active);
                });
                renderTable();
            });
        });
        let searchTimer = null;
        $('#rb-search').addEventListener('input', (e) => {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(() => {
                state.search = e.target.value;
                renderTable();
            }, 200);
        });
    }

    function timeAgo(iso) {
        if (!iso) return '—';
        try {
            const d = new Date(iso);
            const diff = Date.now() - d.getTime();
            const mins = Math.floor(diff / 60000);
            if (mins < 1) return 'just now';
            if (mins < 60) return mins + 'm ago';
            const hrs = Math.floor(mins / 60);
            if (hrs < 24) return hrs + 'h ago';
            const days = Math.floor(hrs / 24);
            if (days < 30) return days + 'd ago';
            return d.toLocaleDateString();
        } catch { return '—'; }
    }

    let toastTimer = null;
    function toast(msg, type = 'success') {
        const t = $('#rb-toast');
        const icon = $('#rb-toast-icon');
        $('#rb-toast-msg').textContent = msg;
        icon.className = type === 'error' ? 'fas fa-exclamation-circle text-rose-400'
            : 'fas fa-check-circle text-emerald-400';
        t.style.display = '';
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => { t.style.display = 'none'; }, 2500);
    }

    document.addEventListener('DOMContentLoaded', () => {
        if (!document.getElementById('rb-search')) return;
        bindFilters();
        load();
    });
})();
