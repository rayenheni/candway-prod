/**
 * Auth Token Manager
 * Solves the stale token problem where localStorage.getItem('token') is read
 * at module load time and never updates after login/logout without page refresh.
 *
 * NOTE: If AppState is loaded, it provides window.AuthToken as a backward-
 * compatible wrapper. This file is kept for pages that load auth-token.js
 * directly without app-state.js.
 *
 * Usage:
 *   const token = AuthToken.get();
 *   AuthToken.set('new-token');
 *   AuthToken.clear();
 *   AuthToken.on('change', (newToken) => { ... });
 */

// Skip if AppState already provides AuthToken
if (window.AuthToken && window.AppState) { /* provided by app-auth.js */ } else {

const AuthToken = (() => {
    let currentToken = null;
    let currentRole = null;
    let currentUserId = null;
    const listeners = [];

    /**
     * Check if the logged_in session marker cookie exists.
     * The actual httponly access_token cookie is invisible to JS,
     * so we use a non-httponly companion marker set by the backend.
     */
    function hasSessionCookie() {
        return document.cookie.split('; ').some(c => c.startsWith('logged_in=') && c !== 'logged_in=;' && c !== 'logged_in=');
    }

    /**
     * Initialize from cookie existence check with localStorage fallback.
     * The backend sets a non-httponly `logged_in` cookie alongside the httponly
     * access_token.  As a safety net, the presence of a role in localStorage
     * (set by the login page) is also accepted as an auth indicator.
     */
    function init() {
        const hasMarker = hasSessionCookie() || !!localStorage.getItem('role');
        currentToken = hasMarker ? 'cookie-auth' : null;
        currentRole = localStorage.getItem('role');
        currentUserId = localStorage.getItem('userId');
        if (currentToken) {
            notifyListeners();
        }
    }

    /**
     * Get current token indicator.
     */
    function get() {
        return currentToken;
    }

    /**
     * Get current user role.
     */
    function getRole() {
        return currentRole;
    }

    /**
     * Get current user ID.
     */
    function getUserId() {
        return currentUserId;
    }

    /**
     * Check if user is authenticated via cookie or localStorage role marker.
     */
    function isAuthenticated() {
        return !!(hasSessionCookie() || localStorage.getItem('role'));
    }

    /**
     * Mark session as active (called after login/signup success).
     * Only stores non-sensitive metadata, never the JWT itself.
     */
    function set(token, role = null, userId = null) {
        currentToken = 'cookie-auth';
        currentRole = role;
        currentUserId = userId;
        if (role) localStorage.setItem('role', role);
        if (userId) localStorage.setItem('userId', String(userId));
        notifyListeners();
    }

    /**
     * Clear auth metadata from localStorage.
     * The httponly cookie is cleared by the backend /auth/logout endpoint.
     */
    function clear() {
        currentToken = null;
        currentRole = null;
        currentUserId = null;
        localStorage.removeItem('role');
        localStorage.removeItem('userId');
        notifyListeners();
    }

    /**
     * Subscribe to token changes.
     * @param {string} event - Event type ('change', 'login', 'logout')
     * @param {Function} callback - Callback function
     */
    function on(event, callback) {
        listeners.push({ event, callback });
    }

    /**
     * Notify all listeners of token change.
     */
    function notifyListeners() {
        listeners.forEach(({ event, callback }) => {
            try {
                if (event === 'change') {
                    callback(currentToken, currentRole, currentUserId);
                } else if (event === 'login' && currentToken) {
                    callback(currentToken, currentRole, currentUserId);
                } else if (event === 'logout' && !currentToken) {
                    callback();
                }
            } catch (e) {
                console.error('[Auth] Listener error:', e);
            }
        });
    }

    /**
     * Get auth headers for API requests.
     * Auth is via httponly cookie — no JWT in localStorage or headers.
     */
    function getHeaders() {
        return {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        };
    }

    // Initialize on load
    init();

    // Listen for storage events from other tabs
    window.addEventListener('storage', (e) => {
        if (e.key === 'token') {
            init();
        }
    });

    return {
        init,
        get,
        getRole,
        getUserId,
        isAuthenticated,
        set,
        clear,
        on,
        getHeaders,
    };
})();

window.AuthToken = AuthToken;

// NOTE: fetchAPI already handles Content-Type and CSRF natively in config.js.
// No wrapper needed here.

console.log('[Auth] Manager initialized');

} // end of AppState guard
