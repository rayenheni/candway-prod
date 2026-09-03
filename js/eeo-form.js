(function() {
    'use strict';

    document.addEventListener('DOMContentLoaded', function() {
        const form = document.getElementById('eeoForm');
        if (!form) return;
        const skipBtn = document.getElementById('skipBtn');
        const successMsg = document.getElementById('successMessage');
        const appIdInput = document.getElementById('applicationId');

        const params = new URLSearchParams(window.location.search);
        const applicationId = params.get('application_id');
        if (applicationId) {
            appIdInput.value = applicationId;
        }

        async function submitEEO(data) {
            try {
                const result = await window.fetchAPI('/candidate/eeo/submit', {
                    method: 'POST',
                    body: JSON.stringify(data)
                });
                return result;
            } catch (e) {
                console.error('EEO submit error:', e);
                throw e;
            }
        }

        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            const formData = new FormData(form);
            const data = {
                application_id: parseInt(appIdInput.value, 10),
                consent_given: true,
                gender: formData.get('gender') || null,
                race_ethnicity: formData.get('race_ethnicity') || null,
                veteran_status: formData.get('veteran_status') || null,
                disability_status: formData.get('disability_status') || null,
                age_group: formData.get('age_group') || null,
            };

            try {
                await submitEEO(data);
                form.classList.add('hidden');
                successMsg.classList.remove('hidden');
            } catch (e) {
                if (typeof Components !== 'undefined' && Components.showToast) {
                    Components.showToast('Failed to submit EEO information. Please try again.', 'error');
                } else {
                    alert('Failed to submit. Please try again.');
                }
            }
        });

        skipBtn.addEventListener('click', async function() {
            if (!appIdInput.value) {
                window.location.href = '/candidate/applications';
                return;
            }
            try {
                await submitEEO({
                    application_id: parseInt(appIdInput.value, 10),
                    consent_given: false,
                    gender: null,
                    race_ethnicity: null,
                    veteran_status: null,
                    disability_status: null,
                    age_group: null,
                });
                form.classList.add('hidden');
                successMsg.classList.remove('hidden');
            } catch (e) {
                window.location.href = '/candidate/applications';
            }
        });
    });
})();
