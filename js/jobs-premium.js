/**
 * PREMIUM JOB MARKETPLACE
 * Advanced filtering, grid/list views, infinite scroll, saved jobs
 */

document.addEventListener('DOMContentLoaded', async () => {
    const jobContainer = document.getElementById('jobs-container');
    if (!jobContainer) return;
    const filterContainer = document.getElementById('category-filters');
    const searchInput = document.getElementById('job-search');
    const locationInput = document.getElementById('location-search');
    const searchBtn = document.getElementById('search-btn');
    const resultsCount = document.getElementById('results-count');
    const liveJobsCount = document.getElementById('live-jobs-count');

    // Advanced Filters
    const advancedFiltersToggle = document.getElementById('advanced-filters-toggle');
    const advancedFiltersPanel = document.getElementById('advanced-filters-panel');
    const salaryFilter = document.getElementById('salary-filter');
    const experienceFilter = document.getElementById('experience-filter');
    const workTypeFilter = document.getElementById('work-type-filter');
    const jobTypeFilter = document.getElementById('job-type-filter');
    const applyFiltersBtn = document.getElementById('apply-filters-btn');
    const clearFiltersBtn = document.getElementById('clear-filters-btn');

    // View Toggle
    const gridViewBtn = document.getElementById('grid-view-btn');
    const listViewBtn = document.getElementById('list-view-btn');

    // Load More
    const loadMoreContainer = document.getElementById('load-more-container');
    const loadMoreBtn = document.getElementById('load-more-btn');

    // Mobile Menu
    const mobileMenuBtn = document.getElementById('mobile-menu-btn');
    const mobileMenu = document.getElementById('mobile-menu');

    // Config
    const API_BASE = window.CONFIG ? CONFIG.API_BASE_URL : 'http://localhost:8001';

    // State
    let currentCategoryId = null;
    let currentSearchTerm = '';
    let currentLocation = '';
    let currentFilters = {
        salary: '',
        experience: '',
        workType: '',
        jobType: ''
    };
    let currentView = 'grid'; // 'grid' or 'list'
    let allJobs = [];
    let displayedJobs = [];
    let savedJobs = JSON.parse(localStorage.getItem('savedJobs') || '[]');
    let searchTimeout;
    let currentPage = 1;
    const jobsPerPage = 12;

    // --- 1. Load Categories ---
    async function loadCategories() {
        if (!filterContainer) return;
        try {
            const response = await fetch(`${API_BASE}/api/v1/categories/job`);
            if (!response.ok) throw new Error('Failed to fetch categories');
            const categories = await response.json();

            let html = `<button onclick="filterJobs(null)" class="pg-filter-pill ${currentCategoryId === null ? 'active' : ''}">All Jobs</button>`;

            categories.forEach(cat => {
                const isActive = currentCategoryId === cat.id;
                html += `<button onclick="filterJobs(${cat.id})" class="pg-filter-pill ${isActive ? 'active' : ''}">${cat.name}</button>`;
            });

            filterContainer.innerHTML = html;

        } catch (e) {
            console.error("Category Load Error", e);
            filterContainer.innerHTML = '';
        }
    }

    // --- 2. Load Jobs ---
    async function loadJobs(catId = null, search = '', location = '', filters = {}, append = false) {
        if (!append) {
            currentPage = 1;
            displayedJobs = [];
        }

        currentCategoryId = catId;
        currentSearchTerm = search;
        currentLocation = location;
        currentFilters = filters;

        if (!append) {
            // Skeleton loading cards
            const skeletons = Array(6).fill(0).map(() => `
                <div class="pg-glass-card pg-p-6">
                    <div class="pg-spinner" style="margin: 2rem auto;"><div class="pg-spinner-ring"></div></div>
                </div>
            `).join('');
            jobContainer.innerHTML = skeletons;
        }

        // Update Filters UI
        if (!append) loadCategories();

        try {
            // Build query params
            let endpoint = '/api/v1/jobs/public?';
            if (catId) endpoint += `category_id=${catId}&`;
            if (search) endpoint += `search=${encodeURIComponent(search)}&`;
            if (location) endpoint += `location=${encodeURIComponent(location)}&`;

            const response = await fetch(`${API_BASE}${endpoint}`);
            if (!response.ok) throw new Error('Failed to fetch jobs');
            const jobs = await response.json();

            // Apply client-side advanced filters
            allJobs = applyAdvancedFilters(jobs, filters);

            // Update live count
            if (liveJobsCount) liveJobsCount.textContent = allJobs.length;

            // Pagination
            const startIndex = (currentPage - 1) * jobsPerPage;
            const endIndex = startIndex + jobsPerPage;
            const jobsToDisplay = allJobs.slice(startIndex, endIndex);

            displayedJobs = append ? [...displayedJobs, ...jobsToDisplay] : jobsToDisplay;

            if (allJobs.length === 0) {
                jobContainer.innerHTML = `
                    <div class="pg-col-span-full pg-empty-state">
                        <div style="font-size: 3rem; margin-bottom: 1rem;"><i class="fas fa-search"></i></div>
                        <h3 class="pg-h3">No jobs found</h3>
                        <p>We couldn't find any jobs matching your criteria. Try adjusting your filters or search terms.</p>
                        <div class="pg-flex pg-justify-center pg-gap-3 pg-mt-4">
                            <button onclick="clearAllFilters()" class="pg-btn pg-btn-primary"><i class="fas fa-times pg-mr-2"></i>Clear Filters</button>
                            <button onclick="filterJobs(null)" class="pg-btn pg-btn-secondary"><i class="fas fa-briefcase pg-mr-2"></i>Browse All Jobs</button>
                        </div>
                    </div>
                `;
                resultsCount.textContent = '0';
                loadMoreContainer.classList.add('pg-hidden');
                return;
            }

            // Update results count
            resultsCount.textContent = allJobs.length;

            // Render jobs
            renderJobs(displayedJobs, append);

            // Show/hide load more button
            if (endIndex < allJobs.length) {
                loadMoreContainer.classList.remove('pg-hidden');
            } else {
                loadMoreContainer.classList.add('pg-hidden');
            }

        } catch (e) {
            console.error(e);
            jobContainer.innerHTML = `<div class="pg-col-span-full pg-empty-state" style="color:var(--pg-rose);">Failed to load jobs. The backend server might be offline.</div>`;
        }
    }

    // --- 3. Apply Advanced Filters (Client-side) ---
    function applyAdvancedFilters(jobs, filters) {
        return jobs.filter(job => {
            // Salary filter
            if (filters.salary) {
                const salary = parseSalary(job.salary_range);
                const [min, max] = filters.salary.split('-').map(s => parseInt(s.replace(/\D/g, '')));
                if (max && (salary < min || salary > max)) return false;
                if (!max && salary < min) return false;
            }

            // Experience filter
            if (filters.experience) {
                const exp = job.experience_level?.toLowerCase() || '';
                if (!exp.includes(filters.experience)) return false;
            }

            // Work type filter
            if (filters.workType) {
                const workType = job.work_type?.toLowerCase() || job.location?.toLowerCase() || '';
                if (!workType.includes(filters.workType)) return false;
            }

            // Job type filter
            if (filters.jobType) {
                const jobType = job.job_type?.toLowerCase() || '';
                if (!jobType.includes(filters.jobType)) return false;
            }

            return true;
        });
    }

    // Helper: Parse salary from string
    function parseSalary(salaryStr) {
        if (!salaryStr) return 0;
        const match = salaryStr.match(/\d+/);
        return match ? parseInt(match[0]) * 1000 : 0;
    }

    // Helper: Get company name as string (handles object or string)
    function companyName(job) {
        const c = job.company;
        if (!c) return 'Company';
        if (typeof c === 'object') return c.name || c.company_name || 'Company';
        return String(c);
    }

    // --- 4. Render Jobs ---
    function renderJobs(jobs, append = false) {
        const html = jobs.map(job => currentView === 'grid' ? renderJobCardGrid(job) : renderJobCardList(job)).join('');

        if (append) {
            jobContainer.innerHTML += html;
        } else {
            jobContainer.innerHTML = html;
        }
    }

    // --- 5. Job Card Templates ---
    function renderJobCardGrid(job) {
        const isSaved = savedJobs.includes(job.id);
        const isFeatured = job.is_featured || false;
        const isHot = job.is_hot || false;

        return `
            <div class="pg-glass-card pg-p-6" style="position: relative; border: ${isFeatured ? '1px solid var(--pg-primary)' : '1px solid var(--pg-glass-border)'};">
                ${isFeatured ? '<span class="pg-badge pg-badge-glass" style="position: absolute; top: 1rem; right: 1rem; background: var(--pg-primary); color: white;"><i class="fas fa-star pg-mr-1"></i> Featured</span>' : ''}
                ${isHot ? '<span class="pg-badge pg-badge-glass" style="position: absolute; top: 1rem; right: 1rem; background: var(--pg-rose); color: white;"><i class="fas fa-fire pg-mr-1"></i> Hot</span>' : ''}
                
                <div class="pg-flex pg-justify-between pg-items-start pg-mb-4">
                    <div class="pg-flex pg-items-center pg-gap-4">
                        <img src="${job.logo_url || 'https://ui-avatars.com/api/?name=' + encodeURIComponent(companyName(job)) + '&background=6366f1&color=fff'}" 
                             style="width: 56px; height: 56px; border-radius: 12px; object-fit: cover;">
                        <div>
                            <a href="/job-details?id=${job.id}" style="text-decoration: none; color: inherit;">
                                <h3 class="pg-h3">${job.title}</h3>
                            </a>
                            <div class="pg-small">${companyName(job)}</div>
                        </div>
                    </div>
                    <button onclick="toggleSaveJob(${job.id})" style="background:none; border:none; cursor:pointer; color: ${isSaved ? 'var(--pg-rose)' : 'var(--pg-ink-m)'}; margin-top: ${isFeatured || isHot ? '2rem' : '0'};">
                        <i class="${isSaved ? 'fas' : 'far'} fa-heart" style="font-size: 1.25rem;"></i>
                    </button>
                </div>

                <div class="pg-flex pg-flex-wrap pg-items-center pg-gap-3 pg-small pg-mb-4">
                    <span class="pg-flex pg-items-center pg-gap-1"><i class="fas fa-map-marker-alt"></i> ${job.location || 'Remote'}</span>
                    <span>•</span>
                    <span class="pg-flex pg-items-center pg-gap-1"><i class="fas fa-briefcase"></i> ${job.job_type || 'Full-time'}</span>
                    <span>•</span>
                    <span class="pg-flex pg-items-center pg-gap-1"><i class="fas fa-clock"></i> ${getTimeAgo(job.created_at)}</span>
                </div>

                <div class="pg-flex pg-flex-wrap pg-gap-2 pg-mb-4">
                    ${job.required_skills ? job.required_skills.split(',').slice(0, 4).map(s => `<span class="pg-badge pg-badge-glass">${s.trim()}</span>`).join('') : ''}
                </div>

                <div class="pg-flex pg-justify-between pg-items-center" style="padding-top: 1rem; border-top: 1px solid var(--pg-glass-border);">
                    <div>
                        <div style="font-weight: 700; color: var(--pg-ink);">${job.salary_range || 'Competitive'}</div>
                        <div class="pg-small" style="color: var(--pg-emerald); font-weight: 700;">Verified Role</div>
                    </div>
                    <a href="/signup?job_id=${job.id}" class="pg-btn pg-btn-primary">
                        Apply Now
                    </a>
                </div>
            </div>
        `;
    }

    function renderJobCardList(job) {
        const isSaved = savedJobs.includes(job.id);
        const isFeatured = job.is_featured || false;

        return `
            <div class="pg-glass-card pg-flex pg-gap-6 pg-items-center pg-p-6" style="border: ${isFeatured ? '1px solid var(--pg-primary)' : '1px solid var(--pg-glass-border)'}; flex-wrap: wrap;">
                <div class="pg-flex pg-items-center pg-gap-4 pg-flex-1" style="min-width: 300px;">
                    <img src="${job.logo_url || 'https://ui-avatars.com/api/?name=' + encodeURIComponent(companyName(job)) + '&background=6366f1&color=fff'}" 
                         style="width: 56px; height: 56px; border-radius: 12px; object-fit: cover; flex-shrink: 0;">
                    <div>
                        <div class="pg-flex pg-items-center pg-gap-2 pg-mb-1">
                            <a href="/job-details?id=${job.id}" style="text-decoration: none; color: inherit;">
                                <h3 class="pg-h3">${job.title}</h3>
                            </a>
                            ${isFeatured ? '<span class="pg-badge pg-badge-glass" style="background: var(--pg-primary); color: white;"><i class="fas fa-star pg-mr-1"></i> Featured</span>' : ''}
                        </div>
                        <div class="pg-flex pg-flex-wrap pg-items-center pg-gap-3 pg-small">
                            <span style="font-weight: 700; color: var(--pg-ink);">${companyName(job)}</span>
                            <span>•</span>
                            <span class="pg-flex pg-items-center pg-gap-1"><i class="fas fa-map-marker-alt"></i> ${job.location || 'Remote'}</span>
                            <span>•</span>
                            <span>${job.salary_range || 'Competitive'}</span>
                        </div>
                    </div>
                </div>
                
                <div class="pg-flex pg-items-center pg-gap-4" style="min-width: 200px;">
                    <div class="pg-flex pg-flex-wrap pg-gap-2" style="max-width: 200px;">
                        ${job.required_skills ? job.required_skills.split(',').slice(0, 3).map(s => `<span class="pg-badge pg-badge-glass">${s.trim()}</span>`).join('') : ''}
                    </div>
                    <button onclick="toggleSaveJob(${job.id})" style="background:none; border:none; cursor:pointer; color: ${isSaved ? 'var(--pg-rose)' : 'var(--pg-ink-m)'};">
                        <i class="${isSaved ? 'fas' : 'far'} fa-heart" style="font-size: 1.25rem;"></i>
                    </button>
                    <a href="/signup?job_id=${job.id}" class="pg-btn pg-btn-primary">
                        Apply
                    </a>
                </div>
            </div>
        `;
    }

    // --- 6. Helper Functions ---
    function getTimeAgo(dateStr) {
        if (!dateStr) return 'Recently';
        const date = new Date(dateStr);
        const now = new Date();
        const diffMs = now - date;
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

        if (diffDays === 0) return 'Today';
        if (diffDays === 1) return 'Yesterday';
        if (diffDays < 7) return `${diffDays} days ago`;
        if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
        return `${Math.floor(diffDays / 30)} months ago`;
    }

    // --- 7. Event Listeners ---

    // Advanced Filters Toggle
    if (advancedFiltersToggle) {
        advancedFiltersToggle.addEventListener('click', () => {
            advancedFiltersPanel.classList.toggle('pg-hidden');
            const icon = advancedFiltersToggle.querySelector('i');
            icon.classList.toggle('fa-sliders-h');
            icon.classList.toggle('fa-times');
        });
    }

    // Apply Filters
    if (applyFiltersBtn) {
        applyFiltersBtn.addEventListener('click', () => {
            const filters = {
                salary: salaryFilter.value,
                experience: experienceFilter.value,
                workType: workTypeFilter.value,
                jobType: jobTypeFilter.value
            };
            loadJobs(currentCategoryId, currentSearchTerm, currentLocation, filters);
            advancedFiltersPanel.classList.add('pg-hidden');
        });
    }

    // Clear Filters
    if (clearFiltersBtn) {
        clearFiltersBtn.addEventListener('click', () => {
            salaryFilter.value = '';
            experienceFilter.value = '';
            workTypeFilter.value = '';
            jobTypeFilter.value = '';
            loadJobs(currentCategoryId, currentSearchTerm, currentLocation, {});
        });
    }

    // Search
    if (searchBtn) {
        searchBtn.addEventListener('click', () => {
            loadJobs(currentCategoryId, searchInput.value.trim(), locationInput.value.trim(), currentFilters);
        });
    }

    if (searchInput) {
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                loadJobs(currentCategoryId, searchInput.value.trim(), locationInput.value.trim(), currentFilters);
            }
        });

        // Debounced search
        searchInput.addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                loadJobs(currentCategoryId, e.target.value.trim(), locationInput.value.trim(), currentFilters);
            }, 600);
        });
    }

    // View Toggle
    if (gridViewBtn) {
        gridViewBtn.addEventListener('click', () => {
            currentView = 'grid';
            gridViewBtn.classList.add('active');
            listViewBtn.classList.remove('active');
            renderJobs(displayedJobs);
        });
    }

    if (listViewBtn) {
        listViewBtn.addEventListener('click', () => {
            currentView = 'list';
            listViewBtn.classList.add('active');
            gridViewBtn.classList.remove('active');
            renderJobs(displayedJobs);
        });
    }

    // Load More
    if (loadMoreBtn) {
        loadMoreBtn.addEventListener('click', () => {
            currentPage++;
            loadJobs(currentCategoryId, currentSearchTerm, currentLocation, currentFilters, true);
        });
    }

    // Mobile Menu
    if (mobileMenuBtn) {
        mobileMenuBtn.addEventListener('click', () => {
            mobileMenu.classList.toggle('open');
        });
    }

    // Global Functions
    window.filterJobs = (catId) => {
        loadJobs(catId, currentSearchTerm, currentLocation, currentFilters);
    };

    window.toggleSaveJob = (jobId) => {
        const index = savedJobs.indexOf(jobId);
        if (index > -1) {
            savedJobs.splice(index, 1);
        } else {
            savedJobs.push(jobId);
        }
        localStorage.setItem('savedJobs', JSON.stringify(savedJobs));
        renderJobs(displayedJobs); // Re-render to update heart icons
    };

    window.clearAllFilters = () => {
        currentCategoryId = null;
        currentSearchTerm = '';
        currentLocation = '';
        currentFilters = {};
        searchInput.value = '';
        locationInput.value = '';
        salaryFilter.value = '';
        experienceFilter.value = '';
        workTypeFilter.value = '';
        jobTypeFilter.value = '';
        loadJobs();
    };

    // Init
    loadCategories();
    loadJobs();

    // Back to Top button visibility
    const backToTopBtn = document.getElementById('back-to-top');
    if (backToTopBtn) {
        window.addEventListener('scroll', () => {
            if (window.scrollY > 500) {
                backToTopBtn.classList.remove('opacity-0', 'pointer-events-none');
            } else {
                backToTopBtn.classList.add('opacity-0', 'pointer-events-none');
            }
        });
    }
});
