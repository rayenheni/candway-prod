/**
 * Feature Flags Manager
 * ======================
 * Client-side feature flag system with server sync.
 * Supports global flags, per-user overrides, and localStorage fallback.
 */

const FeatureFlags = (() => {
    const STORAGE_KEY = 'candway_feature_flags';
    const CACHE_DURATION = 5 * 60 * 1000; // 5 minutes
    let flags = {};
    let lastFetch = 0;

    const DEFAULT_FLAGS = {
        recruiter_enhancements: true,
        recruiter_onboarding_tour: true,
        recruiter_help_center: true,
        recruiter_tooltips: true,
        ai_debrief: true,
        automation_rules: true,
        scorecards: true,
        webhook_integrations: true,
    };

    function loadFromCache() {
        try {
            const cached = localStorage.getItem(STORAGE_KEY);
            if (cached) {
                const data = JSON.parse(cached);
                if (Date.now() - data.timestamp < CACHE_DURATION) {
                    flags = data.flags;
                    lastFetch = data.timestamp;
                    return true;
                }
            }
        } catch (e) {
            // Ignore cache errors
        }
        return false;
    }

    function saveToCache() {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify({
                flags,
                timestamp: Date.now()
            }));
        } catch (e) {
            // Ignore storage errors
        }
    }

    async function fetchFromServer() {
        try {
            const csrfCookie = document.cookie.split('; ').find(c => c.startsWith('csrf_token='));
            const csrfToken = csrfCookie ? csrfCookie.split('=')[1] : '';

            const resp = await fetch('/api/v1/feature-flags/config', {
                credentials: 'same-origin',
                headers: {
                    'X-CSRF-Token': csrfToken,
                    'Content-Type': 'application/json'
                }
            });

            if (resp.ok) {
                flags = await resp.json();
                lastFetch = Date.now();
                saveToCache();
            }
        } catch (e) {
            console.warn('[FeatureFlags] Server fetch failed, using cache/defaults');
        }
    }

    async function init() {
        if (!loadFromCache()) {
            flags = { ...DEFAULT_FLAGS };
        }
        await fetchFromServer();
    }

    function isEnabled(flagKey) {
        if (flags.hasOwnProperty(flagKey)) {
            return flags[flagKey] === true;
        }
        return DEFAULT_FLAGS[flagKey] || false;
    }

    function getAll() {
        return { ...DEFAULT_FLAGS, ...flags };
    }

    function setLocal(flagKey, value) {
        flags[flagKey] = value;
        saveToCache();
    }

    function reset() {
        localStorage.removeItem(STORAGE_KEY);
        flags = { ...DEFAULT_FLAGS };
        lastFetch = 0;
    }

    return {
        init,
        isEnabled,
        getAll,
        setLocal,
        reset,
    };
})();

// Expose globally for cross-bundle access
window.FeatureFlags = FeatureFlags;

// Auto-init on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => FeatureFlags.init());
} else {
    FeatureFlags.init();
}
