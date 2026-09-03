/**
 * Candway Intelligent Translation Engine - Core (Autonomous Loader)
 * 
 * This file serves as the central hub for the platform's multi-language support.
 * It dynamically injects locale-specific modules (EN, FR, AR) and handles
 * automated RTL/LTR switching and language detection.
 */

window.translations = {};

(function () {
    const modules = ['en', 'fr', 'ar'];

    // 1. Asynchronous Injection of Modules
    function loadScript(src) {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = src;
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    // 2. Core Merger & Init Logic
    async function finalize() {
        try {
            await Promise.all(modules.map(lang => loadScript(`/js/lang/${lang}.js?v=${new Date().getTime()}`)));
            
            let loadedCount = 0;
            modules.forEach(lang => {
                const moduleData = window[`translations_${lang}`];
                if (moduleData) {
                    window.translations[lang] = moduleData;
                    loadedCount++;
                }
            });

            if (loadedCount > 0) {
                if (typeof _log === 'function') _log(`[i18n] Successfully merged ${loadedCount} translation modules`);
                initializeIntelligentTranslation();
            } else {
                console.warn('[i18n] Translation modules loaded but data is missing.');
            }
        } catch (e) {
            console.error('[i18n] Failed to load translation modules', e);
            // Fallback initialization so UI doesn't hang
            initializeIntelligentTranslation();
        }
    }

    function initializeIntelligentTranslation() {
        const savedLang = localStorage.getItem('candway_lang');
        const detected = savedLang || detectUserLanguage();

        if (typeof _log === 'function') _log(`[i18n] Initializing with language: ${detected}`);

        // Apply Directionality (RTL/LTR)
        applyDirectionality(detected);

        // Dispatch event
        window.dispatchEvent(new CustomEvent('translationsReady', { detail: { lang: detected } }));

        // Refresh localization if helper is available
        if (window.updateContent) {
            window.updateContent(detected);
        }
    }

    function detectUserLanguage() {
        const browserLang = navigator.language || navigator.userLanguage;
        const shortLang = browserLang.split('-')[0];
        return modules.includes(shortLang) ? shortLang : 'en';
    }

    function applyDirectionality(lang) {
        const html = document.documentElement;
        const isRTL = (lang === 'ar');
        const dir = isRTL ? 'rtl' : 'ltr';

        html.setAttribute('dir', dir);
        html.setAttribute('lang', lang);

        if (isRTL) {
            html.classList.add('rtl-mode');
            document.body.classList.add('font-arabic');
        } else {
            html.classList.remove('rtl-mode');
            document.body.classList.remove('font-arabic');
        }
    }

    // 3. Export utilities
    window.i18n = {
        modules: modules,
        detect: detectUserLanguage,
        applyDir: applyDirectionality,
        refresh: finalize
    };

    // Finalize when modules are ready
    window.addEventListener('load', finalize);

    // Immediate attempt
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', finalize);
    } else {
        finalize();
    }
})();
