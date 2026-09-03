/**
 * Recruiter Onboarding Tour
 * ==========================
 * Interactive step-by-step tour highlighting key features.
 * Triggered on first login or via Help menu.
 */

const RecruiterTour = (() => {
    const STORAGE_KEY = 'recruiter_tour_completed';
    const TOUR_STEPS = [
        {
            target: '#sidebar-container',
            title: 'Navigation Sidebar',
            content: 'Access all your tools from here: Dashboard, Jobs, Analytics, Candidates, Pipeline, Campaigns, Interviews, and Settings.',
            position: 'right',
        },
        {
            target: '#top-header-container, #header-container, [class*="header"]',
            title: 'Search & Quick Actions',
            content: 'Search candidates, jobs, or campaigns quickly. Use the notification bell and messages icon to stay connected.',
            position: 'bottom',
        },
        {
            target: '[data-tooltip="Post a new job"], .btn-premium, button:has(.fa-plus)',
            title: 'Post Jobs',
            content: 'Create new job postings with AI-assisted descriptions. Jobs appear in your dashboard and can be linked to campaigns.',
            position: 'bottom',
        },
        {
            target: '#pipeline-container, [id*="pipeline"], .pipeline-board',
            title: 'Talent Pipeline',
            content: 'Manage candidates in a Kanban board. Drag and drop between stages, use quick actions (invite, shortlist, reject), and hover for rich previews.',
            position: 'top',
        },
        {
            target: '#tools-dropdown, [id*="tools"], button:has(.fa-ellipsis)',
            title: 'Tools Menu',
            content: 'Access Stage Manager, Automation Rules, Mobile Kanban View, and Keyboard Shortcuts from this dropdown.',
            position: 'bottom',
        },
        {
            target: '.analytics-section, [id*="analytics"], .dashboard-stats',
            title: 'Analytics Dashboard',
            content: 'Track Time-in-Stage, Source Attribution, and Cost-per-Hire metrics. Click cards to load detailed reports.',
            position: 'top',
        },
        {
            target: '.candidate-card, .application-card, [class*="candidate"]',
            title: 'Candidate Cards',
            content: 'Click any candidate to view their full profile, AI analysis, interview history, tagged notes, and scorecards.',
            position: 'top',
        },
        {
            target: '#help-button, .help-icon, [data-tooltip="Help & Guide"]',
            title: 'Help & Guide',
            content: 'Access the Help Center anytime for FAQs, keyboard shortcuts, and feature guides. Press ? to show shortcuts.',
            position: 'bottom',
        },
    ];

    let currentStep = 0;
    let overlay = null;
    let tooltip = null;
    let isActive = false;

    function hasCompletedTour() {
        return localStorage.getItem(STORAGE_KEY) === 'true';
    }

    function markCompleted() {
        localStorage.setItem(STORAGE_KEY, 'true');
    }

    function findTarget(selector) {
        if (!selector) return null;
        const selectors = selector.split(',').map(s => s.trim());
        for (const s of selectors) {
            const el = document.querySelector(s);
            if (el) return el;
        }
        return null;
    }

    function createOverlay() {
        if (overlay) return;
        overlay = document.createElement('div');
        overlay.className = 'tour-overlay';
        document.body.appendChild(overlay);
    }

    function removeOverlay() {
        if (overlay) {
            overlay.remove();
            overlay = null;
        }
    }

    function createTooltip() {
        if (tooltip) tooltip.remove();
        tooltip = document.createElement('div');
        tooltip.className = 'tour-tooltip';
        document.body.appendChild(tooltip);
    }

    function removeTooltip() {
        if (tooltip) {
            tooltip.remove();
            tooltip = null;
        }
    }

    function positionTooltip(targetEl, position) {
        if (!targetEl || !tooltip) return;
        const rect = targetEl.getBoundingClientRect();
        const tooltipRect = tooltip.getBoundingClientRect();
        const gap = 12;
        let top, left;

        switch (position) {
            case 'bottom':
                top = rect.bottom + gap;
                left = rect.left + (rect.width - tooltipRect.width) / 2;
                break;
            case 'left':
                top = rect.top + (rect.height - tooltipRect.height) / 2;
                left = rect.left - tooltipRect.width - gap;
                break;
            case 'right':
                top = rect.top + (rect.height - tooltipRect.height) / 2;
                left = rect.right + gap;
                break;
            default: // top
                top = rect.top - tooltipRect.height - gap;
                left = rect.left + (rect.width - tooltipRect.width) / 2;
        }

        // Keep within viewport
        left = Math.max(10, Math.min(left, window.innerWidth - tooltipRect.width - 10));
        top = Math.max(10, Math.min(top, window.innerHeight - tooltipRect.height - 10));

        tooltip.style.top = `${top}px`;
        tooltip.style.left = `${left}px`;
    }

    function highlightTarget(targetEl) {
        document.querySelectorAll('.tour-highlight').forEach(el => el.classList.remove('tour-highlight'));
        if (targetEl) {
            targetEl.classList.add('tour-highlight');
            targetEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }

    function renderStep() {
        if (currentStep >= TOUR_STEPS.length) {
            endTour();
            return;
        }

        const step = TOUR_STEPS[currentStep];
        const targetEl = findTarget(step.target);

        createOverlay();
        createTooltip();
        highlightTarget(targetEl);

        tooltip.innerHTML = `
            <div class="tour-tooltip-header">
                <span class="tour-tooltip-title">${step.title}</span>
                <span class="tour-tooltip-step">${currentStep + 1} / ${TOUR_STEPS.length}</span>
            </div>
            <div class="tour-tooltip-content">${step.content}</div>
            <div class="tour-tooltip-actions">
                <button class="tour-btn tour-btn-skip" data-action="skip">Skip tour</button>
                <div style="display:flex;gap:8px;">
                    ${currentStep > 0 ? '<button class="tour-btn tour-btn-secondary" data-action="prev">Previous</button>' : ''}
                    <button class="tour-btn tour-btn-primary" data-action="next">${currentStep === TOUR_STEPS.length - 1 ? 'Finish' : 'Next'}</button>
                </div>
            </div>
        `;

        // Wait for DOM update then position
        requestAnimationFrame(() => {
            positionTooltip(targetEl, step.position);
        });

        // Bind actions
        tooltip.querySelectorAll('[data-action]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const action = e.target.dataset.action;
                if (action === 'next') {
                    currentStep++;
                    renderStep();
                } else if (action === 'prev') {
                    currentStep--;
                    renderStep();
                } else if (action === 'skip') {
                    endTour();
                }
            });
        });
    }

    function endTour() {
        removeOverlay();
        removeTooltip();
        document.querySelectorAll('.tour-highlight').forEach(el => el.classList.remove('tour-highlight'));
        isActive = false;
        markCompleted();
    }

    function startTour() {
        if (isActive) return;
        isActive = true;
        currentStep = 0;
        renderStep();
    }

    function init() {
        FeatureFlags.init().then(() => {
            if (!FeatureFlags.isEnabled('recruiter_onboarding_tour')) return;
            if (!hasCompletedTour()) {
                // Delay tour start to let page fully render
                setTimeout(() => {
                    startTour();
                }, 1500);
            }
        });
    }

    // Keyboard shortcut: Ctrl+T to restart tour
    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === 't') {
            e.preventDefault();
            startTour();
        }
        if (e.key === 'Escape' && isActive) {
            endTour();
        }
    });

    return {
        init,
        startTour,
        endTour,
        hasCompletedTour,
    };
})();

// Auto-init on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => RecruiterTour.init());
} else {
    RecruiterTour.init();
}
