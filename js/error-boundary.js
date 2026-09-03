/**
 * Error Boundary System
 * Prevents full page crashes when API calls or UI components fail.
 * Wraps critical sections with try/catch and renders fallback UI.
 */

const ErrorBoundary = {
    /**
     * Wrap an async function with error boundary protection.
     * Returns [result, error] tuple like React's try/catch pattern.
     */
    async wrap(asyncFn, fallback = null) {
        try {
            const result = await asyncFn();
            return [result, null];
        } catch (error) {
            console.error('[ErrorBoundary] Caught error:', error);
            this.logError(error);
            return [fallback, error];
        }
    },

    /**
     * Execute a function and render fallback UI on error.
     * @param {Function} renderFn - Function that returns HTML string or DOM element
     * @param {string} targetSelector - CSS selector for target container
     * @param {Function} fallbackFn - Function that returns fallback HTML
     */
    render(renderFn, targetSelector, fallbackFn) {
        try {
            const content = renderFn();
            const target = document.querySelector(targetSelector);
            if (target) {
                if (typeof content === 'string') {
                    target.innerHTML = content;
                } else if (content instanceof HTMLElement) {
                    target.innerHTML = '';
                    target.appendChild(content);
                }
            }
        } catch (error) {
            console.error(`[ErrorBoundary] Render failed for ${targetSelector}:`, error);
            this.logError(error);
            if (fallbackFn) {
                const target = document.querySelector(targetSelector);
                if (target) {
                    const fallback = fallbackFn(error);
                    target.innerHTML = typeof fallback === 'string' ? fallback : '';
                }
            }
        }
    },

    /**
     * Safe API call with automatic error handling and optional retry.
     * @param {Function} apiFn - Async API function to call
     * @param {Object} options - { retries: number, fallback: any, onError: Function }
     */
    async safeApiCall(apiFn, options = {}) {
        const { retries = 1, fallback = null, onError = null } = options;
        let lastError;

        for (let attempt = 0; attempt <= retries; attempt++) {
            try {
                const result = await apiFn();
                return result;
            } catch (error) {
                lastError = error;
                if (attempt < retries) {
                    const delay = Math.pow(2, attempt) * 1000;
                    console.warn(`[ErrorBoundary] API call failed, retrying in ${delay}ms (attempt ${attempt + 1}/${retries})`);
                    await new Promise(resolve => setTimeout(resolve, delay));
                }
            }
        }

        if (onError) onError(lastError);
        return fallback;
    },

    /**
     * Initialize global error handlers.
     * Catches unhandled promise rejections and script errors.
     */
    init() {
        // Catch unhandled promise rejections
        window.addEventListener('unhandledrejection', (event) => {
            console.error('[ErrorBoundary] Unhandled promise rejection:', event.reason);
            this.logError(event.reason);
            
            if (typeof ErrorHandler !== 'undefined') {
                ErrorHandler.show('An unexpected error occurred. Please refresh the page.', 'error');
            }
        });

        // Catch script errors
        window.addEventListener('error', (event) => {
            if (event.filename && event.filename.includes(window.location.origin)) {
                console.error('[ErrorBoundary] Script error:', event.message, 'at', event.filename, ':', event.lineno);
                this.logError(new Error(event.message));
            }
        });

        _log('[ErrorBoundary] Global error handlers initialized');
    },

    /**
     * Log error to console and optionally to backend.
     */
    logError(error) {
        const errorInfo = {
            message: error.message || 'Unknown error',
            stack: error.stack,
            timestamp: new Date().toISOString(),
            url: window.location.href,
            userAgent: navigator.userAgent,
        };

        // Store in localStorage for debugging (last 10 errors)
        try {
            const errors = JSON.parse(localStorage.getItem('error_log') || '[]');
            errors.push(errorInfo);
            localStorage.setItem('error_log', JSON.stringify(errors.slice(-10)));
        } catch (e) {
            // localStorage might be full or disabled
        }
    },

    /**
     * Render a fallback UI for a failed section.
     */
    fallbackUI(title, message, retryFn = null) {
        return `
            <div class="error-fallback p-6 rounded-xl border border-red-200 bg-red-50 text-center">
                <i class="fas fa-exclamation-triangle text-red-500 text-3xl mb-3"></i>
                <h3 class="text-lg font-bold text-red-800 mb-2">${title}</h3>
                <p class="text-red-600 text-sm mb-4">${message}</p>
                ${retryFn ? `<button onclick="(${retryFn.toString()})()" class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition">Try Again</button>` : ''}
            </div>
        `;
    }
};

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => ErrorBoundary.init());
} else {
    ErrorBoundary.init();
}

window.ErrorBoundary = ErrorBoundary;
