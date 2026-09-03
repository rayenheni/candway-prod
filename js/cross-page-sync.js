/**
 * Cross-Page Stage Synchronization
 * Delegates to AppState.StageSync for BroadcastChannel + localStorage fallback.
 * Kept for backward compatibility — existing page scripts call StageSync.broadcast().
 */
(function() {
    'use strict';

    // Delegate to AppState.StageSync if available
    if (window.AppState && window.AppState.StageSync) {
        window.StageSync = window.AppState.StageSync;
        return;
    }

    // Fallback: minimal implementation if AppState hasn't loaded yet
    var listeners = [];
    var CHANNEL_NAME = 'candway-stage-sync';
    var STORAGE_KEY = 'candway_stage_change';
    var channel = null;

    function getWindowId() {
        if (!window._candwayWindowId) {
            window._candwayWindowId = 'win_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        }
        return window._candwayWindowId;
    }

    function getChannel() {
        if (channel) return channel;
        try {
            channel = new BroadcastChannel(CHANNEL_NAME);
            channel.onmessage = function(event) {
                if (event.data && event.data.sourceId !== getWindowId()) {
                    listeners.forEach(function(fn) {
                        try { fn(event.data); } catch (e) { console.warn('StageSync listener error:', e); }
                    });
                }
            };
        } catch (e) { channel = null; }
        return channel;
    }

    getChannel();

    window.addEventListener('storage', function(e) {
        if (e.key === STORAGE_KEY && e.newValue) {
            try {
                var data = JSON.parse(e.newValue);
                if (data.sourceId !== getWindowId()) {
                    listeners.forEach(function(fn) {
                        try { fn(data); } catch (e) { console.warn('StageSync listener error:', e); }
                    });
                }
            } catch (err) { /* ignore */ }
        }
    });

    window.StageSync = {
        broadcast: function(payload) {
            var data = {
                type: 'stage-changed',
                appId: payload.appId,
                oldStatus: payload.oldStatus,
                newStatus: payload.newStatus,
                timestamp: Date.now(),
                sourceId: getWindowId()
            };
            if (channel) {
                try { channel.postMessage(data); } catch (e) { /* ignore */ }
            }
            try {
                localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
                setTimeout(function() { localStorage.removeItem(STORAGE_KEY); }, 1000);
            } catch (e) { /* ignore */ }
            window.dispatchEvent(new CustomEvent('candidate-status-changed', {
                detail: { appId: payload.appId, oldStatus: payload.oldStatus, newStatus: payload.newStatus }
            }));
        },
        onChange: function(callback) {
            if (typeof callback === 'function') listeners.push(callback);
        },
        offChange: function(callback) {
            var idx = listeners.indexOf(callback);
            if (idx !== -1) listeners.splice(idx, 1);
        }
    };
})();
