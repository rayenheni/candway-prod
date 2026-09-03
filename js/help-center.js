/**
 * Help Center Modal
 * ==================
 * Comprehensive help system with FAQ, keyboard shortcuts, and feature guides.
 * Triggered via help button in header or ? key.
 */

const HelpCenter = (() => {
    let modal = null;

    const FAQ_DATA = [
        {
            q: "How do I move candidates between pipeline stages?",
            a: "Drag and drop candidate cards between columns on the Pipeline page, or use the quick action buttons (Invite, Shortlist, Reject, Archive) on each card. You can also customize stages via Tools > Stage Manager."
        },
        {
            q: "How do I create automation rules?",
            a: "Go to Tools > Automation Rules on the Pipeline page. Click 'Add Rule' to create rules based on score thresholds, status changes, interview completion, or inactivity. Rules can auto-move candidates, send reminders, or assign recruiters."
        },
        {
            q: "What are Tagged Notes?",
            a: "Tagged Notes let you add structured notes to candidate profiles with priority levels and tags. Find them on the candidate detail page under the Notes tab. Pin important notes and mark them as resolved when done."
        },
        {
            q: "How do I use Interview Scorecards?",
            a: "Create scorecards in Tools > Scorecards or on the candidate's Interviews tab. Define criteria with weights and max scores, then submit evaluations after interviews. Scorecards calculate weighted overall scores automatically."
        },
        {
            q: "How does the AI Debrief work?",
            a: "After an interview, click the 'AI Debrief' button on the candidate's Interviews tab. It aggregates all feedback, scorecard results, and AI analysis into a comprehensive summary with strengths, concerns, and hiring consensus."
        },
        {
            q: "Can I undo accidental actions?",
            a: "Yes! After using quick actions (Invite, Shortlist, Reject, Archive), a 10-second undo window appears. Click 'Undo' to revert the action. You can also view pending undos in the Tools menu."
        },
        {
            q: "How do I track cost-per-hire?",
            a: "Go to the Dashboard and find the Analytics section. Click 'Cost-per-Hire' to view total costs, breakdown by type, and cost per hire. Add campaign costs via the Analytics page or API."
        },
        {
            q: "How do I set up webhook integrations?",
            a: "Go to Tools > Webhooks (or Settings > Integrations). Add a webhook URL, select events to subscribe to, and test the connection. Webhooks notify external systems when candidates move stages or complete interviews."
        },
        {
            q: "Is there a mobile view for the pipeline?",
            a: "Yes! Click Tools > Mobile View on the Pipeline page to switch to a swipeable Kanban board optimized for mobile devices. Use horizontal swipe gestures to navigate between stages."
        },
        {
            q: "How do I see source attribution analytics?",
            a: "On the Dashboard, click 'Source Attribution' in the Analytics section. It shows which channels (LinkedIn, Direct, Referrals, etc.) produce the best candidates with conversion rates and average scores."
        },
    ];

    const SHORTCUTS = [
        { key: '?', desc: 'Show keyboard shortcuts' },
        { key: 'Ctrl+T', desc: 'Start onboarding tour' },
        { key: 'Ctrl+K', desc: 'Focus search bar' },
        { key: 'N', desc: 'New job posting' },
        { key: 'G P', desc: 'Go to Pipeline' },
        { key: 'G D', desc: 'Go to Dashboard' },
        { key: 'G C', desc: 'Go to Candidates' },
        { key: 'Esc', desc: 'Close modals / exit tour' },
    ];

    const FEATURES = [
        { icon: 'fa-bolt', title: 'Quick Actions', desc: 'One-click invite, shortlist, reject, or archive on pipeline cards.' },
        { icon: 'fa-eye', title: 'Hover Previews', desc: 'Rich candidate previews with scores, skills, and analysis on hover.' },
        { icon: 'fa-rotate-left', title: 'Undo System', desc: '10-second rollback window for accidental actions.' },
        { icon: 'fa-layer-group', title: 'Custom Stages', desc: 'Create, edit, and reorder pipeline stages per campaign.' },
        { icon: 'fa-robot', title: 'Automation Rules', desc: 'Auto-move candidates based on scores, status, or inactivity.' },
        { icon: 'fa-tags', title: 'Tagged Notes', desc: 'Structured notes with priority, tags, pin, and resolve.' },
        { icon: 'fa-clipboard-check', title: 'Scorecards', desc: 'Weighted interview evaluations with auto-calculated scores.' },
        { icon: 'fa-brain', title: 'AI Debrief', desc: 'Auto-generated interview summaries with hiring consensus.' },
        { icon: 'fa-chart-line', title: 'Analytics', desc: 'Time-in-stage, source attribution, and cost-per-hire metrics.' },
        { icon: 'fa-plug', title: 'Webhooks', desc: 'Integrate with Slack, Teams, or custom systems via webhooks.' },
    ];

    function createModal() {
        if (modal) return;

        modal = document.createElement('div');
        modal.className = 'help-center-modal';
        modal.innerHTML = `
            <div class="help-center-content">
                <div class="help-center-header">
                    <h2><i class="fa-solid fa-circle-question" style="margin-right:8px;"></i>Help & Guide</h2>
                    <button class="help-center-close" id="help-close"><i class="fa-solid fa-xmark"></i></button>
                </div>
                <div class="help-center-body">
                    <div class="help-section">
                        <div class="help-section-title">Features Overview</div>
                        <div class="help-feature-list">
                            ${FEATURES.map(f => `
                                <div class="help-feature-item">
                                    <div class="help-feature-icon"><i class="fa-solid ${f.icon}"></i></div>
                                    <div class="help-feature-text">
                                        <h4>${f.title}</h4>
                                        <p>${f.desc}</p>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>

                    <div class="help-section">
                        <div class="help-section-title">Keyboard Shortcuts</div>
                        <div class="help-shortcut-grid">
                            ${SHORTCUTS.map(s => `
                                <div class="help-shortcut-item">
                                    <span class="help-shortcut-key">${s.key}</span>
                                    <span class="help-shortcut-desc">${s.desc}</span>
                                </div>
                            `).join('')}
                        </div>
                    </div>

                    <div class="help-section">
                        <div class="help-section-title">Frequently Asked Questions</div>
                        ${FAQ_DATA.map((faq, i) => `
                            <div class="help-faq-item">
                                <div class="help-faq-question" data-faq="${i}">
                                    <span>${faq.q}</span>
                                    <i class="fa-solid fa-chevron-down" style="font-size:10px;transition:transform 0.2s;"></i>
                                </div>
                                <div class="help-faq-answer" id="faq-answer-${i}">${faq.a}</div>
                            </div>
                        `).join('')}
                    </div>

                    <div class="help-section" style="text-align:center;padding-top:16px;border-top:1px solid rgba(99,102,241,0.1);">
                        <button class="tour-btn tour-btn-primary" id="start-tour-btn" style="margin-right:8px;">
                            <i class="fa-solid fa-play" style="margin-right:6px;"></i>Start Tour
                        </button>
                        <button class="tour-btn tour-btn-secondary" id="reset-tour-btn">
                            <i class="fa-solid fa-rotate-left" style="margin-right:6px;"></i>Reset Tour Progress
                        </button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // Bind close
        modal.querySelector('#help-close').addEventListener('click', closeModal);
        modal.addEventListener('click', (e) => {
            if (e.target === modal) closeModal();
        });

        // Bind FAQ toggles
        modal.querySelectorAll('.help-faq-question').forEach(q => {
            q.addEventListener('click', () => {
                const idx = q.dataset.faq;
                const answer = document.getElementById(`faq-answer-${idx}`);
                const icon = q.querySelector('i');
                answer.classList.toggle('open');
                icon.style.transform = answer.classList.contains('open') ? 'rotate(180deg)' : '';
            });
        });

        // Bind tour buttons
        modal.querySelector('#start-tour-btn').addEventListener('click', () => {
            closeModal();
            setTimeout(() => RecruiterTour.startTour(), 300);
        });

        modal.querySelector('#reset-tour-btn').addEventListener('click', () => {
            localStorage.removeItem('recruiter_tour_completed');
            closeModal();
            setTimeout(() => RecruiterTour.startTour(), 300);
        });
    }

    function openModal() {
        if (!FeatureFlags.isEnabled('recruiter_help_center')) return;
        createModal();
        modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }

    function closeModal() {
        if (modal) {
            modal.style.display = 'none';
            document.body.style.overflow = '';
        }
    }

    function init() {
        FeatureFlags.init().then(() => {
            if (!FeatureFlags.isEnabled('recruiter_help_center')) return;

            // Listen for help button clicks
            document.addEventListener('click', (e) => {
                const btn = e.target.closest('[data-action="open-help"], #help-button, .help-icon');
                if (btn) {
                    e.preventDefault();
                    openModal();
                }
            });

            // ? key shortcut (only when not typing)
            document.addEventListener('keydown', (e) => {
                if (e.key === '?' && !e.target.matches('input, textarea, [contenteditable]')) {
                    e.preventDefault();
                    openModal();
                }
            });
        });
    }

    return {
        init,
        openModal,
        closeModal,
    };
})();

// Auto-init on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => HelpCenter.init());
} else {
    HelpCenter.init();
}
