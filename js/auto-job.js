const STEPS = [
    { id: 'description', label: 'Generating job description', icon: 'fa-file-lines' },
    { id: 'rubric', label: 'Creating scoring rubric', icon: 'fa-layer-group' },
    { id: 'questions', label: 'Generating interview questions', icon: 'fa-question-circle' },
    { id: 'email', label: 'Creating email templates', icon: 'fa-envelope' },
    { id: 'publish', label: 'Publishing job', icon: 'fa-rocket' },
];

async function startAutoCreate() {
    const title = document.getElementById('job-title').value.trim();
    const skillsStr = document.getElementById('job-skills').value.trim();
    const seniority = document.getElementById('job-seniority').value;
    const company = document.getElementById('job-company').value.trim();
    const location = document.getElementById('job-location').value.trim();

    if (!title) { showToast('Please enter a job title', 'error'); return; }
    if (!skillsStr) { showToast('Please enter required skills', 'error'); return; }

    const skills = skillsStr.split(',').map(s => s.trim()).filter(Boolean);

    document.getElementById('input-form').classList.add('hidden');
    document.getElementById('progress-area').classList.remove('hidden');
    document.getElementById('result-area').classList.add('hidden');

    renderSteps();

    try {
        const data = await window.fetchAPI('/recruiter/jobs/auto-create', {
            method: 'POST',
            body: JSON.stringify({
                title,
                skills,
                seniority,
                company: company || null,
                location: location || null,
                type: 'Full-time'
            }),
            timeout: 120000
        });

        if (data.steps) {
            data.steps.forEach((step, i) => {
                completeStep(i, step.status === 'done');
            });
        }

        setTimeout(() => {
            showResult(data);
        }, 500);

    } catch (e) {
        document.querySelectorAll('.step-status').forEach(el => {
            if (el.innerHTML.includes('spinner')) {
                el.innerHTML = '<i class="fas fa-times text-red-500"></i>';
            }
        });
        showToast('Error: ' + e.message, 'error');
        document.getElementById('progress-area').classList.add('hidden');
        document.getElementById('input-form').classList.remove('hidden');
    }
}

function renderSteps() {
    const container = document.getElementById('steps-container');
    container.innerHTML = STEPS.map((step, i) => `
        <div class="flex items-center gap-4 step-animate" style="animation-delay: ${i * 0.1}s">
            <div class="w-10 h-10 rounded-xl bg-slate-100 flex items-center justify-center text-slate-400" id="step-icon-${i}">
                <i class="fas ${step.icon}"></i>
            </div>
            <div class="flex-1">
                <div class="text-sm font-bold text-slate-700">${step.label}</div>
                <div class="text-xs text-slate-400" id="step-status-${i}">Waiting...</div>
            </div>
            <div class="step-status" id="step-status-icon-${i}">
                <i class="fas fa-circle-notch fa-spin text-indigo-400 hidden" id="step-spinner-${i}"></i>
            </div>
        </div>
    `).join('');

    // Activate steps sequentially with delays
    STEPS.forEach((_, i) => {
        setTimeout(() => activateStep(i), i * 800);
    });
}

function activateStep(index) {
    const icon = document.getElementById(`step-icon-${index}`);
    const status = document.getElementById(`step-status-${index}`);
    const spinner = document.getElementById(`step-spinner-${index}`);

    if (icon) {
        icon.className = 'w-10 h-10 rounded-xl bg-indigo-100 flex items-center justify-center text-indigo-600';
    }
    if (status) status.textContent = 'In progress...';
    if (spinner) spinner.classList.remove('hidden');
}

function completeStep(index, success = true) {
    const icon = document.getElementById(`step-icon-${index}`);
    const status = document.getElementById(`step-status-${index}`);
    const spinner = document.getElementById(`step-spinner-${index}`);

    if (spinner) spinner.classList.add('hidden');

    if (success) {
        if (icon) {
            icon.className = 'w-10 h-10 rounded-xl bg-emerald-100 flex items-center justify-center text-emerald-600';
            icon.innerHTML = '<i class="fas fa-check"></i>';
        }
        if (status) status.textContent = 'Complete';
    } else {
        if (icon) {
            icon.className = 'w-10 h-10 rounded-xl bg-red-100 flex items-center justify-center text-red-600';
            icon.innerHTML = '<i class="fas fa-times"></i>';
        }
        if (status) status.textContent = 'Failed';
    }
}

function showResult(data) {
    document.getElementById('progress-area').classList.add('hidden');
    document.getElementById('result-area').classList.remove('hidden');

    document.getElementById('btn-view-job').href = `/recruiter/jobs?highlight=${data.job_id}`;

    const summary = document.getElementById('result-summary');
    summary.innerHTML = `
        <div class="bg-slate-50 rounded-xl p-4 flex items-center gap-4">
            <div class="w-12 h-12 rounded-xl bg-indigo-100 flex items-center justify-center text-indigo-600">
                <i class="fas fa-briefcase text-lg"></i>
            </div>
            <div>
                <div class="font-bold text-slate-900">${escapeHtml(data.job_title)}</div>
                <div class="text-xs text-slate-400">Job ID: ${data.job_id}</div>
            </div>
        </div>
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <div class="bg-slate-50 rounded-xl p-4 text-center">
                <div class="text-2xl font-black text-indigo-600">${data.rubric_id ? '✅' : '❌'}</div>
                <div class="text-[10px] font-bold text-slate-400 uppercase mt-1">Rubric</div>
            </div>
            <div class="bg-slate-50 rounded-xl p-4 text-center">
                <div class="text-2xl font-black text-indigo-600">${data.questions_count || 0}</div>
                <div class="text-[10px] font-bold text-slate-400 uppercase mt-1">Questions</div>
            </div>
            <div class="bg-slate-50 rounded-xl p-4 text-center">
                <div class="text-2xl font-black text-indigo-600">${data.email_template_id ? '✅' : '❌'}</div>
                <div class="text-[10px] font-bold text-slate-400 uppercase mt-1">Email Template</div>
            </div>
            <div class="bg-slate-50 rounded-xl p-4 text-center">
                <div class="text-2xl font-black text-indigo-600">${data.steps?.length || 0}</div>
                <div class="text-[10px] font-bold text-slate-400 uppercase mt-1">AI Steps</div>
            </div>
        </div>
    `;
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
}
