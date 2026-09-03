/**
 * AppAuth — Unified Authentication Module
 * ========================================
 * Replaces AuthGuard + AuthToken + localStorage token bridging.
 * Uses AppState as the single source of truth. Auth tokens are always
 * httponly cookies — this module manages metadata only (role, userId, name).
 *
 * Usage:
 *   AppAuth.requireAuth()          // sync guard — redirects if unauthenticated
 *   AppAuth.requireRole('admin')   // sync guard — redirects if wrong role
 *   AppAuth.checkSession()         // async — validates session with server
 *   AppAuth.refreshUser()          // async — fetches /auth/me and updates AppState
 *   AppAuth.logout()               // async — clears session and redirects
 *   AppAuth.getCurrentUser()       // returns user object from AppState
 */

const AppAuth = (() => {
    'use strict';

    const SESSION_TIMEOUT = 24 * 60 * 60 * 1000; // 24 hours

    // ── Role → Login URL mapping ─────────────────────────────────────────────
    const LOGIN_MAP = {
        candidate: '/login',
        recruiter: '/login/recruiter',
        admin:     '/login/admin',
        mentor:    '/login/mentor',
    };

    function _getLoginBase() {
        const p = window.location.pathname;
        if (p.includes('/recruiter')) return LOGIN_MAP.recruiter;
        if (p.includes('/admin'))     return LOGIN_MAP.admin;
        if (p.includes('/mentor'))    return LOGIN_MAP.mentor;
        return LOGIN_MAP.candidate;
    }

    // ── Session Freshness ─────────────────────────────────────────────────────

    function _isSessionFresh() {
        const loggedInAt = AppState.get('loggedInAt');
        if (loggedInAt) {
            const elapsed = Date.now() - parseInt(loggedInAt, 10);
            if (elapsed > SESSION_TIMEOUT) {
                AppState.clearAuth();
                return false;
            }
        }
        return AppState.isAuthenticated();
    }

    // ── Core Auth API ─────────────────────────────────────────────────────────

    /**
     * Synchronous guard — checks if user is authenticated.
     * Redirects to login if not. Returns false if redirect happened.
     */
    function requireAuth(redirectPath) {
        if (!_isSessionFresh()) {
            redirectPath = redirectPath || window.location.pathname;
            window.location.href = _getLoginBase() + '?session=expired&redirect=' + encodeURIComponent(redirectPath);
            return false;
        }
        const hasCookie = document.cookie.split('; ').some(
            c => c.startsWith('logged_in=') && c !== 'logged_in=;' && c !== 'logged_in='
        );
        const hasRole = !!AppState.get('role');
        if (!hasCookie && !hasRole) {
            redirectPath = redirectPath || window.location.pathname;
            window.location.href = _getLoginBase() + '?redirect=' + encodeURIComponent(redirectPath);
            return false;
        }
        return true;
    }

    /**
     * Synchronous guard — checks if user has the required role(s).
     * Calls requireAuth first. Redirects if unauthorized.
     */
    function requireRole(roles, redirectPath) {
        if (!requireAuth(redirectPath)) return false;
        const roleArray = Array.isArray(roles) ? roles : [roles];
        const userRole = AppState.getRole();
        if (!userRole || !roleArray.includes(userRole)) {
            console.warn('[AppAuth] Unauthorized role:', userRole, 'Required:', roleArray);
            window.location.href = redirectPath || '/login?error=unauthorized';
            return false;
        }
        return true;
    }

    function requireCandidate() { return requireRole(['candidate', 'admin']); }
    function requireRecruiter() { return requireRole(['recruiter', 'admin']); }
    function requireMentor()    { return requireRole(['mentor', 'admin']); }
    function requireAdmin()     { return requireRole(['admin']); }

    // ── Async Session Management ──────────────────────────────────────────────

    /**
     * Validate session by calling /auth/me.
     * Redirects to login if session is expired/invalid.
     */
    async function checkSession() {
        try {
            const resp = await fetch('/api/v1/auth/me', { credentials: 'same-origin' });
            if (resp.ok) {
                AppState.set('loggedInAt', String(Date.now()));
                return true;
            }
        } catch (_e) { /* session check failed */ }
        if (window.location.pathname.startsWith('/login')) return false;
        const role = AppState.getRole();
        window.location.href = (LOGIN_MAP[role] || '/login') + '?session=expired&redirect=' + encodeURIComponent(window.location.pathname);
        return false;
    }

    /**
     * Fetch user data from /auth/me and update AppState.
     * Called on every page load to prevent stale role/user data.
     */
    async function refreshUser() {
        try {
            const resp = await fetch('/api/v1/auth/me', { credentials: 'same-origin' });
            if (resp.ok) {
                const data = await resp.json();
                AppState.setAuth(data);
            }
        } catch (e) {
            // Non-critical; stale cache is acceptable fallback
        }
    }

    /**
     * Logout user — clears auth state and redirects to login.
     */
    async function logout() {
        try {
            await fetch('/api/v1/auth/logout', { method: 'POST', credentials: 'same-origin' });
        } catch (e) {
            console.warn('[AppAuth] Logout API call failed:', e);
        }
        const role = AppState.getRole();
        AppState.clearAuth();
        window.location.href = LOGIN_MAP[role] || '/login';
    }

    // ── Convenience ───────────────────────────────────────────────────────────

    /**
     * Get current user from AppState.
     */
    function getCurrentUser() {
        return AppState.getUser();
    }

    /**
     * Get current user role.
     */
    function getRole() {
        return AppState.getRole();
    }

    /**
     * Check if user is authenticated.
     */
    function isAuthenticated() {
        return AppState.isAuthenticated();
    }

    // ── Auto-Init ─────────────────────────────────────────────────────────────

    function _autoInit() {
        // Synchronous admin page guard (prevents flash of admin content)
        if (window.location.pathname.startsWith('/admin/') && !document.cookie.includes('logged_in=')) {
            window.location.href = '/login/admin';
            return;
        }

        // Auto-run auth guards on protected pages
        const isAuthPage = window.location.pathname.startsWith('/candidate/')
            || window.location.pathname.startsWith('/recruiter/')
            || window.location.pathname.startsWith('/mentor/')
            || window.location.pathname.startsWith('/admin/');

        if (isAuthPage) {
            requireAuth();
            checkSession();
            refreshUser();
            if (window.location.pathname.startsWith('/candidate/'))      requireCandidate();
            else if (window.location.pathname.startsWith('/recruiter/')) requireRecruiter();
            else if (window.location.pathname.startsWith('/mentor/'))    requireMentor();
            else if (window.location.pathname.startsWith('/admin/'))     requireAdmin();
        }
    }

    // Run on DOMContentLoaded to preserve current behavior
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', _autoInit);
    } else {
        _autoInit();
    }

    return {
        requireAuth,
        requireRole,
        requireCandidate,
        requireRecruiter,
        requireMentor,
        requireAdmin,
        checkSession,
        refreshUser,
        logout,
        getCurrentUser,
        getRole,
        isAuthenticated,
    };
})();

window.AppAuth = AppAuth;

// ── Backward Compatibility ───────────────────────────────────────────────────
// Keep AuthGuard and AuthToken as thin wrappers around AppAuth/AppState
// so existing page scripts don't break during migration.
window.AuthGuard = {
    requireAuth: (p) => AppAuth.requireAuth(p),
    requireRole: (roles, p) => AppAuth.requireRole(roles, p),
    requireCandidate: () => AppAuth.requireCandidate(),
    requireRecruiter: () => AppAuth.requireRecruiter(),
    requireMentor: () => AppAuth.requireMentor(),
    requireAdmin: () => AppAuth.requireAdmin(),
    checkSession: () => AppAuth.checkSession(),
    refreshUserCache: () => AppAuth.refreshUser(),
    logout: () => AppAuth.logout(),
    getCurrentUser: () => AppAuth.getCurrentUser(),
    getRole: () => AppAuth.getRole(),
};

window.AuthToken = {
    get: () => AppState.get('token'),
    getRole: () => AppState.getRole(),
    getUserId: () => AppState.get('userId'),
    isAuthenticated: () => AppState.isAuthenticated(),
    set: (token, role, userId) => AppState.setAuth({ role, id: userId }),
    clear: () => AppState.clearAuth(),
    on: (event, callback) => {
        if (event === 'change' || event === 'login') {
            return AppState.on('role', (val) => val ? callback(AppState.get('token'), val, AppState.get('userId')) : null);
        }
        if (event === 'logout') {
            return AppState.on('role', (val) => !val ? callback() : null);
        }
    },
    getHeaders: () => ({ 'Content-Type': 'application/json', 'Accept': 'application/json' }),
    init: () => {},
};
