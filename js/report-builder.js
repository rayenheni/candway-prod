(function () {
    'use strict';

    const API_BASE = '/api/v1/recruiter/reports';
    let reportId = null;
    let widgetIdCounter = 0;
    let widgets = [];
    let chartInstances = {};
    let filters = {};
    let currentConfigWidget = null;

    const METRICS_META = [
        { key: 'total_applications', label: 'Total Applications', category: 'volume', icon: 'fa-users' },
        { key: 'applications_per_job', label: 'Applications Per Job', category: 'volume', icon: 'fa-chart-bar' },
        { key: 'screening_rate', label: 'Screening Rate', category: 'conversion', icon: 'fa-filter' },
        { key: 'interview_rate', label: 'Interview Rate', category: 'conversion', icon: 'fa-phone' },
        { key: 'offer_rate', label: 'Offer Rate', category: 'conversion', icon: 'fa-file-signature' },
        { key: 'hire_rate', label: 'Hire Rate', category: 'conversion', icon: 'fa-check-double' },
        { key: 'avg_time_to_hire', label: 'Avg Time to Hire', category: 'time', icon: 'fa-clock' },
        { key: 'avg_time_to_interview', label: 'Avg Time to Interview', category: 'time', icon: 'fa-calendar-clock' },
        { key: 'avg_cv_score', label: 'Avg CV Score', category: 'quality', icon: 'fa-file-lines' },
        { key: 'avg_interview_score', label: 'Avg Interview Score', category: 'quality', icon: 'fa-star' },
        { key: 'offer_acceptance_rate', label: 'Offer Acceptance Rate', category: 'conversion', icon: 'fa-handshake' },
        { key: 'candidates_per_job', label: 'Avg Candidates Per Job', category: 'volume', icon: 'fa-users-between-lines' },
        { key: 'source_effectiveness', label: 'Source Effectiveness', category: 'source', icon: 'fa-arrow-trend-up' },
        { key: 'pipeline_conversion', label: 'Pipeline Conversion', category: 'funnel', icon: 'fa-funnel-dollar' },
        { key: 'applications_by_source', label: 'Applications by Source', category: 'source', icon: 'fa-chart-pie' },
        { key: 'applications_by_status', label: 'Applications by Status', category: 'status', icon: 'fa-chart-simple' },
        { key: 'applications_over_time', label: 'Applications Over Time', category: 'trend', icon: 'fa-chart-line' },
        { key: 'hires_over_time', label: 'Hires Over Time', category: 'trend', icon: 'fa-arrow-up' },
    ];

    const CATEGORIES = [
        { id: 'volume', label: 'Volume' },
        { id: 'conversion', label: 'Conversion' },
        { id: 'time', label: 'Time' },
        { id: 'quality', label: 'Quality' },
        { id: 'source', label: 'Source' },
        { id: 'status', label: 'Status' },
        { id: 'trend', label: 'Trend' },
        { id: 'funnel', label: 'Funnel' },
    ];

    function getDefaultVizType(metric) {
        const funnelMetrics = ['pipeline_conversion'];
        const pieMetrics = ['applications_by_source', 'applications_by_status'];
        const trendMetrics = ['applications_over_time', 'hires_over_time'];
        const sourceMetrics = ['source_effectiveness'];
        if (funnelMetrics.includes(metric)) return 'funnel';
        if (pieMetrics.includes(metric)) return 'pie_chart';
        if (trendMetrics.includes(metric)) return 'line_chart';
        if (sourceMetrics.includes(metric)) return 'table';
        return 'number_card';
    }

    function populateMetricsList() {
        const container = document.getElementById('metrics-list');
        const searchInput = document.getElementById('metric-search');
        const countEl = document.getElementById('metric-count');
        if (!container || !searchInput || !countEl) return;

        function render(filter = '') {
            const lowered = filter.toLowerCase();
            const cats = CATEGORIES.map(c => ({
                ...c,
                items: METRICS_META.filter(m =>
                    m.category === c.id &&
                    (!lowered || m.label.toLowerCase().includes(lowered) || m.key.toLowerCase().includes(lowered))
                )
            })).filter(c => c.items.length > 0);

            countEl.textContent = cats.reduce((a, c) => a + c.items.length, 0);
            container.innerHTML = cats.map(c => `
                <div class="mb-3">
                    <div class="text-[10px] font-bold text-slate-400 uppercase tracking-wider px-2 mb-1.5">${c.label}</div>
                    ${c.items.map(m => `
                        <div class="metric-item flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-violet-50 text-sm text-slate-700 transition-colors"
                             draggable="true" data-metric="${m.key}" data-label="${m.label}">
                            <i class="fas ${m.icon} text-violet-400 text-xs w-4 text-center"></i>
                            <span>${m.label}</span>
                        </div>
                    `).join('')}
                </div>
            `).join('');

            document.querySelectorAll('.metric-item').forEach(el => {
                el.addEventListener('dragstart', e => {
                    e.dataTransfer.setData('text/plain', JSON.stringify({
                        metric: el.dataset.metric,
                        label: el.dataset.label,
                    }));
                    e.dataTransfer.effectAllowed = 'copy';
                });
            });
        }

        render('');
        searchInput.addEventListener('input', () => render(searchInput.value));
    }

    function getDateRange(preset) {
        const now = new Date();
        let end = now.toISOString().split('T')[0];
        let start;
        switch (preset) {
            case 'last_7': start = new Date(now.getTime() - 7 * 86400000).toISOString().split('T')[0]; break;
            case 'last_30': start = new Date(now.getTime() - 30 * 86400000).toISOString().split('T')[0]; break;
            case 'last_90': start = new Date(now.getTime() - 90 * 86400000).toISOString().split('T')[0]; break;
            case 'this_year': start = new Date(now.getFullYear(), 0, 1).toISOString().split('T')[0]; break;
            default: start = null; end = null;
        }
        return { start, end };
    }

    function buildConfig() {
        return {
            metrics: widgets.map(w => w.metric),
            filters: {
                date_range: getDateRange(document.getElementById('date-preset').value),
                ...filters,
            },
            group_by: "month",
            visualizations: widgets.map(w => ({
                metric: w.metric,
                type: w.vizType || getDefaultVizType(w.metric),
            })),
        };
    }

    async function buildReport() {
        const config = buildConfig();
        try {
            const resp = await fetch(API_BASE + '/build', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(config),
            });
            if (!resp.ok) throw new Error('Build failed');
            const data = await resp.json();
            renderWidgets(data.report_data);
        } catch (e) {
            console.error('Report build error:', e);
        }
    }

    function renderWidgets(reportData) {
        const dropZone = document.getElementById('drop-zone');
        const emptyState = document.getElementById('empty-state');
        emptyState.style.display = widgets.length === 0 ? 'flex' : 'none';

        const existing = dropZone.querySelectorAll('.widget-container');
        existing.forEach(el => el.remove());

        widgets.forEach((w, idx) => {
            const data = reportData[w.metric] || {};
            const el = createWidgetElement(w, data, idx);
            dropZone.appendChild(el);
        });
    }

    function createWidgetElement(widget, data, idx) {
        const div = document.createElement('div');
        div.className = 'widget-container glass-card rounded-xl border border-slate-200 overflow-hidden';
        div.dataset.widgetId = widget.id;

        const header = document.createElement('div');
        header.className = 'flex items-center justify-between px-4 py-2.5 bg-slate-50 border-b border-slate-100';
        header.innerHTML = `
            <div class="flex items-center gap-2">
                <i class="fas fa-grip-lines text-slate-300 cursor-grab handle"></i>
                <span class="text-sm font-bold text-slate-700">${widget.label}</span>
                <span class="text-[10px] font-bold text-violet-500 bg-violet-50 px-1.5 py-0.5 rounded uppercase">${widget.vizType || getDefaultVizType(widget.metric)}</span>
            </div>
            <div class="flex items-center gap-1">
                <button class="config-widget-btn text-slate-400 hover:text-violet-600 p-1 text-xs" title="Configure"><i class="fas fa-sliders"></i></button>
                <button class="remove-widget-btn text-slate-400 hover:text-rose-600 p-1 text-xs" title="Remove"><i class="fas fa-xmark"></i></button>
            </div>
        `;

        const body = document.createElement('div');
        body.className = 'p-4';

        if (data.error) {
            XSS.safeSetHTML(body, `<div class="text-sm text-rose-600"><i class="fas fa-triangle-exclamation mr-1"></i>${XSS.escapeHTML(data.error)}</div>`);
        } else if (data.type === 'number_card') {
            body.innerHTML = renderNumberCard(data, widget);
        } else if (data.type === 'funnel') {
            body.innerHTML = renderFunnelChart(data);
            setTimeout(() => renderFunnelSVG(body.querySelector('.funnel-svg'), data), 100);
        } else if (data.type === 'pie_chart') {
            body.innerHTML = `<canvas class="pie-canvas" style="max-height:200px"></canvas>`;
            setTimeout(() => renderPieChart(body.querySelector('.pie-canvas'), data), 100);
        } else if (data.type === 'line_chart' || data.type === 'bar_chart') {
            body.innerHTML = `<canvas class="chart-canvas" style="max-height:200px"></canvas>`;
            setTimeout(() => renderLineChart(body.querySelector('.chart-canvas'), data, widget), 100);
        } else if (data.type === 'table') {
            body.innerHTML = renderTable(data, widget);
        } else {
            body.innerHTML = `<div class="text-sm text-slate-500">No data available</div>`;
        }

        div.appendChild(header);
        div.appendChild(body);

        header.querySelector('.remove-widget-btn').addEventListener('click', () => removeWidget(widget.id));
        header.querySelector('.config-widget-btn').addEventListener('click', () => openConfigPanel(widget, data));

        return div;
    }

    function renderNumberCard(data, widget) {
        const val = data.value ?? '--';
        const suffix = data.suffix ?? '';
        const change = data.change ?? 0;
        const isUp = change >= 0;
        return `
            <div class="flex items-end justify-between">
                <div>
                    <div class="text-3xl font-black text-slate-900 tracking-tight">${val}<span class="text-lg font-bold text-slate-400 ml-0.5">${suffix}</span></div>
                    <div class="flex items-center gap-1 mt-1 ${isUp ? 'text-emerald-600' : 'text-rose-600'}">
                        <i class="fas fa-${isUp ? 'arrow-up' : 'arrow-down'} text-xs"></i>
                        <span class="text-sm font-bold">${Math.abs(change).toFixed(1)}%</span>
                        <span class="text-xs text-slate-400 font-medium ml-1">vs previous period</span>
                    </div>
                </div>
                <div class="w-12 h-12 rounded-xl bg-violet-50 flex items-center justify-center text-violet-500">
                    <i class="fas ${METRICS_META.find(m => m.key === widget.metric)?.icon || 'fa-chart-simple'} text-lg"></i>
                </div>
            </div>
        `;
    }

    function renderFunnelChart(data) {
        const stages = data.stages || [];
        const total = data.total || 1;
        return `
            <div class="space-y-2 funnel-svg-container">
                ${stages.map((s, i) => {
                    const pct = (s.count / total) * 100;
                    return `
                        <div class="flex items-center gap-3">
                            <span class="text-xs font-bold text-slate-500 w-20 uppercase">${s.stage}</span>
                            <div class="flex-1 h-7 rounded-lg relative overflow-hidden" style="background: #f1f5f9">
                                <div class="h-full rounded-lg flex items-center px-2" style="width: ${Math.max(pct, 5)}%; background: ${['#6366f1','#818cf8','#a5b4fc','#c7d2fe','#e0e7ff'][i] || '#6366f1'}">
                                    <span class="text-xs font-bold text-white drop-shadow">${s.count}</span>
                                </div>
                            </div>
                            <span class="text-xs font-bold text-slate-400 w-12 text-right">${s.conversion}%</span>
                        </div>
                    `;
                }).join('')}
            </div>
        `;
    }

    function renderFunnelSVG(container, data) {}

    function renderPieChart(canvas, data) {
        if (!canvas || !data.labels || !data.values) return;
        const colors = ['#6366f1', '#818cf8', '#a5b4fc', '#c7d2fe', '#e0e7ff', '#4f46e5', '#3730a3'];
        const ctx = canvas.getContext('2d');
        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.labels,
                datasets: [{
                    data: data.values,
                    backgroundColor: colors.slice(0, data.labels.length),
                    borderWidth: 0,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { font: { size: 10, family: 'Outfit' }, boxWidth: 10, padding: 8 },
                    },
                },
                cutout: '60%',
            },
        });
    }

    function renderLineChart(canvas, data, widget) {
        if (!canvas || !data.labels || !data.datasets) return;
        const colors = ['#6366f1', '#f59e0b', '#10b981', '#ef4444'];
        const ctx = canvas.getContext('2d');
        const isBar = data.type === 'bar_chart' || widget.vizType === 'bar_chart';
        new Chart(ctx, {
            type: isBar ? 'bar' : 'line',
            data: {
                labels: data.labels,
                datasets: data.datasets.map((ds, i) => ({
                    label: ds.label,
                    data: ds.data,
                    borderColor: colors[i % colors.length],
                    backgroundColor: isBar ? colors[i % colors.length] + '40' : colors[i % colors.length],
                    borderWidth: 2,
                    fill: !isBar,
                    tension: 0.3,
                    pointRadius: isBar ? 0 : 2,
                })),
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: { display: data.datasets.length > 1, position: 'bottom', labels: { font: { size: 10 } } },
                },
                scales: {
                    x: { grid: { display: false }, ticks: { font: { size: 9 } } },
                    y: { grid: { color: '#f1f5f9' }, ticks: { font: { size: 9 } } },
                },
            },
        });
    }

    function renderTable(data, widget) {
        const raw = data.data || {};
        const entries = Object.entries(raw);
        if (entries.length === 0) return '<div class="text-sm text-slate-400">No data</div>';
        const keys = Object.keys(entries[0][1] || {});
        return `
            <div class="overflow-x-auto">
                <table class="w-full text-xs">
                    <thead>
                        <tr class="text-left text-slate-400 font-bold uppercase">
                            <th class="pb-2 pr-2">Source</th>
                            ${keys.map(k => `<th class="pb-2 pr-2">${k}</th>`).join('')}
                        </tr>
                    </thead>
                    <tbody>
                        ${entries.map(([key, row]) => `
                            <tr class="border-t border-slate-100 text-slate-700">
                                <td class="py-1.5 pr-2 font-medium">${key}</td>
                                ${keys.map(k => `<td class="py-1.5 pr-2">${row[k] ?? '--'}</td>`).join('')}
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    }

    function addWidget(metric, label) {
        const id = 'w-' + (++widgetIdCounter);
        const vizType = getDefaultVizType(metric);
        widgets.push({ id, metric, label, vizType });
        buildReport();
    }

    function removeWidget(id) {
        widgets = widgets.filter(w => w.id !== id);
        buildReport();
    }

    function openConfigPanel(widget, data) {
        currentConfigWidget = widget;
        const panel = document.getElementById('widget-config-panel');
        const content = document.getElementById('config-content');
        panel.classList.remove('hidden');

        const vizOpts = ['number_card', 'bar_chart', 'line_chart', 'pie_chart', 'table', 'funnel'];
        content.innerHTML = `
            <div class="space-y-4">
                <div>
                    <label class="text-xs font-bold text-slate-500 uppercase block mb-1">Widget</label>
                    <p class="text-sm font-bold text-slate-900">${widget.label}</p>
                </div>
                <div>
                    <label class="text-xs font-bold text-slate-500 uppercase block mb-1">Visualization</label>
                    <select id="config-viz-type" class="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm">
                        ${vizOpts.map(v => `<option value="${v}" ${widget.vizType === v ? 'selected' : ''}>${v.replace('_', ' ')}</option>`).join('')}
                    </select>
                </div>
                <div>
                    <label class="text-xs font-bold text-slate-500 uppercase block mb-1">Preview</label>
                    <div class="text-xs text-slate-500 bg-slate-50 rounded-lg p-2">
                        ${data.type === 'number_card' ? `Value: ${data.value}${data.suffix}` : ''}
                        ${data.type === 'funnel' ? `${data.stages?.length || 0} stages` : ''}
                        ${data.type === 'pie_chart' ? `${data.labels?.length || 0} slices` : ''}
                        ${(data.type === 'line_chart' || data.type === 'bar_chart') ? `${data.labels?.length || 0} data points` : ''}
                        ${data.type === 'table' ? `${Object.keys(data.data || {}).length} rows` : ''}
                    </div>
                </div>
                <button id="apply-viz-config" class="w-full px-4 py-2 bg-violet-600 text-white text-sm font-bold rounded-lg hover:bg-violet-700">Apply</button>
            </div>
        `;
        document.getElementById('apply-viz-config')?.addEventListener('click', () => {
            const sel = document.getElementById('config-viz-type').value;
            const w = widgets.find(w => w.id === widget.id);
            if (w) w.vizType = sel;
            panel.classList.add('hidden');
            buildReport();
        });
    }

    document.getElementById('close-config')?.addEventListener('click', () => {
        document.getElementById('widget-config-panel')?.classList.add('hidden');
    });

    function initDropZone() {
        const dropZone = document.getElementById('drop-zone');
        if (!dropZone) return;
        dropZone.addEventListener('dragover', e => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'copy';
            dropZone.classList.add('drag-over');
        });
        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('drag-over');
        });
        dropZone.addEventListener('drop', e => {
            e.preventDefault();
            dropZone.classList.remove('drag-over');
            try {
                const data = JSON.parse(e.dataTransfer.getData('text/plain'));
                if (data.metric && data.label) {
                    addWidget(data.metric, data.label);
                }
            } catch (err) {
                // ignore
            }
        });
    }

    async function saveReport() {
        const name = document.getElementById('report-name').value || 'Untitled Report';
        const config = buildConfig();
        const url = reportId ? `${API_BASE}/${reportId}` : `${API_BASE}/save`;
        const method = reportId ? 'PUT' : 'POST';
        const body = reportId ? JSON.stringify({ name, config }) : JSON.stringify({ name, config });
        try {
            const resp = await fetch(url, {
                method,
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body,
            });
            if (!resp.ok) throw new Error('Save failed');
            const data = await resp.json();
            if (data.id) reportId = data.id;
            showToast('Report saved successfully');
        } catch (e) {
            console.error('Save error:', e);
            showToast('Failed to save report', 'error');
        }
    }

    async function exportReport(format) {
        if (reportId) {
            window.open(`${API_BASE}/${reportId}/export/${format}`, '_blank');
            return;
        }
        const config = buildConfig();
        try {
            const resp = await fetch(API_BASE + '/build', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(config),
            });
            if (!resp.ok) throw new Error('Build failed');
            const data = await resp.json();

            if (format === 'csv') {
                const csvResp = await fetch(API_BASE + '/build', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({ metrics: config.metrics, filters: config.filters, group_by: config.group_by, visualizations: config.visualizations, export_format: 'csv' }),
                });
            }
        } catch (e) {
            console.error('Export error:', e);
            showToast('Export failed', 'error');
        }
    }

    function showToast(msg, type = 'success') {
        const existing = document.querySelector('.report-toast');
        if (existing) existing.remove();
        const div = document.createElement('div');
        div.className = `report-toast fixed bottom-6 right-6 px-5 py-3 rounded-xl shadow-xl text-sm font-bold text-white z-50 ${type === 'error' ? 'bg-rose-600' : 'bg-emerald-600'}`;
        div.textContent = msg;
        document.body.appendChild(div);
        setTimeout(() => div.remove(), 3000);
    }

    document.getElementById('btn-save')?.addEventListener('click', saveReport);
    document.getElementById('date-preset')?.addEventListener('change', buildReport);

    document.querySelectorAll('.export-btn').forEach(btn => {
        btn.addEventListener('click', () => exportReport(btn.dataset.format));
    });

    document.getElementById('btn-schedule')?.addEventListener('click', () => {
        if (!reportId) {
            showToast('Save the report first before scheduling', 'error');
            return;
        }
        document.getElementById('schedule-modal')?.classList.remove('hidden');
    });
    document.getElementById('schedule-cancel')?.addEventListener('click', () => {
        document.getElementById('schedule-modal')?.classList.add('hidden');
    });
    document.getElementById('schedule-save')?.addEventListener('click', async () => {
        const frequency = document.getElementById('schedule-frequency').value;
        const recipientsRaw = document.getElementById('schedule-recipients').value;
        const recipients = recipientsRaw.split(',').map(r => r.trim()).filter(Boolean);
        try {
            const resp = await fetch(`${API_BASE}/${reportId}/schedule`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ frequency, recipients }),
            });
            if (!resp.ok) throw new Error('Schedule failed');
            document.getElementById('schedule-modal').classList.add('hidden');
            showToast('Report scheduled successfully');
        } catch (e) {
            console.error('Schedule error:', e);
            showToast('Failed to schedule', 'error');
        }
    });

    async function loadReport(id) {
        reportId = id;
        try {
            const resp = await fetch(`${API_BASE}/${id}`, { credentials: 'include' });
            if (!resp.ok) throw new Error('Load failed');
            const data = await resp.json();
            document.getElementById('report-name').value = data.name;
            if (data.config && data.config.metrics) {
                widgets = data.config.metrics.map((m, i) => ({
                    id: 'w-' + (++widgetIdCounter),
                    metric: typeof m === 'string' ? m : m.metric,
                    label: METRICS_META.find(meta => meta.key === (typeof m === 'string' ? m : m.metric))?.label || m,
                    vizType: (data.config.visualizations || []).find(v => v.metric === (typeof m === 'string' ? m : m.metric))?.type || getDefaultVizType(typeof m === 'string' ? m : m.metric),
                }));
                buildReport();
            }
        } catch (e) {
            console.error('Load report error:', e);
        }
    }

    const urlParams = new URLSearchParams(window.location.search);
    const loadId = urlParams.get('id');
    if (loadId) {
        loadReport(parseInt(loadId));
    }

    if (document.getElementById('drop-zone')) {
        populateMetricsList();
        initDropZone();
        buildReport();
    }
})();
