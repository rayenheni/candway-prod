// Prompt Management JavaScript
// Fixed: fetchAPI returns parsed data directly (no .json() calls needed)

let currentTab = 'catalog';
let allVariants = [];
let allTests = [];

document.addEventListener('DOMContentLoaded', function () {
    loadStatsOverview();
    loadPromptCatalog();
    loadTests();
    loadVariants();
    // initializeTestForm deferred — form elements may not exist until tab is opened
    const testForm = document.getElementById('testCases');
    if (testForm) initializeTestForm();
});

// Tab switching
function switchPromptTab(tabName) {
    document.querySelectorAll('.prompt-tab').forEach(tab => {
        tab.classList.remove('active');
        tab.classList.add('text-slate-400');
    });
    const activeTab = document.getElementById(`tab-${tabName}`);
    if (activeTab) { activeTab.classList.add('active'); activeTab.classList.remove('text-slate-400'); }

    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    const activeContent = document.getElementById(`${tabName}-tab`);
    if (activeContent) activeContent.classList.add('active');

    currentTab = tabName;

    // Initialize test form lazily when testing tab opens
    if (tabName === 'testing') {
        const tc = document.getElementById('testCases');
        if (tc && tc.children.length === 0) initializeTestForm();
    }
    if (tabName === 'analytics') loadAnalytics();
}

// ── STATS OVERVIEW ──
async function loadStatsOverview() {
    try {
        const stats = await fetchAPI('/admin/prompts/statistics?days=7');
        const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
        set('statTotalTests',  stats.total_runs ?? 0);
        set('statSuccessRate', ((stats.success_rate ?? 0).toFixed(1)) + '%');
        set('statAvgLatency',  ((stats.avg_latency_ms ?? 0).toFixed(0)) + 'ms');
        set('statAvgScore',    (stats.avg_score ?? 0).toFixed(1));
    } catch (error) {
        console.error('Failed to load stats:', error);
    }
}

// ── CATALOG ──
async function loadPromptCatalog() {
    const container = document.getElementById('promptCatalog');
    if (!container) return;
    container.innerHTML = '<p class="text-slate-400 text-center py-8">Loading catalog…</p>';
    try {
        const catalog = await fetchAPI('/admin/prompts/catalog');

        if (!catalog?.catalog?.length) {
            container.innerHTML = '<p class="text-slate-400 text-center py-8">No prompts found.</p>';
            return;
        }

        container.innerHTML = catalog.catalog.map(item => {
            const variantsHtml = (item.variants || []).map(v => `
                <div class="flex items-center justify-between p-3 bg-slate-50 rounded-xl border border-slate-200">
                    <div>
                        <span class="text-sm font-medium text-slate-700">${v.variant_name || '-'}</span>
                        <span class="ml-2 px-2 py-0.5 text-xs font-bold rounded-full ${v.variant_name === 'control' ? 'bg-indigo-100 text-indigo-700' : 'bg-amber-100 text-amber-700'}">${v.variant_name}</span>
                    </div>
                    <div class="text-right">
                        <div class="text-sm font-mono text-slate-400">v${v.version}</div>
                        <div class="text-xs text-slate-400">${v.times_used ?? 0} uses</div>
                    </div>
                </div>`).join('');

            const testsHtml = (item.recent_tests || []).map(t => `
                <div class="flex items-center justify-between text-sm p-2 bg-slate-50 rounded-lg">
                    <span class="text-slate-600">${t.test_name}</span>
                    <span class="font-mono text-slate-400">${(t.avg_latency ?? 0).toFixed(0)}ms</span>
                </div>`).join('');

            return `
                <div class="bg-white rounded-[2rem] border border-slate-200 p-8 shadow-sm">
                    <div class="flex items-center justify-between mb-6">
                        <div>
                            <h3 class="text-xl font-black text-slate-900">${item.type}</h3>
                            <p class="text-slate-400 mt-1 text-sm">Current: v${item.current_version}</p>
                        </div>
                        <span class="px-4 py-2 bg-indigo-50 text-indigo-600 rounded-full text-sm font-bold">
                            ${Object.keys(item.versions || {}).length} versions
                        </span>
                    </div>
                    ${variantsHtml ? `<div class="mb-6"><h4 class="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">Active Variants</h4><div class="space-y-2">${variantsHtml}</div></div>` : ''}
                    ${testsHtml ? `<div class="mb-6"><h4 class="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">Recent Tests</h4><div class="space-y-2">${testsHtml}</div></div>` : ''}
                    <div class="flex gap-3 mt-4">
                        <button onclick="runTestForPrompt('${item.type}')" class="flex-1 px-4 py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-bold text-sm transition">
                            <i class="fas fa-vial mr-2"></i>Run Test
                        </button>
                    </div>
                </div>`;
        }).join('');

    } catch (error) {
        console.error('Failed to load catalog:', error);
        if (container) container.innerHTML = '<p class="text-red-400 text-center py-8">Failed to load catalog. Check console.</p>';
    }
}

// ── TESTS ──
async function loadTests() {
    try {
        const data = await fetchAPI('/admin/prompts/tests');
        allTests = data.tests || [];

        const container = document.getElementById('recentTests');
        if (!container) return;

        if (!allTests.length) {
            container.innerHTML = '<p class="text-slate-400 text-center py-8">No tests found. Create your first test!</p>';
            return;
        }

        container.innerHTML = allTests.map(test => {
            const successRate = test.total_runs > 0 ? (test.successful_runs / test.total_runs * 100).toFixed(1) : 0;
            const statusColor = successRate >= 90 ? 'text-emerald-500' : successRate >= 70 ? 'text-amber-500' : 'text-red-500';
            return `
                <div class="bg-white rounded-xl p-6 border border-slate-200 shadow-sm">
                    <div class="flex items-center justify-between mb-4">
                        <div>
                            <h4 class="text-lg font-black text-slate-900">${test.test_name}</h4>
                            <p class="text-sm text-slate-400">${test.prompt_type} — v${test.version} (${test.variant})</p>
                        </div>
                        <div class="text-right">
                            <div class="text-sm text-slate-400">${test.total_runs} runs</div>
                            <div class="${statusColor} font-bold">${successRate}%</div>
                        </div>
                    </div>
                    <div class="grid grid-cols-3 gap-4 mb-4">
                        <div class="bg-slate-50 rounded-lg p-3">
                            <div class="text-xs text-slate-400 mb-1">Avg Latency</div>
                            <div class="font-mono text-slate-700">${(test.avg_latency_ms ?? 0).toFixed(0)}ms</div>
                        </div>
                        <div class="bg-slate-50 rounded-lg p-3">
                            <div class="text-xs text-slate-400 mb-1">Avg Score</div>
                            <div class="font-mono text-slate-700">${(test.avg_score ?? 0).toFixed(1)}</div>
                        </div>
                        <div class="bg-slate-50 rounded-lg p-3">
                            <div class="text-xs text-slate-400 mb-1">Test Cases</div>
                            <div class="font-mono text-slate-700">${test.test_cases_count ?? 0}</div>
                        </div>
                    </div>
                    <div class="flex gap-3">
                        <button onclick="viewTestResults(${test.id})" class="flex-[2] px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-bold text-sm transition">
                            View Results
                        </button>
                        <button onclick="deleteTest(${test.id})" class="flex-1 px-4 py-2 bg-red-50 hover:bg-red-100 text-red-500 rounded-lg font-bold text-sm transition">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>`;
        }).join('');
    } catch (error) {
        console.error('Failed to load tests:', error);
    }
}

function initializeTestForm() {
    const tc = document.getElementById('testCases');
    const vt = document.getElementById('versionsToTest');
    if (tc && tc.children.length === 0) addTestCase();
    if (vt && vt.children.length === 0) addVersionRow();
}

function addVersionRow() {
    const container = document.getElementById('versionsToTest');
    if (!container) return;
    const row = document.createElement('div');
    row.className = 'flex gap-4 items-center';
    row.innerHTML = `
        <select class="version-select flex-1 bg-white border border-slate-200 rounded-xl px-4 py-3 text-slate-700">
            <option value="v2.1">v2.1</option>
            <option value="v2.0">v2.0</option>
        </select>
        <select class="variant-select flex-1 bg-white border border-slate-200 rounded-xl px-4 py-3 text-slate-700">
            <option value="control">Control</option>
            <option value="variant">Variant</option>
        </select>
        <button type="button" onclick="this.parentElement.remove()" class="p-3 text-red-400 hover:text-red-600">
            <i class="fas fa-times"></i>
        </button>`;
    container.appendChild(row);
}

function addTestCase() {
    const container = document.getElementById('testCases');
    if (!container) return;
    const index = container.children.length;
    const div = document.createElement('div');
    div.className = 'bg-slate-50 rounded-xl p-6 border border-slate-200';
    div.innerHTML = `
        <div class="flex items-center justify-between mb-4">
            <h4 class="text-sm font-bold text-slate-700">Test Case ${index + 1}</h4>
            <button type="button" onclick="this.parentElement.parentElement.remove()" class="text-red-400 hover:text-red-600">
                <i class="fas fa-times"></i>
            </button>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
                <label class="block text-xs font-bold text-slate-400 mb-2">CV Text</label>
                <textarea name="cv_text_${index}" class="w-full bg-white border border-slate-200 rounded-lg px-4 py-3 text-slate-700 text-sm" rows="3" placeholder="Enter CV text…"></textarea>
            </div>
            <div>
                <label class="block text-xs font-bold text-slate-400 mb-2">Declared Role</label>
                <input type="text" name="declared_role_${index}" class="w-full bg-white border border-slate-200 rounded-lg px-4 py-3 text-slate-700 text-sm" placeholder="Software Engineer">
            </div>
        </div>`;
    container.appendChild(div);
}

async function createTest(event) {
    event.preventDefault();
    const versions = [];
    document.querySelectorAll('#versionsToTest > div').forEach(row => {
        const version = row.querySelector('.version-select')?.value;
        const variant = row.querySelector('.variant-select')?.value;
        if (version) versions.push({ version, variant });
    });

    const testCases = [];
    document.querySelectorAll('#testCases > div').forEach((div, index) => {
        const cvText = div.querySelector(`[name="cv_text_${index}"]`)?.value;
        const role = div.querySelector(`[name="declared_role_${index}"]`)?.value;
        if (cvText && role) testCases.push({ cv_text: cvText, declared_role: role });
    });

    try {
        await fetchAPI('/admin/prompts/test', {
            method: 'POST',
            body: JSON.stringify({
                prompt_type: document.getElementById('testPromptType')?.value,
                test_name: document.getElementById('testName')?.value,
                versions, test_cases: testCases
            })
        });
        showToast('Test created and queued!', 'success');
        clearTestForm();
        loadTests();
    } catch (error) {
        console.error('Failed to create test:', error);
        showToast('Failed to create test', 'error');
    }
}

function clearTestForm() {
    const n = document.getElementById('testName'); if (n) n.value = '';
    const v = document.getElementById('versionsToTest'); if (v) v.innerHTML = '';
    const t = document.getElementById('testCases'); if (t) t.innerHTML = '';
    initializeTestForm();
}

async function deleteTest(testId) {
    if (!confirm('Delete this test?')) return;
    try {
        await fetchAPI(`/admin/prompts/tests/${testId}`, { method: 'DELETE' });
        showToast('Test deleted', 'success');
        loadTests();
    } catch (error) {
        showToast('Failed to delete test', 'error');
    }
}

// ── ANALYTICS ──
async function loadAnalytics() {
    try {
        const stats = await fetchAPI('/admin/prompts/statistics?days=7');
        const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
        set('statTotalTests',  stats.total_runs ?? 0);
        set('statSuccessRate', ((stats.success_rate ?? 0).toFixed(1)) + '%');
        set('statAvgLatency',  ((stats.avg_latency_ms ?? 0).toFixed(0)) + 'ms');
        set('statAvgScore',    (stats.avg_score ?? 0).toFixed(1));

        if (stats.by_prompt_type) renderPerformanceChart(stats.by_prompt_type);
        if (stats.daily_trend) renderTrendChart(stats.daily_trend);
    } catch (error) {
        console.error('Failed to load analytics:', error);
    }
}

function renderPerformanceChart(typeStats) {
    const container = document.getElementById('performanceChart');
    if (!container) return;
    if (!typeStats || !Object.keys(typeStats).length) {
        container.innerHTML = '<p class="text-slate-400 text-center py-4">No data yet</p>';
        return;
    }
    XSS.safeSetHTML(container, '<div class="space-y-4">' +
        Object.entries(typeStats).map(([type, stats]) => {
            const sr = stats.success_rate || 0;
            const color = sr >= 90 ? '#10b981' : sr >= 70 ? '#f59e0b' : '#ef4444';
            return `<div>
                <div class="flex justify-between mb-2">
                    <span class="text-sm font-medium text-slate-700">${type}</span>
                    <span class="text-sm font-mono text-slate-400">${sr.toFixed(1)}%</span>
                </div>
                <div class="h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div style="width:${sr}%;background:${color}" class="h-full rounded-full transition-all duration-700"></div>
                </div>
                <div class="flex justify-between mt-1 text-xs text-slate-400">
                    <span>${(stats.avg_latency || 0).toFixed(0)}ms avg</span>
                    <span>${(stats.avg_score || 0).toFixed(1)} avg score</span>
                </div></div>`;
        }).join('') + '</div>');
}

async function loadTrendData() {
    const daysEl = document.getElementById('trendDays');
    const days = daysEl?.value || 7;
    try {
        const stats = await fetchAPI(`/admin/prompts/statistics?days=${days}`);
        renderTrendChart(stats.daily_trend || []);
    } catch (error) {
        console.error('Failed to load trend data:', error);
    }
}

function renderTrendChart(dailyData) {
    const container = document.getElementById('trendChart');
    if (!container) return;
    if (!dailyData.length) {
        container.innerHTML = '<p class="text-slate-400 text-center py-8">No trend data yet</p>';
        return;
    }
    const maxValue = Math.max(...dailyData.map(d => d.total), 1);
    XSS.safeSetHTML(container, '<div class="space-y-3">' +
        dailyData.map(day => {
            const pct = (day.total / maxValue) * 100;
            return `<div class="flex items-center gap-4">
                <div class="w-24 text-sm text-slate-400">${day.date}</div>
                <div class="flex-1 h-6 bg-slate-100 rounded-lg overflow-hidden">
                    <div style="width:${pct}%;background:linear-gradient(90deg,#6366f1,#8b5cf6)" class="h-full rounded-lg transition-all duration-500"></div>
                </div>
                <div class="w-16 text-right">
                    <div class="text-sm font-mono text-slate-700">${day.total}</div>
                    <div class="text-xs text-slate-400">${(day.success_rate || 0).toFixed(0)}%</div>
                </div></div>`;
        }).join('') + '</div>');
}

// ── VARIANTS ──
async function loadVariants() {
    try {
        const data = await fetchAPI('/admin/prompts/variants');
        allVariants = data.variants || [];
        renderVariants(allVariants);
    } catch (error) {
        console.error('Failed to load variants:', error);
    }
}

function renderVariants(variants) {
    const container = document.getElementById('variantsList');
    if (!container) return;
    if (!variants.length) {
        container.innerHTML = '<p class="text-slate-400 text-center py-8">No variants. Create your first!</p>';
        return;
    }
    container.innerHTML = variants.map(v => {
        const enabled = v.is_enabled;
        return `
            <div class="bg-white rounded-xl p-6 border border-slate-200 shadow-sm">
                <div class="flex items-start justify-between mb-4">
                    <div>
                        <div class="flex items-center gap-3 mb-1">
                            <h4 class="text-lg font-black text-slate-900">${v.variant_name}</h4>
                            <span class="px-2 py-0.5 text-xs font-bold rounded-full ${enabled ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}">${enabled ? 'Enabled' : 'Disabled'}</span>
                        </div>
                        <p class="text-sm text-slate-400">${v.prompt_type} — v${v.version}</p>
                    </div>
                    <div class="text-right text-sm text-slate-400">
                        <div>Traffic: ${v.traffic_percentage || 0}%</div>
                        <div>${v.times_used || 0} uses</div>
                    </div>
                </div>
                <p class="text-sm text-slate-600 mb-4">${v.description || ''}</p>
                <div class="grid grid-cols-3 gap-3 mb-4 text-center">
                    <div class="bg-slate-50 rounded-lg p-3">
                        <div class="text-xs text-slate-400">Success Rate</div>
                        <div class="font-mono text-slate-700">${(v.success_rate || 0).toFixed(1)}%</div>
                    </div>
                    <div class="bg-slate-50 rounded-lg p-3">
                        <div class="text-xs text-slate-400">Avg Latency</div>
                        <div class="font-mono text-slate-700">${(v.avg_latency || 0).toFixed(0)}ms</div>
                    </div>
                    <div class="bg-slate-50 rounded-lg p-3">
                        <div class="text-xs text-slate-400">Times Used</div>
                        <div class="font-mono text-slate-700">${v.times_used || 0}</div>
                    </div>
                </div>
                <div class="flex gap-3">
                    <button onclick="openEditVariantModal(${v.id})"
                        class="flex-1 px-4 py-2 bg-indigo-50 text-indigo-600 hover:bg-indigo-100 rounded-lg font-bold text-sm transition">
                        Edit
                    </button>
                    <button onclick="toggleVariant(${v.id}, ${!enabled})"
                        class="flex-1 px-4 py-2 ${enabled ? 'bg-amber-50 text-amber-600 hover:bg-amber-100' : 'bg-emerald-50 text-emerald-600 hover:bg-emerald-100'} rounded-lg font-bold text-sm transition">
                        ${enabled ? 'Disable' : 'Enable'}
                    </button>
                    <button onclick="deleteVariant(${v.id})" class="px-4 py-2 bg-red-50 text-red-500 hover:bg-red-100 rounded-lg font-bold text-sm transition">
                        <i class="fas fa-trash text-xs"></i>
                    </button>
                </div>
            </div>`;
    }).join('');
}

function filterVariants() {
    const type = document.getElementById('filterPromptType')?.value;
    const status = document.getElementById('filterStatus')?.value;
    let filtered = allVariants;
    if (type) filtered = filtered.filter(v => v.prompt_type === type);
    if (status) filtered = filtered.filter(v => v.is_enabled === (status === 'enabled'));
    renderVariants(filtered);
}

async function createVariant(event) {
    event.preventDefault();
    const get = id => document.getElementById(id)?.value;
    try {
        await fetchAPI('/admin/prompts/variants', {
            method: 'POST',
            body: JSON.stringify({
                prompt_type: get('variantPromptType'),
                version: get('variantVersion'),
                variant_name: get('variantName'),
                description: get('variantDescription'),
                content: get('variantContent'),
                traffic_percentage: parseInt(get('variantTraffic') || '0'),
                is_enabled: document.getElementById('variantEnabled')?.checked ?? true
            })
        });
        showToast('Variant saved!', 'success');
        closeModal('createVariantModal');
        loadVariants();
    } catch (error) {
        showToast('Failed to save variant', 'error');
    }
}

async function toggleVariant(variantId, enable) {
    try {
        await fetchAPI(`/admin/prompts/variants/${variantId}`, {
            method: 'PATCH',
            body: JSON.stringify({ is_enabled: enable })
        });
        showToast(`Variant ${enable ? 'enabled' : 'disabled'}`, 'success');
        loadVariants();
    } catch (error) {
        showToast('Failed to update variant', 'error');
    }
}

async function deleteVariant(variantId) {
    if (!confirm('Delete this variant?')) return;
    try {
        await fetchAPI(`/admin/prompts/variants/${variantId}`, { method: 'DELETE' });
        showToast('Variant deleted', 'success');
        loadVariants();
    } catch (error) {
        showToast('Failed to delete variant', 'error');
    }
}

// ── UTILS ──
function openModal(id) { document.getElementById(id)?.classList.add('active'); }
function closeModal(id) { document.getElementById(id)?.classList.remove('active'); }
function runTestForPrompt(promptType) {
    const el = document.getElementById('testPromptType');
    if (el) el.value = promptType;
    switchPromptTab('testing');
}

function openEditVariantModal(id) {
    const v = allVariants.find(x => x.id === id);
    if (!v) return;
    
    document.getElementById('variantPromptType').value = v.prompt_type;
    document.getElementById('variantVersion').value = v.version;
    document.getElementById('variantName').value = v.variant_name;
    document.getElementById('variantDescription').value = v.description || '';
    document.getElementById('variantContent').value = v.content;
    document.getElementById('variantTraffic').value = v.traffic_percentage || 0;
    document.getElementById('variantEnabled').checked = v.is_enabled;
    
    openModal('createVariantModal');
}

async function viewTestResults(testId) {
    try {
        const data = await fetchAPI(`/admin/prompts/tests/${testId}`);
        const modal = document.getElementById('testResultsModal');
        const container = document.getElementById('testResultsContainer');
        if (!modal || !container) return;
        
        container.innerHTML = (data.results || []).map(res => `
            <div class="p-6 bg-slate-800/50 border border-slate-700 rounded-2xl mb-4">
                <div class="flex justify-between items-center mb-4">
                    <span class="px-2 py-1 bg-indigo-500/10 text-indigo-400 text-[10px] font-bold rounded uppercase">
                        ${res.version} - ${res.variant}
                    </span>
                    <span class="font-mono text-xs text-slate-500">${res.response_time_ms.toFixed(0)}ms</span>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <h5 class="text-[10px] font-bold text-slate-500 uppercase mb-2">Actual Output</h5>
                        <pre class="text-xs bg-slate-900 p-3 rounded-lg overflow-x-auto text-emerald-400 font-mono max-h-40 whitespace-pre-wrap">${res.actual_output}</pre>
                    </div>
                    <div>
                        <h5 class="text-[10px] font-bold text-slate-500 uppercase mb-2">Metrics & Scoring</h5>
                        <div class="space-y-3">
                            <div class="flex justify-between text-xs">
                                <span class="text-slate-400">Similarity</span>
                                <span class="text-white">${(res.similarity_score || 0).toFixed(1)}%</span>
                            </div>
                            <div class="flex justify-between text-xs items-center">
                                <span class="text-slate-400">Quality Score</span>
                                <div class="flex items-center gap-2">
                                    <input type="number" id="score-${res.id}" value="${(res.output_score || 0).toFixed(0)}" 
                                        class="w-12 bg-slate-900 border border-slate-700 rounded px-1 py-0.5 text-white text-xs text-center" 
                                        min="0" max="100">
                                    <button onclick="updateManualScore(${res.id})" class="p-1 text-indigo-400 hover:text-indigo-300">
                                        <i class="fas fa-save"></i>
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `).join('') || '<p class="text-center text-slate-400">No detailed results found.</p>';
        
        openModal('testResultsModal');
    } catch (error) {
        console.error('Failed to load test results:', error);
        showToast('Failed to load results', 'error');
    }
}

async function updateManualScore(resultId) {
    const scoreInput = document.getElementById(`score-${resultId}`);
    if (!scoreInput) return;
    const score = parseInt(scoreInput.value);
    
    try {
        await fetchAPI(`/admin/prompts/results/${resultId}/score`, {
            method: 'PATCH',
            body: JSON.stringify({ score })
        });
        showToast('Score updated!', 'success');
        loadTests(); // Refresh stats in background
    } catch (error) {
        console.error('Failed to update score:', error);
        showToast('Failed to update score', 'error');
    }
}

function showToast(message, type = 'success') {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3500);
}

document.querySelectorAll('.modal').forEach(modal => {
    modal.addEventListener('click', e => { if (e.target === modal) modal.classList.remove('active'); });
});

document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal.active').forEach(m => m.classList.remove('active'));
    }
});

setInterval(() => { if (currentTab === 'catalog') loadStatsOverview(); }, 30000);