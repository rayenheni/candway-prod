const wizardState = {
    jobId: null,
    currentStep: 1,
    completedSteps: [],
    isPublished: false,
    isDirty: false,
    stepData: {
        1: { title: '', category_id: null, employment_type: 'full-time', workplace_type: 'hybrid', location: '', num_openings: 1, hiring_manager_id: null, salary_min: null, salary_max: null, salary_currency: 'USD', internal_reference: '' },
        2: { items: [
            { question_key: 'responsibilities', question: window.t('recruiter.job_wizard.step2.responsibilities_q'), answer: '' },
            { question_key: 'outcomes_90_days', question: window.t('recruiter.job_wizard.step2.outcomes_90_q'), answer: '' },
            { question_key: 'problems_solved', question: window.t('recruiter.job_wizard.step2.problems_q'), answer: '' },
            { question_key: 'success_criteria', question: window.t('recruiter.job_wizard.step2.success_q'), answer: '' }
        ], role_summary: '' },
        3: { skills: [] },
        4: { categories: [
            { name: 'Technical Skills', weight: 50, sort_order: 0 },
            { name: 'Problem Solving', weight: 20, sort_order: 1 },
            { name: 'Communication', weight: 15, sort_order: 2 },
            { name: 'Portfolio / Evidence', weight: 15, sort_order: 3 }
        ], ai_config: null },
        5: { screening_questions: [], pipeline_stages: [
            { name: window.t('recruiter.job_wizard.step5.applied'), slug: 'applied', sort_order: 0, color: '#6366f1', icon: 'file-text' },
            { name: window.t('recruiter.job_wizard.step5.screening'), slug: 'screening', sort_order: 1, color: '#f59e0b', icon: 'search' },
            { name: window.t('recruiter.job_wizard.step5.interview'), slug: 'interview', sort_order: 2, color: '#3b82f6', icon: 'users' },
            { name: window.t('recruiter.job_wizard.step5.offer'), slug: 'offer', sort_order: 3, color: '#10b981', icon: 'check-circle' },
            { name: window.t('recruiter.job_wizard.step5.hired'), slug: 'hired', sort_order: 4, color: '#059669', icon: 'user-check' }
        ] }
    }
};

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
}

function showToast(message, type) {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = 'toast ' + (type || 'success');
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(function () { toast.remove(); }, 3500);
}

function showSpinner(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.classList.add('wizard-loading');
    const spinner = document.createElement('div');
    spinner.className = 'wizard-spinner';
    spinner.innerHTML = '<i class="fas fa-circle-notch fa-spin text-indigo-500 text-2xl"></i>';
    container.appendChild(spinner);
}

function hideSpinner(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.classList.remove('wizard-loading');
    const existing = container.querySelector('.wizard-spinner');
    if (existing) existing.remove();
}

function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : null;
}

async function fetchWizardData() {
    try {
        var catSelect = document.getElementById('jw-category');
        var catLoading = document.getElementById('jw-category-loading');
        if (catLoading) catLoading.classList.remove('hidden');
        var cats = await window.fetchAPI('/recruiter/jobs/wizard/categories', { method: 'GET' });
        if (catLoading) catLoading.classList.add('hidden');
        if (cats && Array.isArray(cats) && catSelect) {
            cats.forEach(function (c) {
                var opt = document.createElement('option');
                opt.value = c.id;
                opt.textContent = c.name;
                catSelect.appendChild(opt);
            });
        }
    } catch (e) {
        console.warn('Failed to load categories:', e);
    }

    try {
        var hmSelect = document.getElementById('jw-hiring-manager');
        var rlLoading = document.getElementById('jw-recruiter-loading');
        if (rlLoading) rlLoading.classList.remove('hidden');
        var recruiters = await window.fetchAPI('/recruiter/jobs/wizard/recruiters', { method: 'GET' });
        if (rlLoading) rlLoading.classList.add('hidden');
        if (recruiters && Array.isArray(recruiters) && hmSelect) {
            recruiters.forEach(function (r) {
                var opt = document.createElement('option');
                opt.value = r.id;
                opt.textContent = r.name + (r.email ? ' (' + r.email + ')' : '');
                hmSelect.appendChild(opt);
            });
        }
    } catch (e) {
        console.warn('Failed to load recruiters:', e);
    }
}

async function initWizard() {
    const params = new URLSearchParams(window.location.search);
    const editId = params.get('edit');
    if (editId) {
        await resumeWizard(editId);
        return;
    }
    const savedState = sessionStorage.getItem('wizardState');
    if (savedState) {
        try {
            const parsed = JSON.parse(savedState);
            wizardState.jobId = parsed.jobId;
            wizardState.currentStep = parsed.currentStep || 1;
            wizardState.completedSteps = parsed.completedSteps || [];
            wizardState.isPublished = parsed.isPublished || false;
            if (parsed.stepData) {
                Object.keys(parsed.stepData).forEach(function (k) {
                    if (wizardState.stepData[k]) {
                        wizardState.stepData[k] = parsed.stepData[k];
                    }
                });
            }
        } catch (e) {
            sessionStorage.removeItem('wizardState');
        }
    }
    renderStepIndicator();
    goToStep(wizardState.currentStep);
    fetchWizardData();
}

async function startWizard() {
    const valid = validateStep(1);
    if (!valid.valid) {
        showToast(valid.errors[0], 'error');
        return;
    }
    showSpinner('step-1');
    try {
        const data = await window.fetchAPI('/recruiter/jobs/wizard/start', {
            method: 'POST',
            body: JSON.stringify({
                title: wizardState.stepData[1].title,
                category_id: wizardState.stepData[1].category_id,
                employment_type: wizardState.stepData[1].employment_type,
                workplace_type: wizardState.stepData[1].workplace_type,
                location: wizardState.stepData[1].location,
                num_openings: wizardState.stepData[1].num_openings,
                hiring_manager_id: wizardState.stepData[1].hiring_manager_id,
                salary_min: wizardState.stepData[1].salary_min,
                salary_max: wizardState.stepData[1].salary_max,
                salary_currency: wizardState.stepData[1].salary_currency,
                internal_reference: wizardState.stepData[1].internal_reference
            }),
            headers: { 'X-CSRF-Token': getCsrfToken() }
        });
        wizardState.jobId = data.job_id;
        wizardState.completedSteps.push(1);
        wizardState.isDirty = true;
        persistState();
        goToStep(2);
    } catch (e) {
        showToast(window.t('recruiter.job_wizard.error_start') + ': ' + e.message, 'error');
    } finally {
        hideSpinner('step-1');
    }
}

function renderStepIndicator() {
    for (var i = 1; i <= 6; i++) {
        var dot = document.getElementById('sd-' + i);
        if (dot) {
            dot.onclick = (function (idx) {
                return function () {
                    if (wizardState.completedSteps.indexOf(idx - 1) !== -1 || wizardState.completedSteps.indexOf(idx) !== -1) {
                        goToStep(idx);
                    }
                };
            })(i);
        }
    }
    updateStepIndicator();
}

function updateStepIndicator() {
    for (var i = 1; i <= 6; i++) {
        var dot = document.getElementById('sd-' + i);
        if (!dot) continue;
        var label = document.getElementById('step-label-' + i);
        dot.classList.remove('active', 'completed', 'inactive');
        if (i === wizardState.currentStep) {
            dot.classList.add('active');
            if (label) { label.className = 'text-[10px] font-bold text-indigo-600 uppercase tracking-wider'; }
        } else if (wizardState.completedSteps.indexOf(i) !== -1 || (i < wizardState.currentStep && wizardState.isDirty)) {
            dot.classList.add('completed');
            if (label) { label.className = 'text-[10px] font-bold text-indigo-400 uppercase tracking-wider'; }
        } else {
            dot.classList.add('inactive');
            if (label) { label.className = 'text-[10px] font-bold text-slate-400 uppercase tracking-wider'; }
        }
        dot.textContent = (wizardState.completedSteps.indexOf(i) !== -1) ? '\u2713' : i;
    }
    var connectors = document.querySelectorAll('.step-connector');
    connectors.forEach(function (c, idx) {
        if (wizardState.completedSteps.indexOf(idx + 1) !== -1) {
            c.style.background = '#6366f1';
        } else {
            c.style.background = '#e2e8f0';
        }
    });
}

function syncStep1Inputs() {
    var d = wizardState.stepData[1];
    var el = function (id) { return document.getElementById(id); };
    d.title = (el('jw-job-title') && el('jw-job-title').value) || '';
    d.category_id = (el('jw-category') && el('jw-category').value) ? parseInt(el('jw-category').value) : null;
    d.employment_type = (el('jw-employment-type') && el('jw-employment-type').value) || 'full-time';
    d.workplace_type = (el('jw-workplace') && el('jw-workplace').value) || 'hybrid';
    d.location = (el('jw-location') && el('jw-location').value) || '';
    d.num_openings = parseInt((el('jw-openings') && el('jw-openings').value) || 1);
    d.hiring_manager_id = (el('jw-hiring-manager') && el('jw-hiring-manager').value) ? parseInt(el('jw-hiring-manager').value) : null;
    d.salary_min = (el('jw-salary-min') && el('jw-salary-min').value) ? parseInt(el('jw-salary-min').value) : null;
    d.salary_max = (el('jw-salary-max') && el('jw-salary-max').value) ? parseInt(el('jw-salary-max').value) : null;
    d.salary_currency = (el('jw-salary-currency') && el('jw-salary-currency').value) || 'USD';
    d.internal_reference = (el('jw-internal-ref') && el('jw-internal-ref').value) || '';
}

function populateStep1() {
    var d = wizardState.stepData[1];
    var el = function (id) { return document.getElementById(id); };
    if (el('jw-job-title')) el('jw-job-title').value = d.title || '';
    if (el('jw-category')) el('jw-category').value = d.category_id || '';
    if (el('jw-employment-type')) el('jw-employment-type').value = d.employment_type || 'full-time';
    if (el('jw-workplace')) el('jw-workplace').value = d.workplace_type || 'hybrid';
    if (el('jw-location')) el('jw-location').value = d.location || '';
    if (el('jw-openings')) el('jw-openings').value = d.num_openings || 1;
    if (el('jw-hiring-manager')) el('jw-hiring-manager').value = d.hiring_manager_id || '';
    if (el('jw-salary-min')) el('jw-salary-min').value = d.salary_min || '';
    if (el('jw-salary-max')) el('jw-salary-max').value = d.salary_max || '';
    if (el('jw-salary-currency')) el('jw-salary-currency').value = d.salary_currency || 'USD';
    if (el('jw-internal-ref')) el('jw-internal-ref').value = d.internal_reference || '';
}

function syncStep2Inputs() {
    var d = wizardState.stepData[2];
    var el = function (id) { return document.getElementById(id); };
    if (el('jw-q-responsible')) d.items[0].answer = el('jw-q-responsible').value;
    if (el('jw-q-outcomes')) d.items[1].answer = el('jw-q-outcomes').value;
    if (el('jw-q-problems')) d.items[2].answer = el('jw-q-problems').value;
    if (el('jw-q-success')) d.items[3].answer = el('jw-q-success').value;
    if (el('role-summary')) d.role_summary = el('role-summary').value;
}

function syncStep4Inputs() {
    var el = function (id) { return document.getElementById(id); };
    wizardState.stepData[4].ai_config = {
        ai_scoring_enabled: (el('jw-ai-scoring') && el('jw-ai-scoring').checked) || false,
        minimum_recommended_score: parseFloat((el('jw-passing-threshold') && el('jw-passing-threshold').value) || 70),
        auto_shortlist_threshold: parseFloat((el('jw-top-cutoff') && el('jw-top-cutoff').value) || 85),
        evidence_based_scoring: (el('jw-evidence-mode') ? el('jw-evidence-mode').value !== 'relaxed' : true),
        explain_ai_decisions: true,
        prioritize_verified_skills: true,
    };
}

function goToStep(n) {
    if (n < 1 || n > 6) return;

    // Sync current step inputs before leaving
    if (wizardState.currentStep === 1) syncStep1Inputs();
    else if (wizardState.currentStep === 2) syncStep2Inputs();
    else if (wizardState.currentStep === 4) syncStep4Inputs();

    if (wizardState.jobId && n > 1 && wizardState.completedSteps.indexOf(n) === -1 && wizardState.completedSteps.indexOf(n - 1) === -1 && wizardState.currentStep !== n) {
        showToast(window.t('recruiter.job_wizard.complete_previous'), 'error');
        return;
    }
    for (var i = 1; i <= 6; i++) {
        var content = document.getElementById('step-' + i);
        if (content) content.classList.add('hidden');
    }
    wizardState.currentStep = n;
    var target = document.getElementById('step-' + n);
    if (target) {
        target.classList.remove('hidden');
        if (n === 1) populateStep1();
        if (n === 6) renderStep6Preview();
    }
    updateStepIndicator();
    updateNavButtons();
    if (n === 3 && wizardState.stepData[3].skills.length > 0) {
        updateWeightBars();
    }
    if (n === 4) {
        renderCategories();
    }
    if (n === 5 && wizardState.stepData[5].screening_questions.length === 0) {
        var container = document.getElementById('jw-screening-questions');
        if (container && container.children.length === 0) addScreeningQuestion();
    }
    if (wizardState.jobId && n > 1) {
        callAIDetection();
    }
}

function updateNavButtons() {
    var prevBtn = document.getElementById('btn-prev-step');
    var nextBtn = document.getElementById('btn-next-step');
    if (prevBtn) {
        prevBtn.style.display = wizardState.currentStep > 1 ? '' : 'none';
        prevBtn.disabled = wizardState.currentStep <= 1;
    }
    if (nextBtn) {
        if (wizardState.currentStep === 6) {
            nextBtn.style.display = 'none';
        } else {
            nextBtn.style.display = '';
            nextBtn.textContent = window.t('recruiter.job_wizard.nav.next');
        }
    }
    var publishBtn = document.getElementById('btn-publish');
    if (publishBtn) {
        publishBtn.style.display = wizardState.currentStep === 6 ? '' : 'none';
    }
}

async function saveStep(n) {
    var valid = validateStep(n);
    if (!valid.valid) {
        showToast(valid.errors[0], 'error');
        return;
    }
    if (!wizardState.jobId) {
        await startWizard();
        return;
    }
    showSpinner('step-' + n);
    try {
        var endpoint = '/recruiter/jobs/wizard/' + wizardState.jobId + '/step' + n;
        var body = {};
        if (n === 1) {
            body = {
                title: wizardState.stepData[1].title,
                category_id: wizardState.stepData[1].category_id,
                employment_type: wizardState.stepData[1].employment_type,
                workplace_type: wizardState.stepData[1].workplace_type,
                location: wizardState.stepData[1].location,
                num_openings: wizardState.stepData[1].num_openings,
                hiring_manager_id: wizardState.stepData[1].hiring_manager_id,
                salary_min: wizardState.stepData[1].salary_min,
                salary_max: wizardState.stepData[1].salary_max,
                salary_currency: wizardState.stepData[1].salary_currency,
                internal_reference: wizardState.stepData[1].internal_reference
            };
        } else if (n === 2) {
            body = {
                items: wizardState.stepData[2].items,
                role_summary: wizardState.stepData[2].role_summary
            };
        } else if (n === 3) {
            body = {
                skills: wizardState.stepData[3].skills.map(function (s) {
                    return {
                        skill_name: s.name,
                        required_level: s.level || 'intermediate',
                        weight: parseInt(s.weight) || 1,
                        is_mandatory: s.mandatory !== undefined ? s.mandatory : true,
                        notes: s.notes || null,
                        sort_order: 0
                    };
                }),
                skill_tree_id: wizardState.stepData[3].skillTreeId || null
            };
        } else if (n === 4) {
            body = {
                categories: wizardState.stepData[4].categories,
                ai_config: wizardState.stepData[4].ai_config
            };
        } else if (n === 5) {
            body = {
                screening_questions: wizardState.stepData[5].screening_questions.map(function (q) {
                    return {
                        question: q.question,
                        type: q.type || 'yes_no',
                        is_required: q.required !== undefined ? q.required : true,
                        sort_order: 0
                    };
                }),
                pipeline_stages: wizardState.stepData[5].pipeline_stages.map(function (s) {
                    return {
                        name: s.name,
                        slug: s.slug || s.name.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, ''),
                        sort_order: s.sort_order || 0,
                        color: s.color || '#6366f1',
                        icon: s.icon || 'circle'
                    };
                })
            };
        }
        await window.fetchAPI(endpoint, {
            method: 'PATCH',
            body: JSON.stringify(body),
            headers: { 'X-CSRF-Token': getCsrfToken() }
        });
        if (wizardState.completedSteps.indexOf(n) === -1) {
            wizardState.completedSteps.push(n);
        }
        wizardState.isDirty = true;
        persistState();
        updateStepIndicator();
        showToast(window.t('recruiter.job_wizard.step_saved'), 'success');
        if (n < 5) {
            setTimeout(function () { goToStep(n + 1); }, 500);
        } else if (n === 5) {
            setTimeout(function () { goToStep(6); }, 500);
        }
    } catch (e) {
        showToast(window.t('recruiter.job_wizard.errors.save_failed') + ': ' + e.message, 'error');
    } finally {
        hideSpinner('step-' + n);
    }
}

function addSkill(name, level, weight, mandatory, notes) {
    var skill = {
        name: name || '',
        level: level || 'intermediate',
        weight: weight || 1,
        mandatory: mandatory !== undefined ? mandatory : true,
        notes: notes || ''
    };
    wizardState.stepData[3].skills.push(skill);
    renderSkillList();
    updateWeightBars();
    wizardState.isDirty = true;
}

function removeSkill(index) {
    wizardState.stepData[3].skills.splice(index, 1);
    renderSkillList();
    updateWeightBars();
    wizardState.isDirty = true;
}

function updateSkill(index, field, value) {
    if (index < 0 || index >= wizardState.stepData[3].skills.length) return;
    wizardState.stepData[3].skills[index][field] = value;
    updateWeightBars();
    wizardState.isDirty = true;
}

function renderSkillList() {
    var container = document.getElementById('jw-skills-list');
    if (!container) return;
    var skills = wizardState.stepData[3].skills;
    if (skills.length === 0) {
        container.innerHTML = '<div class="text-slate-400 text-sm py-8 text-center">' + window.t('recruiter.job_wizard.step3.no_skills') + '</div>';
        return;
    }
    var html = '';
    for (var i = 0; i < skills.length; i++) {
        var s = skills[i];
        html += '<div class="skill-item" data-index="' + i + '">';
        html += '<div class="skill-item-header">';
        html += '<span class="skill-name">' + escapeHtml(s.name) + '</span>';
        html += '<button type="button" class="skill-remove" onclick="removeSkill(' + i + ')" aria-label="' + window.t('recruiter.job_wizard.remove_skill') + '"><i class="fas fa-times"></i></button>';
        html += '</div>';
        html += '<div class="skill-item-controls">';
        html += '<label>' + window.t('recruiter.job_wizard.step3.level') + ': <select onchange="updateSkill(' + i + ', \'level\', this.value)">';
        ['beginner', 'intermediate', 'advanced', 'expert'].forEach(function (lvl) {
            var sel = s.level === lvl ? ' selected' : '';
            html += '<option value="' + lvl + '"' + sel + '>' + window.t('recruiter.job_wizard.step3.' + lvl) + '</option>';
        });
        html += '</select></label>';
        html += '<label>' + window.t('recruiter.job_wizard.step3.weight') + ': <input type="number" min="1" max="100" value="' + s.weight + '" onchange="updateSkill(' + i + ', \'weight\', parseInt(this.value) || 1)"></label>';
        html += '<label class="skill-mandatory"><input type="checkbox" ' + (s.mandatory ? 'checked' : '') + ' onchange="updateSkill(' + i + ', \'mandatory\', this.checked)"> ' + window.t('recruiter.job_wizard.step3.mandatory') + '</label>';
        html += '</div>';
        if (s.notes) {
            html += '<div class="skill-notes">' + escapeHtml(s.notes) + '</div>';
        }
        html += '</div>';
    }
    container.innerHTML = html;
}

function updateWeightBars() {
    var container = document.getElementById('jw-weight-hint');
    if (!container) return;
    var skills = wizardState.stepData[3].skills;
    var total = skills.reduce(function (sum, s) { return sum + (parseInt(s.weight) || 0); }, 0);
    if (total === 0) {
        container.innerHTML = '<div class="text-xs text-slate-400">' + window.t('recruiter.job_wizard.add_skills_weight') + '</div>';
        return;
    }
    var html = '<div class="weight-bars-container">';
    skills.forEach(function (s, i) {
        var pct = Math.round((parseInt(s.weight) || 0) / total * 100);
        var hue = (i * 37) % 360;
        html += '<div class="weight-bar-row">';
        html += '<span class="weight-bar-label" title="' + escapeHtml(s.name) + '">' + escapeHtml(s.name) + '</span>';
        html += '<div class="weight-bar-track">';
        html += '<div class="weight-bar-fill" style="width:' + pct + '%;background-color:hsl(' + hue + ',70%,60%)"></div>';
        html += '</div>';
        html += '<span class="weight-bar-pct">' + pct + '%</span>';
        html += '</div>';
    });
    html += '</div>';
    html += '<div class="weight-total text-xs text-slate-400 mt-2">' + window.t('recruiter.job_wizard.step3.total_weight') + ': ' + total + '</div>';
    container.innerHTML = html;
}

function addPipelineStage() {
    var stages = wizardState.stepData[5].pipeline_stages;
    var order = stages.length;
    stages.push({
        name: '',
        slug: '',
        sort_order: order,
        color: '#6366f1',
        icon: 'circle'
    });
    renderPipelineStages();
    wizardState.isDirty = true;
}

function removePipelineStage(index) {
    wizardState.stepData[5].pipeline_stages.splice(index, 1);
    wizardState.stepData[5].pipeline_stages.forEach(function (s, i) { s.sort_order = i; });
    renderPipelineStages();
    wizardState.isDirty = true;
}

function updatePipelineStage(index, field, value) {
    if (index < 0 || index >= wizardState.stepData[5].pipeline_stages.length) return;
    wizardState.stepData[5].pipeline_stages[index][field] = value;
    if (field === 'name') {
        wizardState.stepData[5].pipeline_stages[index].slug = value.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
    }
    wizardState.isDirty = true;
}


function safePipelineColor(value) {
    return /^#[0-9A-Fa-f]{6}$/.test(String(value || ''))
        ? String(value)
        : '#6366f1';
}

function renderPipelineStages() {
    var container = document.getElementById('jw-pipeline-stages');
    if (!container) return;
    var stages = wizardState.stepData[5].pipeline_stages;
    var html = '';
    stages.forEach(function (stage, i) {
        html += '<div class="pipeline-stage-item" data-index="' + i + '">';
        var safeColor = safePipelineColor(stage.color);
        html += '<div class="pipeline-stage-color" style="background-color:' + safeColor + '"></div>';
        html += '<div class="pipeline-stage-fields">';
        html += '<input type="text" class="pipeline-stage-name" value="' + escapeHtml(stage.name) + '" placeholder="' + window.t('recruiter.job_wizard.step5.stage_name_placeholder') + '" onchange="updatePipelineStage(' + i + ', \'name\', this.value)">';
        html += '<input type="color" value="' + safeColor + '" onchange="updatePipelineStage(' + i + ', \'color\', this.value); renderPipelineStages()" title="' + window.t('recruiter.job_wizard.step5.color') + '">';
        html += '<select onchange="updatePipelineStage(' + i + ', \'icon\', this.value)">';
        ['file-text', 'search', 'users', 'check-circle', 'user-check', 'circle', 'star', 'clock', 'flag', 'thumbs-up'].forEach(function (ic) {
            var sel = stage.icon === ic ? ' selected' : '';
            html += '<option value="' + ic + '"' + sel + '><i class="fas fa-' + ic + '"></i> ' + ic + '</option>';
        });
        html += '</select>';
        html += '</div>';
        html += '<button type="button" class="pipeline-stage-remove" onclick="removePipelineStage(' + i + ')" aria-label="' + window.t('recruiter.job_wizard.remove_stage') + '"><i class="fas fa-trash-alt"></i></button>';
        html += '</div>';
    });
    html += '<button type="button" class="btn btn-sm btn-outline mt-2" onclick="addPipelineStage()">+ ' + window.t('recruiter.job_wizard.step5.add_stage') + '</button>';
    container.innerHTML = html;
}

function addScreeningQuestion() {
    wizardState.stepData[5].screening_questions.push({ question: '', type: 'yes_no', required: true });
    renderScreeningQuestions();
    wizardState.isDirty = true;
}

function removeScreeningQuestion(index) {
    wizardState.stepData[5].screening_questions.splice(index, 1);
    renderScreeningQuestions();
    wizardState.isDirty = true;
}

function updateScreeningQuestion(index, field, value) {
    if (index < 0 || index >= wizardState.stepData[5].screening_questions.length) return;
    wizardState.stepData[5].screening_questions[index][field] = value;
    wizardState.isDirty = true;
}

function renderScreeningQuestions() {
    var container = document.getElementById('jw-screening-questions');
    if (!container) return;
    var questions = wizardState.stepData[5].screening_questions;
    if (questions.length === 0) {
        container.innerHTML = '<div class="text-slate-400 text-sm py-4">' + window.t('recruiter.job_wizard.step5.no_questions') + '</div>';
        return;
    }
    var html = '';
    questions.forEach(function (q, i) {
        html += '<div class="screening-question-item" data-index="' + i + '">';
        html += '<div class="screening-question-header">';
        html += '<span class="font-medium text-sm">' + window.t('recruiter.job_wizard.step5.question') + ' ' + (i + 1) + '</span>';
        html += '<button type="button" class="text-red-500 text-sm" onclick="removeScreeningQuestion(' + i + ')"><i class="fas fa-times"></i></button>';
        html += '</div>';
        html += '<input type="text" class="screening-question-input" value="' + escapeHtml(q.question) + '" placeholder="' + window.t('recruiter.job_wizard.step5.question_placeholder') + '" onchange="updateScreeningQuestion(' + i + ', \'question\', this.value)">';
        html += '<div class="screening-question-options mt-1">';
        html += '<select onchange="updateScreeningQuestion(' + i + ', \'type\', this.value)">';
        ['yes_no', 'multiple_choice', 'text', 'rating'].forEach(function (t) {
            var sel = q.type === t ? ' selected' : '';
            html += '<option value="' + t + '"' + sel + '>' + window.t('recruiter.job_wizard.step5.' + t) + '</option>';
        });
        html += '</select>';
        html += '<label class="ml-2"><input type="checkbox" ' + (q.required ? 'checked' : '') + ' onchange="updateScreeningQuestion(' + i + ', \'required\', this.checked)"> ' + window.t('recruiter.job_wizard.step5.required') + '</label>';
        html += '</div>';
        html += '</div>';
    });
    container.innerHTML = html;
}

async function callAI(endpoint, data) {
    if (!wizardState.jobId) {
        showToast(window.t('recruiter.job_wizard.save_first'), 'error');
        return null;
    }
    var containerId = 'step-' + wizardState.currentStep;
    showSpinner(containerId);
    try {
        var result = await window.fetchAPI(endpoint, {
            method: 'POST',
            body: JSON.stringify(data),
            headers: { 'X-CSRF-Token': getCsrfToken() },
            timeout: 30000
        });
        return result;
    } catch (e) {
        showToast(window.t('recruiter.job_wizard.error_ai') + ': ' + e.message, 'error');
        return null;
    } finally {
        hideSpinner(containerId);
    }
}

async function aiSuggestSkills(title) {
    var result = await callAI('/recruiter/jobs/wizard/ai/suggest-skills', { title: title || wizardState.stepData[1].title });
    if (result && result.suggestions && Array.isArray(result.suggestions)) {
        showSkillChips(result.suggestions);
    }
}

function showSkillChips(suggestions) {
    var container = document.getElementById('jw-ai-suggestions');
    var list = document.getElementById('jw-ai-suggestions-list');
    if (!container || !list) return;
    list.innerHTML = '';
    container.classList.remove('hidden');
    suggestions.forEach(function (s) {
        var chip = document.createElement('button');
        chip.className = 'px-3 py-1.5 bg-white border border-indigo-200 text-indigo-700 text-xs font-bold rounded-xl hover:bg-indigo-50 transition active:scale-95';
        chip.textContent = typeof s === 'string' ? s : s.name;
        chip.addEventListener('click', function () {
            addSkill(typeof s === 'string' ? s : s.name, s.level || 'intermediate', s.weight || 1, true, '');
            this.classList.add('bg-emerald-100 border-emerald-300 text-emerald-700');
            this.disabled = true;
        });
        list.appendChild(chip);
    });
}

async function aiSuggestWeights() {
    var skills = wizardState.stepData[3].skills;
    if (skills.length === 0) {
        showToast(window.t('recruiter.job_wizard.add_skills_first'), 'error');
        return;
    }
    var result = await callAI('/recruiter/jobs/wizard/ai/suggest-weights', {
        title: wizardState.stepData[1].title,
        skills: skills.map(function (s) { return { name: s.name, level: s.level }; })
    });
    if (result && result.weights) {
        result.weights.forEach(function (w, i) {
            if (i < wizardState.stepData[3].skills.length) {
                wizardState.stepData[3].skills[i].weight = w.weight || 1;
            }
        });
        renderSkillList();
        updateWeightBars();
        showToast(window.t('recruiter.job_wizard.weights_updated'), 'success');
    }
}

async function aiGenerateSummary() {
    var result = await callAI('/recruiter/jobs/wizard/ai/generate-summary', {
        title: wizardState.stepData[1].title,
        responsibilities: getStep2Answer('responsibilities'),
        skills: wizardState.stepData[3].skills.map(function (s) { return s.name; })
    });
    if (result && result.summary) {
        var summaryField = document.getElementById('role-summary');
        if (summaryField) {
            summaryField.value = result.summary;
            wizardState.stepData[2].role_summary = result.summary;
        }
    }
}

function getStep2Answer(key) {
    for (var i = 0; i < wizardState.stepData[2].items.length; i++) {
        if (wizardState.stepData[2].items[i].question_key === key) {
            return wizardState.stepData[2].items[i].answer;
        }
    }
    return '';
}

async function aiSuggestCategories() {
    var result = await callAI('/recruiter/jobs/wizard/ai/suggest-categories', {
        title: wizardState.stepData[1].title,
        skills: wizardState.stepData[3].skills.map(function (s) { return s.name; })
    });
    if (result && result.categories) {
        wizardState.stepData[4].categories = result.categories;
        renderCategories();
        showToast(window.t('recruiter.job_wizard.categories_updated'), 'success');
    }
}

function renderCategories() {
    var container = document.getElementById('jw-eval-categories');
    if (!container) return;
    var cats = wizardState.stepData[4].categories;
    var totalWeight = cats.reduce(function (sum, c) { return sum + (parseInt(c.weight) || 0); }, 0);
    var html = '';
    cats.forEach(function (cat, i) {
        var pct = totalWeight > 0 ? Math.round((parseInt(cat.weight) || 0) / totalWeight * 100) : 0;
        html += '<div class="flex items-center gap-3 p-3 bg-slate-50 rounded-xl">';
        html += '<input type="text" value="' + escapeHtml(cat.name) + '" onchange="updateCategory(' + i + ', \'name\', this.value)" class="flex-1 bg-white border border-slate-200 rounded-lg px-3 py-1.5 text-sm font-bold text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500/20">';
        html += '<input type="number" min="0" max="100" value="' + (parseInt(cat.weight) || 0) + '" onchange="updateCategory(' + i + ', \'weight\', parseInt(this.value) || 0); renderCategories()" class="w-16 bg-white border border-slate-200 rounded-lg px-2 py-1.5 text-sm font-bold text-slate-800 text-center focus:outline-none focus:ring-2 focus:ring-indigo-500/20">';
        html += '<span class="text-xs font-bold text-slate-400 w-8">' + pct + '%</span>';
        html += '<button type="button" class="text-red-400 hover:text-red-600 transition" onclick="removeCategory(' + i + ')"><i class="fas fa-times"></i></button>';
        html += '</div>';
    });
    var totalEl = document.getElementById('jw-eval-total');
    var barEl = document.getElementById('jw-eval-weight-bar');
    var hintEl = document.getElementById('jw-eval-hint');
    if (totalEl) totalEl.textContent = totalWeight + '%';
    if (barEl) barEl.style.width = Math.min(totalWeight, 100) + '%';
    if (hintEl) hintEl.style.color = totalWeight === 100 ? '#22c55e' : '#f59e0b';
    container.innerHTML = html;
}

function updateCategory(index, field, value) {
    if (index < 0 || index >= wizardState.stepData[4].categories.length) return;
    wizardState.stepData[4].categories[index][field] = value;
    wizardState.isDirty = true;
}

function removeCategory(index) {
    wizardState.stepData[4].categories.splice(index, 1);
    renderCategories();
    wizardState.isDirty = true;
}

function addEvalCategory() {
    wizardState.stepData[4].categories.push({ name: 'New Category', weight: 10, sort_order: wizardState.stepData[4].categories.length });
    renderCategories();
    wizardState.isDirty = true;
}

async function aiSuggestPipeline() {
    var result = await callAI('/recruiter/jobs/wizard/ai/suggest-pipeline', {
        title: wizardState.stepData[1].title,
        employment_type: wizardState.stepData[1].employment_type
    });
    if (result && result.pipeline_stages) {
        wizardState.stepData[5].pipeline_stages = result.pipeline_stages;
        renderPipelineStages();
        showToast(window.t('recruiter.job_wizard.pipeline_updated'), 'success');
    }
}

async function aiSuggestQuestions() {
    var result = await callAI('/recruiter/jobs/wizard/ai/suggest-questions', {
        title: wizardState.stepData[1].title,
        role_summary: wizardState.stepData[2].role_summary,
        skills: wizardState.stepData[3].skills.map(function (s) { return s.name; })
    });
    if (result && result.questions) {
        wizardState.stepData[5].screening_questions = result.questions;
        renderScreeningQuestions();
        showToast(window.t('recruiter.job_wizard.questions_updated'), 'success');
    }
}

let skillTreeLibraryData = [];

async function filterSkillTrees() {
    var searchInput = document.getElementById('jw-st-search');
    var listEl = document.getElementById('jw-st-list');
    if (!listEl) return;
    var q = (searchInput && searchInput.value || '').toLowerCase();

    if (skillTreeLibraryData.length === 0) {
        listEl.innerHTML = '<div class="text-center py-4 text-slate-400 text-xs"><i class="fas fa-spinner fa-spin mr-2"></i><span data-i18n="recruiter.job_wizard.loading">Loading...</span></div>';
        try {
            var data = await window.fetchAPI('/recruiter/skill-trees', { method: 'GET' });
            skillTreeLibraryData = data.skill_trees || [];
        } catch (e) {
            listEl.innerHTML = '<div class="text-center py-4 text-slate-400 text-xs">Failed to load skill trees</div>';
            return;
        }
    }

    var filtered = skillTreeLibraryData;
    if (q) {
        filtered = skillTreeLibraryData.filter(function (t) {
            return (t.job_name || '').toLowerCase().indexOf(q) !== -1
                || (t.category_name || '').toLowerCase().indexOf(q) !== -1
                || (t.categories || []).some(function (c) { return (c || '').toLowerCase().indexOf(q) !== -1; });
        });
    }

    if (filtered.length === 0) {
        listEl.innerHTML = '<div class="text-center py-4 text-slate-400 text-xs">' + (q ? 'No matching skill trees' : 'No skill trees yet. Create one!') + '</div>';
        return;
    }

    var html = '';
    filtered.forEach(function (tree) {
        html += '<div class="flex items-center justify-between p-2 bg-slate-50 rounded-lg skill-tree-item" data-id="' + tree.id + '">';
        html += '<div class="flex-1 min-w-0">';
        html += '<div class="text-xs font-bold text-slate-800 truncate">' + escapeHtml(tree.job_name || 'Untitled') + '</div>';
        html += '<div class="text-[10px] text-slate-400">' + (tree.skill_count || 0) + ' skills · ' + (tree.category_count || 0) + ' categories</div>';
        html += '</div>';
        html += '<button type="button" class="text-[10px] font-bold text-indigo-600 bg-white px-2 py-1 rounded-lg border border-indigo-200 hover:bg-indigo-50 transition ml-2 whitespace-nowrap" onclick="applySkillTree(' + tree.id + ')">Use</button>';
        html += '</div>';
    });
    listEl.innerHTML = html;
}

async function applySkillTree(treeId) {
    if (!treeId) return;
    var listEl = document.getElementById('jw-st-list');
    try {
        var detail = await window.fetchAPI('/recruiter/skill-trees/' + treeId, { method: 'GET' });
        var criteria = detail.rubric_json || (detail.criteria_json ? JSON.parse(detail.criteria_json) : null);
        if (!criteria) {
            showToast('Skill tree has no skills data', 'error');
            return;
        }
        var categories = criteria.categories || [];
        var flatSkills = [];
        var sortOrder = 0;
        categories.forEach(function (cat) {
            var subcategories = cat.subcategories || [];
            if (subcategories.length === 0) {
                var weight = cat.weight || 10;
                flatSkills.push({
                    name: cat.name || '',
                    level: 'intermediate',
                    weight: weight,
                    mandatory: true,
                    notes: '',
                    sort_order: sortOrder++
                });
            } else {
                subcategories.forEach(function (sub) {
                    var skills = sub.skills || [];
                    skills.forEach(function (s) {
                        flatSkills.push({
                            name: s.name || '',
                            level: s.level || 'intermediate',
                            weight: s.weight || 1,
                            mandatory: s.is_required !== undefined ? s.is_required : true,
                            notes: '',
                            sort_order: sortOrder++
                        });
                    });
                });
            }
        });
        if (flatSkills.length === 0) {
            showToast('No skills found in this skill tree', 'error');
            return;
        }
        wizardState.stepData[3].skills = flatSkills;
        wizardState.stepData[3].skillTreeId = treeId;
        persistState();
        renderSkillList();
        updateWeightBars();
        showToast('Skill tree applied: ' + escapeHtml(detail.job_name || ''), 'success');
        filterSkillTrees();
        if (listEl) listEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    } catch (e) {
        showToast('Failed to load skill tree: ' + (e.message || e), 'error');
    }
}

async function aiSuggestSalary() {
    var result = await callAI('/recruiter/jobs/wizard/ai/suggest-salary', {
        title: wizardState.stepData[1].title,
        location: wizardState.stepData[1].location,
        skills: wizardState.stepData[3].skills.map(function (s) { return s.name; })
    });
    if (result) {
        if (result.salary_min) wizardState.stepData[1].salary_min = result.salary_min;
        if (result.salary_max) wizardState.stepData[1].salary_max = result.salary_max;
        if (result.currency) wizardState.stepData[1].salary_currency = result.currency;
        var minField = document.getElementById('jw-salary-min');
        var maxField = document.getElementById('jw-salary-max');
        var currencyField = document.getElementById('jw-salary-currency');
        if (minField) minField.value = result.salary_min || '';
        if (maxField) maxField.value = result.salary_max || '';
        if (currencyField) currencyField.value = result.currency || 'USD';
        showToast(window.t('recruiter.job_wizard.salary_updated'), 'success');
    }
}

let aiDetectionTimer = null;

function callAIDetection() {
    if (aiDetectionTimer) clearTimeout(aiDetectionTimer);
    aiDetectionTimer = setTimeout(function () {
        if (!wizardState.jobId || wizardState.stepData[1].title.length < 3) return;
        callAI('/recruiter/jobs/wizard/ai/detect-gaps', {
            title: wizardState.stepData[1].title,
            current_step: wizardState.currentStep,
            completed_steps: wizardState.completedSteps,
            data: {
                step1: wizardState.stepData[1],
                step2: { items: wizardState.stepData[2].items, role_summary: wizardState.stepData[2].role_summary },
                step3: { skills: wizardState.stepData[3].skills.map(function (s) { return { skill_name: s.name, required_level: s.level, weight: s.weight, is_mandatory: s.mandatory }; }) },
                step4: { categories: wizardState.stepData[4].categories }
            }
        }).then(function (result) {
            if (result && result.gaps && result.gaps.length > 0) {
                showGapAlerts(result.gaps);
            }
        });
    }, 2000);
}


function handleGapAction(action) {
    const match = /^step_([1-6])$/.exec(String(action || ''));
    if (!match) return;

    const step = parseInt(match[1], 10);
    if (step >= 1 && step <= 6) {
        goToStep(step);
    }
}

function showGapAlerts(gaps) {
    var container = document.getElementById('jw-review-eval-summary');
    if (!container) return;
    container.classList.remove('hidden');
    var html = '<div class="text-sm font-semibold text-amber-600 mb-1">' + window.t('recruiter.job_wizard.gaps_found') + '</div>';
    gaps.forEach(function (gap) {
        html += '<div class="ai-gap-item">';
        html += '<i class="fas fa-lightbulb text-amber-500 mr-1"></i>';
        html += '<span>' + escapeHtml(gap.message) + '</span>';
        if (gap.action && /^step_[1-6]$/.test(String(gap.action))) {
            html += '<button type="button" class="btn btn-xs btn-outline ml-2" data-gap-action="' + escapeHtml(String(gap.action)) + '">' + window.t('recruiter.job_wizard.fix_it') + '</button>';
        }
        html += '</div>';
    });
    container.innerHTML = html;

    container.querySelectorAll('[data-gap-action]').forEach(function (button) {
        button.addEventListener('click', function () {
            handleGapAction(button.dataset.gapAction);
        });
    });
}

function renderStep6Preview() {
    var preview = document.getElementById('jw-review-content');
    if (!preview) return;
    preview.innerHTML = '';
    var catName = '';
    var catSelect = document.getElementById('jw-category');
    if (catSelect && wizardState.stepData[1].category_id) {
        var selected = catSelect.querySelector('option[value="' + wizardState.stepData[1].category_id + '"]');
        if (selected) catName = selected.textContent;
    }
    var hmName = '';
    var hmSelect = document.getElementById('jw-hiring-manager');
    if (hmSelect && wizardState.stepData[1].hiring_manager_id) {
        var selected = hmSelect.querySelector('option[value="' + wizardState.stepData[1].hiring_manager_id + '"]');
        if (selected) hmName = selected.textContent;
    }
    var sections = [
        { label: window.t('recruiter.job_wizard.basic_info'), fields: [
            { label: window.t('recruiter.job_wizard.step1.job_title'), value: wizardState.stepData[1].title },
            { label: window.t('recruiter.job_wizard.step1.category'), value: catName },
            { label: window.t('recruiter.job_wizard.step1.employment_type'), value: window.t('recruiter.job_wizard.step1.' + wizardState.stepData[1].employment_type.replace('-', '_')) },
            { label: window.t('recruiter.job_wizard.step1.workplace'), value: window.t('recruiter.job_wizard.step1.' + wizardState.stepData[1].workplace_type.replace('-', '_')) },
            { label: window.t('recruiter.job_wizard.step1.location'), value: wizardState.stepData[1].location },
            { label: window.t('recruiter.job_wizard.step1.num_openings'), value: wizardState.stepData[1].num_openings },
            { label: window.t('recruiter.job_wizard.step6.hiring_manager'), value: hmName }
        ]},
        { label: window.t('recruiter.job_wizard.role_overview'), fields: wizardState.stepData[2].items.filter(function (i) { return i.answer; }).slice(0, 3).map(function (i) {
            return { label: i.question, value: i.answer.length > 100 ? i.answer.substring(0, 100) + '...' : i.answer };
        })},
        { label: window.t('recruiter.job_wizard.skills'), fields: [
            { label: window.t('recruiter.job_wizard.step6.skills_count'), value: wizardState.stepData[3].skills.length }
        ]}
    ];
    if (wizardState.stepData[1].salary_min || wizardState.stepData[1].salary_max) {
        var salaryStr = '';
        if (wizardState.stepData[1].salary_min) salaryStr += wizardState.stepData[1].salary_currency + ' ' + wizardState.stepData[1].salary_min;
        if (wizardState.stepData[1].salary_max) salaryStr += ' - ' + wizardState.stepData[1].salary_currency + ' ' + wizardState.stepData[1].salary_max;
        sections[0].fields.push({ label: window.t('recruiter.job_wizard.step1.salary'), value: salaryStr });
    }
    sections.forEach(function (section) {
        var hasValues = section.fields.some(function (f) { return f.value && f.value !== 0; });
        if (!hasValues) return;
        var secDiv = document.createElement('div');
        secDiv.className = 'preview-section';
        var heading = document.createElement('h4');
        heading.className = 'preview-section-heading';
        heading.textContent = section.label;
        secDiv.appendChild(heading);
        section.fields.forEach(function (f) {
            if (!f.value && f.value !== 0) return;
            var row = document.createElement('div');
            row.className = 'preview-row';
            row.innerHTML = '<span class="preview-label">' + escapeHtml(f.label) + '</span><span class="preview-value">' + escapeHtml(String(f.value)) + '</span>';
            secDiv.appendChild(row);
        });
        preview.appendChild(secDiv);
    });
    if (wizardState.stepData[5].screening_questions.length > 0) {
        var qDiv = document.createElement('div');
        qDiv.className = 'preview-section';
        qDiv.innerHTML = '<h4 class="preview-section-heading">' + window.t('recruiter.job_wizard.step5.screening_section') + ' (' + wizardState.stepData[5].screening_questions.length + ')</h4>';
        preview.appendChild(qDiv);
    }
    if (wizardState.stepData[5].pipeline_stages.length > 0) {
        var pDiv = document.createElement('div');
        pDiv.className = 'preview-section';
        pDiv.innerHTML = '<h4 class="preview-section-heading">' + window.t('recruiter.job_wizard.pipeline_heading') + ': ' + wizardState.stepData[5].pipeline_stages.length + ' ' + window.t('recruiter.job_wizard.stages') + '</h4>';
        preview.appendChild(pDiv);
    }
}

async function publishJob() {
    if (!wizardState.jobId) {
        showToast(window.t('recruiter.job_wizard.save_first'), 'error');
        return;
    }
    if (wizardState.isPublished) {
        showToast(window.t('recruiter.job_wizard.already_published'), 'error');
        return;
    }
    showSpinner('step-6');
    try {
        var data = await window.fetchAPI('/recruiter/jobs/wizard/' + wizardState.jobId + '/publish', {
            method: 'POST',
            headers: { 'X-CSRF-Token': getCsrfToken() }
        });
        wizardState.isPublished = true;
        wizardState.completedSteps.push(6);
        persistState();
        showToast(window.t('recruiter.job_wizard.step6.publish_success'), 'success');
        var successEl = document.getElementById('publish-success');
        if (successEl) {
            successEl.classList.remove('hidden');
            var link = successEl.querySelector('.job-link');
            if (link) link.href = '/recruiter/jobs/' + wizardState.jobId;
        }
        var publishBtn = document.getElementById('btn-publish');
        if (publishBtn) publishBtn.disabled = true;
    } catch (e) {
        showToast(window.t('recruiter.job_wizard.step6.publish_error') + ': ' + e.message, 'error');
    } finally {
        hideSpinner('step-6');
    }
}

function validateStep(n) {
    var errors = [];
    if (n === 1) {
        var d = wizardState.stepData[1];
        if (!d.title || d.title.trim().length < 3) {
            errors.push(window.t('recruiter.job_wizard.error_title'));
        }
        if (d.num_openings < 1) {
            errors.push(window.t('recruiter.job_wizard.error_openings'));
        }
        if (d.salary_min !== null && d.salary_max !== null && d.salary_min > d.salary_max) {
            errors.push(window.t('recruiter.job_wizard.error_salary_range'));
        }
    } else if (n === 2) {
        var hasAnswer = false;
        wizardState.stepData[2].items.forEach(function (item) {
            if (item.answer && item.answer.trim().length > 0) hasAnswer = true;
        });
        if (!hasAnswer) {
            errors.push(window.t('recruiter.job_wizard.error_role_details'));
        }
    } else if (n === 3) {
        if (wizardState.stepData[3].skills.length === 0) {
            errors.push(window.t('recruiter.job_wizard.errors.skills_required'));
        }
    } else if (n === 4) {
        var totalWeight = wizardState.stepData[4].categories.reduce(function (sum, c) { return sum + (parseInt(c.weight) || 0); }, 0);
        if (totalWeight < 95 || totalWeight > 105) {
            errors.push(window.t('recruiter.job_wizard.errors.weight_not_100'));
        }
        if (wizardState.stepData[4].categories.length === 0) {
            errors.push(window.t('recruiter.job_wizard.errors.categories_required'));
        }
    } else if (n === 5) {
        var hasUnnamedStage = wizardState.stepData[5].pipeline_stages.some(function (s) { return !s.name || s.name.trim() === ''; });
        if (hasUnnamedStage) {
            errors.push(window.t('recruiter.job_wizard.error_pipeline_names'));
        }
        if (wizardState.stepData[5].pipeline_stages.length < 2) {
            errors.push(window.t('recruiter.job_wizard.errors.pipeline_required'));
        }
    }
    return { valid: errors.length === 0, errors: errors };
}

async function resumeWizard(jobId) {
    showSpinner('step-1');
    try {
        var data = await window.fetchAPI('/recruiter/jobs/wizard/' + jobId, {
            method: 'GET',
            headers: { 'X-CSRF-Token': getCsrfToken() }
        });
        wizardState.jobId = data.job_id;
        wizardState.isPublished = data.is_published || false;
        if (data.step_data) {
            Object.keys(data.step_data).forEach(function (k) {
                var n = parseInt(k);
                if (n >= 1 && n <= 5 && wizardState.stepData[n]) {
                    wizardState.stepData[n] = data.step_data[k];
                }
            });
        }
        if (data.completed_steps) {
            wizardState.completedSteps = data.completed_steps;
        }
        if (data.current_step) {
            wizardState.currentStep = data.current_step;
        }
        wizardState.isDirty = true;
        persistState();
        renderStepIndicator();
        if (wizardState.currentStep === 6) {
            wizardState.completedSteps.push(6);
        }
        goToStep(wizardState.currentStep);
        showToast(window.t('recruiter.job_wizard.resumed'), 'success');
    } catch (e) {
        showToast(window.t('recruiter.job_wizard.error_resume') + ': ' + e.message, 'error');
    } finally {
        hideSpinner('step-1');
    }
}

function persistState() {
    try {
        sessionStorage.setItem('wizardState', JSON.stringify({
            jobId: wizardState.jobId,
            currentStep: wizardState.currentStep,
            completedSteps: wizardState.completedSteps,
            isPublished: wizardState.isPublished,
            stepData: wizardState.stepData
        }));
    } catch (e) {
    }
}

function previousStep() {
    if (wizardState.currentStep > 1) {
        goToStep(wizardState.currentStep - 1);
    }
}

function nextStep() {
    if (wizardState.currentStep < 5) {
        saveStep(wizardState.currentStep);
    } else if (wizardState.currentStep === 5) {
        saveStep(5);
    }
}

function handleWizardKeydown(e) {
    if (e.key === 'Enter') {
        var active = document.activeElement;
        if (active && active.tagName === 'INPUT' && active.closest('[id^="step-"]')) {
            e.preventDefault();
            if (wizardState.currentStep < 6) {
                nextStep();
            }
        }
    }
}

document.addEventListener('DOMContentLoaded', function () {
    if (!document.getElementById('step-1')) return;
    initWizard();
    document.addEventListener('keydown', handleWizardKeydown);
    window.addEventListener('translationsReady', function () {
        renderStepIndicator();
        goToStep(wizardState.currentStep);
    });
});

/* Expose wizard functions globally for HTML onclick handlers */
window.goToStep = goToStep;
window.saveStep = saveStep;
window.nextStep = nextStep;
window.previousStep = previousStep;
window.syncStep1Inputs = syncStep1Inputs;
window.syncStep2Inputs = syncStep2Inputs;
window.syncStep4Inputs = syncStep4Inputs;
window.populateStep1 = populateStep1;
window.renderStep6Preview = renderStep6Preview;
window.renderStepIndicator = renderStepIndicator;
window.renderSkillList = renderSkillList;
window.updateWeightBars = updateWeightBars;
window.renderCategories = renderCategories;
window.renderPipelineStages = renderPipelineStages;
window.renderScreeningQuestions = renderScreeningQuestions;
window.addSkill = addSkill;
window.removeSkill = removeSkill;
window.updateSkill = updateSkill;
window.addPipelineStage = addPipelineStage;
window.removePipelineStage = removePipelineStage;
window.updatePipelineStage = updatePipelineStage;
window.addScreeningQuestion = addScreeningQuestion;
window.removeScreeningQuestion = removeScreeningQuestion;
window.updateScreeningQuestion = updateScreeningQuestion;
window.addEvalCategory = addEvalCategory;
window.updateCategory = updateCategory;
window.removeCategory = removeCategory;
window.showSkillChips = showSkillChips;
window.applySkillTree = applySkillTree;
window.callAIDetection = callAIDetection;
window.showGapAlerts = showGapAlerts;
window.validateStep = validateStep;
window.showToast = showToast;
window.cancelWizard = cancelWizard;
window.aiQuickAction = aiQuickAction;
window.sendAiChat = sendAiChat;
window.mobilePrev = mobilePrev;
window.mobileNext = mobileNext;
window.dismissError = dismissError;
window.toggleAiPanel = toggleAiPanel;
window.saveDraft = saveDraft;
window.acceptAllAiSuggestions = acceptAllAiSuggestions;
window.generateRoleSummary = generateRoleSummary;
window.runBiasCheck = runBiasCheck;

/* ── AI Assistant Panel ──────────────────────────────────────── */
function toggleAiPanel() {
    var panel = document.getElementById('ai-panel');
    var backdrop = document.getElementById('ai-panel-backdrop');
    if (!panel) return;
    var isOpen = panel.classList.toggle('open');
    if (backdrop) backdrop.classList.toggle('open', isOpen);
    document.body.style.overflow = isOpen ? 'hidden' : '';
}

/* ── Save Draft ──────────────────────────────────────────────── */
function saveDraft() {
    persistState();
    showToast(window.t('recruiter.job_wizard.draft_saved') || 'Draft saved', 'success');
}

/* ── Accept All AI Suggestions ──────────────────────────────── */
function acceptAllAiSuggestions() {
    var chips = document.querySelectorAll('#jw-ai-suggestions-list button:not([disabled])');
    if (chips.length === 0) {
        showToast(window.t('recruiter.job_wizard.no_suggestions') || 'No suggestions to accept', 'info');
        return;
    }
    chips.forEach(function (chip) { chip.click(); });
    showToast(chips.length + ' ' + (window.t('recruiter.job_wizard.step3.skills_added') || 'skills added'), 'success');
}

/* ── Generate Role Summary (alias for aiGenerateSummary) ────── */
function generateRoleSummary() {
    aiGenerateSummary();
}

/* ── Run Bias Check ─────────────────────────────────────────── */
async function runBiasCheck() {
    var btn = document.getElementById('btn-run-bias');
    var loading = document.getElementById('jw-bias-loading');
    var details = document.getElementById('jw-bias-details');
    var scoreEl = document.getElementById('jw-bias-score');
    var labelEl = document.getElementById('jw-bias-label');
    if (!btn || !loading) return;
    btn.disabled = true;
    loading.classList.remove('hidden');
    if (details) details.classList.add('hidden');
    try {
        var result = await callAI('/recruiter/jobs/wizard/ai/detect-gaps', {
            title: wizardState.stepData[1].title,
            current_step: 6,
            completed_steps: wizardState.completedSteps,
            data: {
                step1: wizardState.stepData[1],
                step2: { items: wizardState.stepData[2].items, role_summary: wizardState.stepData[2].role_summary },
                step3: { skills: wizardState.stepData[3].skills.map(function (s) { return { skill_name: s.name, required_level: s.level, weight: s.weight, is_mandatory: s.mandatory }; }) },
                step4: { categories: wizardState.stepData[4].categories }
            }
        });
        if (result && result.gaps) {
            var biasGaps = result.gaps.filter(function (g) { return g.message && g.message.toLowerCase().indexOf('bias') !== -1; });
            var score = Math.max(0, 100 - (biasGaps.length * 10));
            if (scoreEl) scoreEl.textContent = Math.min(100, Math.max(0, score));
            if (labelEl) labelEl.textContent = score >= 80 ? 'Low Bias Risk' : (score >= 50 ? 'Medium Bias Risk' : 'High Bias Risk');
            if (details) {
                details.classList.remove('hidden');
                details.innerHTML = biasGaps.length > 0 ? biasGaps.map(function (g) { return '<div class="text-xs text-slate-500 flex items-start gap-1.5"><i class="fas fa-info-circle text-amber-500 mt-0.5"></i><span>' + escapeHtml(g.message) + '</span></div>'; }).join('') : '<div class="text-xs text-emerald-600">No bias concerns detected</div>';
            }
        }
    } catch (e) {
        if (details) {
            details.classList.remove('hidden');
            details.innerHTML = '<div class="text-xs text-red-500">Bias check failed: ' + escapeHtml(e.message || e) + '</div>';
        }
    } finally {
        btn.disabled = false;
        loading.classList.add('hidden');
    }
}

/* ── Cancel Wizard ──────────────────────────────────────────── */
function cancelWizard() {
    if (confirm(window.t('recruiter.job_wizard.cancel_confirm') || 'Discard changes?')) {
        sessionStorage.removeItem('wizardState');
        window.location.href = '/recruiter/jobs';
    }
}

/* ── AI Quick Action ────────────────────────────────────────── */
function aiQuickAction(action) {
    var input = document.getElementById('ai-chat-input');
    if (!input) return;
    var prompts = {
        summarize: 'Write a professional role summary for this job position.',
        skills: 'Suggest relevant skills for this job based on the title and description.',
        bias: 'Review this job description for potential bias or non-inclusive language.',
        questions: 'Suggest effective screening questions for this role.'
    };
    input.value = prompts[action] || '';
    sendAiChat();
}

/* ── Send AI Chat ───────────────────────────────────────────── */
function sendAiChat() {
    var input = document.getElementById('ai-chat-input');
    if (!input || !input.value.trim()) return;
    var msg = input.value.trim();
    input.value = '';
    var container = document.getElementById('ai-messages');
    if (!container) return;
    container.innerHTML += '<div class="ai-message user"><div class="flex items-start gap-2"><i class="fas fa-user text-slate-400 mt-0.5"></i><div><p class="text-sm">' + escapeHtml(msg) + '</p></div></div></div>';
    container.scrollTop = container.scrollHeight;
    var endpoint = '/recruiter/jobs/wizard/ai/generate-summary';
    var body = {
        title: wizardState.stepData[1].title,
        responsibilities: msg,
        skills: wizardState.stepData[3].skills.map(function (s) { return s.name; })
    };
    if (msg.toLowerCase().indexOf('skill') !== -1) {
        endpoint = '/recruiter/jobs/wizard/ai/suggest-skills';
        body = { title: wizardState.stepData[1].title, context: msg };
    } else if (msg.toLowerCase().indexOf('question') !== -1) {
        endpoint = '/recruiter/jobs/wizard/ai/suggest-questions';
        body = { title: wizardState.stepData[1].title, context: msg };
    } else if (msg.toLowerCase().indexOf('salary') !== -1) {
        endpoint = '/recruiter/jobs/wizard/ai/suggest-salary';
        body = { title: wizardState.stepData[1].title, location: wizardState.stepData[1].location };
    } else if (msg.toLowerCase().indexOf('bias') !== -1) {
        endpoint = '/recruiter/jobs/wizard/ai/detect-gaps';
        body = { title: wizardState.stepData[1].title, current_step: wizardState.currentStep, completed_steps: wizardState.completedSteps, data: { step1: wizardState.stepData[1], step2: { items: wizardState.stepData[2].items, role_summary: wizardState.stepData[2].role_summary }, step3: { skills: wizardState.stepData[3].skills } } };
    } else if (msg.toLowerCase().indexOf('pipeline') !== -1 || msg.toLowerCase().indexOf('stage') !== -1) {
        endpoint = '/recruiter/jobs/wizard/ai/suggest-pipeline';
        body = { title: wizardState.stepData[1].title, context: msg };
    } else if (msg.toLowerCase().indexOf('category') !== -1 || msg.toLowerCase().indexOf('eval') !== -1) {
        endpoint = '/recruiter/jobs/wizard/ai/suggest-categories';
        body = { title: wizardState.stepData[1].title, skills: wizardState.stepData[3].skills.map(function (s) { return s.name; }) };
    }
    window.fetchAPI(endpoint, { method: 'POST', body: body }).then(function (r) {
        var reply = r.summary || (r.suggestions ? (Array.isArray(r.suggestions) ? r.suggestions.join(', ') : r.suggestions) : null) || (r.gaps ? r.gaps.map(function (g) { return g.message; }).join('. ') : null) || 'Here you go! Check the updated fields.';
        container.innerHTML += '<div class="ai-message bot"><div class="flex items-start gap-2"><i class="fas fa-robot text-indigo-500 mt-0.5"></i><div><p class="text-sm">' + escapeHtml(typeof reply === 'string' ? reply : JSON.stringify(reply)) + '</p></div></div></div>';
        container.scrollTop = container.scrollHeight;
    }).catch(function () {
        container.innerHTML += '<div class="ai-message bot"><div class="flex items-start gap-2"><i class="fas fa-robot text-indigo-500 mt-0.5"></i><div><p class="text-sm text-red-500">Error getting response</p></div></div></div>';
        container.scrollTop = container.scrollHeight;
    });
}

/* ── Mobile Navigation ──────────────────────────────────────── */
function mobilePrev() {
    previousStep();
}

function mobileNext() {
    if (wizardState.currentStep === 6) return;
    var syncFn = [null, syncStep1Inputs, null, null, syncStep4Inputs];
    if (syncFn[wizardState.currentStep]) syncFn[wizardState.currentStep]();
    saveStep(wizardState.currentStep);
}

/* ── Dismiss Error ──────────────────────────────────────────── */
function dismissError() {
    document.getElementById('wizard-error').classList.add('hidden');
}
