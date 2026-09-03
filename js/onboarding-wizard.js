/**
 * Candway Candidate Onboarding Wizard
 * Intelligent multi-step onboarding flow for AI Interview preparation
 * Uses onboarding.py API endpoints
 */

function getApiBaseUrl() {
    if (window.CONFIG && window.CONFIG.API_BASE_URL) {
        return window.CONFIG.API_BASE_URL;
    }
    return '';
}

const onboardingState = {
    currentStep: 1,
    role: null,
    cv_uploaded: false,
    detected_skills: [],
    detected_level: null,
    calibration_score: null,
    calibration_questions: [],
    calibration_answers: [],
    analysis_result: null,
    application_id: null
};

const ROLES = [
    { id: 'software_engineer', name: 'Software Engineer', icon: 'fa-code', desc: 'Full-stack, Frontend, Backend, DevOps' },
    { id: 'product_manager', name: 'Product Manager', icon: 'fa-box-open', desc: 'Strategy, Roadmap, Agile' },
    { id: 'data_scientist', name: 'Data Scientist', icon: 'fa-brain', desc: 'ML, Analytics, Python, AI' },
    { id: 'ux_designer', name: 'UX Designer', icon: 'fa-pencil-ruler', desc: 'UI/UX, Figma, Research' },
    { id: 'sales_executive', name: 'Sales Executive', icon: 'fa-chart-line', desc: 'B2B, SaaS, Enterprise' },
    { id: 'marketing_specialist', name: 'Marketing Specialist', icon: 'fa-bullhorn', desc: 'Digital, Content, SEO' }
];

const OnboardingWizard = {
    state: onboardingState,
    
    init() {
        try {
            console.log('[Onboarding] Initializing...');
            this.loadState();
            this.render();
            this.bindEvents();
            console.log('[Onboarding] Initialized, current step:', onboardingState.currentStep);
        } catch (e) {
            console.error('[Onboarding] Init error:', e);
            alert('Onboarding Error: ' + e.message);
        }
    },

    loadState() {
        const saved = localStorage.getItem('onboarding_state');
        if (saved) {
            try {
                const parsed = JSON.parse(saved);
                Object.assign(onboardingState, parsed);
            } catch (e) {
                console.warn('Failed to load onboarding state');
            }
        }
    },

    saveState() {
        const safe = { ...onboardingState };
        delete safe.analysis_result;
        localStorage.setItem('onboarding_state', JSON.stringify(safe));
    },

    async bindEvents() {
        document.addEventListener('click', (e) => {
            if (e.target.closest('[data-action="next"]')) this.nextStep();
            if (e.target.closest('[data-action="prev"]')) this.prevStep();
            if (e.target.closest('[data-action="select-role"]')) {
                const role = e.target.closest('[data-action="select-role"]').dataset.roleId;
                this.selectRole(role);
            }
            if (e.target.closest('[data-action="start-calibration"]')) this.startCalibration();
            if (e.target.closest('[data-action="finish"]')) this.finish();
        });

        const dropZone = document.getElementById('drop-zone');
        if (dropZone) {
            dropZone.addEventListener('dragover', (e) => {
                e.preventDefault();
                dropZone.classList.add('border-indigo-500', 'bg-indigo-50');
            });
            dropZone.addEventListener('dragleave', () => {
                dropZone.classList.remove('border-indigo-500', 'bg-indigo-50');
            });
            dropZone.addEventListener('drop', (e) => {
                e.preventDefault();
                dropZone.classList.remove('border-indigo-500', 'bg-indigo-50');
                const file = e.dataTransfer.files[0];
                if (file) this.handleFile(file);
            });
        }

        const fileInput = document.getElementById('cv-file-input');
        if (fileInput) {
            fileInput.addEventListener('change', (e) => {
                if (e.target.files[0]) this.handleFile(e.target.files[0]);
            });
        }
    },

    selectRole(roleId) {
        onboardingState.role = ROLES.find(r => r.id === roleId)?.name || roleId;
        this.saveState();
        this.nextStep();
    },

    handleFile(file) {
        const validTypes = ['.pdf', '.docx', '.doc', '.txt'];
        const ext = '.' + file.name.split('.').pop().toLowerCase();
        
        if (!validTypes.includes(ext)) {
            this.showError('Format non supporté. Utilisez PDF, DOCX ou TXT.');
            return;
        }
        
        if (file.size > 10 * 1024 * 1024) {
            this.showError('Fichier trop volumineux (max 10MB).');
            return;
        }

        this.showFilePreview(file);
        this.uploadCV(file);
    },

    showFilePreview(file) {
        const preview = document.getElementById('file-preview');
        const nameEl = document.getElementById('file-name');
        if (preview && nameEl) {
            nameEl.textContent = file.name;
            preview.classList.remove('hidden');
        }
        
        const uploadZone = document.getElementById('upload-zone');
        if (uploadZone) uploadZone.classList.add('hidden');
    },

    async uploadCV(file) {
        this.setLoading(true, 'Analyse du CV...');
        
        try {
            const reader = new FileReader();
            reader.readAsDataURL(file);
            
            await new Promise((resolve, reject) => {
                reader.onload = resolve;
                reader.onerror = reject;
            });
            
            const base64 = reader.result.split(',')[1];
            
            const data = await window.fetchAPI('/onboarding/analyze-cv-json', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    file_content: base64,
                    file_name: file.name,
                    declared_role: onboardingState.role || 'General'
                })
            });

            // Validate application_id is a valid positive integer
            if (!data.application_id || typeof data.application_id !== 'number' || data.application_id <= 0 || !Number.isInteger(data.application_id)) {
                throw new Error('Invalid response: no valid application created. Please try again.');
            }

            onboardingState.cv_uploaded = true;
            onboardingState.analysis_result = data;
            onboardingState.detected_skills = data.skills || [];
            onboardingState.detected_level = data.experience_level || 'Unknown';
            onboardingState.application_id = data.application_id;
            
            this.saveState();
            this.nextStep();
            
        } catch (error) {
            this.showError(error.message);
            this.setLoading(false);
        }
    },

    async startCalibration() {
        // Enforce application_id exists before proceeding
        if (!onboardingState.application_id) {
            this.showError('CV non analysé. Veuillez uploader votre CV d\'abord.');
            return;
        }
        
        this.setLoading(true, 'Génération des questions...');
        
        try {
            const analysis = onboardingState.analysis_result;
            
            const data = await window.fetchAPI('/onboarding/calibration-questions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    application_id: onboardingState.application_id,
                    role: onboardingState.role,
                    skills: onboardingState.detected_skills,
                    level: onboardingState.detected_level,
                    cv_summary: (analysis?.experience_timeline?.slice(0, 3) || []).map(e => 
                        `${e.role} at ${e.company}`
                    ).join('; ')
                })
            });

            onboardingState.calibration_questions = data.questions || [];
            
            this.saveState();
            this.nextStep();
            this.setLoading(false);
            
        } catch (error) {
            this.showError(error.message);
            this.setLoading(false);
        }
    },

    async submitCalibrationAnswer(questionIndex, answer) {
        if (!onboardingState.calibration_answers[questionIndex]) {
            onboardingState.calibration_answers[questionIndex] = {};
        }
        onboardingState.calibration_answers[questionIndex].answer = answer;
        this.saveState();
    },

    async finishCalibration() {
        // Enforce application_id exists before proceeding
        if (!onboardingState.application_id) {
            this.showError('Session invalide. Veuillez recommencer l\'onboarding.');
            return;
        }
        
        this.setLoading(true, 'Évaluation en cours...');
        
        try {
            const data = await window.fetchAPI('/onboarding/evaluate-calibration', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    application_id: onboardingState.application_id,
                    answers: onboardingState.calibration_answers.map((a, i) => ({
                        question_index: i,
                        answer: a.answer || ''
                    }))
                })
            });

            onboardingState.calibration_score = data.score_entity?.final_score ?? data.overall_score ?? data.score ?? 0;
            this.saveState();
            this.nextStep();
            
        } catch (error) {
            this.showError(error.message);
            this.setLoading(false);
        }
    },

    finish() {
        if (onboardingState.application_id) {
            localStorage.setItem('pending_interview_app_id', onboardingState.application_id);
            localStorage.setItem('active_app_id', onboardingState.application_id);
            console.log('[Onboarding] Set pending_interview_app_id:', onboardingState.application_id);
        }
        localStorage.removeItem('onboarding_state');
        window.location.href = '/candidate/interview';
    },

    nextStep() {
        console.log('[Onboarding] nextStep called, current:', onboardingState.currentStep);
        if (onboardingState.currentStep < 6) {
            onboardingState.currentStep++;
            this.saveState();
            this.render();
            console.log('[Onboarding] Moved to step:', onboardingState.currentStep);
        }
    },

    prevStep() {
        if (onboardingState.currentStep > 1) {
            onboardingState.currentStep--;
            this.saveState();
            this.render();
        }
    },

    setLoading(loading, message = '') {
        const loader = document.getElementById('global-loader');
        const msg = document.getElementById('loader-message');
        
        if (loader) {
            loader.classList.toggle('hidden', !loading);
        }
        if (msg) {
            msg.textContent = message;
        }
    },

    showError(message) {
        const toast = document.createElement('div');
        toast.className = 'fixed top-4 left-1/2 -translate-x-1/2 bg-red-500 text-white px-6 py-3 rounded-xl shadow-lg z-50 animate-fade-in';
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 5000);
    },

    render() {
        const container = document.getElementById('onboarding-content');
        if (!container) return;

        this.updateProgress();
        container.innerHTML = this.getStepTemplate();
        this.bindEvents();

        if (onboardingState.currentStep === 6) {
            setTimeout(() => this.renderWizardRadar(), 300);
        }
    },

    updateProgress() {
        const progressBar = document.getElementById('progress-bar');
        const steps = document.querySelectorAll('.step-indicator .step-item');
        
        if (progressBar) {
            progressBar.style.width = `${(onboardingState.currentStep / 6) * 100}%`;
        }
        
        steps?.forEach((step, i) => {
            const num = i + 1;
            step.classList.toggle('step-active', num === onboardingState.currentStep);
            step.classList.toggle('step-completed', num < onboardingState.currentStep);
        });
    },

    getStepTemplate() {
        const step = onboardingState.currentStep;
        
        switch(step) {
            case 1: return this.getWelcomeTemplate();
            case 2: return this.getRoleSelectionTemplate();
            case 3: return this.getCVUploadTemplate();
            case 4: return this.getAIFeedbackTemplate();
            case 5: return this.getCalibrationTemplate();
            case 6: return this.getFinalTemplate();
            default: return '';
        }
    },

    getWelcomeTemplate() {
        return `
            <div class="step-content animate-fade-in-up">
                <div class="text-center max-w-lg mx-auto">
                    <div class="w-24 h-24 bg-indigo-100 rounded-full flex items-center justify-center mx-auto mb-8">
                        <i class="fas fa-brain text-4xl text-indigo-600"></i>
                    </div>
                    <h1 class="text-4xl lg:text-5xl font-black text-slate-900 mb-6 tracking-tight">
                        We don't trust <span class="gradient-text">CVs.</span>
                    </h1>
                    <p class="text-xl text-slate-500 mb-10 font-medium">
                        We test real skills. Let's verify what you actually know.
                    </p>
                    <button data-action="next" class="w-full max-w-md py-5 bg-indigo-600 text-white rounded-2xl font-black text-lg shadow-xl hover:bg-indigo-700 transition-all flex items-center justify-center gap-3">
                        Start <i class="fas fa-arrow-right"></i>
                    </button>
                </div>
            </div>
        `;
    },

    getRoleSelectionTemplate() {
        const rolesHtml = ROLES.map(role => `
            <button data-action="select-role" data-role-id="${role.id}" 
                class="p-6 bg-white border-2 border-slate-100 rounded-2xl hover:border-indigo-500 hover:bg-indigo-50 transition-all text-left">
                <div class="w-12 h-12 bg-indigo-100 rounded-xl flex items-center justify-center mb-4">
                    <i class="fas ${role.icon} text-xl text-indigo-600"></i>
                </div>
                <h3 class="font-bold text-slate-900 text-lg mb-1">${role.name}</h3>
                <p class="text-sm text-slate-400">${role.desc}</p>
            </button>
        `).join('');

        return `
            <div class="step-content animate-fade-in-up">
                <div class="text-center mb-8">
                    <h1 class="text-3xl lg:text-4xl font-black text-slate-900 mb-4 tracking-tight">
                        Choose your <span class="gradient-text">Target Role</span>
                    </h1>
                    <p class="text-slate-500 font-medium">This helps our AI tailor the verification specifically for you.</p>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
                    ${rolesHtml}
                </div>
                <div class="flex gap-4">
                    <button data-action="prev" class="w-1/3 py-5 bg-white border border-slate-200 text-slate-400 hover:text-slate-900 rounded-2xl font-bold transition-all">
                        Back
                    </button>
                </div>
            </div>
        `;
    },

    getCVUploadTemplate() {
        return `
            <div class="step-content animate-fade-in-up">
                <div class="text-center mb-8">
                    <h1 class="text-3xl lg:text-4xl font-black text-slate-900 mb-4 tracking-tight">
                        Upload <span class="gradient-text">Your CV</span>
                    </h1>
                    <p class="text-slate-500 font-medium">We support PDF and TXT. Max size 10MB.</p>
                </div>
                
                <div id="upload-zone" class="mb-6">
                    <label for="cv-file-input" id="drop-zone"
                        class="block w-full h-48 border-2 border-dashed border-slate-200 rounded-3xl bg-slate-50/50 hover:bg-white hover:border-indigo-500 transition-all cursor-pointer flex flex-col items-center justify-center gap-3">
                        <div class="w-12 h-12 bg-white text-indigo-600 rounded-xl flex items-center justify-center text-xl shadow-sm">
                            <i class="fas fa-file-pdf"></i>
                        </div>
                        <div class="text-center">
                            <p class="text-sm font-bold text-slate-700">Drop CV here</p>
                            <p class="text-xs text-slate-400 font-bold uppercase tracking-widest mt-0.5">PDF, DOCX or TXT</p>
                        </div>
                    </label>
                    <input type="file" id="cv-file-input" accept=".pdf,.docx,.doc,.txt" class="hidden">
                </div>

                <div id="file-preview" class="hidden mb-10 p-5 bg-emerald-50 border border-emerald-100 rounded-2xl flex items-center justify-between">
                    <div class="flex items-center gap-4">
                        <div class="w-12 h-12 bg-emerald-500 text-white rounded-xl flex items-center justify-center text-xl shadow-lg">
                            <i class="fas fa-file-pdf"></i>
                        </div>
                        <div class="text-start">
                            <p id="file-name" class="font-bold text-slate-800 text-sm truncate max-w-[180px]">resume.pdf</p>
                            <p class="text-xs text-emerald-600 font-bold uppercase">Ready</p>
                        </div>
                    </div>
                    <button onclick="document.getElementById('cv-file-input').value='';document.getElementById('file-preview').classList.add('hidden');document.getElementById('upload-zone').classList.remove('hidden')" class="text-slate-300 hover:text-red-500 transition-colors">
                        <i class="fas fa-times text-lg"></i>
                    </button>
                </div>

                <div class="flex gap-4">
                    <button data-action="prev" class="w-1/3 py-5 bg-white border border-slate-200 text-slate-400 hover:text-slate-900 rounded-2xl font-bold transition-all">
                        Back
                    </button>
                </div>
            </div>
            
            <div id="global-loader" class="hidden fixed inset-0 bg-white/80 flex items-center justify-center z-50">
                <div class="text-center">
                    <div class="w-16 h-16 border-4 border-indigo-100 border-t-indigo-600 rounded-full animate-spin mb-4"></div>
                    <p id="loader-message" class="text-slate-600 font-medium">Chargement...</p>
                </div>
            </div>
        `;
    },

    getAIFeedbackTemplate() {
        const result = onboardingState.analysis_result || {};
        const intelligence = result.intelligence_layer || {};
        
        const skills = onboardingState.detected_skills.length > 0 
            ? onboardingState.detected_skills.slice(0, 8).map(s => `<span class="px-3 py-1 bg-indigo-50 text-indigo-600 rounded-full text-[11px] font-bold border border-indigo-100">${s}</span>`).join('')
            : '<span class="text-slate-400">No skills detected</span>';

        const marketPositioning = result.market_positioning || "Dynamic profile with cross-functional potential.";
        const fastestImpact = result.explainability?.fastest_impact || "Immediate contribution to technical execution and workflow optimization.";

        return `
            <div class="step-content animate-fade-in-up">
                <div class="text-center mb-8">
                    <div class="w-16 h-16 bg-indigo-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                        <i class="fas fa-microchip text-2xl text-indigo-600"></i>
                    </div>
                    <h1 class="text-3xl lg:text-4xl font-black text-slate-900 mb-2 tracking-tight">
                        AI <span class="gradient-text">Profile Analysis</span>
                    </h1>
                    <p class="text-slate-500 font-medium">Deep insights extracted from your experience.</p>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                    <div class="bg-slate-50 rounded-2xl p-5 border border-slate-100">
                        <p class="text-[10px] text-slate-400 font-black uppercase tracking-widest mb-3">Market Positioning</p>
                        <p class="text-sm text-slate-700 leading-relaxed font-medium">${marketPositioning}</p>
                    </div>
                    <div class="bg-indigo-50/30 rounded-2xl p-5 border border-indigo-100/50">
                        <p class="text-[10px] text-indigo-400 font-black uppercase tracking-widest mb-3">Fastest Impact</p>
                        <p class="text-sm text-slate-700 leading-relaxed font-medium">${fastestImpact}</p>
                    </div>
                </div>

                <div class="bg-white border-2 border-slate-50 rounded-3xl p-6 mb-8 shadow-sm">
                    <div class="flex items-center justify-between mb-6">
                        <div>
                            <p class="text-[10px] text-slate-400 font-black uppercase tracking-widest mb-1">Detected Role</p>
                            <p class="font-black text-slate-900 text-lg">${result.detected_industry || onboardingState.role}</p>
                        </div>
                        <div class="text-right">
                            <p class="text-[10px] text-slate-400 font-black uppercase tracking-widest mb-1">Experience Level</p>
                            <p class="font-black text-indigo-600 text-lg">${onboardingState.detected_level}</p>
                        </div>
                    </div>
                    <div>
                        <p class="text-[10px] text-slate-400 font-black uppercase tracking-widest mb-3">Extracted Skill Cloud</p>
                        <div class="flex flex-wrap gap-2">${skills}</div>
                    </div>
                </div>

                <button data-action="start-calibration" class="w-full py-5 bg-indigo-600 text-white rounded-2xl font-black text-lg shadow-xl hover:bg-indigo-700 transition-all flex items-center justify-center gap-3">
                    Continue to Calibration <i class="fas fa-bolt ml-2"></i>
                </button>
            </div>
        `;
    },

    getCalibrationTemplate() {
        const questions = onboardingState.calibration_questions;
        
        return `
            <div class="step-content animate-fade-in-up">
                <div class="text-center mb-8">
                    <h1 class="text-3xl lg:text-4xl font-black text-slate-900 mb-4 tracking-tight">
                        Warm-up <span class="gradient-text">Check</span>
                    </h1>
                    <p class="text-slate-500 font-medium">3 easy questions to get you started.</p>
                </div>

                <div class="space-y-6 mb-10 max-h-[450px] overflow-y-auto px-2">
                    ${questions.length > 0 ? questions.map((q, i) => `
                        <div class="bg-white border border-slate-100 rounded-2xl p-6 shadow-sm">
                            <div class="flex items-center gap-3 mb-4">
                                <span class="w-6 h-6 bg-indigo-600 text-white rounded-lg flex items-center justify-center text-[10px] font-black">${i+1}</span>
                                <p class="font-black text-slate-800">${q.question || q}</p>
                            </div>
                            <div class="grid grid-cols-1 gap-3">
                                ${(q.options || ['A', 'B', 'C', 'D']).map(opt => `
                                    <label class="flex items-center p-4 border-2 border-slate-50 rounded-xl cursor-pointer hover:border-indigo-200 hover:bg-indigo-50/30 transition-all group has-[:checked]:border-indigo-600 has-[:checked]:bg-indigo-50">
                                        <input type="radio" name="q${i}" value="${opt}" class="hidden peer">
                                        <div class="w-5 h-5 border-2 border-slate-200 rounded-full flex items-center justify-center mr-4 peer-checked:border-indigo-600 peer-checked:bg-indigo-600 transition-all">
                                            <div class="w-2 h-2 bg-white rounded-full opacity-0 peer-checked:opacity-100"></div>
                                        </div>
                                        <span class="text-sm font-bold text-slate-600 group-hover:text-indigo-600 peer-checked:text-indigo-900">${opt}</span>
                                    </label>
                                `).join('')}
                            </div>
                        </div>
                    `).join('') : '<p class="text-slate-400 text-center">Génération du quiz...</p>'}
                </div>

                <div class="flex gap-4">
                    <button data-action="prev" class="w-1/3 py-5 bg-white border border-slate-200 text-slate-400 hover:text-slate-900 rounded-2xl font-bold transition-all">
                        Back
                    </button>
                    <button onclick="OnboardingWizard.collectAnswersAndFinish()" class="flex-1 py-5 bg-indigo-600 text-white rounded-2xl font-black text-lg shadow-xl hover:bg-indigo-700 transition-all">
                        Validate Profile
                    </button>
                </div>
            </div>
        `;
    },

    async collectAnswersAndFinish() {
        const questions = onboardingState.calibration_questions;
        const answers = [];
        
        for(let i=0; i<questions.length; i++) {
            const selected = document.querySelector(`input[name="q${i}"]:checked`);
            if(!selected) {
                this.showError(`Veuillez répondre à la question ${i+1}`);
                return;
            }
            answers.push(selected.value);
            this.submitCalibrationAnswer(i, selected.value);
        }
        
        await this.finishCalibration();
    },

    getFinalTemplate() {
        const score = onboardingState.calibration_score || 0;
        const level = score >= 80 ? 'Expert' : score >= 60 ? 'Intermediate' : 'Junior';
        
        return `
            <div class="step-content animate-fade-in-up">
                <div class="text-center">
                    <div class="w-24 h-24 ${score >= 60 ? 'bg-emerald-100' : 'bg-amber-100'} rounded-full flex items-center justify-center mx-auto mb-8">
                        <i class="fas ${score >= 60 ? 'fa-trophy' : 'fa-hourglass-half'} text-4xl ${score >= 60 ? 'text-emerald-600' : 'text-amber-600'}"></i>
                    </div>
                    <h1 class="text-4xl lg:text-5xl font-black text-slate-900 mb-4 tracking-tight">
                        Your Level: <span class="gradient-text">${level}</span>
                    </h1>
                    <p class="text-xl text-slate-500 mb-8 font-medium">
                        Score: ${score}/100
                    </p>

                    <div class="bg-white border-2 border-slate-100 rounded-3xl p-6 mb-8 max-w-sm mx-auto">
                        <p class="text-[10px] text-slate-400 font-black uppercase tracking-widest mb-3">Talent Profile</p>
                        <canvas id="wizardRadarChart" width="280" height="280"></canvas>
                    </div>

                    <div class="bg-slate-50 rounded-2xl p-6 mb-10 text-left">
                        <h3 class="font-bold text-slate-900 mb-4">What's next?</h3>
                        <ul class="space-y-3">
                            <li class="flex items-center gap-3">
                                <i class="fas fa-check text-emerald-500"></i>
                                <span class="text-slate-600">Full AI Interview access</span>
                            </li>
                            <li class="flex items-center gap-3">
                                <i class="fas fa-check text-emerald-500"></i>
                                <span class="text-slate-600">Personalized feedback</span>
                            </li>
                            <li class="flex items-center gap-3">
                                <i class="fas fa-check text-emerald-500"></i>
                                <span class="text-slate-600">Job matching</span>
                            </li>
                        </ul>
                    </div>

                    <button data-action="finish" class="w-full py-5 bg-indigo-600 text-white rounded-2xl font-black text-lg shadow-xl hover:bg-indigo-700 transition-all flex items-center justify-center gap-3">
                        Start AI Interview <i class="fas fa-arrow-right ml-2"></i>
                    </button>
                </div>
            </div>
        `;
    },

    renderWizardRadar() {
        const canvas = document.getElementById('wizardRadarChart');
        if (!canvas || typeof Chart === 'undefined') return;

        const RADAR_7D = ['Technical', 'Communication', 'Problem Solving', 'Adaptability', 'Confidence', 'Consistency', 'Soft Skills'];
        const result = onboardingState.analysis_result || {};
        const intel = result.intelligence_layer || {};
        const confScore = intel.confidence_score || 0;
        const calScore = onboardingState.calibration_score || 0;

        const radarValues = {
            'Technical': Math.min(100, Math.max(0, calScore * 0.8 + 15)),
            'Communication': Math.min(100, Math.max(0, calScore * 0.7 + confScore * 0.3 * 0.5)),
            'Problem Solving': Math.min(100, Math.max(0, calScore * 0.8 + 15)),
            'Adaptability': Math.min(100, Math.max(0, confScore * 0.5 + 40)),
            'Confidence': Math.min(100, Math.max(0, calScore * 0.6 + confScore * 0.4 * 0.5 + 20)),
            'Consistency': Math.min(100, Math.max(0, calScore * 0.75 + 18)),
            'Soft Skills': Math.min(100, Math.max(0, calScore * 0.65 + 25)),
        };

        const values = RADAR_7D.map(d => radarValues[d] ?? 50);
        const baselineValues = RADAR_7D.map(d => Math.max(0, (radarValues[d] ?? 50) - 5));

        if (window._wizardRadarChart) window._wizardRadarChart.destroy();

        window._wizardRadarChart = new Chart(canvas, {
            type: 'radar',
            data: {
                labels: RADAR_7D,
                datasets: [
                    {
                        label: 'Interview',
                        data: values,
                        backgroundColor: 'rgba(124,58,237,0.1)',
                        borderColor: 'rgba(124,58,237,0.6)',
                        borderWidth: 2,
                        pointBackgroundColor: '#7c3aed',
                        pointRadius: 4,
                    },
                    {
                        label: 'CV Baseline',
                        data: baselineValues,
                        backgroundColor: 'rgba(239,68,68,0.05)',
                        borderColor: 'rgba(239,68,68,0.9)',
                        borderWidth: 2,
                        borderDash: [4, 4],
                        pointBackgroundColor: '#ef4444',
                        pointRadius: 2,
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: { legend: { display: false } },
                scales: {
                    r: {
                        min: 0, max: 100,
                        grid: { color: 'rgba(99,102,241,0.08)' },
                        angleLines: { color: 'rgba(99,102,241,0.08)' },
                        ticks: { display: false },
                        pointLabels: {
                            font: { family: 'Outfit', size: 10, weight: '600' },
                            color: '#6b7280',
                        }
                    }
                },
                animation: { duration: 1200, easing: 'easeOutQuart' }
            }
        });
    }
};

window.OnboardingWizard = OnboardingWizard;
window.addEventListener('DOMContentLoaded', () => OnboardingWizard.init());