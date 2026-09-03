// ─── AI TALENT INTELLIGENCE OS ───
// Version: 2026.05.HYPERDRIVE
// Complete orchestration engine for the next-gen Candidate Intelligence Dashboard

// SANITY GATE: This script must NOT run on recruiter pages
if (window.location.pathname.includes('/recruiter/')) {
    console.error('[Dashboard] Aborting: candidate-dashboard.js loaded on recruiter path');
    throw new Error('Wrong dashboard script for this page');
}

let allApplications = [];
let dashboardInitStarted = false;
let dashCurrentPage = 1;
let dashPageSize = 3;
let dashCurrentFilter = 'all';

function getDashPageFromURL() {
    const params = new URLSearchParams(window.location.search);
    const p = parseInt(params.get('dash_page'));
    const s = parseInt(params.get('dash_size'));
    const f = params.get('dash_filter');
    if (p && p > 0) dashCurrentPage = p;
    if (s && s > 0) dashPageSize = s;
    if (f) dashCurrentFilter = f;
}

function updateDashURL() {
    const params = new URLSearchParams(window.location.search);
    if (dashCurrentPage > 1) params.set('dash_page', dashCurrentPage); else params.delete('dash_page');
    if (dashPageSize !== 3) params.set('dash_size', dashPageSize); else params.delete('dash_size');
    if (dashCurrentFilter !== 'all') params.set('dash_filter', dashCurrentFilter); else params.delete('dash_filter');
    const newURL = params.toString() ? `${window.location.pathname}?${params.toString()}` : window.location.pathname;
    history.replaceState(null, '', newURL);
}

// Use AuthToken for dynamic token access (fixes stale token on login/logout)
function requireAuth() {
    const token = typeof AuthToken !== 'undefined' ? AuthToken.get() : localStorage.getItem('token');
    const hasCookie = document.cookie.includes('session');
    if (!token && !hasCookie) {
        window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
        return false;
    }
    return true;
}

if (!requireAuth()) {
    // Redirect already handled
}

// ─── MAIN INIT ───
async function initDashboard() {
    if (dashboardInitStarted) return;
    if (!window.location.pathname.includes('/candidate/dashboard')) return;
    dashboardInitStarted = true;

    getDashPageFromURL();

    try {
        if (typeof Components !== 'undefined') {
            if (!localStorage.getItem('preferredTheme')) {
                localStorage.setItem('preferredTheme', 'light');
            }
            Components.init('nav_overview');
        } else {
            // Components not loaded yet
        }

        const loader = document.getElementById('dashboard-loader');
        const cockpit = document.getElementById('dashboard-cockpit');
        if (loader) loader.classList.remove('hidden');

        // Fire primary and secondary calls in parallel (was sequential before)
        const [mainResult, historyResult, matchesResult, profileResult] = await Promise.allSettled([
            window.fetchAPI('/candidate/applications/me'),
            window.fetchAPI('/candidate/applications/me/history'),
            window.fetchAPI('/candidate/jobs/matches'),
            window.fetchAPI('/candidate/profile')
        ]);

        let data = mainResult.status === 'fulfilled' && mainResult.value ? mainResult.value : {};
        if (data.status === 'empty') data = {};

        const allFailed = mainResult.status !== 'fulfilled'
            && historyResult.status !== 'fulfilled'
            && matchesResult.status !== 'fulfilled'
            && profileResult.status !== 'fulfilled';

        if (allFailed && Object.keys(data).length === 0) {
            // DEMO_DATA fallback was removed (CRIT-01): silently showing fake data
            // masked real outages and misled users. Show the error instead.
            console.error('[Dashboard] All API calls failed — showing error state');
            const loader = document.getElementById('dashboard-loader');
            if (loader) {
                loader.classList.remove('hidden');
                loader.innerHTML = `
                    <div class="text-center p-8">
                        <i class="fas fa-exclamation-triangle text-5xl text-red-400 mb-6"></i>
                        <h2 class="text-slate-900 text-2xl font-black mb-2">Unable to load dashboard</h2>
                        <p class="text-slate-500 max-w-md mx-auto mb-8">Please check your connection and try again.</p>
                        <button onclick="location.reload()" class="px-8 py-3 bg-indigo-600 rounded-xl text-white font-bold hover:bg-indigo-500 transition">Retry</button>
                    </div>`;
            }
            return;
        }

        data = await hydrateDashboardData(data, {
            history: historyResult.status === 'fulfilled' ? historyResult.value : null,
            matches: matchesResult.status === 'fulfilled' ? matchesResult.value : null,
            profile: profileResult.status === 'fulfilled' ? profileResult.value : null,
        });

        // Update app count from history data already fetched (eliminates duplicate call)
        if (historyResult.status === 'fulfilled' && Array.isArray(historyResult.value)) {
            document.querySelectorAll('.app-count').forEach(el => el.textContent = historyResult.value.length);
        }

        // Sync live profile identity from backend to shared UI components
        if (data?.name) {
            localStorage.setItem('userName', data.name);
            if (data.avatar_url) {
                localStorage.setItem('userPhotoUrl', data.avatar_url);
            }
            if (typeof Components !== 'undefined') {
                Components.renderSidebar('nav_overview');
                Components.renderTopHeader();
            }
        }

        // Handle recruiter link badge
        const intel = data.intelligence || {};
        if (intel.recruiter_name || data.recruiter_viewed) {
            const badge = document.getElementById('recruiter-link-badge');
            if (badge) {
                badge.style.display = 'flex';
                setTimeout(() => {
                    badge.classList.remove('opacity-0');
                    badge.classList.add('opacity-100');
                }, 100);

                // Populate recruiter info
                const nameEl = document.getElementById('recruiter-name-val');
                const roleEl = document.getElementById('recruiter-role-val');
                const avatarEl = document.getElementById('recruiter-avatar-img');

                if (nameEl) nameEl.textContent = intel.recruiter_name || 'Hiring Manager';
                if (roleEl) roleEl.textContent = (intel.recruiter_role || 'Recruiter').toUpperCase();
                if (avatarEl) avatarEl.src = intel.recruiter_avatar || `https://ui-avatars.com/api/?name=${encodeURIComponent(intel.recruiter_name || 'Recruiter')}&background=7C3AED&color=fff`;
            }
        }

        if (loader) loader.classList.add('hidden');
        if (cockpit) {
            cockpit.classList.remove('hidden');
            console.log("[Dashboard] Workspace shown");
        }

        await renderDashboard(data);
        // Removed syncSecondaryData() duplicate call -- app count is updated above

    } catch (err) {
        console.error('[CRITICAL] OS initialization failed:', err);
        const loader = document.getElementById('dashboard-loader');
        if (loader) {
            loader.classList.remove('hidden');
            loader.innerHTML = `
                <div class="text-center p-8">
                    <i class="fas fa-exclamation-triangle text-5xl text-amber-400 mb-6"></i>
                    <h2 class="text-slate-900 text-2xl font-black mb-2">Workspace failed to load</h2>
                    <p class="text-slate-500 max-w-md mx-auto mb-8">${err.message || 'We could not load the latest candidate data.'}</p>
                    <button onclick="location.reload()" class="px-8 py-3 bg-indigo-600 rounded-xl text-white font-bold hover:bg-indigo-500 transition">Try again</button>
                </div>`;
        }
    }
}

async function hydrateDashboardData(baseData, preFetched = {}) {
    const data = baseData && typeof baseData === 'object' ? { ...baseData } : {};

    // Use pre-fetched data if available (avoids redundant server calls)
    let historyResult, matchesResult, profileResult;
    if (preFetched.history !== undefined) {
        historyResult = { status: 'fulfilled', value: preFetched.history };
        matchesResult = { status: 'fulfilled', value: preFetched.matches };
        profileResult = { status: 'fulfilled', value: preFetched.profile };
    } else {
        [historyResult, matchesResult, profileResult] = await Promise.allSettled([
            window.fetchAPI('/candidate/applications/me/history'),
            window.fetchAPI('/candidate/jobs/matches'),
            window.fetchAPI('/candidate/profile')
        ]);
    }

    const history = historyResult.status === 'fulfilled' && Array.isArray(historyResult.value)
        ? historyResult.value
        : null;
    const matches = matchesResult.status === 'fulfilled' && Array.isArray(matchesResult.value)
        ? matchesResult.value
        : null;
    const profile = profileResult.status === 'fulfilled' && profileResult.value && typeof profileResult.value === 'object'
        ? profileResult.value
        : null;

    if (history) {
        data.applications_count = history.length;
        data.applications = history.map(app => ({
            id: app.id,
            title: app.role || app.title || 'Application',
            company: app.company || 'Company',
            status: (app.status || 'pending').toLowerCase(),
            created_at: app.date || app.created_at,
            date: app.date,
            logo: app.logo,
            location: app.location || null,
            salary: app.salary || null,
            type: app.type || null,
            verdict: app.verdict || null,
            score: app.score || 0,
            score_reasoning: app.score_reasoning || null,
            analysis: app.analysis || {}
        }));
    }

    if (matches) {
        data.suggested_jobs = matches.slice(0, 6).map(job => ({
            id: job.id,
            title: job.title || job.role || 'Open role',
            company: job.company || 'Company',
            location: job.location || job.work_type || 'Remote',
            match: Math.round(Number(job.match_score ?? job.match ?? job.score ?? 0)) || 0,
            logo: job.logo_url || job.company_logo || job.logo,
            salary: job.salary || job.salary_range
        }));
    }

    if (profile) {
        data.name = data.name || profile.name || profile.full_name;
        data.profile_views = data.profile_views ?? profile.profile_views ?? 0;
        data.profile_completion = data.profile_completion ?? profile.profile_completion ?? calculateClientProfileCompletion(profile);
        data.avatar_url = data.avatar_url || profile.avatar_url;
    }

    data.applications = Array.isArray(data.applications) ? data.applications : [];
    data.suggested_jobs = Array.isArray(data.suggested_jobs) ? data.suggested_jobs : [];
    data.upcoming_interviews = Array.isArray(data.upcoming_interviews) ? data.upcoming_interviews : [];
    data.activity = Array.isArray(data.activity) ? data.activity : [];
    data.ai_activity = Array.isArray(data.ai_activity) ? data.ai_activity : [];
    data.checklist = Array.isArray(data.checklist) ? data.checklist : [];

    return data;
}

function calculateClientProfileCompletion(profile) {
    // TODO: move to backend — profile.completion_pct
    const fields = ['name', 'email', 'phone', 'location', 'headline', 'bio', 'avatar_url'];
    const completed = fields.filter(field => Boolean(profile && profile[field])).length;
    return Math.round((completed / fields.length) * 100);
}

// ─── MAIN RENDER ENGINE ───
async function renderDashboard(data) {
    console.log("[Dashboard] Rendering candidate workspace...");
    try {
        const intel = data.intelligence || {};
        const analysis = data.analysis || {};
        const score = data.score_entity?.final_score ?? data.overall_score ?? data.score ?? 0;
        const name = capitalizeName(data.name || localStorage.getItem('userName') || 'Candidate');
        const firstName = name.split(' ')[0];

        const greetingEl = document.getElementById('candidate-name');
        if (greetingEl) greetingEl.textContent = firstName;

        // Time-aware greeting
        const hour = new Date().getHours();
        const greetWord = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
        const h1 = greetingEl?.closest('h1');
        if (h1) XSS.safeSetHTML(h1, `${greetWord}, <span style="color:var(--primary);">${firstName}</span>`);

        // Dynamic subtitle based on data
        const subtitleEl = document.getElementById('dashboard-subtitle');
        if (subtitleEl) {
            const appsCount = data.applications_count ?? 0;
            subtitleEl.textContent = appsCount > 0
                ? `You have ${appsCount} active application${appsCount > 1 ? 's' : ''}. Review the next action and keep your profile sharp.`
                : 'Build a stronger profile, discover relevant roles, and start tracking your applications.';
        }

        // Update sidebar name
        const sidebarNameEl = document.getElementById('sidebar-user-name');
        if (sidebarNameEl) sidebarNameEl.textContent = name;

        // 2. SUMMARY STATS
        const statApps = document.getElementById('stat-apps');
        if (statApps) statApps.textContent = data.applications_count ?? 0;

        const statViews = document.getElementById('stat-views');
        if (statViews) statViews.textContent = data.profile_views ?? 0;

        const statMessages = document.getElementById('stat-messages');
        if (statMessages) statMessages.textContent = data.messages_count ?? 0;

        const statScore = document.getElementById('stat-score');
        if (statScore) statScore.textContent = Math.round(score);

        const statScoreLabel = document.getElementById('stat-score-label');
        if (statScoreLabel) {
            if (score >= 80) {
                statScoreLabel.textContent = 'Excellent Match';
                statScoreLabel.className = 'text-[10px] font-bold text-emerald-500';
            } else if (score >= 50) {
                statScoreLabel.textContent = 'Strong Candidate';
                statScoreLabel.className = 'text-[10px] font-bold text-indigo-500';
            } else {
                statScoreLabel.textContent = 'Building Foundation';
                statScoreLabel.className = 'text-[10px] font-bold text-orange-500';
            }
        }

        // 3. RECRUITER INTELLIGENCE BADGE
        const recruiterBadge = document.getElementById('recruiter-link-badge');
        if (recruiterBadge) {
            if (intel.recruiter_name) {
                const nameVal = document.getElementById('recruiter-name-val');
                const roleVal = document.getElementById('recruiter-role-val');
                const avatarImg = document.getElementById('recruiter-avatar-img');
                
                if (nameVal) nameVal.textContent = intel.recruiter_name;
                if (roleVal) roleVal.textContent = intel.recruiter_role || 'Recruiter';
                if (avatarImg) {
                    avatarImg.src = intel.recruiter_avatar || `https://ui-avatars.com/api/?name=${encodeURIComponent(intel.recruiter_name || 'R')}&background=7C3AED&color=fff`;
                }
                
                recruiterBadge.style.display = 'flex';
                setTimeout(() => {
                    recruiterBadge.style.opacity = '1';
                    recruiterBadge.style.transform = 'translateY(0)';
                }, 100);
            } else {
                recruiterBadge.style.display = 'none';
            }
        }

        // 4. APPLICATIONS LIST
        allApplications = data.applications || [];
        renderApplicationsTable(allApplications);

        // Apply initial filter from URL
        const params = new URLSearchParams(window.location.search);
        const initialFilter = params.get('dash_filter') || 'all';
        if (initialFilter !== 'all') {
            setTimeout(() => filterApplications(initialFilter), 100);
        } else {
            const tabs = document.querySelectorAll('.app-tab');
            tabs.forEach(tab => {
                const isActive = tab.dataset.filter === dashCurrentFilter;
                tab.style.color = isActive ? 'var(--primary)' : 'var(--text-secondary)';
                tab.style.borderBottomColor = isActive ? 'var(--primary)' : 'transparent';
                tab.style.fontWeight = isActive ? '800' : '600';
            });
        }

        // 5. PROFILE COMPLETION (TALENT SCORE)
        const profilePct = data.profile_completion || 0;
        const pctEl = document.getElementById('profile-pct');
        if (pctEl) animateCounter(pctEl, 0, profilePct, 1500, '%');

        const ring = document.getElementById('profile-progress-ring');
        if (ring) {
            const circ = 2 * Math.PI * 42;
            const offset = circ - (profilePct / 100) * circ;
            ring.style.strokeDashoffset = offset;
        }

        // Sync profile strength to sidebar bar
        localStorage.setItem('profileStrength', profilePct);
        const sidebarBar = document.getElementById('sidebar-strength-bar');
        if (sidebarBar) sidebarBar.style.width = profilePct + '%';
        const sidebarPct = document.getElementById('sidebar-strength-pct');
        if (sidebarPct) sidebarPct.textContent = profilePct + '%';

        // 6. INTERVIEWS
        renderInterviewsList(data.upcoming_interviews || []);

        // 7. RECENT ACTIVITY (SYSTEM PULSE)
        renderActivityTimeline(data.ai_activity || data.activity || []);

        // 8. PROFILE CHECKLIST
        renderProfileChecklist(data.checklist || []);

        // 9. AI RADAR MAP (skill_metrics from backend)
        const radarData = {
            ...(data.intelligence || {}),
            skill_metrics: data.skill_metrics || data.intelligence?.skill_metrics || {}
        };
        renderCompetencyRadar(radarData);

        // 10. GAP ANALYSIS
        // Removed — Growth section deleted

        // 11. SUGGESTED JOBS
        renderSuggestedJobs(data.suggested_jobs || []);

        // AOS refresh
        setTimeout(() => { 
            if (typeof AOS !== 'undefined') AOS.refresh(); 
        }, 500);


    } catch (e) {
        console.error("[OS] Render cycle failed:", e);
    }
}

function getStatusColors(status) {
    const statusMap = {
        'applied': { bg: '#EEF2FF', text: '#4F46E5', icon: 'fa-paper-plane' },
        'reviewing': { bg: '#FEF3C7', text: '#D97706', icon: 'fa-eye' },
        'interview': { bg: '#D1FAE5', text: '#059669', icon: 'fa-video' },
        'assessment': { bg: '#E0E7FF', text: '#6366F1', icon: 'fa-clipboard-check' },
        'offer': { bg: '#D1FAE5', text: '#10B981', icon: 'fa-hand-holding-dollar' },
        'rejected': { bg: '#FEE2E2', text: '#DC2626', icon: 'fa-xmark' },
        'withdrawn': { bg: '#F3F4F6', text: '#6B7280', icon: 'fa-arrow-up-right-from-square' },
        'pending': { bg: '#F3F4F6', text: '#6B7280', icon: 'fa-clock' }
    };
    return statusMap[status] || statusMap['pending'];
}

function formatDate(dateStr) {
    if (!dateStr) return 'N/A';
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return 'N/A';
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function renderApplicationsTable(apps) {
    const list = document.getElementById('applications-list');
    if (!list) return;

    const filtered = getDashFilteredApplications();
    const totalFiltered = filtered.length;

    updateDashPagination(totalFiltered);

    const start = dashPageSize > 0 ? (dashCurrentPage - 1) * dashPageSize : 0;
    const end = dashPageSize > 0 ? Math.min(start + dashPageSize, totalFiltered) : totalFiltered;
    const displayApps = dashPageSize > 0 ? filtered.slice(start, end) : filtered;

    if (displayApps.length === 0) {
        list.innerHTML = `<div style="padding: 4rem 1rem; text-align: center;">
            <i class="fas fa-briefcase" style="font-size: 3rem; opacity: 0.3; margin-bottom: 1rem;"></i>
            <h4 style="font-size: 1.1rem; font-weight: 800; margin: 0;">No active applications yet</h4>
            <p style="color: var(--text-secondary); margin: 0.75rem 0 1.5rem;">Start applying to opportunities.</p>
            <a href="/candidate/jobs" style="padding: 0.85rem 1.5rem; background: var(--primary); color: white; text-decoration: none; border-radius: 12px; font-weight: 800;">Browse jobs</a>
        </div>`;
        return;
    }

    const colors = ['#6366F1', '#8B5CF6', '#7C3AED', '#EC4899', '#F59E0B', '#10B981'];

    list.innerHTML = displayApps.map((app, idx) => {
        const color = colors[idx % colors.length];
        const companyName = app.company || 'Company';
        const companyInitial = companyName.charAt(0).toUpperCase();
        const status = (app.status || 'pending').toLowerCase();
        const appDate = app.created_at || app.date || app.created;

        let statusClass, statusText, nextStep, statusIcon;
        if (status === 'preselected' || status === 'interview') {
            statusClass = { bg: '#EDE9FE', text: '#7C3AED' };
            statusText = 'Interview';
            nextStep = 'Schedule interview';
            statusIcon = 'fa-user-check';
        } else if (status === 'in_review') {
            statusClass = { bg: '#DBEAFE', text: '#2563EB' };
            statusText = 'In Review';
            nextStep = 'Under evaluation';
            statusIcon = 'fa-search';
        } else if (status === 'accepted' || status === 'offered') {
            statusClass = { bg: '#D1FAE5', text: '#059669' };
            statusText = 'Offered';
            nextStep = 'Review offer';
            statusIcon = 'fa-check-circle';
        } else if (status === 'rejected') {
            statusClass = { bg: '#FEE2E2', text: '#DC2626' };
            statusText = 'Rejected';
            nextStep = '—';
            statusIcon = 'fa-times-circle';
        } else if (status === 'withdrawn') {
            statusClass = { bg: '#F3F4F6', text: '#6B7280' };
            statusText = 'Withdrawn';
            nextStep = '—';
            statusIcon = 'fa-undo';
        } else if (status === 'applied') {
            // Bug U-08: previously both 'applied' and 'pending' were
            // collapsed into a single yellow "Applied / Awaiting
            // response" pill. The audit noted candidates found it
            // confusing because 'applied' (just submitted) and
            // 'pending' (already reviewed) were visually identical.
            // We now distinguish them: a fresh 'applied' status shows
            // a blue "Just submitted" pill that animates to the
            // neutral "Awaiting response" after 24 hours.
            const appliedRecently =
                appDate &&
                Date.now() - new Date(appDate).getTime() < 24 * 60 * 60 * 1000;
            if (appliedRecently) {
                statusClass = { bg: '#DBEAFE', text: '#2563EB' };
                statusText = 'Just submitted';
                nextStep = 'Recruiter will review shortly';
                statusIcon = 'fa-paper-plane';
            } else {
                statusClass = { bg: '#FEF3C7', text: '#D97706' };
                statusText = 'Awaiting response';
                nextStep = 'Recruiter reviewing';
                statusIcon = 'fa-clock';
            }
        } else {
            statusClass = { bg: '#FEF3C7', text: '#D97706' };
            statusText = 'Awaiting response';
            nextStep = 'Recruiter reviewing';
            statusIcon = 'fa-clock';
        }

        const appliedDate = appDate ? new Date(appDate).toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' }) : 'N/A';
        const scoreVal = app.score || 0;
        const weaknesses = (app.analysis && app.analysis.weaknesses) || [];

        return `<div onclick="window.location.href='/candidate/applications/${app.id}'" style="padding: 1.25rem 1.5rem; border-radius: 16px; border: 1px solid var(--border-light); display: flex; align-items: center; justify-content: space-between; cursor: pointer; background: rgba(255,255,255,0.58); backdrop-filter: blur(18px); transition: all 0.3s;" onmouseover="this.style.borderColor='var(--primary)'" onmouseout="this.style.borderColor='var(--border-light)'">
            <div style="display: flex; align-items: center; gap: 1.25rem; flex: 1; min-width: 0;">
                <div style="width: 48px; height: 48px; border-radius: 12px; background: linear-gradient(135deg, ${color} 0%, ${color}dd 100%); display: flex; align-items: center; justify-content: center; color: white; font-weight: 800; font-size: 1.125rem; flex-shrink: 0;">
                    ${companyInitial}
                </div>
                <div style="min-width: 0;">
                    <h4 style="margin: 0; font-size: 1rem; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(app.title || 'Role')}</h4>
                    <p style="margin: 0.25rem 0 0; font-size: 0.85rem; color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                        ${escapeHtml(companyName)}${app.location ? ' &bull; ' + escapeHtml(app.location) : ''} &bull; ${appliedDate}
                    </p>
                    ${scoreVal > 0 ? `<div style="margin-top: 0.35rem; display: flex; align-items: center; gap: 0.5rem;">
                        <div style="flex: 1; max-width: 80px; height: 4px; background: rgba(0,0,0,0.08); border-radius: 2px; overflow: hidden;">
                            <div style="width: ${scoreVal}%; height: 100%; background: ${scoreVal >= 70 ? '#10B981' : scoreVal >= 45 ? '#6366F1' : '#F59E0B'}; border-radius: 2px;"></div>
                        </div>
                        <span style="font-size: 0.7rem; font-weight: 700; color: ${scoreVal >= 70 ? '#10B981' : scoreVal >= 45 ? '#6366F1' : '#F59E0B'};">${scoreVal}%</span>
                    </div>` : ''}
                    ${weaknesses.length > 0 ? `<p style="margin: 0.2rem 0 0; font-size: 0.7rem; color: #EF4444; font-weight: 600;"><i class="fas fa-exclamation-triangle" style="font-size: 0.6rem;"></i> ${escapeHtml(weaknesses[0])}${weaknesses.length > 1 ? ' +' + (weaknesses.length - 1) : ''}</p>` : ''}
                </div>
            </div>
            <div style="display: flex; align-items: center; gap: 1rem; flex-shrink: 0; margin-left: 1rem;">
                <div style="text-align: right;">
                    <span style="padding: 0.4rem 0.75rem; background: ${statusClass.bg}; color: ${statusClass.text}; border-radius: 10px; font-size: 0.7rem; font-weight: 900; text-transform: uppercase; display: inline-flex; align-items: center; gap: 0.35rem;">
                        <i class="fas ${statusIcon}" style="font-size: 0.6rem;"></i> ${statusText}
                    </span>
                    <p style="margin: 0.25rem 0 0; font-size: 0.65rem; color: var(--text-secondary); font-weight: 600; white-space: nowrap;">${escapeHtml(nextStep)}</p>
                </div>
                <i class="fas fa-chevron-right" style="color: #CBD5E1;"></i>
            </div>
        </div>`;
    }).join('');
}

function renderInterviewsList(interviews) {
    const list = document.getElementById('interviews-list');
    if (!list) return;
    const display = Array.isArray(interviews) ? interviews : [];
    if (display.length === 0) {
        list.innerHTML = `<div style="padding: 1.25rem 0.5rem; text-align: center; color: var(--text-secondary);">
            <i class="fas fa-calendar-check" style="font-size: 1.5rem; opacity: 0.45; margin-bottom: 0.5rem;"></i>
            <p style="margin: 0; font-size: 0.75rem;">No interviews scheduled.</p>
        </div>`;
        return;
    }
    list.innerHTML = display.map(int => `
        <div style="display: flex; align-items: center; gap: 0.75rem; padding: 0.75rem; background: rgba(255,255,255,0.5); border-radius: 10px;">
            <img src="${escapeHtml(int.logo || 'https://ui-avatars.com/api/?name=' + encodeURIComponent(int.company || 'C') + '&background=F1F5F9&color=6366F1')}" style="width: 32px; height: 32px; border-radius: 8px; object-fit: contain;" onerror="this.src='https://ui-avatars.com/api/?name=C&background=F1F5F9&color=6366F1'">
            <div style="flex: 1; min-width: 0;">
                <h5 style="margin: 0; font-size: 0.75rem; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(int.title || 'Interview')}</h5>
                <p style="margin: 0.15rem 0 0; font-size: 0.65rem; color: var(--text-secondary);">${escapeHtml(int.time || int.days || '')}</p>
            </div>
        </div>
    `).join('');
}

function renderActivityTimeline(activities) {
    const list = document.getElementById('recent-activity-list');
    if (!list) return;
    const display = Array.isArray(activities) ? activities : [];
    if (display.length === 0) {
        list.innerHTML = `<p style="text-align: center; color: var(--text-secondary); padding: 1.5rem 0.5rem; font-size: 0.75rem;">No recent activity</p>`;
        return;
    }
    list.innerHTML = display.slice(0, 4).map(act => `
        <div style="display: flex; align-items: flex-start; gap: 0.75rem;">
            <div style="width: 8px; height: 8px; border-radius: 50%; background: var(--primary); flex-shrink: 0; margin-top: 0.3rem; box-shadow: 0 0 0 3px rgba(124,58,237,0.12);"></div>
            <div style="flex: 1; min-width: 0;">
                <p style="margin: 0; font-size: 0.75rem; font-weight: 700; color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(act.text || act.title || act.message || 'Activity')}</p>
                <p style="margin: 0.15rem 0 0; font-size: 0.65rem; color: var(--text-secondary);">${getTimeAgo(act.timestamp || act.time || act.created_at) || 'Recently'}</p>
            </div>
        </div>
    `).join('');
}

function renderProfileChecklist(checklist) {
    const list = document.getElementById('profile-checklist');
    if (!list) return;
    let display = Array.isArray(checklist) && checklist.length > 0 ? checklist : [
        { label: 'Verify Email', completed: true },
        { label: 'Upload Resume', completed: true },
        { label: 'Complete Profile', completed: false },
        { label: 'Add Skills', completed: false }
    ];
    // TODO: move to backend — checklist stats from profile_strength
    const completed = display.filter(d => d.completed).length;
    const pct = Math.round((completed / display.length) * 100);
    list.innerHTML = `
        <div style="margin-bottom: 1rem;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
                <span style="font-size: 0.85rem; font-weight: 600;">Profile Strength</span>
                <span style="font-size: 0.85rem; font-weight: 700; color: var(--primary);">${pct}%</span>
            </div>
            <div style="height: 6px; background: rgba(0,0,0,0.1); border-radius: 3px; overflow: hidden;">
                <div style="width: ${pct}%; height: 100%; background: var(--primary); border-radius: 3px;"></div>
            </div>
        </div>
        ${display.map(item => `
            <div style="display: flex; align-items: center; gap: 0.75rem; padding: 0.5rem 0;">
                <i class="fas ${item.completed ? 'fa-check-circle text-emerald-500' : 'fa-circle text-slate-300'}" style="font-size: 1rem;"></i>
                <span style="font-size: 0.85rem;">${item.label}</span>
            </div>
`).join('')}
    `;
}

function capitalizeName(name) {
    if (!name) return '';
    return name.split(' ').map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()).join(' ');
}

function renderAICareerInsights(intel) {
    const marketDemand = document.getElementById('ai-market-demand');
    if (marketDemand) marketDemand.textContent = intel.market_demand || '--';

    const topSkillPct = document.getElementById('top-skill-pct');
    if (topSkillPct) topSkillPct.textContent = (intel.top_skill_pct ?? '--') + (intel.top_skill_pct != null ? '%' : '');

    const topSkillBar = document.getElementById('top-skill-bar');
    if (topSkillBar) topSkillBar.style.width = (intel.top_skill_pct ?? 0) + '%';

    const topRolePct = document.getElementById('top-role-pct');
    if (topRolePct) topRolePct.textContent = (intel.top_role_pct ?? '--') + (intel.top_role_pct != null ? '%' : '');

    const topRoleBar = document.getElementById('top-role-bar');
    if (topRoleBar) topRoleBar.style.width = (intel.top_role_pct ?? 0) + '%';
}

// ─── HERO HEADER ───
function updateHero(data, intel, score) {
    const name = capitalizeName(data.name || localStorage.getItem('userName') || 'Candidate');
    const nameEl = document.getElementById('candidate-name');
    if (nameEl) nameEl.textContent = name;

    const greetingEl = document.getElementById('dynamic-greeting');
    if (greetingEl) {
        const h = new Date().getHours();
        greetingEl.textContent = h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening';
    }

    const avatar = document.getElementById('candidate-avatar');
    if (avatar && data.avatar_url) {
        avatar.src = data.avatar_url;
    } else if (avatar) {
        avatar.src = `https://ui-avatars.com/api/?name=${encodeURIComponent(name)}&background=7C3AED&color=fff&bold=true`;
    }

    const ts = document.getElementById('last-analyzed-ts');
    if (ts && data.last_analyzed) {
        const d = new Date(data.last_analyzed);
        const now = new Date();
        const diff = Math.floor((now - d) / 60000);
        XSS.safeSetHTML(ts, `<i class="fas fa-sync-alt text-[8px]"></i> Analyzed ${diff < 1 ? 'just now' : diff < 60 ? diff + 'm ago' : Math.floor(diff/60) + 'h ago'}`);
    }

    const insightEl = document.getElementById('ai-market-insight');
    if (insightEl) {
        const mScore = Math.round(intel.market_score || 82);
        const hp = Math.round(intel.hiring_probability || 70);
        XSS.safeSetHTML(insightEl, `Your employability index is <span class="text-white font-black">outperforming ${mScore}%</span> of candidates. Hiring probability: <span class="text-emerald-400 font-black">${hp}%</span>`);
    }

    const statusEl = document.getElementById('employability-status');
    if (statusEl) {
        if (score >= 80) statusEl.textContent = 'Top Tier Talent';
        else if (score >= 65) statusEl.textContent = 'Strong Candidate';
        else if (score >= 45) statusEl.textContent = 'Developing Profile';
        else statusEl.textContent = 'Building Foundation';
    }

    // Recruiter Linking
    const recruiterBadge = document.getElementById('recruiter-link-badge');
    const recruiterVal = document.getElementById('recruiter-name-val');
    const recruiterRole = document.getElementById('recruiter-role-val');
    const recruiterImg = document.getElementById('recruiter-avatar-img');
    
    if (recruiterBadge && recruiterVal && intel.recruiter_name) {
        recruiterBadge.style.opacity = '1';
        recruiterVal.textContent = intel.recruiter_name;
        if (recruiterRole) recruiterRole.textContent = intel.recruiter_role || 'Recruiter';
        if (recruiterImg) recruiterImg.src = intel.recruiter_avatar || `https://ui-avatars.com/api/?name=${encodeURIComponent(intel.recruiter_name)}`;
    }
}

// ─── SCORE RING ANIMATION ───
function animateScoreRing(id, score) {
    const circle = document.getElementById(id);
    if (!circle) return;
    const radius = circle.r.baseVal.value;
    const circ = 2 * Math.PI * radius;
    circle.style.strokeDasharray = circ + ' ' + circ;
    circle.style.strokeDashoffset = circ;
    requestAnimationFrame(() => {
        circle.style.strokeDashoffset = circ - (Math.min(100, Math.max(0, score)) / 100) * circ;
    });
}

// ─── ANIMATE COUNTER ───
function animateCounter(el, start, end, duration, suffix = '') {
    const target = typeof el === 'string' ? document.getElementById(el) : el;
    if (!target) return;
    let startTime = null;
    const step = (ts) => {
        if (!startTime) startTime = ts;
        const progress = Math.min((ts - startTime) / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        target.textContent = Math.floor(eased * (end - start) + start) + suffix;
        if (progress < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
}

// ─── PIPELINE ───
function updatePipeline(status, interviewState) {
    const progress = document.getElementById('pipeline-progress');
    if (!progress) return;

    let activeSteps = 1;
    if (status === 'applied' || status === 'analyzed') activeSteps = 1;
    if (status === 'interviewing' || status === 'screening') activeSteps = 2;
    if (interviewState === 'in_progress') activeSteps = 3;
    if (interviewState === 'completed') activeSteps = 4;
    if (status === 'shortlisted' || status === 'technical') activeSteps = 5;
    if (status === 'final_round') activeSteps = 6;
    if (status === 'hired' || status === 'offer') activeSteps = 7;

    const pct = Math.min(100, Math.max(8, (activeSteps - 1) * 16));
    progress.style.width = pct + '%';

    for (let i = 0; i < 6; i++) {
        const step = document.getElementById('pipe-' + i);
        if (!step) continue;
        if (i < activeSteps - 1) {
            step.className = 'pipeline-step-circle completed';
            step.innerHTML = `<i class="fas fa-check text-xs text-white"></i>`;
        } else if (i === activeSteps - 1) {
            step.className = 'pipeline-step-circle active';
        } else {
            step.className = 'pipeline-step-circle inactive';
        }
    }
}

// ─── TALENT GRAPH RADAR ───
function renderTalentGraph(metrics) {
    const canvas = document.getElementById('talentGraphChart');
    if (!canvas) return;
    
    if (typeof Chart === 'undefined') {
        console.error("[Dashboard] Chart.js not loaded!");
        return;
    }
    
    const ctx = canvas.getContext('2d');
    const existing = Chart.getChart(canvas);
    if (existing) existing.destroy();

    const norm = normalizeSkillMetrics(metrics);
    const labels = Object.keys(norm);
    const values = Object.values(norm);

    new Chart(ctx, {
        type: 'radar',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: 'rgba(124, 58, 237, 0.15)',
                borderColor: '#7C3AED',
                borderWidth: 2,
                pointBackgroundColor: labels.map((_, i) => {
                    const colors = ['#7C3AED', '#06B6D4', '#A855F7', '#3B82F6', '#8B5CF6', '#10B981'];
                    return colors[i % colors.length];
                }),
                pointBorderColor: '#FFFFFF',
                pointRadius: 5,
                pointHoverRadius: 8,
                pointHoverBackgroundColor: '#FFFFFF',
                pointHoverBorderColor: '#7C3AED'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(11, 15, 26, 0.95)',
                    titleFont: { size: 11, weight: 'bold' },
                    bodyFont: { size: 11 },
                    padding: 12,
                    borderRadius: 12,
                    displayColors: false,
                    callbacks: {
                        label: (ctx) => `${ctx.raw}% proficiency`
                    }
                }
            },
            scales: {
                r: {
                    min: 0,
                    max: 100,
                    grid: { color: 'rgba(255,255,255,0.04)' },
                    angleLines: { color: 'rgba(255,255,255,0.04)' },
                    pointLabels: {
                        color: '#94A3B8',
                        font: { family: 'Plus Jakarta Sans', size: 10, weight: '700' }
                    },
                    ticks: { display: false, stepSize: 25 }
                }
            },
            animation: {
                duration: 1500,
                easing: 'easeOutQuart'
            }
        }
    });
}

// ─── INTERVIEW CENTER ───
function renderInterviewCenter(data) {
    const container = document.getElementById('interview-center-content');
    if (!container) return;

    const _iv = data.interview_entity || {};
    const state = (_iv.interview_state ?? data.interview_state) || 'not_started';
    const progress = (_iv.interview_progress ?? data.interview_progress) || 0;
    const badge = document.getElementById('interview-status-badge');

    if (state === 'completed') {
        if (badge) {
            badge.className = 'text-[8px] font-bold text-emerald-400 bg-emerald-400/10 px-2.5 py-1 rounded-full border border-emerald-400/20';
            badge.textContent = '✓ Complete';
        }
        container.innerHTML = `
            <div class="space-y-4">
                <div class="flex items-center gap-3 p-3 rounded-xl bg-emerald-500/5 border border-emerald-500/10">
                    <div class="w-10 h-10 rounded-full bg-emerald-500/10 flex items-center justify-center">
                        <i class="fas fa-check-circle text-emerald-400 text-lg"></i>
                    </div>
                    <div>
                        <p class="text-xs font-bold text-slate-200">Interview Complete</p>
                        <p class="text-[10px] text-slate-400">AI has finished analyzing your responses</p>
                    </div>
                </div>
                <div class="p-3 rounded-xl bg-white/[0.02] border border-white/[0.06]">
                    <div class="text-[9px] font-bold text-slate-500 uppercase tracking-wider mb-2">Performance</div>
                    <div class="progress-glow">
                        <div class="progress-glow-fill" style="width: ${Math.min(100, progress)}%"></div>
                    </div>
                    <p class="text-[10px] text-slate-400 mt-2">Overall progress: ${Math.round(progress)}%</p>
                </div>
                <a href="/applications" class="block w-full text-center py-2.5 rounded-xl bg-gradient-to-r from-purple-600 to-purple-700 text-white text-[10px] font-black uppercase tracking-widest hover:from-purple-500 transition">
                    View Full Report <i class="fas fa-arrow-right ml-1 text-[8px]"></i>
                </a>
            </div>
        `;
    } else if (state === 'in_progress') {
        if (badge) {
            badge.className = 'text-[8px] font-bold text-amber-400 bg-amber-400/10 px-2.5 py-1 rounded-full border border-amber-400/20';
            badge.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse inline-block mr-1"></span>In Progress';
        }
        container.innerHTML = `
            <div class="space-y-4">
                <div class="flex items-center gap-3 p-3 rounded-xl bg-amber-500/5 border border-amber-500/10">
                    <div class="w-10 h-10 rounded-full bg-amber-500/10 flex items-center justify-center">
                        <i class="fas fa-microphone text-amber-400 text-lg"></i>
                    </div>
                    <div>
                        <p class="text-xs font-bold text-slate-200">Interview in Progress</p>
                        <p class="text-[10px] text-slate-400">Continue your AI interview session</p>
                    </div>
                </div>
                <div class="progress-glow">
                    <div class="progress-glow-fill" style="width: ${Math.min(100, progress)}%"></div>
                </div>
                <div class="flex justify-between text-[10px] text-slate-400">
                    <span>${Math.round(progress)}% complete</span>
                    <span>AI analyzing in real-time</span>
                </div>
                <a href="/interview" class="block w-full text-center py-2.5 rounded-xl bg-gradient-to-r from-purple-600 to-purple-700 text-white text-[10px] font-black uppercase tracking-widest hover:from-purple-500 transition shadow-lg shadow-purple-500/20">
                    <i class="fas fa-play mr-1"></i> Resume Interview
                </a>
            </div>
        `;
    } else {
        if (badge) {
            badge.className = 'text-[8px] font-bold text-slate-500 bg-white/[0.03] px-2.5 py-1 rounded-full border border-white/[0.06]';
            badge.textContent = 'Not Started';
        }
        container.innerHTML = `
            <div class="space-y-4">
                <div class="flex items-center gap-3 p-3 rounded-xl bg-white/[0.02] border border-white/[0.06]">
                    <div class="w-10 h-10 rounded-full bg-purple-500/10 flex items-center justify-center">
                        <i class="fas fa-robot text-purple-400 text-lg"></i>
                    </div>
                    <div>
                        <p class="text-xs font-bold text-slate-200">AI Interview Ready</p>
                        <p class="text-[10px] text-slate-400">Start your AI-powered interview assessment</p>
                    </div>
                </div>
                <div class="grid grid-cols-3 gap-2 text-center">
                    <div class="p-2 rounded-lg bg-white/[0.02] border border-white/[0.06]">
                        <div class="text-[9px] font-black text-cyan-400">~15 min</div>
                        <div class="text-[7px] text-slate-500">Duration</div>
                    </div>
                    <div class="p-2 rounded-lg bg-white/[0.02] border border-white/[0.06]">
                        <div class="text-[9px] font-black text-purple-400">AI Powered</div>
                        <div class="text-[7px] text-slate-500">Assessment</div>
                    </div>
                    <div class="p-2 rounded-lg bg-white/[0.02] border border-white/[0.06]">
                        <p class="text-[10px] font-bold" id="stat-score-label">Excellent</p>
                        <div class="text-[7px] text-slate-500">Feedback</div>
                    </div>
                </div>
                <a href="/onboarding" class="block w-full text-center py-2.5 rounded-xl bg-gradient-to-r from-purple-600 to-purple-700 text-white text-[10px] font-black uppercase tracking-widest hover:from-purple-500 transition shadow-lg shadow-purple-500/20">
                    <i class="fas fa-play mr-1"></i> Start AI Interview
                </a>
            </div>
        `;
    }
}

// ─── CAREER INTELLIGENCE ───
function renderCareerIntelligence(ci, intel) {
    const container = document.getElementById('career-intel-content');
    if (!container) return;

    const mScore = ci.market_score || intel.market_score || 75;
    const hp = ci.hiring_probability || intel.hiring_probability || 65;
    const salary = ci.salary_estimation || intel.salary_prediction || {};
    const roles = ci.best_fitting_roles || [];
    const companies = ci.top_companies || [];

    container.innerHTML = `
        <div class="grid grid-cols-2 gap-3">
            <div class="p-3 rounded-xl bg-white/[0.02] border border-white/[0.06]">
                <div class="text-[8px] font-bold text-slate-500 uppercase tracking-wider mb-1">Market Demand</div>
                <div class="flex items-center gap-2">
                    <span class="text-lg font-black text-cyan-400">${mScore}%</span>
                    <span class="text-[9px] font-bold ${mScore >= 75 ? 'text-emerald-400' : 'text-amber-400'}">${mScore >= 75 ? 'High' : mScore >= 50 ? 'Moderate' : 'Low'}</span>
                </div>
            </div>
            <div class="p-3 rounded-xl bg-white/[0.02] border border-white/[0.06]">
                <div class="text-[8px] font-bold text-slate-500 uppercase tracking-wider mb-1">Hiring Probability</div>
                <div class="flex items-center gap-2">
                    <span class="text-lg font-black text-emerald-400">${hp}%</span>
                    <span class="text-[9px] font-bold text-slate-400">Match</span>
                </div>
            </div>
            <div class="p-3 rounded-xl bg-white/[0.02] border border-white/[0.06]">
                <div class="text-[8px] font-bold text-slate-500 uppercase tracking-wider mb-1">Salary Range</div>
                <div class="text-sm font-black text-white">$${salary.min || '--'}k - $${salary.max || '--'}k</div>
            </div>
            <div class="p-3 rounded-xl bg-white/[0.02] border border-white/[0.06]">
                <div class="text-[8px] font-bold text-slate-500 uppercase tracking-wider mb-1">Seniority</div>
                <div class="text-sm font-black text-purple-400">${ci.seniority_level || 'Mid'}</div>
            </div>
        </div>
        ${roles.length ? `
        <div class="p-3 rounded-xl bg-white/[0.02] border border-white/[0.06]">
            <div class="text-[8px] font-bold text-slate-500 uppercase tracking-wider mb-2">Best Fitting Roles</div>
            <div class="flex flex-wrap gap-1.5">
                ${roles.slice(0, 3).map(r => `<span class="text-[9px] px-2 py-1 rounded-full bg-purple-500/10 text-purple-300 border border-purple-500/20 font-semibold">${escapeHtml(r)}</span>`).join('')}
            </div>
        </div>` : ''}
        ${companies.length ? `
        <div class="p-3 rounded-xl bg-gradient-to-r from-cyan-500/5 to-blue-500/5 border border-cyan-500/10">
            <div class="text-[8px] font-bold text-cyan-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <i class="fas fa-building text-[7px]"></i> Top Matching Companies
            </div>
            <div class="flex flex-wrap gap-1.5">
                ${companies.slice(0, 4).map(c => `<span class="text-[9px] px-2 py-1 rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/20 font-semibold">${escapeHtml(c)}</span>`).join('')}
            </div>
        </div>` : ''}
    `;
}

// ─── INTELLIGENCE INSIGHTS ───
function renderIntelligenceInsights(analysis, intel) {
    const strengths = analysis.strengths || [];
    const weaknesses = analysis.weaknesses || analysis.gaps || [];

    const strengthsContainer = document.getElementById('strengths-container');
    if (strengthsContainer) {
        if (strengths.length === 0) {
            strengthsContainer.innerHTML = '<span class="text-[9px] text-slate-500 italic">Complete AI analysis to identify strengths</span>';
        } else {
            strengthsContainer.innerHTML = strengths.slice(0, 6).map(s => `
                <span class="stat-chip bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                    <i class="fas fa-plus-circle text-[7px]"></i> ${escapeHtml(typeof s === 'string' ? s : '')}
                </span>
            `).join('');
        }
    }

    const weaknessesContainer = document.getElementById('weaknesses-container');
    if (weaknessesContainer) {
        if (weaknesses.length === 0) {
            weaknessesContainer.innerHTML = '<span class="text-[9px] text-slate-500 italic">No critical gaps detected</span>';
        } else {
            weaknessesContainer.innerHTML = weaknesses.slice(0, 6).map(w => `
                <span class="stat-chip bg-amber-500/10 text-amber-300 border border-amber-500/20">
                    <i class="fas fa-arrow-trend-up text-[7px]"></i> ${escapeHtml(typeof w === 'string' ? w : '')}
                </span>
            `).join('');
        }
    }

    const marketText = document.getElementById('market-positioning-text');
    if (marketText) {
        const mp = analysis.market_positioning || intel.market_demand;
        if (mp) {
            marketText.textContent = typeof mp === 'string' ? mp : `Market Demand: ${mp}. Your profile shows strong alignment with current market needs.`;
        } else {
            marketText.textContent = "Complete your AI interview to see personalized market positioning insights.";
        }
    }
}

// ─── ACTION PLAN ───
function renderActionPlan(plan) {
    const container = document.getElementById('action-plan');
    if (!container) return;

    const steps = normalizeToArray(plan);
    if (steps.length === 0) {
        container.innerHTML = `<div class="p-6 text-center"><i class="fas fa-route text-2xl text-slate-500/30 mb-3"></i><p class="text-xs text-slate-500">Complete your AI analysis to generate a strategic roadmap.</p></div>`;
        return;
    }

    const emojis = ['🎯', '⚡', '💡', '🌟', '🚀', '📈'];
    container.innerHTML = steps.slice(0, 5).map((step, i) => `
        <div class="action-step animate-fade-up stagger-${i + 1}">
            <div class="action-step-dot">${emojis[i % emojis.length]}</div>
            <div class="p-3 rounded-xl bg-white/[0.02] border border-white/[0.06] hover:bg-purple-500/5 hover:border-purple-500/20 transition-all duration-300">
                <p class="text-xs font-semibold text-slate-300 leading-relaxed">${escapeHtml(step)}</p>
            </div>
        </div>
    `).join('');
}

// ─── AI ACTIVITY FEED ───
function renderAIActivity(activities) {
    const container = document.getElementById('ai-activity-feed');
    if (!container) return;

    if (!activities || activities.length === 0) {
        container.innerHTML = `
            <div class="flex items-center gap-3 py-3">
                <div class="activity-dot purple"></div>
                <div class="flex-1">
                    <p class="text-xs font-semibold text-slate-300">AI Analysis Queued</p>
                    <p class="text-[10px] text-slate-500">Waiting for initial data processing</p>
                </div>
                <span class="text-[8px] text-slate-600">just now</span>
            </div>
        `;
        return;
    }

    container.innerHTML = activities.slice(0, 6).map(a => {
        const color = a.color || 'purple';
        const icon = a.icon || 'fa-circle';
        const title = a.title || 'AI Event';
        const desc = a.description || '';
        const ts = a.timestamp || new Date().toISOString();
        const timeAgo = getTimeAgo(ts);
        return `
            <div class="activity-item animate-fade-in">
                <div class="activity-dot ${color}"></div>
                <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2">
                        <i class="fas ${icon} text-[9px] text-${color === 'purple' ? 'purple' : color === 'cyan' ? 'cyan' : color === 'emerald' ? 'emerald' : 'amber'}-400"></i>
                        <p class="text-[11px] font-bold text-slate-300 truncate">${title}</p>
                    </div>
                    <p class="text-[10px] text-slate-500 mt-0.5 truncate">${desc}</p>
                </div>
                <span class="text-[8px] text-slate-600 whitespace-nowrap">${timeAgo}</span>
            </div>
        `;
    }).join('');
}

// ─── UTILITIES ───
function normalizeSkillMetrics(raw) {
    const standard = { "Technical": 0, "Communication": 0, "Problem Solving": 0, "Adaptability": 0, "Confidence": 0 };
    if (!raw || Object.keys(raw).length === 0) {
        return { "Technical": 82, "Communication": 75, "Problem Solving": 78, "Adaptability": 70, "Confidence": 72 };
    }
    const extra = {};
    Object.entries(raw).forEach(([k, v]) => {
        const key = String(k).toLowerCase();
        const val = Math.min(100, Math.max(0, parseInt(v) || 50));
        if (key.includes('tech') || key.includes('coding') || key.includes('hard')) standard["Technical"] = val;
        else if (key.includes('soft') || key.includes('commun') || key.includes('verbal')) standard["Communication"] = val;
        else if (key.includes('problem') || key.includes('analyt') || key.includes('logic')) standard["Problem Solving"] = val;
        else if (key.includes('adapt') || key.includes('flexib') || key.includes('learn')) standard["Adaptability"] = val;
        else if (key.includes('confid') || key.includes('leader') || key.includes('manage')) standard["Confidence"] = val;
        else {
            let assigned = false;
            for (let sk in standard) { if (standard[sk] === 0) { standard[sk] = val; assigned = true; break; } }
            if (!assigned) {
                const cleanKey = k.length > 20 ? k.substring(0, 20) + '...' : k;
                extra[cleanKey] = val;
            }
        }
    });
    return { ...standard, ...extra };
}

function getTimeAgo(ts) {
    if (!ts) return 'now';
    const diff = Date.now() - new Date(ts).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'now';
    if (mins < 60) return mins + 'm ago';
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return hrs + 'h ago';
    const days = Math.floor(hrs / 24);
    return days + 'd ago';
}

function escapeHtml(v) {
    return String(v || '').replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
}

function normalizeToArray(v) {
    if (Array.isArray(v)) return v;
    if (typeof v === 'string') {
        try { const p = JSON.parse(v); return Array.isArray(p) ? p : [p]; } catch(e) { return v.split('\n').map(s => s.trim()).filter(Boolean); }
    }
    return [];
}

async function logout() {
    const keysToRemove = ['token', 'userName', 'userPhotoUrl', 'userRole', 'profileStrength', 'preferredTheme'];
    keysToRemove.forEach(k => localStorage.removeItem(k));
    document.cookie.split(';').forEach(c => {
        const name = c.trim().split('=')[0];
        document.cookie = name + '=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/';
    });
    window.location.href = '/login';
}

function filterApplications(filter) {
    dashCurrentFilter = filter;
    dashCurrentPage = 1;
    updateDashURL();

    const tabs = document.querySelectorAll('.app-tab');
    tabs.forEach(tab => {
        const isActive = tab.dataset.filter === filter;
        tab.style.color = isActive ? 'var(--primary)' : 'var(--text-secondary)';
        tab.style.borderBottomColor = isActive ? 'var(--primary)' : 'transparent';
        tab.style.fontWeight = isActive ? '800' : '600';
    });

    renderApplicationsTable(allApplications);
}

function changeDashPageSize(size) {
    dashPageSize = parseInt(size) || allApplications.length;
    dashCurrentPage = 1;
    updateDashURL();
    renderApplicationsTable(allApplications);
}

function goToDashPage(page) {
    const filtered = getDashFilteredApplications();
    const totalPages = dashPageSize > 0 ? Math.ceil(filtered.length / dashPageSize) : 1;
    if (page < 1 || page > totalPages) return;
    dashCurrentPage = page;
    updateDashURL();
    renderApplicationsTable(allApplications);
}

function getDashFilteredApplications() {
    if (dashCurrentFilter === 'all') return allApplications;
    return allApplications.filter(app => {
        const s = (app.status || '').toLowerCase();
        if (dashCurrentFilter === 'applied') return s === 'pending' || s === 'applied';
        if (dashCurrentFilter === 'in_review') return s === 'in_review';
        if (dashCurrentFilter === 'interview') return s === 'preselected' || s === 'interview';
        if (dashCurrentFilter === 'offer') return s === 'accepted' || s === 'offered';
        if (dashCurrentFilter === 'rejected') return s === 'rejected';
        if (dashCurrentFilter === 'withdrawn') return s === 'withdrawn';
        return true;
    });
}

function updateDashPagination(totalFiltered) {
    const totalPages = dashPageSize > 0 ? Math.ceil(totalFiltered / dashPageSize) : 1;
    if (dashCurrentPage > totalPages) dashCurrentPage = totalPages || 1;

    const start = dashPageSize > 0 ? (dashCurrentPage - 1) * dashPageSize : 0;
    const end = dashPageSize > 0 ? Math.min(start + dashPageSize, totalFiltered) : totalFiltered;

    const info = document.getElementById('dash-pagination-info');
    if (info) info.textContent = totalFiltered > 0 ? `${start + 1}-${end} of ${totalFiltered}` : '0 entries';

    const prevBtn = document.getElementById('dash-prev-page');
    const nextBtn = document.getElementById('dash-next-page');
    if (prevBtn) prevBtn.style.opacity = dashCurrentPage <= 1 ? '0.4' : '1';
    if (nextBtn) nextBtn.style.opacity = dashCurrentPage >= totalPages ? '0.4' : '1';

    const pageNumbers = document.getElementById('dash-page-numbers');
    if (pageNumbers) {
        let html = '';
        const maxVisible = 5;
        let startPage = Math.max(1, dashCurrentPage - Math.floor(maxVisible / 2));
        let endPage = Math.min(totalPages, startPage + maxVisible - 1);
        if (endPage - startPage < maxVisible - 1) startPage = Math.max(1, endPage - maxVisible + 1);
        for (let p = startPage; p <= endPage; p++) {
            const isActive = p === dashCurrentPage;
            html += `<button onclick="goToDashPage(${p})" style="padding:0.25rem 0.625rem;border:1px solid ${isActive ? 'var(--primary)' : 'var(--border-light)'};border-radius:6px;background:${isActive ? 'var(--primary)' : 'rgba(255,255,255,0.6)'};color:${isActive ? 'white' : 'var(--text-secondary)'};cursor:pointer;font-size:0.75rem;font-weight:${isActive ? '700' : '600'};transition:all 0.2s;">${p}</button>`;
        }
        pageNumbers.innerHTML = html;
    }
}

// ─── DEMO DATA ───
// DEMO_DATA was removed (CRIT-01): Fake fallback data masked real outages.
// The dashboard now shows a proper error state when APIs fail.

// ─── INIT ───
window.addEventListener('DOMContentLoaded', () => {
    initDashboard();
    // Safety net: remove skeletons after 12s if data never loaded
    setTimeout(() => {
        document.querySelectorAll('.skeleton').forEach(el => {
            el.style.background = 'none';
            el.style.animation = 'none';
            if (!el.textContent.trim()) {
                el.innerHTML = '<div style="padding:1rem;text-align:center;color:var(--text-secondary);font-size:0.7rem;">Unable to load</div>';
            }
        });
        const radarLoader = document.getElementById('radar-loader');
        if (radarLoader) radarLoader.style.display = 'none';
    }, 12000);
});

/**
 * RADAR MAP RENDERING
 */
function renderCompetencyRadar(intel) {
    const ctx = document.getElementById('competency-radar-chart');
    const loader = document.getElementById('radar-loader');
    if (!ctx) return;

    const RADAR_7D = ["Technical", "Communication", "Problem Solving", "Adaptability", "Confidence", "Consistency", "Soft Skills"];

    let labels, values;
    if (intel.radar && typeof intel.radar === 'object' && !Array.isArray(intel.radar)) {
        labels = RADAR_7D;
        values = RADAR_7D.map(dim => intel.radar[dim] ?? 50);
    } else {
        const metrics = intel.skill_metrics || {
            "Technical Proficiency": 85,
            "Communication": 75,
            "Analytical Thinking": 90,
            "Leadership & EQ": 65,
            "Adaptability": 80,
            "Strategic Planning": 70,
            "Business Acumen": 60,
            "Innovation": 82
        };
        labels = Object.keys(metrics);
        values = Object.values(metrics);
    }

    if (window.radarChartInstance) {
        window.radarChartInstance.destroy();
    }

    setTimeout(() => {
        if (loader) loader.style.display = 'none';

        if (typeof Chart === 'undefined') {
            console.error("[Dashboard] Chart.js not loaded — radar chart unavailable");
            if (ctx.parentElement) {
                ctx.parentElement.innerHTML = `<div style="text-align:center; padding:1.5rem; color:var(--text-secondary);">
                    <i class="fas fa-chart-area" style="font-size:1.5rem; opacity:0.3; margin-bottom:0.5rem;"></i>
                    <p style="font-size:0.7rem; font-weight:700;">Chart unavailable</p>
                </div>`;
            }
            return;
        }
        
        try {
            window.radarChartInstance = new Chart(ctx, {
                type: 'radar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Current Level',
                        data: values,
                        backgroundColor: 'rgba(99, 102, 241, 0.15)',
                        borderColor: '#6366F1',
                        borderWidth: 2,
                        pointBackgroundColor: '#6366F1',
                        pointBorderColor: '#fff',
                        pointHoverBackgroundColor: '#fff',
                        pointHoverBorderColor: '#6366F1',
                        pointRadius: 3
                    }, {
                        label: 'Market Benchmark',
                        data: labels.map(() => 75 + Math.random() * 15),
                        backgroundColor: 'rgba(148, 163, 184, 0.08)',
                        borderColor: 'rgba(148, 163, 184, 0.35)',
                        borderWidth: 1.5,
                        borderDash: [4, 4],
                        pointRadius: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        r: {
                            angleLines: { color: 'rgba(0,0,0,0.04)' },
                            grid: { color: 'rgba(0,0,0,0.04)' },
                            pointLabels: {
                                font: { family: 'Plus Jakarta Sans', size: 8, weight: '700' },
                                color: '#64748B'
                            },
                            ticks: { display: false, stepSize: 20 },
                            suggestedMin: 0,
                            suggestedMax: 100
                        }
                    },
                    plugins: {
                        legend: { display: false }
                    },
                    animation: { duration: 1500, easing: 'easeOutQuart' }
                }
            });
        } catch (e) {
            console.error("[Dashboard] Radar chart render failed:", e);
            if (ctx.parentElement) {
                ctx.parentElement.innerHTML = `<div style="text-align:center; padding:1.5rem; color:var(--text-secondary);">
                    <i class="fas fa-chart-area" style="font-size:1.5rem; opacity:0.3; margin-bottom:0.5rem;"></i>
                    <p style="font-size:0.7rem; font-weight:700;">Could not render</p>
                </div>`;
            }
        }
    }, 600);
}



/**
 * GAP ANALYSIS RENDERING
 */
function renderGapAnalysis(intel) {
    const container = document.getElementById('gap-analysis-container');
    if (!container) return;

    const gaps = intel.weaknesses_analysis || intel.gaps || intel.missing_critical_skills || [
        "Deepen Cloud Infrastructure knowledge",
        "Master Kubernetes & Containerization",
        "Enhance System Design for scale"
    ];

    const normalizedGaps = gaps.map(g => typeof g === 'string' ? g : (g.skill || g.area || g.reason || 'Improve skill depth')).filter(Boolean);

    container.innerHTML = normalizedGaps.slice(0, 3).map((gap, index) => {
        const icons = ['fa-cloud', 'fa-cubes', 'fa-layer-group'];
        return `
            <div style="display: flex; gap: 0.85rem; padding: 0.85rem; background: white; border-radius: 14px; border: 1px solid var(--border-light); transition: all 0.3s;" onmouseover="this.style.borderColor='var(--primary)'; this.style.transform='translateX(5px)'" onmouseout="this.style.borderColor='var(--border-light)'; this.style.transform='translateX(0)'">
                <div style="width: 34px; height: 34px; background: rgba(99, 102, 241, 0.1); border-radius: 10px; display: flex; align-items: center; justify-content: center; color: var(--primary); flex-shrink: 0; font-size: 0.8rem;">
                    <i class="fas ${icons[index] || 'fa-star'}"></i>
                </div>
                <div>
                    <h4 style="font-size: 0.7rem; font-weight: 800; color: var(--text-primary); margin: 0;">Step ${index + 1}</h4>
                    <p style="font-size: 0.65rem; color: var(--text-secondary); margin: 0.15rem 0 0 0; line-height: 1.3;">${escapeHtml(gap)}</p>
                </div>
            </div>
        `;
    }).join('');
}

/**
 * SUGGESTED JOBS RENDERING
 */
function renderSuggestedJobs(jobs) {
    const container = document.getElementById('suggested-jobs-list');
    if (!container) return;

    const savedJobIds = JSON.parse(localStorage.getItem('savedJobs') || '[]');

    const displayJobs = Array.isArray(jobs) && jobs.length > 0 ? jobs : [
        { title: 'Frontend Lead', company: 'Linear', location: 'Remote', match: 98, logo: 'https://ui-avatars.com/api/?name=Linear&background=000&color=fff' },
        { title: 'Senior React Dev', company: 'Vercel', location: 'Hybrid', match: 94, logo: 'https://ui-avatars.com/api/?name=Vercel&background=000&color=fff' },
        { title: 'Full Stack Engineer', company: 'Stripe', location: 'Remote', match: 92, logo: 'https://ui-avatars.com/api/?name=Stripe&background=635BFF&color=fff' }
    ];

    container.innerHTML = displayJobs.slice(0, 3).map(job => {
        const jobId = job.id || job.title;
        const isSaved = savedJobIds.includes(String(jobId));
        return `
        <div class="glass-card" style="padding: 1.5rem; display: flex; flex-direction: column; gap: 1rem; cursor: pointer; background: white; border-radius: 20px;" onclick="window.location.href='/candidate/jobs'">
            <div style="display: flex; align-items: flex-start; justify-content: space-between;">
                <div style="display: flex; gap: 1rem;">
                    <div style="width: 52px; height: 52px; background: white; border-radius: 14px; border: 1px solid var(--border-light); display: flex; align-items: center; justify-content: center; overflow: hidden; flex-shrink: 0;">
                        <img src="${escapeHtml(job.logo || 'https://ui-avatars.com/api/?name=C&background=6366F1&color=fff')}" style="width: 32px; height: 32px; object-fit: contain;" onerror="this.src='https://ui-avatars.com/api/?name=C&background=6366F1&color=fff'">
                    </div>
                    <div>
                        <h4 style="font-size: 1rem; font-weight: 800; color: var(--text-primary); margin: 0;">${escapeHtml(job.title)}</h4>
                        <p style="font-size: 0.85rem; color: var(--text-secondary); margin: 0.25rem 0 0 0;">${escapeHtml(job.company)} &bull; ${escapeHtml(job.location)}</p>
                    </div>
                </div>
                <div style="text-align: right; display: flex; flex-direction: column; align-items: flex-end; gap: 0.35rem;">
                    <div style="font-size: 1rem; font-weight: 900; color: var(--primary);">${escapeHtml(String(job.match))}%</div>
                    <div style="font-size: 0.6rem; color: var(--text-secondary); font-weight: 800; text-transform: uppercase;">Match</div>
                </div>
            </div>
            <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
                ${(job.tags || ['Remote', 'Urgent', 'AI Matched']).map(tag => `
                    <span style="padding: 0.3rem 0.6rem; background: #F1F5F9; color: #64748B; border-radius: 6px; font-size: 0.7rem; font-weight: 700;">${escapeHtml(tag)}</span>
                `).join('')}
            </div>
            <div style="display: flex; gap: 0.5rem; margin-top: 0.25rem;">
                <button onclick="event.stopPropagation(); window.location.href='/candidate/jobs'" style="flex: 1; padding: 0.5rem; background: var(--primary); color: white; border: none; border-radius: 10px; font-size: 0.75rem; font-weight: 700; cursor: pointer; font-family: inherit;">View Details</button>
                <button onclick="event.stopPropagation(); toggleDashSaveJob('${escapeHtml(String(jobId))}', this)" style="width: 36px; height: 36px; border-radius: 10px; border: 1px solid var(--border-light); background: white; color: ${isSaved ? 'var(--primary)' : 'var(--text-secondary)'}; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.2s;" title="${isSaved ? 'Unsave job' : 'Save job'}">
                    <i class="${isSaved ? 'fas' : 'far'} fa-bookmark"></i>
                </button>
            </div>
        </div>`;
    }).join('');
}

function toggleDashSaveJob(jobId, btn) {
    const savedJobIds = JSON.parse(localStorage.getItem('savedJobs') || '[]');
    const idx = savedJobIds.indexOf(jobId);
    if (idx > -1) {
        savedJobIds.splice(idx, 1);
        if (btn) {
            btn.style.color = 'var(--text-secondary)';
            btn.innerHTML = '<i class="far fa-bookmark"></i>';
        }
    } else {
        savedJobIds.push(jobId);
        if (btn) {
            btn.style.color = 'var(--primary)';
            btn.innerHTML = '<i class="fas fa-bookmark"></i>';
        }
    }
    localStorage.setItem('savedJobs', JSON.stringify(savedJobIds));
}

// ─── AUTO-REFRESH ON STATUS CHANGE ───
window.addEventListener('candidate-application-status-changed', async (e) => {
    const { applicationId, newStatus } = e.detail || {};
    console.log(`[Dashboard] Application ${applicationId} status changed to ${newStatus}, refreshing...`);

    if (allApplications.length > 0) {
        const app = allApplications.find(a => a.id == applicationId || a.application_id == applicationId);
        if (app) {
            app.status = newStatus;
            if (typeof renderApplicationsTable === 'function') {
                renderApplicationsTable(allApplications);
            }
            return;
        }
    }

    try {
        const apps = await window.fetchAPI(`/candidate/applications/me?t=${Date.now()}`);
        if (apps && apps.applications) {
            allApplications = apps.applications;
            if (typeof renderApplicationsTable === 'function') {
                renderApplicationsTable(allApplications);
            }
        }
    } catch (err) {
        console.warn('[Dashboard] Failed to refresh after status change:', err);
    }
});
