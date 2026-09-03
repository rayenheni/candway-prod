// --- Extracted from recruiter/pipeline.html ---
let allApps = [];
let allJobs = [];
let allCampaigns = [];
let selectedApplications = new Set();
let currentView = 'board';
let currentPage = 1;
let paginationMeta = null;
let isLoading = false;
let searchTimeout = null;
let _scrollContainerIsWindow = false;


function initPipelineSecureHandlers() {
    if (window.__pipelineSecureHandlersInitialized) return;
    window.__pipelineSecureHandlersInitialized = true;

    document.addEventListener('click', function (event) {
        const quickButton = event.target.closest('[data-quick-action]');
        if (quickButton) {
            const applicationId = Number(quickButton.dataset.appId);
            const action = quickButton.dataset.quickAction;

            if (
                Number.isInteger(applicationId) &&
                applicationId > 0 &&
                ['invite', 'shortlist', 'reject'].includes(action)
            ) {
                quickAction(applicationId, action);
            }
            return;
        }

        const nextButton = event.target.closest('#pipeline-next-page');
        if (nextButton) {
            const nextPage = Number(paginationMeta?.page) + 1;

            if (Number.isInteger(nextPage) && nextPage > 1) {
                loadApplications(nextPage, true);
            }
        }
        const retryButton = event.target.closest('[data-pipeline-retry]');
        if (retryButton) {
            loadApplications(1, false);
        }
    });
}

async function initPipeline() {
    // Wait for translations to be ready (with timeout fallback)
    if (window.localizationReadyPromise) {
        try {
            await Promise.race([
                window.localizationReadyPromise,
                new Promise(r => setTimeout(r, 2000)) // 2s fallback
            ]);
        } catch (e) {
            console.warn("Localization wait timed out", e);
        }
    }

    Components.init('nav_pipeline'); // Highlight sidebar

    // Check if token exists
    if (!document.cookie.includes('logged_in=')) {
        console.error('No authentication session found');
        showToast(window.t('recruiter.pipeline.login_error'), "error");
        setTimeout(() => {
            window.location.href = '/login/recruiter';
        }, 1500);
        return;
    }

    // Prep UI for filters from URL
    const urlParams = new URLSearchParams(window.location.search);

    // Fetch Jobs & Campaigns in parallel for filter dropdowns
    const [jobsResult, campaignsResult] = await Promise.all([
        window.fetchAPI('/recruiter/jobs/my').catch(e => { console.warn("Failed to load jobs", e); return null; }),
        window.fetchAPI('/recruiter/campaigns').catch(e => { console.warn("Failed to load campaigns", e); return null; })
    ]);

    if (jobsResult) {
        allJobs = Array.isArray(jobsResult) ? jobsResult : (jobsResult.jobs || []);
        populateJobFilter();
        const jobIdParam = urlParams.get('jobId') || urlParams.get('job');
        if (jobIdParam) {
            const select = document.getElementById('filter-job');
            if (select) select.value = jobIdParam;
            const menu = document.getElementById('filter-job-menu');
            if (menu) {
                const matched = menu.querySelector(`.dropdown-option[data-value="${CSS.escape(jobIdParam)}"]`);
                if (matched) { matched.classList.add('selected'); document.getElementById('filter-job-label').textContent = matched.textContent; }
            }
        }
    }

    if (campaignsResult) {
        allCampaigns = Array.isArray(campaignsResult) ? campaignsResult : [];
        populateCampaignFilter();
        const batchIdParam = urlParams.get('batchId') || urlParams.get('batch');
        if (batchIdParam) {
            const select = document.getElementById('filter-batch');
            if (select) select.value = batchIdParam;
            const menu = document.getElementById('filter-batch-menu');
            if (menu) {
                const matched = menu.querySelector(`.dropdown-option[data-value="${CSS.escape(batchIdParam)}"]`);
                if (matched) { matched.classList.add('selected'); document.getElementById('filter-batch-label').textContent = matched.textContent; }
            }
        }
    }

    loadApplications(1, false);

    // Listen for stage changes from other tabs/pages
    if (window.StageSync) {
        window.StageSync.onChange(function(data) {
            const app = allApps.find(a => a.id == data.appId);
            if (app) {
                app.status = data.newStatus;
                renderPipeline();
                updateStats();
            } else {
                // Candidate not in current list, reload to get fresh data
                loadApplications(1, false);
            }
        });
    }

    // UX Enhancement: Keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Ignore if typing in input
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

        // '/' to focus search
        if (e.key === '/') {
            e.preventDefault();
            document.getElementById('filter-role')?.focus();
        }

        // 'Escape' to clear search and blur
        if (e.key === 'Escape') {
            const searchInput = document.getElementById('filter-role');
            if (searchInput && document.activeElement === searchInput) {
                searchInput.blur();
            } else if (searchInput && searchInput.value) {
                searchInput.value = '';
                loadApplications(1, false);
            }
        }

        // '1-6' to switch views or filter by status
        if (e.key >= '1' && e.key <= '6') {
            const views = ['board', 'list'];
            const viewIndex = parseInt(e.key) - 1;
            if (viewIndex < views.length) {
                toggleView(views[viewIndex]);
            }
        }

        // 'a' for select all in list view
        if (e.key === 'a' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            toggleSelectAll(true);
        }
    });

    // UX Enhancement: Search with debounce
    const searchInput = document.getElementById('filter-role');
    if (searchInput) {
        let searchTimeout = null;
        searchInput.addEventListener('input', function() {
            if (searchTimeout) clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => loadApplications(1, false), 300);
        });
    }

    // UX Enhancement: Infinite scroll (attach to Kanban scrollable container)
    let scrollTimeout = null;
    const kanbanContainer = document.querySelector('.flex-1.overflow-y-auto.custom-scrollbar') || document.getElementById('view-board') || document.querySelector('.kanban-col')?.closest('.overflow-y-auto') || window;
    _scrollContainerIsWindow = kanbanContainer === window;
    kanbanContainer.addEventListener('scroll', function() {
        if (scrollTimeout) clearTimeout(scrollTimeout);
        scrollTimeout = setTimeout(function() {
            const scrollTop = _scrollContainerIsWindow ? (window.scrollY || document.documentElement.scrollTop) : kanbanContainer.scrollTop;
            const scrollHeight = _scrollContainerIsWindow ? document.documentElement.scrollHeight : kanbanContainer.scrollHeight;
            const clientHeight = _scrollContainerIsWindow ? document.documentElement.clientHeight : kanbanContainer.clientHeight;

            if (scrollTop + clientHeight >= scrollHeight - 200) {
                if (paginationMeta && paginationMeta.has_next && !isLoading) {
                    loadApplications(currentPage + 1, true);
                }
            }
        }, 100);
    });
}

async function loadApplications(page = 1, append = false) {
    if (isLoading) return;
    isLoading = true;
    currentPage = page;

    // Show Loading Skeleton if not appending (full reload)
    if (!append) {
        const columns = ['col-applied', 'col-invited', 'col-interviewing', 'col-offer', 'col-hired', 'col-rejected'];
        columns.forEach(colId => {
            const col = document.getElementById(colId);
            if (col) {
                col.innerHTML = `
                    <div class="animate-pulse space-y-3 p-2">
                        ${[1,2,3].map(() => `
                            <div class="bg-slate-100/50 rounded-xl p-3">
                                <div class="h-4 bg-slate-200 rounded w-3/4 mb-2"></div>
                                <div class="h-3 bg-slate-100 rounded w-1/2"></div>
                            </div>
                        `).join('')}
                    </div>
                `;
            }
        });
    }

    // Gather Filters
    const roleEl = document.getElementById('filter-role');
    const scoreEl = document.getElementById('filter-score');
    const jobEl = document.getElementById('filter-job');
    const role = roleEl ? roleEl.value.toLowerCase() : '';
    const minScore = scoreEl ? (parseInt(scoreEl.value) || 0) : 0;
    const jobId = jobEl ? jobEl.value : '';
    const batchId = document.getElementById('filter-batch') ? document.getElementById('filter-batch').value : "";

    let url = `/recruiter/applications?page=${page}&per_page=20`;
    if (jobId) url += `&job_id=${jobId}`;
    if (batchId) url += `&batch_id=${batchId}`;
    if (minScore) url += `&min_score=${minScore}`;
    if (role) url += `&role_filter=${encodeURIComponent(role)}`;

    try {
        const data = await window.fetchAPI(url);

        let newApps = [];
        if (data.items) {
            newApps = data.items;
            paginationMeta = data.pagination;
            window._pipelineStats = data.pipeline_stats || {};
        } else if (Array.isArray(data)) {
            // Fallback
            newApps = data;
        }

        if (append) {
            allApps = [...allApps, ...newApps];
        } else {
            allApps = newApps;
            // Clear columns if fresh load
            ['applied', 'invited', 'interviewing', 'offer', 'hired', 'rejected'].forEach(status => {
                const el = document.getElementById(`col-${status}`);
                if (el) el.innerHTML = '';
            });
        }


        // If no apps found, show empty message in Applied column (or handle generally)
        if (allApps.length === 0 && !append) {
            const colApplied = document.getElementById('col-applied');
            if (colApplied) XSS.safeSetHTML(colApplied, `<div class="p-8 text-center text-slate-400 font-medium">${window.t('recruiter.pipeline.no_candidates')}</div>`);
        }

        renderPipeline(false);
        updateLoadMoreButton();

    } catch (e) {
        console.error("Failed to load apps", e);
        showToast(window.t('recruiter.pipeline.failed_load'), "error");
        ['applied', 'invited', 'interviewing', 'offer', 'hired', 'rejected'].forEach(status => {
            const el = document.getElementById(`col-${status}`);
            if (el) el.innerHTML = '';
        });
        const colApplied = document.getElementById('col-applied');
        if (colApplied) XSS.safeSetHTML(colApplied, `<div class="p-8 text-center"><i class="fas fa-exclamation-triangle text-2xl text-amber-400 mb-2"></i><div class="text-sm font-semibold text-slate-500">${window.t('recruiter.pipeline.load_error')}</div><button type="button" data-pipeline-retry class="mt-3 px-4 py-1.5 bg-indigo-50 text-indigo-600 text-xs font-bold rounded-lg hover:bg-indigo-100 transition"><i class="fas fa-redo mr-1"></i>Retry</button></div>`);
    } finally {
        isLoading = false;
    }
}

function updateLoadMoreButton() {
    const container = document.getElementById('pipeline-load-more');
    if (container) {
        if (paginationMeta && paginationMeta.has_next) {
            if (_scrollContainerIsWindow) {
                container.classList.remove('hidden');
                container.innerHTML = `
                            <button type="button" id="pipeline-next-page" class="px-6 py-2 bg-white border border-slate-200 rounded-full text-indigo-600 font-bold shadow-sm hover:bg-slate-50 transition">
                                ${window.t('recruiter.pipeline.load_more', { count: paginationMeta.total - (paginationMeta.page * paginationMeta.per_page) })}
                            </button>
                        `;
            } else {
                container.classList.add('hidden');
            }
        } else {
            container.classList.add('hidden');
        }
    }
}

function renderKanban(apps) {
    // Clear Columns (applied -> invited -> interviewing -> offer -> hired -> rejected)
    ['applied', 'invited', 'interviewing', 'offer', 'hired', 'rejected'].forEach(status => {
        const el = document.getElementById(`col-${status}`);
        if (el) el.innerHTML = '';
    });

    apps.forEach(app => {
        if (app.status === 'archived') return;

        const displayStatus = app.display_status || app.status;
        const card = createCard(app);
        const col = document.getElementById(`col-${displayStatus}`) || document.getElementById('col-applied');
        if (col) col.appendChild(card);
    });

    if (apps.length === 0) {
        const colApplied = document.getElementById('col-applied');
        if (colApplied) XSS.safeSetHTML(colApplied, `<div class="p-8 text-center text-slate-400 font-medium">${window.t('recruiter.pipeline.no_candidates')}</div>`);
    }
}

function createCard(app) {
    const div = document.createElement('div');
    // Premium Card Style (Intelligence Hub System)
    div.className = "candidate-card glass-panel p-4 mb-4 rounded-2xl relative group cursor-grab active:cursor-grabbing";
    div.draggable = true;
    div.dataset.id = app.id;

    // Status Indicator Dot (Modern replacement for the left border)
    const statusColors = {
        'hired': 'bg-indigo-500',
        'rejected': 'bg-red-500',
        'offer': 'bg-amber-500',
        'interviewing': 'bg-indigo-500',
        'invited': 'bg-sky-500',
        'applied': 'bg-slate-400'
    };
    const dotColor = statusColors[app.status] || 'bg-slate-400';

    const isInterview = (app.score > 0);
    const displayScore = isInterview ? app.score : (app.cv_score || 0);

    // Premium Score Badge logic
    const getScoreBadgeClass = (s) => {
        if (s >= 85) return 'bg-purple-500/10 text-purple-600 border-purple-200';
        if (s >= 70) return 'bg-indigo-500/10 text-indigo-600 border-indigo-200';
        return 'bg-amber-500/10 text-amber-600 border-amber-200';
    };
    const getScoreLabel = (s) => {
        if (s >= 85) return 'Strong match';
        if (s >= 70) return 'Good match';
        return 'Needs review';
    };

    div.innerHTML = `
                <!-- Selection Checkbox -->
                <div class="absolute top-4 right-4 z-10">
                    <input type="checkbox" 
                        class="candidate-checkbox w-4 h-4 rounded-lg border-slate-200 text-indigo-600 focus:ring-indigo-500/20 cursor-pointer shadow-sm hover:border-indigo-400 transition"
                        data-app-id="${app.id}"
                        onchange="toggleSelection('${app.id}', this.checked)"
                        onclick="event.stopPropagation()"
                        ${selectedApplications.has(String(app.id)) ? 'checked' : ''}>
                </div>
                
                <div class="flex items-start gap-3 mb-4 pr-6">
                    ${app.photo_url ? `<img src="${Components.safeHTML(app.photo_url)}" class="w-9 h-9 rounded-full object-cover border-2 border-white shadow-sm flex-shrink-0" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"><div class="w-9 h-9 rounded-full ${dotColor} flex items-center justify-center text-white text-xs font-bold flex-shrink-0" style="display:none">${(app.candidate_name||'?')[0]}</div>` : `<div class="w-9 h-9 rounded-full ${dotColor} flex items-center justify-center text-white text-xs font-bold flex-shrink-0">${(app.candidate_name||'?')[0]}</div>`}
                    <div>
                        <div class="flex items-center gap-2">
                            <h4 class="font-bold text-slate-900 text-sm leading-tight font-outfit">${Components.safeHTML(app.candidate_name)}</h4>
                            <div class="w-1.5 h-1.5 rounded-full ${dotColor} opacity-50 flex-shrink-0"></div>
                        </div>
                        <div class="text-[10px] text-slate-400 font-bold uppercase tracking-widest mt-1">${Components.safeHTML(app.role) || 'General Role'}</div>
                    </div>
                </div>
                
                ${app.assigned_to ? `<div class="text-[9px] font-bold text-indigo-600 bg-indigo-50/50 border border-indigo-100/50 px-2.5 py-1 rounded-lg flex items-center gap-1.5 mb-3 w-fit">
                    <i class="fas fa-user-check text-[8px]"></i>
                    ${Components.safeHTML(app.assigned_to.name || 'Assigned')}
                </div>` : ''}
                
                    <div class="flex items-center gap-2 mb-1">
                        <div title="${getScoreLabel(displayScore)} (${Math.round(displayScore)}/100)" class="px-3 py-1 rounded-lg border flex items-center gap-1.5 font-black text-xs ${getScoreBadgeClass(displayScore)} shadow-sm">
                            ${isInterview ? '<i class="fas fa-brain text-[10px]"></i>' : '<i class="fas fa-file-pdf text-[10px]"></i>'}
                            ${Math.round(displayScore)}
                        </div>
                        <div class="h-1 flex-1 bg-slate-100/50 rounded-full overflow-hidden">
                             <div class="h-full bg-indigo-500/30" style="width: ${displayScore}%"></div>
                        </div>
                    </div>
                    ${app.scorecard_avg !== null && app.scorecard_avg !== undefined ? `
                    <div class="flex items-center gap-1.5 mb-4">
                        <span class="text-[9px] font-bold text-slate-400 uppercase tracking-widest">Eval</span>
                        <span class="text-[10px] font-black px-1.5 py-0.5 rounded ${app.scorecard_avg >= 70 ? 'text-indigo-600 bg-indigo-50' : app.scorecard_avg >= 40 ? 'text-amber-600 bg-amber-50' : 'text-red-600 bg-red-50'}">${Math.round(app.scorecard_avg)}%</span>
                    </div>` : ''}

                ${(() => { const _iv = app.interview_entity || {}; const _ivProgress = _iv.interview_progress ?? app.interview_progress; const _ivState = _iv.interview_state ?? app.interview_state; return _ivProgress > 0 || _ivState === 'completed' ? `
                <div class="mb-4 p-2 bg-slate-50/50 rounded-xl border border-slate-100/50">
                    <div class="flex justify-between items-center mb-1.5 px-1">
                        <span class="text-[9px] font-bold text-slate-400 uppercase tracking-widest">Progress</span>
                        <span class="text-[9px] font-black text-indigo-600">${_ivProgress || 0}/${app.total_questions || 15}</span>
                    </div>
                    <div class="w-full h-1.5 bg-slate-200/50 rounded-full overflow-hidden">
                        <div class="h-full bg-indigo-500 transition-all duration-700" style="width: ${Math.min(100, ((_ivProgress || 0) / (app.total_questions || 15)) * 100)}%"></div>
                    </div>
                </div>` : ''; })()}

                <div class="flex items-center justify-between pt-3 border-t border-slate-100/50">
                    <span class="text-[9px] text-slate-400 font-bold uppercase tracking-widest">${app.created_at || 'Recently'}</span>
                    <div class="flex gap-1.5">
                        <button onclick="viewGhostReport(${parseInt(app.id)})" class="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center hover:bg-indigo-600 hover:text-white transition shadow-sm" title="Intelligence Report">
                             <i class="fas fa-ghost text-xs"></i>
                        </button>
                        <button onclick="viewProfile(${parseInt(app.id)})" class="px-3 py-1 rounded-lg bg-indigo-600 text-white text-[10px] font-bold uppercase tracking-widest shadow-lg shadow-indigo-500/20 hover:scale-105 transition">
                            View
                        </button>
                    </div>
                </div>

                <!-- Quick Actions (v5.0) -->
                ${app.status === 'applied' || app.status === 'screening' ? `
                <div class="quick-actions flex gap-1 mt-2 pt-2 border-t border-slate-100/50">
                    <button data-quick-action="invite" data-app-id="${app.id}"
                        class="flex-1 py-1 px-2 rounded-lg text-[9px] font-bold uppercase tracking-wider bg-sky-50 text-sky-600 hover:bg-sky-600 hover:text-white transition"
                        title="Send Interview Invite">
                        <i class="fas fa-envelope"></i> Invite
                    </button>
                    <button data-quick-action="shortlist" data-app-id="${app.id}"
                        class="flex-1 py-1 px-2 rounded-lg text-[9px] font-bold uppercase tracking-wider bg-indigo-50 text-indigo-600 hover:bg-indigo-600 hover:text-white transition"
                        title="Move to Interviewing">
                        <i class="fas fa-star"></i> Shortlist
                    </button>
                    <button data-quick-action="reject" data-app-id="${app.id}"
                        class="flex-1 py-1 px-2 rounded-lg text-[9px] font-bold uppercase tracking-wider bg-red-50 text-red-600 hover:bg-red-600 hover:text-white transition"
                        title="Reject Candidate">
                        <i class="fas fa-times"></i> Reject
                    </button>
                </div>` : ''}
            `;

    // DnD Events
    div.addEventListener('dragstart', () => {
        div.classList.add('dragging');
        window.draggedId = app.id;
    });
    div.addEventListener('dragend', () => {
        div.classList.remove('dragging');
        window.draggedId = null;
    });

    return div;
}

function getScoreColor(score) {
    if (score >= 85) return 'text-purple-500';
    if (score >= 70) return 'text-indigo-500';
    return 'text-amber-500';
}

// Navigation Helper
function viewRoadmap(userId) {
    window.location.href = `/candidate/learning?view=active&userId=${parseInt(userId)}`;
}

function viewProfile(appId) {
    window.location.href = `/recruiter/candidate?id=${parseInt(appId)}`;
}

function viewGhostReport(appId) {
    window.open(`/recruiter/candidate/${parseInt(appId)}/report`, '_blank');
}

// --- NEW VIEW LOGIC ---
function populateJobFilter() {
    populateFilterDropdown('job', allJobs, window.t('recruiter.pipeline.all_jobs'));
    // Also add handler for score filter
    const scoreSelect = document.getElementById('filter-score');
    if (scoreSelect) {
        scoreSelect.onchange = function() {
            loadApplications(1, false);
        };
    }
}

function populateCampaignFilter() {
    populateFilterDropdown('batch', allCampaigns, window.t('recruiter.pipeline.all_campaigns'));
}

function toggleView(view) {
    currentView = view;
    document.getElementById('btn-view-board')?.classList.toggle('active', view === 'board');
    document.getElementById('btn-view-list')?.classList.toggle('active', view === 'list');
    document.getElementById('btn-view-ranked')?.classList.toggle('active', view === 'ranked');

    document.getElementById('view-board')?.classList.toggle('hidden', view !== 'board');
    document.getElementById('view-list')?.classList.toggle('hidden', view !== 'list');
    document.getElementById('view-ranked')?.classList.toggle('hidden', view !== 'ranked');

    renderPipeline();
}

function renderPipeline(applyClientFilters = true) {
    if (currentView === 'board') renderKanban(allApps);
    else if (currentView === 'ranked') renderRanked(allApps);
    else renderList(allApps);

    updateStageCounts();
    updateStats();
    updateBulkToolbar();
}

function updateStageCounts() {
    const ps = window._pipelineStats || {};
    const counts = ps.status_counts || {};
    ['applied', 'invited', 'interviewing', 'offer', 'hired', 'rejected'].forEach(status => {
        const el = document.getElementById(`badge-count-${status}`);
        if (el) el.textContent = counts[status] || 0;
    });
}

function filterApps() {
    // Trigger server-side reload
    loadApplications(1, false);
}

function renderList(apps) {
    const tbody = document.getElementById('list-tbody');
    if (!tbody) return;
    tbody.innerHTML = apps.map(app => {
        // SECURITY: Sanitize all user-controlled data
        const safeName = SecurityUtils.escapeHTML(app.candidate_name || 'Unknown');
        const safeEmail = SecurityUtils.escapeHTML(app.email || 'No email');
        const safeRole = SecurityUtils.escapeHTML(app.role || 'General Role');
        const safeId = parseInt(app.id) || 0;
        const safeUserId = parseInt(app.user_id) || 0;

        const isInterview = (app.score > 0);
        const displayScore = isInterview ? app.score : (app.cv_score || 0);
        const scoreIcon = isInterview ? '' : '<i class="fas fa-file-pdf mr-1 text-slate-400"></i>';

        return `
                <tr class="hover:bg-slate-50 transition border-b border-slate-100">
                    <td class="p-4">
                        <input type="checkbox" 
                            class="candidate-checkbox w-4 h-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                            data-app-id="${safeId}"
                            onchange="toggleSelection(${safeId}, this.checked)"
                            ${selectedApplications.has(String(app.id)) ? 'checked' : ''}>
                    </td>
                    <td class="p-4">
                        <div class="font-bold text-slate-800">${safeName}</div>
                        ${app.score > 0 ? `<a href="/recruiter/comparison?id=${safeId}" class="text-[10px] text-indigo-600 font-bold hover:underline">Why the change?</a>` : ''}
                        <div class="text-xs text-slate-400">${safeEmail}</div>
                    </td>
                    <td class="p-4 text-sm text-slate-600">${safeRole}</td>
                    <td class="p-4">
                        <span class="font-bold ${getScoreColor(displayScore)} flex items-center gap-1">
                            ${displayScore === 0 ? `<span class="bg-red-100 text-red-600 px-2 py-0.5 rounded text-[10px] uppercase font-black tracking-wide border border-red-200">${window.t('recruiter.pipeline.not_matched')}</span>` : `${scoreIcon}${Math.round(displayScore)}/100`}
                        </span>
                    </td>
                    <td class="p-4">
                        <select onchange="handleStatusChange(${safeId}, this.value)" 
                            class="bg-slate-100 border-none text-xs font-bold rounded-lg py-1 px-2 uppercase tracking-wide text-slate-600 focus:ring-2 focus:ring-indigo-500">
                            <option value="applied" ${app.status === 'applied' ? 'selected' : ''}>${window.t('recruiter.pipeline.status.applied')}</option>
                            <option value="invited" ${app.status === 'invited' ? 'selected' : ''}>${window.t('recruiter.pipeline.status.invited')}</option>
                            <option value="interviewing" ${app.status === 'interviewing' ? 'selected' : ''}>${window.t('recruiter.pipeline.status.interviewing')}</option>
                            <option value="offer" ${app.status === 'offer' ? 'selected' : ''}>${window.t('recruiter.pipeline.status.offer')}</option>
                            <option value="hired" ${app.status === 'hired' ? 'selected' : ''}>${window.t('recruiter.pipeline.status.hired')}</option>
                            <option value="rejected" ${app.status === 'rejected' ? 'selected' : ''}>${window.t('recruiter.pipeline.status.rejected')}</option>
                            <option value="archived" ${app.status === 'archived' ? 'selected' : ''}>${window.t('recruiter.pipeline.status.archived')}</option>
                        </select>
                        ${(() => { const _ivPl = app.interview_entity || {}; const _ivPlProgress = _ivPl.interview_progress ?? app.interview_progress; return _ivPlProgress > 0 ? `
                        <div class="mt-1 text-[9px] font-bold text-slate-400 flex items-center gap-1">
                            <i class="fas fa-tasks"></i> Progress: ${_ivPlProgress}/${app.total_questions || 15}
                        </div>` : ''; })()}
                    </td>
                    <td class="p-4 text-right">
                        <button onclick="deleteApplication(${safeId}, event)" class="text-red-600 hover:text-red-800 font-bold text-xs bg-red-50 px-3 py-1.5 rounded-lg transition mr-1" title="Delete Candidate">
                            <i class="fas fa-trash-alt"></i>
                        </button>
                        <button onclick="viewGhostReport(${safeId})" class="text-indigo-600 hover:text-indigo-800 font-bold text-xs bg-indigo-50 px-3 py-1.5 rounded-lg transition mr-1" title="Anonymized Client Report">
                            <i class="fas fa-ghost"></i> ${window.t('recruiter.pipeline.ghost')}
                        </button>
                        <button onclick="viewProfile(${safeId})" class="text-indigo-600 hover:text-indigo-800 font-bold text-xs bg-indigo-50 px-3 py-1.5 rounded-lg transition">
                            ${window.t('recruiter.pipeline.view_profile')}
                        </button>
                    </td>
                </tr>
            `;
    }).join('');
}

function renderRanked(apps) {
    const container = document.getElementById('ranked-container');
    if (!container) return;

    const scored = apps.filter(a => (a.score || a.cv_score || 0) > 0);
    const unscored = apps.filter(a => !a.score && !a.cv_score);

    scored.sort((a, b) => (b.score || b.cv_score || 0) - (a.score || a.cv_score || 0));

    container.innerHTML = [
        ...scored.map((app, i) => createRankedRow(app, i + 1)),
        ...(unscored.length ? [`<div class="pt-4 pb-2 text-xs font-bold text-slate-400 uppercase tracking-widest">Unscored (${unscored.length})</div>`] : []),
        ...unscored.map((app, i) => createRankedRow(app, null))
    ].join('');
}

function createRankedRow(app, rank) {
    const displayScore = app.score || app.cv_score || 0;
    const scoreLabel = displayScore >= 85 ? 'Strong match' : displayScore >= 70 ? 'Good match' : displayScore >= 1 ? 'Needs review' : 'No score';
    const scoreColor = displayScore >= 85 ? 'text-purple-600 bg-purple-100' : displayScore >= 70 ? 'text-indigo-600 bg-indigo-100' : displayScore >= 1 ? 'text-amber-600 bg-amber-100' : 'text-slate-400 bg-slate-100';

    const badge = app.status === 'hired' ? '<span class="text-[9px] font-black text-indigo-600 bg-indigo-100 px-2 py-0.5 rounded-full uppercase tracking-wider">Hired</span>' :
                  app.status === 'rejected' ? '<span class="text-[9px] font-black text-red-600 bg-red-100 px-2 py-0.5 rounded-full uppercase tracking-wider">Rejected</span>' :
                  app.status === 'interviewing' || app.status === 'completed' ? '<span class="text-[9px] font-black text-indigo-600 bg-indigo-100 px-2 py-0.5 rounded-full uppercase tracking-wider">Active</span>' : '';

    const interviewScore = app.score ? `<div class="flex items-center gap-1.5 text-[10px]"><i class="fas fa-brain text-indigo-400"></i><span class="font-bold text-indigo-600">${Math.round(app.score)}</span><span class="text-slate-400">interview</span></div>` : '';
    const cvScore = app.cv_score ? `<div class="flex items-center gap-1.5 text-[10px]"><i class="fas fa-file-pdf text-slate-400"></i><span class="font-bold text-slate-600">${Math.round(app.cv_score)}</span><span class="text-slate-400">CV match</span></div>` : '';

    const safeName = SecurityUtils.escapeHTML(app.candidate_name || 'Unknown');
    const safeRole = SecurityUtils.escapeHTML(app.role || 'General');

    return `
        <div class="flex items-center gap-4 p-4 bg-white border border-slate-100 rounded-xl hover:shadow-md hover:border-indigo-200 transition cursor-pointer" onclick="viewProfile(${parseInt(app.id)})">
            <div class="shrink-0 w-10 text-center">
                ${rank !== null ? `<div class="text-lg font-black text-slate-300 font-outfit">#${rank}</div>` : '<div class="text-lg text-slate-200"><i class="fas fa-minus"></i></div>'}
            </div>
            <div class="shrink-0 w-1 h-10 rounded-full ${app.score ? 'bg-indigo-500' : 'bg-slate-300'}"></div>
            <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                    <span class="font-bold text-slate-900 text-sm truncate">${safeName}</span>
                    ${badge}
                </div>
                <div class="text-[11px] text-slate-400 font-bold">${safeRole}</div>
                <div class="flex items-center gap-3 mt-1">
                    ${interviewScore}${cvScore}
                </div>
            </div>
            <div class="shrink-0 flex items-center gap-3">
                <div class="text-right">
                    <div class="text-2xl font-black font-outfit ${scoreColor.split(' ')[0]}">${displayScore > 0 ? Math.round(displayScore) : '--'}</div>
                    <div class="text-[9px] font-bold text-slate-400 uppercase tracking-widest">${scoreLabel}</div>
                </div>
                <div class="w-16 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                    <div class="h-full rounded-full ${displayScore >= 85 ? 'bg-purple-500' : displayScore >= 70 ? 'bg-indigo-500' : displayScore >= 1 ? 'bg-amber-500' : 'bg-slate-200'}" style="width: ${Math.min(100, displayScore)}%"></div>
                </div>
                <button onclick="event.stopPropagation();viewGhostReport(${parseInt(app.id)})" class="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center hover:bg-indigo-600 hover:text-white transition" title="Intelligence Report">
                    <i class="fas fa-ghost text-xs"></i>
                </button>
            </div>
        </div>
    `;
}

async function deleteApplication(id, e) {
    e.stopPropagation(); // Prevent drag issue or navigation
    if (!await Components.showConfirm(
        window.t('recruiter.pipeline.delete_confirm_title'),
        window.t('recruiter.pipeline.delete_confirm_desc'),
        window.t('recruiter.pipeline.delete_btn'),
        "danger"
    )) return;

    try {
        // Delete Application
        await window.fetchAPI(`/recruiter/applications/${parseInt(id)}`, {
            method: 'DELETE'
        });

        // Remove the application from allApps and re-render
        allApps = allApps.filter(app => app.id !== id);
        selectedApplications.delete(id); // Also remove from selection
        renderPipeline(); // Refresh board/list
        updateStats();
        showToast(window.t('recruiter.pipeline.delete_success'), "success");

    } catch (err) {
        console.error(err);
        showToast(window.t('recruiter.pipeline.delete_error'), "error");
    }
}

async function updateStatus(appId, newStatus) {
    const app = allApps.find(a => a.id == appId);
    const oldStatus = app ? app.status : null;

    // Optimistic update
    if (app) app.status = newStatus;
    renderPipeline();
    updateStats();

    try {
        await window.fetchAPI(`/recruiter/applications/${parseInt(appId)}/status`, {
            method: 'PUT',
            body: JSON.stringify({ status: newStatus })
        });

        // Broadcast to other tabs/pages
        if (window.StageSync) {
            window.StageSync.broadcast({ appId, oldStatus, newStatus });
        }

        if (newStatus === 'archived') {
            allApps = allApps.filter(a => a.id != appId);
            renderPipeline();
        }
        showToast(window.t('recruiter.pipeline.status_success'), "success");

    } catch (err) {
        console.error(err);
        // Rollback on failure
        if (app && oldStatus !== null) {
            app.status = oldStatus;
            renderPipeline();
            updateStats();
        }
        showToast(window.t('recruiter.pipeline.status_error'), "error");
    }
}

function handleStatusChange(appId, newStatus) {
    if (newStatus === 'invited') {
        openOfferModal(appId);
    } else {
        updateStatus(appId, newStatus);
    }
}

function updateStats() {
    const ps = window._pipelineStats || {};
    const total = ps.total_applications !== undefined ? ps.total_applications : (paginationMeta ? paginationMeta.total : allApps.length);
    const totalUnique = ps.total_candidates !== undefined ? ps.total_candidates : total;
    const newThisWeek = ps.new_this_week !== undefined ? ps.new_this_week : 0;
    const statusCounts = ps.status_counts || {};
    const conversionRates = ps.conversion_rates || {};
    const interviewCount = statusCounts['interviewing'] || 0;
    const hiredCount = statusCounts['hired'] || 0;
    const inReview = (statusCounts['applied'] || 0) + (statusCounts['screening'] || 0) + (statusCounts['invited'] || 0);
    const offers = statusCounts['offer'] || 0;
    const conversion = conversionRates.overall !== undefined ? Math.round(conversionRates.overall) : 0;

    const set = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };
    set('count-total-apps', total);
    set('count-total', totalUnique);
    set('count-new', newThisWeek);
    set('count-review', inReview);
    set('count-interviewing', interviewCount);
    set('count-offer', offers);
    set('count-hired', hiredCount);

    const convEl = document.getElementById('count-conversion');
    if (convEl) convEl.innerText = conversion + '%';
    const convCircle = document.getElementById('conversion-ring-circle');
    if (convCircle) {
        const circumference = 2 * Math.PI * 18;
        convCircle.setAttribute('stroke-dashoffset', circumference - (circumference * conversion / 100));
    }
}

// DnD Logic for Columns
function setupColumns() {
    const columns = document.querySelectorAll('.kanban-col');
    columns.forEach(col => {
        col.addEventListener('dragover', e => {
            e.preventDefault(); // Allow drop
            col.classList.add('drag-over');
        });

        col.addEventListener('dragleave', () => col.classList.remove('drag-over'));

        col.addEventListener('drop', async (e) => {
            e.preventDefault();
            col.classList.remove('drag-over');
            const appId = window.draggedId;
            const newStatus = col.dataset.status;

            if (appId && newStatus) {
                // INTERCEPT INVITED STATUS (Was Offer)
                if (newStatus === 'invited') {
                    openOfferModal(appId); // Reusing logic, renaming labels later
                    return;
                }

                // Optimistic update for DnD
                const app = allApps.find(a => a.id == appId);
                const oldStatus = app ? app.status : null;
                if (app) app.status = newStatus;
                renderPipeline();
                updateStats();

                try {
                    await window.fetchAPI(`/recruiter/applications/${parseInt(appId)}/status`, {
                        method: 'PUT',
                        body: JSON.stringify({ status: newStatus })
                    });

                    // Broadcast to other tabs/pages
                    if (window.StageSync && oldStatus !== newStatus) {
                        window.StageSync.broadcast({ appId, oldStatus, newStatus });
                    }

                    if (newStatus === 'archived') {
                        allApps = allApps.filter(a => a.id != appId);
                        renderPipeline();
                    }
                    showToast(window.t('recruiter.pipeline.status_success'), "success");
                } catch (err) {
                    console.error("Drop update failed:", err);
                    // Rollback
                    if (app && oldStatus !== null) {
                        app.status = oldStatus;
                        renderPipeline();
                        updateStats();
                    }
                    showToast(window.t('recruiter.pipeline.update_failed'), "error");
                }
            }
        });
    });
}

// --- INVITATION EMAIL MODAL LOGIC (Renamed from Offer) ---
let currentOfferAppId = null;
let quill = null;

async function openOfferModal(appId) {
    try {
        currentOfferAppId = appId;

        // Show modal first so it's ready
        const modal = document.getElementById('offer-modal');
        if (modal) modal.classList.remove('hidden');

        // Update Title
        const modalTitleEl = document.querySelector('#offer-modal h3, #offer-modal .modal-title');
        if (modalTitleEl) XSS.safeSetHTML(modalTitleEl, `<i class="fas fa-envelope text-indigo-600"></i> ${window.t('recruiter.pipeline.modal_invite_title')}`);

        const btnSend = document.getElementById('btn-send-offer');
        if (btnSend) XSS.safeSetHTML(btnSend, `${window.t('recruiter.pipeline.modal_invite_btn')} <i class="fas fa-paper-plane"></i>`);

        const subjectInput = document.getElementById('email-subject');
        if (subjectInput) subjectInput.value = '';

        // Load Templates IMMEDIATELY (Don't wait for Quill)
        loadTemplatesDropdown();

        // Initialize Quill if not already done
        if (!quill) {
            if (typeof Quill !== 'undefined') {
                quill = new Quill('#editor-container', {
                    theme: 'snow',
                    placeholder: window.t('recruiter.pipeline.modal_invite_placeholder'),
                    modules: {
                        toolbar: [
                            ['bold', 'italic', 'underline', 'strike'],
                            [{ 'list': 'ordered' }, { 'list': 'bullet' }],
                            [{ 'header': [1, 2, 3, false] }],
                            [{ 'color': [] }, { 'background': [] }],
                            ['link', 'clean']
                        ]
                    }
                });
            } else {
                console.error("Quill.js is not loaded!");
                // Fallback: create a basic textarea if needed, but for now just alert
            }
        }

        // Reset Editor
        if (quill) {
            quill.root.innerHTML = '';
        } else {
            // If Quill failed, we might still want a way to input text?
            // For now, let's hope it loads or warn user.
        }

        // Reset Tabs
        switchTab('write');

        // Trigger default preview load
        setTimeout(() => loadTemplatePreview(), 500);

    } catch (err) {
        console.error("Error opening invitation modal:", err);
        showToast("Could not open invitation modal correctly", "error");
    }
}

function switchTab(tab) {
    const btnWrite = document.getElementById('tab-write');
    const btnPreview = document.getElementById('tab-preview');
    const viewWrite = document.getElementById('view-write');
    const viewPreview = document.getElementById('view-preview');
    if (!btnWrite || !btnPreview || !viewWrite || !viewPreview) return;

    if (tab === 'write') {
        // Active Write
        btnWrite.classList.add('border-indigo-600', 'text-indigo-600');
        btnWrite.classList.remove('border-transparent', 'text-slate-400');
        // Inactive Preview
        btnPreview.classList.remove('border-indigo-600', 'text-indigo-600');
        btnPreview.classList.add('border-transparent', 'text-slate-400');

        viewWrite.classList.remove('hidden');
        viewPreview.classList.add('hidden');
    } else {
        // Inactive Write
        btnWrite.classList.remove('border-indigo-600', 'text-indigo-600');
        btnWrite.classList.add('border-transparent', 'text-slate-400');
        // Active Preview
        btnPreview.classList.add('border-indigo-600', 'text-indigo-600');
        btnPreview.classList.remove('border-transparent', 'text-slate-400');

        viewWrite.classList.add('hidden');
        viewPreview.classList.remove('hidden');
        updatePreview();
    }
}

function updatePreview() {
    const rawHtml = quill.root.innerHTML;
    const container = document.getElementById('email-preview-content');

    // Simulate Variable Replacement for Preview
    let previewHtml = rawHtml
        .replace(/{{INTERVIEW_LINK}}|{INTERVIEW_LINK}/g, '<a href="#" class="inline-block bg-indigo-600 text-white font-bold py-3 px-6 rounded-lg shadow-md hover:bg-indigo-700 transition decoration-0">Start AI Interview</a>')
        .replace(/\n/g, '<br>');

    // Enhance Preview with basic styles if they are missing
    XSS.safeSetHTML(container, `<div class="prose prose-sm max-w-none text-slate-700 font-sans leading-relaxed">${XSS.sanitize(previewHtml)}</div>`);
}

async function loadTemplatesDropdown() {
    const select = document.getElementById('email-template-select');
    if (!select) return;

    // Reset immediately to generic so UI is never stuck on "Loading"
    select.innerHTML = '<option value="">-- Use Default (Generic) --</option>';

    try {
        let templates = await window.fetchAPI('/recruiter/templates');

        // If no templates, try seeding defaults automatically
        if (Array.isArray(templates) && templates.length === 0) {
            console.info("No templates found, seeding defaults...");
            try {
                await window.fetchAPI('/recruiter/templates/seed', { method: 'POST' });
                templates = await window.fetchAPI('/recruiter/templates');
            } catch (seedErr) {
                console.error("Auto-seeding failed:", seedErr);
            }
        }

        if (Array.isArray(templates) && templates.length > 0) {
            // Re-add options if we have them
            templates.forEach(t => {
                const opt = document.createElement('option');
                opt.value = t.id;
                opt.text = t.name + (t.is_default ? ' (Default)' : '');
                if (t.is_default) opt.selected = true;
                select.appendChild(opt);
            });
        }
    } catch (e) {
        console.error("Failed to load templates:", e);
        // We already set generic as fallback above
    }
}

async function loadTemplatePreview() {
    if (!currentOfferAppId) return;
    const tplEl = document.getElementById('email-template-select');
    const tplId = tplEl ? tplEl.value : '';

    // Show loading state in editor if empty
    if (quill && quill.getText().trim().length === 0) {
        quill.root.innerHTML = "<p>Generating preview...</p>";
    }

    try {
        const data = await window.fetchAPI('/recruiter/generate-invitation', {
            method: 'POST',
            body: JSON.stringify({
                app_id: currentOfferAppId,
                template_id: tplId ? parseInt(tplId) : null
            })
        });

        const subjectEl = document.getElementById('email-subject');
        if (subjectEl) subjectEl.value = data.subject || '';
        // Populate Quill
        if (quill) {
            const formattedBody = (data.body || '').replace(/\n/g, '<br>');
            quill.clipboard.dangerouslyPasteHTML(formattedBody);
        }
    } catch (e) { console.error(e); }
}

function closeOfferModal() {
    document.getElementById('offer-modal')?.classList.add('hidden');
    currentOfferAppId = null;
}

async function generateAiOffer() {
    if (!currentOfferAppId) return;
    const btn = document.getElementById('btn-ai-write');
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Writing...';

    try {
        // Call NEW Invitation Endpoint
        const data = await window.fetchAPI('/recruiter/generate-invitation', {
            method: 'POST',
            body: JSON.stringify({ app_id: currentOfferAppId })
        });

        const subjectEl = document.getElementById('email-subject');
        if (subjectEl) subjectEl.value = data.subject || '';
        if (quill) {
            const formattedBody = (data.body || '').replace(/\n/g, '<br>');
            quill.clipboard.dangerouslyPasteHTML(formattedBody);
        }
        showToast("AI Generated Draft!", "success");
    } catch (e) { console.error(e); }

    btn.innerHTML = '<i class="fas fa-magic"></i> Auto-write with AI';
}

async function sendOffer() {
    if (!currentOfferAppId) return;
    const subjectEl = document.getElementById('email-subject');
    const subject = subjectEl ? subjectEl.value : '';
    // Get HTML from Quill
    const body = quill ? quill.root.innerHTML : '';

    // Simple validation (Quill empty is usually <p><br></p>)
    if (!subject || !body || body === '<p><br></p>') {
        alert("Please fill in the email details.");
        return;
    }

    const btn = document.getElementById('btn-send-offer');
    if (!btn) return;
    const originalContent = btn.innerHTML;
    XSS.safeSetHTML(btn, `<i class="fas fa-spinner fa-spin"></i> ${window.t('common.sending')}`);
    btn.disabled = true;

    try {
        const data = await window.fetchAPI(`/recruiter/send-invitation?app_id=${currentOfferAppId}`, {
            method: 'POST',
            body: JSON.stringify({ subject, body })
        });

        // Success Animation
        btn.className = "bg-indigo-600 text-white px-6 py-2.5 rounded-xl font-bold shadow-lg shadow-indigo-500/30 flex items-center gap-2 transition-all duration-300 scale-105";
        XSS.safeSetHTML(btn, `<i class="fas fa-check-circle fa-lg"></i> ${window.t('common.success')}`);

        // Update Pipeline UI immediately
        const app = allApps.find(a => a.id == currentOfferAppId);
        if (app) {
            const oldStatus = app.status;
            app.status = 'invited';
            renderPipeline();
            updateStats();

            // Broadcast to other tabs/pages
            if (window.StageSync) {
                window.StageSync.broadcast({ appId: currentOfferAppId, oldStatus, newStatus: 'invited' });
            }
        }

        // Auto Close
        setTimeout(() => {
            closeOfferModal();
            // Reset Button
            setTimeout(() => {
                btn.className = "bg-indigo-600 text-white px-6 py-2.5 rounded-xl font-bold hover:bg-indigo-700 shadow-lg shadow-indigo-500/30 flex items-center gap-2";
                btn.innerHTML = originalContent;
                btn.disabled = false;
            }, 300);
        }, 1500);

    } catch (e) {
        console.error(e);
        showToast(e.message || window.t('recruiter.pipeline.failed_load'), "error");
        btn.innerHTML = originalContent;
        btn.disabled = false;
    }
}



// --- Bulk Actions Logic ---
function toggleSelection(appId, isChecked) {
    if (isChecked) {
        selectedApplications.add(appId);
    } else {
        selectedApplications.delete(appId);
        // If one is unchecked, uncheck the "Select All" checkbox
        const selectAll = document.getElementById('select-all-checkbox');
        if (selectAll) selectAll.checked = false;
    }
    updateBulkToolbar();
}

function toggleSelectAll(isChecked) {
    const checkboxes = document.querySelectorAll('.candidate-checkbox');
    checkboxes.forEach(cb => {
        const appId = parseInt(cb.dataset.appId);
        if (!appId) return;

        cb.checked = isChecked;
        if (isChecked) {
            selectedApplications.add(appId);
        } else {
            selectedApplications.delete(appId);
        }
    });
    updateBulkToolbar();
}

function updateBulkToolbar() {
    const toolbar = document.getElementById('bulk-toolbar');
    const countSpan = document.getElementById('bulk-count');
    const compareBtn = document.getElementById('btn-bulk-compare');
    if (!toolbar) return;

    if (selectedApplications.size > 0) {
        toolbar.classList.remove('hidden');
        if (countSpan) countSpan.innerText = selectedApplications.size;
        if (compareBtn) {
            const canCompare = selectedApplications.size >= 2 && selectedApplications.size <= 5;
            compareBtn.disabled = !canCompare;
            compareBtn.title = canCompare
                ? `Compare ${selectedApplications.size} candidates`
                : 'Select 2-5 candidates to compare';
        }
    } else {
        toolbar.classList.add('hidden');
    }
}

async function bulkUpdateStatus(newStatus) {
    if (selectedApplications.size === 0) return;

    if (!await Components.showConfirm(
        "Bulk Update Status",
        `Are you sure you want to change the status of ${selectedApplications.size} candidates to "${newStatus.charAt(0).toUpperCase() + newStatus.slice(1)}"?`,
        "Update",
        "primary"
    )) return;

    const appIds = Array.from(selectedApplications);

    // Capture old statuses for rollback and broadcast
    const oldStatuses = {};
    allApps.forEach(app => {
        if (selectedApplications.has(String(app.id))) {
            oldStatuses[app.id] = app.status;
        }
    });

    // Optimistic update
    allApps.forEach(app => {
        if (selectedApplications.has(String(app.id))) {
            app.status = newStatus;
        }
    });
    renderPipeline();
    updateStats();

    try {
        await window.fetchAPI('/recruiter/applications/bulk-update', {
            method: 'POST',
            body: JSON.stringify({ app_ids: appIds, new_status: newStatus })
        });

        // Broadcast each change
        if (window.StageSync) {
            appIds.forEach(id => {
                window.StageSync.broadcast({ appId: id, oldStatus: oldStatuses[id], newStatus });
            });
        }

        showToast(`Updated ${selectedApplications.size} applications to ${newStatus}`, "success");
        clearSelection();
        renderPipeline();
        updateStats();

    } catch (e) {
        console.error("Bulk update error:", e);
        // Rollback
        allApps.forEach(app => {
            if (selectedApplications.has(String(app.id)) && oldStatuses[app.id]) {
                app.status = oldStatuses[app.id];
            }
        });
        renderPipeline();
        updateStats();
        showToast(e.message || "Bulk update failed", "error");
    }
}

async function bulkInvite() {
    if (selectedApplications.size === 0) return;
    const appIds = Array.from(selectedApplications);

    if (!await Components.showConfirm(
        "Bulk Invitation",
        `Are you sure you want to send AI interview invitations to ${selectedApplications.size} selected candidates?`,
        "Send Bulk Invites",
        "primary"
    )) return;

    try {
        // We use the bulk-invite endpoint which handles templates and background sending
        const result = await window.fetchAPI('/recruiter/applications/bulk-invite', {
            method: 'POST',
            body: JSON.stringify({
                application_ids: appIds,
                subject: "Invitation: Technical AI Interview | Candway",
                email_template: "Default Technical Interview Template"
            })
        });

        showToast(result.message || `Bulk invitation started for ${appIds.length} candidates`, "success");

        // Update local state and broadcast
        allApps.forEach(app => {
            if (selectedApplications.has(String(app.id))) {
                const oldStatus = app.status;
                app.status = 'invited';
                if (window.StageSync) {
                    window.StageSync.broadcast({ appId: app.id, oldStatus, newStatus: 'invited' });
                }
            }
        });

        clearSelection();
        renderPipeline();
        updateStats();

    } catch (e) {
        console.error("Bulk invite error:", e);
        showToast(e.message || "Bulk invitation failed", "error");
    }
}

function bulkGhostExport() {
    if (selectedApplications.size === 0) return;
    const idList = Array.from(selectedApplications);
    const appIds = idList.join(',');
    // Use the first ID as path parameter for the backend route
    window.open(`/recruiter/candidate/${idList[0]}/report?ids=${appIds}`, '_blank');
}

function compareSelected() {
    if (selectedApplications.size < 2 || selectedApplications.size > 5) {
        Components.showToast('Select 2-5 candidates to compare', 'warning');
        return;
    }
    const ids = Array.from(selectedApplications).join(',');
    window.location.href = `/recruiter/compare?ids=${ids}`;
}

async function bulkDeleteApplications() {
    if (selectedApplications.size === 0) return;

    if (!await Components.showConfirm(
        "Bulk Delete Candidates",
        `Are you sure you want to permanently remove ${selectedApplications.size} candidates? This action cannot be undone.`,
        "Delete All",
        "danger"
    )) return;

    const appIds = Array.from(selectedApplications);

    try {
        await window.fetchAPI('/recruiter/applications/bulk-delete', {
            method: 'POST',
            body: JSON.stringify({ app_ids: appIds })
        });

        // Update local data
        allApps = allApps.filter(app => !selectedApplications.has(String(app.id)));

        showToast(`Successfully deleted ${selectedApplications.size} candidates`, "success");
        clearSelection();
        renderPipeline();
        updateStats();

    } catch (e) {
        console.error("Bulk delete error:", e);
        showToast(e.message || "Bulk delete failed", "error");
    }
}

async function assignCandidate(appId, event) {
    event.stopPropagation();

    // Get current assignment
    const app = allApps.find(a => a.id === appId);
    const currentAssignment = app ? app.assigned_to : null;

    // Show assignment modal
    const recruiterId = await Components.showAssignmentModal(appId, currentAssignment);

    if (recruiterId === null && currentAssignment) {
        // Unassign
        try {
            await window.fetchAPI(`/recruiter/candidates/${appId}/assign`, { method: 'DELETE' });
            Components.showToast('Candidate unassigned', 'success');
            if (app) app.assigned_to = null;
            renderPipeline();
        } catch (e) {
            console.error(e);
            Components.showToast('Failed to unassign candidate', 'error');
        }
    } else if (recruiterId) {
        // Assign
        try {
            const result = await window.fetchAPI(`/recruiter/candidates/${appId}/assign`, {
                method: 'POST',
                body: JSON.stringify({ assigned_to_id: recruiterId })
            });
            Components.showToast('Candidate assigned successfully', 'success');
            if (app) app.assigned_to = result.assigned_to;
            renderPipeline();
        } catch (e) {
            console.error(e);
            Components.showToast('Failed to assign candidate', 'error');
        }
    }
}

async function loadMyAssigned() {
    try {
        const data = await window.fetchAPI('/recruiter/candidates/assigned-to-me');
        allApps = data.candidates || [];
        renderPipeline();
        updateStats();
        Components.showToast(`Showing ${allApps.length} assigned candidates`, 'info');
    } catch (e) {
        console.error(e);
        Components.showToast('Failed to load assigned candidates', 'error');
    }
}

// ── Custom filter dropdowns ──
function toggleFilterDropdown(name) {
    const menu = document.getElementById(`filter-${name}-menu`);
    if (!menu) return;
    document.querySelectorAll('.dropdown-menu').forEach(m => { if (m.id !== menu.id) m.classList.add('hidden'); });
    menu.classList.toggle('hidden');
}
function selectFilter(name, value, label) {
    document.getElementById(`filter-${name}-label`).textContent = label;
    document.getElementById(`filter-${name}`).value = value;
    document.getElementById(`filter-${name}-menu`).classList.add('hidden');
    document.querySelectorAll(`#filter-${name}-menu .dropdown-option`).forEach(o => o.classList.remove('selected'));
    const sel = document.querySelector(`#filter-${name}-menu .dropdown-option[data-value="${CSS.escape(value || '')}"]`);
    if (sel) sel.classList.add('selected');
    filterApps();
}
document.addEventListener('click', function(e) {
    if (!e.target.closest('.dropdown-wrap')) {
        document.querySelectorAll('.dropdown-menu').forEach(m => m.classList.add('hidden'));
    }
});
function populateFilterDropdown(name, items, defaultLabel) {
    const menu = document.getElementById(`filter-${name}-menu`);
    if (!menu) return;
    const select = document.getElementById(`filter-${name}`);
    select.innerHTML = '<option value=""></option>';
    const safeLabel = defaultLabel.replace(/'/g, "\\'");
    menu.innerHTML = `<div class="dropdown-option selected" data-value="" onclick="selectFilter('${name}', '', '${safeLabel}')">${safeLabel}</div>`;
    items.forEach(item => {
        const val = item.id || item.value;
        const lbl = item.title || item.name || item.label || val;
        const opt = document.createElement('option');
        opt.value = val; opt.textContent = lbl; select.appendChild(opt);
        const div = document.createElement('div');
        div.className = 'dropdown-option';
        div.dataset.value = val;
        div.textContent = lbl;
        div.onclick = function(){ selectFilter(name, val, lbl); };
        menu.appendChild(div);
    });
    // Restore from hidden select if value was set
    const currentVal = select.value;
    if (currentVal) {
        const matched = menu.querySelector(`.dropdown-option[data-value="${CSS.escape(currentVal)}"]`);
        if (matched) { matched.classList.add('selected'); document.getElementById(`filter-${name}-label`).textContent = matched.textContent; }
    }
}


// Set active nav (page doesn't call Components.init directly)
const _pipelineNav = document.querySelector('#main-sidebar .nav-link[data-page="nav_pipeline"], .sidebar-recruiter a[href*="/pipeline"]');
if (_pipelineNav) _pipelineNav.classList.add('active-item');

initPipelineSecureHandlers();

window.addEventListener('load', () => {
    initPipeline();
    setupColumns();
    // Initialize v5.0 enhancements
    if (window.Enhancements) {
        window.Enhancements.init();
    }
});
