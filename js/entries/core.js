// Core bundle entry point — imports in load order
// Source files are in ../ (same directory as the js/ folder)
import '../app-state.js';
import '../app-auth.js';
import '../config.js';
import '../csrf.js';
import '../constants.js';
import '../security.js';
import '../xss-protection.js';
import '../components.js';
import '../toast.js';
import '../error-boundary.js';
import '../translations.js';
import '../localization.js';
import '../performance.js';
import '../load-assets.js';
