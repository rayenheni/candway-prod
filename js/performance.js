/**
 * Performance Utilities for Candway Platform
 * Provides debouncing, throttling, and optimization helpers
 */

window.PerformanceUtils = {
    /**
     * Debounce function - delays execution until after wait time has elapsed
     * Perfect for search inputs, resize handlers, etc.
     * @param {Function} func - Function to debounce
     * @param {number} wait - Milliseconds to wait
     * @param {boolean} immediate - Execute on leading edge instead of trailing
     * @returns {Function} Debounced function
     */
    debounce: function (func, wait = 300, immediate = false) {
        let timeout;

        return function executedFunction(...args) {
            const context = this;

            const later = function () {
                timeout = null;
                if (!immediate) func.apply(context, args);
            };

            const callNow = immediate && !timeout;

            clearTimeout(timeout);
            timeout = setTimeout(later, wait);

            if (callNow) func.apply(context, args);
        };
    },

    /**
     * Throttle function - ensures function is called at most once per interval
     * Perfect for scroll handlers, mouse move, etc.
     * @param {Function} func - Function to throttle
     * @param {number} limit - Milliseconds between calls
     * @returns {Function} Throttled function
     */
    throttle: function (func, limit = 300) {
        let inThrottle;

        return function (...args) {
            const context = this;

            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    },

    /**
     * Lazy load images - only load when in viewport
     * @param {string} selector - CSS selector for images to lazy load
     */
    lazyLoadImages: function (selector = 'img[data-src]') {
        if ('IntersectionObserver' in window) {
            const imageObserver = new IntersectionObserver((entries, observer) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        img.src = img.dataset.src;
                        img.removeAttribute('data-src');
                        imageObserver.unobserve(img);
                    }
                });
            });

            document.querySelectorAll(selector).forEach(img => {
                imageObserver.observe(img);
            });
        } else {
            // Fallback for browsers without IntersectionObserver
            document.querySelectorAll(selector).forEach(img => {
                img.src = img.dataset.src;
                img.removeAttribute('data-src');
            });
        }
    },

    /**
     * Batch DOM updates to minimize reflows
     * @param {Function} callback - Function containing DOM updates
     */
    batchDOMUpdates: function (callback) {
        requestAnimationFrame(() => {
            callback();
        });
    },

    /**
     * Create a search ID tracker to prevent race conditions
     * @returns {Object} Search tracker with getId and isLatest methods
     */
    createSearchTracker: function () {
        let currentId = 0;

        return {
            getId: function () {
                return ++currentId;
            },
            isLatest: function (id) {
                return id === currentId;
            },
            reset: function () {
                currentId = 0;
            }
        };
    },

    /**
     * Limit array/string size to prevent memory issues
     * @param {Array|string} data - Data to limit
     * @param {number} maxSize - Maximum size
     * @returns {Array|string} Limited data
     */
    limitSize: function (data, maxSize = 1000) {
        if (Array.isArray(data)) {
            return data.slice(-maxSize);
        } else if (typeof data === 'string') {
            return data.substring(data.length - maxSize);
        }
        return data;
    },

    /**
     * Memoize function results to avoid redundant calculations
     * @param {Function} func - Function to memoize
     * @param {number} maxCacheSize - Maximum cache entries
     * @returns {Function} Memoized function
     */
    memoize: function (func, maxCacheSize = 100) {
        const cache = new Map();

        return function (...args) {
            const key = JSON.stringify(args);

            if (cache.has(key)) {
                return cache.get(key);
            }

            const result = func.apply(this, args);

            // Limit cache size
            if (cache.size >= maxCacheSize) {
                const firstKey = cache.keys().next().value;
                cache.delete(firstKey);
            }

            cache.set(key, result);
            return result;
        };
    },

    /**
     * Virtual scroll helper for large lists
     * @param {Array} items - All items
     * @param {number} containerHeight - Visible container height
     * @param {number} itemHeight - Height of each item
     * @param {number} scrollTop - Current scroll position
     * @returns {Object} Visible items and offset
     */
    virtualScroll: function (items, containerHeight, itemHeight, scrollTop) {
        const startIndex = Math.floor(scrollTop / itemHeight);
        const endIndex = Math.ceil((scrollTop + containerHeight) / itemHeight);

        return {
            visibleItems: items.slice(startIndex, endIndex + 1),
            offsetY: startIndex * itemHeight,
            startIndex,
            endIndex
        };
    },

    /**
     * Measure function execution time
     * @param {Function} func - Function to measure
     * @param {string} label - Label for console output
     * @returns {Function} Wrapped function
     */
    measurePerformance: function (func, label = 'Function') {
        return async function (...args) {
            const start = performance.now();
            const result = await func.apply(this, args);
            const end = performance.now();
            _log(`${label} took ${(end - start).toFixed(2)}ms`);
            return result;
        };
    }
};

// Expose commonly used functions globally
window.debounce = window.PerformanceUtils.debounce;
window.throttle = window.PerformanceUtils.throttle;

_log('✅ Performance utilities loaded');
