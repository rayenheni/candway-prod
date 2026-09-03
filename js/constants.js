/**
 * Application Constants for Candway Platform
 * Centralizes magic numbers and configuration values
 */

window.AppConstants = {
    // API Configuration
    API: {
        TIMEOUT: 30000,              // 30 seconds
        RETRY_ATTEMPTS: 2,           // Number of retries
        RETRY_DELAY: 1000,          // 1 second between retries
        RATE_LIMIT_WINDOW: 60000,   // 1 minute
        RATE_LIMIT_MAX_REQUESTS: 60 // 60 requests per minute
    },

    // Pricing & Plans
    PRICING: {
        CURRENCY: 'TND',
        PRO_PLAN_MONTHLY: 149,
        PRO_PLAN_YEARLY: 1490, // Example yearly
        BANK_INFO: {
            BANK_NAME: 'Konnect Wallet / Bank Transfer',
            RIB: '123-456-7890-00',
            ACCOUNT_NAME: 'Candway Inc'
        }
    },

    // Performance
    PERFORMANCE: {
        DEBOUNCE_DELAY: 300,        // 300ms for search inputs
        THROTTLE_DELAY: 100,        // 100ms for scroll handlers
        MAX_CHAT_HISTORY: 20,       // Prevent memory leak
        MAX_SEARCH_RESULTS: 1000,   // Limit result set size
        VIRTUAL_SCROLL_BUFFER: 5    // Extra items to render
    },

    // File Upload
    FILE_UPLOAD: {
        MAX_SIZE: 10 * 1024 * 1024,  // 10MB
        ALLOWED_TYPES: ['image/jpeg', 'image/png', 'image/gif', 'application/pdf'],
        ALLOWED_EXTENSIONS: ['.jpg', '.jpeg', '.png', '.gif', '.pdf']
    },

    // Pagination
    PAGINATION: {
        DEFAULT_PAGE_SIZE: 20,
        MAX_PAGE_SIZE: 100,
        SHOW_PAGINATION_THRESHOLD: 10
    },

    // UI
    UI: {
        TOAST_DURATION: 3000,        // 3 seconds
        MODAL_ANIMATION_DURATION: 300, // 300ms
        SIDEBAR_TRANSITION: 400,     // 400ms
        LOADING_MIN_DISPLAY: 500     // Minimum loading spinner time
    },

    // Scoring
    SCORING: {
        MIN_SCORE: 0,
        MAX_SCORE: 100,
        PASS_THRESHOLD: 60,
        EXCELLENT_THRESHOLD: 80
    },

    // Navigation Map
    NAV_MAP: {
        'recruiter.html': 'nav-dashboard',
        'recruiter-search.html': 'nav-search',
        'recruiter-pipeline.html': 'nav-pipeline',
        'recruiter-jobs.html': 'nav-jobs',
        'recruiter-settings.html': 'nav-settings',
        'recruiter-analytics.html': 'nav-analytics',
        'recruiter-billing.html': 'nav-billing',
        'recruiter-bulk-invite.html': 'nav-campaigns'
    },

    // Status Colors
    STATUS_COLORS: {
        'applied': 'bg-blue-100 text-blue-700',
        'invited': 'bg-purple-100 text-purple-700',
        'interviewing': 'bg-yellow-100 text-yellow-700',
        'hired': 'bg-emerald-100 text-emerald-700',
        'rejected': 'bg-red-100 text-red-700',
        'archived': 'bg-slate-100 text-slate-700'
    },

    // Score Colors
    SCORE_COLORS: {
        excellent: 'text-emerald-600',  // >= 80
        good: 'text-blue-600',          // >= 60
        average: 'text-amber-600',      // >= 40
        poor: 'text-slate-400'          // < 40
    },

    // Validation Patterns
    PATTERNS: {
        EMAIL: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
        PHONE: /^\+?[\d\s\-()]+$/,
        URL: /^https?:\/\/.+/,
        LINKEDIN: /^https?:\/\/(www\.)?linkedin\.com\/.+/
    },

    // Error Messages
    ERRORS: {
        NETWORK: 'Network error. Please check your internet connection.',
        TIMEOUT: 'Request timed out. Please try again.',
        UNAUTHORIZED: 'Session expired. Please log in again.',
        FORBIDDEN: 'You do not have permission to perform this action.',
        NOT_FOUND: 'The requested resource was not found.',
        SERVER_ERROR: 'Server error. Please try again later.',
        VALIDATION: 'Please check your input and try again.',
        FILE_TOO_LARGE: 'File size exceeds the maximum allowed size.',
        INVALID_FILE_TYPE: 'Invalid file type. Please upload a supported file.'
    },

    // Success Messages
    SUCCESS: {
        SAVED: 'Changes saved successfully!',
        DELETED: 'Deleted successfully!',
        INVITED: 'Invitation sent successfully!',
        UPDATED: 'Updated successfully!',
        UPLOADED: 'File uploaded successfully!'
    }
};

// Helper function to get score color
window.getScoreColor = function (score) {
    if (score >= AppConstants.SCORING.EXCELLENT_THRESHOLD) return AppConstants.SCORE_COLORS.excellent;
    if (score >= AppConstants.SCORING.PASS_THRESHOLD) return AppConstants.SCORE_COLORS.good;
    if (score >= 40) return AppConstants.SCORE_COLORS.average;
    return AppConstants.SCORE_COLORS.poor;
};

// Helper function to get status color
window.getStatusColor = function (status) {
    return AppConstants.STATUS_COLORS[status] || 'bg-slate-100 text-slate-700';
};

_log('✅ Application constants loaded');
