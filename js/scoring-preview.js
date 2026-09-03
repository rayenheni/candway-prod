/* ============================================================================
   SCORING PREVIEW — Live answer scoring with rubric engine
   Vanilla JS — real-time per-skill breakdown
   ============================================================================ */

class ScoringPreview {
    constructor(container, options = {}) {
        this.container = typeof container === 'string' ? document.getElementById(container) : container;
        this.jobId = options.jobId || 0;
        this.apiBase = '/api/v1/rubric';
        this.debounceTimer = null;
        this.lastAnswer = '';
        this.lastResult = null;
        this.onResult = options.onResult || (() => {});
        this.onSectionNav = options.onSectionNav || (() => {});

        this.init();
    }

    destroy() {
        clearTimeout(this.debounceTimer);
        this.container.innerHTML = '';
    }

    init() {
        this.renderShell();
        this.bindEvents();
    }

    renderShell() {
        this.container.innerHTML = `
            <div class="scoring-preview space-y-4">
                <div id="preview-results" class="hidden space-y-4">
                    <div class="sp-result-section" data-section="breakdown">
                        <div class="bg-white rounded-2xl border border-slate-100 shadow-sm p-6">
                            <div class="flex items-start justify-between gap-6">
                                <div class="flex-1">
                                    <h3 class="text-sm font-bold text-slate-800 mb-4 flex items-center gap-2">
                                        <i class="fas fa-chart-pie text-emerald-400"></i>
                                        Score Breakdown
                                    </h3>
                                    <div id="preview-category-scores" class="space-y-3"></div>
                                </div>
                                <div class="score-gauge flex-shrink-0" id="overall-gauge">
                                    <svg class="w-32 h-32" viewBox="0 0 120 120">
                                        <circle cx="60" cy="60" r="54" fill="none" stroke="#e2e8f0" stroke-width="8"/>
                                        <circle id="gauge-arc" cx="60" cy="60" r="54" fill="none"
                                                stroke="#6366f1" stroke-width="8" stroke-dasharray="339.292"
                                                stroke-dashoffset="339.292" stroke-linecap="round"/>
                                    </svg>
                                    <div class="score-value" id="gauge-score">—</div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="sp-result-section hidden" data-section="skills">
                        <div class="bg-white rounded-2xl border border-slate-100 shadow-sm p-6">
                            <h3 class="text-sm font-bold text-slate-800 mb-4 flex items-center gap-2">
                                <i class="fas fa-microchip text-amber-400"></i>
                                Per-Skill Breakdown
                            </h3>
                            <div id="preview-skill-scores" class="space-y-3"></div>
                        </div>
                    </div>

                    <div class="sp-result-section hidden" data-section="evidence">
                        <div class="bg-white rounded-2xl border border-slate-100 shadow-sm p-6">
                            <h3 class="text-sm font-bold text-slate-800 mb-4 flex items-center gap-2">
                                <i class="fas fa-quote-right text-blue-400"></i>
                                Evidence Mapping
                            </h3>
                            <div id="preview-evidence" class="space-y-3"></div>
                        </div>
                    </div>

                    <div class="sp-result-section hidden" data-section="gaps">
                        <div class="bg-white rounded-2xl border border-slate-100 shadow-sm p-6">
                            <h3 class="text-sm font-bold text-slate-800 mb-4 flex items-center gap-2">
                                <i class="fas fa-lightbulb text-rose-400"></i>
                                Gaps & Improvement
                            </h3>
                            <div id="preview-gaps"></div>
                        </div>
                    </div>

                    <div id="preview-variant-compare" class="hidden sp-result-section" data-section="breakdown">
                        <div class="bg-gradient-to-r from-blue-50 to-purple-50 rounded-2xl border border-blue-100 shadow-sm p-6">
                            <h3 class="text-sm font-bold text-slate-800 mb-3 flex items-center gap-2">
                                <i class="fas fa-flask text-purple-400"></i>
                                Variant Comparison
                            </h3>
                            <div id="preview-variant-scores" class="grid grid-cols-2 gap-4"></div>
                        </div>
                    </div>
                </div>

                <div id="preview-loading" class="hidden space-y-4">
                    <div class="bg-white rounded-2xl border border-slate-100 p-6 animate-pulse">
                        <div class="h-4 bg-slate-100 rounded w-1/3 mb-4"></div>
                        <div class="space-y-3">
                            <div class="h-12 bg-slate-50 rounded-xl"></div>
                            <div class="h-12 bg-slate-50 rounded-xl"></div>
                            <div class="h-12 bg-slate-50 rounded-xl"></div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    bindEvents() {
        const input = this.container.querySelector('#preview-answer-input');
        const btn = this.container.querySelector('#btn-preview-score');
        const seniority = this.container.querySelector('#preview-seniority');

        // Auto-score with debounce (1.5s after typing stops)
        input.addEventListener('input', () => {
            clearTimeout(this.debounceTimer);
            const text = input.value.trim();
            if (text.length < 20) {
                this.container.querySelector('#preview-status').textContent = 'Type more for analysis...';
                return;
            }
            this.container.querySelector('#preview-status').textContent = 'Analyzing...';
            this.debounceTimer = setTimeout(() => this.score(text, seniority.value), 1500);
        });

        // Manual score button
        btn.addEventListener('click', () => {
            const text = input.value.trim();
            if (text.length < 10) {
                this.showToast('Please enter at least 10 characters', 'warning');
                return;
            }
            this.score(text, seniority.value);
        });

        // Enable/disable button based on input
        input.addEventListener('input', () => {
            btn.disabled = input.value.trim().length < 10;
        });
        btn.disabled = true;
    }

    async score(answerText, seniority) {
        this.lastAnswer = answerText;
        this.showLoading(true);
        this.container.querySelector('#preview-status').textContent = 'Scoring...';

        try {
            const resp = await fetch(`${this.apiBase}/preview-score`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({
                    job_id: this.jobId,
                    answer_text: answerText,
                    seniority: seniority || 'mid'
                })
            });

            if (!resp.ok) {
                const err = await resp.json();
                throw new Error(err.detail || 'Scoring failed');
            }

            const data = await resp.json();
            this.lastResult = data;
            this.renderResults(data);
            try { this.onResult(data); } catch (e) { /* ignore */ }
        } catch (e) {
            this.showLoading(false);
            this.container.querySelector('#preview-status').textContent = 'Error: ' + e.message;
            this.showToast(e.message, 'error');
        }
    }

    showLoading(show) {
        const loading = this.container.querySelector('#preview-loading');
        const results = this.container.querySelector('#preview-results');
        if (loading) loading.classList.toggle('hidden', !show);
        if (results) results.classList.toggle('hidden', show);
        const empty = document.getElementById('sp-empty-state');
        if (empty) empty.classList.toggle('hidden', show);
    }

    renderResults(data) {
        const results = this.container.querySelector('#preview-results');
        results.classList.remove('hidden');
        this.showLoading(false);

        const variantA = data.variant_a || {};
        const skills = variantA.skills || {};
        const extracted = data.extracted_skills || [];
        const overall = variantA.overall || 0;

        // Overall gauge
        this.renderGauge(overall);

        // Category scores (compute from skills)
        this.renderCategoryScores(skills);

        // Per-skill breakdown
        this.renderSkillScores(skills);

        // Evidence mapping
        this.renderEvidence(extracted, skills);

        // Gaps
        this.renderGaps(skills);

        // Variant comparison if available
        if (data.variant_b) {
            this.renderVariantComparison(data);
        }
    }

    renderGauge(score) {
        const gaugeArc = this.container.querySelector('#gauge-arc');
        const gaugeScore = this.container.querySelector('#gauge-score');
        const circumference = 339.292;
        const offset = circumference - (score / 100) * circumference;
        gaugeArc.setAttribute('stroke-dashoffset', offset);
        gaugeScore.textContent = score;

        // Color based on score
        const color = score >= 75 ? '#10b981' : score >= 50 ? '#f59e0b' : '#ef4444';
        gaugeArc.setAttribute('stroke', color);
    }

    renderCategoryScores(skills) {
        const container = this.container.querySelector('#preview-category-scores');
        const categories = this.groupByCategory(skills);
        let html = '';

        categories.forEach(cat => {
            // TODO: move to backend — category.average_score
            const avg = Math.round(cat.scores.reduce((a, b) => a + b, 0) / cat.scores.length);
            const color = avg >= 75 ? 'bg-emerald-400' : avg >= 50 ? 'bg-amber-400' : 'bg-rose-400';
            html += `
                <div>
                    <div class="flex items-center justify-between text-xs mb-1">
                        <span class="font-bold text-slate-700">${this.esc(cat.name)}</span>
                        <span class="font-mono font-bold ${avg >= 75 ? 'text-emerald-600' : avg >= 50 ? 'text-amber-600' : 'text-rose-600'}">${avg}</span>
                    </div>
                    <div class="h-2 bg-slate-100 rounded-full overflow-hidden">
                        <div class="h-full rounded-full ${color} transition-all duration-500" style="width: ${avg}%"></div>
                    </div>
                </div>
            `;
        });

        container.innerHTML = html || '<p class="text-xs text-slate-400">No categories scored.</p>';
    }

    groupByCategory(skills) {
        const techSkills = ['Python', 'JavaScript', 'SQL', 'API Design', 'Docker', 'Kubernetes', 'AWS', 'Node.js', 'Git', 'React'];
        const softSkills = ['Communication', 'Problem Solving', 'Leadership', 'Collaboration'];
        const groups = { 'Technical': [], 'Soft Skills': [] };

        Object.entries(skills).forEach(([name, data]) => {
            const score = data.final_score || data.score || 0;
            if (techSkills.some(t => name.toLowerCase().includes(t.toLowerCase()))) {
                groups['Technical'].push(score);
            } else if (softSkills.some(s => name.toLowerCase().includes(s.toLowerCase()))) {
                groups['Soft Skills'].push(score);
            } else {
                groups['Technical'].push(score);
            }
        });

        return Object.entries(groups)
            .filter(([_, scores]) => scores.length > 0)
            .map(([name, scores]) => ({ name, scores }));
    }

    renderSkillScores(skills) {
        const container = this.container.querySelector('#preview-skill-scores');
        const entries = Object.entries(skills).sort((a, b) => {
            return (b[1].final_score || 0) - (a[1].final_score || 0);
        });

        if (entries.length === 0) {
            container.innerHTML = '<p class="text-xs text-slate-400">No skills extracted from this answer.</p>';
            return;
        }

        let html = '';
        entries.forEach(([name, data]) => {
            const score = data.final_score || data.score || 0;
            const quality = data.quality || 'medium';
            const qualityLabel = quality.charAt(0).toUpperCase() + quality.slice(1);
            const barClass = score >= 75 ? 'high' : score >= 50 ? 'medium' : 'low';
            const matchedLevel = data.matched_level || '';

            html += `
                <div class="skill-score-row">
                    <div class="w-24 shrink-0">
                        <span class="text-xs font-bold text-slate-700">${this.esc(name)}</span>
                        <span class="text-[10px] text-slate-400 block">${qualityLabel} evidence</span>
                    </div>
                    <div class="flex-1">
                        <div class="skill-bar">
                            <div class="fill ${barClass}" style="width: ${score}%"></div>
                        </div>
                        ${matchedLevel ? `<span class="text-[10px] text-slate-400 mt-0.5 block">${this.esc(matchedLevel)}</span>` : ''}
                    </div>
                    <span class="text-sm font-bold font-mono w-10 text-right ${barClass === 'high' ? 'text-emerald-600' : barClass === 'medium' ? 'text-amber-600' : 'text-rose-600'}">
                        ${score}
                    </span>
                </div>
            `;
        });

        container.innerHTML = html;
    }

    renderEvidence(extracted, skills) {
        const container = this.container.querySelector('#preview-evidence');

        if (extracted.length === 0) {
            container.innerHTML = '<p class="text-xs text-slate-400">No evidence extracted from the answer.</p>';
            return;
        }

        let html = '';
        extracted.forEach(item => {
            const skillName = item.skill_name || '';
            const skillData = skills[skillName.toLowerCase()] || {};
            const matchedKw = skillData.matched_keywords || [];
            const sentences = item.evidence_sentences || [];

            html += `<div class="evidence-card">
                <div class="flex items-center gap-2 mb-1">
                    <span class="text-xs font-bold text-indigo-600">${this.esc(skillName)}</span>
                    <span class="text-[10px] font-medium px-1.5 py-0.5 rounded ${
                        item.quality === 'strong' ? 'bg-emerald-100 text-emerald-700' :
                        item.quality === 'medium' ? 'bg-amber-100 text-amber-700' :
                        'bg-slate-100 text-slate-500'
                    }">${item.quality || 'weak'}</span>
                </div>`;

            sentences.forEach(s => {
                let highlighted = this.esc(s);
                matchedKw.forEach(kw => {
                    const re = new RegExp(`(${kw.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
                    highlighted = highlighted.replace(re, '<span class="keyword-match">$1</span>');
                });
                html += `<div class="evidence-text">${highlighted}</div>`;
            });

            html += '</div>';
        });

        container.innerHTML = html;
    }

    renderGaps(skills) {
        const container = this.container.querySelector('#preview-gaps');
        const entries = Object.entries(skills);
        const lowScores = entries.filter(([_, d]) => (d.final_score || 0) < 50);

        if (lowScores.length === 0) {
            container.innerHTML = `
                <div class="flex items-center gap-2 text-emerald-600">
                    <i class="fas fa-check-circle"></i>
                    <span class="text-sm font-medium">No critical gaps detected.</span>
                </div>
            `;
            return;
        }

        let html = '<div class="space-y-2">';
        lowScores.forEach(([name, data]) => {
            const missing = data.missing_competencies || [];
            html += `
                <div class="flex items-start gap-3 p-3 bg-rose-50 rounded-xl">
                    <i class="fas fa-exclamation-triangle text-rose-400 mt-0.5"></i>
                    <div>
                        <span class="text-sm font-bold text-rose-700">${this.esc(name)}</span>
                        <span class="text-sm text-rose-600 ml-2">— ${data.final_score || 0}/100</span>
                        ${missing.length > 0 ? `
                            <div class="mt-1 text-xs text-rose-500">
                                Missing: ${missing.slice(0, 2).join('; ')}
                            </div>
                        ` : ''}
                    </div>
                </div>
            `;
        });
        html += '</div>';
        container.innerHTML = html;
    }

    renderVariantComparison(data) {
        const container = this.container.querySelector('#preview-variant-compare');
        const scoresContainer = this.container.querySelector('#preview-variant-scores');
        container.classList.remove('hidden');

        const a = data.variant_a;
        const b = data.variant_b;
        const delta = data.delta || 0;

        scoresContainer.innerHTML = `
            <div class="ab-test-card text-center">
                <span class="variant-badge a">Variant A</span>
                <div class="text-3xl font-black text-blue-600 mt-2">${a.overall || 0}</div>
                <div class="text-xs text-slate-400 mt-1">Current Rubric</div>
            </div>
            <div class="ab-test-card text-center">
                <span class="variant-badge b">Variant B</span>
                <div class="text-3xl font-black text-purple-600 mt-2">${b.overall || 0}</div>
                <div class="text-xs text-slate-400 mt-1">Modified Weights</div>
            </div>
            <div class="col-span-2 text-center mt-2">
                <span class="text-sm font-bold ${delta >= 0 ? 'text-emerald-600' : 'text-rose-600'}">
                    Delta: ${delta >= 0 ? '+' : ''}${delta} points
                </span>
            </div>
        `;
    }

    // ---- UTILITIES ----
    esc(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    showToast(msg, type) {
        const toast = document.createElement('div');
        toast.className = `fixed bottom-6 right-6 z-50 px-5 py-3 rounded-xl shadow-lg text-sm font-bold
                           ${type === 'error' ? 'bg-red-500 text-white' :
                            type === 'warning' ? 'bg-amber-500 text-white' :
                            'bg-slate-800 text-white'}`;
        toast.textContent = msg;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    }

    toast(msg, type) { this.showToast(msg, type); }
}

// ---- EXPORT for legacy pages ----
window.ScoringPreview = ScoringPreview;
