/**
 * XSS Protection Helper (self-sufficient shim)
 *
 * Tries to use window.SecurityUtils first, then DOMPurify, then falls back
 * to a basic HTML escape. Designed to never throw and never leave the caller
 * with an undefined reference.
 *
 * Backward compatibility: exposes window.XSS with the same surface that
 * legacy code expects (.sanitize, .escapeHTML, etc).
 */
(function () {
  if (typeof window === 'undefined') return;

  function basicEscapeHTML(input) {
    if (input === null || input === undefined) return '';
    return String(input)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;')
      .replace(/`/g, '&#96;');
  }

  function dompurifySanitize(dirty) {
    if (!window.DOMPurify || !window.DOMPurify.sanitize) {
      return basicEscapeHTML(dirty);
    }
    try {
      return window.DOMPurify.sanitize(dirty, { USE_PROFILES: { html: true } });
    } catch (e) {
      return basicEscapeHTML(dirty);
    }
  }

  function dompurifySanitizeText(dirty) {
    if (!window.DOMPurify || !window.DOMPurify.sanitize) {
      return basicEscapeHTML(dirty);
    }
    try {
      return window.DOMPurify.sanitize(dirty, { ALLOWED_TAGS: [], ALLOWED_ATTR: [] });
    } catch (e) {
      return basicEscapeHTML(dirty);
    }
  }

  if (typeof window.XSS === 'undefined') {
    if (typeof window.SecurityUtils !== 'undefined') {
      window.XSS = window.SecurityUtils;
    } else if (typeof window.DOMPurify !== 'undefined') {
      window.XSS = {
        sanitize: dompurifySanitize,
        sanitizeText: dompurifySanitizeText,
        escapeHTML: basicEscapeHTML,
        escape: basicEscapeHTML,
        sanitizeURL: function (url) { return String(url || '').replace(/[<>"']/g, ''); },
        basicSanitize: basicEscapeHTML,
        safeSetHTML: function (el, html) {
          if (el && 'innerHTML' in el) el.innerHTML = dompurifySanitize(html);
        },
        safeSetText: function (el, text) {
          if (el && 'textContent' in el) el.textContent = text;
        },
        sanitizeTableRows: function (dirty) {
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
    } else {
      window.XSS = {
        sanitize: function (dirty) { return basicEscapeHTML(dirty); },
        sanitizeText: function (dirty) { return basicEscapeHTML(dirty); },
        escapeHTML: basicEscapeHTML,
        escape: basicEscapeHTML,
        sanitizeURL: function (url) { return String(url || '').replace(/[<>"']/g, ''); },
        basicSanitize: basicEscapeHTML,
        safeSetHTML: function (el, html) {
          if (el && 'innerHTML' in el) el.textContent = String(html || '');
        },
        safeSetText: function (el, text) {
          if (el && 'textContent' in el) el.textContent = text;
        },
        sanitizeTableRows: function (dirty) { return dirty; }
      };
    }
  }
})();

// window.XSS already assigned inside the IIFE above
