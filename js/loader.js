/**
 * Asset Loader — lazy-loads page-specific JS and CSS on demand.
 *
 * Usage in HTML:
 *   <script src="/js/loader.js"></script>
 *   <script>
 *     AssetLoader.require('/js/candidate/dashboard.js', '/js/charts.js');
 *   </script>
 *
 * This reduces the initial page weight by only loading what each page needs,
 * instead of loading all 58 JS files globally.
 */
const AssetLoader = (() => {
    const loaded = new Set();

    function loadScript(src) {
        if (loaded.has(src)) return Promise.resolve();
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = src;
            script.onload = () => { loaded.add(src); resolve(); };
            script.onerror = () => reject(new Error(`Failed to load: ${src}`));
            document.body.appendChild(script);
        });
    }

    function loadCSS(href) {
        if (loaded.has(href)) return Promise.resolve();
        return new Promise((resolve, reject) => {
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = href;
            link.onload = () => { loaded.add(href); resolve(); };
            link.onerror = () => reject(new Error(`Failed to load: ${href}`));
            document.head.appendChild(link);
        });
    }

    async function require(...assets) {
        const results = assets.map(a => {
            if (a.endsWith('.css')) return loadCSS(a);
            return loadScript(a);
        });
        await Promise.allSettled(results);
    }

    return { require, loadScript, loadCSS };
})();
