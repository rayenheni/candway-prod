/**
 * Recruiter Platform Enhancements v5.0
 * ======================================
 * Features: One-click actions, hover previews, undo system,
 * custom stages, keyboard navigation, mobile Kanban,
 * tagged notes, scorecards, automation rules
 */

// ============================================================================
// STATE
// ============================================================================
let undoStack = [];
let hoverPreviewTimeout = null;
let currentHoverCard = null;
let customStages = [];
let isMobileView = false;

// ============================================================================
// INITIALIZATION
// ============================================================================
async function initEnhancements() {
    detectMobileView();
    await loadCustomStages();
    await loadPendingUndos();
    setupHoverPreviews();
    setupKeyboardShortcuts();
    setupMobileKanban();
    setupUndoNotifications();
    window.addEventListener('resize', detectMobileView);
}

function detectMobileView() {
    isMobileView = window.innerWidth < 768;
    document.body.classList.toggle('mobile-kanban', isMobileView);
}

// ============================================================================
// ONE-CLICK ACTIONS
// ============================================================================
async function quickAction(appId, action) {
    const btn = document.querySelector(`[data-quick-action="${action}"][data-app-id="${appId}"]`);
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    }

    try {
        const result = await window.fetchAPI('/recruiter/enhancements/quick-action', {
            method: 'POST',
            body: JSON.stringify({ app_id: appId, action })
        });

        if (result.success) {
            // Update local state
            const app = allApps?.find(a => a.id == appId);
            if (app) {
                const oldStatus = app.status;
                app.status = result.new_status;
                renderPipeline?.();
                updateStats?.();

                // Broadcast to other tabs/pages
                if (window.StageSync) {
                    window.StageSync.broadcast({ appId, oldStatus, newStatus: result.new_status });
                }
            }

            // Show undo notification
            showUndoNotification(result.undo_id, action, 10);

            showToast(`Candidate ${action}ed successfully`, 'success');
        }
    } catch (e) {
        console.error('Quick action failed:', e);
        showToast(`Failed to ${action} candidate`, 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            resetQuickActionBtn(btn, action);
        }
    }
}

function resetQuickActionBtn(btn, action) {
    const icons = {
        invite: 'fa-envelope',
        shortlist: 'fa-star',
        reject: 'fa-times',
        archive: 'fa-archive'
    };
    XSS.safeSetHTML(btn, `<i class="fas ${icons[action] || 'fa-circle'}"></i>`);
}

function addQuickActionButtons(card, app) {
    const actionsDiv = card.querySelector('.quick-actions') || document.createElement('div');
    actionsDiv.className = 'quick-actions flex gap-1 mt-2 pt-2 border-t border-slate-100/50';
    actionsDiv.innerHTML = `
        <button data-quick-action="invite" data-app-id="${app.id}"
            onclick="quickAction(${app.id}, 'invite')"
            class="flex-1 py-1 px-2 rounded-lg text-[9px] font-bold uppercase tracking-wider bg-sky-50 text-sky-600 hover:bg-sky-600 hover:text-white transition"
            title="Send Interview Invite">
            <i class="fas fa-envelope"></i> Invite
        </button>
        <button data-quick-action="shortlist" data-app-id="${app.id}"
            onclick="quickAction(${app.id}, 'shortlist')"
            class="flex-1 py-1 px-2 rounded-lg text-[9px] font-bold uppercase tracking-wider bg-indigo-50 text-indigo-600 hover:bg-indigo-600 hover:text-white transition"
            title="Move to Interviewing">
            <i class="fas fa-star"></i> Shortlist
        </button>
        <button data-quick-action="reject" data-app-id="${app.id}"
            onclick="quickAction(${app.id}, 'reject')"
            class="flex-1 py-1 px-2 rounded-lg text-[9px] font-bold uppercase tracking-wider bg-red-50 text-red-600 hover:bg-red-600 hover:text-white transition"
            title="Reject Candidate">
            <i class="fas fa-times"></i> Reject
        </button>
    `;

    // Insert before the existing footer
    const footer = card.querySelector('.flex.items-center.justify-between.pt-3');
    if (footer) {
        card.insertBefore(actionsDiv, footer);
    } else {
        card.appendChild(actionsDiv);
    }
}

// ============================================================================
// HOVER PREVIEWS
// ============================================================================
function setupHoverPreviews() {
    document.addEventListener('mouseover', function(e) {
        const card = e.target.closest('.candidate-card');
        if (!card) return;

        const appId = card.dataset.id;
        if (!appId) return;

        clearTimeout(hoverPreviewTimeout);
        hoverPreviewTimeout = setTimeout(() => showHoverPreview(appId, card), 500);
    });

    document.addEventListener('mouseout', function(e) {
        const card = e.target.closest('.candidate-card');
        if (!card) return;

        clearTimeout(hoverPreviewTimeout);
        hideHoverPreview();
    });
}

async function showHoverPreview(appId, card) {
    if (currentHoverCard) return;

    try {
        const data = await window.fetchAPI(`/recruiter/enhancements/hover-preview/${appId}`);

        const preview = document.createElement('div');
        preview.id = 'hover-preview';
        preview.className = 'fixed z-50 bg-white rounded-2xl shadow-2xl border border-slate-200 p-5 w-80 max-h-96 overflow-y-auto pointer-events-none';
        preview.style.pointerEvents = 'none';

        const _sc = data.score_entity?.final_score ?? data.overall_score;
        const _ivHover = data.interview_entity || {};
        const scoreColor = _sc >= 85 ? 'text-purple-600' : _sc >= 70 ? 'text-indigo-600' : 'text-amber-600';
        const trustColor = data.trust_score >= 80 ? 'text-indigo-600' : data.trust_score >= 60 ? 'text-amber-600' : 'text-red-600';

        preview.innerHTML = `
            <div class="flex items-start gap-3 mb-4">
                <div class="w-10 h-10 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 font-bold text-lg">
                    ${data.candidate_name.charAt(0)}
                </div>
                <div class="flex-1 min-w-0">
                    <h4 class="font-bold text-slate-900 truncate">${Components.safeHTML(data.candidate_name)}</h4>
                    <p class="text-xs text-slate-500">${Components.safeHTML(data.role)}</p>
                </div>
            </div>

            <div class="grid grid-cols-3 gap-2 mb-4">
                <div class="bg-slate-50 rounded-xl p-2 text-center">
                    <div class="text-lg font-black ${scoreColor}">${Math.round(_sc)}</div>
                    <div class="text-[9px] font-bold text-slate-400 uppercase">Score</div>
                </div>
                <div class="bg-slate-50 rounded-xl p-2 text-center">
                    <div class="text-lg font-black ${trustColor}">${Math.round(data.trust_score)}</div>
                    <div class="text-[9px] font-bold text-slate-400 uppercase">Trust</div>
                </div>
                <div class="bg-slate-50 rounded-xl p-2 text-center">
                    <div class="text-lg font-black text-indigo-600">${_ivHover.interview_progress ?? data.interview_progress}/${data.total_questions}</div>
                    <div class="text-[9px] font-bold text-slate-400 uppercase">Interview</div>
                </div>
            </div>

            ${data.skills.length > 0 ? `
            <div class="mb-3">
                <div class="text-[9px] font-bold text-slate-400 uppercase tracking-widest mb-1.5">Skills</div>
                <div class="flex flex-wrap gap-1">
                    ${data.skills.slice(0, 6).map(s => `<span class="px-2 py-0.5 bg-indigo-50 text-indigo-600 rounded text-[10px] font-bold">${Components.safeHTML(s)}</span>`).join('')}
                </div>
            </div>` : ''}

            ${data.strengths.length > 0 ? `
            <div class="mb-3">
                <div class="text-[9px] font-bold text-indigo-400 uppercase tracking-widest mb-1.5">Strengths</div>
                <div class="flex flex-wrap gap-1">
                    ${data.strengths.slice(0, 3).map(s => `<span class="px-2 py-0.5 bg-indigo-50 text-indigo-600 rounded text-[10px] font-bold">${Components.safeHTML(s)}</span>`).join('')}
                </div>
            </div>` : ''}

            <div class="text-xs text-slate-600 leading-relaxed line-clamp-3 mb-3">${Components.safeHTML(data.summary)}</div>

            <div class="flex items-center justify-between text-[10px] text-slate-400 pt-2 border-t border-slate-100">
                <span>${data.status}</span>
                <span class="flex items-center gap-2">
                    ${data.notes_count > 0 ? `<span><i class="fas fa-sticky-note"></i> ${data.notes_count}</span>` : ''}
                    ${data.comments_count > 0 ? `<span><i class="fas fa-comment"></i> ${data.comments_count}</span>` : ''}
                </span>
            </div>
        `;

        // Position preview
        const rect = card.getBoundingClientRect();
        let left = rect.right + 10;
        let top = rect.top;

        // Adjust if off-screen
        if (left + 320 > window.innerWidth) {
            left = rect.left - 330;
        }
        if (top + 384 > window.innerHeight) {
            top = window.innerHeight - 394;
        }
        if (top < 10) top = 10;

        preview.style.left = left + 'px';
        preview.style.top = top + 'px';

        document.body.appendChild(preview);
        currentHoverCard = preview;
    } catch (e) {
        console.warn('Hover preview failed:', e);
    }
}

function hideHoverPreview() {
    if (currentHoverCard) {
        currentHoverCard.remove();
        currentHoverCard = null;
    }
}

// ============================================================================
// UNDO SYSTEM
// ============================================================================
function showUndoNotification(undoId, action, seconds) {
    const notif = document.createElement('div');
    notif.id = 'undo-notification';
    notif.className = 'fixed bottom-6 left-1/2 -translate-x-1/2 z-50 bg-slate-900 text-white px-6 py-3 rounded-xl shadow-2xl flex items-center gap-4 animate-slide-up';
    notif.innerHTML = `
        <span class="text-sm font-medium">Undid ${action}</span>
        <button onclick="executeUndo(${undoId})" class="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-700 rounded-lg text-sm font-bold transition">
            Undo
        </button>
        <span class="text-slate-400 text-sm" id="undo-countdown">${seconds}s</span>
    `;

    document.body.appendChild(notif);

    // Countdown
    let remaining = seconds;
    const countdown = setInterval(() => {
        remaining--;
        const el = document.getElementById('undo-countdown');
        if (el) el.textContent = remaining + 's';
        if (remaining <= 0) {
            clearInterval(countdown);
            notif.remove();
        }
    }, 1000);

    // Auto-remove after timeout
    setTimeout(() => {
        if (notif.parentNode) notif.remove();
    }, seconds * 1000);
}

async function executeUndo(undoId) {
    try {
        const result = await window.fetchAPI(`/recruiter/enhancements/undo/${undoId}`, {
            method: 'POST'
        });

        if (result.success) {
            showToast('Action undone successfully', 'success');
            const notif = document.getElementById('undo-notification');
            if (notif) notif.remove();

            // Reload pipeline
            if (typeof loadApplications === 'function') {
                loadApplications(1, false);
            }
        }
    } catch (e) {
        console.error('Undo failed:', e);
        showToast(e.message || 'Undo failed', 'error');
    }
}

async function loadPendingUndos() {
    try {
        const undos = await window.fetchAPI('/recruiter/enhancements/undo/pending');
        if (undos && undos.length > 0) {
            // Show most recent undo
            const latest = undos[0];
            showUndoNotification(latest.undo_id, latest.action_type, Math.round(latest.expires_in_seconds));
        }
    } catch (e) {
        console.warn('Failed to load pending undos:', e);
    }
}

function setupUndoNotifications() {
    // Poll for pending undos every 5 seconds
    setInterval(loadPendingUndos, 5000);
}

// ============================================================================
// CUSTOM PIPELINE STAGES
// ============================================================================
async function loadCustomStages() {
    try {
        const stages = await window.fetchAPI('/recruiter/enhancements/stages');
        if (stages && stages.length > 0) {
            customStages = stages;
            renderCustomKanbanColumns();
        }
    } catch (e) {
        console.warn('Failed to load custom stages:', e);
    }
}

function renderCustomKanbanColumns() {
    const board = document.getElementById('kanban-board');
    if (!board || customStages.length === 0) return;

    // Clear existing columns
    board.innerHTML = '';

    customStages.forEach(stage => {
        const col = document.createElement('div');
        col.className = 'kanban-col flex-1 min-w-[280px] max-w-[320px] bg-slate-50/50 rounded-2xl p-3';
        col.dataset.status = stage.slug;

        col.innerHTML = `
            <div class="flex items-center justify-between mb-4 px-1">
                <div class="flex items-center gap-2">
                    <div class="w-2.5 h-2.5 rounded-full" style="background-color: ${stage.color}"></div>
                    <h3 class="font-bold text-slate-700 text-sm">${Components.safeHTML(stage.name)}</h3>
                </div>
                <span class="text-xs font-black text-slate-400 bg-white px-2 py-0.5 rounded-full" id="count-${stage.slug}">0</span>
            </div>
            <div class="min-h-[200px] space-y-3" id="col-${stage.slug}"></div>
        `;

        // DnD setup
        col.addEventListener('dragover', e => {
            e.preventDefault();
            col.classList.add('drag-over');
        });
        col.addEventListener('dragleave', () => col.classList.remove('drag-over'));
        col.addEventListener('drop', async (e) => {
            e.preventDefault();
            col.classList.remove('drag-over');
            const appId = window.draggedId;
            const newStatus = stage.slug;

                    if (appId && newStatus) {
                        try {
                            const app = allApps?.find(a => a.id == appId);
                            const oldStatus = app ? app.status : null;

                            await window.fetchAPI('/recruiter/enhancements/stage-transition', {
                                method: 'POST',
                                body: JSON.stringify({ app_id: appId, new_stage: newStatus })
                            });

                            if (app) {
                                app.status = newStatus;
                                renderPipeline?.();
                                updateStats?.();

                                // Broadcast to other tabs/pages
                                if (window.StageSync) {
                                    window.StageSync.broadcast({ appId, oldStatus, newStatus });
                                }
                            }
                            showToast('Candidate moved', 'success');
                        } catch (err) {
                            showToast('Failed to move candidate', 'error');
                        }
                    }
        });

        board.appendChild(col);
    });
}

async function openStageManager() {
    const modal = document.getElementById('stage-manager-modal');
    if (!modal) {
        // Create modal dynamically
        const modalHtml = `
            <div id="stage-manager-modal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 hidden">
                <div class="bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 max-h-[80vh] overflow-hidden">
                    <div class="flex items-center justify-between p-5 border-b border-slate-100">
                        <h3 class="text-lg font-bold text-slate-900">Manage Pipeline Stages</h3>
                        <button onclick="closeStageManager()" class="w-8 h-8 rounded-lg hover:bg-slate-100 flex items-center justify-center">
                            <i class="fas fa-times text-slate-400"></i>
                        </button>
                    </div>
                    <div class="p-5 overflow-y-auto max-h-[60vh]" id="stage-manager-list"></div>
                    <div class="p-5 border-t border-slate-100">
                        <button onclick="addNewStage()" class="w-full py-2.5 bg-indigo-600 text-white rounded-xl font-bold hover:bg-indigo-700 transition">
                            <i class="fas fa-plus mr-2"></i> Add Stage
                        </button>
                    </div>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', modalHtml);
    }

    modal.classList.remove('hidden');
    renderStageManagerList();
}

function closeStageManager() {
    const modal = document.getElementById('stage-manager-modal');
    if (modal) modal.classList.add('hidden');
}

async function renderStageManagerList() {
    const list = document.getElementById('stage-manager-list');
    if (!list) return;

    try {
        const stages = await window.fetchAPI('/recruiter/enhancements/stages');
        list.innerHTML = stages.map(s => `
            <div class="flex items-center justify-between p-3 bg-slate-50 rounded-xl mb-2">
                <div class="flex items-center gap-3">
                    <div class="w-4 h-4 rounded-full" style="background-color: ${s.color}"></div>
                    <div>
                        <div class="font-bold text-sm text-slate-900">${Components.safeHTML(s.name)}</div>
                        <div class="text-[10px] text-slate-400 font-mono">${s.slug}</div>
                    </div>
                </div>
                ${!s.is_default ? `
                <button onclick="deleteStage(${s.id})" class="text-red-400 hover:text-red-600 text-xs">
                    <i class="fas fa-trash"></i>
                </button>` : '<span class="text-[9px] text-slate-400 font-bold uppercase">Default</span>'}
            </div>
        `).join('');
    } catch (e) {
        list.innerHTML = '<p class="text-red-500 text-sm">Failed to load stages</p>';
    }
}

async function addNewStage() {
    const name = prompt('Stage name:');
    if (!name) return;

    const slug = name.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '');
    const color = '#' + Math.floor(Math.random()*16777215).toString(16).padStart(6, '0');

    try {
        await window.fetchAPI('/recruiter/enhancements/stages', {
            method: 'POST',
            body: JSON.stringify({ name, slug, color })
        });

        await loadCustomStages();
        renderStageManagerList();
        showToast('Stage added', 'success');
    } catch (e) {
        showToast(e.message || 'Failed to add stage', 'error');
    }
}

async function deleteStage(stageId) {
    if (!confirm('Delete this stage? Candidates in this stage will move to Applied.')) return;

    try {
        await window.fetchAPI(`/recruiter/enhancements/stages/${stageId}`, {
            method: 'DELETE'
        });

        await loadCustomStages();
        renderStageManagerList();
        showToast('Stage deleted', 'success');
    } catch (e) {
        showToast('Failed to delete stage', 'error');
    }
}

// ============================================================================
// KEYBOARD NAVIGATION
// ============================================================================
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', function(e) {
        // Ignore if typing in input
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable) return;

        const key = e.key.toLowerCase();

        // 'j' / 'k' — navigate cards (like Gmail)
        if (key === 'j' || key === 'k') {
            e.preventDefault();
            navigateCards(key === 'j' ? 1 : -1);
        }

        // 'Enter' — open selected card
        if (key === 'enter') {
            e.preventDefault();
            openSelectedCard();
        }

        // 'i' — invite selected
        if (key === 'i') {
            e.preventDefault();
            quickActionOnSelected('invite');
        }

        // 's' — shortlist selected
        if (key === 's') {
            e.preventDefault();
            quickActionOnSelected('shortlist');
        }

        // 'r' — reject selected
        if (key === 'r') {
            e.preventDefault();
            quickActionOnSelected('reject');
        }

        // 'u' — undo last action
        if (key === 'u' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            undoLastAction();
        }

        // 'm' — toggle mobile view
        if (key === 'm') {
            e.preventDefault();
            toggleMobileView();
        }

        // '?' — show keyboard shortcuts help
        if (key === '?') {
            e.preventDefault();
            showKeyboardHelp();
        }
    });
}

let selectedCardIndex = -1;

function navigateCards(direction) {
    const cards = document.querySelectorAll('.candidate-card');
    if (cards.length === 0) return;

    // Remove previous selection
    if (selectedCardIndex >= 0 && selectedCardIndex < cards.length) {
        cards[selectedCardIndex].classList.remove('ring-2', 'ring-indigo-500');
    }

    selectedCardIndex += direction;
    if (selectedCardIndex < 0) selectedCardIndex = cards.length - 1;
    if (selectedCardIndex >= cards.length) selectedCardIndex = 0;

    // Highlight new selection
    cards[selectedCardIndex].classList.add('ring-2', 'ring-indigo-500');
    cards[selectedCardIndex].scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function openSelectedCard() {
    const cards = document.querySelectorAll('.candidate-card');
    if (selectedCardIndex < 0 || selectedCardIndex >= cards.length) return;

    const appId = cards[selectedCardIndex].dataset.id;
    if (appId && typeof viewProfile === 'function') {
        viewProfile(parseInt(appId));
    }
}

function quickActionOnSelected(action) {
    const cards = document.querySelectorAll('.candidate-card');
    if (selectedCardIndex < 0 || selectedCardIndex >= cards.length) return;

    const appId = cards[selectedCardIndex].dataset.id;
    if (appId) {
        quickAction(parseInt(appId), action);
    }
}

function undoLastAction() {
    const undos = undoStack.filter(u => !u.executed);
    if (undos.length > 0) {
        executeUndo(undos[undos.length - 1].id);
    }
}

function toggleMobileView() {
    isMobileView = !isMobileView;
    document.body.classList.toggle('mobile-kanban', isMobileView);
    showToast(isMobileView ? 'Mobile view enabled' : 'Desktop view enabled', 'info');
}

function showKeyboardHelp() {
    const help = document.createElement('div');
    help.id = 'keyboard-help';
    help.className = 'fixed inset-0 z-50 flex items-center justify-center bg-black/50';
    help.innerHTML = `
        <div class="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 p-6">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-lg font-bold text-slate-900">Keyboard Shortcuts</h3>
                <button onclick="document.getElementById('keyboard-help')?.remove()" class="w-8 h-8 rounded-lg hover:bg-slate-100 flex items-center justify-center">
                    <i class="fas fa-times text-slate-400"></i>
                </button>
            </div>
            <div class="space-y-2 text-sm">
                <div class="flex justify-between py-2 border-b border-slate-100">
                    <span class="text-slate-600">Navigate cards</span>
                    <span class="font-mono bg-slate-100 px-2 py-0.5 rounded text-xs">J / K</span>
                </div>
                <div class="flex justify-between py-2 border-b border-slate-100">
                    <span class="text-slate-600">Open selected</span>
                    <span class="font-mono bg-slate-100 px-2 py-0.5 rounded text-xs">Enter</span>
                </div>
                <div class="flex justify-between py-2 border-b border-slate-100">
                    <span class="text-slate-600">Invite</span>
                    <span class="font-mono bg-slate-100 px-2 py-0.5 rounded text-xs">I</span>
                </div>
                <div class="flex justify-between py-2 border-b border-slate-100">
                    <span class="text-slate-600">Shortlist</span>
                    <span class="font-mono bg-slate-100 px-2 py-0.5 rounded text-xs">S</span>
                </div>
                <div class="flex justify-between py-2 border-b border-slate-100">
                    <span class="text-slate-600">Reject</span>
                    <span class="font-mono bg-slate-100 px-2 py-0.5 rounded text-xs">R</span>
                </div>
                <div class="flex justify-between py-2 border-b border-slate-100">
                    <span class="text-slate-600">Undo</span>
                    <span class="font-mono bg-slate-100 px-2 py-0.5 rounded text-xs">Ctrl+U</span>
                </div>
                <div class="flex justify-between py-2 border-b border-slate-100">
                    <span class="text-slate-600">Toggle mobile</span>
                    <span class="font-mono bg-slate-100 px-2 py-0.5 rounded text-xs">M</span>
                </div>
                <div class="flex justify-between py-2">
                    <span class="text-slate-600">This help</span>
                    <span class="font-mono bg-slate-100 px-2 py-0.5 rounded text-xs">?</span>
                </div>
            </div>
        </div>
    `;
    help.addEventListener('click', (e) => {
        if (e.target === help) help.remove();
    });
    document.body.appendChild(help);
}

// ============================================================================
// MOBILE KANBAN
// ============================================================================
function setupMobileKanban() {
    // Add mobile-specific styles
    const style = document.createElement('style');
    style.textContent = `
        .mobile-kanban #kanban-board {
            display: flex;
            overflow-x: auto;
            scroll-snap-type: x mandatory;
            -webkit-overflow-scrolling: touch;
            gap: 0;
            padding-bottom: 1rem;
        }
        .mobile-kanban .kanban-col {
            min-width: 85vw;
            max-width: 85vw;
            scroll-snap-align: start;
            margin-right: 0.5rem;
        }
        .mobile-kanban .candidate-card {
            padding: 0.75rem;
        }
        .mobile-kanban .quick-actions {
            flex-wrap: wrap;
        }
        .mobile-kanban .quick-actions button {
            flex: 1 1 calc(50% - 0.25rem);
            min-width: 0;
        }
        #hover-preview {
            display: none !important;
        }
        @keyframes slide-up {
            from { transform: translate(-50%, 100%); opacity: 0; }
            to { transform: translate(-50%, 0); opacity: 1; }
        }
        .animate-slide-up {
            animation: slide-up 0.3s ease-out;
        }
        @media (max-width: 768px) {
            .kanban-board-wrapper {
                overflow-x: auto;
                -webkit-overflow-scrolling: touch;
            }
        }
    `;
    document.head.appendChild(style);

    // Add mobile stage navigation dots
    if (isMobileView) {
        addMobileStageNav();
    }
}

function addMobileStageNav() {
    if (document.getElementById('mobile-stage-nav')) return;

    const nav = document.createElement('div');
    nav.id = 'mobile-stage-nav';
    nav.className = 'flex gap-2 overflow-x-auto pb-2 px-4 -mx-4';

    const stages = customStages.length > 0 ? customStages : [
        { slug: 'applied', name: 'Applied' },
        { slug: 'invited', name: 'Invited' },
        { slug: 'interviewing', name: 'Interviewing' },
        { slug: 'offer', name: 'Offer' },
        { slug: 'hired', name: 'Hired' },
        { slug: 'rejected', name: 'Rejected' }
    ];

    stages.forEach(s => {
        const btn = document.createElement('button');
        btn.className = 'px-3 py-1.5 bg-white border border-slate-200 rounded-full text-xs font-bold text-slate-600 whitespace-nowrap hover:bg-indigo-50 hover:border-indigo-200 hover:text-indigo-600 transition';
        btn.textContent = s.name;
        btn.onclick = () => {
            const col = document.querySelector(`[data-status="${s.slug}"]`);
            if (col) col.scrollIntoView({ behavior: 'smooth', inline: 'start' });
        };
        nav.appendChild(btn);
    });

    const board = document.getElementById('kanban-board');
    if (board) {
        board.parentElement.insertBefore(nav, board);
    }
}

// ============================================================================
// AUTOMATION RULES UI
// ============================================================================
async function loadAutomationRules() {
    try {
        const rules = await window.fetchAPI('/recruiter/enhancements/automation-rules');
        const container = document.getElementById('automation-rules-list');
        if (!container) return;

        if (rules.length === 0) {
            container.innerHTML = `
                <div class="text-center py-8">
                    <i class="fas fa-robot text-4xl text-slate-300 mb-3"></i>
                    <p class="text-slate-500 text-sm">No automation rules yet</p>
                    <button onclick="createAutomationRule()" class="mt-3 px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-bold hover:bg-indigo-700">
                        Create First Rule
                    </button>
                </div>
            `;
            return;
        }

        container.innerHTML = rules.map(r => `
            <div class="flex items-center justify-between p-4 bg-slate-50 rounded-xl mb-2">
                <div class="flex items-center gap-3">
                    <div class="w-8 h-8 rounded-lg ${r.is_active ? 'bg-indigo-100 text-indigo-600' : 'bg-slate-200 text-slate-400'} flex items-center justify-center">
                        <i class="fas fa-bolt"></i>
                    </div>
                    <div>
                        <div class="font-bold text-sm text-slate-900">${Components.safeHTML(r.name)}</div>
                        <div class="text-[10px] text-slate-400">Triggered ${r.execution_count} times</div>
                    </div>
                </div>
                <div class="flex items-center gap-2">
                    <label class="relative inline-flex items-center cursor-pointer">
                        <input type="checkbox" class="sr-only peer" ${r.is_active ? 'checked' : ''}
                            onchange="toggleAutomationRule(${r.id}, this.checked)">
                        <div class="w-9 h-5 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-indigo-600"></div>
                    </label>
                    <button onclick="deleteAutomationRule(${r.id})" class="text-red-400 hover:text-red-600 text-xs">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `).join('');
    } catch (e) {
        console.warn('Failed to load automation rules:', e);
    }
}

async function createAutomationRule() {
    const presets = [
        {
            name: 'Auto-shortlist high scorers',
            trigger_json: { type: 'score_threshold', field: 'overall_score', operator: '>=', value: 80 },
            action_json: { type: 'move_stage', target_stage: 'interviewing' }
        },
        {
            name: 'Auto-reject low scorers',
            trigger_json: { type: 'score_threshold', field: 'overall_score', operator: '<', value: 30 },
            action_json: { type: 'move_stage', target_stage: 'rejected' }
        },
        {
            name: 'Remind inactive candidates',
            trigger_json: { type: 'no_activity_days', days: 7 },
            action_json: { type: 'send_reminder' }
        }
    ];

    const choice = prompt(
        'Choose a preset:\n1. Auto-shortlist high scorers (≥80)\n2. Auto-reject low scorers (<30)\n3. Remind inactive (7 days)\n\nEnter 1, 2, or 3:'
    );

    if (!choice || !['1', '2', '3'].includes(choice)) return;

    const preset = presets[parseInt(choice) - 1];

    try {
        await window.fetchAPI('/recruiter/enhancements/automation-rules', {
            method: 'POST',
            body: JSON.stringify(preset)
        });

        loadAutomationRules();
        showToast('Automation rule created', 'success');
    } catch (e) {
        showToast('Failed to create rule', 'error');
    }
}

async function toggleAutomationRule(ruleId, isActive) {
    try {
        await window.fetchAPI(`/recruiter/enhancements/automation-rules/${ruleId}`, {
            method: 'PATCH',
            body: JSON.stringify({ is_active: isActive })
        });
        showToast(`Rule ${isActive ? 'enabled' : 'disabled'}`, 'success');
    } catch (e) {
        showToast('Failed to update rule', 'error');
    }
}

async function deleteAutomationRule(ruleId) {
    if (!confirm('Delete this automation rule?')) return;

    try {
        await window.fetchAPI(`/recruiter/enhancements/automation-rules/${ruleId}`, {
            method: 'DELETE'
        });

        loadAutomationRules();
        showToast('Rule deleted', 'success');
    } catch (e) {
        showToast('Failed to delete rule', 'error');
    }
}

// ============================================================================
// TAGGED NOTES UI
// ============================================================================
async function loadTaggedNotes(appId) {
    try {
        const notes = await window.fetchAPI(`/recruiter/enhancements/notes/${appId}`);
        const container = document.getElementById('tagged-notes-container');
        if (!container) return;

        if (notes.length === 0) {
            container.innerHTML = '<p class="text-slate-400 text-sm text-center py-4">No notes yet. Add one below.</p>';
            return;
        }

        const priorityColors = {
            low: 'bg-slate-100 text-slate-600',
            normal: 'bg-blue-50 text-blue-600',
            high: 'bg-amber-50 text-amber-600',
            urgent: 'bg-red-50 text-red-600'
        };

        container.innerHTML = notes.map(n => `
            <div class="p-3 bg-slate-50 rounded-xl mb-2 ${n.is_pinned ? 'border-2 border-indigo-200' : ''} ${n.is_resolved ? 'opacity-50' : ''}">
                <div class="flex items-start justify-between mb-2">
                    <div class="flex items-center gap-2">
                        <span class="px-2 py-0.5 rounded text-[9px] font-bold uppercase ${priorityColors[n.priority] || priorityColors.normal}">
                            ${n.priority}
                        </span>
                        ${n.is_pinned ? '<i class="fas fa-thumbtack text-indigo-400 text-[10px]"></i>' : ''}
                        ${n.is_resolved ? '<span class="text-[9px] text-indigo-600 font-bold">RESOLVED</span>' : ''}
                    </div>
                    <div class="flex items-center gap-1">
                        <button onclick="toggleNotePin(${n.id})" class="text-slate-400 hover:text-indigo-600 text-xs" title="${n.is_pinned ? 'Unpin' : 'Pin'}">
                            <i class="fas fa-thumbtack"></i>
                        </button>
                        <button onclick="resolveNote(${n.id})" class="text-slate-400 hover:text-indigo-600 text-xs" title="Resolve">
                            <i class="fas fa-check"></i>
                        </button>
                        <button onclick="deleteNote(${n.id})" class="text-slate-400 hover:text-red-600 text-xs" title="Delete">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
                <p class="text-sm text-slate-700 mb-2">${Components.safeHTML(n.content)}</p>
                ${n.tags?.length > 0 ? `
                <div class="flex flex-wrap gap-1">
                    ${n.tags.map(t => `<span class="px-1.5 py-0.5 bg-indigo-50 text-indigo-600 rounded text-[9px] font-bold">#${Components.safeHTML(t)}</span>`).join('')}
                </div>` : ''}
                <div class="text-[9px] text-slate-400 mt-2">${n.author_name} · ${new Date(n.created_at).toLocaleDateString()}</div>
            </div>
        `).join('');
    } catch (e) {
        console.warn('Failed to load notes:', e);
    }
}

async function addTaggedNote(appId, content, tags, priority) {
    if (!content.trim()) return;

    try {
        await window.fetchAPI('/recruiter/enhancements/notes', {
            method: 'POST',
            body: JSON.stringify({
                application_id: appId,
                content,
                tags: tags || [],
                priority: priority || 'normal'
            })
        });

        loadTaggedNotes(appId);
        showToast('Note added', 'success');
    } catch (e) {
        showToast('Failed to add note', 'error');
    }
}

async function toggleNotePin(noteId) {
    try {
        const note = window._currentNotes?.find(n => n.id === noteId);
        if (!note) return;

        await window.fetchAPI(`/recruiter/enhancements/notes/${noteId}`, {
            method: 'PATCH',
            body: JSON.stringify({ is_pinned: !note.is_pinned })
        });

        loadTaggedNotes(note.application_id);
    } catch (e) {
        showToast('Failed to update note', 'error');
    }
}

async function resolveNote(noteId) {
    try {
        const note = window._currentNotes?.find(n => n.id === noteId);
        if (!note) return;

        await window.fetchAPI(`/recruiter/enhancements/notes/${noteId}`, {
            method: 'PATCH',
            body: JSON.stringify({ is_resolved: !note.is_resolved })
        });

        loadTaggedNotes(note.application_id);
    } catch (e) {
        showToast('Failed to update note', 'error');
    }
}

async function deleteNote(noteId) {
    if (!confirm('Delete this note?')) return;

    try {
        await window.fetchAPI(`/recruiter/enhancements/notes/${noteId}`, {
            method: 'DELETE'
        });

        // Reload notes
        const container = document.getElementById('tagged-notes-container');
        if (container) {
            const appId = container.dataset.appId;
            if (appId) loadTaggedNotes(parseInt(appId));
        }
        showToast('Note deleted', 'success');
    } catch (e) {
        showToast('Failed to delete note', 'error');
    }
}

// ============================================================================
// INTERVIEW SCORECARDS UI
// ============================================================================
async function loadScorecards(roleType) {
    try {
        const url = roleType ? `/recruiter/enhancements/scorecards?role_type=${roleType}` : '/recruiter/enhancements/scorecards';
        const scorecards = await window.fetchAPI(url);

        const container = document.getElementById('scorecards-container');
        if (!container) return;

        if (scorecards.length === 0) {
            container.innerHTML = '<p class="text-slate-400 text-sm text-center py-4">No scorecards available</p>';
            return;
        }

        container.innerHTML = scorecards.map(s => `
            <div class="p-4 bg-slate-50 rounded-xl mb-2 cursor-pointer hover:bg-indigo-50 transition" onclick="openScorecard(${s.id})">
                <div class="flex items-center justify-between">
                    <div>
                        <div class="font-bold text-sm text-slate-900">${Components.safeHTML(s.name)}</div>
                        <div class="text-[10px] text-slate-400">${Components.safeHTML(s.role_type)} · ${s.criteria.length} criteria</div>
                    </div>
                    ${s.is_system ? '<span class="px-2 py-0.5 bg-indigo-100 text-indigo-600 rounded text-[9px] font-bold">SYSTEM</span>' : ''}
                </div>
            </div>
        `).join('');
    } catch (e) {
        console.warn('Failed to load scorecards:', e);
    }
}

function openScorecard(scorecardId) {
    // Open scorecard submission modal
    window.location.href = `/recruiter/scorecard/${scorecardId}`;
}

async function submitScorecard(data) {
    try {
        const result = await window.fetchAPI('/recruiter/enhancements/scorecards/submit', {
            method: 'POST',
            body: JSON.stringify(data)
        });

        if (result.success) {
            showToast(`Scorecard submitted — Overall: ${result.score_entity?.final_score ?? result.overall_score}%`, 'success');
            return result;
        }
    } catch (e) {
        showToast('Failed to submit scorecard', 'error');
    }
}

// ============================================================================
// WEBHOOK INTEGRATIONS UI
// ============================================================================
async function loadWebhooks() {
    try {
        const webhooks = await window.fetchAPI('/recruiter/enhancements/webhooks');
        const container = document.getElementById('webhooks-container');
        if (!container) return;

        if (webhooks.length === 0) {
            container.innerHTML = `
                <div class="text-center py-8">
                    <i class="fas fa-plug text-4xl text-slate-300 mb-3"></i>
                    <p class="text-slate-500 text-sm">No integrations connected</p>
                </div>
            `;
            return;
        }

        const providerIcons = {
            slack: 'fa-slack',
            teams: 'fa-microsoft',
            discord: 'fa-discord',
            custom: 'fa-link'
        };

        container.innerHTML = webhooks.map(w => `
            <div class="flex items-center justify-between p-4 bg-slate-50 rounded-xl mb-2">
                <div class="flex items-center gap-3">
                    <div class="w-8 h-8 rounded-lg bg-indigo-100 text-indigo-600 flex items-center justify-center">
                        <i class="fab ${providerIcons[w.provider] || 'fa-link'}"></i>
                    </div>
                    <div>
                        <div class="font-bold text-sm text-slate-900">${Components.safeHTML(w.name)}</div>
                        <div class="text-[10px] text-slate-400">${w.provider} · ${w.events.length} events</div>
                    </div>
                </div>
                <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" class="sr-only peer" ${w.is_active ? 'checked' : ''}
                        onchange="toggleWebhook(${w.id}, this.checked)">
                    <div class="w-9 h-5 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-indigo-600"></div>
                </label>
            </div>
        `).join('');
    } catch (e) {
        console.warn('Failed to load webhooks:', e);
    }
}

async function toggleWebhook(webhookId, isActive) {
    try {
        await window.fetchAPI(`/recruiter/enhancements/webhooks/${webhookId}`, {
            method: 'PATCH',
            body: JSON.stringify({ is_active: isActive })
        });
        showToast(`Webhook ${isActive ? 'enabled' : 'disabled'}`, 'success');
    } catch (e) {
        showToast('Failed to update webhook', 'error');
    }
}

// ============================================================================
// ANALYTICS UI
// ============================================================================
async function loadTimeInStageAnalytics(days = 30) {
    try {
        const data = await window.fetchAPI(`/recruiter/enhancements/analytics/time-in-stage?days=${days}`);
        const container = document.getElementById('time-in-stage-chart');
        if (!container) return;

        if (Object.keys(data.stages).length === 0) {
            container.innerHTML = '<p class="text-slate-400 text-sm text-center py-4">No stage data yet</p>';
            return;
        }

        container.innerHTML = Object.entries(data.stages).map(([slug, stats]) => `
            <div class="flex items-center justify-between p-3 bg-slate-50 rounded-xl mb-2">
                <div class="font-bold text-sm text-slate-900 capitalize">${slug.replace('_', ' ')}</div>
                <div class="text-right">
                    <div class="font-black text-indigo-600">${stats.avg_duration_hours}h avg</div>
                    <div class="text-[9px] text-slate-400">${stats.sample_size} transitions</div>
                </div>
            </div>
        `).join('');
    } catch (e) {
        console.warn('Failed to load time-in-stage analytics:', e);
    }
}

async function loadSourceAttribution(days = 90) {
    try {
        const data = await window.fetchAPI(`/recruiter/enhancements/analytics/source-attribution?days=${days}`);
        const container = document.getElementById('source-attribution-chart');
        if (!container) return;

        if (Object.keys(data.sources).length === 0) {
            container.innerHTML = '<p class="text-slate-400 text-sm text-center py-4">No source data yet</p>';
            return;
        }

        container.innerHTML = Object.entries(data.sources)
            .sort((a, b) => b[1].total - a[1].total)
            .map(([source, stats]) => `
            <div class="flex items-center justify-between p-3 bg-slate-50 rounded-xl mb-2">
                <div>
                    <div class="font-bold text-sm text-slate-900">${Components.safeHTML(source)}</div>
                    <div class="text-[10px] text-slate-400">${stats.total} candidates · ${stats.avg_score || 0} avg score</div>
                </div>
                <div class="text-right">
                    <div class="font-black text-indigo-600">${stats.hired} hired</div>
                    <div class="text-[9px] text-slate-400">${stats.conversion_rate || 0}% conversion</div>
                </div>
            </div>
        `).join('');
    } catch (e) {
        console.warn('Failed to load source attribution:', e);
    }
}

async function loadCostPerHire(days = 90) {
    try {
        const data = await window.fetchAPI(`/recruiter/enhancements/analytics/cost-per-hire?days=${days}`);
        const container = document.getElementById('cost-per-hire-chart');
        if (!container) return;

        container.innerHTML = `
            <div class="grid grid-cols-2 gap-4 mb-4">
                <div class="bg-slate-50 rounded-xl p-4 text-center">
                    <div class="text-2xl font-black text-indigo-600">${data.total_cost} TND</div>
                    <div class="text-[10px] text-slate-400 font-bold uppercase">Total Spend</div>
                </div>
                <div class="bg-slate-50 rounded-xl p-4 text-center">
                    <div class="text-2xl font-black text-indigo-600">${data.cost_per_hire} TND</div>
                    <div class="text-[10px] text-slate-400 font-bold uppercase">Cost Per Hire</div>
                </div>
            </div>
            <div class="text-center text-sm text-slate-500">
                ${data.total_hires} hires in ${days} days
            </div>
            ${Object.keys(data.cost_by_type).length > 0 ? `
            <div class="mt-4 space-y-2">
                ${Object.entries(data.cost_by_type).map(([type, amount]) => `
                    <div class="flex justify-between text-sm">
                        <span class="text-slate-600 capitalize">${type.replace('_', ' ')}</span>
                        <span class="font-bold">${amount} TND</span>
                    </div>
                `).join('')}
            </div>` : ''}
        `;
    } catch (e) {
        console.warn('Failed to load cost-per-hire:', e);
    }
}

// ============================================================================
// INTERVIEW DEBRIEF
// ============================================================================
async function generateDebrief(interviewId) {
    const container = document.getElementById('debrief-container');
    if (container) {
        container.innerHTML = '<div class="flex items-center justify-center py-8"><i class="fas fa-spinner fa-spin text-2xl text-indigo-600"></i></div>';
    }

    try {
        const debrief = await window.fetchAPI(`/recruiter/enhancements/debrief/${interviewId}`, {
            method: 'POST'
        });

        if (container) {
            container.innerHTML = `
                <div class="bg-white rounded-2xl border border-slate-200 p-6">
                    <h3 class="text-lg font-bold text-slate-900 mb-4">Interview Debrief</h3>
                    
                    <div class="grid grid-cols-3 gap-4 mb-6">
                        <div class="bg-slate-50 rounded-xl p-3 text-center">
                            <div class="text-xl font-black text-indigo-600">${Math.round(debrief.score_entity?.final_score ?? debrief.overall_score)}</div>
                            <div class="text-[9px] text-slate-400 font-bold uppercase">Overall Score</div>
                        </div>
                        <div class="bg-slate-50 rounded-xl p-3 text-center">
                            <div class="text-xl font-black text-indigo-600">${debrief.consensus || 'N/A'}</div>
                            <div class="text-[9px] text-slate-400 font-bold uppercase">Consensus</div>
                        </div>
                        <div class="bg-slate-50 rounded-xl p-3 text-center">
                            <div class="text-xl font-black text-slate-600">${debrief.interview_feedback.length}</div>
                            <div class="text-[9px] text-slate-400 font-bold uppercase">Feedback Entries</div>
                        </div>
                    </div>

                    ${debrief.ai_summary ? `
                    <div class="mb-6 p-4 bg-indigo-50 rounded-xl">
                        <h4 class="text-sm font-bold text-indigo-900 mb-2">AI Summary</h4>
                        <div class="text-sm text-indigo-800 prose prose-sm">${debrief.ai_summary}</div>
                    </div>` : ''}

                    ${debrief.strengths.length > 0 ? `
                    <div class="mb-4">
                        <h4 class="text-sm font-bold text-indigo-600 mb-2">Strengths</h4>
                        <ul class="space-y-1">
                            ${debrief.strengths.map(s => `<li class="text-sm text-slate-700">• ${Components.safeHTML(s)}</li>`).join('')}
                        </ul>
                    </div>` : ''}

                    ${debrief.concerns.length > 0 ? `
                    <div class="mb-4">
                        <h4 class="text-sm font-bold text-red-600 mb-2">Concerns</h4>
                        <ul class="space-y-1">
                            ${debrief.concerns.map(c => `<li class="text-sm text-slate-700">• ${Components.safeHTML(c)}</li>`).join('')}
                        </ul>
                    </div>` : ''}
                </div>
            `;
        }
    } catch (e) {
        console.error('Debrief generation failed:', e);
        if (container) {
            container.innerHTML = '<p class="text-red-500 text-sm text-center py-4">Failed to generate debrief</p>';
        }
    }
}

// ============================================================================
// BIAS ANALYSIS INTEGRATION
// ============================================================================
async function analyzeJobBias(jobId) {
    try {
        const result = await window.fetchAPI(`/jd/analyze/${jobId}`, { method: 'POST' });
        return result;
    } catch (e) {
        console.error('Bias analysis failed:', e);
        throw e;
    }
}

async function runBiasCheckOnDescription(title, description) {
    if (!description || !description.trim()) {
        Components.showToast('No description to analyze.', 'warning');
        return null;
    }
    try {
        const result = await window.fetchAPI('/jd/analyze', {
            method: 'POST',
            body: JSON.stringify({ title, description })
        });
        return result;
    } catch (e) {
        Components.showToast('Bias check failed: ' + e.message, 'error');
        return null;
    }
}

function showBiasResultModal(result) {
    const existing = document.getElementById('bias-result-modal');
    if (existing) existing.remove();

    const gradeColors = { A: 'bg-indigo-100 text-indigo-700 border-indigo-200', B: 'bg-indigo-50 text-indigo-600 border-indigo-100', C: 'bg-amber-100 text-amber-700 border-amber-200', D: 'bg-orange-100 text-orange-700 border-orange-200', F: 'bg-red-100 text-red-700 border-red-200' };
    const gc = gradeColors[result.grade] || 'bg-slate-100 text-slate-600';

    const modal = document.createElement('div');
    modal.id = 'bias-result-modal';
    modal.className = 'fixed inset-0 z-[200] flex items-center justify-center bg-black/50';
    modal.innerHTML = `
        <div class="bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 max-h-[80vh] overflow-y-auto">
            <div class="flex items-center justify-between p-5 border-b border-slate-100">
                <div class="flex items-center gap-3">
                    <span class="px-3 py-1 rounded-xl text-sm font-black ${gc}">${result.grade}</span>
                    <h3 class="text-lg font-bold text-slate-900">Bias Analysis</h3>
                </div>
                <button onclick="this.closest('#bias-result-modal').remove()" class="w-8 h-8 rounded-lg hover:bg-slate-100 flex items-center justify-center">
                    <i class="fas fa-times text-slate-400"></i>
                </button>
            </div>
            <div class="p-5 space-y-4">
                <div class="flex items-center gap-4">
                    <div class="flex-1">
                        <div class="text-[9px] font-bold text-slate-400 uppercase tracking-widest mb-1">Score</div>
                        <div class="text-2xl font-black text-slate-900">${result.score_entity?.final_score ?? result.overall_score}/100</div>
                    </div>
                    ${result.reading_level ? `
                    <div class="flex-1">
                        <div class="text-[9px] font-bold text-slate-400 uppercase tracking-widest mb-1">Reading Level</div>
                        <div class="text-sm font-bold text-slate-900">${result.reading_level}</div>
                    </div>` : ''}
                </div>

                ${result.summary ? `<div class="p-3 bg-slate-50 rounded-xl text-sm text-slate-700 leading-relaxed">${Components.safeHTML(result.summary)}</div>` : ''}

                ${result.flags && result.flags.length > 0 ? `
                <div>
                    <div class="text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">${result.flags.length} Flag(s) Found</div>
                    <div class="space-y-2">
                        ${result.flags.slice(0, 8).map(f => {
                            const colors = { high: 'bg-red-50 border-red-200 text-red-700', medium: 'bg-amber-50 border-amber-200 text-amber-700', low: 'bg-slate-50 border-slate-200 text-slate-600' };
                            return `<div class="p-2.5 rounded-xl border ${colors[f.severity] || colors.low} text-xs">
                                <span class="font-bold">"${Components.safeHTML(f.found)}"</span>
                                <span class="opacity-60 ml-2">${f.category.replace(/_/g, ' ')}</span>
                            </div>`;
                        }).join('')}
                        ${result.flags.length > 8 ? `<p class="text-xs text-slate-400 text-center">...and ${result.flags.length - 8} more</p>` : ''}
                    </div>
                </div>` : `
                <div class="p-4 bg-indigo-50 rounded-xl text-center">
                    <i class="fas fa-check-circle text-indigo-500 text-xl mb-1"></i>
                    <p class="text-sm text-indigo-700 font-medium">No bias flags detected!</p>
                </div>`}

                ${result.rewritten_description ? `
                <div class="border-t border-slate-100 pt-4">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-xs font-bold text-slate-400 uppercase tracking-widest">Inclusive Rewrite</span>
                        <button onclick="copyRewrite()" class="text-[10px] font-bold text-indigo-600 hover:text-indigo-800">Copy</button>
                    </div>
                    <div class="p-3 bg-indigo-50 rounded-xl text-sm text-slate-700 leading-relaxed max-h-32 overflow-y-auto">${Components.safeHTML(result.rewritten_description)}</div>
                    ${result.changelog && result.changelog.length > 0 ? `
                    <div class="mt-3 text-xs text-slate-500 space-y-1">
                        ${result.changelog.map(c => `<div><span class="line-through text-red-400">${Components.safeHTML(c.original)}</span> → <span class="text-indigo-600">${Components.safeHTML(c.replacement)}</span></div>`).join('')}
                    </div>` : ''}
                </div>` : ''}
            </div>
            <div class="p-5 border-t border-slate-100 flex gap-3">
                <button onclick="this.closest('#bias-result-modal').remove()" class="flex-1 py-3 bg-slate-100 text-slate-700 font-bold rounded-xl hover:bg-slate-200 transition">Close</button>
                ${result.rewritten_description ? `<button onclick="applyRewriteFromModal()" class="flex-1 py-3 bg-gradient-to-r from-indigo-600 to-purple-600 text-white font-bold rounded-xl hover:shadow-lg transition">Apply Rewrite</button>` : ''}
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    window._biasResult = result;
}

function copyRewrite() {
    const text = window._biasResult?.rewritten_description;
    if (text) {
        navigator.clipboard.writeText(text).then(() => Components.showToast('Rewrite copied!', 'success'));
    }
}

function applyRewriteFromModal() {
    const text = window._biasResult?.rewritten_description;
    if (text) {
        const descField = document.getElementById('job-desc');
        if (descField) descField.value = text;
        document.getElementById('bias-result-modal')?.remove();
        Components.showToast('Inclusive rewrite applied!', 'success');
    }
}

// ============================================================================
// EXPORT
// ============================================================================
// ============================================================================
// CLONE JOB
// ============================================================================
async function cloneJob(id) {
    if (!await Components.showConfirm('Clone Job', 'Clone this job? This will create a new job posting with "(Copy)" appended to the title.', 'Clone', 'info')) return;
    try {
        const job = await window.fetchAPI(`/recruiter/jobs/${id}/clone`, { method: 'POST' });
        Components.showToast(`Job cloned successfully: ${job.title}`, 'success');
        const loadFn = window.loadJobs;
        if (typeof loadFn === 'function') loadFn();
    } catch (e) {
        Components.showToast(e.message || 'Failed to clone job', 'error');
    }
}

window.Enhancements = {
    init: initEnhancements,
    quickAction,
    showUndoNotification,
    executeUndo,
    openStageManager,
    closeStageManager,
    addNewStage,
    deleteStage,
    loadAutomationRules,
    createAutomationRule,
    toggleAutomationRule,
    deleteAutomationRule,
    loadTaggedNotes,
    addTaggedNote,
    toggleNotePin,
    resolveNote,
    deleteNote,
    loadScorecards,
    submitScorecard,
    loadWebhooks,
    toggleWebhook,
    loadTimeInStageAnalytics,
    loadSourceAttribution,
    loadCostPerHire,
    generateDebrief,
    showKeyboardHelp,
    cloneJob,
    analyzeJobBias,
    runBiasCheckOnDescription,
    showBiasResultModal,
};

// Auto-init when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initEnhancements);
} else {
    initEnhancements();
}
