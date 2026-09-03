/* ============================================================================
   RUBRIC BUILDER — Consolidated (v3.0)
   Modes: admin-wizard, recruiter-view, recruiter-modal
   Replaces: admin IIFE (v2.0), SkillTreeEditor (v1.0), skill-tree-modal.js
   ============================================================================ */

class RubricBuilder {
    // --- STATIC DOM HELPERS ------------------------------------------------
    static $(sel, ctx) { return (ctx || document).querySelector(sel); }
    static $$(sel, ctx) { return Array.from((ctx || document).querySelectorAll(sel)); }
    static esc(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    // --- CONSTRUCTOR --------------------------------------------------------
    constructor(el, options = {}) {
        this.el = typeof el === 'string' ? document.querySelector(el) : el;
        this.mode = options.mode || 'admin';
        this.jobId = options.jobId || null;
        this.readonly = options.readonly || false;
        this.disableCategoryEditing = options.disableCategoryEditing || false;
        this.onChange = options.onChange || null;
        this.onLoad = options.onLoad || null;

        // Shared state
        this.rubricData = null;
        this.draftId = null;
        this.saving = false;
        this.toastTimer = null;

        // Admin state
        this._adminState = null;

        // Modal state
        this._modalStep = 1;
        this._modalTotalSteps = 6;

        if (this.mode === 'admin') this._initAdmin();
        else if (this.mode === 'view') this._initView();
        else if (this.mode === 'modal') this._initModal();
    }

    // ====================================================================
    // SHARED DATA MODEL
    // ====================================================================

    buildRubricJson() {
        const cats = (this.rubricData && this.rubricData.categories || []).map(cat => ({
            id: cat.id,
            name: cat.name,
            description: cat.description || '',
            weight: cat.weight || 1.0,
            subcategories: (cat.subcategories || []).map(sub => ({
                id: sub.id,
                name: sub.name,
                description: sub.description || '',
                weight: sub.weight || 1.0,
                skills: (sub.skills || []).map(sk => ({
                    id: sk.id,
                    name: sk.name,
                    description: sk.description || '',
                    keywords: sk.keywords || [],
                    levels: sk.levels || { junior: [], mid: [], senior: [] },
                    weight: sk.weight || 1.0,
                    is_required: !!sk.is_required,
                })),
            })),
        }));
        return {
            job_id: this.jobId,
            version: (this.rubricData && this.rubricData.version) || 1,
            seniority: (this.rubricData && this.rubricData.seniority) || 'mid',
            categories: cats,
        };
    }

    async loadRubric(jobId) {
        const id = jobId || this.jobId;
        if (!id) {
            this._renderEmpty('No job selected.');
            return;
        }
        const container = this.el;
        container.innerHTML = `
            <div class="flex items-center justify-center h-64 text-slate-400">
                <i class="fas fa-spinner fa-spin text-2xl mr-3"></i>
                <span class="text-sm font-medium">Loading skill tree...</span>
            </div>`;
        try {
            const resp = await fetch(`/api/v1/rubric/jobs/${id}`, { credentials: 'include' });
            if (resp.ok) {
                this.rubricData = await resp.json();
                await this._ensureDraft();
                this.renderTree();
                if (typeof this.onLoad === 'function') this.onLoad(this);
            } else {
                this._renderEmpty('No rubric found for this job. Use the Rubric Builder to create one first.');
            }
        } catch (e) {
            this._renderEmpty('Network error loading rubric.');
        }
    }

    async _ensureDraft() {
        try {
            const resp = await fetch(`/api/v1/rubric/drafts/${this.jobId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ name: `Draft for job ${this.jobId}` }),
            });
            if (resp.ok) {
                const data = await resp.json();
                this.draftId = data.id;
            }
        } catch (e) {
            console.warn('Failed to create draft:', e);
        }
    }

    async saveDraft() {
        if (!this.draftId || this.saving) return;
        this.saving = true;
        const btn = document.getElementById('ste-save-btn');
        if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i> Saving...'; }
        try {
            const payload = this.buildRubricJson();
            const resp = await fetch(`/api/v1/rubric/drafts/${this.draftId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ rubric_json: payload }),
            });
            if (resp.ok) {
                this.showToast('Draft saved', 'success');
            } else {
                this.showToast('Failed to save draft', 'error');
            }
        } catch (e) {
            this.showToast('Save failed: ' + e.message, 'error');
        } finally {
            this.saving = false;
            if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fas fa-save mr-1"></i> Save Draft'; }
        }
    }

    async publishDraft() {
        if (!this.draftId) return;
        if (!confirm('Publish this rubric? It will be used for all new candidate scoring.')) return;
        const btn = document.getElementById('ste-publish-btn');
        if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i> Publishing...'; }
        try {
            const resp = await fetch(`/api/v1/rubric/drafts/${this.draftId}/publish`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ seniority: (this.rubricData && this.rubricData.seniority) || 'mid' }),
            });
            if (resp.ok) {
                this.showToast('Rubric published!', 'success');
            } else {
                const err = await resp.json().catch(() => ({}));
                this.showToast('Publish failed: ' + (err.detail || 'Unknown'), 'error');
            }
        } catch (e) {
            this.showToast('Publish failed: ' + e.message, 'error');
        } finally {
            if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fas fa-check-circle mr-1"></i> Publish'; }
        }
    }

    addSkill(catIndex, name) {
        const cat = this.rubricData.categories[catIndex];
        if (!cat) return;
        let sub = (cat.subcategories || [])[0];
        if (!sub) {
            if (this.disableCategoryEditing) {
                this.showToast('Cannot add skill — no subcategory exists. Ask your admin to set up subcategories.', 'error');
                return;
            }
            sub = {
                id: 'sub_' + Math.random().toString(36).slice(2, 10),
                name: 'General',
                description: '',
                weight: 1.0,
                skills: [],
            };
            if (!cat.subcategories) cat.subcategories = [];
            cat.subcategories.push(sub);
        }
        if (!sub.skills) sub.skills = [];
        sub.skills.push({
            id: 'sk_' + Math.random().toString(36).slice(2, 10),
            name: name,
            description: '',
            keywords: [],
            levels: { junior: [], mid: [], senior: [] },
            weight: 1.0,
            is_required: false,
        });
        this._normalizeCategoryWeights(catIndex);
        this.renderTree();
        this._notifyChange();
        this.showToast(`Added "${name}"`, 'success');
    }

    removeSkill(catIndex, skillIndex) {
        const cat = this.rubricData.categories[catIndex];
        if (!cat) return;
        const subcats = cat.subcategories || [];
        let offset = skillIndex;
        for (const sub of subcats) {
            const skills = sub.skills || [];
            if (offset < skills.length) {
                const name = skills[offset].name;
                skills.splice(offset, 1);
                this._normalizeCategoryWeights(catIndex);
                this.renderTree();
                this._notifyChange();
                this.showToast(`Removed "${name}"`, 'info');
                return;
            }
            offset -= skills.length;
        }
        this.showToast('Skill not found', 'error');
    }

    _normalizeCategoryWeights(catIndex) {
        const cat = this.rubricData.categories[catIndex];
        if (!cat) return;
        const subcats = cat.subcategories || [];
        const allSkills = subcats.flatMap(sc => sc.skills || []);
        if (!allSkills.length) return;
        const total = allSkills.reduce((s, sk) => s + (sk.weight || 1), 0);
        if (total === 0) return;
        const scale = 100 / total;
        let newTotal = 0;
        allSkills.forEach((sk) => { sk.weight = Math.round((sk.weight || 1) * scale); newTotal += sk.weight; });
        if (allSkills.length && newTotal !== 100) {
            allSkills[0].weight += (100 - newTotal);
        }
    }

    _recalcWeights() {
        if (!this.rubricData || !this.rubricData.categories) return;
        const cats = this.rubricData.categories;
        const total = cats.reduce((s, c) => s + (c.weight || 0), 0);
        if (total > 0) {
            cats.forEach(c => { c.weight = (c.weight || 0) / total; });
        }
        this.renderTree();
        this._notifyChange();
    }

    _notifyChange() {
        const total = this.rubricData.categories.reduce((s, c) => s + (c.weight || 0), 0);
        const totalEl = document.getElementById('ste-total-weight');
        if (totalEl) totalEl.textContent = Math.round(total * 100) + '%';
        if (this.onChange) this.onChange(this.rubricData);
    }

    showToast(msg, type) {
        const existing = document.getElementById('rb-toast-global');
        if (existing) existing.remove();
        const colors = { error: 'bg-red-500', success: 'bg-emerald-500', info: 'bg-indigo-500' };
        const toast = document.createElement('div');
        toast.id = 'rb-toast-global';
        toast.className = `fixed bottom-6 right-6 ${colors[type] || 'bg-indigo-500'} text-white px-5 py-3 rounded-2xl text-sm font-bold shadow-2xl z-50 transition-all`;
        toast.textContent = msg;
        document.body.appendChild(toast);
        clearTimeout(this.toastTimer);
        this.toastTimer = setTimeout(() => toast.remove(), 3000);
    }

    // ====================================================================
    // VIEW MODE — renderTree / renderSkills / renderEmpty
    // (was SkillTreeEditor)
    // ====================================================================

    _initView() {
        if (this.jobId) {
            this.loadRubric(this.jobId);
        } else {
            this._renderEmpty();
        }
    }

    _renderEmpty(msg) {
        const m = msg || 'Select a job to view its skill tree.';
        this.el.innerHTML = `
            <div class="flex flex-col items-center justify-center h-64 text-slate-400 gap-3">
                <i class="fas fa-tree text-3xl text-slate-300"></i>
                <span class="text-sm font-medium">${RubricBuilder.esc(m)}</span>
            </div>`;
    }

    renderTree() {
        if (!this.rubricData || !this.rubricData.categories || !this.rubricData.categories.length) {
            this.el.innerHTML = `
                <div class="flex flex-col items-center justify-center h-64 text-slate-400 gap-3">
                    <i class="fas fa-tree text-3xl text-slate-300"></i>
                    <span class="text-sm font-medium">No rubric yet for this job.</span>
                    <a href="/recruiter/skill-tree/create?job_id=${this.jobId}" class="text-xs font-bold text-indigo-600 hover:text-indigo-800 underline">
                        Create one →
                    </a>
                </div>`;
            return;
        }

        const cats = this.rubricData.categories;
        let html = `<div class="space-y-4">`;

        cats.forEach((cat, ci) => {
            const pct = Math.round((cat.weight || 0.25) * 100);
            html += `
                <div class="skill-category border border-slate-200 rounded-2xl overflow-hidden bg-white/80">
                    <div class="flex items-center justify-between px-4 py-3 bg-slate-50 border-b border-slate-100">
                        <div class="flex items-center gap-2">
                            <i class="fas fa-folder-open text-indigo-400 text-sm"></i>
                            <span class="font-bold text-sm text-slate-800">${RubricBuilder.esc(cat.name)}</span>
                            <span class="text-[10px] font-mono font-bold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-full">${pct}%</span>
                        </div>
                        ${this.readonly ? '' : `
                        <div class="flex items-center gap-3">
                            <span class="text-xs font-mono font-bold text-indigo-600 w-8 text-right category-weight-label">${pct}%</span>
                            <input type="range" class="flex-1 h-1.5 bg-slate-200 rounded-full appearance-none cursor-pointer accent-indigo-500 category-weight-slider"
                                min="5" max="60" value="${pct}" data-cat-index="${ci}">
                            <button class="text-slate-400 hover:text-indigo-600 w-6 h-6 flex items-center justify-center transition-colors add-skill-btn" title="Add skill" data-cat-index="${ci}">
                                <i class="fas fa-plus-circle text-sm"></i>
                            </button>
                        </div>`}
                    </div>
                    <div class="px-4 py-3 space-y-1.5" data-skills-container="${ci}">
                        ${this._renderSkills(cat, ci)}
                    </div>
                </div>`;
        });

        const catWeightTotal = cats.reduce((s, c) => s + (c.weight || 0), 0);
        html += `</div>`;

        if (!this.readonly) {
            html += `
                <div class="glass-card p-4 mt-4">
                    <div class="flex items-center justify-center gap-3">
                        <span class="text-xs font-bold text-slate-500">Total:</span>
                        <span class="text-lg font-black font-mono text-indigo-600" id="ste-total-weight">${Math.round(catWeightTotal * 100)}%</span>
                    </div>
                </div>`;
        }

        this.el.innerHTML = html;

        if (!this.readonly) {
            this.el.querySelectorAll('.category-weight-slider').forEach(slider => {
                slider.addEventListener('input', (e) => {
                    const val = parseInt(e.target.value);
                    const label = e.target.closest('.flex').querySelector('.category-weight-label');
                    if (label) label.textContent = val + '%';
                });
                slider.addEventListener('change', (e) => {
                    const ci = parseInt(e.target.dataset.catIndex);
                    const val = parseInt(e.target.value);
                    this.rubricData.categories[ci].weight = val / 100;
                    this._recalcWeights();
                    this._notifyChange();
                });
            });

            this.el.querySelectorAll('.add-skill-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    const ci = parseInt(btn.dataset.catIndex);
                    this._showAddSkillForm(ci);
                });
            });

            this.el.querySelectorAll('.delete-skill-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    const ci = parseInt(btn.dataset.catIndex);
                    const si = parseInt(btn.dataset.skillIndex);
                    this.removeSkill(ci, si);
                });
            });
        }
    }

    _renderSkills(cat, ci) {
        const subcats = cat.subcategories || [];
        if (!subcats.length) {
            return '<div class="text-xs text-slate-400 italic">No skills in this category.</div>';
        }
        let globalSi = 0;
        return subcats.map((sub) => {
            const skills = sub.skills || [];
            if (!skills.length) return '';
            const subHtml = skills.map((skill) => {
                const si = globalSi++;
                const spct = Math.round((skill.weight || 1) * 100 / ((cat.weight || 1) * 100));
                return `
                    <div class="flex items-center gap-2 py-1.5 px-2 rounded-lg hover:bg-slate-50 group" style="padding-left:1rem;">
                        <i class="fas fa-code text-slate-300 text-[10px] w-4"></i>
                        <span class="text-xs text-slate-700 flex-1 font-medium">${RubricBuilder.esc(skill.name)}</span>
                        <span class="skill-score text-xs font-bold font-mono" data-skill-name="${RubricBuilder.esc(skill.name)}"></span>
                        <span class="text-[10px] font-mono text-slate-400">${spct}%</span>
                        ${skill.is_required ? '<span class="text-[10px] text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded font-bold">REQ</span>' : ''}
                        ${this.readonly ? '' : `
                        <button class="text-slate-300 hover:text-rose-500 opacity-0 group-hover:opacity-100 transition-all w-5 h-5 flex items-center justify-center delete-skill-btn" title="Remove skill" data-cat-index="${ci}" data-skill-index="${si}">
                            <i class="fas fa-times text-[10px]"></i>
                        </button>`}
                    </div>`;
            }).join('');
            return `
                <div class="subcategory-group mb-1">
                    <div class="flex items-center gap-1.5 py-1 px-1 text-[11px] font-bold text-sky-700">
                        <i class="fas fa-layer-group text-sky-400 text-[9px]"></i>
                        <span>${RubricBuilder.esc(sub.name)}</span>
                        <span class="text-[10px] font-mono font-bold text-sky-400 bg-sky-50 px-1.5 py-0.5 rounded-full">${Math.round((sub.weight || 1) * 100)}%</span>
                    </div>
                    <div class="border-l-2 border-sky-100 ml-2 pl-2 space-y-0.5">${subHtml}</div>
                </div>`;
        }).join('');
    }

    _showAddSkillForm(catIndex) {
        const name = prompt('Enter skill name:');
        if (!name || !name.trim()) return;
        this.addSkill(catIndex, name.trim());
    }

    // ====================================================================
    // MODAL MODE — step-based creation for skill-tree-list.html
    // (was skill-tree-modal.js)
    // ====================================================================

    static get _modalInstance() { return this.__modalInstance; }
    static set _modalInstance(v) { this.__modalInstance = v; }

    _initModal() {
        this._modalState = {
            jobId: null,
            selectedCategories: [],
            jobTitle: '',
            jobDescription: '',
            templateId: null,
            rubric: null,
        };
        this._modalStep = 1;
        this._modalTotalSteps = 6;
        this._modalBindNav();
        this._modalRenderStep();
        RubricBuilder._modalInstance = this;
    }

    _modalStepTemplates() {
        return {
            1: '<h3 class="text-lg font-bold mb-3">Select a Job</h3><select id="modal-job" class="w-full border rounded p-2"><option value="">Loading jobs...</option></select>',
            2: '<h3 class="text-lg font-bold mb-3">Select Categories</h3><div id="category-grid" class="grid grid-cols-2 gap-2"></div>',
            3: '<h3 class="text-lg font-bold mb-3">Job Details</h3><label class="block mb-2">Job Title</label><input id="job-title" type="text" class="w-full border rounded p-2 mb-4"/><label class="block mb-2">Job Description</label><textarea id="job-desc" rows="4" class="w-full border rounded p-2"></textarea>',
            4: '<h3 class="text-lg font-bold mb-3">Choose a Template</h3><button id="browse-templates" class="px-4 py-2 bg-indigo-600 text-white rounded mr-2">Browse Templates</button><button id="generate-ai" class="px-4 py-2 bg-emerald-600 text-white rounded">Generate with AI</button><div id="templates-list" class="mt-4 grid grid-cols-1 md:grid-cols-2 gap-2"></div>',
            5: '<h3 class="text-lg font-bold mb-3">Customize Rubric</h3><div id="rubric-editor" class="overflow-auto max-h-96 border rounded p-2"></div>',
            6: '<h3 class="text-lg font-bold mb-3">Publish Skill Tree</h3><p class="mb-4">Review your rubric below and click Publish.</p><pre id="final-rubric-preview" class="bg-gray-100 p-2 rounded overflow-auto"></pre>',
        };
    }

    _modalBindNav() {
        const prevBtn = document.getElementById('prev-step-btn');
        const nextBtn = document.getElementById('next-step-btn');
        if (prevBtn) prevBtn.onclick = () => this._modalPrev();
        if (nextBtn) nextBtn.onclick = () => this._modalNext();
    }

    _modalRenderStep() {
        const container = document.getElementById('modal-step-container');
        if (!container) return;
        const templates = this._modalStepTemplates();
        container.innerHTML = templates[this._modalStep] || '';
        const prevBtn = document.getElementById('prev-step-btn');
        const nextBtn = document.getElementById('next-step-btn');
        if (prevBtn) prevBtn.disabled = this._modalStep === 1;
        if (nextBtn) nextBtn.textContent = this._modalStep === this._modalTotalSteps ? 'Finish' : 'Next';
        switch (this._modalStep) {
            case 1: this._modalLoadJobs(); break;
            case 2: this._modalLoadCategories(); break;
            case 3:
                document.getElementById('job-title').value = this._modalState.jobTitle;
                document.getElementById('job-desc').value = this._modalState.jobDescription;
                break;
            case 4:
                const bt = document.getElementById('browse-templates');
                const ga = document.getElementById('generate-ai');
                if (bt) bt.onclick = () => this._modalBrowseTemplates();
                if (ga) ga.onclick = () => this._modalGenerateWithAI();
                break;
            case 5: this._modalRenderRubricEditor(); break;
            case 6: this._modalRenderFinalRubric(); break;
        }
    }

    _modalPrev() {
        if (this._modalStep > 1) {
            this._modalStep--;
            this._modalRenderStep();
        }
    }

    _modalNext() {
        if (this._modalStep === 1 && !this._modalState.jobId) { alert('Select a job first'); return; }
        if (this._modalStep === 2 && this._modalState.selectedCategories.length === 0) { alert('Pick at least one category'); return; }
        if (this._modalStep === 3) {
            this._modalState.jobTitle = (document.getElementById('job-title')?.value || '').trim();
            this._modalState.jobDescription = (document.getElementById('job-desc')?.value || '').trim();
            if (!this._modalState.jobTitle) { alert('Job title required'); return; }
        }
        if (this._modalStep === 4 && !this._modalState.rubric) { alert('Select a template or generate a rubric'); return; }
        if (this._modalStep === this._modalTotalSteps) {
            this._modalPublish();
            return;
        }
        this._modalStep++;
        this._modalRenderStep();
    }

    async _modalLoadJobs() {
        const select = document.getElementById('modal-job');
        if (!select) return;
        try {
            const res = await fetch('/api/v1/recruiter/jobs/my');
            if (!res.ok) throw new Error('Failed to fetch');
            const data = await res.json();
            select.innerHTML = '<option value="">Select job...</option>';
            (data.jobs || []).forEach(j => {
                const opt = document.createElement('option');
                opt.value = j.id;
                opt.textContent = `${j.title} – ${j.company}`;
                select.appendChild(opt);
            });
            select.onchange = () => {
                this._modalState.jobId = select.value;
                const chosen = (data.jobs || []).find(j => j.id == this._modalState.jobId);
                if (chosen) {
                    this._modalState.jobTitle = chosen.title;
                    this._modalState.jobDescription = chosen.description || '';
                }
            };
        } catch (e) {
            select.innerHTML = '<option value="">Error loading jobs</option>';
        }
    }

    async _modalLoadCategories() {
        const container = document.getElementById('category-grid');
        if (!container) return;
        container.innerHTML = 'Loading categories...';
        try {
            const res = await fetch('/api/v1/categories/job');
            const data = await res.json();
            container.innerHTML = '';
            (Array.isArray(data) ? data : data.categories || []).forEach(cat => {
                const btn = document.createElement('button');
                btn.className = 'p-2 border rounded hover:bg-indigo-50';
                btn.textContent = cat.name;
                btn.onclick = () => {
                    const idx = this._modalState.selectedCategories.indexOf(cat.id);
                    if (idx > -1) {
                        this._modalState.selectedCategories.splice(idx, 1);
                        btn.classList.remove('bg-indigo-200');
                    } else {
                        this._modalState.selectedCategories.push(cat.id);
                        btn.classList.add('bg-indigo-200');
                    }
                };
                container.appendChild(btn);
            });
        } catch (e) {
            container.textContent = 'Error loading categories';
        }
    }

    async _modalBrowseTemplates() {
        const list = document.getElementById('templates-list');
        if (!list) return;
        list.innerHTML = 'Loading templates...';
        try {
            const res = await fetch('/api/v1/rubric/templates');
            const data = await res.json();
            list.innerHTML = '';
            (data.templates || []).forEach(tpl => {
                const card = document.createElement('div');
                card.className = 'p-3 border rounded cursor-pointer hover:bg-gray-50';
                card.textContent = tpl.title;
                card.onclick = async () => {
                    this._modalState.templateId = tpl.id;
                    try {
                        const detail = await fetch(`/api/v1/rubric/template-detail/${tpl.id}`).then(r => r.json());
                        this._modalState.rubric = detail.rubric || detail;
                    } catch (_) {}
                    Array.from(list.children).forEach(c => c.classList.remove('bg-indigo-100'));
                    card.classList.add('bg-indigo-100');
                };
                list.appendChild(card);
            });
        } catch (e) {
            list.textContent = 'Error loading templates';
        }
    }

    async _modalGenerateWithAI() {
        if (!this._modalState.jobDescription) {
            alert('Provide a job description first (Step 3)');
            return;
        }
        const list = document.getElementById('templates-list');
        if (!list) return;
        list.innerHTML = '<div class="text-gray-500 italic">Generating...</div>';
        try {
            const res = await fetch('/api/v1/rubric/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ description: this._modalState.jobDescription, job_id: this._modalState.jobId }),
            });
            const data = await res.json();
            this._modalState.rubric = data.rubric || data;
            this._modalState.templateId = null;
            list.innerHTML = '<div class="text-green-600">AI rubric generated -- proceed to Customize.</div>';
        } catch (e) {
            list.textContent = 'AI generation failed';
        }
    }

    _modalRenderRubricEditor() {
        const container = document.getElementById('rubric-editor');
        if (!container) return;
        if (!this._modalState.rubric || !this._modalState.rubric.categories) {
            container.textContent = 'No rubric loaded. Choose a template or generate with AI.';
            return;
        }
        container.innerHTML = '';
        Object.entries(this._modalState.rubric.categories).forEach(([catId, cat]) => {
            const catDiv = document.createElement('div');
            catDiv.className = 'mb-3 p-2 border-b';
            const title = document.createElement('h4');
            title.textContent = cat.name || catId;
            catDiv.appendChild(title);
            const skillList = document.createElement('ul');
            skillList.className = 'list-disc pl-5';
            (cat.skills || []).forEach((skill, idx) => {
                const li = document.createElement('li');
                li.textContent = skill.name;
                const rm = document.createElement('button');
                rm.className = 'ml-2 text-red-500';
                rm.textContent = '\u2715';
                rm.onclick = () => {
                    cat.skills.splice(idx, 1);
                    this._modalRenderRubricEditor();
                };
                li.appendChild(rm);
                skillList.appendChild(li);
            });
            const addInput = document.createElement('input');
            addInput.type = 'text';
            addInput.placeholder = 'New skill name';
            addInput.className = 'border rounded p-1 mr-2';
            const addBtn = document.createElement('button');
            addBtn.textContent = 'Add Skill';
            addBtn.className = 'bg-indigo-600 text-white px-2 py-1 rounded';
            addBtn.onclick = () => {
                const name = addInput.value.trim();
                if (!name) return;
                cat.skills = cat.skills || [];
                cat.skills.push({ name });
                addInput.value = '';
                this._modalRenderRubricEditor();
            };
            catDiv.appendChild(skillList);
            catDiv.appendChild(addInput);
            catDiv.appendChild(addBtn);
            container.appendChild(catDiv);
        });
    }

    _modalRenderFinalRubric() {
        const pre = document.getElementById('final-rubric-preview');
        if (pre) pre.textContent = JSON.stringify(this._modalState.rubric, null, 2);
    }

    async _modalPublish() {
        try {
            const payload = {
                job_id: Number(this._modalState.jobId),
                title: this._modalState.jobTitle,
                description: this._modalState.jobDescription,
                categories: this._modalState.selectedCategories,
                rubric: this._modalState.rubric,
            };
            const res = await fetch('/api/v1/recruiter/skill-trees', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            if (!res.ok) throw new Error('Publish failed');
            alert('Skill tree published!');
            this._modalClose();
            if (window.loadSkillTrees) window.loadSkillTrees();
        } catch (e) {
            alert(e.message);
        }
    }

    _modalClose() {
        const modal = document.getElementById('skill-tree-modal');
        if (modal) modal.classList.add('hidden');
    }

    // ====================================================================
    // ADMIN MODE — wizard flow for admin/rubric-builder.html
    // (was the IIFE in rubric-builder.js v2.0)
    // ====================================================================

    _initAdmin() {
        const S = {
            step: 1,
            contextTab: 'jd',
            context: {
                job_id: parseInt(new URLSearchParams(window.location.search).get('job_id') || '0', 10) || null,
                jd_text: '',
                role_title: '',
            },
            generatedRubric: null,
            draftId: null,
            skillList: [],
            categories: [],
            autoBalance: true,
            saving: false,
            lastSavedAt: null,
            advancedOpen: false,
            advancedTab: 'categories',
            _cachedTotal: null,
            _cachedCategories: null,
            _cachedCategoryCount: null,
        };
        function _invalidateCache() {
            S._cachedTotal = null;
            S._cachedCategories = null;
            S._cachedCategoryCount = null;
        }
        function _getTotalWeight() {
            if (S._cachedTotal === null) S._cachedTotal = S.skillList.reduce((s, x) => s + x.weight, 0);
            return S._cachedTotal;
        }
        function _getUniqueCategories() {
            if (S._cachedCategories === null) {
                S._cachedCategories = Array.from(new Set(S.skillList.map(s => s.category))).sort();
            }
            return S._cachedCategories;
        }
        function _getCategoryCount() {
            if (S._cachedCategoryCount === null) S._cachedCategoryCount = new Set(S.skillList.map(s => s.category)).size;
            return S._cachedCategoryCount;
        }
        this._adminState = S;

        const $ = RubricBuilder.$;
        const $$ = RubricBuilder.$$;
        const esc = RubricBuilder.esc;

        function goToStep(n) {
            S.step = n;
            $$('.rb-step').forEach(el => {
                const panel = parseInt(el.dataset.stepPanel, 10);
                el.style.display = (panel === n || (n === 'success' && el.dataset.stepPanel === 'success')) ? '' : 'none';
            });
            updateStepIndicator();
            if (n === 4) renderEditor();
            if (n === 3) renderPreview();
        }

        function updateStepIndicator() {
            $$('#rb-step-indicator .rb-step-dot').forEach(dot => {
                const ds = parseInt(dot.dataset.step, 10);
                dot.classList.remove('active', 'done', 'pending');
                if (ds < S.step) dot.classList.add('done');
                else if (ds === S.step) dot.classList.add('active');
                else dot.classList.add('pending');
            });
            const titles = {
                1: ['Create a Rubric', 'AI will generate a skill framework based on your role'],
                2: ['Generating...', 'AI is building your rubric'],
                3: ['Preview', 'Review what AI generated'],
                4: ['Edit & Publish', 'Fine-tune weights and publish'],
            };
            if (titles[S.step]) {
                $('#rb-page-title').textContent = titles[S.step][0];
                $('#rb-page-subtitle').textContent = titles[S.step][1];
            }
        }

        function switchContextTab(tab) {
            S.contextTab = tab;
            $$('.rb-context-tab').forEach(t => {
                const active = t.dataset.contextTab === tab;
                t.classList.toggle('bg-white', active);
                t.classList.toggle('text-indigo-600', active);
                t.classList.toggle('shadow-sm', active);
                t.classList.toggle('text-slate-600', !active);
                t.classList.toggle('hover:text-slate-900', !active);
            });
            $$('.rb-context-panel').forEach(p => {
                p.style.display = p.dataset.contextPanel === tab ? '' : 'none';
            });
            validateContext();
        }

        async function loadJobs() {
            const sel = $('#rb-input-job');
            try {
                const res = await fetch('/api/v1/recruiter/jobs/my?per_page=100', { credentials: 'include' });
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                const data = await res.json();
                const jobs = data.jobs || data.items || data || [];
                if (!jobs.length) {
                    sel.innerHTML = '<option value="">No jobs yet</option>';
                    const empty = $('#rb-jobs-empty');
                    if (empty) empty.style.display = '';
                    return;
                }
                sel.innerHTML = '<option value="">Select a job...</option>' +
                    jobs.map(j => `<option value="${j.id}" ${j.id === S.context.job_id ? 'selected' : ''}>${esc(j.title || ('Job #' + j.id))}</option>`).join('');
            } catch (e) {
                sel.innerHTML = '<option value="">Could not load jobs</option>';
            }
        }

        function validateContext() {
            const btn = $('#rb-generate-btn');
            let valid = false;
            if (S.contextTab === 'job') valid = !!S.context.job_id;
            else if (S.contextTab === 'jd') valid = S.context.jd_text.length >= 50;
            else valid = S.context.role_title.trim().length >= 2;
            btn.disabled = !valid;
        }

        function bindContextStep() {
            $$('.rb-context-tab').forEach(tab => {
                tab.addEventListener('click', () => switchContextTab(tab.dataset.contextTab));
            });
            const jdInput = $('#rb-input-jd');
            if (jdInput) {
                jdInput.addEventListener('input', e => {
                    S.context.jd_text = e.target.value;
                    const count = $('#rb-jd-count');
                    if (count) count.textContent = e.target.value.length;
                    validateContext();
                });
            }
            const roleInput = $('#rb-input-role');
            if (roleInput) {
                roleInput.addEventListener('input', e => {
                    S.context.role_title = e.target.value;
                    validateContext();
                });
            }
            const jobInput = $('#rb-input-job');
            if (jobInput) {
                jobInput.addEventListener('change', e => {
                    S.context.job_id = parseInt(e.target.value, 10) || null;
                    validateContext();
                });
            }
            const genBtn = $('#rb-generate-btn');
            if (genBtn) genBtn.addEventListener('click', onGenerate);
            const scratchBtn = $('#rb-start-scratch-btn');
            if (scratchBtn) scratchBtn.addEventListener('click', onStartScratch);
            loadJobs();
            if (S.context.job_id) switchContextTab('job');
        }

        async function onGenerate() {
            goToStep(2);
            await runAIGeneration();
        }

        function onStartScratch() {
            S.generatedRubric = { categories: [], role_title: 'New Rubric', seniority: 'mid', suggested_extra_skills: [] };
            S.skillList = [];
            S.categories = [];
            S.draftId = null;
            const title = $('#rb-editor-title');
            const subtitle = $('#rb-editor-subtitle');
            if (title) title.textContent = S.context.role_title || 'New Rubric';
            if (subtitle) subtitle.textContent = 'Build your rubric from scratch';
            goToStep(4);
        }

        async function runAIGeneration() {
            const statuses = ['Analyzing role requirements...', 'Identifying key skills...', 'Generating rubric...'];
            const statusEl = $('#rb-ai-status');
            const dots = $$('#rb-ai-steps .rb-step-dot');
            let i = 0;
            const statusInterval = setInterval(() => {
                i = (i + 1) % statuses.length;
                if (statusEl) statusEl.textContent = statuses[i];
                dots.forEach((d, idx) => {
                    if (idx < i) d.classList.replace('pending', 'done');
                    else if (idx === i) d.classList.replace('pending', 'active');
                    else d.classList.add('pending');
                });
            }, 3500);
            try {
                const body = {};
                if (S.contextTab === 'job') body.job_id = S.context.job_id;
                else if (S.contextTab === 'jd') body.jd_text = S.context.jd_text;
                else body.role_title = S.context.role_title;
                const res = await fetch('/api/v1/rubric/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify(body),
                });
                if (!res.ok) {
                    const err = await res.json().catch(() => ({}));
                    throw new Error(err.detail || `HTTP ${res.status}`);
                }
                S.generatedRubric = await res.json();
                clearInterval(statusInterval);
                goToStep(3);
            } catch (e) {
                clearInterval(statusInterval);
                if (statusEl) statusEl.textContent = 'Error: ' + e.message;
                toast('Failed to generate: ' + e.message, 'error');
                setTimeout(() => goToStep(1), 2500);
            }
        }

        function renderPreview() {
            const r = S.generatedRubric;
            if (!r) return;
            const pTitle = $('#rb-preview-title');
            if (pTitle) pTitle.textContent = `Here's your AI-generated rubric for ${r.role_title || 'this role'}`;
            const totalSkills = (r.categories || []).reduce((s, c) => s + (c.skills || []).length, 0);
            const summary = $('#rb-preview-summary');
            if (summary) summary.textContent = `${r.categories.length} categories, ${totalSkills} skills, ${r.seniority} level${r._source === 'fallback' ? ' · (using offline template)' : ''}`;
            const source = $('#rb-preview-source');
            if (source) source.textContent = r._source === 'fallback' ? 'Offline template' : 'AI-generated';

            const catHtml = (r.categories || []).map((cat, ci) => `
                <div class="mb-3 border border-slate-100 rounded-xl overflow-hidden" data-cat-idx="${ci}">
                    <button class="rb-cat-toggle w-full p-3 flex items-center justify-between hover:bg-slate-50 transition-colors" data-cat-toggle="${ci}">
                        <div class="flex items-center gap-2">
                            <i class="fas fa-chevron-right text-[10px] text-slate-400 transition-transform" data-cat-chevron="${ci}"></i>
                            <span class="text-sm font-black text-slate-800">${esc(cat.name)}</span>
                            <span class="text-[10px] font-bold text-slate-400">${(cat.skills || []).length} skills · ${cat.weight}%</span>
                        </div>
                        <span class="text-xs font-mono font-black text-slate-700">${cat.weight}%</span>
                    </button>
                    <div class="hidden px-3 pb-3 space-y-1" data-cat-skills="${ci}">
                        ${(cat.skills || []).map(sk => `
                            <div class="flex items-center justify-between py-1.5 px-2 rounded-lg hover:bg-slate-50">
                                <div class="flex items-center gap-2 min-w-0">
                                    <i class="fas fa-circle text-[4px] text-slate-300"></i>
                                    <span class="text-xs font-medium text-slate-700">${esc(sk.name)}</span>
                                    ${sk.is_required ? '<span class="text-[9px] font-bold text-rose-500 bg-rose-50 px-1.5 py-0.5 rounded">Required</span>' : ''}
                                </div>
                                <span class="text-[11px] font-mono font-bold text-slate-500 flex-shrink-0">${sk.weight}%</span>
                            </div>`).join('')}
                    </div>
                </div>`).join('');
            const previewCats = $('#rb-preview-categories');
            if (previewCats) previewCats.innerHTML = catHtml || '<p class="text-sm text-slate-400 text-center py-8">No categories generated. Try regenerating.</p>';

            $$('.rb-cat-toggle').forEach(btn => {
                btn.addEventListener('click', () => {
                    const idx = btn.dataset.catToggle;
                    const skills = document.querySelector(`[data-cat-skills="${idx}"]`);
                    const chev = document.querySelector(`[data-cat-chevron="${idx}"]`);
                    const isHidden = skills.classList.toggle('hidden');
                    if (chev) chev.style.transform = isHidden ? '' : 'rotate(90deg)';
                });
            });
            const first = $('.rb-cat-toggle');
            if (first) first.click();

            const sug = r.suggested_extra_skills || [];
            const banner = $('#rb-suggestions-banner');
            const chips = $('#rb-suggestions-chips');
            if (sug.length && banner && chips) {
                banner.style.display = '';
                chips.innerHTML = sug.map(s =>
                    `<button class="rb-suggestion-chip inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-bold text-indigo-700 bg-white border border-indigo-200 rounded-full hover:bg-indigo-100 transition-colors" data-suggest="${esc(s)}">
                        <i class="fas fa-plus text-[9px]"></i> ${esc(s)}
                    </button>`
                ).join('');
                $$('.rb-suggestion-chip').forEach(chip => {
                    chip.addEventListener('click', () => addSuggestedSkill(chip.dataset.suggest, chip));
                });
            } else if (banner) {
                banner.style.display = 'none';
            }
        }

        function addSuggestedSkill(name, chipEl) {
            const r = S.generatedRubric;
            const last = r.categories[r.categories.length - 1];
            if (!last) return;
            if (!last.skills) last.skills = [];
            const taken = last.skills.reduce((s, x) => s + x.weight, 0);
            const remaining = Math.max(5, last.weight - taken);
            last.skills.push({ name, weight: remaining, is_required: false, keywords: [] });
            chipEl.remove();
            toast(`Added "${name}"`);
            renderPreview();
        }

        function acceptAndEdit() {
            const r = S.generatedRubric;
            S.skillList = [];
            (r.categories || []).forEach(cat => {
                (cat.skills || []).forEach(sk => {
                    S.skillList.push({
                        id: 'sk_' + Math.random().toString(36).slice(2, 10),
                        name: sk.name,
                        weight: sk.weight,
                        category: cat.name,
                        is_required: !!sk.is_required,
                        keywords: sk.keywords || [],
                    });
                });
            });
            S.categories = r.categories;
            S.generatedRubric = null;
            normalizeWeights();
            const title = $('#rb-editor-title');
            const subtitle = $('#rb-editor-subtitle');
            if (title) title.textContent = r.role_title || 'Rubric';
            if (subtitle) subtitle.textContent = 'Auto-saving as you edit';
            goToStep(4);
        }

        function bindPreviewStep() {
            const backBtn = $('#rb-preview-back-btn');
            if (backBtn) backBtn.addEventListener('click', () => goToStep(1));
            const regenBtn = $('#rb-preview-regen-btn');
            if (regenBtn) regenBtn.addEventListener('click', () => { goToStep(2); runAIGeneration(); });
            const editBtn = $('#rb-preview-edit-btn');
            if (editBtn) editBtn.addEventListener('click', acceptAndEdit);
            const continueBtn = $('#rb-preview-continue-btn');
            if (continueBtn) continueBtn.addEventListener('click', acceptAndEdit);
        }

        function renderEditor() {
            const count = $('#rb-skill-count');
            if (count) count.textContent = `${S.skillList.length} skill${S.skillList.length !== 1 ? 's' : ''}`;
            const list = $('#rb-skill-list');
            if (!list) return;
            if (!S.skillList.length) {
                list.innerHTML = `
                    <div class="text-center py-10">
                        <div class="w-12 h-12 mx-auto mb-3 rounded-xl bg-slate-100 flex items-center justify-center">
                            <i class="fas fa-list text-slate-400"></i>
                        </div>
                        <p class="text-sm font-bold text-slate-700 mb-1">No skills yet</p>
                        <p class="text-xs text-slate-400 mb-3">Add skills manually or ask AI for suggestions.</p>
                        <button class="rb-empty-ai text-xs font-bold text-indigo-600 hover:text-indigo-800">✨ Ask AI for suggestions</button>
                    </div>`;
                const emptyAi = $('.rb-empty-ai');
                if (emptyAi) emptyAi.addEventListener('click', onAISuggest);
                updateTotalWeight();
                return;
            }
            list.innerHTML = S.skillList.map((sk, i) => `
                <div class="rb-skill-row flex items-center gap-3 p-2 rounded-lg hover:bg-slate-50 transition-colors group" draggable="true" data-skill-idx="${i}">
                    <i class="fas fa-grip-vertical text-slate-300 group-hover:text-slate-500 cursor-grab text-xs flex-shrink-0"></i>
                    <div class="flex-1 min-w-0">
                        <input type="text" value="${esc(sk.name)}" data-edit-name="${i}"
                               class="w-full text-sm font-bold text-slate-800 bg-transparent border-0 outline-none focus:bg-white focus:px-2 focus:py-0.5 focus:rounded focus:ring-1 focus:ring-indigo-200">
                        <div class="flex items-center gap-2 mt-0.5">
                            <span class="text-[10px] font-bold text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">${esc(sk.category)}</span>
                            ${sk.is_required ? '<span class="text-[9px] font-bold text-rose-500">Required</span>' : ''}
                        </div>
                    </div>
                    <div class="flex items-center gap-2 flex-shrink-0 w-48">
                        <input type="range" min="0" max="100" value="${sk.weight}" data-edit-weight="${i}" class="rb-slider flex-1">
                        <span class="text-xs font-mono font-black text-slate-700 w-10 text-right" data-weight-label="${i}">${sk.weight}%</span>
                    </div>
                    <button class="text-slate-300 hover:text-rose-500 w-6 h-6 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all flex-shrink-0" data-delete-skill="${i}">
                        <i class="fas fa-trash-alt text-xs"></i>
                    </button>
                </div>`).join('');

            $$('[data-edit-name]').forEach(inp => {
                inp.addEventListener('change', e => {
                    const i = parseInt(e.target.dataset.editName, 10);
                    S.skillList[i].name = e.target.value.trim() || 'Untitled';
                    scheduleAutoSave();
                });
            });
            $$('[data-edit-weight]').forEach(inp => {
                inp.addEventListener('input', e => {
                    const i = parseInt(e.target.dataset.editWeight, 10);
                    const v = parseInt(e.target.value, 10);
                    S.skillList[i].weight = v;
                    const label = document.querySelector(`[data-weight-label="${i}"]`);
                    if (label) label.textContent = v + '%';
                    if (S.autoBalance) autoBalance(i);
                    updateTotalWeight();
                    scheduleAutoSave();
                });
            });
            $$('[data-delete-skill]').forEach(btn => {
                btn.addEventListener('click', () => {
                    const i = parseInt(btn.dataset.deleteSkill, 10);
                    S.skillList.splice(i, 1);
                    _invalidateCache();
                    renderEditor();
                    scheduleAutoSave();
                });
            });
            bindDragAndDrop();
            updateTotalWeight();
        }

        function updateTotalWeight() {
            const total = _getTotalWeight();
            const weightEl = $('#rb-total-weight');
            if (weightEl) weightEl.textContent = total + '%';
            const badge = $('#rb-balance-badge');
            if (badge) {
                if (Math.abs(total - 100) <= 1) {
                    badge.textContent = '\u2713 Balanced';
                    badge.className = 'text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700';
                } else {
                    badge.textContent = total > 100 ? `+${total - 100}% over` : `${total - 100}% under`;
                    badge.className = 'text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-100 text-amber-700';
                }
            }
            const bar = $('#rb-weight-bar');
            if (bar) bar.style.width = Math.min(100, total) + '%';
        }

        function autoBalance(changedIdx) {
            const changed = S.skillList[changedIdx];
            const others = S.skillList.filter((_, i) => i !== changedIdx);
            const othersTotal = _getTotalWeight() - changed.weight;
            const target = Math.max(0, 100 - changed.weight);
            if (othersTotal === 0) {
                if (others.length) others[0].weight = target;
            } else {
                const scale = target / othersTotal;
                others.forEach((sk, i) => {
                    const newW = i === others.length - 1
                        ? Math.max(0, target - others.slice(0, -1).reduce((s, x) => s + Math.round(x.weight * scale), 0))
                        : Math.round(sk.weight * scale);
                    const realIdx = S.skillList.indexOf(sk);
                    sk.weight = newW;
                    const slider = document.querySelector(`[data-edit-weight="${realIdx}"]`);
                    const label = document.querySelector(`[data-weight-label="${realIdx}"]`);
                    if (slider) slider.value = newW;
                    if (label) label.textContent = newW + '%';
                });
            }
            _invalidateCache();
        }

        function normalizeWeights() {
            const total = _getTotalWeight();
            if (total === 0 || Math.abs(total - 100) < 1) return;
            const scale = 100 / total;
            let newTotal = 0;
            S.skillList.forEach(sk => { sk.weight = Math.round(sk.weight * scale); newTotal += sk.weight; });
            if (S.skillList.length && newTotal !== 100) {
                S.skillList[0].weight += (100 - newTotal);
            }
            _invalidateCache();
        }

        function bindDragAndDrop() {
            const rows = $$('.rb-skill-row');
            let dragSrc = null;
            rows.forEach(row => {
                row.addEventListener('dragstart', e => {
                    dragSrc = parseInt(row.dataset.skillIdx, 10);
                    row.classList.add('dragging');
                    e.dataTransfer.effectAllowed = 'move';
                });
                row.addEventListener('dragend', () => {
                    row.classList.remove('dragging');
                    $$('.rb-skill-row').forEach(r => r.classList.remove('drag-over-top', 'drag-over-bottom'));
                });
                row.addEventListener('dragover', e => {
                    e.preventDefault();
                    const tgt = parseInt(row.dataset.skillIdx, 10);
                    if (tgt === dragSrc) return;
                    const rect = row.getBoundingClientRect();
                    const before = e.clientY < rect.top + rect.height / 2;
                    row.classList.toggle('drag-over-top', before);
                    row.classList.toggle('drag-over-bottom', !before);
                });
                row.addEventListener('dragleave', () => {
                    row.classList.remove('drag-over-top', 'drag-over-bottom');
                });
                row.addEventListener('drop', e => {
                    e.preventDefault();
                    const tgt = parseInt(row.dataset.skillIdx, 10);
                    if (tgt === dragSrc) return;
                    const rect = row.getBoundingClientRect();
                    const before = e.clientY < rect.top + rect.height / 2;
                    const [moved] = S.skillList.splice(dragSrc, 1);
                    const insertAt = before ? tgt : tgt + 1;
                    S.skillList.splice(insertAt > dragSrc ? insertAt - 1 : insertAt, 0, moved);
                    renderEditor();
                    scheduleAutoSave();
                });
            });
        }

        function showAddSkillForm() {
            const form = $('#rb-add-skill-form');
            if (!form) return;
            const isHidden = form.classList.contains('hidden');
            form.classList.toggle('hidden', !isHidden);
            if (isHidden) {
                const cats = _getUniqueCategories();
                const existingCats = $('#rb-existing-cats');
                if (existingCats) existingCats.innerHTML = cats.map(c => `<option value="${esc(c)}">`).join('');
                const catInput = $('#rb-new-skill-cat');
                if (cats.length && catInput && !catInput.value) catInput.value = cats[0];
                const nameInput = $('#rb-new-skill-name');
                if (nameInput) nameInput.focus();
            }
        }

        function hideAddSkillForm() {
            const form = $('#rb-add-skill-form');
            if (form) form.classList.add('hidden');
            const nameInput = $('#rb-new-skill-name');
            if (nameInput) nameInput.value = '';
        }

        function submitAddSkill() {
            const nameInput = $('#rb-new-skill-name');
            const catInput = $('#rb-new-skill-cat');
            const weightInput = $('#rb-new-skill-weight');
            const reqInput = $('#rb-new-skill-required');
            const name = nameInput ? nameInput.value.trim() : '';
            if (!name) { if (nameInput) nameInput.focus(); return; }
            const category = (catInput ? catInput.value.trim() : '') || 'General';
            const weight = parseInt(weightInput ? weightInput.value : '10', 10) || 0;
            const is_required = reqInput ? reqInput.checked : false;
            S.skillList.push({
                id: 'sk_' + Math.random().toString(36).slice(2, 10),
                name, weight, category, is_required, keywords: [],
            });
            _invalidateCache();
            hideAddSkillForm();
            renderEditor();
            scheduleAutoSave();
            toast(`Added "${name}"`);
        }

        function onBrowseByCategory() {
            if (!S.categories.length) {
                toast('No categories defined. Use "Suggest skills" instead.', 'info');
                return;
            }
            toast('Browse-by-category is in Advanced > Categories. Coming soon.', 'info');
        }

        async function onAISuggest() {
            const panel = $('#rb-ai-suggest-panel');
            if (!panel) return;
            const chips = $('#rb-ai-suggest-chips');
            if (!chips) return;
            if (!panel.classList.contains('hidden') && chips.dataset.loaded === '1') {
                panel.classList.add('hidden');
                return;
            }
            panel.classList.remove('hidden');
            chips.innerHTML = '<span class="text-[11px] text-slate-500 italic"><i class="fas fa-spinner fa-spin mr-1"></i>Asking AI...</span>';
            try {
                const body = S.context.job_id ? { job_id: S.context.job_id }
                    : S.context.jd_text ? { jd_text: S.context.jd_text }
                    : { role_title: S.context.role_title || 'this role' };
                const res = await fetch('/api/v1/rubric/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify(body),
                });
                if (!res.ok) throw new Error('HTTP ' + res.status);
                const data = await res.json();
                const existing = new Set(S.skillList.map(s => s.name.toLowerCase()));
                const newSkills = [];
                (data.categories || []).forEach(cat => {
                    (cat.skills || []).forEach(sk => {
                        if (!existing.has(sk.name.toLowerCase())) {
                            newSkills.push({ ...sk, category: cat.name });
                        }
                    });
                });
                if (!newSkills.length) {
                    chips.innerHTML = '<span class="text-[11px] text-slate-500 italic">No new suggestions -- your rubric covers it all.</span>';
                    return;
                }
                chips.dataset.loaded = '1';
                chips.innerHTML = newSkills.slice(0, 12).map((s, i) => `
                    <button class="rb-ai-chip inline-flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-bold text-indigo-700 bg-white border border-indigo-200 rounded-full hover:bg-indigo-100 transition-colors" data-suggest-idx="${i}">
                        <i class="fas fa-plus text-[9px]"></i> ${esc(s.name)} <span class="text-indigo-400 text-[9px]">\u00b7${esc(s.category)}</span>
                    </button>
                `).join('') + (newSkills.length > 12 ? `<span class="text-[10px] text-slate-500 self-center">+${newSkills.length - 12} more</span>` : '');
                chips._newSkills = newSkills;
                chips.querySelectorAll('.rb-ai-chip').forEach(chip => {
                    chip.addEventListener('click', () => {
                        const idx = parseInt(chip.dataset.suggestIdx, 10);
                        const s = newSkills[idx];
                        S.skillList.push({
                            id: 'sk_' + Math.random().toString(36).slice(2, 10),
                            name: s.name, weight: 5, category: s.category,
                            is_required: false, keywords: s.keywords || [],
                        });
                        chip.remove();
                        normalizeWeights();
                        renderEditor();
                        scheduleAutoSave();
                        toast(`Added "${s.name}"`);
                    });
                });
            } catch (e) {
                chips.innerHTML = `<span class="text-[11px] text-rose-500 italic">AI unavailable: ${esc(e.message)}</span>`;
            }
        }

        function onPublishClick() {
            if (!S.skillList.length) {
                toast('Add at least one skill first', 'error');
                return;
            }
            const total = _getTotalWeight();
            const catCount = _getCategoryCount();
            const stats = $('#rb-publish-stats');
            if (stats) {
                stats.innerHTML = `
                    <div class="flex items-center justify-between text-xs">
                        <span class="text-slate-500">Skills</span>
                        <span class="font-bold text-slate-700">${S.skillList.length}</span>
                    </div>
                    <div class="flex items-center justify-between text-xs">
                        <span class="text-slate-500">Categories</span>
                        <span class="font-bold text-slate-700">${catCount}</span>
                    </div>
                    <div class="flex items-center justify-between text-xs">
                        <span class="text-slate-500">Total weight</span>
                        <span class="font-bold ${Math.abs(total - 100) <= 1 ? 'text-emerald-600' : 'text-amber-600'}">${total}%</span>
                    </div>`;
            }
            const modal = $('#rb-publish-modal');
            if (modal) modal.style.display = '';
        }

        async function onPublishConfirm() {
            if (!S.context.job_id) {
                toast('Select a job first before publishing', 'error');
                return;
            }
            const total = _getTotalWeight();
            if (total < 90 || total > 110) {
                toast('Weights should sum to ~100% before publishing (currently ' + total + '%)', 'warning');
            }
            const btn = $('#rb-publish-confirm-btn');
            if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i> Publishing...'; }
            try {
                await adminSaveDraft(true);
                toast('Rubric published!');
                const modal = $('#rb-publish-modal');
                if (modal) modal.style.display = 'none';
                goToStep('success');
                const subtitle = $('#rb-success-subtitle');
                if (subtitle) subtitle.textContent = `${S.skillList.length} skills across ${_getCategoryCount()} categories -- ready to score interviews.`;
                if (S.context.job_id) {
                    const testBtn = $('#rb-success-test-btn');
                    if (testBtn) testBtn.href = `/recruiter/scoring-preview?job_id=${S.context.job_id}`;
                }
                const editBtn = $('#rb-success-edit-btn');
                if (editBtn) editBtn.onclick = () => goToStep(4);
            } catch (e) {
                toast('Publish failed: ' + e.message, 'error');
            } finally {
                if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fas fa-rocket mr-1"></i> Publish'; }
            }
        }

        let saveTimer = null;
        function scheduleAutoSave() {
            clearTimeout(saveTimer);
            saveTimer = setTimeout(() => adminSaveDraft(), 1200);
        }

        async function adminSaveDraft(publish = false) {
            if (!S.context.job_id) {
                markSaved();
                return;
            }
            if (S.saving) return;
            S.saving = true;
            const indicator = $('#rb-save-indicator');
            if (indicator) indicator.innerHTML = '<i class="fas fa-spinner fa-spin text-amber-500"></i> Saving';
            try {
                let draftId = S.draftId;
                if (!draftId) {
                    const createRes = await fetch(`/api/v1/rubric/drafts/${S.context.job_id}`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        credentials: 'include',
                        body: JSON.stringify({ name: S.context.role_title || 'Rubric' }),
                    });
                    if (!createRes.ok) throw new Error('Cannot create draft');
                    const created = await createRes.json();
                    draftId = created.id;
                    S.draftId = draftId;
                }
                const grouped = {};
                S.skillList.forEach(sk => {
                    if (!grouped[sk.category]) grouped[sk.category] = [];
                    grouped[sk.category].push(sk);
                });
                const categories = Object.entries(grouped).map(([name, skills]) => {
                    const catWeight = skills.reduce((s, x) => s + x.weight, 0);
                    return {
                        name,
                        description: '',
                        weight: catWeight,
                        subcategories: [{
                            name: 'General',
                            description: '',
                            weight: catWeight,
                            skills: skills.map(sk => ({
                                name: sk.name,
                                description: '',
                                weight: sk.weight,
                                is_required: sk.is_required,
                                keywords: sk.keywords || [],
                                levels: { junior: [], mid: [], senior: [] },
                            })),
                        }],
                    };
                });
                const rubricJson = {
                    job_id: S.context.job_id,
                    version: 1,
                    seniority: 'mid',
                    categories,
                };
                const putRes = await fetch(`/api/v1/rubric/drafts/${draftId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({ rubric_json: rubricJson }),
                });
                if (!putRes.ok) throw new Error('Cannot save draft');
                if (publish) {
                    const pubRes = await fetch(`/api/v1/rubric/drafts/${draftId}/publish`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        credentials: 'include',
                        body: JSON.stringify({ seniority: 'senior' }),
                    });
                    if (!pubRes.ok) throw new Error('Cannot publish');
                }
                markSaved();
            } catch (e) {
                const indicator = $('#rb-save-indicator');
                if (indicator) indicator.innerHTML = '<i class="fas fa-exclamation-circle text-rose-500"></i> ' + esc(e.message);
                throw e;
            } finally {
                S.saving = false;
            }
        }

        function markSaved() {
            S.lastSavedAt = new Date();
            const indicator = $('#rb-save-indicator');
            if (indicator) indicator.innerHTML = '<i class="fas fa-check-circle text-emerald-500"></i> Saved';
        }

        function toggleAdvanced() {
            S.advancedOpen = !S.advancedOpen;
            const panel = $('#rb-advanced-panel');
            if (panel) panel.classList.toggle('hidden', !S.advancedOpen);
            const chev = $('#rb-advanced-chevron');
            if (chev) chev.style.transform = S.advancedOpen ? 'rotate(180deg)' : '';
            if (S.advancedOpen) renderAdvanced();
        }

        function switchAdvancedTab(tab) {
            S.advancedTab = tab;
            $$('.rb-adv-tab').forEach(t => {
                const active = t.dataset.advTab === tab;
                t.classList.toggle('text-indigo-600', active);
                t.classList.toggle('border-indigo-500', active);
                t.classList.toggle('text-slate-500', !active);
                t.classList.toggle('border-transparent', !active);
            });
            renderAdvanced();
        }

        async function renderAdvanced() {
            const c = $('#rb-advanced-content');
            if (!c) return;
            c.innerHTML = '<p class="text-xs text-slate-400 text-center py-6">Loading...</p>';
            try {
                if (S.advancedTab === 'categories') {
                    c.innerHTML = renderAdvancedCategories();
                } else if (S.advancedTab === 'versions') {
                    if (!S.context.job_id) { c.innerHTML = '<p class="text-xs text-slate-400 text-center py-6">Versions require a job context.</p>'; return; }
                    const res = await fetch(`/api/v1/rubric/jobs/${S.context.job_id}/versions`, { credentials: 'include' });
                    if (!res.ok) throw new Error('HTTP ' + res.status);
                    const versions = await res.json();
                    const list = versions.versions || versions || [];
                    c.innerHTML = list.length
                        ? list.map(v => `
                            <div class="p-2.5 mb-1.5 border border-slate-100 rounded-lg flex items-center justify-between">
                                <div>
                                    <div class="text-sm font-bold text-slate-800">v${v.version || v.id}</div>
                                    <div class="text-[10px] text-slate-400">${esc(v.published_at || v.created_at || '')}</div>
                                </div>
                                <span class="text-[10px] font-bold text-slate-500">${v.skill_count || ''} skills</span>
                            </div>`).join('')
                        : '<p class="text-xs text-slate-400 text-center py-6">No versions yet.</p>';
                } else if (S.advancedTab === 'drafts') {
                    const res = await fetch('/api/v1/rubric/drafts', { credentials: 'include' });
                    if (!res.ok) throw new Error('HTTP ' + res.status);
                    const drafts = await res.json();
                    const list = drafts.drafts || drafts || [];
                    c.innerHTML = list.length
                        ? list.map(d => `
                            <div class="p-2.5 mb-1.5 border border-slate-100 rounded-lg flex items-center justify-between">
                                <div>
                                    <div class="text-sm font-bold text-slate-800">${esc(d.name)}</div>
                                    <div class="text-[10px] text-slate-400">${esc(d.updated_at || '')}</div>
                                </div>
                                <span class="text-[10px] font-bold text-slate-500">${d.status || 'draft'}</span>
                            </div>`).join('')
                        : '<p class="text-xs text-slate-400 text-center py-6">No drafts.</p>';
                } else if (S.advancedTab === 'ab') {
                    const res = await fetch('/api/v1/rubric/ab-test/list', { credentials: 'include' });
                    if (!res.ok) throw new Error('HTTP ' + res.status);
                    const exps = await res.json();
                    const list = exps.experiments || exps || [];
                    c.innerHTML = list.length
                        ? list.map(x => `
                            <div class="p-2.5 mb-1.5 border border-slate-100 rounded-lg flex items-center justify-between">
                                <div>
                                    <div class="text-sm font-bold text-slate-800">${esc(x.name || ('Experiment #' + x.id))}</div>
                                    <div class="text-[10px] text-slate-400">${esc(x.status || '')}</div>
                                </div>
                            </div>`).join('')
                        : '<p class="text-xs text-slate-400 text-center py-6">No A/B tests yet.</p>';
                }
            } catch (e) {
                c.innerHTML = `<p class="text-xs text-rose-500 text-center py-6">Error: ${esc(e.message)}</p>`;
            }
        }

        function renderAdvancedCategories() {
            if (!S.skillList.length) {
                return '<p class="text-xs text-slate-400 text-center py-6">No skills yet. Switch to the simple editor and add skills first.</p>';
            }
            const grouped = {};
            S.skillList.forEach(sk => {
                if (!grouped[sk.category]) grouped[sk.category] = [];
                grouped[sk.category].push(sk);
            });
            return Object.entries(grouped).map(([cat, skills]) => {
                const catTotal = skills.reduce((s, x) => s + x.weight, 0);
                return `
                <div class="mb-3 border border-slate-100 rounded-lg p-2.5">
                    <div class="flex items-center justify-between mb-1.5">
                        <span class="text-sm font-black text-slate-800">${esc(cat)}</span>
                        <span class="text-xs font-mono text-slate-500">${catTotal}%</span>
                    </div>
                    ${skills.map(sk => `
                        <div class="text-xs text-slate-600 pl-2 py-0.5">\u2022 ${esc(sk.name)} <span class="text-slate-400">(${sk.weight}%)</span></div>
                    `).join('')}
                </div>`;
            }).join('');
        }

        function toast(msg, type = 'success') {
            const t = $('#rb-toast');
            if (!t) return;
            const icon = $('#rb-toast-icon');
            const msgEl = $('#rb-toast-msg');
            if (msgEl) msgEl.textContent = msg;
            if (icon) {
                icon.className = type === 'error' ? 'fas fa-exclamation-circle text-rose-400'
                    : type === 'info' ? 'fas fa-info-circle text-sky-400'
                    : 'fas fa-check-circle text-emerald-400';
            }
            t.style.display = '';
            clearTimeout(S._toastTimer);
            S._toastTimer = setTimeout(() => { t.style.display = 'none'; }, 2500);
        }

        function bindShortcuts() {
            const isMac = navigator.platform.toUpperCase().includes('MAC');
            document.addEventListener('keydown', (e) => {
                if (e.target.matches('input, textarea, select, [contenteditable]')) {
                    if (e.key === 'Escape') e.target.blur();
                    return;
                }
                const mod = isMac ? e.metaKey : e.ctrlKey;
                if (mod && e.key === 'Enter' && S.step === 4) { e.preventDefault(); onPublishClick(); return; }
                if (mod && (e.key === 's' || e.key === 'S')) { e.preventDefault(); adminSaveDraft().then(() => toast('Saved')); return; }
                if (e.key === 'Escape') {
                    const publishModal = $('#rb-publish-modal');
                    if (publishModal && publishModal.style.display !== 'none') { publishModal.style.display = 'none'; }
                    const addForm = $('#rb-add-skill-form');
                    if (addForm && !addForm.classList.contains('hidden')) { hideAddSkillForm(); }
                    const aiPanel = $('#rb-ai-suggest-panel');
                    if (aiPanel && !aiPanel.classList.contains('hidden')) { aiPanel.classList.add('hidden'); }
                }
            });
        }

        function bindEditorStep() {
            const backBtn = $('#rb-editor-back-btn');
            if (backBtn) backBtn.addEventListener('click', () => { goToStep(S.generatedRubric ? 3 : 1); });
            const autoBal = $('#rb-auto-balance');
            if (autoBal) autoBal.addEventListener('change', e => { S.autoBalance = e.target.checked; });
            const addBtn = $('#rb-add-skill-btn');
            if (addBtn) addBtn.addEventListener('click', showAddSkillForm);
            const suggestBtn = $('#rb-add-suggest-btn');
            if (suggestBtn) suggestBtn.addEventListener('click', onBrowseByCategory);
            const aiBtn = $('#rb-ai-suggest-btn');
            if (aiBtn) aiBtn.addEventListener('click', onAISuggest);
            const pubBtn = $('#rb-publish-btn');
            if (pubBtn) pubBtn.addEventListener('click', onPublishClick);
            const advToggle = $('#rb-advanced-toggle');
            if (advToggle) advToggle.addEventListener('click', toggleAdvanced);
            $$('.rb-adv-tab').forEach(t => t.addEventListener('click', () => switchAdvancedTab(t.dataset.advTab)));
            const pubCancel = $('#rb-publish-cancel-btn');
            if (pubCancel) pubCancel.addEventListener('click', () => { const m = $('#rb-publish-modal'); if (m) m.style.display = 'none'; });
            const pubDraft = $('#rb-publish-draft-btn');
            if (pubDraft) pubDraft.addEventListener('click', () => adminSaveDraft().then(() => { const m = $('#rb-publish-modal'); if (m) m.style.display = 'none'; toast('Saved as draft'); }));
            const pubConfirm = $('#rb-publish-confirm-btn');
            if (pubConfirm) pubConfirm.addEventListener('click', onPublishConfirm);
            const closeBtn = $('#rb-close-btn');
            if (closeBtn) closeBtn.addEventListener('click', () => { window.location.href = '/admin/rubrics'; });
            const newSkillCancel = $('#rb-new-skill-cancel');
            if (newSkillCancel) newSkillCancel.addEventListener('click', hideAddSkillForm);
            const newSkillSave = $('#rb-new-skill-save');
            if (newSkillSave) newSkillSave.addEventListener('click', submitAddSkill);
            const newSkillName = $('#rb-new-skill-name');
            if (newSkillName) {
                newSkillName.addEventListener('keydown', e => {
                    if (e.key === 'Enter') submitAddSkill();
                    else if (e.key === 'Escape') hideAddSkillForm();
                });
            }
            const newSkillWeight = $('#rb-new-skill-weight');
            if (newSkillWeight) {
                newSkillWeight.addEventListener('input', e => {
                    const val = $('#rb-new-skill-weight-val');
                    if (val) val.textContent = e.target.value;
                });
            }
            const aiClose = $('#rb-ai-suggest-close');
            if (aiClose) aiClose.addEventListener('click', () => { const p = $('#rb-ai-suggest-panel'); if (p) p.classList.add('hidden'); });
        }

        // Init admin
        bindContextStep();
        bindPreviewStep();
        bindEditorStep();
        bindShortcuts();
        updateStepIndicator();
    }
}

// ============================================================================
// BACKWARD-COMPATIBLE ALIASES
// ============================================================================

// SkillTreeEditor (used by recruiter/skill-tree.html)
window.SkillTreeEditor = function(container, config) {
    const el = typeof container === 'string' ? document.querySelector(container) : container;
    const options = Object.assign({ mode: 'view' }, config);
    return new RubricBuilder(el, options);
};

// SkillTreeModal (used by recruiter/skill-tree-list.html)
window.SkillTreeModal = {
    open() {
        // Create modal instance if needed
        if (!RubricBuilder._modalInstance) {
            new RubricBuilder(document.body, { mode: 'modal' });
        } else {
            const modal = document.getElementById('skill-tree-modal');
            if (modal) modal.classList.remove('hidden');
            const inst = RubricBuilder._modalInstance;
            inst._modalStep = 1;
            inst._modalState = {
                jobId: null, selectedCategories: [], jobTitle: '',
                jobDescription: '', templateId: null, rubric: null,
            };
            inst._modalBindNav();
            inst._modalRenderStep();
        }
    },
    close() {
        const modal = document.getElementById('skill-tree-modal');
        if (modal) modal.classList.add('hidden');
    },
    edit() { this.open(); },
    delete(id) {
        if (!confirm('Delete this skill tree?')) return;
        fetch(`/api/v1/recruiter/skill-trees/${id}`, { method: 'DELETE' })
            .then(r => r.ok ? (window.loadSkillTrees && window.loadSkillTrees()) : alert('Delete failed'));
    },
};

// Admin auto-init
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('rb-step-indicator')) {
        new RubricBuilder(document.body, { mode: 'admin' });
    }
});
