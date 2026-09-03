/**
 * CSRF Protection Helper
 * Automatically handles CSRF tokens for all forms and AJAX requests
 */

// Get CSRF token from cookie
function getCSRFToken() {
    const name = 'csrf_token=';
    let decodedCookie;
    try {
        decodedCookie = decodeURIComponent(document.cookie);
    } catch (e) {
        console.warn('CSRF: Failed to decode cookie, falling back to raw value.');
        decodedCookie = document.cookie;
    }
    const cookieArray = decodedCookie.split(';');

    for (let i = 0; i < cookieArray.length; i++) {
        let cookie = cookieArray[i].trim();
        if (cookie.indexOf(name) === 0) {
            return cookie.substring(name.length, cookie.length);
        }
    }

    // If not in cookie, try to get from meta tag or response header
    const metaTag = document.querySelector('meta[name="csrf-token"]');
    if (metaTag) {
        return metaTag.getAttribute('content');
    }

    return null;
}

// Add CSRF token to all forms on page load
document.addEventListener('DOMContentLoaded', function () {
    const csrfToken = getCSRFToken();

    if (csrfToken) {
        // Add hidden input to all forms
        const forms = document.querySelectorAll('form');
        forms.forEach(form => {
            // Check if form already has CSRF token
            const existingToken = form.querySelector('input[name="csrf_token"]');
            if (!existingToken) {
                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'csrf_token';
                input.value = csrfToken;
                form.appendChild(input);
            }
        });
    }
});

// NOTE: window.fetchAPI CSRF handling is natively built into config.js
// (see config.js lines 59-66). No wrapper needed here.

// Enhance native fetch to include CSRF token
if (typeof window.fetch === 'function') {
    const originalFetch = window.fetch;

    window.fetch = function (url, options = {}) {
        const csrfToken = getCSRFToken();

        // Add CSRF token to headers for state-changing requests
        if (options.method && ['POST', 'PUT', 'DELETE', 'PATCH'].includes(options.method.toUpperCase())) {
            if (csrfToken) {
                // Avoid mutating caller's options object — create new headers
                const originalHeaders = options.headers || {};
                const newHeaders = new Headers(originalHeaders);
                newHeaders.set('X-CSRF-Token', csrfToken);
                options = { ...options, headers: newHeaders };
            }
        }

        return originalFetch(url, options);
    };
}

window.getCSRFToken = getCSRFToken;
