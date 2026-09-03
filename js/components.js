class Components {
    static safeHTML(dirty) {
        if (!dirty) return '';
        if (typeof dirty !== 'string') return String(dirty);
        if (typeof window.SecurityUtils !== 'undefined' && window.SecurityUtils.sanitizeHTML) {
            return window.SecurityUtils.sanitizeHTML(dirty);
        }
        const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#x27;', '/': '&#x2F;' };
        return String(dirty).replace(/[&<>"'/]/g, s => map[s]);
    }

    static showToast(message, type = 'info') {
        if (typeof window.showToast === 'function') {
            window.showToast(message, type);
        } else if (typeof Toast !== 'undefined' && Toast.show) {
            Toast.show(message, type);
        } else {
            console.warn('[Components] No toast implementation found:', message);
        }
    }

    static getHomeLink() {
        const role = localStorage.getItem('role');
        if (role === 'mentor') return '/mentor/dashboard';
        if (role === 'recruiter') return '/recruiter/dashboard';
        if (role === 'admin') return '/admin/dashboard';
        return '/dashboard';
    }

    static init(activePage = null) {
        // Guard: prevent double-render when auto-init + page init both fire
        if (document.getElementById('main-sidebar')) {
            if (activePage) this.renderSidebar(activePage);
            return;
        }

        const role = localStorage.getItem('role') || 'candidate';
        document.body.classList.add(`role-${role}`);

        if (typeof window.t !== 'function') {
            window.t = function(k) {
                if (typeof window.tRaw === 'function') {
                    var raw = window.tRaw(k);
                    return raw !== k ? raw : undefined;
                }
                const lang = localStorage.getItem('candway_lang') || 'en';
                const dict = window[`translations_${lang}`];
                if (dict) {
                    const parts = k.split('.');
                    let val = dict;
                    for (const p of parts) {
                        if (val && typeof val === 'object' && p in val) { val = val[p]; } else { val = undefined; break; }
                    }
                    if (typeof val === 'string') return val;
                }
                return undefined;
            };
        }

        const token = localStorage.getItem('token');
        if (token) {
            try {
                const parts = token.split('.');
                if (parts.length > 1) {
                    const payload = JSON.parse(atob(parts[1]));
                    if (payload.role) {
                        localStorage.setItem('role', payload.role);
                        let name = payload.name || (payload.email ? payload.email.split('@')[0].replace(/[._-]/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) : 'Candidate');
                        localStorage.setItem('userName', name || localStorage.getItem('userName'));
                        if (payload.id) localStorage.setItem('userId', payload.id);
                    }
                }
            } catch (e) {
                console.warn("Role claim parsing skipped", e);
            }
        }

        this.injectStyles();
        this.renderSidebar(activePage);
        this.renderTopHeader();
        this.applySidebarState();

        const theme = localStorage.getItem('preferredTheme') || 'light';
        document.documentElement.setAttribute('data-theme', theme);

        // Apply theme to sidebar
        this.updateSidebarTheme();

        // Sync sidebar state across tabs
        this.initCrossTabSync();

        // Re-render sidebar + header when language changes
        window.addEventListener('languageChanged', () => {
            this.renderSidebar();
            this.renderTopHeader();
        });
    }

    static injectStyles() {
        if (document.getElementById('candway-global-styles')) return;

        const link = document.createElement('link');
        link.id = 'candway-font-link';
        link.rel = 'stylesheet';
        link.href = 'https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap';
        document.head.appendChild(link);

        // Preload Zain Arabic font via <link> for reliability
        if (!document.querySelector('link[href*="family=Zain"]')) {
            const zainLink = document.createElement('link');
            zainLink.rel = 'stylesheet';
            zainLink.href = 'https://fonts.googleapis.com/css2?family=Zain:wght@300;400;700&display=swap';
            document.head.appendChild(zainLink);
        }

        const style = document.createElement('style');
        style.id = 'candway-global-styles';
        style.textContent = `
            @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&display=swap');
            @import url('https://fonts.googleapis.com/css2?family=Zain:wght@300;400;700&display=swap');
            :root {
                --sidebar-width: 280px;
                --sidebar-width-collapsed: 88px;
                --primary: #7C3AED;
                --primary-dark: #5B21B6;
                --primary-light: #A78BFA;
                --success: #10B981;
                --warning: #F59E0B;
                --danger: #EF4444;
                --surface: #F5F3FF;
                --surface-dark: #0F172A;
                --text-main: #0F172A;
                --text-muted: #64748B;
                --text-light: #F1F5F9;
                --border-light: rgba(167,139,250,0.18);
                --border-dark: #1E293B;
                --glass-bg: rgba(255, 255, 255, 0.62);
                --glass-border: rgba(255, 255, 255, 0.58);
                --card-shadow: 0 24px 70px -32px rgba(88, 28, 135, 0.38), inset 0 1px 0 rgba(255,255,255,0.72);
                --glow-primary: 0 0 28px rgba(124, 58, 237, 0.26);
            }

            body.role-recruiter {
                --primary: #6366f1;
                --primary-dark: #4f46e5;
                --primary-light: #818cf8;
                --glow-primary: 0 0 28px rgba(99, 102, 241, 0.26);
            }

            /* SIDEBAR CONTAINER — matches fixed sidebar background to prevent body bg leak */
            #sidebar-container {
                background: linear-gradient(180deg, rgba(30,20,60,0.85) 0%, rgba(20,15,45,0.92) 50%, rgba(15,10,35,0.95) 100%);
            }
            body.role-recruiter #sidebar-container {
                background:
                    radial-gradient(circle at 20% 0%, rgba(139, 92, 246, 0.25), transparent 40%),
                    radial-gradient(circle at 80% 100%, rgba(79, 70, 229, 0.15), transparent 40%),
                    linear-gradient(180deg, rgba(30, 20, 60, 0.85) 0%, rgba(20, 15, 45, 0.92) 50%, rgba(15, 10, 35, 0.95) 100%);
            }
            [dir="rtl"] #sidebar-container,
            html.rtl-mode #sidebar-container {
                background: none;
                width: 0;
                min-width: 0;
                overflow: hidden;
            }

            /* COLLAPSED SIDEBAR (desktop toggle) */
            body.sidebar-collapsed #sidebar-container {
                width: 88px !important;
                min-width: 88px !important;
            }

            body.sidebar-collapsed #candway-top-header {
                left: var(--sidebar-width-collapsed) !important;
            }

            body.sidebar-collapsed #sidebar-container .nav-label,
            body.sidebar-collapsed #sidebar-container .sidebar-section-header,
            body.sidebar-collapsed #sidebar-container .sidebar-user-info,
            body.sidebar-collapsed #sidebar-container .upgrade-strip-text {
                display: none;
            }

            body.sidebar-collapsed #sidebar-container .nav-link {
                justify-content: center;
                padding: 12px;
                margin: 2px 8px;
            }

            body.sidebar-collapsed #sidebar-container .nav-link i {
                font-size: 18px;
                margin: 0;
            }

            body.sidebar-collapsed #sidebar-container .logo-container {
                justify-content: center;
                padding: 16px 12px;
                height: 60px;
            }

            body.sidebar-collapsed #sidebar-container .sidebar-logo-img {
                width: 40px;
                height: 40px;
            }

            body.sidebar-collapsed #sidebar-container .sidebar-user-card {
                justify-content: center;
                padding: 8px;
            }

            body.sidebar-collapsed #sidebar-container .sidebar-avatar {
                width: 36px;
                height: 36px;
            }

            body.sidebar-collapsed #sidebar-container .sidebar-collapse-btn {
                transform: rotate(180deg);
            }

            [data-theme="dark"] {
                --surface: #0F172A;
                --text-main: #F1F5F9;
                --text-muted: #94A3B8;
                --border-light: #1E293B;
                --glass-bg: rgba(15, 23, 42, 0.85);
                --glass-border: rgba(51, 65, 85, 0.25);
            }


            body {
                font-family: 'Plus Jakarta Sans', system-ui, sans-serif;
                background: var(--surface);
                color: var(--text-main);
                margin: 0;
                transition: background-color 0.3s ease, color 0.3s ease;
                -webkit-font-smoothing: antialiased;
            }

            /* Arabic font override -- Zain for Arabic text, exclude icon elements */
            body.font-arabic {
                font-family: 'Zain', 'Plus Jakarta Sans', 'Outfit', system-ui, sans-serif !important;
            }
            body.font-arabic h1, body.font-arabic h2, body.font-arabic h3,
            body.font-arabic h4, body.font-arabic h5, body.font-arabic h6,
            body.font-arabic p, body.font-arabic span, body.font-arabic a,
            body.font-arabic label, body.font-arabic input, body.font-arabic textarea,
            body.font-arabic select, body.font-arabic button, body.font-arabic div,
            body.font-arabic td, body.font-arabic th, body.font-arabic li,
            body.font-arabic nav-link, body.font-arabic .nav-label,
            body.font-arabic .stat-label, body.font-arabic .stat-value,
            body.font-arabic .section-title, body.font-arabic .card-title {
                font-family: 'Zain', 'Plus Jakarta Sans', 'Outfit', system-ui, sans-serif !important;
            }
            /* Preserve Font Awesome icon rendering -- icons must keep their font-family */
            body.font-arabic i,
            body.font-arabic i.fa-solid,
            body.font-arabic i.fa-regular,
            body.font-arabic i.fa-brands,
            body.font-arabic i.fas,
            body.font-arabic i.far,
            body.font-arabic i.fab,
            body.font-arabic [class*="fa-"],
            body.font-arabic span.fa-solid,
            body.font-arabic span.fa-regular,
            body.font-arabic span.fa-brands {
                font-family: 'Font Awesome 6 Free', 'Font Awesome 6 Free Solid', 'Font Awesome 6 Free Regular', 'Font Awesome 6 Brands' !important;
            }
            body.font-arabic .sidebar-logo-img {
                font-family: 'Outfit', sans-serif !important;
            }
            #main-sidebar a { text-decoration: none; }

            /* ===== RTL LAYOUT FLIP ===== */
            [dir="rtl"] aside#main-sidebar,
            html.rtl-mode aside#main-sidebar {
                left: auto;
                right: 0;
                border-right: none;
                border-left: 1px solid rgba(139, 92, 246, 0.15);
                box-shadow: -12px 0 50px rgba(79, 70, 229, 0.25);
            }
            [dir="rtl"] aside#main-sidebar::before,
            html.rtl-mode aside#main-sidebar::before {
                background:
                    linear-gradient(270deg, rgba(255,255,255,0.09), transparent 42%),
                    linear-gradient(180deg, rgba(167,139,250,0.2), transparent 34%) !important;
            }
            [dir="rtl"] aside#main-sidebar.sidebar-recruiter::before,
            html.rtl-mode aside#main-sidebar.sidebar-recruiter::before {
                background:
                    linear-gradient(270deg, rgba(255,255,255,0.06), transparent 42%),
                    linear-gradient(180deg, rgba(139, 92, 246, 0.12), transparent 34%) !important;
            }
            [dir="rtl"] .nav-link:hover,
            html.rtl-mode .nav-link:hover {
                transform: translateX(-2px);
            }
            [dir="rtl"] .nav-link.active-item,
            html.rtl-mode .nav-link.active-item {
                transform: translateX(-2px);
            }
            [dir="rtl"] .nav-link.active-item::after,
            html.rtl-mode .nav-link.active-item::after {
                left: auto;
                right: -75%;
            }
            [dir="rtl"] .nav-link.active-item::before,
            html.rtl-mode .nav-link.active-item::before {
                left: auto;
                right: -10px;
            }
            [dir="rtl"] .nav-badge,
            html.rtl-mode .nav-badge {
                margin-left: 0;
                margin-right: auto;
            }
            [dir="rtl"] .sidebar-section-header,
            html.rtl-mode .sidebar-section-header {
                padding-left: 0;
                padding-right: 2px;
            }
            [dir="rtl"] aside#main-sidebar .sidebar-collapse-btn,
            html.rtl-mode aside#main-sidebar .sidebar-collapse-btn {
                right: auto;
                left: -14px;
            }
            /* Main content */
            [dir="rtl"] #main-wrapper,
            html.rtl-mode #main-wrapper {
                margin-left: 0;
                margin-right: var(--sidebar-width);
            }
            [dir="rtl"] body.sidebar-collapsed #main-wrapper,
            html.rtl-mode body.sidebar-collapsed #main-wrapper {
                margin-left: 0;
                margin-right: var(--sidebar-width-collapsed);
            }
            /* Top header */
            [dir="rtl"] header#candway-top-header,
            html.rtl-mode header#candway-top-header {
                left: 0;
                right: var(--sidebar-width);
                flex-direction: row-reverse;
            }
            [dir="rtl"] body.sidebar-collapsed header#candway-top-header,
            html.rtl-mode body.sidebar-collapsed header#candway-top-header {
                left: 0;
                right: var(--sidebar-width-collapsed);
            }
            [dir="rtl"] header#candway-top-header .header-actions,
            html.rtl-mode header#candway-top-header .header-actions {
                flex-direction: row-reverse;
            }
            [dir="rtl"] header#candway-top-header .header-search-container,
            html.rtl-mode header#candway-top-header .header-search-container {
                order: -1;
            }
            [dir="rtl"] header#candway-top-header .header-search-container input,
            html.rtl-mode header#candway-top-header .header-search-container input {
                text-align: right;
                padding-right: 48px;
                padding-left: 16px;
            }
            /* Main padding */
            [dir="rtl"] main,
            html.rtl-mode main {
                padding-left: 0;
                padding-right: 24px;
            }
            /* Dropdown direction */
            [dir="rtl"] .candway-dropdown,
            html.rtl-mode .candway-dropdown {
                right: auto;
                left: 0;
                transform-origin: top left;
            }
            /* Mobile */
            @media (max-width: 1024px) {
                [dir="rtl"] aside#main-sidebar,
                html.rtl-mode aside#main-sidebar {
                    left: auto;
                    right: -100%;
                    border-left: none;
                }
                [dir="rtl"] aside#main-sidebar.mobile-open,
                html.rtl-mode aside#main-sidebar.mobile-open {
                    left: auto;
                    right: 0;
                }
                [dir="rtl"] aside#main-sidebar,
                html.rtl-mode aside#main-sidebar {
                    transform: translateX(100%);
                }
                [dir="rtl"] header#candway-top-header,
                html.rtl-mode header#candway-top-header {
                    left: 0;
                    right: 0;
                }
                [dir="rtl"] .mobile-menu-toggle,
                html.rtl-mode .mobile-menu-toggle {
                    left: auto;
                    right: 20px;
                }
                [dir="rtl"] #main-wrapper,
                html.rtl-mode #main-wrapper {
                    margin-left: 0;
                    margin-right: 0;
                }
            }
            /* Sidebar collapse chevron direction */
            [dir="rtl"] body.sidebar-collapsed aside#main-sidebar .sidebar-collapse-btn i,
            html.rtl-mode body.sidebar-collapsed aside#main-sidebar .sidebar-collapse-btn i {
                transform: scaleX(-1);
            }
            /* ===== END RTL LAYOUT FLIP ===== */

            /* SIDEBAR */
            aside#main-sidebar {
                position: fixed;
                top: 0;
                bottom: 0;
                left: 0;
                width: var(--sidebar-width);
                background:
                    radial-gradient(circle at 28% 0%, rgba(168, 85, 247, 0.34), transparent 34%),
                    linear-gradient(180deg, rgba(31, 18, 57, 0.86) 0%, rgba(24, 17, 45, 0.9) 50%, rgba(17, 13, 32, 0.94) 100%);
                backdrop-filter: blur(28px) saturate(155%);
                -webkit-backdrop-filter: blur(28px) saturate(155%);
                border-right: 1px solid rgba(255, 255, 255, 0.12);
                z-index: 1000;
                display: flex;
                flex-direction: column;
                box-shadow: 12px 0 50px rgba(46, 16, 101, 0.3);
                transition: all 0.35s cubic-bezier(0.4,0,0.2,1);
            }

            /* RECRUITER SIDEBAR THEME */
            aside#main-sidebar.sidebar-recruiter {
                background: 
                    radial-gradient(circle at 20% 0%, rgba(139, 92, 246, 0.25), transparent 40%),
                    radial-gradient(circle at 80% 100%, rgba(79, 70, 229, 0.15), transparent 40%),
                    linear-gradient(180deg, rgba(30, 20, 60, 0.85) 0%, rgba(20, 15, 45, 0.92) 50%, rgba(15, 10, 35, 0.95) 100%);
                backdrop-filter: blur(24px) saturate(140%);
                -webkit-backdrop-filter: blur(24px) saturate(140%);
                border-right: 1px solid rgba(139, 92, 246, 0.15);
                box-shadow: 12px 0 50px rgba(79, 70, 229, 0.25);
            }

            aside#main-sidebar.sidebar-recruiter::before {
                background: 
                    linear-gradient(90deg, rgba(255,255,255,0.06), transparent 42%),
                    linear-gradient(180deg, rgba(139, 92, 246, 0.12), transparent 34%);
            }

            aside#main-sidebar.sidebar-recruiter .nav-link.active-item {
                background: linear-gradient(135deg, rgba(139, 92, 246, 0.35), rgba(255, 255, 255, 0.08));
                box-shadow: 0 14px 30px rgba(79, 70, 229, 0.25), inset 0 1px 0 rgba(255,255,255,0.12);
                position: relative;
                overflow: hidden;
            }
            aside#main-sidebar.sidebar-recruiter .nav-link.active-item::after {
                content: '';
                position: absolute;
                top: 0;
                left: -75%;
                width: 50%;
                height: 100%;
                background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
                animation: light-sweep 3s ease-in-out infinite;
                pointer-events: none;
            }

            aside#main-sidebar.sidebar-recruiter .nav-link.active-item::before {
                background: linear-gradient(180deg, #c4b5fd, #8b5cf6);
                box-shadow: 0 0 18px rgba(139, 92, 246, 0.5);
            }

            aside#main-sidebar.sidebar-recruiter .upgrade-strip {
                background: linear-gradient(135deg, rgba(139, 92, 246, 0.25), rgba(255, 255, 255, 0.08));
                border-color: rgba(139, 92, 246, 0.2);
            }

            aside#main-sidebar.sidebar-recruiter .logo-icon-box {
                background: linear-gradient(135deg, #ffffff 0%, #f3e8ff 100%);
                color: #6d28d9;
            }

            aside#main-sidebar.sidebar-recruiter .strength-bar-fill {
                background: linear-gradient(90deg, #8b5cf6 0%, #a78bfa 55%, #c4b5fd 100%);
            }

            aside#main-sidebar::before {
                content: '';
                position: absolute;
                inset: 0;
                pointer-events: none;
                background:
                    linear-gradient(90deg, rgba(255,255,255,0.09), transparent 42%),
                    linear-gradient(180deg, rgba(167,139,250,0.2), transparent 34%);
            }

            /* NAV LINKS */
            .nav-link {
                display: flex;
                align-items: center;
                gap: 12px;
                padding: 10px 13px;
                margin: 2px 12px;
                border-radius: 12px;
                text-decoration: none;
                color: rgba(237,233,254,0.76);
                transition: all 0.22s ease;
                position: relative;
                font-weight: 700;
                font-size: 13px;
                letter-spacing: 0;
            }
            .nav-link i {
                width: 18px;
                text-align: center;
                font-size: 14px;
                flex-shrink: 0;
                opacity: 0.7;
                transition: opacity 0.2s;
            }
            .nav-link:hover {
                background: rgba(255,255,255,0.1);
                color: #ffffff;
                transform: translateX(2px);
            }
            .nav-link:hover i { opacity: 1; }
                        .nav-link.active-item {
                background: linear-gradient(135deg, rgba(124, 58, 237, 0.34), rgba(255, 255, 255, 0.12));
                color: #ffffff !important;
                border: 1px solid rgba(255, 255, 255, 0.18);
                transform: translateX(2px);
                font-weight: 700;
                box-shadow: 0 14px 30px rgba(88, 28, 135, 0.28), inset 0 1px 0 rgba(255,255,255,0.12);
                position: relative;
                overflow: hidden;
            }
            .nav-link.active-item::after {
                content: '';
                position: absolute;
                top: 0;
                left: -75%;
                width: 50%;
                height: 100%;
                background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
                animation: light-sweep 3s ease-in-out infinite;
                pointer-events: none;
            }
            @keyframes light-sweep {
                0% { left: -75%; }
                100% { left: 125%; }
            }
            .nav-link.active-item i { opacity: 1; color: #ddd6fe; }
            .nav-link.active-item::before {
                content: '';
                position: absolute;
                left: -10px;
                top: 10px;
                bottom: 10px;
                width: 3px;
                background: linear-gradient(180deg, #ddd6fe, #a855f7);
                border-radius: 999px;
                box-shadow: 0 0 18px rgba(192, 132, 252, 0.58);
                z-index: 10;
            }

            [data-theme="dark"] .nav-link:hover {
                background: rgba(99, 102, 241, 0.1);
            }

            [data-theme="dark"] .nav-link.active-item {
                background: linear-gradient(135deg, #6366F1 0%, #818CF8 100%);
                color: white !important;
                box-shadow: 0 0 20px rgba(99, 102, 241, 0.3);
                position: relative;
                overflow: hidden;
            }
            [data-theme="dark"] .nav-link.active-item::after {
                content: '';
                position: absolute;
                top: 0;
                left: -75%;
                width: 50%;
                height: 100%;
                background: linear-gradient(90deg, transparent, rgba(255,255,255,0.15), transparent);
                animation: light-sweep 3s ease-in-out infinite;
                pointer-events: none;
            }

            /* ACCESSIBILITY */
            .nav-link:focus-visible {
                outline: 2px solid var(--primary);
                outline-offset: 2px;
            }

            .sidebar-collapse-btn:focus-visible,
            .mobile-menu-toggle:focus-visible,
            .notification-bell:focus-visible,
            .theme-toggle:focus-visible {
                outline: 2px solid var(--primary);
                outline-offset: 2px;
            }

            /* SEARCH INPUT */
            .header-search-input {
                width: 100%;
                max-width: 400px;
                padding: 12px 20px 12px 52px;
                border-radius: 12px;
                border: 1px solid var(--border-light);
                background: var(--glass-bg);
                backdrop-filter: blur(10px);
                color: var(--text-main);
                font-size: 14px;
                transition: all 0.2s ease;
            }

            .header-search-input:focus {
                outline: none;
                border-color: var(--primary);
                box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.12);
            }

            .header-search-input::placeholder {
                color: #94a3b8;
            }

            [data-theme="dark"] .header-search-input {
                background: rgba(15, 23, 42, 0.85);
                border-color: var(--border-dark);
                color: var(--text-light);
            }

            [data-theme="dark"] .header-search-input::placeholder {
                color: #64748b;
            }

            /* SEARCH DROPDOWN */
            .search-dropdown {
                background: var(--glass-bg);
                backdrop-filter: blur(20px);
                border-color: var(--glass-border);
            }

            [data-theme="dark"] .search-dropdown {
                background: rgba(15, 23, 42, 0.95);
                border-color: var(--border-dark);
            }

            .sidebar-section-header {
                font-size: 10px;
                font-weight: 800;
                color: rgba(221,214,254,0.58);
                text-transform: uppercase;
                letter-spacing: 0.12em;
                margin: 18px 22px 6px;
                padding-left: 2px;
            }

            .collapsible-nav-group {
                margin: 0 12px;
            }

            .collapsible-nav-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 8px 10px;
                cursor: pointer;
                border-radius: 8px;
                transition: background 0.2s ease;
            }

            .collapsible-nav-header:hover {
                background: rgba(255,255,255,0.06);
            }

            .collapsible-nav-chevron {
                transition: transform 0.2s ease;
            }

            .collapsible-nav-items {
                overflow: hidden;
            }

            .collapsible-nav-items .nav-link {
                margin: 2px 0;
            }


            /* PROFILE STRENGTH */
            .sidebar-profile-strength {
                margin: 0;
                padding: 0;
            }
            .strength-bar-bg {
                height: 3px;
                background: rgba(255,255,255,0.1);
                border-radius: 2px;
                margin-top: 6px;
                overflow: hidden;
            }
            .strength-bar-fill {
                height: 100%;
                background: linear-gradient(90deg, #8B5CF6 0%, #C084FC 55%, #F0ABFC 100%);
                border-radius: 2px;
                transition: width 1.2s cubic-bezier(0.16,1,0.3,1);
            }

            /* CUSTOM SCROLLBAR FOR NAV */
            nav::-webkit-scrollbar {
                width: 4px;
            }
            nav::-webkit-scrollbar-track {
                background: transparent;
            }
            nav::-webkit-scrollbar-thumb {
                background: rgba(99, 102, 241, 0.1);
                border-radius: 10px;
            }
            nav::-webkit-scrollbar-thumb:hover {
                background: rgba(99, 102, 241, 0.3);
            }

            aside#main-sidebar .sidebar-collapse-btn {
                position: absolute;
                top: 28px;
                right: -14px;
                width: 28px;
                height: 28px;
                border-radius: 999px;
                border: 1px solid rgba(139, 92, 246, 0.3);
                background: linear-gradient(135deg, rgba(139, 92, 246, 0.9), rgba(109, 40, 217, 0.9));
                color: #ffffff;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 10px;
                cursor: pointer;
                box-shadow: 0 4px 16px rgba(109, 40, 217, 0.4);
                z-index: 10;
                transition: all 0.2s ease;
            }
            aside#main-sidebar .sidebar-collapse-btn:hover {
                background: linear-gradient(135deg, rgba(167, 139, 250, 0.95), rgba(139, 92, 246, 0.95));
                color: white;
                border-color: rgba(167, 139, 250, 0.5);
                transform: scale(1.08);
            }

            .logo-container {
                padding: 20px 18px;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 14px;
                border-bottom: 1px solid rgba(255,255,255,0.06);
                margin-bottom: 8px;
                position: relative;
                z-index: 1;
                transition: all 0.3s ease;
                height: 72px;
            }
            .sidebar-logo-img {
                display: block;
                object-fit: contain;
                max-width: 140px;
                width: auto;
                height: auto;
            }
            body.sidebar-collapsed .sidebar-logo-img {
                max-width: 36px !important;
                max-height: 36px !important;
                width: 36px !important;
                height: 36px !important;
                object-fit: contain !important;
            }
            .logo-icon-box {
                display: flex;
                align-items: center;
                justify-content: center;
                flex-shrink: 0;
            }
            .logo-text-box {
                font-family: 'Outfit', sans-serif;
                font-size: 19px;
                font-weight: 800;
                color: #ffffff;
                letter-spacing: -0.02em;
            }
            .sidebar-section-label {
                font-size: 9px;
                letter-spacing: .12em;
                font-weight: 800;
                color: rgba(100,116,139,0.7);
                text-transform: uppercase;
                padding: 20px 20px 6px 20px;
            }

            /* MOBILE MENU */
            @media (max-width: 1024px) {
                aside#main-sidebar {
                    left: -100%;
                    transition: left 0.4s cubic-bezier(0.4, 0, 0.2, 1);
                }
                aside#main-sidebar.mobile-open {
                    left: 0;
                }
                .mobile-overlay {
                    position: fixed;
                    inset: 0;
                    background: rgba(0, 0, 0, 0.4);
                    backdrop-filter: blur(4px);
                    z-index: 999;
                    display: none;
                    opacity: 0;
                    transition: opacity 0.3s ease;
                }
                .mobile-overlay.active {
                    display: block;
                    opacity: 1;
                }
                .sidebar-collapse-btn {
                    display: none !important;
                }
            }

            .nav-badge {
                padding: 2px 7px;
                border-radius: 6px;
                font-size: 10px;
                font-weight: 800;
                margin-left: auto;
            }
            .nav-badge.new { background: rgba(255,255,255,0.13); color: #f5d0fe; border: 1px solid rgba(255,255,255,0.18); }
            .nav-badge.count { background: #6366f1; color: white; }
            .nav-badge.alert { background: rgba(239,68,68,0.2); color: #fca5a5; }

            /* UPGRADE STRIP */
            .upgrade-strip {
                margin: 14px 12px 8px;
                padding: 12px 13px;
                border-radius: 14px;
                background: linear-gradient(135deg, rgba(124,58,237,0.28), rgba(255,255,255,0.1));
                border: 1px solid rgba(255,255,255,0.16);
                display: flex;
                align-items: center;
                gap: 10px;
                text-decoration: none;
                transition: all 0.2s ease;
                flex-shrink: 0;
            }
            .upgrade-strip:hover {
                background: linear-gradient(135deg, rgba(124,58,237,0.38), rgba(255,255,255,0.14));
                border-color: rgba(255,255,255,0.2);
                transform: translateY(-1px);
            }
            .upgrade-strip-icon {
                width: 28px; height: 28px;
                border-radius: 9px;
                background: rgba(255,255,255,0.84);
                display: flex; align-items: center; justify-content: center;
                flex-shrink: 0;
                font-size: 13px;
                color: #7C3AED;
            }
            .upgrade-strip-text { flex: 1; min-width: 0; overflow: hidden; }
            .upgrade-strip-text h5 {
                margin: 0; font-size: 12px; font-weight: 700;
                color: #ffffff; white-space: nowrap;
            }
            .upgrade-strip-text p {
                margin: 2px 0 0; font-size: 10px; color: rgba(203,213,225,0.72);
                white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
            }

            .sidebar-user-section {
                padding: 12px;
                border-top: 1px solid rgba(255,255,255,0.08);
                background: rgba(255,255,255,0.06);
                flex-shrink: 0;
            }
            .sidebar-user-card {
                display: flex;
                align-items: center;
                gap: 10px;
                padding: 8px 10px;
                border-radius: 14px;
                transition: all 0.2s ease;
                text-decoration: none;
                cursor: pointer;
            }
            .sidebar-user-card:hover {
                background: rgba(255,255,255,0.08);
            }
            .sidebar-avatar {
                width: 36px; height: 36px;
                border-radius: 12px;
                object-fit: cover;
                border: 2px solid rgba(255,255,255,0.16);
                flex-shrink: 0;
            }
            .sidebar-user-info h5 {
                margin: 0; font-size: 12.5px; font-weight: 800;
                color: #ffffff; white-space: nowrap; overflow: hidden;
                text-overflow: ellipsis; max-width: 140px;
            }
            .sidebar-user-info p {
                margin: 2px 0 0; font-size: 10px; color: rgba(203,213,225,0.62);
                text-transform: capitalize;
            }


            /* HEADER */
            #main-wrapper {
                margin-left: var(--sidebar-width);
                transition: margin-left .2s ease;
            }

            header#candway-top-header {
                position: fixed;
                top: 0;
                left: var(--sidebar-width);
                right: 0;
                height: 76px;
                z-index: 900;
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 0 32px;
                background: rgba(255, 255, 255, 0.48);
                backdrop-filter: blur(24px) saturate(160%);
                -webkit-backdrop-filter: blur(24px) saturate(160%);
                border-bottom: 1px solid rgba(255, 255, 255, 0.52);
                box-shadow: 0 18px 45px -34px rgba(88, 28, 135, 0.42);
                transition: all .3s cubic-bezier(0.4, 0, 0.2, 1);
            }

            [data-theme="dark"] header#candway-top-header {
                background: rgba(15, 23, 42, 0.95);
                border-bottom-color: var(--border-dark);
            }

            /* MOBILE RESPONSIVE */
            @media (max-width: 1024px) {
                aside#main-sidebar {
                    transform: translateX(-100%);
                    width: var(--sidebar-width);
                }

                aside#main-sidebar.mobile-open {
                    transform: translateX(0);
                }

                body.mobile-menu-open::before {
                    content: '';
                    position: fixed;
                    inset: 0;
                    background: rgba(0, 0, 0, 0.5);
                    z-index: 999;
                    backdrop-filter: blur(2px);
                }

                #main-wrapper {
                    margin-left: 0 !important;
                }

                header#candway-top-header {
                    left: 0;
                    padding: 0 20px;
                }

                .mobile-menu-toggle {
                    display: flex !important;
                    position: fixed;
                    top: 20px;
                    left: 20px;
                    z-index: 1001;
                    width: 44px;
                    height: 44px;
                    border-radius: 12px;
                    background: var(--glass-bg);
                    backdrop-filter: blur(20px);
                    border: 1px solid var(--glass-border);
                    color: var(--text-main);
                    align-items: center;
                    justify-content: center;
                    cursor: pointer;
                    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
                    transition: all 0.2s ease;
                }

                .mobile-menu-toggle:hover {
                    background: var(--primary);
                    color: white;
                    transform: scale(1.05);
                }

                .header-search-container {
                    display: none;
                }

                .header-actions {
                    gap: 12px;
                }
            }

            @media (min-width: 1025px) {
                .mobile-menu-toggle {
                    display: none !important;
                }
            }

            .header-search-container {
                flex: 1;
                max-width: 440px;
            }

            .topbar-primary-action {
                height: 44px;
                padding: 0 16px;
                border-radius: 14px;
                border: 1px solid rgba(124,58,237,0.22);
                background: linear-gradient(135deg, rgba(124,58,237,0.96), rgba(91,33,182,0.96));
                color: #fff;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                gap: 9px;
                text-decoration: none;
                font-size: 13px;
                font-weight: 800;
                box-shadow: 0 18px 34px -22px rgba(88, 28, 135, 0.8);
                white-space: nowrap;
                transition: transform 0.2s ease, box-shadow 0.2s ease, filter 0.2s ease;
            }

            .topbar-primary-action:hover {
                transform: translateY(-1px);
                filter: brightness(1.03);
                box-shadow: 0 22px 42px -24px rgba(88, 28, 135, 0.9);
            }

            body.role-recruiter .topbar-primary-action {
                border-color: rgba(99, 102, 241, 0.22);
                background: linear-gradient(135deg, rgba(99, 102, 241, 0.96), rgba(79, 70, 229, 0.96));
                box-shadow: 0 18px 34px -22px rgba(55, 48, 163, 0.8);
            }

            body.role-recruiter .topbar-primary-action:hover {
                box-shadow: 0 22px 42px -24px rgba(55, 48, 163, 0.9);
            }

            .topbar-icon-btn {
                width: 44px;
                height: 44px;
                background: rgba(255,255,255,0.58);
                border-radius: 14px;
                display: flex;
                align-items: center;
                justify-content: center;
                color: #6b7280;
                position: relative;
                cursor: pointer;
                border: 1px solid rgba(255,255,255,0.64);
                backdrop-filter: blur(16px);
                transition: all 0.2s ease;
            }

            .topbar-icon-btn:hover {
                color: var(--primary);
                border-color: rgba(124,58,237,0.22);
                background: rgba(255,255,255,0.74);
            }

            .header-search-input {
                width: 100%;
                height: 48px;
                padding: 0 20px 0 52px;
                background: rgba(255,255,255,0.7);
                border: 1px solid rgba(203,213,225,0.5);
                border-radius: 12px;
                font-size: 14px;
                color: var(--text-main);
            }
            .header-search-input::placeholder {
                color: #94a3b8;
            }

            .header-avatar {
                width: 44px;
                height: 44px;
                border-radius: 12px;
                object-fit: cover;
            }

            main {
                padding-left: 24px;
                padding-top: 80px;
            }

            @media (max-width: 1024px) {
                #main-wrapper {
                    margin-left: 0 !important;
                }

                header#candway-top-header {
                    left: 0;
                }
            }

            @media (max-width: 680px) {
                header#candway-top-header {
                    height: auto;
                    min-height: 72px;
                    padding: 12px 14px 12px 72px;
                    gap: 10px;
                    flex-wrap: wrap;
                }

                .topbar-primary-action {
                    height: 40px;
                    padding: 0 12px;
                    font-size: 12px;
                }

                .topbar-icon-btn,
                .header-avatar {
                    width: 40px !important;
                    height: 40px !important;
                    border-radius: 12px !important;
                }
            }

            body.sidebar-collapsed #main-wrapper {
                margin-left: var(--sidebar-width-collapsed);
            }

            body.sidebar-collapsed header#candway-top-header {
                left: var(--sidebar-width-collapsed);
            }

            body.sidebar-collapsed aside#main-sidebar {
                width: var(--sidebar-width-collapsed);
            }

            body.sidebar-collapsed .logo-text-box,
            body.sidebar-collapsed .nav-label,
            body.sidebar-collapsed .nav-badge,
            body.sidebar-collapsed .upgrade-strip,
            body.sidebar-collapsed .sidebar-user-info,
            body.sidebar-collapsed .sidebar-section-header {
                opacity: 0;
                pointer-events: none;
                width: 0;
                overflow: hidden;
                white-space: nowrap;
            }

            .logo-text-box, .nav-label, .nav-badge, .upgrade-strip, .sidebar-user-info {
                transition: opacity 0.2s ease, width 0.2s ease;
            }

            /* DROPDOWN COMMON */
            .candway-dropdown {
                position: absolute;
                top: calc(100% + 12px);
                right: 0;
                width: 320px;
                background: var(--glass-bg);
                backdrop-filter: blur(28px) saturate(160%);
                border: 1px solid var(--glass-border);
                border-radius: 20px;
                box-shadow: 0 24px 50px -12px rgba(88, 28, 135, 0.25);
                z-index: 1001;
                display: none;
                flex-direction: column;
                overflow: hidden;
                transform-origin: top right;
                animation: dropdownFadeIn 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards;
            }

            .candway-dropdown.active {
                display: flex;
            }

            @keyframes dropdownFadeIn {
                from { opacity: 0; transform: scale(0.95) translateY(-10px); }
                to { opacity: 1; transform: scale(1) translateY(0); }
            }

            .dropdown-header {
                padding: 18px 20px;
                border-bottom: 1px solid var(--border-light);
                display: flex;
                align-items: center;
                justify-content: space-between;
            }

            .dropdown-header h4 {
                margin: 0;
                font-size: 15px;
                font-weight: 800;
                color: var(--text-main);
            }

            .dropdown-content {
                max-height: 380px;
                overflow-y: auto;
            }

            .dropdown-item {
                padding: 14px 20px;
                display: flex;
                gap: 12px;
                text-decoration: none;
                color: var(--text-main);
                transition: background 0.2s ease;
                border-bottom: 1px solid rgba(167, 139, 250, 0.08);
            }

            .dropdown-item:last-child {
                border-bottom: none;
            }

            .dropdown-item:hover {
                background: rgba(124, 58, 237, 0.06);
            }

            .dropdown-footer {
                padding: 14px;
                background: rgba(124, 58, 237, 0.04);
                text-align: center;
                border-top: 1px solid var(--border-light);
            }

            .dropdown-footer-link {
                color: var(--primary);
                text-decoration: none;
                font-size: 13px;
                font-weight: 700;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 6px;
            }

            .dropdown-footer-link:hover {
                text-decoration: underline;
            }

            .message-dot {
                width: 8px;
                height: 8px;
                background: var(--primary);
                border-radius: 50%;
                flex-shrink: 0;
                margin-top: 6px;
            }
        `;
        document.head.appendChild(style);
    }

    static getUserAvatar(name, photoUrl = null) {
        // Use real photo if available
        if (photoUrl) {
            return photoUrl;
        }

        // Try cached avatar first
        const cached = localStorage.getItem('userAvatar');
        if (cached && !cached.includes('ui-avatars') && !cached.startsWith('data:')) {
            return cached;
        }

        // Generate fallback SVG
        const initials = name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
        const role = localStorage.getItem('role') || 'candidate';
        const fillColor = role === 'recruiter' ? '#10b981' : '#6366f1';
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="44" height="44" viewBox="0 0 44 44">
            <circle cx="22" cy="22" r="22" fill="${fillColor}"/>
            <text x="22" y="23" font-family="Plus Jakarta Sans" font-size="17" font-weight="700"
                  fill="white" text-anchor="middle" dominant-baseline="central">${initials}</text>
        </svg>`;
        const avatarUrl = `data:image/svg+xml;base64,${btoa(svg)}`;

        // Try external API with fallback
        const img = new Image();
        const externalUrl = `https://ui-avatars.com/api/?name=${encodeURIComponent(name)}&background=6366F1&color=fff&bold=true&size=44`;

        img.onload = () => {
            localStorage.setItem('userAvatar', externalUrl);
        };

        img.onerror = () => {
            localStorage.setItem('userAvatar', avatarUrl);
        };

        img.src = externalUrl;

        return avatarUrl; // Return fallback immediately
    }

    static getDisplayName() {
        const raw = localStorage.getItem('userName') || 'User';
        if (raw.includes('@')) {
            return raw.split('@')[0].replace(/[._-]/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
        }
        return raw;
    }

    static renderSidebar(activePage) {
        const name = this.getDisplayName();
        const role = localStorage.getItem('role') || 'candidate';
        const photoUrl = localStorage.getItem('userPhotoUrl');
        const pathname = window.location.pathname;
        const profileStrength = parseInt(localStorage.getItem('profileStrength') || '65');

        const navGroups = role === 'recruiter' ? [
            {
                label: 'Overview', i18n: 'recruiter.sidebar.overview',
                items: [
                    { id: 'nav_dashboard', href: '/recruiter/dashboard', icon: 'fa-gauge-high', text: 'Dashboard', i18n: 'recruiter.sidebar.dashboard' },
                    { id: 'nav_jobs', href: '/recruiter/jobs', icon: 'fa-briefcase', text: 'Jobs', i18n: 'recruiter.sidebar.jobs' },
                    { id: 'nav_job_wizard', href: '/recruiter/job-wizard', icon: 'fa-wand-magic-sparkles', text: 'Create Job (Skill-First)', i18n: 'recruiter.sidebar.job_wizard' },
                    { id: 'nav_analytics', href: '/recruiter/analytics', icon: 'fa-chart-pie', text: 'Analytics', i18n: 'recruiter.sidebar.analytics' },
                    { id: 'nav_reports', href: '/recruiter/reports', icon: 'fa-file-alt', text: 'Reports', i18n: 'recruiter.sidebar.reports' }
                ]
            },
            {
                label: 'Candidates', i18n: 'recruiter.sidebar.candidates',
                items: [
                    { id: 'nav_candidates', href: '/recruiter/candidates', icon: 'fa-users', text: 'Candidates Management', i18n: 'recruiter.sidebar.candidates_management' }
                ]
            },
            {
                label: 'Operations', i18n: 'recruiter.sidebar.operations',
                items: [
                    { id: 'nav_pipeline', href: '/recruiter/pipeline', icon: 'fa-users-rectangle', text: 'Talent Pipeline', i18n: 'recruiter.sidebar.talent_pipeline' },
                    { id: 'nav_campaigns', href: '/recruiter/campaigns', icon: 'fa-bullhorn', text: 'Campaign Manager', i18n: 'recruiter.sidebar.campaign_manager' },
                    { id: 'nav_interviews', href: '/recruiter/interviews', icon: 'fa-video', text: 'Interviews', i18n: 'recruiter.sidebar.interviews' }
                ]
            },
            {
                label: 'Skills', i18n: 'recruiter.sidebar.skills',
                items: [
                    { id: 'nav_skill_tree_library', href: '/recruiter/skill-tree-library', icon: 'fa-tree', text: 'Skills Library', i18n: 'recruiter.sidebar.skills_library' }
                ]
            },
            {
                label: 'Administration', i18n: 'recruiter.sidebar.administration',
                items: [
                    { id: 'nav_team', href: '/recruiter/team', icon: 'fa-user-group', text: 'Team', i18n: 'recruiter.sidebar.team' },
                    { id: 'nav_settings', href: '/recruiter/settings', icon: 'fa-sliders', text: 'Settings', i18n: 'recruiter.sidebar.settings' },
                    { id: 'nav_help', href: '#', icon: 'fa-circle-question', text: 'Help & Guide', i18n: 'recruiter.sidebar.help', onclick: 'HelpCenter.openModal(); return false;' }
                ]
            }
        ] : [
            {
                label: 'Intelligence', i18n: 'candidate.sidebar.intelligence',
                items: [
                    { id: 'nav_overview', href: '/candidate/dashboard', icon: 'fa-house-chimney', text: 'Dashboard', i18n: 'candidate.sidebar.dashboard' },
                    { id: 'nav_profile', href: '/candidate/profile', icon: 'fa-user', text: 'Profile', i18n: 'candidate.sidebar.profile' },
                    { id: 'nav_learning', href: '/candidate/learning', icon: 'fa-graduation-cap', text: 'Learning', i18n: 'candidate.sidebar.learning' }
                ]
            },
            {
                label: 'Pipeline', i18n: 'candidate.sidebar.pipeline',
                items: [
                    { id: 'nav_jobs', href: '/candidate/jobs', icon: 'fa-briefcase', text: 'Jobs', i18n: 'candidate.sidebar.jobs' }
                ]
            },
            {
                label: 'Tracking', i18n: 'candidate.sidebar.tracking',
                collapsible: true,
                items: [
                    { id: 'nav_applications', href: '/candidate/applications', icon: 'fa-folder-open', text: 'Applications', i18n: 'candidate.sidebar.applications' },
                    { id: 'nav_interviews', href: '/candidate/interviews', icon: 'fa-calendar-check', text: 'Interviews', i18n: 'candidate.sidebar.interviews' }
                ]
            },
            {
                label: 'Account', i18n: 'candidate.sidebar.account',
                items: [
                    { id: 'nav_settings', href: '/candidate/settings', icon: 'fa-gear', text: 'Settings', i18n: 'candidate.sidebar.settings' }
                ]
            }
        ];

        const isActive = (item) => {
            const pathMatch = pathname === item.href || pathname.startsWith(item.href + '/') || pathname.startsWith(item.href + '?');
            if (pathMatch) return true;
            if (activePage && item.id === activePage) return true;
            return false;
        };

        let groupsHTML = '';
        navGroups.forEach((group, index) => {
            const isCollapsible = group.collapsible;
            const groupId = `nav-group-${index}`;
            
            if (isCollapsible) {
                const hasActive = group.items.some(item => isActive(item));
                const groupLabel = group.label;
                groupsHTML += `
                    <div class="collapsible-nav-group" data-group="${groupId}">
                        <div class="collapsible-nav-header" onclick="Components.toggleNavGroup('${groupId}')">
                            <span class="sidebar-section-header" style="margin:0;padding:0;cursor:pointer;flex:1;" data-i18n="${group.i18n || ''}">${groupLabel}</span>
                            <i class="fas fa-chevron-down collapsible-nav-chevron" style="font-size:10px;color:rgba(221,214,254,0.58);transition:transform 0.2s ease;"></i>
                        </div>
                        <div class="collapsible-nav-items" style="max-height:${hasActive ? '500px' : '0'};overflow:hidden;transition:max-height 0.3s ease;">
                `;
                group.items.forEach(item => {
                    const activeClass = isActive(item) ? 'active-item' : '';
                    const onclickAttr = item.onclick ? `onclick="${item.onclick}"` : '';
                    const itemLabel = item.text;
                    groupsHTML += `
                        <a href="${item.href}" title="${itemLabel}" class="nav-link ${activeClass}" style="padding-left:28px;" ${onclickAttr}>
                            <i class="fa-solid ${item.icon}"></i>
                            <span class="nav-label" data-i18n="${item.i18n || ''}">${itemLabel}</span>
                            ${item.badge ? `<span class="nav-badge ${item.badgeType}">${item.badge}</span>` : ''}
                        </a>
                    `;
                });
                groupsHTML += `</div></div>`;
            } else {
                const groupLabel = group.label;
                groupsHTML += `<div class="sidebar-section-header" data-i18n="${group.i18n || ''}">${groupLabel}</div>`;
                group.items.forEach(item => {
                    const activeClass = isActive(item) ? 'active-item' : '';
                    const onclickAttr = item.onclick ? `onclick="${item.onclick}"` : '';
                    const itemLabel = item.text;
                    groupsHTML += `
                        <a href="${item.href}" title="${itemLabel}" class="nav-link ${activeClass}" ${onclickAttr}>
                            <i class="fa-solid ${item.icon}"></i>
                            <span class="nav-label" data-i18n="${item.i18n || ''}">${itemLabel}</span>
                            ${item.badge ? `<span class="nav-badge ${item.badgeType}">${item.badge}</span>` : ''}
                        </a>
                    `;
                });
            }
        });

        const sidebarHTML = `
        <div class="mobile-overlay" id="mobile-sidebar-overlay" onclick="Components.toggleMobileMenu()"></div>
        <aside id="main-sidebar" class="${role === 'recruiter' ? 'sidebar-recruiter' : ''}">
            <button class="sidebar-collapse-btn" onclick="Components.toggleSidebar()" aria-label="Toggle sidebar">
                <i class="fas fa-chevron-left"></i>
            </button>
    <a href="${role === 'recruiter' ? '/recruiter/dashboard' : '/candidate/dashboard'}" class="logo-container" style="text-decoration:none;padding:16px 18px;display:flex;align-items:center;justify-content:center;overflow:hidden;height:72px;">
        <img src="/assets/images/candway_logo.png" class="sidebar-logo-img" alt="Candway" style="max-width:140px;width:auto;height:auto;object-fit:contain;display:block;">
    </a>
            <nav style="flex:1;overflow-y:auto;padding:4px 0 8px;scrollbar-width:thin;scrollbar-color:rgba(99,102,241,0.15) transparent;">
                ${groupsHTML}
            </nav>
            <a href="${role === 'recruiter' ? '/recruiter/subscription' : '/subscription'}" class="upgrade-strip nav-label">
                <div class="upgrade-strip-icon"><i class="fas fa-arrow-trend-up"></i></div>
                <div class="upgrade-strip-text">
                    <h5 data-i18n="${role === 'recruiter' ? 'recruiter.sidebar.talent_accelerator' : 'candidate.sidebar.career_accelerator'}">${role === 'recruiter' ? 'Talent Accelerator' : 'Career Accelerator'}</h5>
                    <p data-i18n="${role === 'recruiter' ? 'recruiter.sidebar.ai_sourcing_subtitle' : 'candidate.sidebar.coaching_subtitle'}">${role === 'recruiter' ? 'AI Sourcing, priority matching' : 'Coaching, insights, priority matching'}</p>
                </div>
            </a>
            <div class="sidebar-user-section">
                <a href="${role === 'recruiter' ? '/recruiter/settings' : '/candidate/profile'}" class="sidebar-user-card">
                    <img src="${this.getUserAvatar(name, photoUrl)}" class="sidebar-avatar" alt="${name}" id="sidebar-avatar-img">
                    <div class="sidebar-user-info nav-label">
                        <h5 id="sidebar-user-name">${name}</h5>
                        <p data-i18n="${role === 'recruiter' ? 'recruiter.sidebar.recruiter_role' : 'candidate.sidebar.candidate_role'}">${role === 'recruiter' ? 'Recruiter' : 'Candidate'}</p>
                    </div>
                    <i class="fas fa-chevron-right nav-label" style="font-size:9px;color:rgba(100,116,139,0.4);margin-left:auto;flex-shrink:0;"></i>
                </a>
                <div class="nav-label" style="padding:0 6px;margin-top:8px;">
                    <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                        <span style="font-size:9px;font-weight:700;color:rgba(100,116,139,0.65);text-transform:uppercase;letter-spacing:.1em;" data-i18n="${role === 'recruiter' ? 'recruiter.sidebar.usage_balance' : 'candidate.sidebar.profile_strength'}">${role === 'recruiter' ? 'Usage Balance' : 'Profile Strength'}</span>
                        <span style="font-size:9px;font-weight:800;color:${role === 'recruiter' ? '#10b981' : '#818cf8'};" id="sidebar-strength-pct">${profileStrength}%</span>
                    </div>
                    <div class="strength-bar-bg">
                        <div class="strength-bar-fill" id="sidebar-strength-bar" style="width:${profileStrength}%"></div>
                    </div>
                </div>
                <a href="/logout" style="display:flex;align-items:center;gap:8px;padding:8px 10px;margin-top:6px;border-radius:8px;font-size:11px;font-weight:600;color:rgba(100,116,139,0.6);text-decoration:none;transition:all 0.2s ease;" onmouseover="this.style.background='rgba(239,68,68,0.08)';this.style.color='#fca5a5';" onmouseout="this.style.background='';this.style.color='rgba(100,116,139,0.6)';">
                    <i class="fas fa-arrow-right-from-bracket" style="width:16px;text-align:center;font-size:11px;"></i>
                    <span class="nav-label" data-i18n="header.sign_out">Sign Out</span>
                </a>
            </div>
        </aside>
        `;

        const container = document.getElementById('sidebar-container');
        if (container) container.innerHTML = sidebarHTML;
    }

    static toggleSidebar() {
        const isCollapsed = document.body.classList.toggle('sidebar-collapsed');
        localStorage.setItem('candway_sidebar_collapsed', isCollapsed ? '1' : '0');
        const icon = document.querySelector('#main-sidebar .sidebar-collapse-btn i');
        if (icon) {
            const isRtl = document.documentElement.getAttribute('dir') === 'rtl';
            if (isRtl) {
                icon.className = `fas ${isCollapsed ? 'fa-chevron-left' : 'fa-chevron-right'}`;
            } else {
                icon.className = `fas ${isCollapsed ? 'fa-chevron-right' : 'fa-chevron-left'}`;
            }
        }
    }

    static applySidebarState() {
        const isCollapsed = localStorage.getItem('candway_sidebar_collapsed') === '1';
        document.body.classList.toggle('sidebar-collapsed', isCollapsed);
        const icon = document.querySelector('#main-sidebar .sidebar-collapse-btn i');
        if (icon) {
            const isRtl = document.documentElement.getAttribute('dir') === 'rtl';
            if (isRtl) {
                icon.className = `fas ${isCollapsed ? 'fa-chevron-left' : 'fa-chevron-right'}`;
            } else {
                icon.className = `fas ${isCollapsed ? 'fa-chevron-right' : 'fa-chevron-left'}`;
            }
        }
        
        document.querySelectorAll('.collapsible-nav-group').forEach(group => {
            const groupId = group.dataset.group;
            const isExpanded = localStorage.getItem(`candway_nav_group_${groupId}`) !== 'collapsed';
            const chevron = group.querySelector('.collapsible-nav-chevron');
            const items = group.querySelector('.collapsible-nav-items');
            if (chevron) chevron.style.transform = isExpanded ? 'rotate(0deg)' : 'rotate(-90deg)';
            if (items) items.style.maxHeight = isExpanded ? '500px' : '0';
        });
    }

    static initCrossTabSync() {
        window.addEventListener('storage', (e) => {
            if (e.key === 'candway_sidebar_collapsed') {
                Components.applySidebarState();
            }
        });
    }

    static toggleNavGroup(groupId) {
        const group = document.querySelector(`.collapsible-nav-group[data-group="${groupId}"]`);
        if (!group) return;
        
        const chevron = group.querySelector('.collapsible-nav-chevron');
        const items = group.querySelector('.collapsible-nav-items');
        const isExpanded = items.style.maxHeight !== '0px' && items.style.maxHeight !== '0';
        
        if (isExpanded) {
            items.style.maxHeight = '0';
            chevron.style.transform = 'rotate(-90deg)';
            localStorage.setItem(`candway_nav_group_${groupId}`, 'collapsed');
        } else {
            items.style.maxHeight = '500px';
            chevron.style.transform = 'rotate(0deg)';
            localStorage.setItem(`candway_nav_group_${groupId}`, 'expanded');
        }
    }

    static toggleMobileMenu() {
        const sidebar = document.getElementById('main-sidebar');
        const overlay = document.getElementById('mobile-sidebar-overlay');
        const container = document.getElementById('sidebar-container');
        const isOpen = document.body.classList.toggle('mobile-menu-open');

        if (sidebar) sidebar.classList.toggle('mobile-open', isOpen);
        if (overlay) overlay.classList.toggle('active', isOpen);
        if (container) container.classList.toggle('mobile-open', isOpen);

        document.body.style.overflow = isOpen ? 'hidden' : '';
    }

    static toggleTheme() {
        const currentTheme = localStorage.getItem('preferredTheme') || 'light';
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';
        localStorage.setItem('preferredTheme', newTheme);
        document.documentElement.setAttribute('data-theme', newTheme);

        const icon = document.querySelector('.theme-toggle i');
        if (icon) {
            icon.className = `fas ${newTheme === 'dark' ? 'fa-sun' : 'fa-moon'}`;
        }

        this.updateSidebarTheme();
    }

    static updateSidebarTheme() {
        const theme = localStorage.getItem('preferredTheme') || 'light';
        const sidebar = document.getElementById('main-sidebar');
        if (sidebar) {
            sidebar.setAttribute('data-theme', theme);
        }
    }

    static toggleNotifications(event) {
        if (event) event.stopPropagation();
        const dropdown = document.getElementById('notif-dropdown');
        if (!dropdown) return;

        const isActive = dropdown.classList.contains('active');
        Components.closeAllDropdowns();

        if (!isActive) {
            dropdown.classList.add('active');
            Components.loadNotifications();
            const closeHandler = (e) => {
                if (!dropdown.contains(e.target) && !document.getElementById('notif-trigger').contains(e.target)) {
                    dropdown.classList.remove('active');
                    document.removeEventListener('click', closeHandler);
                }
            };
            setTimeout(() => document.addEventListener('click', closeHandler), 10);
        }
    }

    static async loadNotifications() {
        const content = document.getElementById('notif-dropdown-content');
        if (!content) return;

        try {
            const data = await window.fetchAPI('/notifications/latest?limit=5');
            const notifications = data || [];

            if (notifications.length === 0) {
                content.innerHTML = `
                    <div class="dropdown-item" style="justify-content:center;padding:24px;cursor:default;">
                        <p style="margin:0;font-size:12px;color:var(--text-muted);">No notifications</p>
                    </div>
                `;
                return;
            }

            content.innerHTML = notifications.map(notif => `
                <div class="dropdown-item" style="${notif.is_read ? '' : 'background:rgba(124,58,237,0.04);'}cursor:pointer;" onclick="Components.markNotifRead(${notif.id})">
                    <div style="flex:1;min-width:0;">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2px;">
                            <span style="font-weight:${notif.is_read ? '500' : '700'};font-size:13px;color:var(--text-main);">${notif.title || 'Notification'}</span>
                            <span style="font-size:11px;color:var(--text-muted);">${Components._timeAgo(notif.created_at)}</span>
                        </div>
                        <p style="margin:0;font-size:12px;color:var(--text-muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${notif.message || ''}</p>
                    </div>
                    ${notif.is_read ? '' : '<div style="width:8px;height:8px;border-radius:50%;background:var(--primary);flex-shrink:0;margin-left:8px;"></div>'}
                </div>
            `).join('');
        } catch (e) {
            content.innerHTML = `
                <div class="dropdown-item" style="justify-content:center;padding:24px;cursor:default;">
                    <p style="margin:0;font-size:12px;color:var(--text-muted);">Could not load notifications</p>
                </div>
            `;
        }
    }

    static async loadUnreadNotifCount() {
        try {
            const data = await window.fetchAPI('/notifications/unread-count');
            const count = data?.unread_count || 0;
            const badge = document.getElementById('notif-badge');
            if (badge) badge.style.display = count > 0 ? 'block' : 'none';
        } catch (e) {
            // Silently fail — badge just won't show
        }
    }

    static async markAllNotifRead() {
        try {
            await window.fetchAPI('/notifications/mark-all-read', { method: 'POST' });
            const badge = document.getElementById('notif-badge');
            if (badge) badge.style.display = 'none';
            Components.loadNotifications();
        } catch (e) {
            console.error('Failed to mark all notifications as read:', e);
        }
    }

    static async markNotifRead(id) {
        try {
            await window.fetchAPI(`/notifications/${id}/mark-read`, { method: 'POST' });
            Components.loadNotifications();
            Components.loadUnreadNotifCount();
        } catch (e) {
            console.error('Failed to mark notification as read:', e);
        }
    }

    static toggleLangDropdown(event) {
        if (event) event.stopPropagation();
        const dropdown = document.getElementById('header-lang-dropdown');
        if (!dropdown) return;

        const isActive = dropdown.classList.contains('active');
        Components.closeAllDropdowns();

        if (!isActive) {
            dropdown.classList.add('active');
            const closeHandler = (e) => {
                if (!dropdown.contains(e.target) && !document.getElementById('lang-trigger').contains(e.target)) {
                    dropdown.classList.remove('active');
                    document.removeEventListener('click', closeHandler);
                }
            };
            setTimeout(() => document.addEventListener('click', closeHandler), 10);
        }
    }

    static toggleMessages(event) {
        if (event) event.stopPropagation();
        const dropdown = document.getElementById('messages-dropdown');
        if (!dropdown) return;

        const isActive = dropdown.classList.contains('active');
        this.closeAllDropdowns();

        if (!isActive) {
            dropdown.classList.add('active');
            this.loadMessages();

            const closeHandler = (e) => {
                if (!dropdown.contains(e.target) && !document.getElementById('messages-trigger').contains(e.target)) {
                    dropdown.classList.remove('active');
                    document.removeEventListener('click', closeHandler);
                }
            };
            setTimeout(() => document.addEventListener('click', closeHandler), 10);
        }
    }

    static closeAllDropdowns() {
        document.querySelectorAll('.candway-dropdown').forEach(d => d.classList.remove('active'));
    }

    static async loadMessages() {
        const content = document.getElementById('messages-dropdown-content');
        if (!content) return;

        const unreadLabel = document.getElementById('messages-unread-count');

        try {
            const data = await window.fetchAPI('/messages/conversations');
            const conversations = data || [];

            if (conversations.length === 0) {
                content.innerHTML = `
                    <div class="dropdown-item" style="justify-content:center;padding:24px;cursor:default;">
                        <p style="margin:0;font-size:12px;color:var(--text-muted);">No new messages</p>
                    </div>
                `;
                if (unreadLabel) unreadLabel.textContent = '0 New';
                const badge = document.getElementById('messages-badge');
                if (badge) badge.style.display = 'none';
                return;
            }

            const role = localStorage.getItem('role') || 'candidate';
            const messagesLink = role === 'recruiter' ? '/recruiter/messages' : '/candidate/messages';

            let totalUnread = 0;
            content.innerHTML = conversations.slice(0, 5).map(conv => {
                const p = conv.participant || {};
                totalUnread += conv.unread_count || 0;
                const initials = (p.name || 'U').split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
                return `
                    <a href="${messagesLink}" class="dropdown-item" onclick="event.stopPropagation();Components.closeAllDropdowns();">
                        <div style="width:40px; height:40px; border-radius:10px; background:rgba(124,58,237,0.1); display:flex; align-items:center; justify-content:center; color:var(--primary); font-weight:700; flex-shrink:0; overflow:hidden;">
                            ${p.avatar_url ? `<img src="${p.avatar_url}" style="width:100%;height:100%;object-fit:cover;">` : initials}
                        </div>
                        <div style="flex:1; min-width:0;">
                            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:2px;">
                                <span style="font-weight:700; font-size:13px; color:var(--text-main);">${p.name || 'Unknown'}</span>
                                <span style="font-size:11px; color:var(--text-muted);">${conv.last_message_at ? this._timeAgo(conv.last_message_at) : ''}</span>
                            </div>
                            <p style="margin:0; font-size:12px; color:var(--text-muted); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${conv.last_message_preview || 'No messages yet'}</p>
                        </div>
                        ${conv.unread_count > 0 ? '<div class="message-dot"></div>' : ''}
                    </a>
                `;
            }).join('');

            if (unreadLabel) unreadLabel.textContent = totalUnread > 0 ? totalUnread + ' New' : '0 New';
            const badge = document.getElementById('messages-badge');
            if (badge) badge.style.display = totalUnread > 0 ? 'block' : 'none';
        } catch (e) {
            content.innerHTML = `
                <div class="dropdown-item" style="justify-content:center;padding:24px;cursor:default;">
                    <p style="margin:0;font-size:12px;color:var(--text-muted);">Could not load messages</p>
                </div>
            `;
        }
    }

    static _timeAgo(dateStr) {
        if (!dateStr) return '';
        const diff = Date.now() - new Date(dateStr).getTime();
        if (diff < 60000) return 'now';
        const mins = Math.floor(diff / 60000);
        if (mins < 60) return mins + 'm';
        const hrs = Math.floor(mins / 60);
        if (hrs < 24) return hrs + 'h';
        return Math.floor(hrs / 24) + 'd';
    }

    static renderTopHeader() {
        const name = this.getDisplayName();
        const role = localStorage.getItem('role') || 'candidate';
        const photoUrl = localStorage.getItem('userPhotoUrl');
        const searchPlaceholder = role === 'recruiter' ? 'Search candidates, jobs...' : 'Search jobs, companies...';
        const postJobLabel = 'Post Job';
        const newAuditLabel = 'New audit';
        const notifTitle = 'Notifications';
        const markAllRead = 'Mark all read';
        const messagesTitle = 'Messages';
        const loadingText = 'Loading...';
        const viewAllNotif = 'View all notifications';
        const headerHTML = `
        <header id="candway-top-header">
            <button class="mobile-menu-toggle" onclick="Components.toggleMobileMenu()" aria-label="Toggle mobile menu">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg>
            </button>

            <div class="header-search-container">
                <div style="position:relative">
                    <i class="fas fa-search" style="position:absolute;left:20px;top:16px;color:var(--text-muted)"></i>
                    <input type="text" id="header-search-input" class="header-search-input" placeholder="${searchPlaceholder} (⌘K)" data-i18n-placeholder="${role === 'recruiter' ? 'header.search_recruiter' : 'header.search_candidate'}">
                </div>
            </div>
            <div class="header-actions" style="display:flex;align-items:center;gap:12px">
                <a href="${role === 'recruiter' ? '/recruiter/jobs' : '/onboarding'}" class="topbar-primary-action" title="${role === 'recruiter' ? postJobLabel : newAuditLabel}">
                    <i class="fas ${role === 'recruiter' ? 'fa-plus-circle' : 'fa-file-circle-check'}"></i>
                    <span data-i18n="${role === 'recruiter' ? 'header.post_job' : 'header.new_audit'}">${role === 'recruiter' ? postJobLabel : newAuditLabel}</span>
                </a>
                <div class="topbar-icon-btn" onclick="Components.toggleLangDropdown(event)" title="Language" id="lang-trigger" style="position:relative">
                    <i class="fas fa-globe"></i>
                    <div id="header-lang-dropdown" class="candway-dropdown" style="right:0;left:auto;width:auto;min-width:100px">
                        <div class="dropdown-item lang-option" data-lang="en" onclick="event.stopPropagation(); window.setLanguage('en');" style="gap:8px;padding:8px 16px;cursor:pointer">
                            <span>🇬🇧</span> EN
                        </div>
                        <div class="dropdown-item lang-option" data-lang="fr" onclick="event.stopPropagation(); window.setLanguage('fr');" style="gap:8px;padding:8px 16px;cursor:pointer">
                            <span>🇫🇷</span> FR
                        </div>
                        <div class="dropdown-item lang-option" data-lang="ar" onclick="event.stopPropagation(); window.setLanguage('ar');" style="gap:8px;padding:8px 16px;cursor:pointer">
                            <span>🇹🇳</span> AR
                        </div>
                    </div>
                </div>
                <div class="notification-bell topbar-icon-btn" onclick="Components.toggleNotifications(event)" title="${notifTitle}" id="notif-trigger" style="position:relative">
                    <i class="fas fa-bell"></i>
                    <span id="notif-badge" class="notification-badge" style="position:absolute;top:10px;right:10px;width:8px;height:8px;background:var(--danger);border-radius:50%;border:2px solid white;display:none"></span>
                    <div id="notif-dropdown" class="candway-dropdown" style="right:0;left:auto;width:320px">
                        <div class="dropdown-header">
                            <h3 data-i18n="header.notifications">${notifTitle}</h3>
                            <button onclick="Components.markAllNotifRead()" style="background:none;border:none;color:var(--primary);font-size:12px;cursor:pointer" data-i18n="header.mark_all_read">${markAllRead}</button>
                        </div>
                        <div class="dropdown-content" id="notif-dropdown-content">
                            <div style="padding:20px;text-align:center;color:var(--text-muted);font-size:13px" data-i18n="loading">${loadingText}</div>
                        </div>
                        <div class="dropdown-footer">
                            <a href="/notifications" data-i18n="recruiter.dashboard.ai_matches.view_all">${viewAllNotif}</a>
                        </div>
                    </div>
                </div>
                <div class="messages-dropdown-trigger topbar-icon-btn" onclick="Components.toggleMessages(event)" title="${messagesTitle}" id="messages-trigger">
                    <i class="fas fa-comment-dots"></i>
                    <span id="messages-badge" class="notification-badge" style="position:absolute;top:10px;right:10px;width:8px;height:8px;background:var(--primary);border-radius:50%;border:2px solid white;display:none"></span>
                    
                    <div id="messages-dropdown" class="candway-dropdown">
                        <div class="dropdown-header">
                            <h3 data-i18n="header.messages">${messagesTitle}</h3>
                            <span class="badge" id="messages-unread-count">0 New</span>
                        </div>
                        <div class="dropdown-content" id="messages-dropdown-content">
                            <span data-i18n="loading">${loadingText}</span>
                        </div>
                        <div class="dropdown-footer">
                            <a href="${role === 'recruiter' ? '/recruiter/messages' : '/candidate/messages'}" data-i18n="recruiter.dashboard.ai_matches.view_all">${viewAllNotif}</a>
                        </div>
                    </div>
                </div>
                <div class="user-profile-trigger" style="display:flex;align-items:center;gap:10px;padding:4px 4px 4px 12px;background:var(--primary-light);border-radius:50px;cursor:pointer;border:1px solid rgba(255,255,255,0.1)">
                    <div style="text-align:right" class="nav-label">
                        <div style="font-size:11px;font-weight:800;color:var(--text-main);line-height:1">${name}</div>
                        <div style="font-size:9px;font-weight:700;color:var(--primary);text-transform:uppercase;letter-spacing:0.05em;margin-top:2px;">${role}</div>
                    </div>
                    <img src="${this.getUserAvatar(name, photoUrl)}" style="width:32px;height:32px;border-radius:50%;object-fit:cover;border:2px solid white;box-shadow:0 4px 10px rgba(0,0,0,0.1)">
                </div>
            </div>
        </header>
        `;
        const container = document.getElementById('top-header-container') || document.getElementById('header-container') || document.getElementById('top-bar-extra') || document.getElementById('topbar-container');
        if (container) container.innerHTML = headerHTML;
        this.initSearch();
        this.loadUnreadNotifCount();
    }

    static initSearch() {
        const searchInput = document.getElementById('header-search-input');
        if (!searchInput) return;

        let searchTimeout;

        searchInput.addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            const query = e.target.value.trim();

            if (query.length < 2) {
                this.hideSearchResults();
                return;
            }

            searchTimeout = setTimeout(() => {
                this.performSearch(query);
            }, 300);
        });

        document.addEventListener('keydown', (e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
                e.preventDefault();
                searchInput.focus();
            }
            if (e.key === 'Escape') {
                searchInput.blur();
                this.hideSearchResults();
            }
        });

        searchInput.addEventListener('focus', () => {
            if (searchInput.value.trim().length >= 2) {
                this.performSearch(searchInput.value.trim());
            }
        });

        searchInput.addEventListener('blur', () => {
            setTimeout(() => this.hideSearchResults(), 150);
        });
    }

    static async performSearch(query) {
        try {
            this.showSearchLoading();
            const results = await window.fetchAPI('/search', {
                method: 'POST',
                body: JSON.stringify({ query })
            });
            this.showSearchResults(results || []);
        } catch (error) {
            console.error('Search failed:', error);
            this.showSearchError();
        }
    }

    static showSearchLoading() {
        const searchContainer = document.querySelector('.header-search-container');
        if (!searchContainer) return;

        let dropdown = searchContainer.querySelector('.search-dropdown');
        if (!dropdown) {
            dropdown = document.createElement('div');
            dropdown.className = 'search-dropdown';
            dropdown.style.cssText = `
                position: absolute;
                top: 100%;
                left: 0;
                right: 0;
                background: var(--glass-bg);
                backdrop-filter: blur(20px);
                border: 1px solid var(--glass-border);
                border-radius: 12px;
                margin-top: 8px;
                box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
                z-index: 1000;
                max-height: 400px;
                overflow-y: auto;
            `;
            searchContainer.appendChild(dropdown);
        }

        dropdown.innerHTML = `
            <div style="padding: 16px; text-align: center; color: var(--text-muted);">
                <div class="animate-spin w-5 h-5 border-2 border-current border-t-transparent rounded-full mx-auto mb-2"></div>
                Searching...
            </div>
        `;
    }

    static showSearchResults(results) {
        const dropdown = document.querySelector('.search-dropdown');
        if (!dropdown) return;

        const items = Array.isArray(results) ? results : (results.results || []);
        if (!items || items.length === 0) {
            dropdown.innerHTML = `
                <div style="padding: 16px; text-align: center; color: var(--text-muted);">
                    <i class="fas fa-search text-2xl mb-2 opacity-50"></i>
                    <div>No results found</div>
                </div>
            `;
            return;
        }

        const role = localStorage.getItem('role') || 'candidate';
        const resultsHTML = items.slice(0, 5).map(item => {
            const url = item.url || (role === 'recruiter' ? `/recruiter/candidates/${item.id}` : '#');
            const title = item.title || item.full_name || item.candidate_name || 'Candidate';
            const description = item.description || item.match_reason || item.role || '';
            const type = item.type || (item.match_reason ? 'Candidate' : 'Result');
            return `<a href="${url}" style="display: block; padding: 12px 16px; border-bottom: 1px solid var(--border-light); text-decoration: none; color: var(--text-main); transition: background 0.2s ease;" onmouseover="this.style.background='rgba(99, 102, 241, 0.05)'" onmouseout="this.style.background='transparent'">
                <div style="font-weight: 600; margin-bottom: 4px;">${Components.safeHTML(title)}</div>
                <div style="font-size: 12px; color: var(--text-muted);">${Components.safeHTML(description)}</div>
                <div style="font-size: 11px; color: var(--primary); margin-top: 2px;">${Components.safeHTML(type)}</div>
            </a>`;
        }).join('');

        dropdown.innerHTML = resultsHTML;
    }

    static hideSearchResults() {
        const dropdown = document.querySelector('.search-dropdown');
        if (dropdown) dropdown.remove();
    }

    static showSearchError() {
        const dropdown = document.querySelector('.search-dropdown');
        if (!dropdown) return;

        dropdown.innerHTML = `
            <div style="padding: 16px; text-align: center; color: var(--danger);">
                <i class="fas fa-exclamation-triangle text-xl mb-2"></i>
                <div>Search failed. Try again.</div>
            </div>
        `;
    }
    static showConfirm(opts) {
        return new Promise((resolve, reject) => {
            const title = typeof opts === 'string' ? opts : (opts.title || 'Confirm');
            const message = typeof opts === 'string' ? arguments[1] || '' : (opts.message || '');
            const confirmText = typeof opts === 'string' ? arguments[2] || 'Confirm' : (opts.confirmText || 'Confirm');
            const cancelText = typeof opts === 'string' ? arguments[3] || 'Cancel' : (opts.cancelText || 'Cancel');
            const type = typeof opts === 'string' ? arguments[4] || 'primary' : (opts.type || 'primary');
            const onConfirm = opts.onConfirm;

            const overlay = document.createElement('div');
            overlay.className = 'fixed inset-0 z-[200] flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4';
            overlay.innerHTML = `
                <div class="bg-white rounded-3xl shadow-2xl max-w-md w-full p-6 border border-slate-100">
                    <div class="flex items-center gap-3 mb-4">
                        <div class="w-10 h-10 rounded-xl ${type === 'danger' ? 'bg-red-100 text-red-600' : 'bg-indigo-100 text-indigo-600'} flex items-center justify-center">
                            <i class="fas ${type === 'danger' ? 'fa-exclamation-triangle' : 'fa-question-circle'}"></i>
                        </div>
                        <h3 class="text-lg font-bold text-slate-900">${this.safeHTML(title)}</h3>
                    </div>
                    <p class="text-sm text-slate-600 mb-6">${this.safeHTML(message)}</p>
                    <div class="flex gap-3 justify-end">
                        <button class="cancel-btn px-5 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold rounded-xl transition">
                            ${cancelText}
                        </button>
                        <button class="confirm-btn px-5 py-2.5 ${type === 'danger' ? 'bg-red-600 hover:bg-red-700' : 'bg-indigo-600 hover:bg-indigo-700'} text-white font-bold rounded-xl shadow-lg transition">
                            ${confirmText}
                        </button>
                    </div>
                </div>
            `;
            document.body.appendChild(overlay);

            overlay.querySelector('.cancel-btn').onclick = () => { overlay.remove(); resolve(false); };
            overlay.querySelector('.confirm-btn').onclick = () => {
                overlay.remove();
                if (onConfirm) onConfirm();
                resolve(true);
            };
            overlay.onclick = (e) => { if (e.target === overlay) { overlay.remove(); resolve(false); } };
        });
    }

    static showInterviewModal(appId, existingInterview = null) {
        return new Promise((resolve, reject) => {
            const isEdit = !!existingInterview;
            const defaultDate = new Date();
            defaultDate.setHours(defaultDate.getHours() + 24, 0, 0, 0);
            const formatDate = (d) => {
                const pad = (n) => String(n).padStart(2, '0');
                return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
            };

            const sTime = isEdit ? (existingInterview.scheduled_time ? existingInterview.scheduled_time.slice(0, 16) : formatDate(defaultDate)) : formatDate(defaultDate);
            const duration = isEdit ? (existingInterview.duration_minutes || 60) : 60;
            const type = isEdit ? (existingInterview.type || 'video') : 'video';
            const meetingLink = isEdit ? (existingInterview.meeting_link || '') : '';
            const location = isEdit ? (existingInterview.location || '') : '';
            const agenda = isEdit ? (existingInterview.agenda || '') : '';

            const overlay = document.createElement('div');
            overlay.className = 'fixed inset-0 z-[200] flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4';
            overlay.innerHTML = `
                <div class="bg-white rounded-3xl shadow-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto border border-slate-100">
                    <div class="p-6 border-b border-slate-100 flex justify-between items-center">
                        <h3 class="text-xl font-bold text-slate-900 flex items-center gap-2">
                            <i class="fas ${isEdit ? 'fa-redo-alt' : 'fa-calendar-plus'} text-indigo-600"></i>
                            ${isEdit ? 'Reschedule Interview' : 'Schedule Interview'}
                        </h3>
                        <button class="close-btn w-8 h-8 rounded-full bg-slate-100 hover:bg-slate-200 flex items-center justify-center text-slate-500 transition">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    <div class="p-6 space-y-4">
                        <div>
                            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">Date & Time *</label>
                            <input type="datetime-local" id="modal-interview-time" value="${sTime}"
                                class="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-300">
                        </div>
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">Duration (min) *</label>
                                <input type="number" id="modal-interview-duration" value="${duration}" min="15" step="15"
                                    class="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-300">
                            </div>
                            <div>
                                <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">Type *</label>
                                <select id="modal-interview-type"
                                    class="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-300">
                                    <option value="phone" ${type === 'phone' ? 'selected' : ''}>Phone</option>
                                    <option value="video" ${type === 'video' ? 'selected' : ''}>Video</option>
                                    <option value="onsite" ${type === 'onsite' ? 'selected' : ''}>On-site</option>
                                    <option value="technical" ${type === 'technical' ? 'selected' : ''}>Technical</option>
                                    <option value="behavioral" ${type === 'behavioral' ? 'selected' : ''}>Behavioral</option>
                                    <option value="panel" ${type === 'panel' ? 'selected' : ''}>Panel</option>
                                </select>
                            </div>
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">Meeting Link</label>
                            <input type="url" id="modal-interview-link" value="${this.safeHTML(meetingLink)}" placeholder="https://meet.google.com/..."
                                class="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-300">
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">Location</label>
                            <input type="text" id="modal-interview-location" value="${this.safeHTML(location)}" placeholder="Office address or room"
                                class="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-300">
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">Agenda / Notes</label>
                            <textarea id="modal-interview-agenda" rows="3" placeholder="Interview agenda, topics to cover..."
                                class="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-300 resize-none">${this.safeHTML(agenda)}</textarea>
                        </div>
                    </div>
                    <div class="p-6 border-t border-slate-100 flex gap-3 justify-end">
                        <button class="cancel-btn px-5 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold rounded-xl transition">
                            Cancel
                        </button>
                        <button class="submit-btn px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl shadow-lg shadow-indigo-500/30 transition flex items-center gap-2">
                            <i class="fas fa-spinner fa-spin hidden"></i>
                            ${isEdit ? 'Update Interview' : 'Schedule Interview'}
                        </button>
                    </div>
                </div>
            `;
            document.body.appendChild(overlay);

            const close = () => { overlay.remove(); reject('cancelled'); };
            overlay.querySelector('.close-btn').onclick = close;
            overlay.querySelector('.cancel-btn').onclick = close;
            overlay.onclick = (e) => { if (e.target === overlay) close(); };

            overlay.querySelector('.submit-btn').onclick = async () => {
                const btn = overlay.querySelector('.submit-btn');
                const spinner = btn.querySelector('.fa-spinner');
                const data = {
                    application_id: appId,
                    scheduled_time: document.getElementById('modal-interview-time').value,
                    duration_minutes: parseInt(document.getElementById('modal-interview-duration').value) || 60,
                    type: document.getElementById('modal-interview-type').value,
                    meeting_link: document.getElementById('modal-interview-link').value || null,
                    location: document.getElementById('modal-interview-location').value || null,
                    agenda: document.getElementById('modal-interview-agenda').value || null
                };

                if (!data.scheduled_time) {
                    this.showToast('Please select a date and time', 'error');
                    return;
                }

                btn.disabled = true;
                spinner.classList.remove('hidden');

                try {
                    if (isEdit) {
                        await window.fetchAPI(`/recruiter/interviews/${existingInterview.id}`, {
                            method: 'PUT',
                            body: JSON.stringify(data)
                        });
                    } else {
                        await window.fetchAPI('/recruiter/interviews/schedule', {
                            method: 'POST',
                            body: JSON.stringify(data)
                        });
                    }
                    overlay.remove();
                    this.showToast(isEdit ? 'Interview rescheduled' : 'Interview scheduled', 'success');
                    resolve(true);
                } catch (err) {
                    btn.disabled = false;
                    spinner.classList.add('hidden');
                    this.showToast(err.message || 'Failed to save interview', 'error');
                }
            };
        });
    }

    static showFeedbackModal(interviewId) {
        return new Promise((resolve, reject) => {
            const overlay = document.createElement('div');
            overlay.className = 'fixed inset-0 z-[200] flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4';
            overlay.innerHTML = `
                <div class="bg-white rounded-3xl shadow-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto border border-slate-100">
                    <div class="p-6 border-b border-slate-100 flex justify-between items-center">
                        <h3 class="text-xl font-bold text-slate-900 flex items-center gap-2">
                            <i class="fas fa-clipboard-check text-amber-500"></i>
                            Submit Interview Feedback
                        </h3>
                        <button class="close-btn w-8 h-8 rounded-full bg-slate-100 hover:bg-slate-200 flex items-center justify-center text-slate-500 transition">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    <div class="p-6 space-y-4">
                        <div>
                            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">Overall Rating *</label>
                            <div class="flex gap-2" id="modal-feedback-overall">
                                ${[1,2,3,4,5].map(n => `<button type="button" data-val="${n}" class="w-10 h-10 rounded-xl bg-slate-100 hover:bg-amber-100 text-slate-400 hover:text-amber-500 text-lg transition"><i class="fas fa-star"></i></button>`).join('')}
                            </div>
                        </div>
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">Technical (1-5)</label>
                                <select id="modal-feedback-technical" class="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-300">
                                    ${[1,2,3,4,5].map(n => `<option value="${n}">${n}</option>`).join('')}
                                </select>
                            </div>
                            <div>
                                <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">Communication (1-5)</label>
                                <select id="modal-feedback-communication" class="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-300">
                                    ${[1,2,3,4,5].map(n => `<option value="${n}">${n}</option>`).join('')}
                                </select>
                            </div>
                            <div>
                                <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">Culture Fit (1-5)</label>
                                <select id="modal-feedback-culture" class="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-300">
                                    ${[1,2,3,4,5].map(n => `<option value="${n}">${n}</option>`).join('')}
                                </select>
                            </div>
                            <div>
                                <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">Problem Solving (1-5)</label>
                                <select id="modal-feedback-problem" class="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-300">
                                    ${[1,2,3,4,5].map(n => `<option value="${n}">${n}</option>`).join('')}
                                </select>
                            </div>
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">Recommendation *</label>
                            <select id="modal-feedback-recommendation" class="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-300">
                                <option value="strong_yes">Strong Yes</option>
                                <option value="yes" selected>Yes</option>
                                <option value="maybe">Maybe</option>
                                <option value="no">No</option>
                                <option value="strong_no">Strong No</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">Strengths</label>
                            <textarea id="modal-feedback-strengths" rows="2" placeholder="What went well..."
                                class="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-300 resize-none"></textarea>
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">Concerns</label>
                            <textarea id="modal-feedback-concerns" rows="2" placeholder="Areas for improvement..."
                                class="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-300 resize-none"></textarea>
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">Additional Notes</label>
                            <textarea id="modal-feedback-notes" rows="2" placeholder="Any other observations..."
                                class="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-300 resize-none"></textarea>
                        </div>
                    </div>
                    <div class="p-6 border-t border-slate-100 flex gap-3 justify-end">
                        <button class="cancel-btn px-5 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold rounded-xl transition">
                            Cancel
                        </button>
                        <button class="submit-btn px-6 py-2.5 bg-amber-500 hover:bg-amber-600 text-white font-bold rounded-xl shadow-lg shadow-amber-500/30 transition flex items-center gap-2">
                            <i class="fas fa-spinner fa-spin hidden"></i>
                            Submit Feedback
                        </button>
                    </div>
                </div>
            `;
            document.body.appendChild(overlay);

            // Star rating interaction
            let selectedOverall = 0;
            const stars = overlay.querySelectorAll('#modal-feedback-overall button');
            stars.forEach(btn => {
                btn.onclick = () => {
                    selectedOverall = parseInt(btn.dataset.val);
                    stars.forEach((s, i) => {
                        const val = parseInt(s.dataset.val);
                        s.className = val <= selectedOverall
                            ? 'w-10 h-10 rounded-xl bg-amber-100 text-amber-500 text-lg transition'
                            : 'w-10 h-10 rounded-xl bg-slate-100 hover:bg-amber-100 text-slate-400 hover:text-amber-500 text-lg transition';
                    });
                };
            });

            const close = () => { overlay.remove(); reject('cancelled'); };
            overlay.querySelector('.close-btn').onclick = close;
            overlay.querySelector('.cancel-btn').onclick = close;
            overlay.onclick = (e) => { if (e.target === overlay) close(); };

            overlay.querySelector('.submit-btn').onclick = async () => {
                if (selectedOverall === 0) {
                    this.showToast('Please select an overall rating', 'error');
                    return;
                }

                const btn = overlay.querySelector('.submit-btn');
                const spinner = btn.querySelector('.fa-spinner');
                btn.disabled = true;
                spinner.classList.remove('hidden');

                try {
                    await window.fetchAPI(`/recruiter/interviews/${interviewId}/feedback`, {
                        method: 'POST',
                        body: JSON.stringify({
                            overall_rating: selectedOverall,
                            technical_rating: parseInt(document.getElementById('modal-feedback-technical').value) || null,
                            communication_rating: parseInt(document.getElementById('modal-feedback-communication').value) || null,
                            culture_fit_rating: parseInt(document.getElementById('modal-feedback-culture').value) || null,
                            problem_solving_rating: parseInt(document.getElementById('modal-feedback-problem').value) || null,
                            recommendation: document.getElementById('modal-feedback-recommendation').value,
                            strengths: document.getElementById('modal-feedback-strengths').value || null,
                            concerns: document.getElementById('modal-feedback-concerns').value || null,
                            additional_notes: document.getElementById('modal-feedback-notes').value || null
                        })
                    });
                    overlay.remove();
                    this.showToast('Feedback submitted successfully', 'success');
                    resolve(true);
                } catch (err) {
                    btn.disabled = false;
                    spinner.classList.add('hidden');
                    this.showToast(err.message || 'Failed to submit feedback', 'error');
                }
            };
        });
    }

    static async renderComments(containerId, appId) {
        const container = document.getElementById(containerId);
        if (!container) return;
        try {
            const comments = await window.fetchAPI(`/recruiter/collaboration/comments/${appId}`);
            const currentUser = await window.fetchAPI('/auth/me');
            container.innerHTML = `
                <div class="space-y-4 mb-4" id="comments-list">
                    ${Array.isArray(comments) && comments.length > 0
                        ? comments.map(c => Components._renderCommentItem(c, currentUser)).join('')
                        : '<p class="text-sm text-slate-400 text-center py-6" data-i18n="recruiter.candidate.no_comments">No comments yet. Start the discussion!</p>'}
                </div>
                <div class="flex gap-2">
                    <input type="text" id="comment-input-${appId}" placeholder="Add a comment..." class="flex-1 px-4 py-2 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-300">
                    <button onclick="Components.addComment('${appId}')" class="px-4 py-2 bg-indigo-600 text-white text-sm font-bold rounded-xl hover:bg-indigo-700 transition shadow-sm flex items-center gap-1.5">
                        <i class="fas fa-paper-plane text-xs"></i> Send
                    </button>
                </div>`;
        } catch (e) {
            container.innerHTML = '<p class="text-sm text-red-400 text-center py-4">Failed to load comments.</p>';
        }
    }

    static _renderCommentItem(comment, currentUser) {
        const canDelete = comment.user_email === currentUser?.email;
        const date = comment.created_at ? new Date(comment.created_at).toLocaleDateString() : '';
        return `
            <div class="p-3 bg-slate-50 rounded-xl border border-slate-100">
                <div class="flex justify-between items-start mb-1">
                    <div class="flex items-center gap-2">
                        <span class="text-xs font-bold text-slate-700">${Components.safeHTML(comment.user_name || 'Unknown')}</span>
                        <span class="text-[10px] text-slate-400">${date}</span>
                    </div>
                    ${canDelete ? `<button onclick="Components.deleteComment(${comment.id}, '${comment.application_id}')" class="text-slate-300 hover:text-red-500 transition"><i class="fas fa-trash-can text-[10px]"></i></button>` : ''}
                </div>
                <p class="text-sm text-slate-600">${Components.safeHTML(comment.content || '')}</p>
                ${Array.isArray(comment.replies) && comment.replies.length > 0
                    ? `<div class="mt-2 ml-4 space-y-2 border-l-2 border-indigo-100 pl-3">${comment.replies.map(r => Components._renderCommentItem(r, currentUser)).join('')}</div>`
                    : ''}
            </div>`;
    }

    static async addComment(appId) {
        const input = document.getElementById(`comment-input-${appId}`);
        if (!input || !input.value.trim()) return;
        try {
            await window.fetchAPI('/recruiter/collaboration/comments', {
                method: 'POST',
                body: JSON.stringify({ application_id: parseInt(appId), content: input.value.trim() })
            });
            input.value = '';
            await Components.renderComments('comments-section', appId);
        } catch (e) {
            Components.showToast('Failed to add comment', 'error');
        }
    }

    static showAssignmentModal(appId, currentAssignment) {
        return new Promise((resolve) => {
            const overlay = document.createElement('div');
            overlay.className = 'fixed inset-0 z-[200] flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4';
            overlay.innerHTML = `
                <div class="bg-white rounded-3xl shadow-2xl max-w-md w-full max-h-[90vh] overflow-y-auto border border-slate-100">
                    <div class="p-6 border-b border-slate-100 flex justify-between items-center">
                        <h3 class="text-xl font-bold text-slate-900 flex items-center gap-2">
                            <i class="fas fa-user-plus text-indigo-600"></i>
                            Assign Candidate
                        </h3>
                        <button class="close-btn w-8 h-8 rounded-full bg-slate-100 hover:bg-slate-200 flex items-center justify-center text-slate-500 transition">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    <div class="p-6">
                        <p class="text-sm text-slate-500 mb-4">Select a team member to assign this candidate to:</p>
                        <div id="assignment-recruiters-list" class="space-y-2 max-h-60 overflow-y-auto">
                            <div class="flex items-center justify-center py-4">
                                <i class="fas fa-spinner fa-spin text-indigo-600"></i>
                            </div>
                        </div>
                        ${currentAssignment ? '<button id="unassign-btn" class="mt-4 w-full px-4 py-2.5 bg-red-50 hover:bg-red-100 text-red-600 font-bold rounded-xl transition flex items-center justify-center gap-2"><i class="fas fa-user-slash"></i> Unassign</button>' : ''}
                    </div>
                </div>
            `;
            document.body.appendChild(overlay);

            overlay.querySelector('.close-btn').onclick = () => { overlay.remove(); resolve(null); };
            overlay.onclick = (e) => { if (e.target === overlay) { overlay.remove(); resolve(null); } };

            if (currentAssignment) {
                overlay.querySelector('#unassign-btn').onclick = () => { overlay.remove(); resolve(null); };
            }

            // Fetch team members
            window.fetchAPI('/recruiter/collaboration/team')
                .then(members => {
                    const list = overlay.querySelector('#assignment-recruiters-list');
                    if (!members || members.length === 0) {
                        list.innerHTML = '<p class="text-sm text-slate-400 text-center py-4">No other team members available.</p>';
                        return;
                    }
                    list.innerHTML = members.map(m => `
                        <button class="recruiter-option w-full text-left px-4 py-3 rounded-xl border border-slate-200 hover:border-indigo-300 hover:bg-indigo-50 transition flex items-center gap-3 ${m.id === currentAssignment ? 'border-indigo-300 bg-indigo-50' : ''}"
                            data-id="${m.id}">
                            <div class="w-8 h-8 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center text-sm font-bold">
                                ${(m.name || m.email || '?')[0].toUpperCase()}
                            </div>
                            <div>
                                <div class="text-sm font-bold text-slate-800">${m.name || 'Unknown'}</div>
                                <div class="text-xs text-slate-400">${m.email || ''}</div>
                            </div>
                        </button>
                    `).join('');

                    list.querySelectorAll('.recruiter-option').forEach(btn => {
                        btn.onclick = () => {
                            overlay.remove();
                            resolve(parseInt(btn.dataset.id));
                        };
                    });
                })
                .catch(() => {
                    const list = overlay.querySelector('#assignment-recruiters-list');
                    list.innerHTML = '<p class="text-sm text-red-400 text-center py-4">Failed to load team members.</p>';
                });
        });
    }

    static async deleteComment(commentId, appId) {
        try {
            await window.fetchAPI(`/recruiter/collaboration/comments/${commentId}`, { method: 'DELETE' });
            await Components.renderComments('comments-section', appId);
        } catch (e) {
            Components.showToast('Failed to delete comment', 'error');
        }
    }
}

// Auto-initialize
if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', () => Components.init());
}

// Expose globally for inline scripts and bundle compatibility
if (typeof window !== 'undefined') window.Components = Components;
