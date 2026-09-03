(function() {
    'use strict';

    window.EEOCoverage = {
        chart: null,

        init: function() {
            this.loadData();
        },

        async loadData() {
            try {
                const result = await window.fetchAPI('/recruiter/eeo/coverage-detail');
                if (!result || !result.success) return;
                const data = result.coverage;

                document.getElementById('overallRate').textContent = (data.overall.coverage_rate || 0) + '%';
                document.getElementById('totalApps').textContent = data.overall.total_applicants || 0;
                document.getElementById('eeoProvided').textContent = data.overall.total_applicants_with_eeo || 0;
                document.getElementById('impactFlags').textContent = data.overall.adverse_impact_flags || 0;

                this.renderJobTable(data.by_job || []);
                this.renderTrendChart(data.trend || []);
            } catch (e) {
                console.error('Failed to load coverage data:', e);
            }
        },

        renderJobTable(jobs) {
            const container = document.getElementById('jobCoverageTable');
            if (!jobs || jobs.length === 0) {
                container.innerHTML = '<p class="text-sm text-slate-400 italic">No job data available.</p>';
                return;
            }

            let html = '<table class="w-full text-sm"><thead><tr class="border-b border-slate-200">';
            html += '<th class="text-left py-2 font-semibold text-slate-600">Job Title</th>';
            html += '<th class="text-right py-2 font-semibold text-slate-600 px-2">Applicants</th>';
            html += '<th class="text-right py-2 font-semibold text-slate-600 px-2">EEO Provided</th>';
            html += '<th class="text-right py-2 font-semibold text-slate-600 px-2">Coverage</th>';
            html += '</tr></thead><tbody>';

            jobs.forEach(job => {
                const rateColor = job.coverage_rate >= 70 ? 'text-green-600' : (job.coverage_rate >= 40 ? 'text-amber-600' : 'text-red-600');
                html += `<tr class="border-b border-slate-100">
                    <td class="py-2 font-medium text-slate-700">${job.job_title || 'Untitled'}</td>
                    <td class="text-right py-2 text-slate-600 px-2">${job.total_applicants}</td>
                    <td class="text-right py-2 text-slate-600 px-2">${job.eeo_provided}</td>
                    <td class="text-right py-2 font-bold ${rateColor} px-2">${job.coverage_rate}%</td>
                </tr>`;
            });

            html += '</tbody></table>';
            container.innerHTML = html;
        },

        renderTrendChart(trend) {
            if (this.chart) this.chart.destroy();
            if (!trend || trend.length === 0) return;

            const ctx = document.getElementById('coverageTrendChart').getContext('2d');

            this.chart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: trend.map(t => t.month),
                    datasets: [{
                        label: 'Coverage Rate',
                        data: trend.map(t => t.coverage_rate),
                        borderColor: '#8b5cf6',
                        backgroundColor: '#8b5cf620',
                        fill: true,
                        tension: 0.4,
                        borderWidth: 2,
                        pointBackgroundColor: '#fff',
                        pointBorderColor: '#8b5cf6',
                        pointBorderWidth: 2,
                        pointRadius: 4,
                    }, {
                        label: 'Total Applicants',
                        data: trend.map(t => t.total_applicants),
                        borderColor: '#f59e0b',
                        backgroundColor: '#f59e0b20',
                        fill: true,
                        tension: 0.4,
                        borderWidth: 2,
                        pointBackgroundColor: '#fff',
                        pointBorderColor: '#f59e0b',
                        pointBorderWidth: 2,
                        pointRadius: 4,
                        yAxisID: 'y1',
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: { font: { family: 'Outfit', size: 11 }, padding: 16, usePointStyle: true }
                        }
                    },
                    scales: {
                        x: { grid: { display: false } },
                        y: { grid: { color: '#f1f5f9' }, border: { display: false }, beginAtZero: true, max: 100, title: { display: true, text: 'Coverage %' } },
                        y1: { position: 'right', grid: { display: false }, border: { display: false }, beginAtZero: true, title: { display: true, text: 'Applicants' } }
                    }
                }
            });
        },
    };
})();
