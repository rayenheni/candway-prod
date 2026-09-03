(function() {
    'use strict';

    window.EEODashboard = {
        charts: {},

        init: function() {
            for (let y = new Date().getFullYear(); y >= 2020; y--) {
                const opt = document.createElement('option');
                opt.value = y;
                opt.textContent = y;
                document.getElementById('eeo1Year').appendChild(opt);
            }
            this.refresh();
        },

        refresh: function() {
            this.loadOverview();
            this.loadPipeline();
            this.loadSelection();
            this.loadTrends(12);
            this.loadEEO1();
            this.loadCompliance();
        },

        switchTab: function(tab) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
            document.querySelectorAll('.tab-btn').forEach(el => {
                el.classList.remove('text-indigo-600', 'border-b-2', 'border-indigo-600');
                el.classList.add('text-slate-500');
            });
            const target = document.getElementById(tab + '-tab');
            if (target) target.classList.remove('hidden');
            const btn = document.querySelector(`[data-tab="${tab}"]`);
            if (btn) {
                btn.classList.remove('text-slate-500');
                btn.classList.add('text-indigo-600', 'border-b-2', 'border-indigo-600');
            }
        },

        async loadOverview() {
            try {
                const result = await window.fetchAPI('/recruiter/eeo/dashboard');
                if (!result || !result.success) return;
                const { stats, compliance, trends } = result;

                document.getElementById('coverageRate').textContent = (stats.coverage_rate || 0) + '%';
                document.getElementById('totalEEO').textContent = stats.total_applicants_with_eeo || 0;
                document.getElementById('totalApplicants').textContent = stats.total_applicants || 0;
                document.getElementById('genderBalance').textContent = (stats.gender_balance_ratio || 0) + '%';
                document.getElementById('impactFlags').textContent = stats.adverse_impact_flags || 0;

                const riskBadge = document.getElementById('riskBadge');
                if (compliance.risk_score === 'high') {
                    riskBadge.textContent = 'High Risk';
                    riskBadge.className = 'px-3 py-1 rounded-full text-xs font-bold uppercase bg-red-100 text-red-700';
                } else if (compliance.risk_score === 'medium') {
                    riskBadge.textContent = 'Medium Risk';
                    riskBadge.className = 'px-3 py-1 rounded-full text-xs font-bold uppercase bg-amber-100 text-amber-700';
                } else {
                    riskBadge.textContent = 'Low Risk';
                    riskBadge.className = 'px-3 py-1 rounded-full text-xs font-bold uppercase bg-green-100 text-green-700';
                }

                const suggestions = document.getElementById('suggestionsList');
                suggestions.innerHTML = '';
                if (compliance.suggestions && compliance.suggestions.length > 0) {
                    compliance.suggestions.forEach(s => {
                        const li = document.createElement('li');
                        li.className = 'text-sm text-slate-600 flex items-start gap-2';
                        XSS.safeSetHTML(li, '<i class="fas fa-lightbulb text-amber-400 mt-0.5"></i> ' + XSS.escapeHTML(s));
                        suggestions.appendChild(li);
                    });
                } else {
                    suggestions.innerHTML = '<li class="text-sm text-green-600"><i class="fas fa-check-circle mr-1"></i> No compliance issues detected.</li>';
                }

                if (trends && trends.months && trends.months.length > 0) {
                    this.renderTrendChart('overviewTrendChart', trends);
                }
            } catch (e) {
                console.error('Failed to load overview:', e);
            }
        },

        async loadPipeline() {
            const groupBy = document.getElementById('pipelineGroupBy').value;
            try {
                const result = await window.fetchAPI(`/recruiter/eeo/pipeline-diversity?group_by=${groupBy}`);
                if (!result || !result.success) return;
                const diversity = result.diversity;

                if (this.charts.pipeline) this.charts.pipeline.destroy();

                const ctx = document.getElementById('pipelineChart').getContext('2d');
                const colors = ['#8b5cf6', '#a78bfa', '#c4b5fd', '#7c3aed', '#6d28d9', '#ddd6fe', '#f5f3ff', '#ede9fe'];

                const datasets = diversity.groups.map((group, i) => ({
                    label: group,
                    data: diversity.stages.map(s => diversity.data[s][i] || 0),
                    backgroundColor: colors[i % colors.length],
                    borderRadius: 4,
                }));

                this.charts.pipeline = new Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels: diversity.stages.map(s => s.charAt(0).toUpperCase() + s.slice(1)),
                        datasets: datasets,
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'bottom',
                                labels: { font: { family: 'Outfit', size: 11 }, padding: 16, usePointStyle: true }
                            },
                            tooltip: {
                                callbacks: {
                                    label: function(ctx) {
                                        // TODO: move to backend — stage totals and percentages
                                        const stage = ctx.chart.data.labels[ctx.dataIndex].toLowerCase();
                                        const total = diversity.data[stage].reduce((a, b) => a + b, 0);
                                        const pct = total > 0 ? ((ctx.raw / total) * 100).toFixed(1) : 0;
                                        return ctx.dataset.label + ': ' + ctx.raw + ' (' + pct + '%)';
                                    }
                                }
                            }
                        },
                        scales: {
                            x: { stacked: true, grid: { display: false } },
                            y: { stacked: true, grid: { color: '#f1f5f9' }, border: { display: false } }
                        }
                    }
                });

                const repContainer = document.getElementById('repTableContainer');
                let tableHtml = '<table class="w-full text-sm"><thead><tr class="border-b border-slate-200"><th class="text-left py-2 font-semibold text-slate-600">Stage</th>';
                diversity.groups.forEach(g => {
                    tableHtml += `<th class="text-right py-2 font-semibold text-slate-600 px-2">${g}</th>`;
                });
                tableHtml += '</tr></thead><tbody>';
                diversity.stages.forEach(stage => {
                    tableHtml += `<tr class="border-b border-slate-100"><td class="py-2 font-medium text-slate-700">${stage.charAt(0).toUpperCase() + stage.slice(1)}</td>`;
                    diversity.groups.forEach(g => {
                        const pct = diversity.representation_pct[stage][g] || 0;
                        tableHtml += `<td class="text-right py-2 text-slate-600 px-2">${pct}%</td>`;
                    });
                    tableHtml += '</tr>';
                });
                tableHtml += '</tbody></table>';
                repContainer.innerHTML = tableHtml;
            } catch (e) {
                console.error('Failed to load pipeline:', e);
            }
        },

        async loadSelection() {
            const groupBy = document.getElementById('selectionGroupBy').value;
            try {
                const result = await window.fetchAPI(`/recruiter/eeo/selection-rates?group_by=${groupBy}`);
                if (!result || !result.success) return;
                const sr = result.selection_rates;

                const container = document.getElementById('selectionTableContainer');
                const transitions = ['applied_to_screened', 'screened_to_interviewed', 'interviewed_to_offered', 'offered_to_hired'];
                const transLabels = { 'applied_to_screened': 'Applied → Screened', 'screened_to_interviewed': 'Screened → Interviewed', 'interviewed_to_offered': 'Interviewed → Offered', 'offered_to_hired': 'Offered → Hired' };

                let tableHtml = '<table class="w-full text-sm"><thead><tr class="border-b border-slate-200"><th class="text-left py-2 font-semibold text-slate-600">Transition</th>';
                Object.keys(sr.groups).forEach(g => {
                    tableHtml += `<th class="text-right py-2 font-semibold text-slate-600 px-2">${g}</th>`;
                });
                tableHtml += '<th class="text-right py-2 font-semibold text-slate-600 px-2">4/5ths</th></tr></thead><tbody>';

                transitions.forEach(t => {
                    const ai = sr.adverse_impact[t] || {};
                    const passes = ai.passes_4_5ths !== false;
                    const badgeClass = passes ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700';
                    const badgeText = passes ? 'Pass' : 'Fail';

                    tableHtml += `<tr class="border-b border-slate-100"><td class="py-2 font-medium text-slate-700">${transLabels[t]}</td>`;
                    Object.keys(sr.groups).forEach(g => {
                        const rate = sr.groups[g][t] || 0;
                        const flagged = ai.flagged_group === g && !passes;
                        tableHtml += `<td class="text-right py-2 px-2 ${flagged ? 'text-red-600 font-bold bg-red-50' : 'text-slate-600'}">${rate}%</td>`;
                    });
                    tableHtml += `<td class="text-right py-2 px-2"><span class="px-2 py-0.5 rounded text-xs font-bold ${badgeClass}">${badgeText}</span></td>`;
                    tableHtml += '</tr>';
                });
                tableHtml += '</tbody></table>';
                container.innerHTML = tableHtml;

                const impactBox = document.getElementById('adverseImpactBox');
                if (sr.four_fifths_rule) {
                    impactBox.classList.remove('hidden');
                    impactBox.className = 'rounded-2xl p-4 card-shadow bg-red-50 border border-red-200 mt-4';
                    XSS.safeSetHTML(impactBox, '<div class="flex items-start gap-3"><i class="fas fa-exclamation-circle text-red-500 mt-1"></i><div><p class="font-semibold text-red-800 text-sm">Adverse Impact Detected</p><p class="text-sm text-red-700 mt-1">' + XSS.escapeHTML(sr.four_fifths_rule) + '</p></div></div>');
                } else {
                    impactBox.classList.add('hidden');
                }
            } catch (e) {
                console.error('Failed to load selection rates:', e);
            }
        },

        async loadTrends(months) {
            document.querySelectorAll('.trend-btn').forEach(b => {
                b.className = 'trend-btn px-3 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wider ' +
                    (parseInt(b.dataset.months) === months ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-500');
            });
            try {
                const result = await window.fetchAPI(`/recruiter/eeo/trends?months=${months}`);
                if (!result || !result.success) return;
                this.renderTrendChart('trendChart', result.trends);
            } catch (e) {
                console.error('Failed to load trends:', e);
            }
        },

        renderTrendChart(canvasId, trends) {
            if (this.charts[canvasId]) this.charts[canvasId].destroy();

            const ctx = document.getElementById(canvasId).getContext('2d');
            const colors = ['#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#3b82f6', '#ef4444', '#8b5cf6', '#6366f1'];

            const datasets = Object.keys(trends.data || {}).map((group, i) => ({
                label: group,
                data: trends.data[group],
                borderColor: colors[i % colors.length],
                backgroundColor: colors[i % colors.length] + '20',
                fill: true,
                tension: 0.4,
                borderWidth: 2,
                pointRadius: 3,
                pointHoverRadius: 5,
            }));

            this.charts[canvasId] = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: trends.months || [],
                    datasets: datasets,
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: { font: { family: 'Outfit', size: 11 }, padding: 16, usePointStyle: true }
                        },
                        tooltip: {
                            callbacks: {
                                label: function(ctx) { return ctx.dataset.label + ': ' + ctx.raw + '%'; }
                            }
                        }
                    },
                    scales: {
                        x: { grid: { display: false } },
                        y: { grid: { color: '#f1f5f9' }, border: { display: false }, beginAtZero: true, max: 100 }
                    }
                }
            });
        },

        async loadEEO1() {
            const year = document.getElementById('eeo1Year').value;
            try {
                const result = await window.fetchAPI(`/recruiter/eeo/eeo1-report?year=${year}`);
                if (!result || !result.success) return;
                const eeo1 = result.eeo1;

                const container = document.getElementById('eeo1TableContainer');
                let tableHtml = '<div class="overflow-x-auto"><table class="w-full text-xs"><thead><tr class="border-b border-slate-200">';
                tableHtml += '<th class="text-left py-2 font-semibold text-slate-600">Job Category</th>';
                (eeo1.race_groups || []).forEach(race => {
                    tableHtml += `<th class="text-center py-2 font-semibold text-slate-600 px-1" colspan="2">${race}</th>`;
                });
                tableHtml += '<th class="text-center py-2 font-semibold text-slate-600 px-2">Total</th></tr>';
                tableHtml += '<tr class="border-b border-slate-200"><th></th>';
                (eeo1.race_groups || []).forEach(() => {
                    tableHtml += '<th class="text-center text-[10px] text-slate-400 font-medium pb-1">M</th><th class="text-center text-[10px] text-slate-400 font-medium pb-1">F</th>';
                });
                tableHtml += '<th></th></tr></thead><tbody>';

                (eeo1.job_categories || []).forEach(cat => {
                    const row = eeo1.matrix[cat] || {};
                    tableHtml += `<tr class="border-b border-slate-100"><td class="py-2 font-medium text-slate-700">${cat}</td>`;
                    (eeo1.race_groups || []).forEach(race => {
                        const cell = row[race] || {};
                        tableHtml += `<td class="text-center py-2 text-slate-600">${cell.male || 0}</td>`;
                        tableHtml += `<td class="text-center py-2 text-slate-600">${cell.female || 0}</td>`;
                    });
                    tableHtml += `<td class="text-center py-2 font-bold text-slate-700">${row.total || 0}</td>`;
                    tableHtml += '</tr>';
                });
                tableHtml += '</tbody></table></div>';
                container.innerHTML = tableHtml;
            } catch (e) {
                console.error('Failed to load EEO-1:', e);
            }
        },

        async loadCompliance() {
            try {
                const result = await window.fetchAPI('/recruiter/eeo/compliance-summary');
                if (!result || !result.success) return;
                const c = result.compliance;

                const riskColors = { high: 'bg-red-100 text-red-700 border-red-200', medium: 'bg-amber-100 text-amber-700 border-amber-200', low: 'bg-green-100 text-green-700 border-green-200' };
                const riskDiv = document.getElementById('complianceRisk');
                XSS.safeSetHTML(riskDiv, `<div class="p-4 rounded-xl border ${riskColors[c.risk_score] || riskColors.low}">
                    <span class="text-lg font-bold uppercase">${XSS.escapeHTML(c.risk_score)} Risk</span>
                    <p class="text-sm mt-1">${XSS.escapeHTML(c.adverse_impact_flags)} adverse impact flag(s) · ${XSS.escapeHTML(c.coverage_rate)}% coverage rate</p>
                </div>`);

                const suggestions = document.getElementById('complianceSuggestions');
                suggestions.innerHTML = '';
                if (c.suggestions && c.suggestions.length > 0) {
                    c.suggestions.forEach(s => {
                        const li = document.createElement('li');
                        li.className = 'text-sm text-slate-600 flex items-start gap-2';
                        XSS.safeSetHTML(li, '<i class="fas fa-arrow-right text-indigo-400 mt-0.5"></i> ' + XSS.escapeHTML(s));
                        suggestions.appendChild(li);
                    });
                } else {
                    suggestions.innerHTML = '<li class="text-sm text-green-600"><i class="fas fa-check-circle mr-1"></i> All compliance checks passed.</li>';
                }

                const cov = document.getElementById('coverageStats');
                cov.innerHTML = `
                    <div class="flex justify-between items-center p-3 bg-slate-50 rounded-xl">
                        <span class="text-sm text-slate-600">EEO Coverage Rate</span>
                        <span class="font-bold text-slate-900">${c.coverage_rate}%</span>
                    </div>
                    <div class="flex justify-between items-center p-3 bg-slate-50 rounded-xl">
                        <span class="text-sm text-slate-600">Adverse Impact Flags</span>
                        <span class="font-bold ${c.adverse_impact_flags > 0 ? 'text-red-600' : 'text-green-600'}">${c.adverse_impact_flags}</span>
                    </div>
                    <div class="flex justify-between items-center p-3 bg-slate-50 rounded-xl">
                        <span class="text-sm text-slate-600">Risk Level</span>
                        <span class="font-bold uppercase text-${c.risk_score === 'high' ? 'red' : c.risk_score === 'medium' ? 'amber' : 'green'}-600">${c.risk_score}</span>
                    </div>
                `;
            } catch (e) {
                console.error('Failed to load compliance:', e);
            }
        },

        async exportCSV() {
            try {
                const groupBy = document.getElementById('pipelineGroupBy').value;
                const year = document.getElementById('eeo1Year').value || new Date().getFullYear();
                const link = document.createElement('a');
                link.href = `${window.CONFIG.API_BASE_URL}${window.CONFIG.API_PREFIX}/recruiter/eeo/export/csv?group_by=${groupBy}&year=${year}`;
                link.target = '_blank';
                link.click();
            } catch (e) {
                console.error('Export error:', e);
            }
        },

        exportEEO1: function() {
            this.exportCSV();
        },
    };
})();
