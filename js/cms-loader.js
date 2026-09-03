/**
 * CMS Loader
 * Fetches dynamic content overrides from the API and updates the DOM.
 */
// Expose globally for localization.js to call
window.applyCMSOverrides = applyCMSOverrides;

async function applyCMSOverrides() {
    const pageIdMeta = document.querySelector('meta[name="cms-page-id"]');
    if (!pageIdMeta) return;

    const pageSlug = pageIdMeta.content;
    const API_BASE_URL = (window.CONFIG && window.CONFIG.API_BASE_URL) || 'http://localhost:8000';

    // Check Editor Mode
    const urlParams = new URLSearchParams(window.location.search);
    const isEditor = urlParams.get('edit_mode') === 'true';
    if (isEditor && !document.getElementById('cms-toolbar')) {
        enableVisualEditor();
    }

    try {
        // Fetch overrides without triggering auth redirects
        const sections = [];

        // Use direct fetch instead of fetchAPI to avoid redirect on public pages
        try {
            const pageResponse = await fetch(`${API_BASE_URL}/api/v1/admin/pages/${pageSlug}`);
            if (pageResponse.ok) {
                const pageData = await pageResponse.json();
                if (Array.isArray(pageData)) sections.push(...pageData);
            }
        } catch (e) {
            // Silently fail - CMS content is optional
        }

        try {
            const globalResponse = await fetch(`${API_BASE_URL}/api/v1/admin/pages/global`);
            if (globalResponse.ok) {
                const globalData = await globalResponse.json();
                if (Array.isArray(globalData)) sections.push(...globalData);
            }
        } catch (e) {
            // Silently fail - CMS content is optional
        }

        if (sections.length > 0) {
            const overrideMap = {};
            sections.forEach(section => {
                try {
                    const content = JSON.parse(section.content_json);
                    for (const [key, value] of Object.entries(content)) {
                        overrideMap[`${section.section_slug}.${key}`] = value;
                    }
                } catch (e) { }
            });

            // 1. Standard Content Overrides (data-cms)
            const elements = document.querySelectorAll('[data-cms]');
            elements.forEach(el => {
                const key = el.getAttribute('data-cms');
                if (overrideMap[key] !== undefined) {
                    if (el.tagName === 'IMG') {
                        el.src = overrideMap[key];
                    } else {
                        el.innerHTML = overrideMap[key];
                    }
                }
            });

            // 2. Attribute Overrides (data-cms-attr="attrName:cmsKey")
            const attrElements = document.querySelectorAll('[data-cms-attr]');
            attrElements.forEach(el => {
                const parts = el.getAttribute('data-cms-attr').split(':');
                if (parts.length === 2) {
                    const attrName = parts[0];
                    const key = parts[1];
                    if (overrideMap[key] !== undefined) {
                        el.setAttribute(attrName, overrideMap[key]);
                    }
                }
            });

            // 3. List Overrides (data-cms-list="cmsKey" data-cms-template="templateId")
            // This is for dynamic things like logos or success stories if needed
            // For now, simpler overrides are better for the visual editor
        }
    } catch (e) {
        console.warn("CMS Load Error:", e);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    applyCMSOverrides();
});

function enableVisualEditor() {
    // console.log("CMS Visual Editor Active");

    // 0. Visual Badge
    const badge = document.createElement('div');
    badge.innerText = "✏️ Editor Mode";
    badge.style.cssText = "position:fixed; bottom:20px; right:20px; background:#6366f1; color:white; padding:8px 16px; border-radius:30px; font-weight:bold; z-index:2147483647; box-shadow:0 10px 25px rgba(0,0,0,0.2); font-family:sans-serif; pointer-events:none;";
    document.body.appendChild(badge);

    // 1. Inject Editor Styles
    const style = document.createElement('style');
    style.innerHTML = `
        [data-cms] {
            outline: 2px dashed rgba(99, 102, 241, 0.3) !important;
            outline-offset: 4px;
            cursor: text;
            transition: all 0.2s;
            position: relative;
            border-radius: 4px;
        }
        [data-cms]:hover {
            outline: 2px solid #6366f1 !important;
            background-color: rgba(99, 102, 241, 0.05);
        }
        [data-cms]:focus {
            outline: 2px solid #4f46e5 !important;
            background-color: rgba(99, 102, 241, 0.1);
            z-index: 50;
        }
        /* Floating Toolbar */
        #cms-toolbar {
            position: fixed;
            z-index: 1000;
            background: #1e293b;
            padding: 8px 12px;
            border-radius: 12px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
            display: flex;
            gap: 8px;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.2s, transform 0.2s;
            transform: translateY(10px);
        }
        #cms-toolbar.visible {
            opacity: 1;
            pointer-events: auto;
            transform: translateY(0);
        }
        .cms-tool-btn {
            color: #cbd5e1;
            background: transparent;
            border: none;
            padding: 6px;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            width: 32px;
            height: 32px;
        }
        .cms-tool-btn:hover {
            background: #334155;
            color: #ffffff;
        }
        .cms-tool-btn.active {
            color: #6366f1;
            background: #334155;
        }
        .cms-tool-divider {
            width: 1px;
            background: #475569;
            margin: 0 4px;
        }
    `;
    document.head.appendChild(style);

    // 2. Create Toolbar Element
    const toolbar = document.createElement('div');
    toolbar.id = 'cms-toolbar';
    toolbar.innerHTML = `
        <button class="cms-tool-btn" data-cmd="bold" title="Bold"><i class="fas fa-bold"></i></button>
        <button class="cms-tool-btn" data-cmd="italic" title="Italic"><i class="fas fa-italic"></i></button>
        <button class="cms-tool-btn" data-cmd="underline" title="Underline"><i class="fas fa-underline"></i></button>
        <div class="cms-tool-divider"></div>
        <button class="cms-tool-btn" data-cmd="justifyLeft" title="Align Left"><i class="fas fa-align-left"></i></button>
        <button class="cms-tool-btn" data-cmd="justifyCenter" title="Align Center"><i class="fas fa-align-center"></i></button>
        <button class="cms-tool-btn" data-cmd="justifyRight" title="Align Right"><i class="fas fa-align-right"></i></button>
        <div class="cms-tool-divider"></div>
        <button class="cms-tool-btn" data-cmd="removeFormat" title="Clear Formatting"><i class="fas fa-eraser"></i></button>
    `;
    document.body.appendChild(toolbar);

    // 3. Toolbar Functionality
    const buttons = toolbar.querySelectorAll('.cms-tool-btn');
    buttons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault(); // Prevent focus loss
            const cmd = btn.dataset.cmd;
            document.execCommand(cmd, false, null);
            updateToolbarState();
        });
        // Prevent focus loss on mousedown
        btn.addEventListener('mousedown', (e) => e.preventDefault());
    });

    function updateToolbarState() {
        buttons.forEach(btn => {
            if (document.queryCommandState(btn.dataset.cmd)) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
    }

    // 4. Attach Setup to Elements
    let activeElement = null;

    function positionToolbar(el) {
        if (!el) return;
        const rect = el.getBoundingClientRect();
        const toolbarRect = toolbar.getBoundingClientRect();

        // Position above the element, centered
        let top = rect.top - toolbarRect.height - 12;
        let left = rect.left + (rect.width / 2) - (toolbarRect.width / 2);

        // Keep within viewport
        if (top < 10) top = rect.bottom + 12; // Flip to bottom if no space on top
        if (left < 10) left = 10;
        if (left + toolbarRect.width > window.innerWidth) left = window.innerWidth - toolbarRect.width - 10;

        toolbar.style.top = `${top}px`;
        toolbar.style.left = `${left}px`;
        toolbar.classList.add('visible');
    }

    document.querySelectorAll('[data-cms]').forEach(el => {
        el.contentEditable = "true";
        el.setAttribute('spellcheck', 'false');

        // Prevent link navigation in editor
        if (el.tagName === 'A') {
            el.addEventListener('click', (e) => e.preventDefault());
        }

        // Show Toolbar on Focus
        el.addEventListener('focus', () => {
            activeElement = el;
            positionToolbar(el);
            updateToolbarState();
        });

        // Track selection changes for button state (Bold active? etc)
        el.addEventListener('keyup', updateToolbarState);
        el.addEventListener('mouseup', updateToolbarState);

        // Hide on blur (delayed to allow toolbar clicks)
        el.addEventListener('blur', (e) => {
            // Check if relatedTarget is toolbar
            // But we used preventDefault on mousedown, so blur shouldn't happen when clicking toolbar
            // However, if we click elsewhere, we want to hide.
            activeElement = null;
            toolbar.classList.remove('visible');
        });
    });

    // Intercept clicks to prevent nav
    document.addEventListener('click', (e) => {
        if (e.target.tagName === 'A' && !e.target.hasAttribute('data-cms')) {
            e.preventDefault();
        }
    }, true);
}
