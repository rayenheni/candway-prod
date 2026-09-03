/**
 * Candway Real-time Notification System
 * WebSocket client with HTTP polling fallback
 */

// Helper for debug logging
const NOTIF_DEBUG = (typeof CONFIG !== 'undefined' && CONFIG.DEBUG) || false;

class CandwayNotifications {
    constructor() {
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 8;
        this.reconnectDelay = 3000; // base delay, overridden by exponential backoff
        this.userId = null;
        this.listeners = new Map();
        this.isConnected = false;
        this.pollInterval = null;
        this.pollDelay = 30000; // 30 seconds fallback polling
    }

    /**
     * Initialize WebSocket connection
     * @param {number} userId - Current user ID
     */
    async init(userId) {
        if (!userId) {
            // Check for guest session
            const isGuest = localStorage.getItem('is_guest') === 'true';
            const appId = localStorage.getItem('active_app_id');
            if (isGuest && appId) {
                if (NOTIF_DEBUG) console.log('Initializing guest notifications for AppID:', appId);
                this.userId = appId;
                this.connect();
                return;
            }
            console.warn('Cannot initialize notifications: No user ID or guest AppID');
            return;
        }

        this.userId = userId;
        this.connect();
    }

    /**
     * Establish WebSocket connection
     */
    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.hostname;
        // WebSocket is on the same server as the HTTP server. Use the page's port.
        // Remove any stale ws_port that might point to a different port.
        if (localStorage.getItem('ws_port')) {
            localStorage.removeItem('ws_port');
        }
        const port = window.location.port || '8000';
        const wsUrl = `${protocol}//${host}:${port}/ws/${this.userId}`;

        if (NOTIF_DEBUG) console.log('[WS] Connecting');

        try {
            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = () => {
                if (NOTIF_DEBUG) console.log('✅ WebSocket connected');
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.showConnectionStatus('connected');
                // Start polling as backup
                this.startPolling();
            };

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    // Skip empty or invalid messages
                    if (!data || (data.type === 'ping')) return;
                    this.handleMessage(data);
                } catch (error) {
                    console.error('Failed to parse WebSocket message:', error);
                }
            };

            this.ws.onerror = (error) => {
                console.error('❌ WebSocket error:', error);
                this.isConnected = false;
            };

            this.ws.onclose = () => {
                if (NOTIF_DEBUG) console.log('🔌 WebSocket disconnected');
                this.isConnected = false;
                this.showConnectionStatus('disconnected');
                this.attemptReconnect();
            };
        } catch (error) {
            console.error('Failed to create WebSocket:', error);
            // Fallback to polling immediately
            this.startPolling();
        }
    }

    /**
     * Start HTTP polling fallback
     */
    startPolling() {
        if (this.pollInterval) return; // Already polling

        if (NOTIF_DEBUG) console.log('📡 Starting polling fallback for notifications');

        this.pollInterval = setInterval(async () => {
            try {
                const notifications = await window.fetchAPI('/notifications/latest?limit=5');
                if (Array.isArray(notifications) && notifications.length > 0) {
                    notifications.forEach(n => {
                        // Skip empty notifications
                        if (n && (n.message || n.title || n.content)) {
                            this.handleMessage({ type: 'polled_notification', payload: n });
                        }
                    });
                }
            } catch (e) {
                // Silently fail polling
            }
        }, this.pollDelay);
    }

    /**
     * Stop polling
     */
    stopPolling() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
    }

    /**
     * Handle incoming WebSocket messages
     * @param {Object} data - Message data
     */
    handleMessage(data) {
        const { type, payload } = data;

        // Skip empty or invalid messages
        if (!data || (!type && !payload)) {
            if (NOTIF_DEBUG) console.log('Skipping empty/invalid message');
            return;
        }

        if (NOTIF_DEBUG) console.log('📨 Received notification:', type, payload);

        // Trigger registered listeners (pass payload if it exists, otherwise pass the full data)
        if (this.listeners.has(type)) {
            const callbacks = this.listeners.get(type);
            const listenerData = payload !== undefined ? payload : data;
            callbacks.forEach(callback => callback(listenerData));
        }

        // Default handlers
        switch (type) {
            case 'new_application':
                this.showNotification(
                    'New Application',
                    `${payload.candidate_name} applied for ${payload.job_title}`,
                    'info',
                    () => window.location.href = `/recruiter/candidate?id=${payload.application_id}`
                );
                break;

            case 'interview_scheduled':
                this.showNotification(
                    'Interview Scheduled',
                    `Interview scheduled for ${payload.candidate_name} on ${payload.date}`,
                    'success'
                );
                break;

            case 'offer_accepted':
                this.showNotification(
                    'Offer Accepted! 🎉',
                    `${payload.candidate_name} accepted your offer`,
                    'success'
                );
                break;

            case 'offer_rejected':
                this.showNotification(
                    'Offer Declined',
                    `${payload.candidate_name} declined the offer`,
                    'warning'
                );
                break;

            case 'comment_mention':
                this.showNotification(
                    'You were mentioned',
                    `${payload.author} mentioned you in a comment`,
                    'info',
                    () => window.location.href = `/recruiter/candidate?id=${payload.application_id}`
                );
                break;

            case 'interview_reminder':
                this.showNotification(
                    'Interview Reminder',
                    `Interview with ${payload.candidate_name} in ${payload.time_until}`,
                    'warning'
                );
                break;

            case 'application_status_changed':
                this.showNotification(
                    'Application Update',
                    `Your application status changed to: ${payload.new_status}`,
                    'info',
                    () => window.location.href = '/candidate/applications'
                );
                // Dispatch custom event for page-specific handlers to auto-refresh
                window.dispatchEvent(new CustomEvent('candidate-application-status-changed', {
                    detail: {
                        applicationId: payload.application_id,
                        oldStatus: payload.old_status,
                        newStatus: payload.new_status,
                        jobTitle: payload.job_title,
                        timestamp: payload.timestamp
                    }
                }));
                break;

            case 'new_message':
                if (data && data.message) {
                    const senderName = data.message.sender_name || 'Someone';
                    const preview = (data.message.content || '').substring(0, 100);
                    this.showNotification(
                        'New Message',
                        `${senderName}: ${preview}`,
                        'info',
                        () => {
                            const role = localStorage.getItem('role') || 'candidate';
                            window.location.href = role === 'recruiter' ? '/recruiter/messages' : '/candidate/messages';
                        }
                    );
                }
                break;

            case 'new_conversation':
                this.showNotification(
                    'New Conversation',
                    'Someone started a conversation with you',
                    'info',
                    () => {
                        const role = localStorage.getItem('role') || 'candidate';
                        window.location.href = role === 'recruiter' ? '/recruiter/messages' : '/candidate/messages';
                    }
                );
                break;

            default:
                if (NOTIF_DEBUG) console.log('Unhandled notification type:', type);
        }

        // Invalidate frontend cache for mutation events received via WebSocket
        if (typeof _invalidateForMutation === 'function') {
            switch (type) {
                case 'application_status_changed':
                    _invalidateForMutation('/recruiter/applications');
                    break;
                case 'new_application':
                    _invalidateForMutation('/recruiter/candidates');
                    break;
                case 'interview_scheduled':
                    _invalidateForMutation('/recruiter/interviews');
                    break;
                case 'offer_accepted':
                case 'offer_rejected':
                    _invalidateForMutation('/recruiter/offers');
                    break;
                case 'new_message':
                    _invalidateForMutation('/messages');
                    break;
                case 'comment_mention':
                    _invalidateForMutation('/recruiter/collaboration');
                    break;
            }
        }
    }

    /**
     * Show toast notification
     * @param {string} title - Notification title
     * @param {string} message - Notification message
     * @param {string} type - Notification type (success, error, warning, info)
     * @param {Function} onClick - Click handler
     */
    showNotification(title, message, type = 'info', onClick = null) {
        // Skip empty notifications
        if (!title || !message || (typeof title === 'string' && !title.trim()) || (typeof message === 'string' && !message.trim())) {
            if (NOTIF_DEBUG) console.log('Skipping empty notification');
            return;
        }

        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification-toast notification-${type}`;

        const icons = {
            success: '✅',
            error: '❌',
            warning: '⚠️',
            info: 'ℹ️'
        };

        notification.innerHTML = `
            <div class="notification-content">
                <div class="notification-icon">${icons[type] || icons.info}</div>
                <div class="notification-text">
                    <div class="notification-title">${title}</div>
                    <div class="notification-message">${message}</div>
                </div>
                <button class="notification-close" onclick="this.parentElement.parentElement.remove()">×</button>
            </div>
        `;

        // Add click handler
        if (onClick) {
            notification.style.cursor = 'pointer';
            notification.addEventListener('click', (e) => {
                if (!e.target.classList.contains('notification-close')) {
                    onClick();
                    notification.remove();
                }
            });
        }

        // Add to DOM
        let container = document.getElementById('notification-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'notification-container';
            document.body.appendChild(container);
        }
        container.appendChild(notification);

        // Auto-remove after 5 seconds
        setTimeout(() => {
            notification.classList.add('notification-fade-out');
            setTimeout(() => notification.remove(), 300);
        }, 5000);

        // Play sound (optional)
        this.playNotificationSound();
    }

    /**
     * Play notification sound
     */
    playNotificationSound() {
        // Only play if user has interacted with page (browser restriction)
        if (document.visibilityState === 'visible') {
            const audio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBSuBzvLZiTYIGGS57OihUBELTKXh8LRiHAU2jdXyzn0vBSh+zPDajkALFF+16+qnVRQLRp/g8r5sIQYrgc7y2Ik2CBhkuezooVARC0yl4fC0YhwFNo3V8s59LwUofsz');
            audio.volume = 0.3;
            audio.play().catch(() => { }); // Ignore errors
        }
    }

    /**
     * Show connection status indicator
     * @param {string} status - 'connected' or 'disconnected'
     */
    showConnectionStatus(status) {
        let indicator = document.getElementById('ws-status-indicator');
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.id = 'ws-status-indicator';
            document.body.appendChild(indicator);
        }

        indicator.className = `ws-status ws-status-${status}`;
        indicator.innerHTML = status === 'connected'
            ? '<span class="ws-status-dot"></span> Live'
            : '<span class="ws-status-dot"></span> Reconnecting...';

        // Hide after 3 seconds if connected
        if (status === 'connected') {
            setTimeout(() => {
                indicator.classList.add('ws-status-hidden');
            }, 3000);
        }
    }

    /**
     * Attempt to reconnect with exponential backoff
     * Delays: 1s, 2s, 4s, 8s, 16s, 30s (capped)
     */
    attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.warn('Max reconnection attempts reached, falling back to polling');
            this.startPolling();
            return;
        }

        // Exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s (capped at 30s)
        const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
        console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts + 1}/${this.maxReconnectAttempts})`);

        setTimeout(() => {
            this.reconnectAttempts++;
            this.connect();
        }, delay);
    }

    /**
     * Register event listener
     * @param {string} eventType - Event type to listen for
     * @param {Function} callback - Callback function
     */
    on(eventType, callback) {
        if (!this.listeners.has(eventType)) {
            this.listeners.set(eventType, []);
        }
        this.listeners.get(eventType).push(callback);
    }

    /**
     * Unregister event listener
     * @param {string} eventType - Event type
     * @param {Function} callback - Callback to remove
     */
    off(eventType, callback) {
        if (this.listeners.has(eventType)) {
            const callbacks = this.listeners.get(eventType);
            const index = callbacks.indexOf(callback);
            if (index > -1) {
                callbacks.splice(index, 1);
            }
        }
    }

    /**
     * Send message to server
     * @param {Object} data - Data to send
     */
    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        } else {
            console.warn('WebSocket not connected, cannot send message');
        }
    }

    /**
     * Close connection
     */
    disconnect() {
        this.stopPolling();
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }
}

// Global instance
window.CandwayNotifications = new CandwayNotifications();

// Auto-initialize when user is logged in or guest session is active
document.addEventListener('DOMContentLoaded', async () => {
    try {
        const token = localStorage.getItem('token');
        if (token) {
            const isGuest = localStorage.getItem('is_guest') === 'true';
            const appId = localStorage.getItem('active_app_id');

            if (isGuest && appId) {
                // Guest mode: Initialize with appId
                window.CandwayNotifications.init();
            } else {
                // Authenticated mode: Get current user using fetchAPI
                try {
                    const user = await getAuthMe();
                    if (user && user.id) {
                        window.CandwayNotifications.init(user.id);
                    }
                } catch (e) {
                    console.warn('Failed to get user for notifications:', e);
                    // Fallback for guests if me fails but we have app context
                    if (isGuest && appId) {
                        window.CandwayNotifications.init();
                    }
                }
            }
        }
    } catch (error) {
        console.error('Failed to initialize notifications:', error);
    }
});

// Add CSS styles
const style = document.createElement('style');
style.textContent = `
    #notification-container {
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 999999;
        max-width: 400px;
    }

    .notification-toast {
        background: white;
        border-radius: 12px;
        box-shadow: 0 10px 40px rgba(0,0,0,0.15);
        margin-bottom: 12px;
        animation: slideIn 0.3s ease-out;
        border-left: 4px solid;
    }

    .notification-success { border-left-color: #10b981; }
    .notification-error { border-left-color: #ef4444; }
    .notification-warning { border-left-color: #f59e0b; }
    .notification-info { border-left-color: #3b82f6; }

    .notification-content {
        display: flex;
        align-items: flex-start;
        padding: 16px;
        gap: 12px;
    }

    .notification-icon {
        font-size: 24px;
        flex-shrink: 0;
    }

    .notification-text {
        flex: 1;
        min-width: 0;
    }

    .notification-title {
        font-weight: 700;
        font-size: 14px;
        color: #1f2937;
        margin-bottom: 4px;
    }

    .notification-message {
        font-size: 13px;
        color: #6b7280;
        line-height: 1.4;
    }

    .notification-close {
        background: none;
        border: none;
        font-size: 24px;
        color: #9ca3af;
        cursor: pointer;
        padding: 0;
        width: 24px;
        height: 24px;
        flex-shrink: 0;
        transition: color 0.2s;
    }

    .notification-close:hover {
        color: #1f2937;
    }

    .notification-fade-out {
        animation: slideOut 0.3s ease-out forwards;
    }

    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }

    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }

    #ws-status-indicator {
        position: fixed;
        bottom: 20px;
        right: 20px;
        background: white;
        padding: 8px 16px;
        border-radius: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        font-size: 12px;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 8px;
        z-index: 999998;
        transition: opacity 0.3s, transform 0.3s;
    }

    .ws-status-hidden {
        opacity: 0;
        transform: translateY(10px);
        pointer-events: none;
    }

    .ws-status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
    }

    .ws-status-connected .ws-status-dot {
        background: #10b981;
        animation: pulse 2s infinite;
    }

    .ws-status-disconnected .ws-status-dot {
        background: #ef4444;
    }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }

    [data-theme='dark'] .notification-toast {
        background: #1f2937;
    }

    [data-theme='dark'] .notification-title {
        color: #f9fafb;
    }

    [data-theme='dark'] .notification-message {
        color: #d1d5db;
    }

    [data-theme='dark'] #ws-status-indicator {
        background: #1f2937;
        color: #f9fafb;
    }
`;
document.head.appendChild(style);
