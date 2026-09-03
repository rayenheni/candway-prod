document.addEventListener('DOMContentLoaded', () => {
    // Initial Render
    renderExperienceInputs();
    renderEducationInputs();
    renderProjectsInputs();
    renderLanguagesInputs();
    renderCertificationsInputs();
    setupListeners();
    loadCVData(); // Auto-fill
});

// --- Helper: Set value safely ---
function setVal(id, val) {
    const el = document.getElementById(id);
    if (el) el.value = val || '';
}
async function loadCVData() {
    const token = localStorage.getItem('token');
    if (!token) return;

    try {
        // 1. Try to get Full CV Data
        const result = await fetchAPI('/candidate/cv-data');
        // console.log("loadCVData: Fetch Response Status:", res.status);

        if (result) {
            if (result.found && result.data) {
                // CASE A: Full CV Exists
                const data = result.data;
                // console.log("Auto-filling CV Builder from Saved App...", data);

                experienceData = data.experience || [];
                educationData = data.education || [];
                projectsData = data.projects || [];
                languagesData = data.languages || [];
                certificationsData = data.certifications || [];

                setVal('input-role', data.declared_role || "");
                setVal('input-summary', data.summary || "");
                setVal('input-skills', (data.skills || []).join(', '));
                setVal('input-location', data.location || "");
                setVal('input-phone', data.phone || "");
                // Need to set Name/Email if preserved in CV data, or fall back to profile?
                // Usually CV data might not store name/email explicitly in the JSON blob if it's tied to user.

                // Refresh UI
                renderExperienceInputs();
                renderExperiencePreview();
                renderEducationInputs();
                renderEducationPreview();
                renderProjectsInputs();
                renderProjectsPreview();
                renderLanguagesInputs();
                renderLanguagesPreview();
                renderCertificationsInputs();
                renderCertificationsPreview();
                updatePreview();

                if (window.showToast) showToast('CV Data Auto-Restored!', 'success');

            } else {
                // CASE B: No CV Found -> Fetch Basic Profile
                await loadBasicProfile();
            }
        }

        // Refresh UI (Common)
        renderExperienceInputs();
        renderExperiencePreview();
        renderEducationInputs();
        renderEducationPreview();
        renderProjectsInputs();
        renderProjectsPreview();
        renderLanguagesInputs();
        renderLanguagesPreview();
        renderCertificationsInputs();
        renderCertificationsPreview();
        updatePreview();

        // Optional: Show toast?
    } catch (e) {
        console.error("Failed to load CV data", e);
    }
}

async function loadBasicProfile() {
    try {
        const user = await fetchAPI('/auth/me');
        if (user) {
            // console.log("Auto-filling Basic Profile...", user);

            setVal('input-name', user.name || "");
            setVal('input-email', user.email || "");
            setVal('input-phone', user.phone || "");
            setVal('input-location', user.location || "");
            setVal('input-role', user.headline || ""); // user.headline usually maps to role

            // Removed risky demo data clearing logic to prevent accidental data loss for real users
        }
    } catch (e) {
        console.error("Failed to load basic profile", e);
    }
}

// --- State Management ---

let experienceData = [];
let educationData = [];
let projectsData = [];
let languagesData = [];
let certificationsData = [];

// --- Listeners & Core Functions ---

function setupListeners() {
    const inputs = ['input-name', 'input-role', 'input-email', 'input-phone', 'input-location', 'input-website', 'input-summary', 'input-skills'];
    inputs.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('input', updatePreview);
    });
}

function getTrans(key) {
    if (window.t) return window.t(key);
    const lang = localStorage.getItem('candway_lang') || 'en';
    if (window.translations && window.translations[lang]) {
        return window.translations[lang][key] || key;
    }
    return key;
}

function updatePreview() {
    // Personal Info
    updateText('preview-name', getVal('input-name') || getTrans('cv.ph_fullname'));
    updateText('preview-role', getVal('input-role') || getTrans('cv.ph_role'));
    updateText('preview-email', getVal('input-email') || 'email@example.com');
    updateText('preview-phone', getVal('input-phone') || '123-456-7890');
    updateText('preview-location', getVal('input-location') || 'City, Country');
    updateText('preview-website', getVal('input-website') || 'portfolio.com');

    // Visibility checks for personal info items
    toggleVisibility('preview-email-container', getVal('input-email'));
    toggleVisibility('preview-phone-container', getVal('input-phone'));
    toggleVisibility('preview-location-container', getVal('input-location'));
    toggleVisibility('preview-website-container', getVal('input-website'));

    // Summary
    updateText('preview-summary', getVal('input-summary') || getTrans('cv.ph_summary'));

    // Skills
    const skillsVal = getVal('input-skills');
    const skills = skillsVal ? skillsVal.split(',').map(s => s.trim()).filter(s => s) : [];
    const skillsContainer = document.getElementById('preview-skills');
    if (skillsContainer) {
        skillsContainer.innerHTML = skills.length ? skills.map(s =>
            `<span class="px-2 py-1 bg-slate-100 text-slate-700 rounded text-xs font-semibold border border-slate-200 print:border-slate-300">${s}</span>`
        ).join('') : `<span class="text-xs text-slate-400 italic">${getTrans('cv.ph_skills')}</span>`;
    }

    // Profile Score Update (client-side completeness heuristic)
    calculateScore();
}

function calculateScore() {
    let score = 0;
    const suggestions = [];

    // 1. Personal Info (10 pts)
    const name = getVal('input-name');
    const role = getVal('input-role');
    const email = getVal('input-email');
    const phone = getVal('input-phone');
    const location = getVal('input-location');

    // Core Identity
    if (name.length > 5 && name.includes(' ')) score += 3;
    if (role.length > 3) score += 3;
    if (email.includes('@') && email.includes('.')) score += 2;
    if (phone.length > 6 || location.length > 3) score += 2;

    if (score < 10) suggestions.push(getTrans('cv.sugg_contact') || "Complete your contact details");

    // 2. Professional Summary (20 pts)
    const summary = getVal('input-summary');
    // TODO: move to backend — summary.stats.word_count
    const wordCount = summary.split(/\s+/).filter(w => w.length > 0).length;

    if (wordCount > 10) score += 5;
    if (wordCount > 30) score += 5;
    if (wordCount > 50) score += 5;
    if (["led", "managed", "developed", "created", "designed"].some(w => summary.toLowerCase().includes(w))) score += 5; // Action verbs

    if (wordCount < 10) suggestions.push(getTrans('cv.sugg_summary') || "Expand your professional summary");

    // 3. Experience (30 pts)
    // Quality over quantity
    if (experienceData.length > 0) score += 10;
    if (experienceData.length > 1) score += 5;

    // Check descriptions depth
    // TODO: move to backend — experience[].description_word_count
    const strongDescriptions = experienceData.filter(e => e.description && e.description.split(/\s+/).length > 20).length;
    if (strongDescriptions > 0) score += 10;
    if (strongDescriptions > 1) score += 5;

    if (experienceData.length === 0) suggestions.push(getTrans('cv.sugg_exp_missing') || "Add at least one experience");
    else if (strongDescriptions === 0) suggestions.push(getTrans('cv.sugg_exp_detail') || "Add more details to your experience");

    // 4. Education (10 pts)
    if (educationData.length > 0) score += 10;
    else suggestions.push(getTrans('cv.sugg_edu') || "Add your education");

    // 5. Skills (20 pts)
    const skills = getVal('input-skills').split(',').map(s => s.trim()).filter(s => s.length > 0);
    if (skills.length >= 3) score += 5;
    if (skills.length >= 5) score += 5;
    if (skills.length >= 8) score += 5;
    if (skills.length >= 10) score += 5;

    if (skills.length < 5) suggestions.push(getTrans('cv.sugg_skills') || "Add more key skills (aim for 5+)");

    // 6. Extras (Projects/Languages/Certs) (10 pts)
    if (projectsData.length > 0) score += 4;
    if (languagesData.length > 0) score += 3;
    if (certificationsData.length > 0) score += 3;

    // UI Update
    const scoreBar = document.getElementById('cv-score-bar');
    const scoreText = document.getElementById('cv-score');
    const suggestionText = document.getElementById('cv-suggestion');

    if (scoreBar) scoreBar.style.width = `${score}%`;
    if (scoreText) {
        scoreText.innerText = `${score}/100`;
        // Color coding
        scoreText.className = "text-lg font-black " + (score < 50 ? "text-red-500" : score < 80 ? "text-amber-500" : "text-emerald-500");
        if (scoreBar) {
            scoreBar.className = "h-full transition-all duration-500 " + (score < 50 ? "bg-red-500" : score < 80 ? "bg-amber-500" : "bg-emerald-500");
        }
    }

    if (suggestionText) {
        // Pick random suggestion if multiple, or congratulations
        if (score >= 95) suggestionText.innerText = "🌟 Outstanding! Your CV is top-tier.";
        else if (suggestions.length > 0) {
            // Rotate suggestions or pick first
            XSS.safeSetHTML(suggestionText, `<i class="fas fa-lightbulb text-amber-500 mr-1"></i> ${XSS.escapeHTML(suggestions[0])}`);
        } else {
            suggestionText.innerText = "Great progress! Keep refining.";
        }
    }
}

async function saveAndInterview() {
    const token = localStorage.getItem('token');
    if (!token) {
        alert(getTrans('cv.alert_save') || "Please log in to save.");
        return;
    }

    const btn = document.querySelector('button[onclick="saveAndInterview()"]');
    const originalContent = btn ? btn.innerHTML : "Save & Interview";
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i> Saving...';
    }

    // Prepare Payload
    const cvData = {
        declared_role: getVal('input-role') || "General",
        summary: getVal('input-summary'),
        skills: getVal('input-skills').split(',').map(s => s.trim()).filter(s => s),
        location: getVal('input-location'),
        phone: getVal('input-phone'),
        experience: experienceData,
        education: educationData,
        projects: projectsData,
        languages: languagesData,
        certifications: certificationsData
    };

    try {
        await fetchAPI('/candidate/applications', {
            method: 'POST',
            body: JSON.stringify(cvData)
        });

        if (true) { // fetchAPI throws if not ok
            // Local Storage Backup (Just in case)
            localStorage.setItem('candway_resume_text', document.getElementById('preview-summary').innerText);

            window.location.href = '/interview';
        } else {
            const err = await res.json();
            alert("Error saving CV: " + (err.detail || "Unknown error"));
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = originalContent;
            }
        }
    } catch (e) {
        console.error(e);
        alert("Save Failed: " + e.message + "\n\nEnsure backend is running and you are logged in.");
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalContent;
        }
    }
}

function updateText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

function toggleVisibility(id, hasContent) {
    const el = document.getElementById(id);
    if (el) el.style.display = hasContent ? 'flex' : 'none';
}

function getVal(id) {
    const el = document.getElementById(id);
    return el ? el.value : '';
}

// --- Experience ---

function addExperience() {
    experienceData.push({ role: "", company: "", date: "", description: "" });
    renderExperienceInputs();
    renderExperiencePreview();
}

function removeExperience(index) {
    experienceData.splice(index, 1);
    renderExperienceInputs();
    renderExperiencePreview();
}

function updateExperienceData(index, field, value) {
    experienceData[index][field] = value;
    renderExperiencePreview();
}

function renderExperienceInputs() {
    const container = document.getElementById('experience-list');
    if (!container) return;
    container.innerHTML = experienceData.map((item, index) => `
        <div class="p-4 bg-slate-50 rounded-xl border border-slate-200 relative group animate-fade-in">
            <button onclick="removeExperience(${index})" class="absolute top-2 right-2 text-slate-300 hover:text-red-500 transition"><i class="fas fa-trash"></i></button>
            <div class="grid grid-cols-2 gap-3 mb-3">
                <input type="text" placeholder="${getTrans('cv.ph_exp_role')}" data-i18n-placeholder="cv.ph_exp_role" value="${item.role}" oninput="updateExperienceData(${index}, 'role', this.value)" class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-indigo-500">
                <input type="text" placeholder="${getTrans('cv.ph_exp_company')}" data-i18n-placeholder="cv.ph_exp_company" value="${item.company}" oninput="updateExperienceData(${index}, 'company', this.value)" class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-indigo-500">
            </div>
            <input type="text" placeholder="${getTrans('cv.ph_exp_date')}" data-i18n-placeholder="cv.ph_exp_date" value="${item.date}" oninput="updateExperienceData(${index}, 'date', this.value)" class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm mb-3 focus:outline-none focus:border-indigo-500">
            <textarea rows="3" placeholder="${getTrans('cv.ph_exp_desc')}" data-i18n-placeholder="cv.ph_exp_desc" oninput="updateExperienceData(${index}, 'description', this.value)" class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-indigo-500 resize-none">${item.description}</textarea>
        </div>
    `).join('');
}

function renderExperiencePreview() {
    const container = document.getElementById('preview-experience');
    if (!container) return;
    container.innerHTML = experienceData.map(item => `
        <div class="mb-4 break-inside-avoid">
            <div class="flex justify-between items-baseline mb-1">
                <h3 class="font-bold text-slate-800">${item.role || getTrans('cv.ph_exp_role')}</h3>
                <span class="text-xs text-slate-500 font-medium whitespace-nowrap ml-4">${item.date || getTrans('cv.ph_exp_date')}</span>
            </div>
                <div class="text-sm text-indigo-600 font-medium mb-2">${item.company || getTrans('cv.ph_exp_company')}</div>
                ${renderDescriptionList(item.description)}
        </div>
    `).join('');

    // Hide section if empty
    const section = document.getElementById('section-experience');
    if (section) section.style.display = experienceData.length ? 'block' : 'none';
}

// --- Education ---

function addEducation() {
    educationData.push({ degree: "", school: "", date: "", description: "" });
    renderEducationInputs();
    renderEducationPreview();
}

function removeEducation(index) {
    educationData.splice(index, 1);
    renderEducationInputs();
    renderEducationPreview();
}

function updateEducationData(index, field, value) {
    educationData[index][field] = value;
    renderEducationPreview();
}

function renderEducationInputs() {
    const container = document.getElementById('education-list');
    if (!container) return;
    container.innerHTML = educationData.map((item, index) => `
        <div class="p-4 bg-slate-50 rounded-xl border border-slate-200 relative group animate-fade-in">
            <button onclick="removeEducation(${index})" class="absolute top-2 right-2 text-slate-300 hover:text-red-500 transition"><i class="fas fa-trash"></i></button>
            <div class="grid grid-cols-2 gap-3 mb-3">
                <input type="text" placeholder="${getTrans('cv.ph_edu_degree')}" data-i18n-placeholder="cv.ph_edu_degree" value="${item.degree}" oninput="updateEducationData(${index}, 'degree', this.value)" class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-indigo-500">
                <input type="text" placeholder="${getTrans('cv.ph_edu_school')}" data-i18n-placeholder="cv.ph_edu_school" value="${item.school}" oninput="updateEducationData(${index}, 'school', this.value)" class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-indigo-500">
            </div>
            <input type="text" placeholder="${getTrans('cv.ph_edu_date')}" data-i18n-placeholder="cv.ph_edu_date" value="${item.date}" oninput="updateEducationData(${index}, 'date', this.value)" class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm mb-3 focus:outline-none focus:border-indigo-500">
            <textarea rows="2" placeholder="${getTrans('cv.ph_edu_desc')}" data-i18n-placeholder="cv.ph_edu_desc" oninput="updateEducationData(${index}, 'description', this.value)" class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-indigo-500 resize-none">${item.description}</textarea>
        </div>
    `).join('');
}

function renderEducationPreview() {
    const container = document.getElementById('preview-education');
    if (!container) return;
    container.innerHTML = educationData.map(item => `
        <div class="mb-4 break-inside-avoid">
            <h3 class="font-bold text-slate-800 text-sm">${item.degree || getTrans('cv.ph_edu_degree')}</h3>
            <div class="text-xs text-indigo-600 font-medium mb-1">${item.school || getTrans('cv.ph_edu_school')}</div>
            <div class="text-xs text-slate-400 mb-2">${item.date || getTrans('cv.ph_edu_date')}</div>
            ${item.description ? renderDescriptionList(item.description) : ''}
        </div>
    `).join('');

    const section = document.getElementById('section-education');
    if (section) section.style.display = educationData.length ? 'block' : 'none';
}

// --- Projects ---

function addProject() {
    projectsData.push({ title: "", link: "", description: "" });
    renderProjectsInputs();
    renderProjectsPreview();
}

function removeProject(index) {
    projectsData.splice(index, 1);
    renderProjectsInputs();
    renderProjectsPreview();
}

function updateProjectsData(index, field, value) {
    projectsData[index][field] = value;
    renderProjectsPreview();
}

function renderProjectsInputs() {
    const container = document.getElementById('projects-list');
    if (!container) return;
    container.innerHTML = projectsData.map((item, index) => `
        <div class="p-4 bg-slate-50 rounded-xl border border-slate-200 relative group animate-fade-in">
            <button onclick="removeProject(${index})" class="absolute top-2 right-2 text-slate-300 hover:text-red-500 transition"><i class="fas fa-trash"></i></button>
            <input type="text" placeholder="${getTrans('cv.ph_proj_title')}" data-i18n-placeholder="cv.ph_proj_title" value="${item.title}" oninput="updateProjectsData(${index}, 'title', this.value)" class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm mb-3 focus:outline-none focus:border-indigo-500">
            <input type="text" placeholder="${getTrans('cv.ph_proj_link')}" data-i18n-placeholder="cv.ph_proj_link" value="${item.link}" oninput="updateProjectsData(${index}, 'link', this.value)" class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm mb-3 focus:outline-none focus:border-indigo-500">
            <textarea rows="2" placeholder="${getTrans('cv.ph_proj_desc')}" data-i18n-placeholder="cv.ph_proj_desc" oninput="updateProjectsData(${index}, 'description', this.value)" class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-indigo-500 resize-none">${item.description}</textarea>
        </div>
    `).join('');
}

function renderProjectsPreview() {
    const container = document.getElementById('preview-projects');
    if (!container) return;
    container.innerHTML = projectsData.map(item => `
        <div class="mb-4 break-inside-avoid">
            <div class="flex justify-between items-center mb-1">
                <h3 class="font-bold text-slate-800 text-sm">${item.title || getTrans('cv.ph_proj_title')}</h3>
                ${item.link ? `<a href="${item.link.startsWith('http') ? item.link : 'https://' + item.link}" target="_blank" class="text-xs text-indigo-500 hover:underline"><i class="fas fa-external-link-alt"></i> View</a>` : ''}
            </div>
            <p class="text-xs text-slate-600 leading-relaxed text-justify">${item.description || ''}</p>
        </div>
    `).join('');

    const section = document.getElementById('section-projects');
    if (section) section.style.display = projectsData.length ? 'block' : 'none';
}

function renderDescriptionList(text) {
    if (!text) return '';
    // TODO: move to backend — description.bullet_points
    const points = text.split('\n').filter(line => line.trim().length > 0);
    if (points.length === 0) return '';

    // If single line, render as paragraph or single bullet? 
    // User asked for points, so let's check if it looks like a list or just a block.
    // Defaulting to list for consistency based on request "description should be like points".

    return `<ul class="list-disc ml-4 text-xs text-slate-600 leading-relaxed space-y-1">
        ${points.map(point => `<li>${point.trim()}</li>`).join('')}
    </ul>`;
}

// --- Languages ---

function addLanguage() {
    languagesData.push({ language: "", level: "" });
    renderLanguagesInputs();
    renderLanguagesPreview();
}

function removeLanguage(index) {
    languagesData.splice(index, 1);
    renderLanguagesInputs();
    renderLanguagesPreview();
}

function updateLanguagesData(index, field, value) {
    languagesData[index][field] = value;
    renderLanguagesPreview();
}

function renderLanguagesInputs() {
    const container = document.getElementById('languages-list');
    if (!container) return;
    container.innerHTML = languagesData.map((item, index) => `
        <div class="flex gap-2 items-center mb-2 animate-fade-in group">
            <input type="text" placeholder="${getTrans('cv.ph_lang_name')}" data-i18n-placeholder="cv.ph_lang_name" value="${item.language}" oninput="updateLanguagesData(${index}, 'language', this.value)" class="flex-1 px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-indigo-500">
            <input type="text" placeholder="${getTrans('cv.ph_lang_level')}" data-i18n-placeholder="cv.ph_lang_level" value="${item.level}" oninput="updateLanguagesData(${index}, 'level', this.value)" class="w-1/3 px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-indigo-500">
            <button onclick="removeLanguage(${index})" class="text-slate-300 hover:text-red-500 transition px-1"><i class="fas fa-times"></i></button>
        </div>
    `).join('');
}

function renderLanguagesPreview() {
    const container = document.getElementById('preview-languages');
    if (!container) return;
    container.innerHTML = languagesData.map(item => `
        <div class="flex justify-between items-center text-xs">
            <span class="font-medium text-slate-700">${item.language || getTrans('cv.ph_lang_name')}</span>
            <span class="text-slate-500">${item.level || ''}</span>
        </div>
    `).join('');

    const section = document.getElementById('section-languages');
    if (section) section.style.display = languagesData.length ? 'block' : 'none';
}

// --- Certifications ---

function addCertification() {
    certificationsData.push({ name: "", issuer: "", date: "" });
    renderCertificationsInputs();
    renderCertificationsPreview();
}

function removeCertification(index) {
    certificationsData.splice(index, 1);
    renderCertificationsInputs();
    renderCertificationsPreview();
}

function updateCertificationsData(index, field, value) {
    certificationsData[index][field] = value;
    renderCertificationsPreview();
}

function renderCertificationsInputs() {
    const container = document.getElementById('certifications-list');
    if (!container) return;
    container.innerHTML = certificationsData.map((item, index) => `
        <div class="p-3 bg-slate-50 rounded-lg border border-slate-200 mb-2 relative group animate-fade-in">
             <button onclick="removeCertification(${index})" class="absolute top-2 right-2 text-slate-300 hover:text-red-500 transition"><i class="fas fa-trash text-xs"></i></button>
             <input type="text" placeholder="${getTrans('cv.ph_cert_name')}" data-i18n-placeholder="cv.ph_cert_name" value="${item.name}" oninput="updateCertificationsData(${index}, 'name', this.value)" class="w-full px-3 py-1.5 rounded border border-slate-200 text-sm mb-2 focus:outline-none focus:border-indigo-500">
             <div class="flex gap-2">
                <input type="text" placeholder="${getTrans('cv.ph_cert_issuer')}" data-i18n-placeholder="cv.ph_cert_issuer" value="${item.issuer}" oninput="updateCertificationsData(${index}, 'issuer', this.value)" class="w-full px-3 py-1.5 rounded border border-slate-200 text-sm focus:outline-none focus:border-indigo-500">
                <input type="text" placeholder="${getTrans('cv.ph_cert_year')}" data-i18n-placeholder="cv.ph_cert_year" value="${item.date}" oninput="updateCertificationsData(${index}, 'date', this.value)" class="w-1/3 px-3 py-1.5 rounded border border-slate-200 text-sm focus:outline-none focus:border-indigo-500">
             </div>
        </div>
    `).join('');
}

function renderCertificationsPreview() {
    const container = document.getElementById('preview-certifications');
    if (!container) return;
    container.innerHTML = certificationsData.map(item => `
        <div class="mb-2">
            <div class="font-bold text-slate-800 text-xs">${item.name || getTrans('cv.ph_cert_name')}</div>
            <div class="text-[10px] text-slate-500">${item.issuer ? item.issuer + ' • ' : ''}${item.date || ''}</div>
        </div>
    `).join('');

    const section = document.getElementById('section-certifications');
    if (section) section.style.display = certificationsData.length ? 'block' : 'none';
}

// --- AI Feature (disabled for production — was a hardcoded setTimeout, not real AI)
// The enhanceWithAI() function was removed because it used fake hardcoded text.
// A real AI enhancement feature should call a backend endpoint.
// See git history or JIRA-123 for the removed implementation.

// Initial Population Calls
renderExperiencePreview();
renderEducationPreview();
renderProjectsPreview();
renderLanguagesPreview();
renderCertificationsPreview();
