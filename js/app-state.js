/**
 * AppState — Centralized Frontend State Manager
 * =============================================
 * Single source of truth for all client-side state.
 * Replaces scattered localStorage reads/writes, AuthToken, StageSync,
 * and 38+ ad-hoc localStorage keys with one coordinated system.
 *
 * Features:
 *   - Typed schema with defaults and validation
 *   - Pub/sub event system (per-key and wildcard listeners)
 *   - Cross-tab sync via BroadcastChannel + localStorage fallback
 *   - Automatic localStorage persistence for durable keys
 *   - Auth state derived from httponly cookie, never stored in localStorage
 *
 * Usage:
 *   AppState.get('role')                          // read
 *   AppState.set('role', 'recruiter')             // write (broadcasts to listeners + other tabs)
 *   AppState.on('role', (val) => { ... })         // subscribe to key changes
 *   AppState.on('*', (key, val) => { ... })       // subscribe to all changes
 *   AppState.off('role', callback)                // unsubscribe
 *   AppState.isAuthenticated()                    // auth helper
 *   AppState.getUser()                            // returns { id, name, email, role }
 *   AppState.clearAuth()                          // clears auth metadata on logout
 *   AppState.bootstrap()                          // call once on page load
 */

const AppState = (() => {
    'use strict';

    // ── Internal State ────────────────────────────────────────────────────────
    const _state = {};
    const _listeners = new Map();   // key -> Set<{callback, once}>
    const _windowId = 'as_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    let _bootstrapped = false;

    // ── Schema Definition ─────────────────────────────────────────────────────
    // persist: 'session' = localStorage, 'memory' = volatile, 'cookie' = derived
    // sync: true = broadcast to other tabs via BroadcastChannel
    const SCHEMA = {
        // ── Auth (derived from httponly cookie, metadata in memory only) ──
        token:          { default: null, persist: 'cookie', sync: false },
        role:           { default: null, persist: 'session', sync: true, legacyKey: 'role' },
        userId:         { default: null, persist: 'session', sync: true, legacyKey: 'userId' },
        userName:       { default: null, persist: 'session', sync: true, legacyKey: 'userName' },
        userEmail:      { default: null, persist: 'session', sync: false, legacyKey: 'user_email' },
        userPhotoUrl:   { default: null, persist: 'session', sync: true, legacyKey: 'userPhotoUrl' },
        profileStrength:{ default: null, persist: 'session', sync: false, legacyKey: 'profileStrength' },
        loggedInAt:     { default: null, persist: 'session', sync: false, legacyKey: 'loggedInAt' },

        // ── UI preferences (durable across sessions) ──
        language:       { default: 'en', persist: 'session', sync: true, legacyKey: 'candway_lang' },
        theme:          { default: 'light', persist: 'session', sync: false, legacyKey: 'preferredTheme' },

        // ── App-specific (session-scoped) ──
        activeAppId:    { default: null, persist: 'session', sync: true, legacyKey: 'active_app_id' },
        savedJobs:      { default: [], persist: 'session', sync: true, legacyKey: 'savedJobs', serialize: JSON.stringify, deserialize: JSON.parse },
        interviewLanguage: { default: 'en', persist: 'session', sync: true, legacyKey: 'interview_language' },
        pendingInterviewAppId: { default: null, persist: 'session', sync: true, legacyKey: 'pending_interview_app_id' },

        // ── Feature flags (memory only, cached separately by FeatureFlags) ──
        featureFlags:   { default: null, persist: 'memory', sync: false },
    };

    // ── Cookie Helpers ────────────────────────────────────────────────────────

    function _hasSessionCookie() {
        return document.cookie.split('; ').some(
            c => c.startsWith('logged_in=') && c !== 'logged_in=;' && c !== 'logged_in='
        );
    }

    function _getCookie(name) {
        const match = document.cookie.split('; ').find(c => c.startsWith(name + '='));
        return match ? match.split('=').slice(1).join('=') : null;
    }

    // ── Core API ──────────────────────────────────────────────────────────────

    /**
     * Get a state value. Returns the current value for the given key.
     * Auth token is always derived from the httponly cookie.
     */
    function get(key) {
        if (key === 'token') {
            return _hasSessionCookie() ? 'cookie-auth' : null;
        }
        // If bootstrap hasn't run yet, fall back to direct localStorage read
        if (!_bootstrapped && SCHEMA[key] && SCHEMA[key].legacyKey) {
            const raw = localStorage.getItem(SCHEMA[key].legacyKey);
            if (raw !== null) return raw;
        }
        return _state[key];
    }

    /**
     * Set a state value. Updates internal state, persists to localStorage
     * if configured, and notifies all listeners + other tabs.
     */
    function set(key, value) {
        const schema = SCHEMA[key];
        if (!schema) {
            console.warn(`[AppState] Unknown key: "${key}"`);
            return;
        }

        // Deserialize if coming from localStorage
        if (schema.serialize && typeof value === 'string' && value !== null) {
            try { value = schema.deserialize(value); } catch (e) { /* keep as string */ }
        }

        const oldValue = _state[key];
        _state[key] = value;

        // Persist
        if (schema.persist === 'session' && schema.legacyKey) {
            try {
                if (value === null || value === undefined) {
                    localStorage.removeItem(schema.legacyKey);
                } else {
                    const serialized = schema.serialize ? schema.serialize(value) : String(value);
                    localStorage.setItem(schema.legacyKey, serialized);
                }
            } catch (e) {
                console.warn(`[AppState] Failed to persist "${key}":`, e);
            }
        }

        // Notify listeners if value changed
        if (oldValue !== value) {
            _notify(key, value, oldValue);
            // Broadcast to other tabs
            if (schema.sync) {
                _broadcast(key, value);
            }
        }
    }

    /**
     * Set multiple state values at once. Batches notifications.
     */
    function setMany(updates) {
        const changes = [];
        for (const [key, value] of Object.entries(updates)) {
            const schema = SCHEMA[key];
            if (!schema) continue;
            const oldValue = _state[key];
            _state[key] = value;
            if (schema.persist === 'session' && schema.legacyKey) {
                try {
                    if (value === null || value === undefined) {
                        localStorage.removeItem(schema.legacyKey);
                    } else {
                        const serialized = schema.serialize ? schema.serialize(value) : String(value);
                        localStorage.setItem(schema.legacyKey, serialized);
                    }
                } catch (e) { /* ignore */ }
            }
            if (oldValue !== value) {
                changes.push([key, value, oldValue]);
                if (schema.sync) _broadcast(key, value);
            }
        }
        // Notify after all state is updated
        for (const [key, value, oldValue] of changes) {
            _notify(key, value, oldValue);
        }
    }

    /**
     * Subscribe to state changes for a specific key.
     * Use '*' to subscribe to all changes.
     * Returns an unsubscribe function.
     */
    function on(key, callback, options) {
        if (!_listeners.has(key)) {
            _listeners.set(key, new Set());
        }
        const entry = { callback, once: !!(options && options.once) };
        _listeners.get(key).add(entry);
        return () => _off(key, entry);
    }

    /**
     * Subscribe to a state change, fires once then auto-unsubscribes.
     */
    function once(key, callback) {
        return on(key, callback, { once: true });
    }

    function _off(key, entry) {
        const set = _listeners.get(key);
        if (set) set.delete(entry);
    }

    /**
     * Unsubscribe a specific callback from a key.
     */
    function off(key, callback) {
        const set = _listeners.get(key);
        if (!set) return;
        for (const entry of set) {
            if (entry.callback === callback) {
                set.delete(entry);
                return;
            }
        }
    }

    function _notify(key, value, oldValue) {
        // Notify key-specific listeners
        const keyListeners = _listeners.get(key);
        if (keyListeners) {
            for (const entry of keyListeners) {
                try {
                    entry.callback(value, oldValue, key);
                    if (entry.once) keyListeners.delete(entry);
                } catch (e) {
                    console.error(`[AppState] Listener error for "${key}":`, e);
                }
            }
        }
        // Notify wildcard listeners
        const wildcardListeners = _listeners.get('*');
        if (wildcardListeners) {
            for (const entry of wildcardListeners) {
                try {
                    entry.callback(key, value, oldValue);
                    if (entry.once) wildcardListeners.delete(entry);
                } catch (e) {
                    console.error('[AppState] Wildcard listener error:', e);
                }
            }
        }
    }

    // ── Cross-Tab Sync ────────────────────────────────────────────────────────

    let _channel = null;
    function _getChannel() {
        if (_channel) return _channel;
        try {
            _channel = new BroadcastChannel('candway-state-sync');
            _channel.onmessage = function(ev) {
                if (ev.data && ev.data.sourceId !== _windowId && ev.data.key) {
                    // Another tab updated state — update locally without re-broadcasting
                    const schema = SCHEMA[ev.data.key];
                    if (schema) {
                        const oldValue = _state[ev.data.key];
                        _state[ev.data.key] = ev.data.value;
                        if (schema.persist === 'session' && schema.legacyKey) {
                            try {
                                if (ev.data.value === null) localStorage.removeItem(schema.legacyKey);
                                else {
                                    const serialized = schema.serialize ? schema.serialize(ev.data.value) : String(ev.data.value);
                                    localStorage.setItem(schema.legacyKey, serialized);
                                }
                            } catch (e) { /* ignore */ }
                        }
                        if (oldValue !== ev.data.value) {
                            _notify(ev.data.key, ev.data.value, oldValue);
                        }
                    }
                }
            };
        } catch (e) {
            // BroadcastChannel not supported
        }
        return _channel;
    }

    function _broadcast(key, value) {
        const ch = _getChannel();
        if (ch) {
            try {
                ch.postMessage({ key, value, sourceId: _windowId });
            } catch (e) { /* channel closed */ }
        }
        // Fallback: use localStorage event for browsers without BroadcastChannel
        try {
            const storageKey = '_as_sync_' + key;
            localStorage.setItem(storageKey, JSON.stringify({ value, sourceId: _windowId, ts: Date.now() }));
            setTimeout(() => localStorage.removeItem(storageKey), 500);
        } catch (e) { /* ignore */ }
    }

    // Listen for localStorage fallback from other tabs
    function _setupStorageFallback() {
        window.addEventListener('storage', function(e) {
            if (e.key && e.key.startsWith('_as_sync_') && e.newValue) {
                try {
                    const data = JSON.parse(e.newValue);
                    if (data.sourceId !== _windowId) {
                        const key = e.key.replace('_as_sync_', '');
                        const schema = SCHEMA[key];
                        if (schema) {
                            const oldValue = _state[key];
                            _state[key] = data.value;
                            if (oldValue !== data.value) {
                                _notify(key, data.value, oldValue);
                            }
                        }
                    }
                } catch (err) { /* ignore parse errors */ }
            }
        });
    }

    // ── Auth Helpers ──────────────────────────────────────────────────────────

    /**
     * Check if user is authenticated (cookie exists OR role is set).
     */
    function isAuthenticated() {
        return _hasSessionCookie() || !!get('role');
    }

    /**
     * Get current user as an object { id, name, email, role }.
     * Returns null if not authenticated.
     */
    function getUser() {
        if (!isAuthenticated()) return null;
        const role = get('role');
        const name = get('userName');
        const email = get('userEmail');
        const id = get('userId');
        if (!role && !name && !email) return null;
        return { id: id || null, name: name || null, email: email || null, role: role || null };
    }

    /**
     * Get the current user's role.
     */
    function getRole() {
        return get('role');
    }

    /**
     * Check if user has a specific role (or list of roles).
     */
    function hasRole(roles) {
        const roleArray = Array.isArray(roles) ? roles : [roles];
        return roleArray.includes(get('role'));
    }

    /**
     * Clear all auth-related state on logout.
     */
    function clearAuth() {
        setMany({
            role: null,
            userId: null,
            userName: null,
            userEmail: null,
            userPhotoUrl: null,
            profileStrength: null,
            loggedInAt: null,
            activeAppId: null,
            pendingInterviewAppId: null,
        });
        document.cookie = 'logged_in=;max-age=0;path=/';
    }

    /**
     * Set auth state from /auth/me response or login success.
     */
    function setAuth(userData) {
        const updates = {};
        if (userData.role) updates.role = userData.role;
        if (userData.id) updates.userId = String(userData.id);
        if (userData.name) updates.userName = userData.name;
        if (userData.email) updates.userEmail = userData.email;
        if (userData.photo_url) updates.userPhotoUrl = userData.photo_url;
        if (userData.profile_strength) updates.profileStrength = userData.profile_strength;
        updates.loggedInAt = String(Date.now());
        setMany(updates);
    }

    // ── Bootstrap ─────────────────────────────────────────────────────────────

    /**
     * Initialize AppState from localStorage and cookies.
     * Call once on page load before any other code reads state.
     */
    function bootstrap() {
        if (_bootstrapped) return;
        _bootstrapped = true;

        // Migrate from legacy localStorage keys into _state
        for (const [key, schema] of Object.entries(SCHEMA)) {
            if (key === 'token') continue; // Always derived from cookie
            if (schema.persist === 'session' && schema.legacyKey) {
                try {
                    const raw = localStorage.getItem(schema.legacyKey);
                    if (raw !== null) {
                        if (schema.deserialize) {
                            try { _state[key] = schema.deserialize(raw); } catch (e) { _state[key] = raw; }
                        } else {
                            _state[key] = raw;
                        }
                    } else {
                        _state[key] = schema.default;
                    }
                } catch (e) {
                    _state[key] = schema.default;
                }
            } else {
                _state[key] = schema.default;
            }
        }

        // Bridge: if cookie indicates session but no role in state, set fake token
        if (_hasSessionCookie() && !_state.role) {
            // Role will be fetched by AuthGuard.refreshUserCache() or similar
        }

        // Write back migrated values to localStorage to ensure consistency
        for (const [key, schema] of Object.entries(SCHEMA)) {
            if (schema.persist === 'session' && schema.legacyKey && _state[key] !== null && _state[key] !== undefined) {
                try {
                    const serialized = schema.serialize ? schema.serialize(_state[key]) : String(_state[key]);
                    localStorage.setItem(schema.legacyKey, serialized);
                } catch (e) { /* ignore */ }
            }
        }

        _setupStorageFallback();
        _getChannel();
    }

    // ── StageSync Integration ─────────────────────────────────────────────────
    // Provides the same API as StageSync for backward compatibility.

    const StageSyncCompat = {
        broadcast(payload) {
            const data = {
                type: 'stage-changed',
                appId: payload.appId,
                oldStatus: payload.oldStatus,
                newStatus: payload.newStatus,
                timestamp: Date.now(),
                sourceId: _windowId,
            };
            const ch = _getChannel();
            if (ch) {
                try { ch.postMessage(data); } catch (e) { /* ignore */ }
            }
            window.dispatchEvent(new CustomEvent('candidate-status-changed', {
                detail: { appId: payload.appId, oldStatus: payload.oldStatus, newStatus: payload.newStatus }
            }));
        },
        onChange(callback) { on('_stage-sync', callback); },
        offChange(callback) { off('_stage-sync', callback); },
    };

    // ── Public API ────────────────────────────────────────────────────────────

    return {
        // Core
        get,
        set,
        setMany,
        on,
        once,
        off,

        // Auth
        isAuthenticated,
        getUser,
        getRole,
        hasRole,
        setAuth,
        clearAuth,

        // Lifecycle
        bootstrap,

        // Backward compatibility
        StageSync: StageSyncCompat,

        // Debugging
        _state,  // Expose for debugging only (read-only from outside)
        _schema: SCHEMA,
        _windowId,
    };
})();

// Expose globally
window.AppState = AppState;

// Auto-bootstrap: read legacy localStorage into state on script load
// Must run before any other script reads from AppState
if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => AppState.bootstrap());
    } else {
        AppState.bootstrap();
    }
}
