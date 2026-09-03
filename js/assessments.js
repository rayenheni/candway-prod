const skillsList = [];

document.addEventListener('DOMContentLoaded', async () => {
    await loadSidebar('assessments');
    await loadJobs();
    await loadAssessments();
});

async function loadJobs() {
    try {
        const data = await fetchAPI('/recruiter/jobs');
        const select = document.getElementById('field-job');
        if (data && data.jobs) {
            data.jobs.forEach(job => {
                const opt = document.createElement('option');
                opt.value = job.id;
                opt.textContent = job.title;
                select.appendChild(opt);
            });
        }
    } catch (e) {
        console.error('Failed to load jobs:', e);
    }
}

async function loadAssessments() {
    try {
        const data = await fetchAPI('/recruiter/assessments');
        const container = document.getElementById('assessments-list');

        if (!data || data.length === 0) {
            container.innerHTML = `
                <div class="card p-12 text-center">
                    <div class="w-16 h-16 bg-indigo-50 rounded-2xl flex items-center justify-center mx-auto mb-4">
                        <i class="fas fa-flask text-2xl text-indigo-400"></i>
                    </div>
                    <h3 class="text-lg font-outfit font-semibold text-slate-700 mb-2">No Assessments Yet</h3>
                    <p class="text-slate-400 text-sm">Create your first assessment to start evaluating candidates</p>
                </div>`;
            return;
        }

        XSS.safeSetHTML(container, `<div class="grid gap-4">${data.map(a => `
            <div class="card p-5 flex items-center justify-between hover:border-indigo-100 cursor-pointer" onclick="showAssessmentDetail(${a.id})">
                <div class="flex items-center gap-4">
                    <div class="w-10 h-10 rounded-xl flex items-center justify-center text-lg ${a.provider === 'hackerrank' ? 'bg-emerald-50 text-emerald-600' : 'bg-blue-50 text-blue-600'}">
                        <i class="fas ${a.provider === 'hackerrank' ? 'fa-code' : 'fa-brain'}"></i>
                    </div>
                    <div>
                        <h3 class="font-outfit font-semibold text-slate-800">${esc(a.test_name)}</h3>
                        <div class="flex items-center gap-2 mt-1">
                            <span class="tag ${a.status === 'active' ? 'tag-emerald' : 'tag-gray'}">${a.status}</span>
                            <span class="text-xs text-slate-400 capitalize">${a.provider}</span>
                            <span class="text-xs text-slate-400">${a.difficulty}</span>
                            <span class="text-xs text-slate-400">${a.duration_minutes} min</span>
                        </div>
                    </div>
                </div>
                <div class="flex items-center gap-6">
                    <div class="text-center">
                        <div class="text-lg font-bold text-slate-700">${a.total_invited || 0}</div>
                        <div class="text-xs text-slate-400">Invited</div>
                    </div>
                    <div class="text-center">
                        <div class="text-lg font-bold text-slate-700">${a.completed_count || 0}</div>
                        <div class="text-xs text-slate-400">Done</div>
                    </div>
                    <div class="text-center">
                        <div class="text-lg font-bold ${a.avg_score ? (a.avg_score >= 70 ? 'text-emerald-600' : a.avg_score >= 40 ? 'text-amber-600' : 'text-red-600') : 'text-slate-400'}">${a.avg_score != null ? a.avg_score + '%' : '--'}</div>
                        <div class="text-xs text-slate-400">Avg Score</div>
                    </div>
                    <i class="fas fa-chevron-right text-slate-300"></i>
                </div>
            </div>
        `).join('')}</div>`;
    } catch (e) {
        document.getElementById('assessments-list').innerHTML = `
            <div class="card p-12 text-center text-red-400">
                <i class="fas fa-exclamation-triangle text-3xl mb-4"></i>
                <p>Failed to load assessments: ${esc(e.message)}</p>
            </div>`;
    }
}

function showCreateModal() {
    document.getElementById('create-modal').classList.add('active');
}

function hideCreateModal() {
    document.getElementById('create-modal').classList.remove('active');
}

function addSkill() {
    const input = document.getElementById('field-skill-input');
    const val = input.value.trim();
    if (val && !skillsList.includes(val)) {
        skillsList.push(val);
        renderSkills();
        input.value = '';
    }
}

function removeSkill(skill) {
    const idx = skillsList.indexOf(skill);
    if (idx > -1) {
        skillsList.splice(idx, 1);
        renderSkills();
    }
}

function renderSkills() {
    const container = document.getElementById('skills-tags');
    container.innerHTML = skillsList.map(s => `
        <span class="tag tag-violet">${esc(s)} <button type="button" onclick="removeSkill('${esc(s)}')" class="ml-1 hover:text-red-500">&times;</button></span>
    `).join('');
}

async function handleCreate(e) {
    e.preventDefault();
    const provider = document.getElementById('field-provider').value;
    const jobId = document.getElementById('field-job').value;
    const testName = document.getElementById('field-name').value;
    const difficulty = document.getElementById('field-difficulty').value;
    const duration = parseInt(document.getElementById('field-duration').value);

    if (!provider) { showToast('Please select a provider', 'error'); return; }
    if (!testName) { showToast('Please enter a test name', 'error'); return; }

    try {
        const result = await fetchAPI('/recruiter/assessments/create', {
            method: 'POST',
            body: JSON.stringify({
                job_id: jobId || 0,
                provider,
                test_name: testName,
                difficulty,
                duration_minutes: duration,
                skills: skillsList,
            }),
        });
        showToast('Assessment created successfully!', 'success');
        hideCreateModal();
        document.getElementById('create-form').reset();
        skillsList.length = 0;
        renderSkills();
        await loadAssessments();
    } catch (e) {
        showToast('Failed to create: ' + e.message, 'error');
    }
}

async function showAssessmentDetail(id) {
    try {
        const data = await fetchAPI('/recruiter/assessments/' + id);
        const modal = document.getElementById('detail-modal');
        document.getElementById('detail-title').textContent = data.test_name;
        const container = document.getElementById('detail-content');

        container.innerHTML = `
            <div class="grid grid-cols-3 gap-4 mb-6">
                <div class="card p-4 text-center">
                    <div class="text-sm text-slate-400">Provider</div>
                    <div class="font-semibold mt-1 capitalize">${esc(data.provider)}</div>
                </div>
                <div class="card p-4 text-center">
                    <div class="text-sm text-slate-400">Difficulty</div>
                    <div class="font-semibold mt-1 capitalize">${esc(data.difficulty)}</div>
                </div>
                <div class="card p-4 text-center">
                    <div class="text-sm text-slate-400">Duration</div>
                    <div class="font-semibold mt-1">${data.duration_minutes} min</div>
                </div>
            </div>

            <div class="flex gap-2 flex-wrap mb-6">
                ${(data.skills || []).map(s => `<span class="tag tag-violet">${esc(s)}</span>`).join('')}
                ${data.status === 'active' ? `<span class="tag tag-emerald">Active</span>` : `<span class="tag tag-gray">${esc(data.status)}</span>`}
                ${data.provider_test_id ? `<a href="#" class="tag tag-amber" onclick="alert('Provider URL: ' + '${esc(data.provider_test_id)}')"><i class="fas fa-external-link-alt mr-1"></i> View on ${esc(data.provider)}</a>` : ''}
            </div>

            <div class="flex items-center justify-between mb-4">
                <h3 class="font-outfit font-semibold text-slate-800">Invitations (${data.total_invited || 0})</h3>
                ${data.status === 'active' ? `<button onclick="showInviteModal(${id})" class="text-sm px-3 py-1.5 bg-indigo-50 text-indigo-600 rounded-lg hover:bg-indigo-100"><i class="fas fa-user-plus mr-1"></i> Invite More</button>` : ''}
            </div>

            <div class="space-y-2">
                ${data.invitations && data.invitations.length > 0 ? data.invitations.map(inv => `
                    <div class="flex items-center justify-between p-3 bg-slate-50 rounded-xl">
                        <div>
                            <div class="font-medium text-sm text-slate-700">${esc(inv.candidate_name)}</div>
                            <div class="text-xs text-slate-400">${esc(inv.candidate_email)}</div>
                        </div>
                        <div class="flex items-center gap-3">
                            <span class="tag ${inv.status === 'completed' ? 'tag-emerald' : inv.status === 'invited' ? 'tag-amber' : 'tag-gray'}">${inv.status}</span>
                            ${inv.score != null ? `<span class="text-sm font-bold ${inv.score >= 70 ? 'text-emerald-600' : 'text-red-600'}">${Math.round(inv.score/inv.max_score*100)}%</span>` : ''}
                            ${inv.plagiarism_flag ? `<span class="plagiarism-badge"><i class="fas fa-exclamation-triangle"></i> Plagiarism</span>` : ''}
                            ${inv.status === 'completed' ? `<a href="/recruiter/assessment-results?id=${inv.application_id}&assessment=${id}" class="text-indigo-600 text-sm">View Results</a>` : ''}
                        </div>
                    </div>
                `).join('') : '<p class="text-sm text-slate-400 text-center py-4">No invitations yet</p>'}
            </div>

            <div class="mt-6 flex gap-3">
                ${data.status === 'active' ? `<button onclick="closeAssessment(${id})" class="px-4 py-2 text-red-600 bg-red-50 rounded-xl hover:bg-red-100 text-sm"><i class="fas fa-times mr-1"></i> Close Assessment</button>` : `<button onclick="reopenAssessment(${id})" class="px-4 py-2 text-emerald-600 bg-emerald-50 rounded-xl hover:bg-emerald-100 text-sm"><i class="fas fa-play mr-1"></i> Reopen Assessment</button>`}
                <a href="?assessment=${id}&results=true" class="px-4 py-2 text-indigo-600 bg-indigo-50 rounded-xl hover:bg-indigo-100 text-sm"><i class="fas fa-chart-bar mr-1"></i> View All Results</a>
            </div>
        `;

        modal.classList.add('active');
    } catch (e) {
        showToast('Failed to load details: ' + e.message, 'error');
    }
}

function hideDetailModal() {
    document.getElementById('detail-modal').classList.remove('active');
}

async function closeAssessment(id) {
    if (!confirm('Close this assessment? Candidates will no longer be able to take it.')) return;
    try {
        await fetchAPI('/recruiter/assessments/' + id + '/close', { method: 'POST' });
        showToast('Assessment closed', 'success');
        hideDetailModal();
        await loadAssessments();
    } catch (e) {
        showToast('Failed to close: ' + e.message, 'error');
    }
}

async function reopenAssessment(id) {
    try {
        await fetchAPI('/recruiter/assessments/' + id + '/reopen', { method: 'POST' });
        showToast('Assessment reopened', 'success');
        hideDetailModal();
        await loadAssessments();
    } catch (e) {
        showToast('Failed to reopen: ' + e.message, 'error');
    }
}

function esc(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
