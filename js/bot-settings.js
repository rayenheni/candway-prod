const API_BASE_URL = CONFIG.API_BASE_URL;

const SlackBotUI = {
    popupWindows: {},

    init: async function() {
        await this.checkStatus();
    },

    checkStatus: async function() {
        try {
            const resp = await fetch(`${API_BASE_URL}/api/v1/bot/status`, {
                credentials: 'include'
            });
            const data = await resp.json();

            const slackBadge = document.getElementById('slack-status-badge');
            const slackConnect = document.getElementById('slack-connect-btn');
            const slackDisconnect = document.getElementById('slack-disconnect-btn');

            if (data.has_slack) {
                slackBadge.innerHTML = '<i class="fas fa-check-circle text-green-500 mr-1"></i> Connected';
                slackBadge.className = 'px-3 py-1.5 rounded-full text-xs font-bold bg-green-100 text-green-700';
                slackConnect.classList.add('hidden');
                slackDisconnect.classList.remove('hidden');
            } else {
                slackBadge.innerHTML = '<i class="fas fa-times-circle text-slate-400 mr-1"></i> Not connected';
                slackBadge.className = 'px-3 py-1.5 rounded-full text-xs font-bold bg-slate-100 text-slate-500';
                slackConnect.classList.remove('hidden');
                slackDisconnect.classList.add('hidden');
            }

            const teamsBadge = document.getElementById('teams-status-badge');
            const teamsConnect = document.getElementById('teams-connect-btn');
            const teamsDisconnect = document.getElementById('teams-disconnect-btn');

            if (data.has_teams) {
                teamsBadge.innerHTML = '<i class="fas fa-check-circle text-green-500 mr-1"></i> Connected';
                teamsBadge.className = 'px-3 py-1.5 rounded-full text-xs font-bold bg-green-100 text-green-700';
                teamsConnect.classList.add('hidden');
                teamsDisconnect.classList.remove('hidden');
            } else {
                teamsBadge.innerHTML = '<i class="fas fa-times-circle text-slate-400 mr-1"></i> Not connected';
                teamsBadge.className = 'px-3 py-1.5 rounded-full text-xs font-bold bg-slate-100 text-slate-500';
                teamsConnect.classList.remove('hidden');
                teamsDisconnect.classList.add('hidden');
            }

            try {
                const usageResp = await fetch(`${API_BASE_URL}/api/v1/bot/usage`, {
                    credentials: 'include'
                });
                const usage = await usageResp.json();
                document.getElementById('usage-slack').textContent = usage.platforms.filter(p => p === 'slack').length; // noqa: bot domain
                document.getElementById('usage-teams').textContent = usage.platforms.filter(p => p === 'teams').length; // noqa: bot domain
                document.getElementById('usage-total').textContent = usage.active_integrations;
            } catch(e) {}

        } catch (e) {
            console.error('Bot status check failed:', e);
        }
    },

    connectSlack: async function() {
        try {
            const resp = await fetch(`${API_BASE_URL}/api/v1/bot/slack/auth-url`, {
                credentials: 'include'
            });
            const data = await resp.json();

            if (data.url) {
                const w = 600, h = 700;
                const left = (screen.width / 2) - (w / 2);
                const top = (screen.height / 2) - (h / 2);
                this.popupWindows.slack = window.open(
                    data.url,
                    'slack-oauth',
                    `width=${w},height=${h},top=${top},left=${left}`
                );
                this._pollPopup('slack');
            }
        } catch (e) {
            Components.showToast('Failed to initiate Slack connection', 'error');
        }
    },

    connectTeams: async function() {
        try {
            const resp = await fetch(`${API_BASE_URL}/api/v1/bot/teams/auth-url`, {
                credentials: 'include'
            });
            const data = await resp.json();

            if (data.url) {
                const w = 600, h = 700;
                const left = (screen.width / 2) - (w / 2);
                const top = (screen.height / 2) - (h / 2);
                this.popupWindows.teams = window.open(
                    data.url,
                    'teams-oauth',
                    `width=${w},height=${h},top=${top},left=${left}`
                );
                this._pollPopup('teams');
            }
        } catch (e) {
            Components.showToast('Failed to initiate Teams connection', 'error');
        }
    },

    _pollPopup: function(platform) {
        const checkClosed = setInterval(() => {
            const popup = this.popupWindows[platform];
            if (!popup || popup.closed) {
                clearInterval(checkClosed);
                this.checkStatus();
            }
        }, 1000);

        setTimeout(() => {
            clearInterval(checkClosed);
        }, 120000);
    },

    disconnect: async function(platform) {
        if (!confirm(`Disconnect ${platform}? You can reconnect anytime.`)) return;

        const btn = document.getElementById(`${platform}-disconnect-btn`);
        const original = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Disconnecting...';
        btn.disabled = true;

        try {
            await fetch(`${API_BASE_URL}/api/v1/bot/disconnect`, {
                method: 'POST',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ platform: platform })
            });
            Components.showToast(`${platform} disconnected`, 'success');
            this.checkStatus();
        } catch (e) {
            Components.showToast(`Failed to disconnect ${platform}`, 'error');
        } finally {
            btn.innerHTML = original;
            btn.disabled = false;
        }
    },

    testNotification: async function() {
        const btn = document.getElementById('test-notification-btn');
        const original = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Sending...';
        btn.disabled = true;

        try {
            await fetch(`${API_BASE_URL}/api/v1/bot/test-notification`, {
                method: 'POST',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' }
            });
            Components.showToast('Test notification sent!', 'success');
        } catch (e) {
            Components.showToast('Failed to send test notification', 'error');
        } finally {
            btn.innerHTML = original;
            btn.disabled = false;
        }
    }
};
