let currentJobId = null;
let currentCandidates = [];
let currentCampaign = null;

async function initReengagement() {
    if (!document.getElementById('analyze-btn')) return;

    await loadJobs();
    await loadCampaignHistory();
    await loadStats();

    document.getElementById('analyze-btn').addEventListener('click', triggerAnalysis);
    document.getElementById('invite-all-btn').addEventListener('click', bulkInviteAll);
    document.getElementById('job-selector').addEventListener('change', (e) => {
        currentJobId = e.target.value;
        if (currentJobId) {
            document.getElementById('analyze-btn').disabled = false;
            loadExistingCampaign(currentJobId);
        }
    });
}

async function loadJobs() {
    try {
        const data = await fetchAPI('/recruiter/jobs/my?page=1&per_page=100');
        const sel = document.getElementById('job-selector');
        sel.innerHTML = '<option value="">Select a job...</option>';
        if (data.jobs && data.jobs.length > 0) {
            data.jobs.forEach(job => {
                sel.innerHTML += `<option value="${job.id}">${escapeHtml(job.title)} - ${escapeHtml(job.company || '')}</option>`;
            });
        } else {
            sel.innerHTML = '<option value="">No jobs found</option>';
        }
    } catch (e) {
        console.error('Failed to load jobs:', e);
        showToast('Failed to load jobs', 'error');
    }
}

async function loadStats() {
    try {
        const data = await fetchAPI('/recruiter/reengagement/stats');
        const section = document.getElementById('stats-section');
        section.innerHTML = `
            <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
                <p class="text-xs text-gray-500 font-medium uppercase tracking-wide">Campaigns</p>
                <p class="text-2xl font-bold text-gray-900 mt-1">${data.total_campaigns || 0}</p>
            </div>
            <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
                <p class="text-xs text-gray-500 font-medium uppercase tracking-wide">Candidates Analyzed</p>
                <p class="text-2xl font-bold text-gray-900 mt-1">${data.total_candidates_analyzed || 0}</p>
            </div>
            <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
                <p class="text-xs text-gray-500 font-medium uppercase tracking-wide">Invited</p>
                <p class="text-2xl font-bold text-gray-900 mt-1">${data.total_invited || 0}</p>
            </div>
            <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
                <p class="text-xs text-gray-500 font-medium uppercase tracking-wide">Response Rate</p>
                <p class="text-2xl font-bold text-gray-900 mt-1">${data.response_rate || 0}%</p>
            </div>
            <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
                <p class="text-xs text-gray-500 font-medium uppercase tracking-wide">Avg Match Score</p>
                <p class="text-2xl font-bold text-gray-900 mt-1">${data.avg_match_score || 0}%</p>
            </div>
        `;
    } catch (e) {
        console.error('Failed to load stats:', e);
    }
}

async function loadExistingCampaign(jobId) {
    try {
        const data = await fetchAPI(`/recruiter/reengagement/candidates/${jobId}?min_score=0&limit=5`);
        if (data.candidates && data.candidates.length > 0) {
            currentCampaign = data.campaign;
            displayCandidates(data.candidates, data.campaign);
            const resultsSection = document.getElementById('results-section');
            if (resultsSection) resultsSection.style.display = 'block';
            const inviteAllBtn = document.getElementById('invite-all-btn');
            if (inviteAllBtn) inviteAllBtn.style.display = 'inline-flex';
        }
    } catch (e) {
        // No existing campaign
    }
}

async function triggerAnalysis() {
    if (!currentJobId) {
        showToast('Please select a job first', 'warning');
        return;
    }

    const btn = document.getElementById('analyze-btn');
    if (!btn) return;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Analyzing...';

    try {
        const result = await fetchAPI(`/recruiter/reengagement/analyze/${currentJobId}`, {
            method: 'POST'
        });
        showToast(result.message || 'Analysis started', 'success');

        // Poll for results
        setTimeout(async () => {
            await loadResults();
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-search"></i> Find Candidates';
        }, 2000);
    } catch (e) {
        console.error('Analysis failed:', e);
        showToast('Analysis failed: ' + (e.message || 'Unknown error'), 'error');
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-search"></i> Find Candidates';
    }
}

async function loadResults() {
    if (!currentJobId) return;
    const minScoreEl = document.getElementById('min-score');
    const limitEl = document.getElementById('limit');
    const minScore = minScoreEl ? minScoreEl.value : 65;
    const limit = limitEl ? limitEl.value : 20;

    try {
        const data = await fetchAPI(`/recruiter/reengagement/candidates/${currentJobId}?min_score=${minScore}&limit=${limit}`);
        currentCampaign = data.campaign;
        displayCandidates(data.candidates || [], data.campaign);
        const resultsSection = document.getElementById('results-section');
        if (resultsSection) resultsSection.style.display = 'block';

        const inviteAllBtn = document.getElementById('invite-all-btn');
        if (inviteAllBtn) {
            if (data.candidates && data.candidates.length > 0) {
                inviteAllBtn.style.display = 'inline-flex';
            } else {
                inviteAllBtn.style.display = 'none';
            }
        }
    } catch (e) {
        console.error('Failed to load results:', e);
        showToast('Failed to load results', 'error');
    }
}

function displayCandidates(candidates, campaign) {
    currentCandidates = candidates;
    const resultsCountEl = document.getElementById('results-count');
    if (resultsCountEl) resultsCountEl.textContent = candidates.length;
    const avgScoreEl = document.getElementById('avg-score');
    if (avgScoreEl) avgScoreEl.textContent = campaign?.avg_match_score?.toFixed(1) || '0';
    const invitedCountEl = document.getElementById('invited-count');
    if (invitedCountEl) invitedCountEl.textContent = campaign?.invited_count || '0';

    const list = document.getElementById('candidates-list');
    if (!list) return;
    list.innerHTML = '';

    if (candidates.length === 0) {
        list.innerHTML = '<div class="text-center py-12 text-gray-400"><i class="fas fa-users text-4xl mb-3"></i><p>No matching candidates found above the threshold.</p></div>';
        return;
    }

    candidates.forEach(c => {
        const scoreColor = c.match_score >= 80 ? 'score-high' : c.match_score >= 65 ? 'score-mid' : 'score-low';
        const dateStr = c.original_date ? new Date(c.original_date).toLocaleDateString() : 'Unknown';
        const invitedLabel = c.invited_at
            ? `<span class="badge badge-green"><i class="fas fa-check mr-1"></i> Invited ${new Date(c.invited_at).toLocaleDateString()}</span>`
            : '<span class="badge badge-gray">Not invited</span>';

        const div = document.createElement('div');
        div.className = 're-card bg-white rounded-xl border border-gray-100 p-4 shadow-sm';
        div.innerHTML = `
            <div class="flex items-start justify-between">
                <div class="flex-1">
                    <div class="flex items-center gap-2 mb-2">
                        <h3 class="font-semibold text-gray-900">${escapeHtml(c.candidate_name)}</h3>
                        ${invitedLabel}
                    </div>
                    <div class="flex items-center gap-4 text-sm text-gray-500">
                        <span><i class="fas fa-briefcase mr-1"></i> ${escapeHtml(c.declared_role || 'Unknown')}</span>
                        <span><i class="far fa-calendar mr-1"></i> ${dateStr}</span>
                        <span><i class="far fa-envelope mr-1"></i> ${escapeHtml(c.candidate_email || '')}</span>
                    </div>
                    <div class="mt-2 text-sm text-gray-600">${escapeHtml(c.match_reason || '')}</div>
                </div>
                <div class="flex flex-col items-end ml-4">
                    <div class="text-2xl font-bold ${c.match_score >= 80 ? 'text-emerald-600' : c.match_score >= 65 ? 'text-amber-600' : 'text-red-600'}">${c.match_score}</div>
                    <div class="text-xs text-gray-400 mb-1">/ 100</div>
                    <div class="score-bar w-24">
                        <div class="score-fill ${scoreColor}" style="width:${c.match_score}%"></div>
                    </div>
                    ${c.responded_at ? `<div class="mt-1"><span class="badge badge-blue">Responded</span></div>` : ''}
                </div>
            </div>
            ${!c.invited_at ? `
            <div class="mt-3 pt-3 border-t border-gray-50 flex items-center justify-end gap-2">
                <button onclick="previewMessage(${c.id}, '${escapeHtml(c.candidate_name)}')" class="px-3 py-1.5 text-xs font-medium text-indigo-600 hover:bg-indigo-50 rounded-lg transition">
                    <i class="fas fa-eye mr-1"></i> Preview
                </button>
                <button onclick="inviteSingle(${c.id})" class="px-3 py-1.5 text-xs font-medium bg-indigo-600 text-white hover:bg-indigo-700 rounded-lg transition">
                    <i class="fas fa-paper-plane mr-1"></i> Invite
                </button>
            </div>` : `
            <div class="mt-3 pt-3 border-t border-gray-50 text-right">
                ${c.response_status ? `<span class="badge ${c.response_status === 'applied' ? 'badge-green' : 'badge-yellow'}">${c.response_status}</span>` : ''}
            </div>`}
        `;
        list.appendChild(div);
    });
}

async function inviteSingle(candidateId) {
    if (!confirm('Send re-engagement invitation to this candidate?')) return;
    try {
        const result = await fetchAPI('/recruiter/reengagement/invite', {
            method: 'POST',
            body: JSON.stringify({ candidate_ids: [candidateId], job_id: currentJobId })
        });
        showToast(result.message || 'Invitation sent', 'success');
        await loadResults();
        await loadStats();
    } catch (e) {
        showToast('Failed to send invitation: ' + (e.message || 'Unknown error'), 'error');
    }
}

async function bulkInviteAll() {
    if (!currentCampaign || !currentCampaign.id) {
        showToast('No campaign found. Run analysis first.', 'warning');
        return;
    }

    // TODO: move to backend — uninvited_count from reengagement stats endpoint
    const count = currentCandidates.filter(c => !c.invited_at).length;
    if (count === 0) {
        showToast('All candidates have already been invited', 'info');
        return;
    }

    if (!confirm(`Send re-engagement invitations to ${count} candidates?`)) return;

    try {
        const result = await fetchAPI(`/recruiter/reengagement/bulk-invite/${currentJobId}`, {
            method: 'POST'
        });
        showToast(result.message || `Sent ${result.sent} invitations`, 'success');
        await loadResults();
        await loadStats();
        await loadCampaignHistory();
    } catch (e) {
        showToast('Bulk invite failed: ' + (e.message || 'Unknown error'), 'error');
    }
}

async function previewMessage(candidateId, name) {
    try {
        const data = await fetchAPI('/recruiter/reengagement/invite', {
            method: 'POST',
            body: JSON.stringify({ candidate_ids: [candidateId], job_id: currentJobId, message_template: '', preview: true })
        });
        if (data.preview && data.candidates && data.candidates.length > 0) {
            var c = data.candidates[0];
            showToast('Preview: Would send to ' + c.candidate_name + ' (match: ' + c.match_score + '%)', 'info', 5000);
        } else {
            showToast('Preview: Would send to ' + name, 'info', 5000);
        }
    } catch (e) {
        showToast('Preview unavailable', 'warning');
    }
}

async function loadCampaignHistory() {
    try {
        const data = await fetchAPI('/recruiter/reengagement/stats');
        const list = document.getElementById('campaigns-list');
        if (!list) return;
        const campaigns = data.recent_campaigns || [];
        if (campaigns.length === 0) {
            list.innerHTML = '<p class="text-sm text-gray-400 text-center py-4">No previous re-engagement campaigns</p>';
            return;
        }
        list.innerHTML = campaigns.map(c => `
            <div class="bg-white rounded-lg border border-gray-100 p-3 flex items-center justify-between text-sm">
                <div>
                    <span class="font-medium text-gray-700">Job #${c.job_id}</span>
                    <span class="mx-2 text-gray-300">|</span>
                    <span>${c.matched_candidates || 0} matched</span>
                    <span class="mx-2 text-gray-300">|</span>
                    <span>${c.invited_count || 0} invited</span>
                    <span class="mx-2 text-gray-300">|</span>
                    <span>Avg: ${c.avg_match_score?.toFixed(1) || '0'}%</span>
                </div>
                <div class="flex items-center gap-2">
                    <span class="badge ${c.status === 'completed' ? 'badge-green' : c.status === 'sending' ? 'badge-yellow' : 'badge-blue'}">${c.status}</span>
                    <span class="text-xs text-gray-400">${new Date(c.created_at).toLocaleDateString()}</span>
                </div>
            </div>
        `).join('');
    } catch (e) {
        console.error('Failed to load campaign history:', e);
    }
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}