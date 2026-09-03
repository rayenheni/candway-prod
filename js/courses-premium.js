/**
 * PREMIUM COURSE MARKETPLACE
 * Dynamic loading, ratings, wishlist, instructor profiles
 */

document.addEventListener('DOMContentLoaded', async () => {
    const courseContainer = document.getElementById('courses-container');
    const featuredContainer = document.getElementById('featured-course');
    const categoryFilters = document.getElementById('category-filters');
    const searchInput = document.getElementById('course-search');
    const resultsCount = document.getElementById('results-count');
    const viewToggleGrid = document.getElementById('grid-view-btn');
    const viewToggleList = document.getElementById('list-view-btn');
    const sortSelect = document.getElementById('sort-select');
    const mobileMenuBtn = document.getElementById('mobile-menu-btn');
    const mobileMenu = document.getElementById('mobile-menu');

    // Config
    const API_BASE = window.CONFIG ? CONFIG.API_BASE_URL : 'http://localhost:8001';

    // State
    let currentCategoryId = null;
    let currentSearchTerm = '';
    let currentView = 'grid';
    let currentSort = 'popular';
    let allCourses = [];
    let wishlist = JSON.parse(localStorage.getItem('courseWishlist') || '[]');
    let searchTimeout;

    // --- 1. Load Categories (Extract from courses) ---
    async function loadCategories(courses = []) {
        if (!categoryFilters) return;

        // Extract unique categories from courses
        const categories = [...new Set(courses.map(c => c.category).filter(Boolean))];

        let html = `<button onclick="filterCourses(null)" class="pg-filter-pill ${currentCategoryId === null ? 'active' : ''}">All Courses</button>`;

        categories.forEach((catName, index) => {
            const isActive = currentCategoryId === catName;
            html += `<button onclick="filterCourses('${catName}')" class="pg-filter-pill ${isActive ? 'active' : ''}">${catName}</button>`;
        });

        categoryFilters.innerHTML = html;
    }

    // --- 2. Load Courses ---
    async function loadCourses(catName = null, search = '') {
        currentCategoryId = catName;
        currentSearchTerm = search;

        if (courseContainer) {
            courseContainer.innerHTML = `
                <div class="pg-col-span-full pg-text-center pg-py-12">
                    <div class="pg-spinner pg-mb-4" style="margin-left:auto;margin-right:auto;"><div class="pg-spinner-ring"></div></div>
                    <p>Loading Premium Courses...</p>
                </div>
            `;
        }

        try {
            let endpoint = '/api/v1/courses/public?';
            if (search) endpoint += `search=${encodeURIComponent(search)}&`;

            const response = await fetch(`${API_BASE}${endpoint}`);
            if (!response.ok) throw new Error('Failed to fetch courses');
            const courses = await response.json();

            // Filter by category name if provided
            allCourses = catName ? courses.filter(c => c.category === catName) : courses;

            // Filter by search term if provided
            if (search) {
                allCourses = allCourses.filter(c =>
                    c.title.toLowerCase().includes(search.toLowerCase()) ||
                    (c.description && c.description.toLowerCase().includes(search.toLowerCase()))
                );
            }

            // Load categories from all courses (not filtered)
            loadCategories(courses);

            // Sort courses
            sortCourses();

            // Update results count
            if (resultsCount) resultsCount.textContent = allCourses.length;

            if (allCourses.length === 0) {
                if (courseContainer) {
                    courseContainer.innerHTML = `
                        <div class="pg-col-span-full pg-empty-state">
                            <div style="font-size: 3rem; margin-bottom: 1rem;">📚</div>
                            <h3 class="pg-h3">No courses found</h3>
                            <p>Try adjusting your search or filters.</p>
                            <button onclick="clearFilters()" class="pg-btn pg-btn-secondary" style="margin-top: 1rem;">Clear Filters</button>
                        </div>
                    `;
                }
                return;
            }

            // Load featured course (first course or random)
            if (featuredContainer && allCourses.length > 0) {
                const featured = allCourses.find(c => c.is_featured) || allCourses[0];
                renderFeaturedCourse(featured);
            }

            // Render courses
            renderCourses(allCourses);

        } catch (e) {
            console.error(e);
            if (courseContainer) {
                courseContainer.innerHTML = `<div class="col-span-full text-center text-red-500 py-10 bg-red-50 rounded-lg">Failed to load courses. The backend server might be offline.</div>`;
            }
        }
    }

    // --- 3. Sort Courses ---
    function sortCourses() {
        switch (currentSort) {
            case 'popular':
                allCourses.sort((a, b) => (b.student_count || 0) - (a.student_count || 0));
                break;
            case 'rating':
                allCourses.sort((a, b) => (b.rating || 0) - (a.rating || 0));
                break;
            case 'price-low':
                allCourses.sort((a, b) => (a.price || 0) - (b.price || 0));
                break;
            case 'price-high':
                allCourses.sort((a, b) => (b.price || 0) - (a.price || 0));
                break;
            case 'newest':
                allCourses.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
                break;
        }
    }

    // --- 4. Render Featured Course ---
    function renderFeaturedCourse(course) {
        if (!featuredContainer) return;

        const studentCount = course.student_count || Math.floor(Math.random() * 2000) + 500;
        const rating = course.rating || 4.8;

        featuredContainer.innerHTML = `
            <div class="pg-glass-card pg-grid-2" style="padding: 0; overflow: hidden; background: linear-gradient(135deg, rgba(99,102,241,0.1), rgba(168,85,247,0.1));">
                <div class="pg-p-8 pg-flex pg-flex-col pg-justify-center">
                    <div>
                        <span class="pg-badge pg-badge-glass pg-mb-4">
                            <i class="fas fa-fire pg-mr-1" style="color:#ff9800;"></i> Trending Now
                        </span>
                        <h3 class="pg-h2 pg-mb-4">${course.title}</h3>
                        <p class="pg-lead pg-mb-6">${course.description || 'Master the skills that matter. Learn from industry experts.'}</p>

                        <div class="pg-flex pg-items-center pg-gap-3 pg-mb-6">
                            <img src="${course.mentor_avatar || 'https://ui-avatars.com/api/?name=' + encodeURIComponent(course.mentor_name || 'Instructor') + '&background=6366f1&color=fff'}" 
                                 style="width: 48px; height: 48px; border-radius: 50%; border: 2px solid var(--pg-glass-border);">
                            <div>
                                <div style="font-weight: 700; color: var(--pg-ink);">${course.mentor_name || 'Expert Instructor'}</div>
                                <div class="pg-small">Course Instructor</div>
                            </div>
                        </div>

                        <div class="pg-flex pg-items-center pg-gap-6 pg-small pg-mb-8">
                            <div class="pg-flex pg-items-center pg-gap-1">
                                <i class="fas fa-star" style="color: #ffc107;"></i>
                                <span style="font-weight: 700; color: var(--pg-ink);">${rating}</span>
                                <span>(${Math.floor(studentCount / 10)} reviews)</span>
                            </div>
                            <div class="pg-flex pg-items-center pg-gap-1">
                                <i class="fas fa-users"></i>
                                <span>${studentCount.toLocaleString()} enrolled</span>
                            </div>
                        </div>

                        <div class="pg-flex pg-items-center pg-gap-4">
                            <a href="/course-details?id=${course.id}" class="pg-btn pg-btn-primary">
                                View Course
                            </a>
                            <div class="pg-h3">${course.price ? '$' + course.price : 'Free'}</div>
                        </div>
                    </div>
                </div>
                <div class="pg-p-8 pg-flex pg-items-center pg-justify-center" style="position: relative;">
                    <div style="width: 100%; aspect-ratio: 16/9; border-radius: 16px; overflow: hidden; position: relative; box-shadow: var(--pg-sh-xl); cursor: pointer;"
                         onclick="window.location.href='/course-details?id=${course.id}'">
                        <img src="${course.thumbnail_url || 'https://images.unsplash.com/photo-1555066931-4365d14bab8c?auto=format&fit=crop&w=800'}" style="width: 100%; height: 100%; object-fit: cover;">
                        <div class="pg-flex pg-items-center pg-justify-center" style="position: absolute; inset: 0; background: rgba(0,0,0,0.3);">
                            <div class="pg-icon-box" style="background: white; color: var(--pg-primary);">
                                <i class="fas fa-play"></i>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    // --- 5. Render Courses ---
    function renderCourses(courses) {
        if (!courseContainer) return;

        const html = courses.map(course =>
            currentView === 'grid' ? renderCourseCardGrid(course) : renderCourseCardList(course)
        ).join('');

        courseContainer.innerHTML = html;
    }

    // --- 6. Course Card Templates ---
    function renderCourseCardGrid(course) {
        const isWishlisted = wishlist.includes(course.id);
        const rating = course.rating || 4.7;
        const studentCount = course.student_count || Math.floor(Math.random() * 1000) + 100;
        const price = course.price || 0;
        const isFree = price === 0;

        return `
            <div class="pg-glass-card pg-course-card">
                <div class="pg-course-img" onclick="window.location.href='/course-details?id=${course.id}'">
                    <img src="${course.thumbnail_url || 'https://images.unsplash.com/photo-1555066931-4365d14bab8c?auto=format&fit=crop&w=800'}">
                    <div class="pg-course-play"><i class="fas fa-play"></i></div>
                    ${isFree ? '<span class="pg-badge pg-badge-glass" style="position:absolute; top:12px; left:12px; background:var(--pg-emerald); color:white; border-color:var(--pg-emerald);">FREE</span>' : ''}
                </div>
                <div class="pg-course-body">
                    <div class="pg-flex pg-justify-between pg-items-center pg-mb-2">
                        <span class="pg-badge pg-badge-glass">${course.category || 'General'}</span>
                        <button onclick="toggleWishlist(${course.id})" style="background:none; border:none; cursor:pointer; color: ${isWishlisted ? 'var(--pg-rose)' : 'var(--pg-ink-m)'};">
                            <i class="${isWishlisted ? 'fas' : 'far'} fa-heart"></i>
                        </button>
                    </div>
                    <h3 class="pg-course-title" onclick="window.location.href='/course-details?id=${course.id}'">${course.title}</h3>
                    <p class="pg-course-desc">${course.description || 'Comprehensive course to master this topic.'}</p>
                    
                    <div class="pg-course-instructor">
                        <img src="${course.mentor_avatar || 'https://ui-avatars.com/api/?name=' + encodeURIComponent(course.mentor_name || 'Instructor') + '&background=random&color=fff'}">
                        <span>${course.mentor_name || 'Expert Instructor'}</span>
                    </div>

                    <div class="pg-course-meta">
                        <div><i class="fas fa-star" style="color:#ffc107;"></i> <strong style="color:var(--pg-ink);">${rating}</strong> (${Math.floor(studentCount / 10)})</div>
                        <div><i class="fas fa-users"></i> ${studentCount.toLocaleString()}</div>
                    </div>

                    <div class="pg-course-footer">
                        <div class="pg-course-price">${isFree ? '<span style="color:var(--pg-emerald);">Free</span>' : '$' + price}</div>
                        <a href="/course-details?id=${course.id}" style="color:var(--pg-primary); font-weight:700; font-size:14px; text-decoration:none;">View Course</a>
                    </div>
                </div>
            </div>
        `;
    }

    function renderCourseCardList(course) {
        const isWishlisted = wishlist.includes(course.id);
        const rating = course.rating || 4.7;
        const studentCount = course.student_count || Math.floor(Math.random() * 1000) + 100;
        const price = course.price || 0;
        const isFree = price === 0;

        return `
            <div class="pg-glass-card pg-flex pg-gap-6 pg-items-center pg-p-6" style="grid-column: 1 / -1; flex-direction: row; flex-wrap: wrap;">
                <div class="pg-course-img" style="width: 240px; height: 160px; flex-shrink: 0;" onclick="window.location.href='/course-details?id=${course.id}'">
                    <img src="${course.thumbnail_url || 'https://images.unsplash.com/photo-1555066931-4365d14bab8c?auto=format&fit=crop&w=800'}">
                    <div class="pg-course-play"><i class="fas fa-play"></i></div>
                </div>
                
                <div class="pg-flex-1" style="min-width: 250px;">
                    <div class="pg-flex pg-justify-between pg-items-start pg-mb-2">
                        <span class="pg-badge pg-badge-glass">${course.category || 'General'}</span>
                        <button onclick="toggleWishlist(${course.id})" style="background:none; border:none; cursor:pointer; color: ${isWishlisted ? 'var(--pg-rose)' : 'var(--pg-ink-m)'};">
                            <i class="${isWishlisted ? 'fas' : 'far'} fa-heart"></i>
                        </button>
                    </div>
                    <h3 class="pg-h3 pg-mb-2" style="cursor:pointer;" onclick="window.location.href='/course-details?id=${course.id}'">${course.title}</h3>
                    <p class="pg-course-desc pg-mb-4">${course.description || 'Comprehensive course to master this topic.'}</p>
                    
                    <div class="pg-flex pg-items-center pg-gap-6 pg-small">
                        <div class="pg-course-instructor" style="margin:0;">
                            <img src="${course.mentor_avatar || 'https://ui-avatars.com/api/?name=' + encodeURIComponent(course.mentor_name || 'Instructor') + '&background=random&color=fff'}">
                            <span>${course.mentor_name || 'Expert Instructor'}</span>
                        </div>
                        <div class="pg-flex pg-items-center pg-gap-1">
                            <i class="fas fa-star" style="color:#ffc107;"></i> <strong style="color:var(--pg-ink);">${rating}</strong> (${Math.floor(studentCount / 10)})
                        </div>
                        <div class="pg-flex pg-items-center pg-gap-1">
                            <i class="fas fa-users"></i> ${studentCount.toLocaleString()}
                        </div>
                    </div>
                </div>

                <div class="pg-flex pg-flex-col pg-items-end pg-gap-4 pg-ml-4">
                    <div class="pg-h3">${isFree ? '<span style="color:var(--pg-emerald);">Free</span>' : '$' + price}</div>
                    <a href="/course-details?id=${course.id}" class="pg-btn pg-btn-primary">Enroll Now</a>
                </div>
            </div>
        `;
    }

    // --- 7. Event Listeners ---

    // Search
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                loadCourses(currentCategoryId, e.target.value.trim());
            }, 600);
        });
    }

    // Sort
    if (sortSelect) {
        sortSelect.addEventListener('change', (e) => {
            currentSort = e.target.value;
            sortCourses();
            renderCourses(allCourses);
        });
    }

    // View Toggle
    if (viewToggleGrid) {
        viewToggleGrid.addEventListener('click', () => {
            currentView = 'grid';
            viewToggleGrid.classList.add('active');
            viewToggleList.classList.remove('active');
            renderCourses(allCourses);
        });
    }

    if (viewToggleList) {
        viewToggleList.addEventListener('click', () => {
            currentView = 'list';
            viewToggleList.classList.add('active');
            viewToggleGrid.classList.remove('active');
            renderCourses(allCourses);
        });
    }

    // Mobile Menu
    if (mobileMenuBtn) {
        mobileMenuBtn.addEventListener('click', () => {
            mobileMenu.classList.toggle('open');
        });
    }

    // Global Functions
    window.filterCourses = (catName) => {
        loadCourses(catName, currentSearchTerm);
    };

    window.toggleWishlist = (courseId) => {
        const index = wishlist.indexOf(courseId);
        if (index > -1) {
            wishlist.splice(index, 1);
        } else {
            wishlist.push(courseId);
        }
        localStorage.setItem('courseWishlist', JSON.stringify(wishlist));
        renderCourses(allCourses);
    };

    window.clearFilters = () => {
        currentCategoryId = null;
        currentSearchTerm = '';
        if (searchInput) searchInput.value = '';
        loadCourses();
    };

    // Init
    loadCourses();
});
