/**
 * Async asset loader & performance optimizer.
 * Loads non-critical CSS/JS without blocking page render.
 * Insert via: <script defer src="/js/load-assets.js"></script>
 */
(function() {
    'use strict';

    // Preconnect to known third-party origins (runs immediately)
    const origins = [
        'https://cdnjs.cloudflare.com',
        'https://fonts.googleapis.com',
        'https://fonts.gstatic.com',
        'https://cdn.jsdelivr.net',
        'https://unpkg.com',
        'https://cdn.quilljs.com',
    ];
    origins.forEach(origin => {
        if (!document.querySelector(`link[rel="preconnect"][href="${origin}"]`)) {
            const link = document.createElement('link');
            link.rel = 'dns-prefetch';
            link.href = origin;
            document.head.appendChild(link);
        }
    });

    function loadCSS(href) {
        if (document.querySelector(`link[href="${href}"]`)) return;
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = href;
        link.media = 'print';
        link.onload = function() { this.media = 'all'; };
        document.head.appendChild(link);
    }

    function loadJS(src) {
        if (document.querySelector(`script[src="${src}"]`)) return;
        const script = document.createElement('script');
        script.src = src;
        script.defer = true;
        const target = document.body || document.head;
        target.appendChild(script);
    }

    // Detect page-specific assets
    const hasQuill = document.querySelector('.ql-editor, #quill-editor, .quill-wrapper');
    const hasChart = document.querySelector('canvas#radarChart, canvas#scoreChart, .chart-js');
    const hasAOS = document.querySelector('[data-aos]');
    const hasDOMPurify = typeof DOMPurify === 'undefined';

    loadCSS('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css');
    if (hasQuill) {
        loadCSS('https://cdn.quilljs.com/1.3.6/quill.snow.css');
        loadJS('https://cdn.quilljs.com/1.3.6/quill.js');
    }
    if (hasChart) {
        loadJS('https://cdn.jsdelivr.net/npm/chart.js');
    }
    if (hasAOS) {
        loadCSS('https://unpkg.com/aos@2.3.1/dist/aos.css');
        loadJS('https://unpkg.com/aos@2.3.1/dist/aos.js');
    }
    if (hasDOMPurify) {
        loadJS('https://cdn.jsdelivr.net/npm/dompurify@3.0.6/dist/purify.min.js');
    }

    // ---- Post-paint optimizations ----

    // Lazy-load images with IntersectionObserver
    if ('IntersectionObserver' in window) {
        const observer = new IntersectionObserver((entries, obs) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    const src = img.dataset.src || img.src;
                    if (img.dataset.src) img.src = img.dataset.src;
                    img.removeAttribute('loading');
                    img.removeAttribute('data-src');
                    obs.unobserve(img);
                }
            });
        }, { rootMargin: '200px' });
        document.querySelectorAll('img[loading="lazy"], img[data-src]').forEach(img => observer.observe(img));
    }

    // Initialize AOS if loaded
    const checkAOS = setInterval(function() {
        if (typeof AOS !== 'undefined') {
            AOS.init({ once: true, duration: 600 });
            clearInterval(checkAOS);
        }
    }, 100);
    setTimeout(function() { clearInterval(checkAOS); }, 5000);

    // Register service worker if available (silent fail if no sw.js)
    if ('serviceWorker' in navigator) {
        window.addEventListener('load', function() {
            navigator.serviceWorker.register('/sw.js').catch(function() {});
        });
    }
})();
