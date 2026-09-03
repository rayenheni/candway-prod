/**
 * Centralized Authentication Guard
 * Replaces duplicate token checks across 30+ HTML files
 *
 * NOTE: If app-auth.js is loaded, it already provides window.AuthGuard
 * backed by AppState. This file is kept for pages that load auth-guard.js
 * directly without app-auth.js.
 */

(function() {
    'use strict';

    // If AppAuth already provided AuthGuard, skip re-initialization
    if (window.AuthGuard && window.AppState) return;

    window.AuthGuard = {
        /**
         * Check session freshness — removes stale localStorage if >24h old
         */
        _checkSessionFreshness: function() {
            const loggedInAt = localStorage.getItem('loggedInAt');
            if (loggedInAt) {
                const elapsed = Date.now() - parseInt(loggedInAt, 10);
                const SESSION_TIMEOUT = 24 * 60 * 60 * 1000; // 24 hours
                if (elapsed > SESSION_TIMEOUT) {
                    localStorage.removeItem('token');
                    localStorage.removeItem('role');
                    localStorage.removeItem('userName');
                    localStorage.removeItem('userId');
                    localStorage.removeItem('loggedInAt');
                    localStorage.removeItem('user');
                    localStorage.removeItem('userPhotoUrl');
                    localStorage.removeItem('profileStrength');
                    localStorage.removeItem('user_email');
                    return false;
                }
            }
            return !!localStorage.getItem('token') || document.cookie.includes('logged_in=');
        },

        /**
         * Check if user is authenticated, redirect to login if not
         * @param {string} redirectPath - Path to redirect after login (default: current path)
         */
        requireAuth: function(redirectPath) {
            if (!this._checkSessionFreshness()) {
                redirectPath = redirectPath || window.location.pathname;
                const p = window.location.pathname;
                let loginBase = '/login';
                if (p.includes('/recruiter')) loginBase = '/login/recruiter';
                else if (p.includes('/admin')) loginBase = '/login/admin';
                else if (p.includes('/mentor')) loginBase = '/login/mentor';
                window.location.href = loginBase + '?session=expired&redirect=' + encodeURIComponent(redirectPath);
                return false;
            }
            const hasCookie = document.cookie.split('; ').some(c => c.startsWith('logged_in=') && c !== 'logged_in=;' && c !== 'logged_in=');
            const hasRole = !!localStorage.getItem('role');
            if (!hasCookie && !hasRole) {
                redirectPath = redirectPath || window.location.pathname;
                const p = window.location.pathname;
                let loginBase = '/login';
                if (p.includes('/recruiter')) loginBase = '/login/recruiter';
                else if (p.includes('/admin')) loginBase = '/login/admin';
                else if (p.includes('/mentor')) loginBase = '/login/mentor';
                window.location.href = loginBase + '?redirect=' + encodeURIComponent(redirectPath);
                return false;
            }
            return true;
        },

        /**
         * Check if user has a specific role
         * @param {string|string[]} roles - Required role(s)
         * @param {string} redirectPath - Path to redirect if unauthorized
         */
        requireRole: function(roles, redirectPath) {
            if (!this.requireAuth(redirectPath)) return false;

            const roleArray = Array.isArray(roles) ? roles : [roles];
            let userRole = null;

            // Try localStorage 'user' JSON object first
            const userStr = localStorage.getItem('user');
            if (userStr) {
                try {
                    const user = JSON.parse(userStr);
                    userRole = user.role;
                } catch (e) {
                    console.error('[AuthGuard] Failed to parse user data:', e);
                }
            }

            // Fall back to direct 'role' key (used by login pages)
            if (!userRole) {
                userRole = localStorage.getItem('role');
            }

            if (!userRole || !roleArray.includes(userRole)) {
                console.warn('[AuthGuard] Unauthorized role:', userRole, 'Required:', roleArray);
                window.location.href = redirectPath || '/login?error=unauthorized';
                return false;
            }
            return true;
        },

        /**
         * Check if user is a candidate
         */
        requireCandidate: function() {
            return this.requireRole(['candidate', 'admin']);
        },

        /**
         * Check if user is a recruiter
         */
        requireRecruiter: function() {
            return this.requireRole(['recruiter', 'admin']);
        },

        /**
         * Check if user is a mentor
         */
        requireMentor: function() {
            return this.requireRole(['mentor', 'admin']);
        },

        /**
         * Check if user is an admin
         * NOTE: "super_admin" is NOT a valid role string.
         * Super admin status is determined by the is_super_admin boolean column.
         * All authorization decisions are enforced server-side via dependencies.py.
         * This client-side guard is a UX convenience only — the real trust boundary is the API.
         */
        requireAdmin: function() {
            return this.requireRole(['admin']);
        },

        /**
         * Get current user data
         */
        getCurrentUser: function() {
            const userStr = localStorage.getItem('user');
            if (userStr) {
                try {
                    return JSON.parse(userStr);
                } catch (e) {
                    return null;
                }
            }
            // Fall back to direct localStorage keys used by login pages
            const role = localStorage.getItem('role');
            const name = localStorage.getItem('userName');
            const email = localStorage.getItem('user_email');
            const id = localStorage.getItem('userId');
            if (role || name || email) {
                return { role, name, email, id };
            }
            return null;
        },

        /**
         * Get current user role
         */
        getRole: function() {
            const user = this.getCurrentUser();
            return user ? user.role : null;
        },

        /**
         * Validate session by calling /auth/me.
         * Redirects to login if session is expired/invalid.
         */
        checkSession: async function() {
            try {
                const resp = await fetch('/api/v1/auth/me', { credentials: 'same-origin' });
                if (resp.ok) {
                    localStorage.setItem('loggedInAt', String(Date.now()));
                    return true;
                }
            } catch (_e) { /* session check failed */ }
            if (window.location.pathname.startsWith('/login')) return false;
            const role = localStorage.getItem('role');
            const loginMap = { candidate: '/login', recruiter: '/login/recruiter', admin: '/login/admin', mentor: '/login/mentor' };
            window.location.href = (loginMap[role] || '/login') + '?session=expired&redirect=' + encodeURIComponent(window.location.pathname);
            return false;
        },

    /**
     * Refresh the user cache from the server on every page load
     * to prevent stale role/user data in localStorage.
     */
    refreshUserCache: async function() {
        try {
            const resp = await fetch('/api/v1/auth/me', { credentials: 'same-origin' });
            if (resp.ok) {
                const data = await resp.json();
                if (data.role) localStorage.setItem('role', data.role);
                if (data.name) localStorage.setItem('userName', data.name);
                if (data.id) localStorage.setItem('userId', data.id.toString());
            }
        } catch (e) {
            // Non-critical; stale cache is acceptable fallback
        }
    },

    /**
     * Logout user and redirect to login
     */
    logout: async function() {
            try {
                await fetch('/api/v1/auth/logout', { method: 'POST', credentials: 'same-origin' });
            } catch (e) {
                console.warn('[AuthGuard] Logout API call failed:', e);
            }
            const role = localStorage.getItem('role');
            localStorage.removeItem('token');
            localStorage.removeItem('user');
            localStorage.removeItem('userName');
            localStorage.removeItem('role');
            localStorage.removeItem('userPhotoUrl');
            localStorage.removeItem('profileStrength');
            localStorage.removeItem('userId');
            localStorage.removeItem('user_email');
            document.cookie = 'logged_in=;max-age=0;path=/';
            const loginMap = { candidate: '/login', recruiter: '/login/recruiter', admin: '/login/admin', mentor: '/login/mentor' };
            window.location.href = loginMap[role] || '/login';
        }
    };

    // Legacy localStorage token bridging is now handled by AppState.bootstrap().
    // Pages loading auth-guard.js without app-state.js still need this bridge:
    if (document.cookie.includes('logged_in=') && !localStorage.getItem('token')) {
        localStorage.setItem('token', 'cookie-auth');
    }

    // Synchronous guard at script parse time — prevents flash of admin content
    if (window.location.pathname.startsWith('/admin/') && !document.cookie.includes('logged_in=')) {
        window.location.href = '/login/admin';
    }

    /**
     * Auto-initialize auth guard on DOMContentLoaded
     * Usage in HTML: <script>AuthGuard.requireCandidate();</script>
     */
    document.addEventListener('DOMContentLoaded', function() {
        const isAuthPage = window.location.pathname.startsWith('/candidate/')
            || window.location.pathname.startsWith('/recruiter/')
            || window.location.pathname.startsWith('/mentor/')
            || window.location.pathname.startsWith('/admin/');
        if (isAuthPage) {
            AuthGuard.requireAuth();
            AuthGuard.checkSession();
            AuthGuard.refreshUserCache();
            if (window.location.pathname.startsWith('/candidate/')) {
                AuthGuard.requireCandidate();
            } else if (window.location.pathname.startsWith('/recruiter/')) {
                AuthGuard.requireRecruiter();
            } else if (window.location.pathname.startsWith('/mentor/')) {
                AuthGuard.requireMentor();
            } else if (window.location.pathname.startsWith('/admin/')) {
                AuthGuard.requireAdmin();
            }
        }
    });

})();
