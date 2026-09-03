/**
 * Candway Localization Engine
 * Handles multi-language switching, RTL support, and dynamic text updates.
 */

// Initialize global promise immediately to avoid race conditions
window.localizationReadyPromise = new Promise((resolve) => {
    window.resolveLocalization = resolve;
    
    // Fallback & Initialization: Fetch default language from server if not in localStorage
    const initLang = async () => {
        let lang = localStorage.getItem('candway_lang');
        if (!lang) {
            try {
                const res = await fetch('/config/public');
                const data = await res.json();
                lang = data.default_language || 'en';
            } catch (e) {
                lang = 'en';
            }
        }
        if (window.updateContent) window.updateContent(lang);
        if (window.resolveLocalization) {
            window.resolveLocalization(lang);
            window.resolveLocalization = null;
        }
    };
    initLang();

    // Safety timeout
    setTimeout(() => {
        if (window.resolveLocalization) {
            console.warn('[Localization] Promise auto-resolved via timeout fallback.');
            const lang = localStorage.getItem('candway_lang') || 'en';
            if (window.updateContent) window.updateContent(lang);
            window.resolveLocalization(lang);
            window.resolveLocalization = null;
        }
    }, 2500);
});

// Listen for translations immediately (outside DOMContentLoaded) to prevent race condition
window.addEventListener('translationsReady', (e) => {
    if (typeof _log === 'function') _log(`[Localization] Translations ready event received for ${e.detail.lang}`);
    if (document.readyState === 'complete' || document.readyState === 'interactive') {
        window.updateContent(e.detail.lang);
    }
    if (window.resolveLocalization) {
        window.resolveLocalization(e.detail.lang);
        window.resolveLocalization = null; // Prevent double resolve
    }
});

document.addEventListener('DOMContentLoaded', () => {
    const savedLang = localStorage.getItem('candway_lang') || 'en';

    // Initialize Language (Directionality, etc.)
    window.setLanguage(savedLang);

    // Global click listener for data-lang buttons (delegation)
    document.addEventListener('click', (e) => {
        const langBtn = e.target.closest('[data-lang]');
        if (langBtn && !langBtn.classList.contains('lang-dropdown-btn')) {
            const lang = langBtn.getAttribute('data-lang');
            window.setLanguage(lang);
        }

        // Close dropdown when clicking outside
        const menu = document.getElementById('candwayLangMenu');
        const btn = e.target.closest('.lang-dropdown-btn');
        if (menu && menu.classList.contains('show') && !btn) {
            menu.classList.remove('show');
        }
    });

    // Dropdown toggle function
    window.toggleLangDropdown = function (e) {
        if (e) e.stopPropagation();
        const menu = document.getElementById('candwayLangMenu');
        if (menu) {
            menu.classList.toggle('show');
        }
    };

    // Initialize Mobile Menu
    initMobileMenu();
});

/**
 * Global Translation Helper
 * Supports nested keys like 'candidate.dashboard.header_hello'
 * Supports parameters like {count} via the second argument
 */
window.tRaw = function (key, params = {}) {
    const lang = localStorage.getItem('candway_lang') || 'en';
    const currentObj = (window.translations && window.translations[lang]) || window[`translations_${lang}`];
    const fallbackEnObj = (window.translations && window.translations['en']) || window.translations_en;

    let translation = resolveTranslation(currentObj, key);

    // Key-level fallback to English if current language is missing this key
    if ((translation === null || translation === undefined) && lang !== 'en') {
        translation = resolveTranslation(fallbackEnObj, key);
    }

    if (translation === null || translation === undefined) {
        // Final fallback: try window.translations_en directly
        if (window.translations_en) {
            translation = resolveTranslation(window.translations_en, key);
        }
    }

    if (translation === null || translation === undefined) {
        return key;
    }

    // Handle string replacements for parameters
    if (typeof translation === 'string' && params && typeof params === 'object' && !Array.isArray(params)) {
        Object.keys(params).forEach(param => {
            translation = translation.replace(new RegExp(`{${param}}`, 'g'), params[param]);
        });
    }

    return translation;
};

window.t = function (key, params = {}) {
    const raw = window.tRaw(key, params);

    // If it found something that is NOT an object, return it
    if (raw !== key && typeof raw !== 'object') {
        return raw;
    }

    // If it found an object, it's probably a namespace conflict, fallback to key
    if (typeof raw === 'object' && raw !== null) {
        console.warn(`[Localization] Key "${key}" resolved to an object. Falling back to key name.`);
        return key;
    }

    // Use string fallback as params if provided
    if (typeof params === 'string') {
        return params;
    }
    return key;
};

function resolveTranslation(translationObj, key) {
    if (!translationObj || !key) return null;

    // 1) Direct and nested lookup (existing behavior)
    let value = getNestedValue(translationObj, key);
    if (value !== null && value !== undefined) return value;

    // 2) Namespace fallback: candidate.subscription.recommended -> subscription.recommended -> recommended
    if (key.includes('.')) {
        const segments = key.split('.');
        for (let i = 1; i < segments.length; i++) {
            const candidate = segments.slice(i).join('.');
            // Prevent dangerous global fallbacks to exact generic keys
            if (['title', 'subtitle', 'description', 'label'].includes(candidate)) {
                continue;
            }
            value = getNestedValue(translationObj, candidate);
            if (value !== null && value !== undefined) {
                return value;
            }
        }
    }

    return null;
}

function humanizeMissingKey(key) {
    if (!key || typeof key !== 'string') return '';
    if (!key.includes('.')) return key;

    const leaf = key.split('.').pop();
    if (!leaf || leaf.includes('/') || leaf.includes('\\') || leaf.includes('.')) {
        return key;
    }

    const words = leaf.replace(/[_-]+/g, ' ').trim();
    if (!words) return key;
    return words.replace(/\b\w/g, (ch) => ch.toUpperCase());
}

/**
 * Sets the application language and updates the UI
 */
window.setLanguage = function (lang) {
    const html = document.documentElement;
    html.setAttribute('lang', lang);

    // Persist Preference
    localStorage.setItem('candway_lang', lang);

    // Apply directionality based on language (RTL for Arabic)
    if (lang === 'ar') {
        html.setAttribute('dir', 'rtl');
        document.body.setAttribute('dir', 'rtl');
        html.classList.add('rtl-mode');
        document.body.classList.add('font-arabic');
    } else {
        html.setAttribute('dir', 'ltr');
        document.body.setAttribute('dir', 'ltr');
        html.classList.remove('rtl-mode');
        document.body.classList.remove('font-arabic');
    }

    // Update UI Elements with data-i18n attributes
    window.updateContent(lang);

    // Update Active Button States
    updateActiveButtons(lang);

    // Update main dropdown flag
    const currentFlagImg = document.getElementById('current-lang-flag');
    if (currentFlagImg) {
        const flagMap = { 'en': 'gb', 'fr': 'fr', 'ar': 'tn' };
        currentFlagImg.src = `https://flagcdn.com/w40/${flagMap[lang] || 'gb'}.png`;
    }

    // Close any open language dropdowns
    const headerDropdown = document.getElementById('header-lang-dropdown');
    if (headerDropdown) headerDropdown.classList.remove('active');
    const candwayLangMenu = document.getElementById('candwayLangMenu');
    if (candwayLangMenu) candwayLangMenu.classList.remove('active');

    // Dispatch event for other components to listen
    window.dispatchEvent(new CustomEvent('languageChanged', { detail: { language: lang } }));

    _log(`[Localization] Language set to: ${lang}`);
};

/**
 * Scans the DOM for elements with data-i18n attributes and updates them
 */
window.updateContent = function (lang) {
    // 1. Standard text translations
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        const count = el.getAttribute('data-count');
        const params = count !== null ? { count } : {};

        const translation = window.t(key, params);
        if (translation !== key) {
            el.innerHTML = translation;
        }
    });

    // 2. Placeholder translations
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        const key = el.getAttribute('data-i18n-placeholder');
        const translation = window.t(key);
        if (translation !== key) {
            el.placeholder = translation;
        }
    });

    // 3. Tooltip translations
    document.querySelectorAll('[data-i18n-tooltip]').forEach(el => {
        const key = el.getAttribute('data-i18n-tooltip');
        const translation = window.t(key);
        if (translation !== key) {
            el.setAttribute('data-tooltip', translation);
        }
    });

    // 4. Update elements that use data-i18n-attr (e.g. data-i18n-attr="title:nav.home")
    document.querySelectorAll('[data-i18n-attr]').forEach(el => {
        const attrMapping = el.getAttribute('data-i18n-attr'); // Format: "attr1:key1,attr2:key2"
        attrMapping.split(',').forEach(part => {
            const [attr, key] = part.split(':').map(s => s.trim());
            const translation = window.t(key);
            if (translation !== key) {
                el.setAttribute(attr, translation);
            }
        });
    });

    // Re-apply CMS Overrides if function exists
    if (window.applyCMSOverrides) {
        window.applyCMSOverrides();
    }
};

function updateActiveButtons(lang) {
    // Old pill buttons logic
    document.querySelectorAll('[data-lang]:not(.lang-option)').forEach(btn => {
        if (btn.getAttribute('data-lang') === lang) {
            btn.classList.add('bg-white', 'shadow-sm', 'text-indigo-600', 'active');
        } else {
            btn.classList.remove('bg-white', 'shadow-sm', 'text-indigo-600', 'active');
        }
    });

    // New dropdown logic
    document.querySelectorAll('.lang-option').forEach(option => {
        const checkIcon = option.querySelector('.check-icon');
        if (option.getAttribute('data-lang') === lang) {
            option.classList.add('active');
            if (checkIcon) checkIcon.style.opacity = '1';
        } else {
            option.classList.remove('active');
            if (checkIcon) checkIcon.style.opacity = '0';
        }
    });
}

function getNestedValue(obj, key) {
    if (!obj || !key) return null;
    if (obj[key] !== undefined) return obj[key];
    return key.split('.').reduce((o, i) => (o ? o[i] : null), obj);
}

function initMobileMenu() {
    const btn = document.getElementById('mobile-menu-btn');
    const menu = document.getElementById('mobile-menu');

    if (btn && menu) {
        btn.addEventListener('click', () => {
            const isHidden = menu.classList.contains('hidden');
            if (isHidden) {
                menu.classList.remove('hidden');
                menu.classList.add('flex');
            } else {
                menu.classList.add('hidden');
                menu.classList.remove('flex');
            }
        });
    }
}

