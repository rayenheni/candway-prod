/**
 * Admin Sidebar Component v4.0 — Recruiter Design System Applied
 *
 * Now uses the same dark gradient glass sidebar style as the recruiter
 * dashboard, with violet/indigo tones, glassmorphism, and premium feel.
 */

const ADMIN_NAV = [
    {
        label: "Overview", i18n: "admin.nav.overview",
        items: [
            { href: "/admin/dashboard", icon: "fas fa-tachometer-alt", label: "Dashboard", i18n: "admin.nav.dashboard" },
            { href: "/admin/analytics", icon: "fas fa-brain", label: "Intelligence & Stats", i18n: "admin.nav.analytics", permission: "view_analytics" },
            { href: "/admin/users", icon: "fas fa-users", label: "Users & Roles", i18n: "admin.nav.users", permission: "view_users" }
        ]
    },
    {
        label: "Commercial", i18n: "admin.nav.commercial",
        items: [
            { href: "/admin/subscriptions", icon: "fas fa-crown", label: "Subscriptions", i18n: "admin.nav.subscriptions", permission: "manage_finance" },
            { href: "/admin/recruiter-usage", icon: "fas fa-chart-line", label: "Usage Monitor", i18n: "admin.nav.usage", permission: "manage_finance" },
            { href: "/admin/payments", icon: "fas fa-coins", label: "Transactions", i18n: "admin.nav.payments", permission: "manage_finance" },
            { href: "/admin/invoices", icon: "fas fa-file-invoice", label: "Invoices (TND)", i18n: "admin.nav.invoices", permission: "manage_finance" },
            { href: "/admin/marketing", icon: "fas fa-bullhorn", label: "Marketing", i18n: "admin.nav.marketing", permission: "manage_content" }
        ]
    },
    {
        label: "Content & CMS", i18n: "admin.nav.cms",
        items: [
            { href: "/admin/content", icon: "fas fa-pen-nib", label: "Blog Manager", i18n: "admin.nav.content", permission: "manage_content" },
            { href: "/admin/opportunities", icon: "fas fa-globe", label: "Opportunities", i18n: "admin.nav.opportunities", permission: "manage_content" }
        ]
    },
    {
        label: "LMS & Training", i18n: "admin.nav.lms",
        items: [
            { href: "/admin/courses", icon: "fas fa-chalkboard-teacher", label: "Courses", i18n: "admin.nav.courses", permission: "manage_content" },
            { href: "/admin/jobs", icon: "fas fa-briefcase", label: "Job Board", i18n: "admin.nav.jobs", permission: "manage_content" },
            { href: "/admin/categories", icon: "fas fa-layer-group", label: "Categories", i18n: "admin.nav.categories", permission: "manage_content" }
        ]
    },
    {
        label: "System", i18n: "admin.nav.system",
        items: [
            { href: "/admin/support", icon: "fas fa-ticket-alt", label: "Support", i18n: "admin.nav.support", permission: "view_users" },
            { href: "/admin/settings", icon: "fas fa-cogs", label: "Settings", i18n: "admin.nav.settings", permission: "manage_admins" },
            { href: "/admin/prompt-management", icon: "fas fa-brain", label: "Prompt Management", i18n: "admin.nav.prompts", permission: "manage_content" },
            { href: "/admin/ai-sales", icon: "fas fa-robot", label: "AI Sales Engine", i18n: "admin.nav.ai_sales", permission: "manage_content" },
            { href: "/admin/announcements", icon: "fas fa-broadcast-tower", label: "Broadcasts", i18n: "admin.nav.broadcasts", permission: "manage_content" },
            { href: "/admin/technical", icon: "fas fa-server", label: "System Health", i18n: "admin.nav.technical", permission: "view_logs" }
        ]
    },
    {
        label: "Scoring", i18n: "admin.nav.scoring",
        items: [
            { href: "/admin/rubric-builder", icon: "fas fa-layer-group", label: "Rubric Builder", i18n: "admin.nav.rubric_builder" },
            { href: "/admin/ab-testing", icon: "fas fa-flask", label: "A/B Testing", i18n: "admin.nav.ab_testing", permission: "manage_content" }
        ]
    },
    {
        label: "Compliance (TN)", i18n: "admin.nav.compliance",
        items: [
            { href: "/admin/verifications", icon: "fas fa-check-double", label: "KYB Verification", i18n: "admin.nav.verifications", permission: "manage_admins" }
        ]
    },
    {
        label: "Links", i18n: "admin.nav.links",
        items: [
            { href: "/dashboard", icon: "fas fa-external-link-alt", label: "Live Site (Candidate)", i18n: "admin.nav.live_candidate" },
            { href: "/recruiter/dashboard", icon: "fas fa-briefcase", label: "Live Site (Recruiter)", i18n: "admin.nav.live_recruiter" }
        ]
    }
];

function normalizePath(path) {
    return (path || '').replace(/\/+$|\/+(?=\?)|\/+(?=#)/g, '') || '/';
}

function renderLink(item) {
    const label = (window.t && window.t(item.i18n) !== item.i18n) ? window.t(item.i18n) : item.label;
    const currentPath = normalizePath(window.location.pathname);
    const itemPath = normalizePath(item.href);
    const isActive = currentPath === itemPath || currentPath.startsWith(itemPath + '/');
    const permAttr = item.permission ? ` data-permission="${item.permission}"` : '';
    return `<a href="${item.href}" title="${label}" class="admin-nav-link ${isActive ? 'active' : ''}" role="menuitem" aria-label="${label}" ${isActive ? 'aria-current="page"' : ''}${permAttr}>
                <i class="${item.icon} admin-nav-link__icon" aria-hidden="true"></i>
                <span>${label}</span>
            </a>`;
}

function renderAdminSidebar() {
    const container = document.getElementById('admin-sidebar-container');
    if (!container) return;

    container.classList.add('admin-sidebar');

    const existingSpacer = document.getElementById('admin-sidebar-spacer');
    if (existingSpacer) {
        existingSpacer.remove();
    }

    let navHTML = '';
    ADMIN_NAV.forEach(group => {
        const groupLabel = (window.t && window.t(group.i18n) !== group.i18n) ? window.t(group.i18n) : group.label;
        navHTML += `
            <section class="admin-sidebar-section">
                <div class="admin-sidebar-section__label" data-i18n="${group.i18n}">${groupLabel}</div>
                <div class="admin-sidebar-links">${group.items.map(renderLink).join('')}</div>
            </section>`;
    });

    const logoutLabel = window.t ? window.t('nav.logout') : 'Logout';
    const currentLang = localStorage.getItem('candway_lang') || 'en';

    container.innerHTML = `
        <button class="admin-sidebar__toggle" onclick="window.toggleAdminSidebar(true)" aria-label="Open sidebar">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg>
        </button>
        <div class="admin-sidebar-overlay" onclick="window.toggleAdminSidebar(false)"></div>
        <div class="admin-sidebar__panel" id="admin-sidebar-panel">
            <button class="admin-sidebar__close" onclick="window.toggleAdminSidebar(false)" aria-label="Close sidebar">&times;</button>
            <div class="admin-sidebar__header">
                <img src="/assets/images/candway_logo.png" alt="Candway" class="admin-sidebar__logo" onerror="this.style.display='none'">
                <div>
                    <span class="admin-sidebar__brand-name">Candway<span class="admin-sidebar__brand-accent">Admin</span></span>
                    <div class="admin-sidebar__brand-tagline" data-i18n="admin.nav.control_panel">Control Panel</div>
                </div>
            </div>
            <nav id="admin-nav" class="admin-nav" role="navigation" aria-label="Admin navigation">
                ${navHTML}
            </nav>
            <div class="admin-sidebar__footer">
                <div class="admin-lang-switcher" role="group" aria-label="Language selector">
                    <button type="button" class="admin-lang-switcher__btn${currentLang === 'en' ? ' active' : ''}" data-lang="en">EN</button>
                    <button type="button" class="admin-lang-switcher__btn${currentLang === 'fr' ? ' active' : ''}" data-lang="fr">FR</button>
                    <button type="button" class="admin-lang-switcher__btn${currentLang === 'ar' ? ' active' : ''}" data-lang="ar">AR</button>
                </div>
                <button type="button" class="admin-logout-btn" onclick="logout()" aria-label="${logoutLabel}">
                    <i class="fas fa-sign-out-alt" aria-hidden="true"></i>
                    <span data-i18n="nav.logout">${logoutLabel}</span>
                </button>
            </div>
        </div>
    `;

    document.querySelectorAll('.admin-lang-switcher__btn').forEach(btn => {
        btn.addEventListener('click', () => setLanguage(btn.getAttribute('data-lang')));
    });

    if (window.applyRBACUI) {
        window.applyRBACUI();
    }
}

window.toggleAdminSidebar = function (open) {
    const container = document.getElementById('admin-sidebar-container');
    if (!container) return;
    container.classList.toggle('admin-sidebar--open', !!open);
    document.body.classList.toggle('admin-sidebar-open', !!open);
};

window.applyRBACUI = (function () {
    let _cache = null;
    let _cacheTime = 0;
    const CACHE_TTL = 30000;

    async function _fetchPermissions() {
        const now = Date.now();
        if (_cache && now - _cacheTime < CACHE_TTL) return _cache;
        try {
            const resp = await window.fetchAPI('/auth/me');
            _cache = {
                perms: (resp.admin_permissions || '').split(',').map(function (p) { return p.trim(); }).filter(Boolean),
                isSuperAdmin: resp.is_super_admin || false,
            };
            _cacheTime = now;
            return _cache;
        } catch (_e) {
            return { perms: [], isSuperAdmin: false };
        }
    }

    return async function () {
        const user = await _fetchPermissions();
        if (user.error || user.isSuperAdmin) return;
        if (!Array.isArray(user.perms)) return;

        var links = document.querySelectorAll('#admin-nav a[data-permission]');
        for (var i = 0; i < links.length; i++) {
            var required = links[i].getAttribute('data-permission');
            if (required && user.perms.indexOf(required) === -1) {
                links[i].style.display = 'none';
            }
        }
    };
})();

function logout() {
    if (typeof window.fetchAPI === 'function') {
        window.fetchAPI('/logout', { method: 'POST' }).catch(() => {});
    } else {
        fetch('/api/v1/logout', { method: 'POST', credentials: 'same-origin' }).catch(() => {});
    }

    for (let i = 1; i <= 99999; i++) clearInterval(i);

    const authKeys = ['token', 'role', 'user', 'userName', 'user_email', 'userId', 'userPhotoUrl', 'profileStrength'];
    authKeys.forEach(key => localStorage.removeItem(key));

    document.cookie = 'logged_in=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';

    window.location.href = '/login';
}

document.addEventListener('DOMContentLoaded', async () => {
    if (window.localizationReadyPromise) {
        await window.localizationReadyPromise;
    }
    renderAdminSidebar();
});

window.addEventListener('languageChanged', () => {
    renderAdminSidebar();
});
