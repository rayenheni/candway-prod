#!/usr/bin/env node
/**
 * JS Bundle Build Script for Candway Platform
 * =============================================
 * Uses esbuild to bundle JS files into role-specific bundles.
 *
 * Bundle structure:
 *   js/dist/core.js      — loaded on every page (AppState, AppAuth, config, security, UI)
 *   js/dist/shared.js    — shared features (feature-flags, notifications, GDPR)
 *   js/dist/candidate.js — candidate-specific features
 *   js/dist/recruiter.js — recruiter-specific features
 *   js/dist/admin.js     — admin-specific features
 *   js/dist/mentor.js    — mentor-specific features
 *
 * Usage:
 *   node scripts/build-js.js              # production build
 *   node scripts/build-js.js --dev        # development build (no minify, source maps)
 */

const esbuild = require('esbuild');
const path = require('path');
const fs = require('fs');

const isDev = process.argv.includes('--dev');
const JS_DIR = path.join(__dirname, '..', 'js');
const DIST_DIR = path.join(__dirname, '..', 'js', 'dist');
const ENTRY_DIR = path.join(__dirname, '..', 'js', 'entries');

// ── Bundle Definitions ───────────────────────────────────────────────────────

const bundles = ['core', 'shared', 'candidate', 'recruiter', 'admin', 'mentor'];

// ── Build ────────────────────────────────────────────────────────────────────

async function build() {
    console.log(`\n  Building JS bundles (${isDev ? 'development' : 'production'})...\n`);

    // Ensure dist directory exists
    if (!fs.existsSync(DIST_DIR)) {
        fs.mkdirSync(DIST_DIR, { recursive: true });
    }

    const results = [];

    for (const name of bundles) {
        const entryPoint = path.join(ENTRY_DIR, `${name}.js`);

        if (!fs.existsSync(entryPoint)) {
            console.warn(`  Skipping ${name}.js (entry point not found)`);
            continue;
        }

        try {
            await esbuild.build({
                entryPoints: [entryPoint],
                bundle: true,
                outfile: path.join(DIST_DIR, `${name}.js`),
                format: 'iife',
                target: ['es2020'],
                minify: !isDev,
                sourcemap: isDev,
                // Preserve window.* assignments from IIFEs
                // Don't tree-shake — IIFEs have side effects
                treeShaking: false,
                legalComments: 'none',
                logLevel: 'warning',
                // Define process.env.NODE_ENV for feature flags
                define: {
                    'process.env.NODE_ENV': isDev ? '"development"' : '"production"',
                },
            });

            const stats = fs.statSync(path.join(DIST_DIR, `${name}.js`));
            const sizeKB = (stats.size / 1024).toFixed(1);
            console.log(`  ${name}.js -- ${sizeKB} KB`);
            results.push({ name, size: stats.size });
        } catch (err) {
            console.error(`  ${name}.js FAILED -- ${err.message}`);
        }
    }

    // Summary
    if (results.length > 0) {
        console.log('\n  Bundle Summary:');
        let totalSize = 0;
        for (const r of results) {
            totalSize += r.size;
            console.log(`   ${r.name}.js: ${(r.size / 1024).toFixed(1)} KB`);
        }
        console.log(`   Total: ${(totalSize / 1024).toFixed(1)} KB`);

        // Calculate savings vs individual files
        let originalSize = 0;
        const allFiles = [
            // core files
            'app-state.js', 'app-auth.js', 'config.js', 'csrf.js', 'constants.js',
            'security.js', 'xss-protection.js', 'components.js', 'toast.js', 'error-boundary.js',
            'translations.js', 'localization.js', 'performance.js', 'load-assets.js',
            // shared
            'feature-flags.js', 'cross-page-sync.js', 'notifications.js', 'chat-widget.js',
            'gdpr.js', 'accessibility-enhanced.js',
            // candidate
            'candidate-dashboard.js', 'candidate-interview.js', 'career-chat-widget.js',
            'eeo-form.js', 'eeo-coverage.js', 'profile-visitors.js', 'courses-premium.js',
            'jobs-premium.js', 'cv-builder.js',
            // recruiter
            'recruiter-enhancements.js', 'recruiter-pipeline.js', 'recruiter-onboarding.js',
            'onboarding-wizard.js', 'jd-editor.js', 'job-wizard.js', 'scoring-preview.js',
            'rubric-builder.js', 'rubrics.js', 'skill-tree-modal.js', 'reengagement.js',
            'report-builder.js', 'reports-list.js', 'background-checks.js', 'chatbot-leads.js',
            'talent-pool.js',
            // admin
            'admin-components.js', 'eeo-dashboard.js', 'prompt-management.js',
            // mentor
            'help-center.js',
        ];
        for (const f of allFiles) {
            const fp = path.join(JS_DIR, f);
            if (fs.existsSync(fp)) {
                originalSize += fs.statSync(fp).size;
            }
        }
        const savings = originalSize > 0 ? ((1 - totalSize / originalSize) * 100).toFixed(0) : 0;
        console.log(`   Original: ${(originalSize / 1024).toFixed(1)} KB -> Bundled: ${(totalSize / 1024).toFixed(1)} KB (${savings}% smaller via minification)`);
    }

    console.log('\n  Build complete!\n');
}

build().catch(err => {
    console.error('Build failed:', err);
    process.exit(1);
});
