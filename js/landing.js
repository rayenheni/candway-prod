// Main Landing Page Logic
document.addEventListener('DOMContentLoaded', () => {
    // Initialize Animations
    initScrollAnimations();

    // Fetch Live Stats
    fetchPlatformStats();

    // Initialize Role Tabs (if any exist on page)
    // Initialize Role Tabs (if any exist on page)
    initTabs();

    // Fetch Latest Jobs (New)
    // Fetch Latest Jobs (New)
    fetchLatestJobs();

    // Initialize Recruiter Stats
    initRecruiterStats();
});

// --- 3. Fetch Latest Jobs ---
async function fetchLatestJobs() {
    const container = document.getElementById('latest-jobs-container');
    if (!container) return;

    try {
        // Fetch jobs without authentication
        const response = await fetch(`${window.CONFIG.API_BASE_URL}/api/v1/jobs/public`);

        // If endpoint doesn't exist or fails, show placeholder
        if (!response.ok) {
            container.innerHTML = `
                <div class="col-span-full text-center py-12">
                    <div class="text-slate-400 mb-4">
                        <i class="fas fa-briefcase text-4xl"></i>
                    </div>
                    <p class="text-slate-500 font-medium">Check out our job marketplace</p>
                    <a href="/jobs" class="mt-4 inline-block px-6 py-2 bg-indigo-600 text-white rounded-lg font-bold hover:bg-indigo-700 transition">
                        Browse Jobs
                    </a>
                </div>
            `;
            return;
        }

        const jobs = await response.json();

        // Take top 3
        const recentJobs = jobs.slice(0, 3);

        if (recentJobs.length === 0) {
            XSS.setHTML(container, '<div class="col-span-full text-center text-slate-500">No opportunities available at the moment.</div>');
            return;
        }

        XSS.setHTML(container, recentJobs.map(job => `
            <div class="group relative bg-white p-6 rounded-3xl border border-slate-100 shadow-sm hover:shadow-xl hover:-translate-y-1 transition-all duration-300 cursor-pointer overflow-hidden job-card">

                <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-indigo-500 to-purple-500 transform scale-x-0 group-hover:scale-x-100 transition-transform duration-300 origin-left"></div>

                <div class="flex justify-between items-start mb-5">
                    <div class="flex items-center gap-4">
                        <div class="w-14 h-14 rounded-2xl bg-white shadow-md border border-slate-100 p-1 flex items-center justify-center overflow-hidden shrink-0">
                            <img src="${XSS.sanitizeURL(job.logo_url)}" alt="${XSS.escapeHTML(job.company)}" class="w-full h-full object-cover rounded-xl">
                        </div>
                        <div>
                            <h3 class="font-bold text-lg text-slate-900 leading-tight group-hover:text-indigo-600 transition line-clamp-1">${XSS.escapeHTML(job.title)}</h3>
                            <div class="text-sm text-slate-500 flex items-center gap-2 mt-1">
                                <span class="font-medium text-slate-700">${XSS.escapeHTML(job.company)}</span>
                                <span class="w-1 h-1 bg-slate-300 rounded-full"></span>
                                <span class="truncate max-w-[100px]">${XSS.escapeHTML(job.location)}</span>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="flex flex-wrap gap-2 mb-6">
                    <span class="px-2.5 py-1 rounded-lg bg-indigo-50 text-indigo-700 text-xs font-bold border border-indigo-100 flex items-center gap-1">
                        <i class="fas fa-briefcase text-[10px]"></i> ${XSS.escapeHTML(job.type)}
                    </span>
                    ${job.required_skills ? job.required_skills.split(',').slice(0, 2).map(skill =>
            `<span class="px-2.5 py-1 rounded-lg bg-slate-50 text-slate-600 text-xs font-medium border border-slate-100">${XSS.escapeHTML(skill.trim())}</span>`
        ).join('') : ''}
                </div>

                <div class="flex items-center justify-between pt-4 border-t border-slate-50 mt-auto">
                    <div>
                        <div class="text-xs text-slate-400 font-bold uppercase tracking-wider mb-0.5">Salary Range</div>
                        <div class="font-black text-slate-900 text-lg">${XSS.escapeHTML(job.salary_range || '')}</div>
                    </div>
                    <div class="w-10 h-10 rounded-full bg-slate-50 group-hover:bg-indigo-600 group-hover:text-white flex items-center justify-center text-slate-400 transition-colors duration-300 shadow-sm">
                        <i class="fas fa-arrow-right -rotate-45 group-hover:rotate-0 transition-transform duration-300"></i>
                    </div>
                </div>
            </div>
        `).join(''));

        container.querySelectorAll('.job-card').forEach(card => {
            card.addEventListener('click', () => { window.location.href = '/jobs'; });
        });

    } catch (error) {
        console.error("Failed to fetch jobs");
        XSS.setHTML(container, `
            <div class="col-span-full text-center py-12">
                <div class="text-slate-400 mb-4">
                    <i class="fas fa-briefcase text-4xl"></i>
                </div>
                <p class="text-slate-500 font-medium">Explore our job marketplace</p>
                <a href="/jobs" class="mt-4 inline-block px-6 py-2 bg-indigo-600 text-white rounded-lg font-bold hover:bg-indigo-700 transition">
                    Browse Jobs
                </a>
            </div>
        `);
    }
}

// --- 2. Live Stats Counter (with Null Checks) ---
async function fetchPlatformStats() {
    try {
        // Try to fetch stats, but don't redirect if it fails
        const response = await fetch(`${window.CONFIG.API_BASE_URL}/api/v1/stats/public`);

        let stats = {
            candidates: 12000,
            jobs: 800,
            interviews: 150,
            companies: 500
        };

        if (response.ok) {
            const data = await response.json();
            stats = {
                candidates: data.verified_talent || 12000,
                jobs: data.active_jobs || 800,
                interviews: data.interviews_today || 150,
                companies: data.hiring_companies || 500
            };
        }

        // Animate only if elements exist
        animateValue("stat-candidates", 0, stats.candidates, 2000);
        animateValue("stat-jobs", 0, stats.jobs, 2000);
        animateValue("stat-interviews", 0, stats.interviews, 2000);
        animateValue("stat-companies", 0, stats.companies, 2000);

    } catch (error) {
        console.error("Failed to fetch stats:", error);
        // Use default values on error
        animateValue("stat-candidates", 0, 12000, 2000);
        animateValue("stat-jobs", 0, 800, 2000);
        animateValue("stat-interviews", 0, 150, 2000);
        animateValue("stat-companies", 0, 500, 2000);
    }
}

function initRecruiterStats() {
    // Check if elements exist
    if (document.getElementById('stat-time-hire')) {
        animateValue("stat-time-hire", 0, 72, 2000, "h");
        animateValue("stat-retention", 0, 98, 2000, "%");
        animateValue("stat-hiring-speed", 0, 3, 2000, "x");
    }
}

function animateValue(id, start, end, duration, customSuffix = null) {
    const obj = document.getElementById(id);
    if (!obj) return; // Exit if element doesn't exist on this page

    // Add '+' symbol if end is large or specific ID, unless customSuffix is provided
    let suffix = customSuffix;
    if (suffix === null) {
        suffix = (id === 'stat-companies' || end > 1000) ? "+" : "";
    }

    let startTimestamp = null;
    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);

        // Easing (Out Quart)
        const ease = 1 - Math.pow(1 - progress, 4);

        const current = Math.floor(progress * (end - start) + start);
        obj.textContent = current.toLocaleString() + suffix;

        if (progress < 1) {
            window.requestAnimationFrame(step);
        } else {
            obj.textContent = end.toLocaleString() + suffix;
        }
    };
    window.requestAnimationFrame(step);
}

function initScrollAnimations() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('active');
            }
        });
    }, { threshold: 0.1 });

    document.querySelectorAll('.reveal').forEach(el => observer.observe(el));
}

function initTabs() {
    const tabs = document.querySelectorAll('.role-tab');
    const contents = document.querySelectorAll('.role-content');

    if (tabs.length === 0) return;

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => {
                t.classList.remove('bg-indigo-600', 'text-white', 'shadow-lg', 'active');
                t.classList.add('text-slate-500');
            });
            tab.classList.remove('text-slate-500');
            tab.classList.add('bg-indigo-600', 'text-white', 'shadow-lg', 'active');
            contents.forEach(c => c.classList.add('hidden'));

            const targetId = tab.getAttribute('data-target');
            const targetContent = document.getElementById(targetId);
            if (targetContent) {
                targetContent.classList.remove('hidden');
                targetContent.classList.add('animate-fade-in');
            }
        });
    });
}
