const CONFIG = {
    // API Versioning Prefix
    API_PREFIX: "/api/v1",

    API_BASE_URL: (window.location.protocol === 'file:') ? "http://127.0.0.1:8083" : window.location.origin,
    APP_NAME: "Candway Intelligence",
    DEBUG: false  // CRIT-01: Debug mode disabled for production. Set to true for local dev only.
};

// Production log helper — silences console.log when DEBUG is off.
const _log = CONFIG.DEBUG ? console.log.bind(console) : function(){};
// Expose globally — esbuild wraps each file in its own scope, so _log
// must be on window for other files (constants.js, accessibility.js, etc.)
// to access it.
window._log = _log;

// Simple in-memory cache for GET responses within the same page navigation.
// Pages that navigate away lose this cache, but re-fetches within the same page are instant.
const _apiCache = new Map();
const CACHE_TTL_MS = 30000; // 30 seconds
const CACHE_MAX_SIZE = 100; // LRU eviction limit
function _cacheSet(key, value) {
    if (_apiCache.size >= CACHE_MAX_SIZE) {
        const oldest = _apiCache.keys().next().value;
        if (oldest !== undefined) _apiCache.delete(oldest);
    }
    _apiCache.set(key, value);
}

// Dedup singleton for /auth/me — prevents N concurrent calls; caches for 5s
let _authMePromise = null;
let _authMeCache = null;
let _authMeCachedAt = 0;
const AUTH_ME_TTL_MS = 5000;
async function getAuthMe() {
    if (_authMeCache && Date.now() - _authMeCachedAt < AUTH_ME_TTL_MS) return _authMeCache;
    if (_authMePromise) return _authMePromise;
    _authMePromise = (async () => {
        try {
            const data = await fetch('/api/v1/auth/me', { credentials: 'same-origin' });
            if (!data.ok) throw new Error('Not authenticated');
            const user = await data.json();
            _authMeCache = user;
            _authMeCachedAt = Date.now();
            return user;
        } finally {
            _authMePromise = null;
        }
    })();
    return _authMePromise;
}
function clearAuthMeCache() { _authMeCache = null; _authMeCachedAt = 0; }

// ── Cache Invalidation ──────────────────────────────────────────────────────
// Maps mutation endpoint patterns to cache prefixes that must be invalidated.
// Every entry means: "a mutation matching the key pattern stales all cached GET
// responses whose endpoint starts with any value in the array."
const _MUTATION_CACHE_MAP = [
    // Application/Candidate mutations stale lists, detail, dashboards, analytics
    { match: '/recruiter/applications', invalidate: ['/recruiter/applications', '/recruiter/candidates', '/recruiter/dashboard', '/recruiter/analytics', '/recruiter/collaboration', '/recruiter/enhancements/analytics'] },
    { match: '/recruiter/candidates', invalidate: ['/recruiter/applications', '/recruiter/candidates', '/recruiter/dashboard', '/recruiter/analytics', '/recruiter/collaboration'] },

    // Interview mutations stale interview lists + related app data
    { match: '/recruiter/interviews', invalidate: ['/recruiter/interviews', '/recruiter/applications', '/recruiter/candidates'] },

    // Job mutations stale job lists + dashboard
    { match: '/recruiter/jobs', invalidate: ['/recruiter/jobs', '/recruiter/dashboard', '/recruiter/campaigns'] },

    // Campaign mutations stale campaign lists + apps + dashboard
    { match: '/recruiter/campaigns', invalidate: ['/recruiter/campaigns', '/recruiter/applications', '/recruiter/dashboard'] },

    // Offer & Background-check mutations stale offers + apps + dashboard
    { match: '/recruiter/offers', invalidate: ['/recruiter/offers', '/recruiter/background-checks', '/recruiter/applications', '/recruiter/dashboard'] },
    { match: '/recruiter/background-checks', invalidate: ['/recruiter/background-checks', '/recruiter/offers', '/recruiter/applications'] },

    // Team mutations stale team list
    { match: '/recruiter/collaboration/team', invalidate: ['/recruiter/collaboration/team'] },

    // Email templates, settings, automation
    { match: '/recruiter/templates', invalidate: ['/recruiter/templates', '/recruiter/email-settings'] },
    { match: '/recruiter/email-settings', invalidate: ['/recruiter/email-settings', '/recruiter/settings'] },
    { match: '/recruiter/settings', invalidate: ['/recruiter/settings'] },
    { match: '/recruiter/automation-settings', invalidate: ['/recruiter/enhancements'] },

    // Stage management, automation rules
    { match: '/recruiter/enhancements/stages', invalidate: ['/recruiter/enhancements/stages'] },
    { match: '/recruiter/enhancements/automation-rules', invalidate: ['/recruiter/enhancements/automation-rules'] },

    // Scorecards, webhooks
    { match: '/recruiter/enhancements/scorecards', invalidate: ['/recruiter/enhancements/scorecards', '/recruiter/applications'] },
    { match: '/recruiter/enhancements/webhooks', invalidate: ['/recruiter/enhancements/webhooks'] },

    // Skill trees & rubrics
    { match: '/recruiter/skill-trees', invalidate: ['/recruiter/skill-trees'] },
    { match: '/rubric/', invalidate: ['/rubric'] },

    // Messages & notifications
    { match: '/messages/', invalidate: ['/messages'] },
    { match: '/notifications/', invalidate: ['/notifications'] },

    // Reports
    { match: '/recruiter/reports', invalidate: ['/recruiter/reports'] },

    // Re-engagement
    { match: '/recruiter/reengagement', invalidate: ['/recruiter/reengagement'] },

    // Chatbot leads
    { match: '/chatbot/leads', invalidate: ['/chatbot/leads'] },

    // EEO submissions stale EEO dashboards
    { match: '/candidate/eeo', invalidate: ['/recruiter/eeo'] },

    // Subscription changes stale billing
    { match: '/recruiter/subscription', invalidate: ['/recruiter/subscription'] },
];

function _cacheKeyMatchesPrefix(cacheKey, prefix) {
    // cacheKey format: "auth:/endpoint/path:GET" or "anon:/endpoint/path:GET"
    const colonIdx = cacheKey.indexOf(':');
    if (colonIdx === -1) return false;
    const endpoint = cacheKey.substring(colonIdx + 1, cacheKey.lastIndexOf(':'));
    return endpoint.startsWith(prefix);
}

function _invalidateCache(mode, pattern) {
    if (mode === 'all') {
        _apiCache.clear();
        if (CONFIG.DEBUG) _log('[Cache] Cleared all entries');
        return;
    }
    const patterns = [];
    if (mode === 'exact') {
        const loggedIn = document.cookie.includes('logged_in=') ? 'auth' : 'anon';
        patterns.push(`${loggedIn}:${pattern}`);
    } else if (mode === 'prefix') {
        const loggedIn = document.cookie.includes('logged_in=') ? 'auth' : 'anon';
        for (const key of _apiCache.keys()) {
            if (_cacheKeyMatchesPrefix(key, pattern)) {
                _apiCache.delete(key);
            }
        }
        if (CONFIG.DEBUG) _log(`[Cache] Invalidated prefix "${pattern}"`);
        return;
    }
    if (patterns.length > 0) {
        patterns.forEach(p => _apiCache.delete(p));
    }
}

function _invalidateForMutation(endpoint) {
    let invalidationCount = 0;
    for (const rule of _MUTATION_CACHE_MAP) {
        if (endpoint.startsWith(rule.match)) {
            for (const prefix of rule.invalidate) {
                const before = _apiCache.size;
                _invalidateCache('prefix', prefix);
                invalidationCount += (before - _apiCache.size);
            }
        }
    }
    // Also clear by exact endpoint to catch cached GET for the mutated resource
    _invalidateCache('exact', endpoint);
    // Broadcast a cross-page invalidation event so other tabs clear stale caches
    window.dispatchEvent(new CustomEvent('candway-cache-invalidate', { detail: { endpoint } }));
    if (CONFIG.DEBUG && invalidationCount > 0) _log(`[Cache] Invalidated ${invalidationCount} entries for mutation "${endpoint}"`);
}

function _getCacheKey(endpoint, options) {
    // Only cache GET requests
    if (options.method && options.method.toUpperCase() !== 'GET') return null;
    if (!options.method && options.body) return null; // POST without explicit method
    // Use cookie auth state instead of localStorage token to avoid leaking auth into cache keys
    const loggedIn = document.cookie.includes('logged_in=') ? 'auth' : 'anon';
    return `${loggedIn}:${endpoint}:${options.method || 'GET'}`;
}

// GLOBAL API HELPER - Enhanced with timeout, retry, in-memory caching, and better error handling
window.fetchAPI = async (endpoint, options = {}) => {
    let url = endpoint.startsWith('http') ? endpoint : `${CONFIG.API_BASE_URL}${CONFIG.API_PREFIX}${endpoint.startsWith('/') ? '' : '/'}${endpoint}`;

    // Prevent path traversal attacks
    if (endpoint.includes('..')) throw new Error('Invalid endpoint path');

    // Configuration
    const timeout = options.timeout || 30000; // 30 seconds default
    const maxRetries = options.retry !== undefined ? options.retry : 0; // No retry by default
    const retryDelay = options.retryDelay || 1000; // 1 second between retries

    // Check in-memory cache for GET requests to avoid redundant server calls
    const cacheKey = _getCacheKey(endpoint, options);
    if (cacheKey && _apiCache.has(cacheKey)) {
        const cached = _apiCache.get(cacheKey);
        if (Date.now() - cached.timestamp < CACHE_TTL_MS) {
            return cached.data;
        }
        _apiCache.delete(cacheKey); // Expired
    }

    // Prepare headers
    const headers = { ...options.headers };

    // Set default Content-Type to JSON only if body is not FormData and not already set
    if (!(options.body instanceof FormData) && !headers['Content-Type']) {
        headers['Content-Type'] = 'application/json';
    }

    // Add CSRF token from cookie for state-changing requests
    const method = (options.method || 'GET').toUpperCase();
    if (method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS') {
        if (!headers['X-CSRF-Token']) {  // Only add if csrf.js hasn't already set it
            const csrfCookie = document.cookie.split('; ').find(c => c.startsWith('csrf_token='));
            if (csrfCookie) {
                headers['X-CSRF-Token'] = csrfCookie.split('=')[1];
            }
        }
    }

    // Auth is handled via httponly cookie (credentials: 'same-origin').
    // No JWT is stored in localStorage — this prevents XSS token theft.

    // Retry logic
    let lastError;
    for (let attempt = 0; attempt <= maxRetries; attempt++) {
        // Create abort controller for timeout (Fresh for each attempt)
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeout);

        try {
            const response = await fetch(url, {
                ...options,
                headers,
                credentials: 'same-origin',
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            // Handle non-JSON responses gracefully
            let data;
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                data = await response.json();
            } else {
                // For non-JSON responses, return text
                const text = await response.text();
                data = { message: text };
            }

            if (response.status === 401 && !endpoint.includes('/auth/') && !window.location.pathname.startsWith('/login')) {
                try {
                    const refreshResp = await fetch(`${CONFIG.API_BASE_URL}${CONFIG.API_PREFIX}/auth/refresh`, {
                        method: 'POST', credentials: 'same-origin'
                    });
                    if (refreshResp.ok) {
                        return await window.fetchAPI(endpoint, options);
                    }
                } catch (_e) { /* refresh failed, redirect to login */ }
                const role = (window.AppState ? window.AppState.getRole() : null)
                    || (() => {
                        const p = window.location.pathname;
                        if (p.includes('/admin')) return 'admin';
                        if (p.includes('/recruiter')) return 'recruiter';
                        if (p.includes('/candidate')) return 'candidate';
                        if (p.includes('/mentor')) return 'mentor';
                        return null;
                    })();
                const loginMap = { candidate: '/login', recruiter: '/login/recruiter', admin: '/login/admin', mentor: '/login/mentor' };
                const loginUrl = loginMap[role] || '/login';
                if (window.AppState) { AppState.clearAuth(); } else { localStorage.clear(); }
                window.location.href = loginUrl + '?redirect=' + encodeURIComponent(window.location.pathname + window.location.search);
                return;
            }

            if (!response.ok) {
                // Handle standardized error response
                const errorMsg = typeof data.detail === 'string' ? data.detail : 
                        (data.message || `Request failed with status ${response.status}`);

                throw new Error(errorMsg);
            }

            // Cache GET responses in memory to avoid redundant server calls
            if (cacheKey && response.ok) {
                _cacheSet(cacheKey, { data, timestamp: Date.now() });
            }

            // After any successful mutation, invalidate stale cached GET responses
            if (method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS') {
                _invalidateForMutation(endpoint);
            }

            return data;

        } catch (error) {
            clearTimeout(timeoutId);
            lastError = error;

            // Handle timeout
            if (error.name === 'AbortError') {
                throw new Error(`Request timed out after ${timeout}ms. Please check your connection and try again.`);
            }

            // Handle network errors
            if (error instanceof TypeError) {
                lastError = new Error('Network error. Please check your internet connection.');
            }

            // Retry logic
            if (attempt < maxRetries) {
                if (CONFIG.DEBUG) _log(`Retry attempt ${attempt + 1}/${maxRetries} for ${endpoint}`);
                await new Promise(resolve => setTimeout(resolve, retryDelay));
                continue;
            }

            // Log error in debug mode
            if (CONFIG.DEBUG) console.error(`API Error [${endpoint}]:`, error);
            throw lastError;
        }
    }

    throw lastError;
};

// ── Cross-Tab Cache Invalidation ─────────────────────────────────────────────
// Ensure window ID even if cross-page-sync.js hasn't loaded yet
if (!window._candwayWindowId) {
    window._candwayWindowId = 'cfg_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}
(function() {
    var ch = null;
    try { ch = new BroadcastChannel('candway-cache-sync'); } catch (e) { /* not supported */ }
    if (!ch) return;
    // Listen for mutations performed in OTHER tabs
    ch.onmessage = function(ev) {
        if (ev.data && ev.data.type === 'cache-invalidate' && ev.data.endpoint && ev.data.sourceId !== window._candwayWindowId) {
            _invalidateForMutation(ev.data.endpoint);
        }
    };
    // When THIS tab performs a mutation, tell other tabs
    window.addEventListener('candway-cache-invalidate', function(ev) {
        if (ev.detail && ev.detail.endpoint) {
            try {
                ch.postMessage({ type: 'cache-invalidate', endpoint: ev.detail.endpoint, sourceId: window._candwayWindowId });
            } catch (e) { /* channel may be closed */ }
        }
    });
})();

window.CONFIG = CONFIG;
