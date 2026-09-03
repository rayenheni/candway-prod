class LinkedInIntegration {
    constructor(options = {}) {
        this.apiBase = options.apiBase || (window.CONFIG ? CONFIG.API_BASE_URL : window.location.origin);
        this.connected = false;
        this.profile = null;
    }

    async checkStatus() {
        try {
            const res = await fetch(`${this.apiBase}/api/v1/linkedin/status`, {
                credentials: 'include',
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            if (!res.ok) throw new Error('Failed to check status');
            const data = await res.json();
            this.connected = data.connected;
            this.profile = data.profile;
            return data;
        } catch (e) {
            console.error('LinkedIn status check failed:', e);
            return { connected: false, profile: null };
        }
    }

    async connect() {
        try {
            const res = await fetch(`${this.apiBase}/api/v1/linkedin/auth-url`, {
                credentials: 'include',
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            if (!res.ok) throw new Error('Failed to get auth URL');
            const data = await res.json();

            const width = 600;
            const height = 700;
            const left = (screen.width / 2) - (width / 2);
            const top = (screen.height / 2) - (height / 2);

            const popup = window.open(
                data.auth_url,
                'linkedin-oauth',
                `width=${width},height=${height},left=${left},top=${top},toolbar=no,menubar=no,scrollbars=yes`
            );

            return new Promise((resolve, reject) => {
                const checkClosed = setInterval(async () => {
                    if (!popup || popup.closed) {
                        clearInterval(checkClosed);
                        const status = await this.checkStatus();
                        if (status.connected) {
                            resolve(status);
                        } else {
                            reject(new Error('Connection was not completed'));
                        }
                        return;
                    }

                    try {
                        if (popup.location.href && popup.location.href.includes('linkedin=connected')) {
                            popup.close();
                            clearInterval(checkClosed);
                            const status = await this.checkStatus();
                            resolve(status);
                            return;
                        }
                    } catch (e) {
                        // Cross-origin - expected, keep polling
                    }
                }, 500);

                setTimeout(() => {
                    clearInterval(checkClosed);
                    reject(new Error('Connection timeout'));
                }, 120000);
            });
        } catch (e) {
            console.error('LinkedIn connect error:', e);
            throw e;
        }
    }

    async disconnect() {
        try {
            const res = await fetch(`${this.apiBase}/api/v1/linkedin/disconnect`, {
                method: 'POST',
                credentials: 'include',
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            if (!res.ok) throw new Error('Failed to disconnect');
            this.connected = false;
            this.profile = null;
            return true;
        } catch (e) {
            console.error('LinkedIn disconnect error:', e);
            throw e;
        }
    }

    async postJob(jobId, companyUrn = '', posterUrn = '') {
        try {
            const res = await fetch(`${this.apiBase}/api/v1/linkedin/post-job/${jobId}`, {
                method: 'POST',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ company_urn: companyUrn, poster_urn: posterUrn })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Failed to post job');
            return data;
        } catch (e) {
            console.error('LinkedIn post job error:', e);
            throw e;
        }
    }

    async importProfile(profileUrl) {
        try {
            const res = await fetch(`${this.apiBase}/api/v1/linkedin/import-profile`, {
                method: 'POST',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ profile_url: profileUrl })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Failed to import profile');
            return data;
        } catch (e) {
            console.error('LinkedIn import profile error:', e);
            throw e;
        }
    }

    renderConnectButton(container) {
        if (this.connected) {
            container.innerHTML = `
                <div class="flex items-center justify-between p-4 bg-green-50 rounded-2xl border border-green-200">
                    <div class="flex items-center gap-3">
                        <div class="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center">
                            <i class="fab fa-linkedin text-green-600 text-lg"></i>
                        </div>
                        <div>
                            <p class="font-bold text-green-800 text-sm">Connected</p>
                            <p class="text-xs text-green-600">${this.profile ? this.profile.name || 'LinkedIn User' : ''}</p>
                        </div>
                    </div>
                    <button onclick="liIntegration.disconnect()" class="px-4 py-2 text-xs font-bold text-red-600 bg-red-50 rounded-xl hover:bg-red-100 transition">
                        Disconnect
                    </button>
                </div>
            `;
        } else {
            container.innerHTML = `
                <div class="flex items-center justify-between p-4 bg-slate-50 rounded-2xl border border-slate-200">
                    <div class="flex items-center gap-3">
                        <div class="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
                            <i class="fab fa-linkedin text-blue-600 text-lg"></i>
                        </div>
                        <div>
                            <p class="font-bold text-slate-800 text-sm">LinkedIn</p>
                            <p class="text-xs text-slate-500">Connect to post jobs and import profiles</p>
                        </div>
                    </div>
                    <button onclick="liIntegration.connect()" class="px-4 py-2 text-xs font-bold text-white bg-blue-600 rounded-xl hover:bg-blue-700 transition">
                        Connect
                    </button>
                </div>
            `;
        }
    }
}

window.LinkedInIntegration = LinkedInIntegration;
