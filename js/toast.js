const Toast = {
    show: (message, type = 'info') => {
        const container = document.getElementById('toast-container') || createContainer();

        const toast = document.createElement('div');
        toast.className = `flex items-center w-full max-w-xs p-4 mb-4 rounded-lg shadow-2xl border-l-4 ${getTypeClass(type)} animate-fade-in-down`;
        toast.style.cssText = "background: white !important; color: #0f172a !important; font-weight: 600; box-shadow: 0 10px 25px rgba(0,0,0,0.15) !important;";

        const iconDiv = document.createElement('div');
        iconDiv.className = `inline-flex items-center justify-center flex-shrink-0 w-8 h-8 ${getIconBg(type)} rounded-lg`;
        XSS.safeSetHTML(iconDiv, `<i class="fas ${getIcon(type)}"></i>`);

        const msgDiv = document.createElement('div');
        msgDiv.className = 'ml-3 text-sm font-semibold';
        msgDiv.style.color = '#1e293b';
        msgDiv.textContent = message;

        const closeBtn = document.createElement('button');
        closeBtn.type = 'button';
        closeBtn.className = 'ml-auto -mx-1.5 -my-1.5 bg-gray-100 text-gray-500 hover:text-gray-900 rounded-lg focus:ring-2 focus:ring-gray-300 p-1.5 hover:bg-gray-200 inline-flex h-8 w-8 transition-colors';
        closeBtn.innerHTML = '<i class="fas fa-times"></i>';
        closeBtn.onclick = () => toast.remove();

        toast.appendChild(iconDiv);
        toast.appendChild(msgDiv);
        toast.appendChild(closeBtn);

        container.appendChild(toast);

        // Auto remove
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
};

window.showToast = function (message, type = 'info') {
    Toast.show(message, type);
};

function createContainer() {
    const div = document.createElement('div');
    div.id = 'toast-container';
    div.className = 'fixed top-5 right-5 z-[10000] pointer-events-none';
    div.innerHTML = '<style>.pointer-events-none > * { pointer-events: auto; } @keyframes fade-in-down { from { opacity: 0; transform: translateY(-20px); } to { opacity: 1; transform: translateY(0); } }</style>';
    document.body.appendChild(div);
    return div;
}

function getTypeClass(type) {
    switch (type) {
        case 'success': return 'border-green-500';
        case 'error': return 'border-red-500';
        case 'warning': return 'border-yellow-500';
        default: return 'border-blue-500';
    }
}

function getIconBg(type) {
    switch (type) {
        case 'success': return 'text-green-600 bg-green-100';
        case 'error': return 'text-red-600 bg-red-100';
        case 'warning': return 'text-yellow-600 bg-yellow-100';
        default: return 'text-blue-600 bg-blue-100';
    }
}

function getIcon(type) {
    switch (type) {
        case 'success': return 'fa-check';
        case 'error': return 'fa-exclamation-circle';
        case 'warning': return 'fa-exclamation-triangle';
        default: return 'fa-info-circle';
    }
}

// Check for toast in URL params (e.g. from redirects)
document.addEventListener('DOMContentLoaded', () => {
    const urlParams = new URLSearchParams(window.location.search);
    const msg = urlParams.get('msg');
    const type = urlParams.get('type');
    if (msg) {
        Toast.show(msg, type || 'info');
        // Clean URL
        window.history.replaceState({}, document.title, window.location.pathname);
    }
});
