class JDEditor {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        if (!this.container) return;

        this.options = Object.assign({
            onSave: null,
            initialContent: '',
            showBiasPanel: true,
            autoAnalyze: true,
            debounceMs: 1000,
        }, options);

        this.editor = null;
        this.biasPanel = null;
        this.analysisTimeout = null;
        this.lastAnalysis = null;
        this.score = null;
        this.debounceTimer = null;

        this.init();
    }

    init() {
        this.container.innerHTML = `
            <div class="jd-editor-wrapper flex gap-6">
                <div class="jd-editor-main flex-1 min-w-0">
                    <div class="flex items-center justify-between mb-2 px-1">
                        <label class="text-xs font-bold text-slate-400 uppercase tracking-wider">Job Description</label>
                        <div class="flex items-center gap-2">
                            <button type="button" onclick="window.jdEditor?.checkBias()" class="text-xs font-bold text-indigo-600 bg-indigo-50 hover:bg-indigo-100 px-3 py-1.5 rounded-lg transition flex items-center gap-1.5">
                                <i class="fas fa-shield-halved"></i> Check Bias
                            </button>
                            <button type="button" onclick="window.jdEditor?.generateWithAI()" class="text-xs font-bold text-purple-600 bg-purple-50 hover:bg-purple-100 px-3 py-1.5 rounded-lg transition flex items-center gap-1.5">
                                <i class="fas fa-wand-magic-sparkles"></i> Generate with AI
                            </button>
                        </div>
                    </div>
                    <div class="jd-editor-textarea-wrapper relative">
                        <textarea id="jd-editor-textarea" rows="8"
                            class="w-full bg-slate-50 border border-slate-200 rounded-2xl px-5 py-4 text-sm font-medium text-slate-700 focus:outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all resize-y min-h-[200px]"
                            placeholder="Describe the role responsibilities and requirements..."></textarea>
                        <div id="jd-editor-highlights" class="absolute inset-0 pointer-events-none rounded-2xl overflow-hidden px-5 py-4 text-sm font-medium" style="display:none;"></div>
                    </div>
                </div>
                <div id="jd-bias-panel" class="w-80 shrink-0 space-y-4 hidden">
                    <div class="bg-white rounded-2xl border border-slate-200 p-4">
                        <div class="flex items-center justify-between mb-3">
                            <h3 class="text-xs font-bold text-slate-400 uppercase tracking-wider">Inclusivity Score</h3>
                            <span class="text-[9px] text-slate-400 font-medium" id="bias-timestamp"></span>
                        </div>
                        <div class="text-center mb-4" id="bias-grade-container">
                            <div class="w-20 h-20 rounded-full border-4 mx-auto flex items-center justify-center text-3xl font-black transition-all duration-500" id="bias-grade-circle" style="border-color: #cbd5e1; color: #94a3b8;">--</div>
                            <div class="text-sm font-bold mt-2 text-slate-600" id="bias-score-text">Not analyzed</div>
                        </div>
                        <div class="space-y-2" id="bias-category-scores"></div>
                    </div>
                    <div class="bg-white rounded-2xl border border-slate-200 p-4" id="bias-flags-container">
                        <h3 class="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">Flags</h3>
                        <div id="bias-flags-list" class="space-y-2 max-h-60 overflow-y-auto">
                            <p class="text-xs text-slate-400 text-center py-4">Run analysis to see flags</p>
                        </div>
                    </div>
                    <div class="bg-white rounded-2xl border border-slate-200 p-4 hidden" id="bias-rewrite-container">
                        <div class="flex items-center justify-between mb-3">
                            <h3 class="text-xs font-bold text-slate-400 uppercase tracking-wider">Inclusive Rewrite</h3>
                            <button type="button" onclick="window.jdEditor?.applyRewrite()" class="text-[10px] font-bold text-emerald-600 bg-emerald-50 hover:bg-emerald-100 px-2 py-1 rounded-lg transition">Apply</button>
                        </div>
                        <div id="bias-rewrite-content" class="text-sm text-slate-600 leading-relaxed max-h-40 overflow-y-auto"></div>
                    </div>
                </div>
            </div>
        `;

        this.editor = this.container.querySelector('#jd-editor-textarea');
        this.biasPanel = this.container.querySelector('#jd-bias-panel');
        this.highlightsEl = this.container.querySelector('#jd-editor-highlights');

        if (this.options.initialContent) {
            this.editor.value = this.options.initialContent;
        }

        if (this.options.showBiasPanel) {
            this.biasPanel.classList.remove('hidden');
        }

        this.editor.addEventListener('input', () => this.onEditorInput());
        this.editor.addEventListener('scroll', () => this.syncScroll());

        window.jdEditor = this;
    }

    onEditorInput() {
        if (this.options.autoAnalyze) {
            clearTimeout(this.debounceTimer);
            this.debounceTimer = setTimeout(() => this.checkBias(), this.options.debounceMs);
        }
        if (typeof this.options.onChange === 'function') {
            this.options.onChange(this.editor.value);
        }
    }

    syncScroll() {
        if (this.highlightsEl) {
            this.highlightsEl.scrollTop = this.editor.scrollTop;
        }
    }

    getValue() {
        return this.editor ? this.editor.value : '';
    }

    setValue(text) {
        if (this.editor) {
            this.editor.value = text;
            this.onEditorInput();
        }
    }

    async checkBias() {
        const description = this.getValue();
        const titleInput = document.getElementById('job-title');
        const title = titleInput ? titleInput.value : '';

        if (!description.trim()) {
            this.showToast('Please enter a job description first.', 'warning');
            return;
        }

        this.setAnalyzingState(true);

        try {
            const result = await window.fetchAPI('/jd/analyze', {
                method: 'POST',
                body: JSON.stringify({ title, description })
            });

            this.lastAnalysis = result;
            this.score = result.score_entity?.final_score ?? result.overall_score;
            this.renderBiasResults(result);
        } catch (e) {
            console.error('[JD Editor] Analysis failed:', e);
            this.showToast('Bias analysis failed. Please try again.', 'error');
        } finally {
            this.setAnalyzingState(false);
        }
    }

    setAnalyzingState(analyzing) {
        const gradeCircle = document.getElementById('bias-grade-circle');
        const scoreText = document.getElementById('bias-score-text');
        const flagsList = document.getElementById('bias-flags-list');

        if (analyzing) {
            if (gradeCircle) {
                gradeCircle.innerHTML = '<i class="fas fa-spinner fa-spin text-xl"></i>';
                gradeCircle.style.borderColor = '#cbd5e1';
                gradeCircle.style.color = '#94a3b8';
            }
            if (scoreText) scoreText.textContent = 'Analyzing...';
            if (flagsList) flagsList.innerHTML = '<p class="text-xs text-slate-400 text-center py-4"><i class="fas fa-spinner fa-spin mr-2"></i>Analyzing...</p>';
        }
    }

    renderBiasResults(result) {
        const gradeCircle = document.getElementById('bias-grade-circle');
        const scoreText = document.getElementById('bias-score-text');
        const categoryScores = document.getElementById('bias-category-scores');
        const flagsList = document.getElementById('bias-flags-list');
        const timestamp = document.getElementById('bias-timestamp');

        const gradeColors = {
            'A': { bg: '#059669', border: '#059669', text: '#fff' },
            'B': { bg: '#16a34a', border: '#16a34a', text: '#fff' },
            'C': { bg: '#d97706', border: '#d97706', text: '#fff' },
            'D': { bg: '#ea580c', border: '#ea580c', text: '#fff' },
            'F': { bg: '#dc2626', border: '#dc2626', text: '#fff' },
        };
        const gc = gradeColors[result.grade] || gradeColors['F'];

        if (gradeCircle) {
            gradeCircle.textContent = result.grade;
            gradeCircle.style.borderColor = gc.border;
            gradeCircle.style.color = gc.bg;
        }
        if (scoreText) scoreText.textContent = `${result.score_entity?.final_score ?? result.overall_score}/100 - ${result.summary.split('.')[0]}`;
        if (timestamp) timestamp.textContent = new Date().toLocaleTimeString();

        const catLabels = {
            gender_inclusivity: 'Gender Inclusivity',
            age_inclusivity: 'Age Inclusivity',
            requirement_fairness: 'Requirement Fairness',
            confidence_balance: 'Confidence Balance',
            accessibility: 'Accessibility',
        };

        if (categoryScores) {
            categoryScores.innerHTML = Object.entries(result.category_scores || {}).map(([key, val]) => {
                const label = catLabels[key] || key;
                const barColor = val >= 80 ? 'bg-emerald-500' : val >= 60 ? 'bg-amber-500' : 'bg-red-500';
                return `
                    <div>
                        <div class="flex justify-between text-[10px] font-bold text-slate-500 mb-0.5">
                            <span>${label}</span>
                            <span>${val}</span>
                        </div>
                        <div class="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
                            <div class="h-full ${barColor} rounded-full transition-all duration-500" style="width:${val}%"></div>
                        </div>
                    </div>
                `;
            }).join('');
        }

        if (flagsList) {
            const flags = result.flags || [];
            if (flags.length === 0) {
                flagsList.innerHTML = '<p class="text-xs text-emerald-600 text-center py-3"><i class="fas fa-check-circle mr-1"></i> No bias flags detected</p>';
            } else {
                const severityColors = { high: 'bg-red-100 text-red-700 border-red-200', medium: 'bg-amber-100 text-amber-700 border-amber-200', low: 'bg-slate-100 text-slate-600 border-slate-200' };
                const severityIcons = { high: 'fa-circle-exclamation', medium: 'fa-triangle-exclamation', low: 'fa-circle-info' };

                flagsList.innerHTML = flags.map((f, i) => `
                    <div class="p-2.5 rounded-xl border ${severityColors[f.severity] || severityColors.low} cursor-pointer hover:opacity-80 transition" onclick="window.jdEditor?.showAlternatives(${i})" title="Click for alternatives">
                        <div class="flex items-start gap-2">
                            <i class="fas ${severityIcons[f.severity] || 'fa-circle-info'} text-xs mt-0.5"></i>
                            <div class="min-w-0 flex-1">
                                <div class="text-xs font-bold">"${SecurityUtils.escapeHTML(f.found)}"</div>
                                <div class="text-[9px] opacity-75 mt-0.5">${f.category.replace(/_/g, ' ')}</div>
                                ${f.alternatives && f.alternatives.length > 0 ? `
                                <div class="text-[9px] mt-1 text-emerald-700">Suggest: ${f.alternatives.filter(a => a).map(a => `<span class="inline-block bg-emerald-50 px-1.5 py-0.5 rounded mr-1 text-[9px] font-medium">${SecurityUtils.escapeHTML(a)}</span>`).join('')}</div>
                                ` : ''}
                            </div>
                        </div>
                    </div>
                `).join('');
            }
        }

        const rewriteContainer = document.getElementById('bias-rewrite-container');
        const rewriteContent = document.getElementById('bias-rewrite-content');
        if (rewriteContainer && rewriteContent && result.rewritten_description) {
            rewriteContainer.classList.remove('hidden');
            rewriteContent.textContent = result.rewritten_description;
        } else if (rewriteContainer) {
            rewriteContainer.classList.add('hidden');
        }
    }

    showAlternatives(flagIndex) {
        const flags = this.lastAnalysis?.flags || [];
        const flag = flags[flagIndex];
        if (!flag || !flag.alternatives || flag.alternatives.length === 0) return;

        const textarea = this.editor;
        const word = flag.found;
        const alt = flag.alternatives.filter(a => a)[0];
        if (!alt) return;

        const cursorPos = textarea.selectionStart;
        const text = textarea.value;
        const wordRegex = new RegExp('\\b' + this.escapeRegex(word) + '\\b', 'i');
        const match = wordRegex.exec(text);

        if (match) {
            const before = text.substring(0, match.index);
            const after = text.substring(match.index + match[0].length);
            textarea.value = before + alt + after;
            textarea.selectionStart = textarea.selectionEnd = match.index + alt.length;
            textarea.dispatchEvent(new Event('input'));
            this.showToast(`Replaced "${word}" with "${alt}"`, 'success');
            this.checkBias();
        }
    }

    escapeRegex(str) {
        return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    applyRewrite() {
        const rewriteContent = document.getElementById('bias-rewrite-content');
        if (!rewriteContent || !rewriteContent.textContent) return;

        this.setValue(rewriteContent.textContent);
        this.showToast('Inclusive rewrite applied!', 'success');
        document.getElementById('bias-rewrite-container')?.classList.add('hidden');
    }

    async generateWithAI() {
        const titleInput = document.getElementById('job-title');
        const skillsInput = document.getElementById('job-skills');
        const title = titleInput ? titleInput.value : '';
        const skills = skillsInput ? skillsInput.value.split(',').map(s => s.trim()).filter(s => s) : [];

        if (!title) {
            this.showToast('Please enter a job title first.', 'warning');
            return;
        }

        const btn = this.container.querySelector('[onclick*="generateWithAI"]');
        if (btn) {
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating...';
            btn.disabled = true;
        }

        try {
            const data = await window.fetchAPI('/recruiter/generate-job', {
                method: 'POST',
                body: JSON.stringify({ title, skills })
            });

            if (data.description) {
                this.setValue(data.description);
                this.showToast('Job description generated!', 'success');
            }
        } catch (e) {
            console.error('[JD Editor] AI generation failed:', e);
            this.showToast('AI generation failed. Please try again.', 'error');
        } finally {
            if (btn) {
                btn.innerHTML = '<i class="fas fa-wand-magic-sparkles"></i> Generate with AI';
                btn.disabled = false;
            }
        }
    }

    showToast(message, type) {
        if (typeof Components !== 'undefined' && Components.showToast) {
            Components.showToast(message, type);
        }
    }
}

window.JDEditor = JDEditor;
