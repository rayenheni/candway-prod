let resultChart = null;

document.addEventListener('DOMContentLoaded', async () => {
    await loadSidebar('assessments');
    const params = new URLSearchParams(window.location.search);
    const appId = params.get('id');
    const assessmentId = params.get('assessment');
    if (appId && assessmentId) {
        await loadCandidateResult(assessmentId, appId);
    } else if (assessmentId) {
        await loadAssessmentResults(assessmentId);
    } else {
        document.getElementById('result-content').innerHTML = `
            <div class="card p-12 text-center text-slate-400">
                <i class="fas fa-search text-3xl mb-4"></i>
                <p>No result data provided. Please select a candidate from the assessments page.</p>
            </div>`;
    }
});

async function loadAssessmentResults(assessmentId) {
    try {
        const data = await fetchAPI('/recruiter/assessments/' + assessmentId + '/results');
        document.getElementById('result-title').textContent = data.test_name + ' - Results';
        document.getElementById('result-subtitle').textContent = data.total_completed + ' candidate(s) completed';

        if (!data.results || data.results.length === 0) {
            document.getElementById('result-content').innerHTML = `
                <div class="card p-12 text-center text-slate-400">
                    <i class="fas fa-hourglass text-3xl mb-4"></i>
                    <p>No results yet. Candidates are still working on their assessments.</p>
                </div>`;
            return;
        }

        const avgScore = data.results.reduce((s, r) => s + (r.percentage || 0), 0) / data.results.length;
        const plagiarismCount = data.results.filter(r => r.plagiarism_flag).length;

        document.getElementById('result-content').innerHTML = `
            <div class="grid grid-cols-3 gap-4 mb-8">
                <div class="card p-5 text-center">
                    <div class="text-2xl font-bold ${avgScore >= 70 ? 'text-emerald-600' : avgScore >= 40 ? 'text-amber-600' : 'text-red-600'}">${avgScore.toFixed(1)}%</div>
                    <div class="text-sm text-slate-400 mt-1">Average Score</div>
                </div>
                <div class="card p-5 text-center">
                    <div class="text-2xl font-bold text-slate-700">${data.total_completed}</div>
                    <div class="text-sm text-slate-400 mt-1">Completed</div>
                </div>
                <div class="card p-5 text-center">
                    <div class="text-2xl font-bold ${plagiarismCount > 0 ? 'text-red-600' : 'text-slate-700'}">${plagiarismCount}</div>
                    <div class="text-sm text-slate-400 mt-1">Plagiarism Flags</div>
                </div>
            </div>

            <div class="card overflow-hidden">
                <table class="w-full">
                    <thead>
                        <tr class="bg-slate-50 text-left">
                            <th class="p-3 text-xs font-semibold text-slate-500 uppercase">Candidate</th>
                            <th class="p-3 text-xs font-semibold text-slate-500 uppercase">Score</th>
                            <th class="p-3 text-xs font-semibold text-slate-500 uppercase">Duration</th>
                            <th class="p-3 text-xs font-semibold text-slate-500 uppercase">Plagiarism</th>
                            <th class="p-3 text-xs font-semibold text-slate-500 uppercase">Skills</th>
                            <th class="p-3 text-xs font-semibold text-slate-500 uppercase">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.results.map(r => `
                            <tr class="border-t border-slate-100 hover:bg-slate-50">
                                <td class="p-3">
                                    <div class="font-medium text-slate-700">${esc(r.candidate_name)}</div>
                                    <div class="text-xs text-slate-400">${esc(r.candidate_email)}</div>
                                </td>
                                <td class="p-3">
                                    <span class="font-bold ${r.percentage >= 70 ? 'text-emerald-600' : r.percentage >= 40 ? 'text-amber-600' : 'text-red-600'}">${r.percentage != null ? r.percentage + '%' : 'N/A'}</span>
                                </td>
                                <td class="p-3 text-sm text-slate-500">${r.duration_seconds ? Math.round(r.duration_seconds / 60) + ' min' : '--'}</td>
                                <td class="p-3">${r.plagiarism_flag ? '<span class="text-red-600 text-sm font-medium"><i class="fas fa-exclamation-triangle"></i> Flagged</span>' : '<span class="text-emerald-600 text-sm">Clean</span>'}</td>
                                <td class="p-3">
                                    <div class="flex gap-1 flex-wrap max-w-[200px]">
                                        ${r.skills_breakdown ? Object.keys(r.skills_breakdown).slice(0, 3).map(s => `<span class="tag tag-violet text-[10px]">${esc(s)}</span>`).join('') : '<span class="text-xs text-slate-400">--</span>'}
                                    </div>
                                </td>
                                <td class="p-3">
                                    <a href="?id=${r.application_id}&assessment=${assessmentId}" class="text-indigo-600 text-sm hover:underline">View Details</a>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>`;
    } catch (e) {
        document.getElementById('result-content').innerHTML = `
            <div class="card p-12 text-center text-red-400">
                <i class="fas fa-exclamation-triangle text-3xl mb-4"></i>
                <p>Failed to load results: ${e.message}</p>
            </div>`;
    }
}

async function loadCandidateResult(assessmentId, appId) {
    try {
        const data = await fetchAPI('/recruiter/assessments/' + assessmentId + '/candidate/' + appId + '/result');
        document.getElementById('result-title').textContent = data.candidate_name + ' - Assessment Result';
        document.getElementById('result-subtitle').textContent = data.status;

        const scoreColor = data.percentage >= 70 ? '#10b981' : data.percentage >= 40 ? '#f59e0b' : '#ef4444';

        let skillsHtml = '';
        if (data.skills_breakdown) {
            skillsHtml = Object.entries(data.skills_breakdown).map(([skill, score]) => `
                <div class="flex items-center justify-between p-2">
                    <span class="text-sm text-slate-600">${esc(skill)}</span>
                    <div class="flex items-center gap-2">
                        <div class="w-32 h-2 bg-slate-100 rounded-full overflow-hidden">
                            <div class="h-full rounded-full" style="width:${score}%;background:${score >= 70 ? '#10b981' : score >= 40 ? '#f59e0b' : '#ef4444'}"></div>
                        </div>
                        <span class="text-sm font-medium w-10 text-right">${score}</span>
                    </div>
                </div>
            `).join('');
        }

        const durationMin = data.duration_seconds ? Math.round(data.duration_seconds / 60) : '--';

        document.getElementById('result-content').innerHTML = `
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
                <div class="card p-6 flex flex-col items-center justify-center">
                    <div class="score-circle" style="background:${scoreColor}15;color:${scoreColor};border:4px solid ${scoreColor}">
                        ${data.percentage != null ? data.percentage : '--'}
                    </div>
                    <div class="text-slate-500 text-sm mt-3">Score</div>
                    <div class="text-xs text-slate-400">${data.score != null ? data.score + ' / ' + data.max_score : ''}</div>
                </div>
                <div class="card p-6">
                    <h3 class="font-outfit font-semibold text-slate-700 mb-3">Skills Breakdown</h3>
                    ${skillsHtml || '<p class="text-sm text-slate-400">No skills data available</p>'}
                </div>
                <div class="card p-6">
                    <h3 class="font-outfit font-semibold text-slate-700 mb-3">Assessment Info</h3>
                    <div class="space-y-3 text-sm">
                        <div class="flex justify-between"><span class="text-slate-400">Duration</span><span class="font-medium">${durationMin} min</span></div>
                        <div class="flex justify-between"><span class="text-slate-400">Plagiarism</span>${data.plagiarism_flag ? '<span class="text-red-600 font-medium"><i class="fas fa-exclamation-triangle"></i> Flagged</span>' : '<span class="text-emerald-600 font-medium">Clean</span>'}</div>
                        <div class="flex justify-between"><span class="text-slate-400">Completed</span><span class="font-medium">${data.completed_at ? new Date(data.completed_at).toLocaleDateString() : '--'}</span></div>
                        <div class="flex justify-between"><span class="text-slate-400">Status</span><span class="font-medium capitalize">${esc(data.status)}</span></div>
                    </div>
                    ${data.plagiarism_flag ? `
                        <div class="mt-4 p-3 bg-red-50 border border-red-100 rounded-xl">
                            <p class="text-xs text-red-700"><i class="fas fa-exclamation-circle mr-1"></i> Plagiarism detected. Review the candidate's submission on the provider platform for details.</p>
                        </div>
                    ` : ''}
                    <div class="mt-4 flex gap-2">
                        ${data.invite_url ? `<a href="${esc(data.invite_url)}" target="_blank" class="flex-1 text-center px-3 py-2 bg-indigo-50 text-indigo-600 rounded-xl text-sm hover:bg-indigo-100"><i class="fas fa-external-link-alt mr-1"></i> View on Provider</a>` : ''}
                        <button onclick="addScoreToEvaluation(${data.application_id}, ${data.percentage})" class="flex-1 px-3 py-2 bg-emerald-50 text-emerald-600 rounded-xl text-sm hover:bg-emerald-100"><i class="fas fa-plus mr-1"></i> Add Score to Evaluation</button>
                    </div>
                </div>
            </div>`;

        if (data.skills_breakdown && Object.keys(data.skills_breakdown).length > 0) {
            setTimeout(() => renderSkillsChart(data.skills_breakdown), 100);
        }
    } catch (e) {
        document.getElementById('result-content').innerHTML = `
            <div class="card p-12 text-center text-red-400">
                <i class="fas fa-exclamation-triangle text-3xl mb-4"></i>
                <p>Failed to load result: ${e.message}</p>
            </div>`;
    }
}

function renderSkillsChart(skillsBreakdown) {
    const canvas = document.createElement('canvas');
    canvas.id = 'skills-chart';
    canvas.className = 'mt-6 max-w-lg mx-auto';

    const container = document.getElementById('result-content');
    if (container) {
        container.appendChild(canvas);
    }

    if (resultChart) resultChart.destroy();

    const labels = Object.keys(skillsBreakdown);
    const values = Object.values(skillsBreakdown);

    resultChart = new Chart(canvas, {
        type: 'radar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Skill Score',
                data: values,
                backgroundColor: 'rgba(99, 102, 241, 0.2)',
                borderColor: '#6366f1',
                borderWidth: 2,
                pointBackgroundColor: '#6366f1',
            }]
        },
        options: {
            responsive: true,
            scales: {
                r: {
                    beginAtZero: true,
                    max: 100,
                    ticks: { stepSize: 20 }
                }
            }
        }
    });
}

async function addScoreToEvaluation(applicationId, percentage) {
    try {
        const data = await fetchAPI('/recruiter/applications/' + applicationId + '/scores');
        showToast('Assessment score loaded into evaluation. Refreshing...', 'success');
        setTimeout(() => window.location.reload(), 1500);
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

function esc(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
