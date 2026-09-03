/**
 * Security Utilities for Candway Platform
 * Provides XSS protection and input sanitization
 */

// Import DOMPurify (will be loaded via CDN in HTML)
// <script src="https://cdn.jsdelivr.net/npm/dompurify@3.0.6/dist/purify.min.js"></script>

window.SecurityUtils = {
    /**
     * Sanitizes HTML content to prevent XSS attacks
     * @param {string} dirty - Potentially unsafe HTML string
     * @param {Object} options - DOMPurify configuration options
     * @returns {string} Sanitized HTML string
     */
    sanitizeHTML: function (dirty, options = {}) {
        if (!dirty) return '';
        if (typeof dirty !== 'string') return String(dirty);

        // Check if DOMPurify is available
        if (typeof DOMPurify === 'undefined') {
            console.error('DOMPurify not loaded! Falling back to basic sanitization.');
            return this.basicSanitize(dirty);
        }

        const defaultConfig = {
            ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'a', 'p', 'br', 'ul', 'ol', 'li', 'span', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'],
            ALLOWED_ATTR: ['href', 'class', 'id', 'style'],
            ALLOW_DATA_ATTR: false,
            ...options
        };

        return DOMPurify.sanitize(dirty, defaultConfig);
    },

    /**
     * Basic sanitization fallback (when DOMPurify is not available)
     * @param {string} str - String to sanitize
     * @returns {string} Sanitized string
     */
    basicSanitize: function (str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    },

    /**
     * Escapes HTML special characters for safe text display
     * @param {string} text - Text to escape
     * @returns {string} Escaped text
     */
    escapeHTML: function (text) {
        if (typeof text !== 'string' || text === '') return '';
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#x27;',
            '/': '&#x2F;'
        };
        return String(text).replace(/[&<>"'/]/g, char => map[char]);
    },

    /**
     * Validates and sanitizes search input
     * @param {string} input - User search input
     * @param {number} maxLength - Maximum allowed length
     * @returns {string} Sanitized input
     */
    sanitizeSearchInput: function (input, maxLength = 100) {
        if (!input) return '';

        // Remove dangerous characters
        let sanitized = String(input)
            .replace(/[<>\"'`]/g, '')
            .trim()
            .substring(0, maxLength);

        return sanitized;
    },

    /**
     * Validates email format
     * @param {string} email - Email to validate
     * @returns {boolean} True if valid email format
     */
    isValidEmail: function (email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    },

    /**
     * Sanitizes URL to prevent javascript: and data: protocols
     * @param {string} url - URL to sanitize
     * @returns {string} Safe URL or empty string
     */
    sanitizeURL: function (url) {
        if (!url) return '';

        const urlStr = String(url).trim().toLowerCase();

        // Block dangerous protocols
        if (urlStr.startsWith('javascript:') ||
            urlStr.startsWith('data:') ||
            urlStr.startsWith('vbscript:')) {
            console.warn('Blocked dangerous URL protocol:', url);
            return '';
        }

        return url;
    },

    /**
     * Safely sets innerHTML with sanitization
     * @param {HTMLElement} element - Target element
     * @param {string} html - HTML content to set
     * @param {Object} options - Sanitization options
     */
    safeSetHTML: function (element, html, options = {}) {
        if (!element) {
            console.error('safeSetHTML: element is null');
            return;
        }

        const sanitized = this.sanitizeHTML(html, options);
        element.innerHTML = sanitized;
    },

    /**
     * Creates a safe text node (no HTML parsing)
     * @param {HTMLElement} element - Target element
     * @param {string} text - Text content
     */
    safeSetText: function (element, text) {
        if (!element) {
            console.error('safeSetText: element is null');
            return;
        }

        element.textContent = text;
    },

    /**
     * Validates file upload
     * @param {File} file - File to validate
     * @param {Object} options - Validation options
     * @returns {Object} { valid: boolean, error: string }
     */
    validateFile: function (file, options = {}) {
        const defaults = {
            maxSize: 5 * 1024 * 1024, // 5MB
            allowedTypes: ['image/jpeg', 'image/png', 'image/gif', 'application/pdf'],
            allowedExtensions: ['.jpg', '.jpeg', '.png', '.gif', '.pdf']
        };

        const config = { ...defaults, ...options };

        if (!file) {
            return { valid: false, error: 'No file provided' };
        }

        // Check file size
        if (file.size > config.maxSize) {
            return {
                valid: false,
                error: `File too large. Maximum size: ${(config.maxSize / 1024 / 1024).toFixed(1)}MB`
            };
        }

        // Check file type
        if (config.allowedTypes.length > 0 && !config.allowedTypes.includes(file.type)) {
            return {
                valid: false,
                error: `Invalid file type. Allowed: ${config.allowedTypes.join(', ')}`
            };
        }

        // Check file extension
        const fileName = file.name.toLowerCase();
        const ext = fileName.slice(fileName.lastIndexOf('.'));
        const hasValidExtension = config.allowedExtensions.includes(ext);

        if (!hasValidExtension) {
            return {
                valid: false,
                error: `Invalid file extension. Allowed: ${config.allowedExtensions.join(', ')}`
            };
        }

        return { valid: true, error: null };
    },

    /**
     * Rate limiting helper
     * @param {string} key - Unique key for this action
     * @param {number} maxAttempts - Maximum attempts allowed
     * @param {number} windowMs - Time window in milliseconds
     * @returns {boolean} True if action is allowed
     */
    checkRateLimit: function (key, maxAttempts = 5, windowMs = 60000) {
        const now = Date.now();
        const storageKey = `rateLimit_${key}`;

        let attempts = [];
        try {
            const stored = localStorage.getItem(storageKey);
            if (stored) {
                attempts = JSON.parse(stored);
            }
        } catch (e) {
            console.error('Rate limit storage error:', e);
        }

        // Filter out old attempts
        attempts = attempts.filter(timestamp => now - timestamp < windowMs);

        // Check if limit exceeded
        if (attempts.length >= maxAttempts) {
            console.warn(`Rate limit exceeded for: ${key}`);
            return false;
        }

        // Add new attempt
        attempts.push(now);

        try {
            localStorage.setItem(storageKey, JSON.stringify(attempts));
        } catch (e) {
            console.error('Rate limit storage error:', e);
        }

        return true;
    },

    /**
     * Retrieves the CSRF token from cookies
     * @returns {string|null} CSRF token or null if not found
     */
    getCSRFToken: function () {
        const name = "csrf_token=";
        const decodedCookie = decodeURIComponent(document.cookie);
        const ca = decodedCookie.split(';');
        for (let i = 0; i < ca.length; i++) {
            let c = ca[i];
            while (c.charAt(0) == ' ') {
                c = c.substring(1);
            }
            if (c.indexOf(name) == 0) {
                return c.substring(name.length, c.length);
            }
        }
        return null;
    }
};

// ── XSS namespace (backward compat with xss-protection.js API) ──
window.XSS = {
    sanitize(dirty, config = {}) {
        if (typeof DOMPurify === 'undefined') {
            console.error('DOMPurify not loaded! Falling back to text-only mode.');
            return window.SecurityUtils.basicSanitize(dirty);
        }
        const isTableFragment = /^\s*<tbody|^\s*<thead|^\s*<tfoot|^\s*<tr|^\s*<td|^\s*<th/i.test(dirty);
        let contentToSanitize = dirty;
        if (isTableFragment) {
            contentToSanitize = `<table><tbody>${dirty}</tbody></table>`;
        }
        const defaultConfig = {
            ALLOWED_TAGS: ['b', 'i', 'u', 'em', 'strong', 'p', 'br', 'ul', 'ol', 'li', 'a', 'span', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'code', 'pre', 'blockquote', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'button', 'svg', 'path', 'img', 'canvas'],
            ALLOWED_ATTR: ['href', 'title', 'target', 'class', 'id', 'src', 'alt', 'd', 'viewBox', 'fill', 'stroke', 'stroke-width', 'stroke-linecap', 'stroke-linejoin', 'colspan', 'scope', 'role', 'height', 'width'],
            ALLOW_DATA_ATTR: false,
            ...config
        };
        let sanitized = DOMPurify.sanitize(contentToSanitize, defaultConfig);
        if (isTableFragment) {
            const prefix = '<table><tbody>';
            const suffix = '</tbody></table>';
            if (sanitized.startsWith(prefix)) sanitized = sanitized.slice(prefix.length);
            if (sanitized.endsWith(suffix)) sanitized = sanitized.slice(0, -suffix.length);
        }
        return sanitized;
    },

    setHTML(element, content, config = {}) {
        if (!element) { console.error('XSS.setHTML: Invalid element'); return; }
        element.innerHTML = this.sanitize(content, config);
    },

    escapeHTML(text) {
        return window.SecurityUtils.escapeHTML(text);
    },

    setText(element, text) {
        if (!element) { console.error('XSS.setText: Invalid element'); return; }
        element.textContent = text;
    },

    appendHTML(element, content, config = {}) {
        if (!element) { console.error('XSS.appendHTML: Invalid element'); return; }
        element.insertAdjacentHTML('beforeend', this.sanitize(content, config));
    },

    sanitizeURL(url) {
        return window.SecurityUtils.sanitizeURL(url);
    },

    createElement(tagName, attributes = {}, content = '') {
        const element = document.createElement(tagName);
        for (const [key, value] of Object.entries(attributes)) {
            if (/^on/i.test(key)) {
                console.warn(`XSS: Event handler attribute "${key}" blocked.`);
                continue;
            }
            if (key === 'href' || key === 'src') {
                element.setAttribute(key, this.sanitizeURL(value));
            } else if (key === 'style') {
                console.warn('XSS: Inline styles blocked. Use classes instead.');
            } else {
                element.setAttribute(key, value);
            }
        }
        if (content) this.setHTML(element, content);
        return element;
    },

    safeSetHTML(element, html, options = {}) {
        return window.SecurityUtils.safeSetHTML(element, html, options);
    },

    safeSetText(element, text) {
        return window.SecurityUtils.safeSetText(element, text);
    },

    sanitizeTableRows(dirty) {
        if (window.DOMPurify && window.DOMPurify.sanitize) {
            var wrapped = '<table><tbody>' + dirty + '</tbody></table>';
            var clean = window.DOMPurify.sanitize(wrapped, { USE_PROFILES: { html: true } });
            var div = document.createElement('div');
            div.innerHTML = clean;
            var tb = div.querySelector('tbody');
            return tb ? tb.innerHTML : dirty;
        }
        return dirty;
    }
};

// Expose globally
window.sanitizeHTML = window.SecurityUtils.sanitizeHTML.bind(window.SecurityUtils);
window.escapeHTML = window.SecurityUtils.escapeHTML.bind(window.SecurityUtils);
window.safeSetHTML = window.SecurityUtils.safeSetHTML.bind(window.SecurityUtils);
window.safeSetText = window.SecurityUtils.safeSetText.bind(window.SecurityUtils);
