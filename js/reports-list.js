(function () {
    'use strict';

    const API_BASE = '/api/v1/recruiter/reports';
    let deleteTargetId = null;
    let scheduleTargetId = null;

    async function loadReports() {
        const container = document.getElementById('reports-container');
        container.innerHTML = `<div class="flex items-center justify-center py-16 text-slate-400"><i class="fas fa-spinner fa-spin text-2xl"></i><span class="ml-3 font-medium">Loading reports...</span></div>`;
        try {
            const resp = await fetch(API_BASE, { credentials: 'include' });
            if (!resp.ok) throw new Error('Failed to load');
            const data = await resp.json();
            renderReports(container, data.reports || []);
        } catch (e) {
            console.error(e);
            container.innerHTML = `<div class="flex items-center justify-center py-16 text-rose-500"><i class="fas fa-triangle-exclamation text-2xl"></i><span class="ml-3 font-medium">Failed to load reports</span></div>`;
        }
    }

    function renderReports(container, reports) {
        if (reports.length === 0) {
            container.innerHTML = `
                <div class="flex flex-col items-center justify-center py-20 text-slate-400">
                    <i class="fas fa-chart-simple text-6xl mb-4 text-slate-300"></i>
                    <p class="text-xl font-bold text-slate-500 mb-1">No reports yet</p>
                    <p class="text-sm mb-6">Create your first custom report</p>
                    <a href="/recruiter/report-builder" class="px-6 py-3 bg-violet-600 text-white font-bold rounded-xl hover:bg-violet-700 transition-colors shadow-lg shadow-violet-500/20">
                        <i class="fas fa-plus mr-1.5"></i>Create Report
                    </a>
                </div>
            `;
            return;
        }

        container.innerHTML = reports.map(r => {
            const hasSchedule = r.is_scheduled;
            const freq = r.schedule_frequency || '';
            const lastGen = r.last_generated_at ? new Date(r.last_generated_at).toLocaleDateString() : 'Never';
            const nextRun = r.next_scheduled_at ? new Date(r.next_scheduled_at).toLocaleDateString() : '--';
            return `
                <div class="glass-card rounded-xl border border-slate-200 p-5 hover:border-violet-200 transition-all" data-id="${r.id}">
                    <div class="flex items-start justify-between gap-4">
                        <div class="flex-1 min-w-0">
                            <div class="flex items-center gap-2 mb-1">
                                <h3 class="text-lg font-bold text-slate-900 truncate">${r.name}</h3>
                                ${hasSchedule ? `<span class="shrink-0 text-[10px] font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full uppercase">Scheduled</span>` : ''}
                            </div>
                            ${r.description ? `<p class="text-sm text-slate-500 mb-3">${r.description}</p>` : ''}
                            <div class="flex items-center gap-4 text-xs text-slate-400">
                                <span><span class="font-medium text-slate-500">Last:</span> ${lastGen}</span>
                                ${hasSchedule ? `<span><span class="font-medium text-slate-500">Next:</span> ${nextRun}</span>` : ''}
                                ${hasSchedule ? `<span><span class="font-medium text-slate-500">Freq:</span> ${freq}</span>` : ''}
                            </div>
                        </div>
                        <div class="flex items-center gap-1 shrink-0">
                            <button class="generate-now-btn px-3 py-1.5 text-xs font-bold text-emerald-600 bg-emerald-50 rounded-lg hover:bg-emerald-100 transition-colors" title="Generate Now">
                                <i class="fas fa-play mr-1"></i>Generate
                            </button>
                            <a href="/recruiter/report-builder?id=${r.id}" class="px-3 py-1.5 text-xs font-bold text-violet-600 bg-violet-50 rounded-lg hover:bg-violet-100 transition-colors">
                                <i class="fas fa-pen mr-1"></i>Edit
                            </a>
                            <div class="relative group">
                                <button class="px-3 py-1.5 text-xs font-bold text-slate-500 bg-slate-50 rounded-lg hover:bg-slate-100 transition-colors">
                                    <i class="fas fa-ellipsis"></i>
                                </button>
                                <div class="absolute right-0 top-full mt-1 bg-white border border-slate-200 rounded-lg shadow-lg hidden group-hover:block z-50 min-w-[150px]">
                                    <button class="schedule-btn w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-slate-50" data-id="${r.id}">
                                        <i class="fas fa-clock mr-2 text-emerald-500"></i>Schedule
                                    </button>
                                    <button class="export-csv-btn w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-slate-50" data-id="${r.id}">
                                        <i class="fas fa-file-csv mr-2 text-emerald-500"></i>Export CSV
                                    </button>
                                    <button class="export-pdf-btn w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-slate-50" data-id="${r.id}">
                                        <i class="fas fa-file-pdf mr-2 text-rose-500"></i>Export PDF
                                    </button>
                                    <hr class="border-slate-100">
                                    <button class="delete-btn w-full text-left px-4 py-2 text-sm text-rose-600 hover:bg-rose-50" data-id="${r.id}">
                                        <i class="fas fa-trash-can mr-2"></i>Delete
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        attachEventListeners();
    }

    function attachEventListeners() {
        document.querySelectorAll('.delete-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                deleteTargetId = parseInt(btn.dataset.id);
                document.getElementById('delete-modal')?.classList.remove('hidden');
            });
        });

        document.querySelectorAll('.generate-now-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                const card = btn.closest('[data-id]');
                const id = parseInt(card.dataset.id);
                btn.disabled = true;
                btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i>Generating...';
                try {
                    const resp = await fetch(`${API_BASE}/${id}/generate`, {
                        method: 'POST',
                        credentials: 'include',
                    });
                    if (!resp.ok) throw new Error('Failed');
                    showToast('Report generated successfully');
                    loadReports();
                } catch (e) {
                    showToast('Generation failed', 'error');
                    btn.innerHTML = '<i class="fas fa-play mr-1"></i>Generate';
                    btn.disabled = false;
                }
            });
        });

        document.querySelectorAll('.schedule-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                scheduleTargetId = parseInt(btn.dataset.id);
                document.getElementById('schedule-modal')?.classList.remove('hidden');
            });
        });

        document.querySelectorAll('.export-csv-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const id = parseInt(btn.dataset.id);
                window.open(`${API_BASE}/${id}/export/csv`, '_blank');
            });
        });

        document.querySelectorAll('.export-pdf-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const id = parseInt(btn.dataset.id);
                window.open(`${API_BASE}/${id}/export/pdf`, '_blank');
            });
        });
    }

    document.getElementById('delete-cancel')?.addEventListener('click', () => {
        document.getElementById('delete-modal')?.classList.add('hidden');
        deleteTargetId = null;
    });

    document.getElementById('delete-confirm')?.addEventListener('click', async () => {
        if (!deleteTargetId) return;
        try {
            const resp = await fetch(`${API_BASE}/${deleteTargetId}`, {
                method: 'DELETE',
                credentials: 'include',
            });
            if (!resp.ok) throw new Error('Delete failed');
            document.getElementById('delete-modal')?.classList.add('hidden');
            showToast('Report deleted');
            loadReports();
        } catch (e) {
            showToast('Delete failed', 'error');
        }
        deleteTargetId = null;
    });

    document.getElementById('schedule-cancel')?.addEventListener('click', () => {
        document.getElementById('schedule-modal')?.classList.add('hidden');
    });

    document.getElementById('schedule-save')?.addEventListener('click', async () => {
        if (!scheduleTargetId) return;
        const frequency = document.getElementById('schedule-frequency')?.value;
        const recipientsRaw = document.getElementById('schedule-recipients')?.value;
        const recipients = (recipientsRaw || '').split(',').map(r => r.trim()).filter(Boolean);
        try {
            const resp = await fetch(`${API_BASE}/${scheduleTargetId}/schedule`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ frequency, recipients }),
            });
            if (!resp.ok) throw new Error('Schedule failed');
            document.getElementById('schedule-modal')?.classList.add('hidden');
            showToast('Report scheduled');
            loadReports();
        } catch (e) {
            showToast('Schedule failed', 'error');
        }
        scheduleTargetId = null;
    });

    function showToast(msg, type = 'success') {
        const existing = document.querySelector('.report-toast');
        if (existing) existing.remove();
        const div = document.createElement('div');
        div.className = `report-toast fixed bottom-6 right-6 px-5 py-3 rounded-xl shadow-xl text-sm font-bold text-white z-50 ${type === 'error' ? 'bg-rose-600' : 'bg-emerald-600'}`;
        div.textContent = msg;
        document.body.appendChild(div);
        setTimeout(() => div.remove(), 3000);
    }

    if (document.getElementById('reports-container')) {
        loadReports();
    }
})();
