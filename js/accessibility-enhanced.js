/**
 * Accessibility Module
 * Adds ARIA labels, keyboard navigation, focus management, and screen reader support.
 * Improves WCAG 2.1 AA compliance across the platform.
 */

const Accessibility = {
    /**
     * Initialize accessibility improvements.
     */
    init() {
        this.addSkipLink();
        this.enhanceFocusIndicators();
        this.addAriaLabels();
        this.setupKeyboardNav();
        this.setupScreenReaderAnnouncer();
        this.enhanceColorContrast();
        _log('[Accessibility] Module initialized');
    },

    /**
     * Add skip-to-content link for keyboard users.
     */
    addSkipLink() {
        if (document.getElementById('skip-link')) return;
        
        const skipLink = document.createElement('a');
        skipLink.id = 'skip-link';
        skipLink.href = '#main-content';
        skipLink.textContent = 'Skip to main content';
        skipLink.className = 'skip-link';
        document.body.insertBefore(skipLink, document.body.firstChild);
    },

    /**
     * Enhance focus indicators for better visibility.
     */
    enhanceFocusIndicators() {
        const style = document.createElement('style');
        style.textContent = `
            .skip-link {
                position: absolute;
                top: -40px;
                left: 0;
                background: #7C3AED;
                color: white;
                padding: 8px 16px;
                z-index: 10000;
                transition: top 0.2s;
                font-weight: bold;
                text-decoration: none;
            }
            .skip-link:focus {
                top: 0;
            }
            /* Focus indicators - scoped to interactive elements only */
            button:focus-visible, a:focus-visible, input:focus-visible, select:focus-visible, textarea:focus-visible, [tabindex]:focus-visible {
                outline: 2px solid #7C3AED;
                outline-offset: 2px;
            }
            /* Prevent focus ring on mouse clicks */
            :focus:not(:focus-visible) {
                outline: none;
            }
            .sr-only {
                position: absolute;
                width: 1px;
                height: 1px;
                padding: 0;
                margin: -1px;
                overflow: hidden;
                clip: rect(0, 0, 0, 0);
                white-space: nowrap;
                border-width: 0;
            }
        `;
        document.head.appendChild(style);
    },

    /**
     * Add ARIA labels to interactive elements missing them.
     */
    addAriaLabels() {
        // Add aria-label to buttons with only icons
        document.querySelectorAll('button:not([aria-label]):not([aria-labelledby])').forEach(btn => {
            const icon = btn.querySelector('i, svg');
            if (icon && !btn.textContent.trim()) {
                const title = btn.title || icon.className || 'Button';
                btn.setAttribute('aria-label', title.replace(/fa-/g, '').replace(/fas |far |fab /g, ''));
            }
        });

        // Add role="main" to main content area
        const mainContent = document.querySelector('#main-content, main, .main-content, #dashboard-cockpit');
        if (mainContent && !mainContent.getAttribute('role')) {
            mainContent.setAttribute('role', 'main');
            mainContent.id = mainContent.id || 'main-content';
        }

        // Add aria-live regions for dynamic content
        this.ensureAriaLive('toast-container', 'polite');
        this.ensureAriaLive('notification-area', 'assertive');

        // Add aria-describedby to form inputs with errors
        document.querySelectorAll('input[aria-invalid="true"], input.is-invalid').forEach(input => {
            if (!input.getAttribute('aria-describedby')) {
                const errorEl = input.parentElement?.querySelector('.error-message, .text-red-500');
                if (errorEl) {
                    const errorId = `error-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`;
                    errorEl.id = errorId;
                    input.setAttribute('aria-describedby', errorId);
                }
            }
        });
    },

    /**
     * Ensure an aria-live region exists.
     */
    ensureAriaLive(id, politeness = 'polite') {
        if (!document.getElementById(id)) {
            const region = document.createElement('div');
            region.id = id;
            region.setAttribute('aria-live', politeness);
            region.setAttribute('aria-atomic', 'true');
            region.className = 'sr-only';
            document.body.appendChild(region);
        }
    },

    /**
     * Announce message to screen readers.
     */
    announce(message, politeness = 'polite') {
        const region = document.getElementById(`toast-container`) || document.getElementById('notification-area');
        if (region) {
            region.textContent = '';
            setTimeout(() => { region.textContent = message; }, 100);
        }
    },

    /**
     * Setup keyboard navigation shortcuts.
     */
    setupKeyboardNav() {
        document.addEventListener('keydown', (e) => {
            // Alt + 1: Skip to main content
            if (e.altKey && e.key === '1') {
                e.preventDefault();
                const main = document.getElementById('main-content');
                if (main) main.focus();
            }

            // Alt + 2: Skip to navigation
            if (e.altKey && e.key === '2') {
                e.preventDefault();
                const nav = document.querySelector('nav, [role="navigation"]');
                if (nav) nav.focus();
            }

            // Alt + 0: Skip to footer
            if (e.altKey && e.key === '0') {
                e.preventDefault();
                const footer = document.querySelector('footer, [role="contentinfo"]');
                if (footer) footer.focus();
            }

            // Escape: Close modals
            if (e.key === 'Escape') {
                const openModal = document.querySelector('[role="dialog"]:not(.hidden), .modal:not(.hidden)');
                if (openModal) {
                    e.preventDefault();
                    const closeBtn = openModal.querySelector('[data-close], .close-btn, button.close');
                    if (closeBtn) closeBtn.click();
                }
            }
        });
    },

    /**
     * Setup screen reader announcer region.
     */
    setupScreenReaderAnnouncer() {
        this.ensureAriaLive('sr-announcer', 'assertive');
    },

    /**
     * Enhance color contrast for better readability.
     * Only applies to specific low-contrast elements, not global overrides.
     */
    enhanceColorContrast() {
        const style = document.createElement('style');
        style.textContent = `
            /* Only improve contrast for body text, not UI components */
            p.text-slate-500, span.text-slate-500, div.text-slate-500 {
                color: #475569;
            }
            /* Ensure links are distinguishable from text */
            a:not([class*="btn"]):not([class*="button"]):not([class*="nav-"]) {
                text-decoration: underline;
            }
            /* Improve focus ring visibility in dark mode only */
            [data-theme="dark"] button:focus-visible,
            [data-theme="dark"] a:focus-visible,
            [data-theme="dark"] input:focus-visible {
                outline-color: #A78BFA;
            }
        `;
        document.head.appendChild(style);
    },

    /**
     * Trap focus within a modal/dialog.
     */
    trapFocus(modal) {
        if (!modal) return;
        
        const focusable = modal.querySelectorAll(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        const firstFocusable = focusable[0];
        const lastFocusable = focusable[focusable.length - 1];

        modal.addEventListener('keydown', (e) => {
            if (e.key !== 'Tab') return;

            if (e.shiftKey) {
                if (document.activeElement === firstFocusable) {
                    e.preventDefault();
                    lastFocusable.focus();
                }
            } else {
                if (document.activeElement === lastFocusable) {
                    e.preventDefault();
                    firstFocusable.focus();
                }
            }
        });

        // Focus first element when modal opens
        setTimeout(() => firstFocusable?.focus(), 100);
    }
};

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => Accessibility.init());
} else {
    Accessibility.init();
}

window.Accessibility = Accessibility;
