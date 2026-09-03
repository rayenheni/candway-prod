document.addEventListener('DOMContentLoaded', () => {
    if (typeof Components !== 'undefined') {
        Components.init('nav_visitors');
    }
    initVisitors();
});

async function initVisitors() {
    const visitorsList = document.getElementById('visitors-list');
    if (!visitorsList) return;
    const emptyState = document.getElementById('empty-state');
    
    try {
        const visitors = await fetchAPI('/candidate/profile-visitors');
        
        if (visitors.length === 0) {
            visitorsList.innerHTML = '';
            emptyState.classList.remove('hidden');
            return;
        }
        
        renderVisitors(visitors);
    } catch (error) {
        console.error('Error loading visitors:', error);
        showToast('Error loading visitors', 'error');
        visitorsList.innerHTML = `<div class="p-8 text-center text-red-400">Failed to load visitors. Please try again.</div>`;
    }
}

function renderVisitors(visitors) {
    const visitorsList = document.getElementById('visitors-list');
    visitorsList.innerHTML = '';
    
    visitors.forEach((visitor, index) => {
        const date = new Date(visitor.visited_at);
        const timeAgo = formatTimeAgo(date);
        
        const card = document.createElement('div');
        card.className = 'premium-glass p-6 rounded-2xl flex items-center justify-between visitor-card';
        card.setAttribute('data-aos', 'fade-up');
        card.setAttribute('data-aos-delay', index * 50);
        
        card.innerHTML = `
            <div class="flex items-center gap-6">
                <div class="relative">
                    <img src="${visitor.avatar || '/assets/default-avatar.png'}" 
                         class="w-16 h-16 rounded-full object-cover border-2 border-indigo-500/20" 
                         alt="${visitor.name}">
                    <div class="absolute -bottom-1 -right-1 w-6 h-6 rounded-full bg-emerald-500 border-4 border-slate-900 flex items-center justify-center text-[10px] text-white">
                        <i class="fas fa-check"></i>
                    </div>
                </div>
                <div>
                    <h3 class="text-xl font-bold mb-0.5">${visitor.name}</h3>
                    <p class="text-slate-500 dark:text-slate-400 font-medium flex items-center gap-2">
                        <i class="fas fa-building text-xs"></i> ${visitor.company || 'Private Recruiter'}
                    </p>
                </div>
            </div>
            <div class="text-right">
                <div class="text-sm font-bold text-indigo-400 mb-1">${timeAgo}</div>
                <div class="text-[10px] text-slate-500 uppercase tracking-widest font-black">Visited Profile</div>
            </div>
        `;
        
        visitorsList.appendChild(card);
    });
}

function formatTimeAgo(date) {
    const now = new Date();
    const diff = Math.floor((now - date) / 1000);
    
    if (diff < 60) return 'Just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
    
    return date.toLocaleDateString();
}
