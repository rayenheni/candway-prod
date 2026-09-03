// Game State
let applicationId = null;
let urlInterviewToken = null;

// Only run interview init on the interview page
const _isInterviewPath = window.location.pathname.includes('/interview');

// Restore applicationId from URL or storage (only on interview page)
if (_isInterviewPath) {
    const urlParams = new URLSearchParams(window.location.search);
    const urlAppId = urlParams.get('id') || urlParams.get('app') || urlParams.get('applicationId');
    urlInterviewToken = urlParams.get('token');

    // U-04 (Bug B-19): the live score and per-turn score deltas were
    // surfaced to candidates in real time, which both enables
    // score-chasing gaming behaviour and demotivates honest candidates
    // after a single low-scoring answer. We default to hiding these
    // signals; recruiters/QA can opt in for debugging with
    // `?showLiveScore=1`.
    const SHOW_LIVE_SCORE =
        urlParams.get('showLiveScore') === '1' ||
        urlParams.get('debug_score') === '1';

    if (urlAppId) {
        applicationId = urlAppId;
        _log("[INIT] Set applicationId from URL:", applicationId);
    } else {
        // Check both storage keys
        const storedId = localStorage.getItem('active_app_id') || localStorage.getItem('pending_interview_app_id');
        if (storedId && storedId !== 'undefined' && storedId !== 'null') {
            applicationId = storedId;
            _log("[INIT] Restored applicationId from storage:", applicationId);
        }
    }
} else {
    // Clean up stale interview references on non-interview pages
    localStorage.removeItem('active_app_id');
    localStorage.removeItem('pending_interview_app_id');
}

let mediaRecorder;
let recordedChunks = [];
let questionCount = 1;
let maxQuestions = 15;
let score = 0;
let timeLeft = 1800;
let timerInterval = null;
let selectedLanguage = null;
let sendInProgress = false;

// DOM References (Initialized on DOMContentLoaded)
let chatBox, chatForm, input, lazyWarning, qCounter, timer, liveScore, sendBtn;

// Constants & Timing (Moved to top to prevent TDZ issues)
const MODEL_URL = 'https://cdn.jsdelivr.net/npm/@vladmandic/face-api@1.7.13/model/';
let lastQuestionTime = Date.now();
let faceApiReady = false;
let lastViolationTime = {}; 
const VIOLATION_DEBOUNCE_MS = 5000;
let cheatCount = 0;
let gracePeriod = true;

const getChatBox = () => chatBox || document.getElementById('chat-box');
const getChatForm = () => chatForm || document.getElementById('chat-form');
const getChatInput = () => input || document.getElementById('msg-input');
const getLazyWarning = () => lazyWarning || document.getElementById('lazy-warning');
const getQCounter = () => qCounter || document.getElementById('q-counter');
const getTimer = () => timer || document.getElementById('timer');
const getLiveScore = () => liveScore || document.getElementById('live-score');

function normalizeInterviewLanguage(value) {
    if (!value) return null;
    const raw = String(value).trim().toLowerCase();
    if (!raw) return null;
    if (raw === 'french' || raw === 'francais' || raw === 'français' || raw === 'fr') return 'French';
    if (raw === 'arabic' || raw === 'arabe' || raw === 'ar') return 'Arabic';
    if (raw === 'english' || raw === 'en') return 'English';
    return null;
}

function getInterviewLanguage() {
    const current = normalizeInterviewLanguage(selectedLanguage);
    if (current) return current;
    const stored = normalizeInterviewLanguage(localStorage.getItem('interview_language'));
    if (stored) {
        selectedLanguage = stored;
        return stored;
    }
    return 'English';
}

function getRecognitionLocale(language) {
    const normalized = normalizeInterviewLanguage(language) || 'English';
    if (normalized === 'French') return 'fr-FR';
    if (normalized === 'Arabic') return 'ar-TN';
    return 'en-US';
}

function formatTime(seconds) {
    if (seconds === null || seconds === undefined || isNaN(seconds)) return "--:--";
    if (seconds < 0) return "00:00";
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

function applyLanguageUI(language) {
    const normalized = normalizeInterviewLanguage(language) || 'English';
    selectedLanguage = normalized;
    localStorage.setItem('interview_language', normalized);

    if (chatBox && input) {
        if (normalized === 'Arabic') {
            chatBox.setAttribute('dir', 'rtl');
            chatBox.classList.add('rtl-mode');
            input.setAttribute('dir', 'rtl');
            input.placeholder = "اكتب إجابتك...";
        } else {
            chatBox.removeAttribute('dir');
            chatBox.classList.remove('rtl-mode');
            input.removeAttribute('dir');
            input.placeholder = normalized === 'French' ? "Tapez votre réponse..." : "Type your answer...";
        }
    }

    if (recognition) {
        recognition.lang = getRecognitionLocale(normalized);
    }
}

selectedLanguage = normalizeInterviewLanguage(localStorage.getItem('interview_language'));

function safeText(value) {
    if (value === null || value === undefined) return '';
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function extractMessageText(value) {
    if (value === null || value === undefined) return '';

    // Handle stringified JSON that might have slipped through
    if (typeof value === 'string' && value.trim().startsWith('{') && value.trim().endsWith('}')) {
        try {
            const parsed = JSON.parse(value);
            if (parsed && typeof parsed === 'object') {
                return extractMessageText(parsed); // Recursive extraction
            }
        } catch (e) {
            // Not JSON, continue normally
        }
    }

    if (typeof value === 'object') {
        if (typeof value.reply === 'string') return extractMessageText(value.reply);
        if (typeof value.message === 'string') return extractMessageText(value.message);
        if (typeof value.question === 'string') return extractMessageText(value.question);

        // Recursive string extraction for complex scenario formats
        let parts = [];
        const extractStrings = (obj) => {
            if (typeof obj === 'string') {
                parts.push(obj);
            } else if (Array.isArray(obj)) {
                obj.forEach(extractStrings);
            } else if (obj !== null && typeof obj === 'object') {
                for (const [k, v] of Object.entries(obj)) {
                    if (!['type', 'scenario_type', 'skills', 'current_score'].includes(k)) {
                        extractStrings(v);
                    }
                }
            } else if (obj !== null && obj !== undefined) {
                parts.push(String(obj));
            }
        };

        extractStrings(value);

        if (parts.length > 0) {
            return parts.join("\n\n");
        }

        try {
            return JSON.stringify(value);
        } catch (e) {
            return String(value);
        }
    }
    return String(value);
}

function clampPercent(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return 0;
    return Math.max(0, Math.min(100, n));
}

function normalizeSkillKey(value) {
    return String(value || '')
        .toLowerCase()
        .replace(/[^a-z0-9]/g, '');
}

function normalizeSkillMetrics(rawSkills) {
    if (!rawSkills || typeof rawSkills !== 'object' || Array.isArray(rawSkills)) {
        return {};
    }
    const normalized = {};
    const standardKeys = ["Technical", "Communication", "Problem Solving", "Adaptability", "Confidence", "Consistency", "Soft Skills"];

    Object.entries(rawSkills).forEach(([key, rawValue]) => {
        let label = String(key || '').trim();
        if (!label) return;

        const lowKey = label.toLowerCase();
        if (lowKey.includes('tech') || lowKey.includes('dev') || lowKey.includes('prog')) label = "Technical";
        else if (lowKey.includes('commun') || lowKey.includes('interper') || lowKey.includes('relat')) label = "Communication";
        else if (lowKey.includes('problem') || lowKey.includes('solve') || lowKey.includes('analyt') || lowKey.includes('logic')) label = "Problem Solving";
        else if (lowKey.includes('adapt') || lowKey.includes('flex') || lowKey.includes('change') || lowKey.includes('agil')) label = "Adaptability";
        else if (lowKey.includes('confid') || lowKey.includes('present') || lowKey.includes('leader') || lowKey.includes('motiv')) label = "Confidence";
        else if (lowKey.includes('consist') || lowKey.includes('stabl') || lowKey.includes('reliabl')) label = "Consistency";
        else if (lowKey.includes('soft') || lowKey.includes('people') || lowKey.includes('teambuild')) label = "Soft Skills";

        const valueNum = Number(
            String(rawValue === null || rawValue === undefined ? '' : rawValue).replace(/[^0-9.+-]/g, '')
        );
        normalized[label] = clampPercent(valueNum);
    });

    standardKeys.forEach(k => {
        if (normalized[k] === undefined) {
            const scoreVal = Number(liveScore?.innerText) || 50;
            normalized[k] = scoreVal;
        }
    });

    return normalized;
}

function resolveLiveSkills(rawSkills, scoreValue) {
    const normalized = normalizeSkillMetrics(rawSkills);
    const vals = Object.values(normalized || {});
    const allZero = vals.length >= 3 && vals.every(v => Number(v) <= 0);
    if (Object.keys(normalized).length >= 3 && !allZero) return normalized;

    const cvVals = Object.values(cvBaselineSkills || {});
    const cvAllZero = cvVals.length >= 3 && cvVals.every(v => Number(v) <= 0);
    if (cvBaselineSkills && Object.keys(cvBaselineSkills).length >= 3 && !cvAllZero) {
        return { ...cvBaselineSkills };
    }

    const baseline = clampPercent(scoreValue);
    return {
        "Technical": baseline,
        "Communication": clampPercent(Math.round(baseline * 0.92)),
        "Problem Solving": baseline < 90 ? clampPercent(Math.round(baseline * 1.05)) : 95,
        "Adaptability": clampPercent(Math.round(baseline * 0.88)),
        "Confidence": clampPercent(Math.round(baseline * 0.95)),
        "Consistency": clampPercent(Math.round(baseline * 0.90)),
        "Soft Skills": clampPercent(Math.round(baseline * 0.94))
    };
}

function resolveBaselineSkills(serverBaselineSkills, liveSkills, scoreValue) {
    const normalizedBaseline = normalizeSkillMetrics(serverBaselineSkills);
    const baseVals = Object.values(normalizedBaseline || {});
    const baselineIsValid = Object.keys(normalizedBaseline).length >= 3 && !baseVals.every(v => Number(v) <= 0);
    if (baselineIsValid) return normalizedBaseline;

    const live = normalizeSkillMetrics(liveSkills);
    const liveVals = Object.values(live || {});
    const liveIsValid = Object.keys(live).length >= 3 && !liveVals.every(v => Number(v) <= 0);
    if (liveIsValid) return live;

    const seed = clampPercent(scoreValue);
    return {
        "Technical": seed,
        "Communication": seed,
        "Problem Solving": seed,
        "Adaptability": seed,
        "Confidence": seed,
        "Consistency": seed,
        "Soft Skills": seed
    };
}

// Real-time Lazy Answer Monitoring (Initialized in setupDOMListeners)
function setupDOMListeners() {
    if (input && lazyWarning) {
        input.addEventListener('input', () => {
            const val = input.value.toLowerCase().trim();
            const lazyPhrases = ["ok", "okay", "yes", "no", "ready", "what", "next"];

            // Lazy check
            if (val.length > 0 && (val.length < 7 || lazyPhrases.includes(val))) {
                lazyWarning.style.display = 'block';
                lazyWarning.innerHTML = `<i class="fas fa-magic" style="margin-right:6px"></i>Detailed answers unlock higher scores`;
                lazyWarning.style.color = 'var(--amber)';
                lazyWarning.style.background = 'rgba(245, 158, 11, 0.08)';
            } else if (val.length > 30 && val.length < 60) {
                // HINT ENGINE: Proactive tip for medium length answers
                lazyWarning.style.display = 'block';
                lazyWarning.innerHTML = `<i class="fas fa-lightbulb" style="margin-right:6px"></i>Tip: Mention specific tools or methodologies to boost your depth score`;
                lazyWarning.style.color = 'var(--purple)';
                lazyWarning.style.background = 'var(--purple-soft)';
            } else {
                lazyWarning.style.display = 'none';
            }
        });
    }
    // Attach form handler properly outside event listeners
// Fixed: Using chatForm instead of 'form'
if (chatForm) {
    chatForm.onsubmit = async (e) => {
    e.preventDefault();
    const txt = input.value.trim();
    if (!txt || !applicationId || sendInProgress) return;
    sendInProgress = true;
    input.disabled = true;
    // Initialize sendBtn globally
    sendBtn = document.getElementById('send-btn');
    if (sendBtn) sendBtn.disabled = true;

    // 0. Check answer latency (anti-cheat)
    if (typeof checkAnswerLatency === 'function') checkAnswerLatency();

    // 1. Show User Message
    appendMessage('user', txt);
    input.value = '';
    showTyping();

    // 2. Send to API (Do NOT return early, ensure backend gets the answer)
    try {
        const interviewLanguage = getInterviewLanguage();
        let chatUrl = '/ai/interview/chat';
        if (applicationId) {
            chatUrl += `?candidate_id=${applicationId}`;
            if (urlInterviewToken) chatUrl += `&token=${urlInterviewToken}`;
        }
        
        const data = await fetchAPI(chatUrl, {
            method: 'POST',
            body: JSON.stringify({
                candidate_id: applicationId,
                message: txt,
                language: interviewLanguage
            }),
            timeout: 180000 // 3 minutes for technical evaluation turn
        });

        // Keep client language state aligned with server-locked interview language.
        if (data && data.language) {
            const serverLanguage = normalizeInterviewLanguage(data.language);
            if (serverLanguage) applyLanguageUI(serverLanguage);
        }

        removeTyping();

        if (data) {
            const liveSkills = resolveLiveSkills(data.skills, data.current_score !== undefined ? data.current_score : score);
            const baselineSkills = resolveBaselineSkills(data.cv_skill_metrics, liveSkills, score);
            updateTalentGraph(baselineSkills, data.talent_analysis || "Initial CV Baseline", "", { source: 'cv' });

            if (Number.isFinite(Number(data.total_questions)) && Number(data.total_questions) > 0) {
                maxQuestions = Number(data.total_questions);
            }

            // Backend hard timeout: end immediately without applying fake score penalties.
            if (data.time_limit_reached || data.type === 'timeout') {
                clearInterval(timerInterval);
                appendMessage('ai', data.reply || "Interview time limit exceeded. Thank you for your participation.");
                if (data.feedback) {
                    addFeedbackItem(0, data.feedback, questionCount - 1);
                }
                await endInterview();
                return;
            }

            // Count only successful, non-timeout answers to avoid local drift.
            questionCount = Math.min(questionCount + 1, maxQuestions + 1);

            // 3. Update Score and Show Feedback
            let diff = 0;
            if (data.current_score !== undefined) {
                const prevScore = Number.isFinite(Number(score)) ? Number(score) : 0;
                const nextScore = Number(data.current_score);
                diff = Number.isFinite(nextScore) ? (nextScore - prevScore) : 0;
                score = Number.isFinite(nextScore) ? nextScore : prevScore;

                // Only show floating "+5/-3" toasts when explicitly
                // opted in (Bug B-19). The default is a calmer
                // interview experience with no moving target.
                if (diff !== 0 && SHOW_LIVE_SCORE) {
                    if (diff < 0) showFeedback(diff, 'red');
                    if (diff > 0) showFeedback(`+${diff}`, 'green');
                }
            }

            // Keep graph and skill breakdown live even if backend sends sparse skills payload.
            updateTalentGraph(liveSkills, data.talent_analysis, data.score_reasoning, { source: 'live' });
            if (data.feedback) {
                addFeedbackItem(diff, data.feedback, questionCount - 1);
            }

            // Sync Time with Backend (only accept positive values, preserve client timer)
            // CRITICAL: Do NOT sync time_left from server during active interview to prevent reset
            if (data.time_left !== undefined && !timerInterval) {
                const serverTimeLeft = Number(data.time_left);
                if (Number.isFinite(serverTimeLeft) && serverTimeLeft > 0 && serverTimeLeft <= 1800) {
                    _log("[TIME] Initial sync with server time:", serverTimeLeft);
                    timeLeft = serverTimeLeft;
                }
            }

            // 3b. Handle AI Hint UI
            const hintBubble = document.getElementById('ai-hint-bubble');
            const hintText = document.getElementById('ai-hint-text');
            if (data.is_vague && data.hint_text) {
                if (hintBubble && hintText) {
                    hintText.innerText = data.hint_text;
                    hintBubble.classList.remove('hidden');
                    // Hide after 30 seconds or next question
                    setTimeout(() => hintBubble.classList.add('hidden'), 30000);
                }
            } else if (hintBubble) {
                hintBubble.classList.add('hidden');
            }

            updateUI();

            // 4. Check for Completion Signals - Only end if both conditions met
            // Or if explicitly marked as complete AND we have enough questions
            const hasEnoughQuestions = questionCount >= 10; // Minimum questions before allowing complete
            if ((data.type === 'complete' && hasEnoughQuestions) || questionCount > maxQuestions) {
                _log("[INTERVIEW] Ending - type:", data.type, "questions:", questionCount, "max:", maxQuestions);
                await endInterview();
                return;
            } else if (data.type === 'complete') {
                _log("[INTERVIEW] Ignoring complete signal - only", questionCount, "questions so far");
            }

            // 5. Show Next Question (Open-Ended Format)
            appendMessage('ai', data.reply);
            // Mark question received for latency tracking
            if (typeof markQuestionReceived === 'function') markQuestionReceived();
            // No QCM rendering - all questions are open-ended

        }
    } catch (err) {
        removeTyping();
        console.error("Chat Error:", err);

        // Fail-safe: If we are at the end but network failed, try to end anyway
        if (questionCount > maxQuestions) {
            endInterview();
        } else {
            appendMessage('ai', "I'm having trouble connecting to my brain. Please check your connection.");
        }
    } finally {
        sendInProgress = false;
        input.disabled = false;
        if (sendBtn) sendBtn.disabled = false;
        input.focus();
    }
};
}
}

// --- AI-POWERED CHEAT DETECTION SYSTEM ---
let webcamStream = null;
let detectionInterval = null;
let trustScore = 100;

// Enterprise Video Recording Configuration
let mediaSegments = [];
const SEGMENT_DURATION_MS = 30000; // 30 seconds per segment
let segmentInterval = null;
let violations = {
    multipleFaces: 0,
    noFace: 0,
    lookingAway: 0,
    phoneUsage: 0,
    movement: 0
};
let lastFacePosition = null;
let noFaceCounter = 0;
let lookingAwayCounter = 0;

let talentChart = null;
let cvBaselineSkills = null;
let isUpdatingGraph = false; // Phase 23: Race condition prevention (Issue #9)



// --- SPEECH RECOGNITION SETUP ---
let micBtn, recognition;
let isRecording = false;

function setupSpeechRecognition() {
    micBtn = document.getElementById('mic-btn');
    if (!micBtn) return;

    if ('webkitSpeechRecognition' in window) {
        recognition = new webkitSpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US'; // Default to English, will update dynamically

    recognition.onstart = function () {
        isRecording = true;
        micBtn.classList.remove('bg-slate-200', 'text-slate-600');
        micBtn.classList.add('bg-red-500', 'text-white', 'animate-pulse');
        input.placeholder = "Listening...";
    };

    recognition.onend = function () {
        isRecording = false;
        micBtn.classList.add('bg-slate-200', 'text-slate-600');
        micBtn.classList.remove('bg-red-500', 'text-white', 'animate-pulse');
        input.placeholder = "Type your answer...";
    };

    recognition.onresult = function (event) {
        const transcript = event.results[0][0].transcript;
        input.value += (input.value ? ' ' : '') + transcript;
        input.focus();
    };

    recognition.onerror = function (event) {
        console.error("Speech detection error", event.error);
        isRecording = false;
        micBtn.classList.add('bg-slate-200', 'text-slate-600');
        micBtn.classList.remove('bg-red-500', 'text-white', 'animate-pulse');
        input.placeholder = "Type your answer...";

        if (event.error === 'not-allowed') {
            alert("Microphone access blocked. Please check your browser settings.");
        }
    };

        micBtn.addEventListener('click', () => {
            if (isRecording) {
                recognition.stop();
            } else {
                // Sync lang with selected language logic
                recognition.lang = getRecognitionLocale(getInterviewLanguage());
                recognition.start();
            }
        });
    } else {
        console.warn("Web Speech API not supported");
        micBtn.style.display = 'none';
    }
}

function initTalentGraph() {
    const canvas = document.getElementById('talentChart');
    if (!canvas) {
        console.error("[INIT] talentChart canvas not found!");
        return;
    }
    const ctx = canvas.getContext('2d');

    if (typeof Chart === 'undefined') {
        console.error("[INIT] Chart.js NOT LOADED! Radar chart will be unavailable.");
        const container = canvas.parentElement;
        if (container) container.innerHTML = '<div class="p-8 text-center text-slate-500 italic">Chart engine failed to load</div>';
        return;
    }

    talentChart = new Chart(ctx, {
        type: 'radar',
        data: {
            labels: ['Technical', 'Communication', 'Problem Solving', 'Adaptability', 'Confidence', 'Consistency', 'Soft Skills'],
            datasets: [
                {
                    label: 'Interview',
                    data: [0, 0, 0, 0, 0, 0, 0],
                    backgroundColor: 'rgba(124,58,237,0.1)',
                    borderColor: 'rgba(124,58,237,0.6)',
                    borderWidth: 2,
                    pointBackgroundColor: '#7c3aed',
                    pointRadius: 4,
                },
                {
                    label: 'CV Baseline',
                    data: [0, 0, 0, 0, 0, 0, 0],
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
                        font: { family: 'Outfit', size: 9, weight: '600' },
                        color: '#6b7280',
                    }
                }
            }
        }
    });
}

function mapSkillsToLabels(skills, labels, fallback = 0) {
    return labels.map(label => {
        if (skills[label] !== undefined) return clampPercent(skills[label]);
        const labelNorm = normalizeSkillKey(label);
        const foundKey = Object.keys(skills || {}).find(k => normalizeSkillKey(k) === labelNorm);
        return foundKey ? clampPercent(skills[foundKey]) : clampPercent(fallback);
    });
}

function updateTalentGraph(skillParam, analysisData, scoreReasoning, meta = {}) {
    if (isUpdatingGraph) return;
    isUpdatingGraph = true;

    const releaseFlag = () => { isUpdatingGraph = false; };

    try {
        let skills = skillParam;
        if (skillParam && skillParam.skills) skills = skillParam.skills;
        if (skillParam && skillParam.skill_metrics) skills = skillParam.skill_metrics;
        skills = normalizeSkillMetrics(skills);

        if (!talentChart || !skills || Object.keys(skills).length === 0) {
            isUpdatingGraph = false;
            return;
        }

        const source = (meta && meta.source) || 'live';

        if (source === 'cv' || !cvBaselineSkills) {
            if (!cvBaselineSkills) {
                cvBaselineSkills = { ...skills };
                _log("[GRAPH] CV Baseline locked:", cvBaselineSkills);
            }
        }

        const standardKeys = ["Technical", "Communication", "Problem Solving", "Adaptability", "Confidence", "Consistency", "Soft Skills"];
        const allKeys = [...new Set([...Object.keys(cvBaselineSkills || {}), ...Object.keys(skills)])];

        let skillKeys = allKeys.filter(k => standardKeys.includes(k));
        allKeys.forEach(k => { if (!skillKeys.includes(k) && skillKeys.length < standardKeys.length) skillKeys.push(k); });

        if (skillKeys.length < 3) {
            skillKeys = standardKeys;
        }

        talentChart.data.labels = skillKeys;
        const labels = skillKeys;

        const currentScore = Number(liveScore?.innerText) || 50;
        const liveData = mapSkillsToLabels(skills, labels, currentScore);
        const baselineData = mapSkillsToLabels(cvBaselineSkills || skills, labels, currentScore);

        talentChart.data.datasets[0].data = liveData;
        talentChart.data.datasets[1].data = baselineData;
        talentChart.update('none');

        updateSkillBreakdownBars(labels, talentChart.data.datasets[0].data);
        updateAnalysisList(scoreReasoning, analysisData);
    } finally {
        isUpdatingGraph = false;
    }
}

function updateSkillBreakdownBars(labels, data) {
    const breakdownContainer = document.getElementById('skill-breakdown-container');
    if (!breakdownContainer) return;
    const colorMap = ['var(--purple)', 'var(--green)', 'var(--indigo)', 'var(--amber)', 'var(--purple)', 'var(--cyan)', 'var(--red)'];
    breakdownContainer.innerHTML = labels.map((label, i) => `
        <div class="skill-row animate-fadeIn" style="animation-delay: ${i * 100}ms">
            <div class="skill-top">
                <span class="skill-name">${safeText(label)}</span>
                <span class="skill-pct" style="color:${colorMap[i % colorMap.length]}">${Math.round(data[i] || 0)}%</span>
            </div>
            <div class="skill-track">
                <div class="skill-fill" style="width:${data[i] || 0}%; background: ${colorMap[i % colorMap.length]}"></div>
            </div>
        </div>
    `).join('');
}

function updateAnalysisList(scoreReasoning, analysisData) {
    const listEl = document.getElementById('talent-analysis-list');
    if (!listEl) return;
    const reasoning = scoreReasoning || "";
    let htmlContent = "";
    if (reasoning) {
        htmlContent += `
            <div class="analysis-item animate-fadeIn">
                <i class="fas fa-lightbulb text-amber-500"></i>
                <span class="font-bold uppercase text-[10px]">${safeText(reasoning)}</span>
            </div>
        `;
    }
    let items = [];
    if (analysisData && typeof analysisData === 'object' && !Array.isArray(analysisData)) {
        items = Object.entries(analysisData).map(([key, text]) => ({ key, text: safeText(text) }));
    } else if (Array.isArray(analysisData)) {
        items = analysisData.map(text => ({ key: 'Insight', text: safeText(text) }));
    } else if (typeof analysisData === 'string' && analysisData) {
        items = [{ key: 'Status', text: safeText(analysisData) }];
    }
    listEl.innerHTML = items.map(item => `
        <div class="analysis-item animate-fadeIn p-2 border-l-2 border-indigo-500 bg-indigo-500/5 mb-1">
            <div class="text-[8px] font-black text-indigo-400 uppercase tracking-widest mb-0.5">${item.key}</div>
            <div class="text-[10px] text-slate-300 font-medium leading-relaxed">${item.text}</div>
        </div>
    `).join('') + htmlContent;
}

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    _log("[LIFECYCLE] DOMContentLoaded. Initializing...");
    if (!_isInterviewPath || !document.getElementById('chat-box')) {
        _log("[INIT] Not interview page — skipping interview init");
        return;
    }
    try {
        // 1. Initialize DOM References
        chatBox = document.getElementById('chat-box');
        chatForm = document.getElementById('chat-form');
        input = document.getElementById('msg-input');
        lazyWarning = document.getElementById('lazy-warning');
        qCounter = document.getElementById('q-counter');
        timer = document.getElementById('timer');
        liveScore = document.getElementById('live-score');

        _log("[INIT] DOM Elements captured. chatBox:", !!chatBox);

        // 2. Setup Listeners
        try {
            setupDOMListeners();
            _log("[INIT] DOM Listeners ready.");
        } catch(e) { console.error("[CRITICAL] setupDOMListeners failed:", e); }

        try {
            setupSpeechRecognition();
            _log("[INIT] Speech recognition ready.");
        } catch(e) { console.error("[CRITICAL] setupSpeechRecognition failed:", e); }

        // 3. Initialize Graph
        try {
            initTalentGraph();
            _log("[INIT] Talent graph initialized.");
        } catch(e) { console.error("[CRITICAL] initTalentGraph failed:", e); }

        // 4. Run Core App Init
        _log("[INIT] Invoking init()...");
        init();

        // 5. Setup Anti-Cheat
        setupAntiCheat();
    } catch (globalErr) {
        console.error("[FATAL] DOMContentLoaded handler crashed:", globalErr);
        Toast.show("Interface failed to load. Please refresh.", "error");
    }
});

async function init() {
    const urlParams = new URLSearchParams(window.location.search);

    // GUEST AUTH: Check for invitation parameters in URL if not logged in
    const urlAppId = urlParams.get('id') || urlParams.get('app') || urlParams.get('applicationId');
    const urlInterviewToken = urlParams.get('token');

    // GUEST AUTH: Silent authentication disabled to enforce manual login as requested.
    /*
    if (urlAppId && urlInterviewToken && !localStorage.getItem('token')) {
        _log("Guest invitation detected. Silent authentication skipped to enforce manual login.");
    }
    */

    if (typeof CONFIG === 'undefined') {
        Toast.show("Configuration Error: CONFIG not loaded. Check connection.", 'error');
        return;
    }

    // Use AuthToken for dynamic token access (fixes stale token on login/logout)
    const token = typeof AuthToken !== 'undefined' ? AuthToken.get() : localStorage.getItem('token');

    if (!token) {
        // Redirect to login with return URL and pre-fill email
        let next = '/dashboard';
        if (urlAppId) {
            next = `/interview?id=${urlAppId}`;
            if (urlInterviewToken) next += `&token=${urlInterviewToken}`;
        }
        
        let loginUrl = `/login?next=${encodeURIComponent(next)}`;
        const email = urlParams.get('email');
        if (email) loginUrl += `&email=${encodeURIComponent(email)}`;
        
        _log("[AUTH] No session found. Redirecting to login:", loginUrl);
        window.location.href = loginUrl;
        return;
    }

    // Initialize webcam proctoring (non-blocking)
    initWebcam().then(() => {
        // --- Enterprise: Start Segmented Video Recording ---
        startEnterpriseRecording();
    }).catch(err => {
        console.warn("Webcam initialization failed:", err);
    });

    // --- NEW: Check for Direct Invitation App ID (URL Priority) ---
    let storedAppId = localStorage.getItem('active_app_id') || localStorage.getItem('pending_interview_app_id');
    
    if (storedAppId === 'undefined' || storedAppId === 'null' || storedAppId === '') {
        console.warn("[INIT] Cleaning up invalid storedAppId:", storedAppId);
        localStorage.removeItem('active_app_id');
        localStorage.removeItem('pending_interview_app_id');
        storedAppId = null;
    }
    
    const activeAppId = urlAppId || storedAppId;
    _log("[INIT] Resolved activeAppId:", activeAppId, "(Source:", urlAppId ? "URL" : "Storage", ")");

    if (activeAppId) {
        localStorage.setItem('active_app_id', activeAppId);
        applicationId = activeAppId; // Sync global state
    }

    // FIXED: Using fetchAPI ensures /api/v1 prefix and auth headers are correct
    const fetchOptions = {
        timeout: 10000
    };

    try {
        // REC #1: Pass token to backend for IDOR verification
        let apiPath = activeAppId
            ? `/candidate/applications/${activeAppId}`
            : `/candidate/current-application?t=${Date.now()}`;

        if (urlInterviewToken && activeAppId) {
            apiPath += (apiPath.includes('?') ? '&' : '?') + `token=${urlInterviewToken}`;
        }

        const data = await window.fetchAPI(apiPath, fetchOptions);

        if (data.status === 'none') {
            Toast.show("No active application found for this account.", 'warning');
            setTimeout(() => window.location.href = '/dashboard', 2000);
            return;
        }

        // UI Update: Distinguish between Audit and Job Interview
        const headerTitle = document.querySelector('h2.font-bold.text-lg');
        const headerMode = document.querySelector('p.text-xs.text-slate-500 span');

        if (data.job_title && !data.is_audit) {
            if (headerTitle) headerTitle.innerText = `Interview: ${data.job_title}`;
            if (headerMode) {
                headerMode.innerText = data.company_name || "Official Assessment";
                headerMode.classList.remove('text-indigo-600');
                headerMode.classList.add('text-emerald-600');
            }
        } else {
            if (headerTitle) headerTitle.innerText = "Professional Profile Audit";
            if (headerMode) headerMode.innerText = "General Career Simulation";
        }

        // Initialize Stats and Page based on App Data
        _log("[INIT] Starting interview with data...");
        await startInterviewWithData(data);

    } catch (err) {
        console.error("[INIT] Initialization failed:", err);

        // 401 = session expired / invalid token
        if (err.message && (err.message.includes('401') || err.message.toLowerCase().includes('credential') || err.message.toLowerCase().includes('not authenticated'))) {
            console.warn("[INIT] Auth error. Redirecting to login.");
            localStorage.removeItem('token');
            Toast.show("Session expired. Redirecting to login...", 'warning');
            setTimeout(() => {
                const next = urlAppId ? `/interview?id=${urlAppId}` : '/interview';
                window.location.href = `/login?next=${encodeURIComponent(next)}`;
            }, 1500);
            return;
        }

        // If specific application failed, offer fallback
        if (activeAppId && (err.message.includes('404') || err.message.includes('403') || err.message.includes('Access denied') || err.message.includes('422') || err.message.includes('Validation Error'))) {
            console.warn(`[INIT] Application ${activeAppId} access error. Clearing and Retrying...`);
            localStorage.removeItem('active_app_id');

            // Also clear from URL to prevent infinite loop
            const newUrl = new URL(window.location);
            newUrl.searchParams.delete('id');
            window.history.replaceState({}, '', newUrl);

            Toast.show("Interview reference stale. Recovering your session...", 'info');
            setTimeout(() => window.location.reload(), 1500);
        } else {
            Toast.show("Failed to initialize interview. Please refresh.", 'error');
        }
    }
}

async function startInterviewWithData(data) {
    _log("[DATA] startInterviewWithData triggered for status:", data.status);

    // 1. Handle Terminal Statuses
    const terminalStatuses = ['hired', 'rejected', 'evaluated', 'completed'];
    const _iv = data.interview_entity || {};
    if (terminalStatuses.includes(data.status) || (_iv.interview_state ?? data.interview_state) === 'expired') {
        console.warn("[DATA] Interview already processed or terminal. Redirecting...");
        const msg = (_iv.interview_state ?? data.interview_state) === 'expired' 
            ? "This interview has expired and is no longer active."
            : "This interview has already been completed or is no longer active.";
        alert(msg);
        window.location.href = '/candidate/interviews';
        return;
    }

    // 2. Initialize Application State
    applicationId = data.id;
    localStorage.setItem('active_app_id', applicationId);
    cvBaselineSkills = null; // Reset baseline for fresh graph initialization
    window.userEmail = data.email;

    // INITIAL SCORE: Start with CV score as baseline if available
    if (data.cv_score !== undefined && data.cv_score !== null) {
        score = Number(data.cv_score);
        _log(`[DATA] Initializing live score with CV Score: ${score}`);
        updateUI();
    }

    _log(`[DATA] applicationId set to: ${applicationId}, email: ${window.userEmail}`);

    // 3. UI Background Setup
    if (data.job_title || data.declared_role) {
        const headerRole = document.getElementById('header-role');
        if (headerRole) headerRole.innerText = data.job_title || data.declared_role || "Technical Simulation";
    }

    // 4. Initial Talent Graph (from CV analysis)
    const _analysisJson = data.cv_entity?.analysis_json ?? data.analysis_json;
    if (_analysisJson) {
        try {
            const analysis = typeof _analysisJson === 'string' ? JSON.parse(_analysisJson) : _analysisJson;
            if (analysis && analysis.skill_metrics) {
                _log("[DATA] Updating talent graph from cv_entity.analysis_json");
                updateTalentGraph(analysis.skill_metrics, analysis.talent_analysis || "Initial CV Baseline", "", { source: 'cv' });
            }
        } catch (e) { console.warn("[DATA] Failed to parse analysis_json", e); }
    }

    // ─── NEW: Immediate History Restoration ───
    // We restore history as soon as data is loaded so the background isn't empty
    if (data.interview_log) {
        try {
            const history = typeof data.interview_log === 'string' ? JSON.parse(data.interview_log) : data.interview_log;
            if (Array.isArray(history) && history.length > 0) {
                _log("[INIT] Pre-restoring history to UI...");
                restoreSessionUI({
                    ...data,
                    history: history,
                    qa_history: data.qa_history || []
                });
            }
        } catch(e) { console.warn("[INIT] Failed to pre-restore history", e); }
    }
    
    // Sync critical variables before flow decision
    const _ivProgress = _iv.interview_progress ?? data.interview_progress;
    questionCount = (_ivProgress || 0) + 1;
    timeLeft = data.interview_time_left || 1800;
    
    // Ensure UI reflects current state immediately
    updateUI();

    // AUTO-START TIMER if interview is in progress
    if (data.status === 'in-progress' || (_iv.interview_state ?? data.interview_state) === 'in-progress') {
        _log("[INIT] Auto-starting timer for active session...");
        startTimer();
    }
    _log(`[INIT] UI Synced. Progress: ${_ivProgress}, Time Left: ${timeLeft}`);

    // 5. Decide Flow: Completion vs Resume vs Start Fresh
    const isFinished = (_iv.interview_state ?? data.interview_state) === 'completed';
    const isFlaggedAndDone = (_iv.interview_state ?? data.interview_state) === 'flagged' && (_ivProgress || 0) >= (data.total_questions || 15);

    if (isFinished || isFlaggedAndDone) {
        let log = [];
        try {
            log = typeof data.interview_log === 'string' ? JSON.parse(data.interview_log || "[]") : (data.interview_log || []);
        } catch(e) { log = []; }

        if (log.length > 0) {
            _log("[DATA] Interview state is finished. Restoring history & showing results.");
            // Restore UI state but DON'T start timer
            restoreSessionUI({
                ...data,
                history: log,
                qa_history: data.qa_history || []
            });
            if ((_iv.interview_state ?? data.interview_state) === 'flagged') {
                Toast.show("This session was flagged for review. Your results are being analyzed.", "warning");
            }
            showCompletionModal(data);
        } else if ((_iv.interview_state ?? data.interview_state) === 'expired') {
            alert("This interview session has expired.");
            window.location.href = '/candidate/interviews';
        } else {
            _log("[DATA] Status is finished but log is empty. Proceeding to preflight.");
            checkPreflightStatus();
        }
    } else {
        // Check if we can resume an in-progress session
        _log("[DATA] Checking for resume status...");
        try {
            const resumeData = await checkResumeStatus();
            if (resumeData && resumeData.can_resume && resumeData.history && resumeData.history.length > 0) {
                _log("[DATA] Session resumable. Progress:", resumeData.progress);
                resumeInterview(resumeData);
            } else if (window.resumeRestartHandled) {
                // startFreshInterview already handled the flow (window.location.reload usually)
                window.resumeRestartHandled = false;
            } else {
                _log("[DATA] Proceeding to fresh interview flow (Preflight).");
                checkPreflightStatus();
            }
        } catch (err) {
            console.error("[DATA] Resume check failed logic:", err);
            checkPreflightStatus();
        }
    }
}

// Continue old interview
async function resumeInterview(resumeData) {
    _log("[RESUME] Resuming session...", resumeData);
    restoreSessionUI(resumeData);
    startTimer();
    showPauseButton();
}

function restoreSessionUI(data) {
    _log("[STATE] Restoring UI components...", data);

    applicationId = data.application_id || data.id || applicationId;
    
    if (Number.isFinite(Number(data.total_questions)) && Number(data.total_questions) > 0) {
        maxQuestions = Number(data.total_questions);
    }
    
    const _restoreIv = data.interview_entity || {};
    questionCount = Number.isFinite(Number(data.progress)) ? Number(data.progress) : ((_restoreIv.interview_progress ?? data.interview_progress) || 1);
    
    // Restore score
    const resumeScore = Number(data.score_entity?.final_score ?? data.current_score ?? data.overall_score);
    score = Number.isFinite(resumeScore) && resumeScore >= 0 && resumeScore <= 100 ? resumeScore : 0;
    
    timeLeft = data.time_left !== undefined ? data.time_left : (data.interview_time_left !== undefined ? data.interview_time_left : 1800);
    if (!Number.isFinite(Number(timeLeft)) || Number(timeLeft) < 0) {
        timeLeft = 1800;
    }

    const resumeLanguage = normalizeInterviewLanguage(data.language)
        || normalizeInterviewLanguage(localStorage.getItem('interview_language'))
        || 'English';
    applyLanguageUI(resumeLanguage);

    // Restore History if available
    const cb = getChatBox();
    if (data.history && Array.isArray(data.history) && cb) {
        cb.innerHTML = '';
        data.history.forEach(msg => {
            if (msg.role !== 'system') {
                appendMessage(msg.role === 'user' ? 'user' : 'ai', msg.content);
            }
        });
    }

    // Restore Feedback History if available
    const qa_history = data.qa_history || [];
    if (qa_history && Array.isArray(qa_history)) {
        // Clear placeholder first
        const container = document.getElementById('feedback-container');
        if (container) {
            const empty = container.querySelector('.fb-empty');
            if (empty) empty.remove();
        }

        qa_history.forEach((qa, idx) => {
            if (qa.feedback) {
                addFeedbackItem(0, qa.feedback, idx + 1);
            }
        });
    }

    updateUI();
}

async function continueInterview() {
    const appId = localStorage.getItem('active_app_id');
    if (!appId) {
        checkPreflightStatus();
        return;
    }
    try {
        let resumeUrl = '/ai/interview/resume';
        if (applicationId) {
            resumeUrl += `?candidate_id=${applicationId}`;
            if (urlInterviewToken) resumeUrl += `&token=${urlInterviewToken}`;
        }
        const data = await window.fetchAPI(resumeUrl, {
            method: 'POST',
            body: JSON.stringify({ application_id: applicationId }),
            timeout: 15000
        });
        if (data && data.can_resume && data.history && data.history.length > 0) {
            resumeInterview(data);
            return;
        }
    } catch (error) {
        console.error('Continue interview failed:', error);
    }
    checkPreflightStatus();
}

function resetInterviewState() {
    _log("[STATE] Resetting interview session state");
    cvBaselineSkills = null;
    questionCount = 1;
    score = 0;
    timeLeft = 1800;
    if (chatBox) chatBox.innerHTML = '';
    isUpdatingGraph = false;

    // Reset UI
    if (qCounter) qCounter.innerHTML = `Start <span class="text-slate-300 text-sm"></span>`;
    if (timer) timer.innerText = "Ready";
    if (liveScore) liveScore.innerText = "0";

    // Reset Graph
    if (talentChart) {
        talentChart.data.datasets[0].data = [0, 0, 0, 0, 0, 0, 0];
        talentChart.data.datasets[1].data = [0, 0, 0, 0, 0, 0, 0];
        talentChart.update('none');
    }
}

// Start fresh interview
async function startFreshInterview() {
    resetInterviewState();

    const token = localStorage.getItem('token');
    const appId = localStorage.getItem('active_app_id');

    try {
        // FIXED: Using fetchAPI for consistency and correct pathing
        const data = await window.fetchAPI('/candidate/reset-interview', {
            method: 'POST',
            body: JSON.stringify({
                application_id: applicationId ? parseInt(applicationId) : (appId ? parseInt(appId) : undefined)
            })
        });

        // Hide modal
        document.getElementById('resume-modal').classList.add('hidden');

        // Reset local state
        questionCount = 1;
        score = (data.active_app_id || data.id) ? (data.score || 0) : 0;
        if (data.active_app_id || data.id) {
            localStorage.setItem('active_app_id', data.active_app_id || data.id);
        }

        timeLeft = 1800;
        if (chatBox) chatBox.innerHTML = '';

        // Clear old history
        window.oldHistory = null;
        window.oldQuestionCount = 0;

        // Show fresh start UI
        if (qCounter) qCounter.innerHTML = `Start <span class="text-slate-300 text-sm"></span>`;
        if (timer) timer.innerText = "Ready";
        if (liveScore) liveScore.innerText = "--";

        // Preserve language from onboarding if set
        const savedLang = localStorage.getItem('interview_language');
        if (savedLang) {
            selectedLanguage = normalizeInterviewLanguage(savedLang);
            _log('[FLOW] Preserving onboarding language:', selectedLanguage);
        } else {
            selectedLanguage = null;
        }

        // Check Pre-flight instead of direct language
        checkPreflightStatus();

        // Add welcome message
        appendMessage('ai', 'Welcome to your technical interview! Type "ready" to begin.');
    } catch (e) {
        console.error('Reset error:', e);
        Toast.show('Error resetting interview: ' + e.message, 'error');
    }
}

// Check hardware before choosing language
function checkPreflightStatus() {
    _log("[FLOW] checkPreflightStatus triggered. preflightDone:", window.preflightDone);
    // If already done in this session, skip
    if (window.preflightDone) {
        checkLanguageSelection();
        return;
    }
    const modal = document.getElementById('preflight-modal');
    if (modal) {
        _log("[FLOW] Showing preflight-modal");
        modal.classList.remove('hidden');
    } else {
        console.error("[ERR] preflight-modal not found!");
        checkLanguageSelection(); // Fallback
    }
}

let preflightStream = null;
let audioContext = null;
let analyser = null;
let microphone = null;
let javascriptNode = null;

async function runPreflight() {
    const btn = document.getElementById('btn-start-preflight');
    const camCheck = document.getElementById('cam-check');
    const micCheckRow = document.getElementById('mic-check-row');
    const video = document.getElementById('preflight-video');
    const micStatus = document.getElementById('mic-status');
    const micMeter = document.getElementById('mic-meter');

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i class="fas fa-spinner fa-spin mr-2"></i>Testing Hardware...`;
    }

    try {
        preflightStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });

        // Video Link
        if (video) video.srcObject = preflightStream;

        // UI OK
        if (camCheck) camCheck.classList.add('ok');
        const camStatusEl = document.getElementById('cam-status');
        if (camStatusEl) {
            camStatusEl.innerText = 'OK âœ“';
            camStatusEl.className = 'check-status ok';
        }

        if (micCheckRow) micCheckRow.classList.add('ok');
        const micStatusEl = document.getElementById('mic-check-status');
        if (micStatusEl) {
            micStatusEl.innerText = 'OK âœ“';
            micStatusEl.className = 'check-status ok';
        }

        if (micStatus) micStatus.innerText = 'Detected';

        // Start Mic Meter
        try {
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            analyser = audioContext.createAnalyser();
            microphone = audioContext.createMediaStreamSource(preflightStream);
            const updateMeter = () => {
                if (!analyser || !preflightStream.active) return;
                const array = new Uint8Array(analyser.frequencyBinCount);
                analyser.getByteFrequencyData(array);
                let values = 0;
                for (let i = 0; i < array.length; i++) values += array[i];
                const average = values / array.length;
                if (micMeter) micMeter.style.width = Math.min(100, average * 1.5) + "%";
                requestAnimationFrame(updateMeter);
            };

            analyser.smoothingTimeConstant = 0.8;
            analyser.fftSize = 1024;
            microphone.connect(analyser);
            updateMeter();
        } catch (e) {
            console.warn("Visualizer failed", e);
        }

        if (btn) btn.classList.add('hidden');
        const proceedBtn = document.getElementById('btn-proceed-to-lang');
        if (proceedBtn) proceedBtn.classList.remove('hidden');

    } catch (err) {
        console.error("Hardware access denied:", err);
        Toast.show("Permission denied. Camera and Microphone are required.", "error");
        if (btn) {
            btn.disabled = false;
            btn.innerText = "Retry Access Check";
        }
    }
}

function proceedAfterPreflight() {
    window.preflightDone = true;
    if (preflightStream) {
        preflightStream.getTracks().forEach(track => track.stop());
    }
    const modal = document.getElementById('preflight-modal');
    if (modal) modal.classList.add('hidden');
    checkLanguageSelection();
}

// Check if language is already selected
function checkLanguageSelection() {
    _log("[FLOW] checkLanguageSelection triggered");

    // If language was already set (from onboarding), skip the modal
    if (selectedLanguage) {
        _log('[FLOW] Language already selected:', selectedLanguage, '- skipping modal');
        applyLanguageUI(selectedLanguage);
        startInterview();
        return;
    }

    const modal = document.getElementById('language-modal');
    if (modal) modal.classList.remove('hidden');

    // Reset UI for fresh start
    if (qCounter) qCounter.innerHTML = `Start <span class="text-slate-300 text-sm"></span>`;
    if (timer) timer.innerText = "Ready";
    if (liveScore) liveScore.innerText = "--";
}

// Select language and start interview
function selectLanguage(lang, el) {
    applyLanguageUI(lang);

    // Visual feedback - highlight selected button
    document.querySelectorAll('.lang-opt').forEach(opt => {
        opt.classList.remove('selected');
    });
    if (el) el.classList.add('selected');

    // Small delay for visual feedback, then hide modal and start
    setTimeout(() => {
        const modal = document.getElementById('language-modal');
        if (modal) modal.classList.add('hidden');
        startInterview();
    }, 300);
}

// Start interview with selected language - AUTO TRIGGER
async function startInterview() {
    // UI Feedback
    if (!chatBox) {
        console.error("[CRITICAL] chatBox element not found in DOM during startInterview");
        Toast.show("Interface error: Chat container missing.", 'error');
        return;
    }
    const loadingId = 'loading-' + Date.now();
    const loadingDiv = document.createElement('div');
    loadingDiv.id = loadingId;
    loadingDiv.className = 'flex justify-center p-4';
    loadingDiv.innerHTML = `<div class="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>`;
    chatBox.appendChild(loadingDiv);

    // Send "Language: X" as the hidden handshake message
    try {
        const interviewLanguage = getInterviewLanguage();
        // 1. We assume reset-interview was already handled by startFreshInterview or caller
        // if not, we use fetchAPI for safety. 
        // However, doing it inside startInterview might be redundant.
        // Let's use fetchAPI for the handshake.
        let handshakeUrl = '/ai/interview/chat';
        if (applicationId) {
            handshakeUrl += `?candidate_id=${applicationId}`;
            if (urlInterviewToken) handshakeUrl += `&token=${urlInterviewToken}`;
        }

        const data = await window.fetchAPI(handshakeUrl, {
            method: 'POST',
            body: JSON.stringify({
                candidate_id: applicationId,
                message: interviewLanguage,
                language: interviewLanguage
            }),
            timeout: 180000 // 3 minutes for initial handshake/analysis
        });

        // Keep client language state aligned with server-locked interview language.
        if (data && data.language) {
            const serverLanguage = normalizeInterviewLanguage(data.language);
            if (serverLanguage) applyLanguageUI(serverLanguage);
        }

        if (document.getElementById(loadingId)) document.getElementById(loadingId).remove();

        // Show AI Question (Q1)
        _log("[START] AI Reply received:", data.reply);
        if (data.reply) {
            appendMessage('ai', data.reply);
            if (typeof markQuestionReceived === 'function') markQuestionReceived();
        } else {
            console.warn("[START] AI Reply was empty. Using fallback.");
            appendMessage('ai', "Welcome! Let's begin the interview. I'll be asking you technical questions to assess your skills. Ready?");
            if (typeof markQuestionReceived === 'function') markQuestionReceived();
        }
        if (data.feedback) {
            addFeedbackItem(0, data.feedback, 0);
        }

        // Initialize Stats
        // Initialize Stats
        // If backend omitted current_score (grade skip), use null (or preserve existing if any) 
        score = (data.current_score !== undefined) ? data.current_score : null;

        {
            const liveSkills = resolveLiveSkills(data.skills, data.current_score !== undefined ? data.current_score : score);
            const baselineSkills = resolveBaselineSkills(data.cv_skill_metrics, liveSkills, score);
            updateTalentGraph(baselineSkills, data.talent_analysis || "Initial CV Baseline", "", { source: 'cv' });
            // Update Radar Chart
            const analysis = data.talent_analysis || "Deep technical match check complete.";
            updateTalentGraph(liveSkills, analysis, "", { source: 'live' });

        }
        if (Number.isFinite(Number(data.total_questions)) && Number(data.total_questions) > 0) {
            maxQuestions = Number(data.total_questions);
        }
        questionCount = 1; // Handshake is done, this is Q1 state

        // Update UI
        updateUI();
        startTimer();
        showPauseButton();
        // startRecording() removed — startEnterpriseRecording() handles video recording

    } catch (error) {
        console.error("Start Interview Handshake Failed:", error);
        const errorMsg = error.message || "System Connection Error";
        
        // Remove loading
        if (document.getElementById(loadingId)) document.getElementById(loadingId).remove();

        appendMessage('ai', `Interview initiation failed.\n\n${errorMsg}\n\nPlease refresh the page to try again.`);
        Toast.show("Interview could not start.", 'error');
    }
}

function startRecording() {
    if (!webcamStream) return;
    recordedChunks = [];
    try {
        const options = { mimeType: 'video/webm;codecs=vp8,opus' };
        if (!MediaRecorder.isTypeSupported(options.mimeType)) {
            console.warn("VP8 not supported, trying default");
            delete options.mimeType;
        }
        mediaRecorder = new MediaRecorder(webcamStream, options);
        mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) recordedChunks.push(e.data);
        };
        mediaRecorder.start(1000); // 1s chunks
        _log("🎥 Video recording started");

        const recInd = document.getElementById('rec-indicator');
        if (recInd) recInd.style.display = 'flex';
    } catch (err) {
        console.error("Failed to start recording:", err);
    }
}

let _lastTimerStart = 0;
let _serverSyncInterval = null;

function startTimer() {
    const now = Date.now();
    if (now - _lastTimerStart < 500) return;
    _lastTimerStart = now;

    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }
    
    if (!Number.isFinite(timeLeft) || timeLeft <= 0) {
        console.warn("[TIMER] Invalid timeLeft detected:", timeLeft, "- Defaulting to 1800s");
        timeLeft = 1800;
    }

    _log("[TIMER] Starting countdown from:", timeLeft);
    
    updateUI();

    timerInterval = setInterval(() => {
        try {
            timeLeft--;
            
            if (timeLeft % 10 === 0) {
                _log("[TIMER] Tick. Time left:", timeLeft);
            }

            const progressFill = document.getElementById('timer-progress-fill');
            const progressWrap = document.getElementById('timer-progress-wrap');
            if (progressWrap) progressWrap.style.display = 'block';
            if (progressFill) {
                const pct = (timeLeft / 1800) * 100;
                progressFill.style.width = `${pct}%`;
                if (timeLeft < 300) progressFill.style.background = 'var(--red)';
                else if (timeLeft < 900) progressFill.style.background = 'var(--amber)';
                else progressFill.style.background = 'var(--purple)';
            }

            updateUI();

            if (timeLeft <= 0) {
                timeLeft = 0;
                updateUI();
                clearInterval(timerInterval);
                timerInterval = null;
                stopServerTimeSync();
                _log("[TIMER] Time expired.");
                appendMessage('ai', "Global Time Limit Reached! End of Interview.");
                endInterview();
            }
        } catch (err) {
            console.error("[TIMER] Interval error:", err);
        }
    }, 1000);
    
    _log("[TIMER] Interval started, ID:", timerInterval);
    startServerTimeSync();
}

function startServerTimeSync() {
    stopServerTimeSync();
    _serverSyncInterval = setInterval(async () => {
        if (!applicationId || !timerInterval) return;
        try {
            let syncUrl = `/ai/interview/time?candidate_id=${applicationId}`;
            if (urlInterviewToken) syncUrl += `&token=${urlInterviewToken}`;
            const data = await window.fetchAPI(syncUrl, { timeout: 5000 });
            if (data && Number.isFinite(Number(data.time_left))) {
                const serverTime = Number(data.time_left);
                const drift = Math.abs(serverTime - timeLeft);
                if (drift > 5) {
                    _log(`[TIMER SYNC] Drift detected: ${drift}s. Adjusting from ${timeLeft}s to ${serverTime}s`);
                    timeLeft = serverTime;
                    updateUI();
                }
            }
        } catch (err) {
            console.warn("[TIMER SYNC] Failed to sync with server:", err.message);
        }
    }, 60000);
}

function stopServerTimeSync() {
    if (_serverSyncInterval) {
        clearInterval(_serverSyncInterval);
        _serverSyncInterval = null;
    }
}

function updateUI() {
    const elTimer = getTimer();
    const elScore = getLiveScore();
    const elQCount = getQCounter();

    // Timer Format
    if (elTimer) {
        const m = Math.floor(timeLeft / 60).toString().padStart(2, '0');
        const s = (timeLeft % 60).toString().padStart(2, '0');
        elTimer.innerText = `${m}:${s}`;
        
        // Color Warning
        if (timeLeft < 300) elTimer.classList.add('text-red-600');
        else elTimer.classList.remove('text-red-600');
        
        // If not running but we have time, show static time
        if (!timerInterval && timeLeft > 0) {
            _log("[UI] Timer static update:", timeLeft);
        }
    }

    // Score & Question
    if (liveScore) {
        if (SHOW_LIVE_SCORE) {
            liveScore.innerText = score !== null ? Math.round(score) : "--";
        } else {
            // Hide the live score entirely (Bug B-19). We replace the
            // visible number with a neutral "—/100" so the surrounding
            // layout doesn't shift; the candidate sees a stable
            // "interview in progress" indicator instead of a moving
            // target they can game or get demotivated by.
            liveScore.innerText = "—/100";
            liveScore.setAttribute("aria-label", "Live score hidden during interview");
        }
    }

    // Display Logic
    const displayCount = Math.max(0, questionCount - 1);
    const totalQuestions = Number.isFinite(Number(maxQuestions)) && Number(maxQuestions) > 0 ? Number(maxQuestions) : 15;
    
    // Counter Update
    if (qCounter) {
        if (displayCount <= 0) {
            qCounter.innerHTML = `Start <span class="text-slate-300 text-sm"></span>`;
        } else {
            XSS.safeSetHTML(qCounter, `${Math.min(displayCount, totalQuestions)}<span class="text-slate-300 text-sm">/${totalQuestions}</span>`);
        }
    }

    // Timer Update
    if (timer) {
        timer.innerText = formatTime(timeLeft);
    }

    // Score Update (mirrors the block above; kept for legacy callers)
    if (liveScore && SHOW_LIVE_SCORE) {
        liveScore.innerText = Math.round(score);
    }
}

function showFeedback(text, color) {
    const el = document.createElement('div');
    el.className = `fixed top-24 left-1/2 transform -translate-x-1/2 px-6 py-2 rounded-full font-bold text-white shadow-xl z-50 animate-bounce ${color === 'red' ? 'bg-red-500' : 'bg-emerald-500'}`;
    el.innerText = text;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 2000);
}

// QCM REMOVED - All questions are now open-ended
// Candidates type full answers instead of selecting options

function appendMessage(role, text) {
    const messageText = extractMessageText(text);
    const cb = getChatBox();
    if (!cb) {
        console.error("[CHAT] Cannot append message: chatBox not found");
        return;
    }

    _log(`[CHAT] Appending ${role} message:`, messageText);
    const container = document.createElement('div');
    container.className = role === 'ai' ? 'chat-container-ai' : 'chat-container-user';

    const avatarWrap = document.createElement('div');
    avatarWrap.className = 'msg-av';
    const avatarInner = document.createElement('div');
    avatarInner.className = role === 'ai' ? 'ai-inner-avatar' : 'user-av';
    const icon = document.createElement('i');
    icon.className = role === 'ai' ? 'fas fa-robot' : 'fas fa-user';
    avatarInner.appendChild(icon);
    avatarWrap.appendChild(avatarInner);

    const bubble = document.createElement('div');
    bubble.className = role === 'ai' ? 'chat-bubble ai' : 'chat-bubble user';
    bubble.textContent = messageText;

    container.appendChild(avatarWrap);
    container.appendChild(bubble);

    cb.appendChild(container);
    cb.scrollTop = cb.scrollHeight;
}

function showTyping() {
    const row = document.createElement('div');
    row.id = 'typing-indicator';
    row.className = 'chat-container-ai';
    row.innerHTML = `
        <div class="msg-av"><div class="ai-inner-avatar"><i class="fas fa-robot"></i></div></div>
        <div class="chat-bubble ai">
            <span class="typing"></span>
            <span class="typing" style="animation-delay:0.2s"></span>
            <span class="typing" style="animation-delay:0.4s"></span>
        </div>
    `;
    chatBox.appendChild(row);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function removeTyping() {
    const el = document.getElementById('typing-indicator');
    if (el) el.remove();
}

function addFeedbackItem(scoreDiff, explanation, questionNum) {
    const container = document.getElementById('feedback-container');
    if (!container) return;

    // Clear placeholder
    const empty = container.querySelector('.fb-empty');
    if (empty) empty.remove();

    const fb = document.createElement('div');
    const isPos = scoreDiff > 0;
    const isNeg = scoreDiff < 0;

    fb.className = `fb-item ${isPos ? 'pos' : (isNeg ? 'neg' : 'neu')}`;

    if (SHOW_LIVE_SCORE) {
        const scoreVal = Math.round(scoreDiff);
        const scoreText = scoreVal > 0 ? `+${scoreVal}` : scoreVal;
        const scoreClass = isPos ? 'pos' : (isNeg ? 'neg' : 'neu');

        const scoreEl = document.createElement('div');
        scoreEl.className = `fb-score ${scoreClass}`;
        scoreEl.textContent = String(scoreText);
        fb.appendChild(scoreEl);
    }

    const textEl = document.createElement('div');
    textEl.className = 'fb-text';
    textEl.textContent = extractMessageText(explanation);

    fb.appendChild(textEl);

    // Add to top
    container.insertBefore(fb, container.firstChild);

    // Limit to 5
    while (container.children.length > 5) {
        container.removeChild(container.lastChild);
    }
}

async function endInterview() {
    clearInterval(timerInterval);
    timerInterval = null;

    // Show Analyzer Loading State
    const loadingId = 'analyzer-loading';
    if (!document.getElementById(loadingId)) {
        const loadingDiv = document.createElement('div');
        loadingDiv.id = loadingId;
        loadingDiv.className = 'fixed inset-0 bg-slate-900/80 z-[10000] flex flex-col items-center justify-center backdrop-blur-sm';
        loadingDiv.innerHTML = `
            <div class="bg-white p-8 rounded-3xl shadow-2xl text-center max-w-md mx-4 transform transition-all scale-100">
                <div class="relative w-20 h-20 mx-auto mb-6">
                    <div class="absolute inset-0 border-4 border-indigo-100 rounded-full"></div>
                    <div class="absolute inset-0 border-4 border-indigo-600 rounded-full border-t-transparent animate-spin"></div>
                    <i class="fas fa-brain absolute inset-0 flex items-center justify-center text-indigo-600 text-2xl animate-pulse"></i>
                </div>
                <h2 class="text-2xl font-black text-slate-800 mb-2">Finalizing Results</h2>
                <p class="text-slate-500 font-medium mb-4" id="analyzer-text">Our AI is analyzing your answers against ${window.expertRole || 'the role'} standards...</p>
                
                <div id="upload-progress-wrap" style="display: none;">
                    <div class="flex justify-between text-xs font-bold text-slate-400 mb-1">
                        <span>Uploading Recording</span>
                        <span id="upload-pct">0%</span>
                    </div>
                    <div class="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
                        <div id="upload-bar" class="bg-indigo-600 h-full transition-all duration-300" style="width: 0%"></div>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(loadingDiv);
    }

    // Stop and Upload Video
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
        const recInd = document.getElementById('rec-indicator');
        if (recInd) recInd.style.display = 'none';
        await uploadVideo();
    }

    try {
        let evalUrl = '/ai/interview/evaluate-final';
        if (applicationId) {
            evalUrl += `?application_id=${applicationId}`;
            if (urlInterviewToken) evalUrl += `&token=${urlInterviewToken}`;
        }
        const data = await window.fetchAPI(evalUrl, {
            method: 'POST',
            body: JSON.stringify({ application_id: applicationId }),
            timeout: 300000
        });

        if (data) {
            _log("Final Evaluation:", data);
            showCompletionModal(data);
        }
    } catch (e) {
        console.error("Evaluation Error", e);
        // Fallback: show modal with current local score even if final eval failed
        showCompletionModal({ final_score: score });
    } finally {
        const loader = document.getElementById(loadingId);
        if (loader) loader.remove();
    }
}

async function uploadVideo() {
    if (recordedChunks.length === 0) return;

    const blob = new Blob(recordedChunks, { type: 'video/webm' });
    const formData = new FormData();
    formData.append('file', blob, 'interview_recording.webm');
    formData.append('application_id', applicationId);

    const progressWrap = document.getElementById('upload-progress-wrap');
    const progressBar = document.getElementById('upload-bar');
    const progressPct = document.getElementById('upload-pct');
    const analyzerText = document.getElementById('analyzer-text');

    if (progressWrap) progressWrap.style.display = 'block';
    if (analyzerText) analyzerText.innerText = "Securing your interview recording...";

    return new Promise((resolve) => {
        const xhr = new XMLHttpRequest();
        const uploadUrl = `${CONFIG.API_BASE_URL}${CONFIG.API_PREFIX}/ai/interview/upload-video?application_id=${applicationId}`;
        xhr.open('POST', uploadUrl, true);

        // CSRF token for mutation
        const csrfMatch = document.cookie.match(/csrf_token=([^;]+)/);
        if (csrfMatch) {
            xhr.setRequestHeader('X-CSRF-Token', csrfMatch[1]);
        }

        // Progress tracking
        xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) {
                const pct = Math.round((e.loaded / e.total) * 100);
                if (progressBar) progressBar.style.width = `${pct}%`;
                if (progressPct) progressPct.innerText = `${pct}%`;
            }
        };

        xhr.onload = () => {
            if (analyzerText) analyzerText.innerText = "Finalizing AI analysis...";
            _log("✅ Video upload complete");
            resolve();
        };

        xhr.onerror = () => {
            console.error("❌ Video upload failed");
            resolve(); // Still resolve to let evaluation continue
        };

        xhr.send(formData);
    });
}

// Enterprise: Segmented Video Recording
function startEnterpriseRecording() {
    if (!webcamStream) return;

    try {
        const options = { mimeType: 'video/webm;codecs=vp8,opus' };
        mediaRecorder = new MediaRecorder(webcamStream, options);

        mediaRecorder.ondataavailable = (event) => {
            if (event.data && event.data.size > 0) {
                uploadVideoSegment(event.data);
            }
        };

        // Request segments every 30 seconds
        mediaRecorder.start(SEGMENT_DURATION_MS);
        _log("🎥 Enterprise Segmented Recording Started");

    } catch (err) {
        console.error("Failed to start enterprise recording:", err);
    }
}

async function uploadVideoSegment(blob) {
    if (!applicationId) return;

    const formData = new FormData();
    formData.append('video_segment', blob, `segment_${Date.now()}.webm`);

    try {
        let uploadUrl = `/ai/interview/upload-segment?application_id=${applicationId}`;
        if (urlInterviewToken) uploadUrl += `&token=${urlInterviewToken}`;
        
        await window.fetchAPI(uploadUrl, {
            method: 'POST',
            body: formData,
            priority: 'low',
            timeout: 120000 // 2 minutes for segmented uploads
        });
        console.debug("✅ Video segment uploaded");
    } catch (err) {
        console.error("❌ Segment upload failed:", err);
    }
}

function showCompletionModal(data) {
    const finalScore = data.final_score !== undefined ? data.final_score : (score || 0);

    const elFinalScore = document.getElementById('final-score');
    const elReliability = document.getElementById('final-reliability');
    const elHireProb = document.getElementById('final-hire-prob');
    const elConfidence = document.getElementById('final-confidence');
    const elDecision = document.getElementById('v3-decision-badge');

    if (elFinalScore) elFinalScore.innerText = Math.round(finalScore);
    
    // V3 Decision Intelligence Sync
    if (elHireProb) elHireProb.innerText = (data.hire_probability || 0).toFixed(1) + '%';
    if (elConfidence) elConfidence.innerText = (data.confidence_score || 0).toFixed(1);
    if (elDecision) {
        elDecision.innerText = data.hiring_decision || "EVALUATED";
        // Color coding for decision
        if (elDecision.innerText.includes("REJECT")) elDecision.style.color = "var(--red)";
        else if (elDecision.innerText.includes("RECOMMENDED")) elDecision.style.color = "var(--green)";
        else elDecision.style.color = "var(--indigo)";
    }

    if (elReliability) {
        if (trustScore > 80) elReliability.innerText = "High";
        else if (trustScore > 40) elReliability.innerText = "Medium";
        else elReliability.innerText = "Low";
    }

    // FIX: Update Talent Graph with skill_metrics if available
    if (data.skill_metrics) {
        _log("[COMPLETION] Updating talent graph with skill_metrics:", data.skill_metrics);
        const analysisText = data.detailed_feedback || data.explainability?.why_this_score || "Interview Analysis";
        updateTalentGraph(data.skill_metrics, [analysisText], data.recommendation, { source: 'live' });
    }

    // --- Phase 4: Render AI Roadmap ---
    if (data.roadmap_json) {
        try {
            const roadmap = typeof data.roadmap_json === 'string' ? JSON.parse(data.roadmap_json) : data.roadmap_json;
            const summaryEl = document.getElementById('roadmap-summary');
            const itemsEl = document.getElementById('roadmap-items');

            if (summaryEl && roadmap.summary) {
                summaryEl.innerText = roadmap.summary;
                summaryEl.classList.remove('hidden');
            }

            if (itemsEl && roadmap.roadmap) {
                itemsEl.innerHTML = roadmap.roadmap.map(item => `
                    <div class="bg-white/10 p-3 rounded-lg border border-white/10 hover:border-indigo-500/50 transition">
                        <div class="flex justify-between items-start mb-1">
                            <span class="text-xs font-bold text-white">${item.milestone}</span>
                            <span class="text-[10px] px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-400 font-bold">${item.weeks}</span>
                        </div>
                        <div class="text-[10px] text-slate-400">${item.action_items[0] || ''}</div>
                        ${item.course_id ? `
                            <div class="mt-2 text-[9px] font-bold text-emerald-400 flex items-center gap-1">
                                <i class="fas fa-graduation-cap"></i> Recommended Course Available
                            </div>
                        ` : ''}
                    </div>
                `).join('');
                itemsEl.classList.remove('hidden');
            }
        } catch (e) {
            console.error("Roadmap Render Error:", e);
        }
    }

    const modal = document.getElementById('completion-modal');
    if (modal) modal.classList.remove('hidden');

    // Add metadata for potential automation
    window.interviewCompleteData = data;
}


// Voice recognition removed

// --- ANTI-CHEAT SYSTEM ---
function setupAntiCheat() {
    _log("[INIT] Setting up anti-cheat listeners...");
    
    // 1. Tab Switching Detection (Logs violation, reduces trust)
    document.addEventListener('visibilitychange', () => {
        if (document.hidden && !gracePeriod) {
            console.warn("⚠️ Tab switch detected — trust penalty applied");
            updateTrust(-3, "Tab switch detected");
        }
    });

    if (input) {
        // 2. Prevent Copy/Paste
        input.addEventListener('paste', (e) => {
            e.preventDefault();
            handleCheatAttempt("Pasting is forbidden");
        });

        input.addEventListener('copy', (e) => {
            e.preventDefault();
            handleCheatAttempt("Copying is forbidden");
        });
    }

    // Allow 10 seconds for setup/fullscreen transitions
    setTimeout(() => { 
        gracePeriod = false; 
        _log("Anti-Cheat Active"); 
    }, 10000);
}

async function handleCheatAttempt(reason) {
    if (gracePeriod) {
        _log(`Grace Period detected: ${reason} ignored.`);
        return;
    }

    cheatCount++;

    // 1. Immediate Visual Feedback
    // score = 0; // DISABLED: Score preserved for review
    updateUI();

    // 2. Show Blocking Overlay
    const overlay = document.createElement('div');
    overlay.className = "fixed inset-0 bg-red-900/90 z-[9999] flex flex-col items-center justify-center text-center p-8 backdrop-blur-xl";
    overlay.innerHTML = `
                <div class="text-6xl text-white mb-6 animate-pulse"><i class="fas fa shield-alt"></i></div>
                <h1 class="text-4xl font-black text-white mb-2">FRAUD DETECTED</h1>
                <p class="text-xl text-red-200 font-bold max-w-lg">${reason}</p>
                <p class="text-sm text-white/50 mt-8 uppercase tracking-widest">Redirecting to Dashboard...</p>
            `;
    document.body.appendChild(overlay);

    // 3. Report to Backend (Reliable)
    try {
        let fraudUrl = '/ai/interview/report-fraud';
        if (applicationId) {
            fraudUrl += `?application_id=${applicationId}`;
            if (urlInterviewToken) fraudUrl += `&token=${urlInterviewToken}`;
        }
        fetchAPI(fraudUrl, {
            method: 'POST',
            body: JSON.stringify({ application_id: applicationId, reason: reason }),
            keepalive: true
        });
    } catch (e) { console.error("Report Fraud Failed", e); }

    // 4. Force Redirect
    setTimeout(() => {
        window.location.replace('/dashboard');
    }, 1500);
}

// ============================================
// ADVANCED ANTI-CHEAT FEATURES
// ============================================

// 3. DevTools Detection (window size difference heuristic)
(function detectDevTools() {
    const devToolsThreshold = 160;
    let devToolsWarned = false;
    setInterval(() => {
        if (gracePeriod) return;
        const widthDiff = window.outerWidth - window.innerWidth > devToolsThreshold;
        const heightDiff = window.outerHeight - window.innerHeight > devToolsThreshold;
        if ((widthDiff || heightDiff) && !devToolsWarned) {
            devToolsWarned = true;
            console.warn("⚠️ DevTools detected — trust penalty applied");
            updateTrust(-10, "DevTools opened");
            const badge = document.querySelector('.col-left .badge');
            if (badge) { badge.innerText = "⛔ DevTools"; badge.className = "badge badge-red"; }
        }
        if (!widthDiff && !heightDiff) devToolsWarned = false;
    }, 2000);
})();

// 4. Window Blur Detection (second window/Alt-Tab)
window.addEventListener('blur', () => {
    if (gracePeriod) return;
    console.warn("⚠️ Window lost focus — trust penalty applied");
    updateTrust(-2, "Window focus lost");
});

// 5. Answer Latency Tracking (suspiciously fast answers)
// Increased from 3s to 8s to reduce false positives on knowledgeable candidates
const FAST_ANSWER_THRESHOLD_MS = 8000;

function markQuestionReceived() {
    lastQuestionTime = Date.now();
}

function checkAnswerLatency() {
    const elapsed = Date.now() - lastQuestionTime;
    if (elapsed < FAST_ANSWER_THRESHOLD_MS && !gracePeriod) {
        console.warn(`⚠️ Suspiciously fast answer (${(elapsed / 1000).toFixed(1)}s)`);
        updateTrust(-3, "Suspiciously fast answer");
        return true;
    }
    return false;
}

// 6. Right-click prevention
document.addEventListener('contextmenu', (e) => {
    if (!gracePeriod) {
        e.preventDefault();
        updateTrust(-1, "Right-click attempt");
    }
});

// ============================================
// SAVE/RESUME FUNCTIONALITY
// ============================================

async function checkResumeStatus() {
    const appId = localStorage.getItem('active_app_id') || applicationId;
    if (!appId) {
        console.warn("[RESUME] No application ID found in storage or URL.");
        return false;
    }

    try {
        let resumeUrl = '/ai/interview/resume';
        if (applicationId) {
            resumeUrl += `?candidate_id=${applicationId}`;
            if (urlInterviewToken) resumeUrl += `&token=${urlInterviewToken}`;
        }
        const data = await window.fetchAPI(resumeUrl, {
            method: 'POST',
            body: JSON.stringify({ application_id: applicationId }),
            timeout: 15000
        });

        if (data.can_resume && data.history && data.history.length > 0) {
            // Show resume modal
            const shouldResume = await showResumeModal(data);

            if (shouldResume) {
                // Return data to restore state
                return data;
            } else {
                // User chose to start fresh
                window.resumeRestartHandled = true;
                await startFreshInterview();
                return false;
            }
        }
    } catch (error) {
        console.error('Resume check failed:', error);
    }

    return false;
}

function showResumeModal(data) {
    return new Promise((resolve) => {
        const totalQuestions = Number.isFinite(Number(data.total_questions)) && Number(data.total_questions) > 0 ? Number(data.total_questions) : maxQuestions;
        const progressCount = Number.isFinite(Number(data.progress)) ? Number(data.progress) : 0;
        const currentScore = Number.isFinite(Number(data.current_score)) ? Number(data.current_score) : 0;
        const percentage = Math.round((progressCount / totalQuestions) * 100);
        const lastSaved = data.last_saved ? new Date(data.last_saved).toLocaleString() : 'Unknown';

        const modal = document.createElement('div');
        modal.className = 'fixed inset-0 bg-black/60 flex items-center justify-center z-[9999] backdrop-blur-sm';
        modal.innerHTML = `
                    <div class="bg-white dark:bg-slate-800 rounded-2xl p-8 max-w-md shadow-2xl animate-fadeIn mx-4">
                        <div class="text-center mb-6">
                            <div class="w-20 h-20 bg-yellow-100 dark:bg-yellow-900/30 rounded-full flex items-center justify-center mx-auto mb-4">
                                <i class="fas fa-pause-circle text-5xl text-yellow-500"></i>
                            </div>
                            <h2 class="text-2xl font-bold mb-2 text-slate-900 dark:text-white">Resume Session</h2>
                            <p class="text-slate-600 dark:text-slate-400">
                                You have an interview in progress
                            </p>
                        </div>
                        
                        <div class="bg-indigo-50 dark:bg-indigo-900/20 rounded-xl p-4 mb-6">
                            <div class="flex justify-between mb-3">
                                <span class="font-semibold text-slate-700 dark:text-slate-300">Progress:</span>
                                <span class="text-indigo-600 dark:text-indigo-400 font-bold">${progressCount}/${totalQuestions} questions</span>
                            </div>
                            <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3 mb-3">
                                <div class="bg-indigo-600 h-3 rounded-full transition-all" style="width: ${percentage}%"></div>
                            </div>
                            ${SHOW_LIVE_SCORE ? `
                            <div class="flex justify-between text-sm">
                                <span class="text-slate-500 dark:text-slate-400">Current Score:</span>
                                <span class="font-bold text-slate-700 dark:text-slate-300">${currentScore}/100</span>
                            </div>
                            ` : ''}
                            <div class="text-xs text-slate-500 dark:text-slate-400 mt-2">
                                Last saved: ${safeText(lastSaved)}
                            </div>
                        </div>

                        <div class="flex">
                            <button id="resume-btn" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-4 rounded-xl font-bold transition-all shadow-lg shadow-indigo-500/30 hover:scale-[1.02] active:scale-95 flex items-center justify-center gap-3">
                                <i class="fas fa-play"></i> Continue from where you left off
                            </button>
                        </div>
                    </div>
                `;

        document.body.appendChild(modal);

        document.getElementById('resume-btn').onclick = () => {
            modal.remove();
            resolve(true);
        };
    });
}

async function pauseInterview() {
    const appId = localStorage.getItem('active_app_id') || applicationId;
    if (!appId) {
        console.error('[ERROR] Cannot pause: No applicationId found.');
        Toast.show('Cannot pause: No active session found.', 'error');
        return;
    }

    try {
        let pauseUrl = '/ai/interview/pause';
        if (applicationId) {
            pauseUrl += `?application_id=${applicationId}`;
            if (urlInterviewToken) pauseUrl += `&token=${urlInterviewToken}`;
        }
        await window.fetchAPI(pauseUrl, {
            method: 'POST',
            body: JSON.stringify({ 
                application_id: applicationId,
                time_left: timeLeft 
            }),
            timeout: 15000
        });

        Toast.show('Interview paused. Redirecting to dashboard...', 'success');
        setTimeout(() => {
            window.location.href = '/dashboard';
        }, 2000);
    } catch (error) {
        console.error('Pause failed:', error);
        Toast.show('Failed to pause interview', 'error');
    }
}

// Pause button click handler
document.getElementById('pause-interview-btn')?.addEventListener('click', async () => {
    const confirmed = confirm('Pause interview? You can resume anytime from your dashboard.');
    if (confirmed) {
        await pauseInterview();
    }
});

// Show pause button once interview starts (call this after first question)
function showPauseButton() {
    const pauseBtn = document.getElementById('pause-interview-btn');
    if (pauseBtn) {
        pauseBtn.classList.remove('hidden');
    }
}

// --- ADVANCED PROCTORING: face-api.js with face rectangles & emotion ---
function toggleSidebar(side) {
    const el = document.querySelector(side === 'left' ? '.col-left' : '.col-right');
    if (!el) return;

    // Toggle active class
    el.classList.toggle('active');

    // Auto-hide other if visible on very small screens
    if (window.innerWidth < 640 && el.classList.contains('active')) {
        const other = document.querySelector(side === 'left' ? '.col-right' : '.col-left');
        if (other) other.classList.remove('active');
    }
}

async function initWebcam() {
    if (webcamStream) return; // FIX: Prevent multiple webcam streams
    const video = document.getElementById('webcam');
    if (!video) return;

    try {
        webcamStream = await navigator.mediaDevices.getUserMedia({ video: { width: 320, height: 240, facingMode: 'user' } });
        video.srcObject = webcamStream;

        // Wait for video to be ready
        await new Promise(resolve => {
            video.onloadedmetadata = () => { video.play(); resolve(); };
        });

        // Load face-api.js models
        _log("🔄 Loading AI Vision Models...");
        const badge = document.querySelector('.col-left .badge');

        if (typeof faceapi === 'undefined') {
            console.warn("⚠️ face-api.js not loaded — proctoring disabled");
            if (badge) { badge.innerText = "Unavailable"; badge.className = "badge badge-amber"; }
            return;
        }

        await Promise.all([
            faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL),
            faceapi.nets.faceExpressionNet.loadFromUri(MODEL_URL)
        ]);

        faceApiReady = true;
        _log("✅ AI Vision Models loaded (TinyFaceDetector + FaceExpression)");

        // Setup canvas overlay
        const canvas = document.getElementById('face-canvas');
        if (canvas) {
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
        }

        startDetection();
    } catch (err) {
        console.error("Webcam/AI init error:", err);
        const badge = document.querySelector('.col-left .badge');
        if (badge) { badge.innerText = "Unavailable"; badge.className = "badge badge-amber"; }
        const emotionEl = document.getElementById('emotion-badge');
        if (emotionEl) emotionEl.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Camera denied';
    }
}

// Emotion icons mapping
const EMOTION_ICONS = {
    neutral: '😐', happy: '😊', sad: '😢', angry: '😠',
    fearful: '😨', disgusted: '🤢', surprised: '😲'
};

function startDetection() {
    const video = document.getElementById('webcam');
    const canvas = document.getElementById('face-canvas');
    const badge = document.querySelector('.col-left .badge');
    const emotionEl = document.getElementById('emotion-badge');
    const faceCountEl = document.getElementById('face-count');

    if (!canvas || !video) return;
    const ctx = canvas.getContext('2d');

    const options = new faceapi.TinyFaceDetectorOptions({ inputSize: 416, scoreThreshold: 0.1 });
    
    if (detectionInterval) clearInterval(detectionInterval);
    detectionInterval = setInterval(async () => {
        if (!faceApiReady || !video || video.readyState < 2) return;

        try {
            // Detect faces + expressions
            const detections = await faceapi.detectAllFaces(video, options).withFaceExpressions();

            // Clear canvas
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            // Scale factor: canvas size may differ from display size
            const scaleX = canvas.width / video.videoWidth;
            const scaleY = canvas.height / video.videoHeight;

            const faceCount = detections.length;

            // Update face count badge
            if (faceCountEl) {
                XSS.safeSetHTML(faceCountEl, `<i class="fas fa-user${faceCount > 1 ? 's' : ''}"></i> ${faceCount} face${faceCount !== 1 ? 's' : ''}`);
                faceCountEl.className = 'face-count-badge' + (faceCount === 0 ? ' warn' : faceCount > 1 ? ' danger' : '');
            }

            if (faceCount === 0) {
                // --- NO FACE ---
                window.multiFaceCounter = 0; // Reset multi-face tracking
                noFaceCounter++;

                // 8 intervals * 800ms = 6.4 seconds grace period
                if (noFaceCounter > 8) {
                    if (noFaceCounter % 10 === 6) {
                        updateTrust(-2, "Face not detected");
                    }
                    if (badge) { badge.innerText = "⚠ No Face"; badge.className = "badge badge-amber"; }
                }
                if (emotionEl) emotionEl.innerHTML = '<i class="fas fa-eye-slash"></i> No face detected';
            } else if (faceCount > 1) {
                // --- MULTIPLE FACES ---
                noFaceCounter = 0; // Reset no-face tracking
                if (typeof window.multiFaceCounter === 'undefined') window.multiFaceCounter = 0;
                window.multiFaceCounter++;

                // 2 intervals * 800ms = 1.6s grace period
                if (window.multiFaceCounter > 2) {
                    if (window.multiFaceCounter % 10 === 3) {
                        updateTrust(-5, "Multiple faces detected");
                    }
                    if (badge) { badge.innerText = "⛔ Multi-Face"; badge.className = "badge badge-red"; }
                } else {
                    if (badge) { badge.innerText = "⚠ Warning"; badge.className = "badge badge-amber"; }
                }

                // Draw red boxes for all faces
                detections.forEach(det => {
                    const { x, y, width, height } = det.detection.box;
                    ctx.strokeStyle = '#ef4444';
                    ctx.lineWidth = 2;
                    ctx.shadowColor = '#ef4444';
                    ctx.shadowBlur = 8;
                    ctx.strokeRect(x * scaleX, y * scaleY, width * scaleX, height * scaleY);
                    ctx.shadowBlur = 0;
                });

                if (emotionEl) emotionEl.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Multiple faces!';
            } else {
                // --- SINGLE FACE (GOOD) ---
                noFaceCounter = 0;
                window.multiFaceCounter = 0;

                if (badge) { badge.innerText = "Active"; badge.className = "badge badge-green"; }
                if (trustScore < 100) updateTrust(0.01, null, false);

                const det = detections[0];
                const { x, y, width, height } = det.detection.box;

                // Draw green bounding box with glow
                ctx.strokeStyle = '#10b981';
                ctx.lineWidth = 2;
                ctx.shadowColor = '#10b981';
                ctx.shadowBlur = 10;
                ctx.strokeRect(x * scaleX, y * scaleY, width * scaleX, height * scaleY);
                ctx.shadowBlur = 0;

                // Draw corner brackets for premium look
                const cornerLen = 12;
                const cx = x * scaleX, cy = y * scaleY, cw = width * scaleX, ch = height * scaleY;
                ctx.strokeStyle = '#34d399';
                ctx.lineWidth = 3;
                // Top-left
                ctx.beginPath(); ctx.moveTo(cx, cy + cornerLen); ctx.lineTo(cx, cy); ctx.lineTo(cx + cornerLen, cy); ctx.stroke();
                // Top-right
                ctx.beginPath(); ctx.moveTo(cx + cw - cornerLen, cy); ctx.lineTo(cx + cw, cy); ctx.lineTo(cx + cw, cy + cornerLen); ctx.stroke();
                // Bottom-left
                ctx.beginPath(); ctx.moveTo(cx, cy + ch - cornerLen); ctx.lineTo(cx, cy + ch); ctx.lineTo(cx + cornerLen, cy + ch); ctx.stroke();
                // Bottom-right
                ctx.beginPath(); ctx.moveTo(cx + cw - cornerLen, cy + ch); ctx.lineTo(cx + cw, cy + ch); ctx.lineTo(cx + cw, cy + ch - cornerLen); ctx.stroke();

                // Get dominant emotion
                const expressions = det.expressions;
                const sorted = Object.entries(expressions).sort((a, b) => b[1] - a[1]);
                const [emotion, confidence] = sorted[0];
                const icon = EMOTION_ICONS[emotion] || '🤔';
                const pct = Math.round(confidence * 100);

                if (emotionEl) {
                    XSS.safeSetHTML(emotionEl, `${icon} ${emotion.charAt(0).toUpperCase() + emotion.slice(1)} <span style="opacity:0.6">${pct}%</span>`);
                }

                // Draw emotion label above face box
                const label = `${icon} ${emotion} ${pct}%`;
                ctx.fillStyle = 'rgba(15, 23, 42, 0.75)';
                const textWidth = ctx.measureText(label).width + 14;
                ctx.fillRect(cx, cy - 22, textWidth, 20);
                ctx.fillStyle = '#a5b4fc';
                ctx.font = 'bold 11px Outfit, sans-serif';
                ctx.fillText(label, cx + 6, cy - 7);
            }
        } catch (e) {
            console.warn("Detection cycle error:", e);
        }
    }, 800);
}


async function updateTrust(delta, reason, shouldSync = true) {
    trustScore = Math.max(0, Math.min(100, trustScore + delta));

    const trustValEl = document.getElementById('trust-value');
    const trustBarEl = document.getElementById('trust-bar');

    if (trustValEl) trustValEl.innerText = `${Math.round(trustScore)}%`;
    if (trustBarEl) {
        trustBarEl.style.width = `${trustScore}%`;
        // Update coloring via inline style or classes if defined
        if (trustScore < 30) trustBarEl.style.background = 'var(--red)';
        else if (trustScore < 70) trustBarEl.style.background = 'var(--amber)';
        else trustBarEl.style.background = 'linear-gradient(to right, var(--green), #34d399)';
    }

    if (shouldSync && delta < 0 && reason) {
        // Phase 20: Hiding security penalties from live feedback UI to avoid stressing candidate.
        // addFeedbackItem(delta, `Security Penalty: ${reason}`, questionCount);
        syncViolation(reason);
    }

    if (trustScore < 20) {
        handleCheatAttempt("Critical security failure: Persistent violations");
    }
}

async function syncViolation(type) {
    if (!applicationId) return;

    // Bug #20: Debounce identical violations
    const now = Date.now();
    if (lastViolationTime[type] && (now - lastViolationTime[type]) < VIOLATION_DEBOUNCE_MS) {
        console.debug(`[VIOLATION] Throttled: ${type}`);
        return;
    }
    lastViolationTime[type] = now;

    try {
        let syncUrl = '/ai/interview/sync-proctoring';
        if (applicationId) {
            syncUrl += `?application_id=${applicationId}`;
            if (urlInterviewToken) syncUrl += `&token=${urlInterviewToken}`;
        }
        const data = await window.fetchAPI(syncUrl, {
            method: 'POST',
            body: JSON.stringify({
                application_id: applicationId,
                violation_type: type,
                timestamp: new Date().toISOString(),
                details: `Trust score dropped to ${trustScore}%`
            })
        });

        // Server-side trust overrides client-side (anti-tampering)
        if (data && typeof data.server_trust_score === 'number') {
            trustScore = data.server_trust_score;
            const trustValEl = document.getElementById('trust-value');
            const trustBarEl = document.getElementById('trust-bar');
            if (trustValEl) trustValEl.innerText = `${Math.round(trustScore)}%`;
            if (trustBarEl) {
                trustBarEl.style.width = `${trustScore}%`;
                // Re-apply colors based on server trust
                if (trustScore < 30) trustBarEl.style.background = 'var(--red)';
                else if (trustScore < 70) trustBarEl.style.background = 'var(--amber)';
                else trustBarEl.style.background = 'linear-gradient(to right, var(--green), #34d399)';
            }
        }
    } catch (e) {
        console.error("Failed to sync proctoring violation:", e);
    }
}

// --- PRIVACY MODE FUNCTIONS REMOVED ---
function toggleTrustMode() {
    console.warn("Privacy Toggle requested but feature is removed.");
    Toast.show("Standard monitoring active", "info");
}

// --- GUEST FINALIZATION LOGIC ---
document.getElementById('finalize-guest-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = e.target.querySelector('button');
    const password = document.getElementById('guest-password').value;
    const email = localStorage.getItem('guestEmail');

    if (!email) {
        Toast.show("Error: Guest email missing. Please contact support.", "error");
        return;
    }

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Finalizing...';

    try {
        const resp = await fetch(`${CONFIG.API_BASE_URL}/auth/signup`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email: email,
                password: password,
                role: 'candidate',
                name: localStorage.getItem('userName') || "Candidate"
            })
        });

        if (resp.ok) {
            const data = await resp.json();
            // Auth via httponly cookie (set by backend) — no JWT in localStorage
            localStorage.setItem('role', data.role || 'candidate');
            localStorage.setItem('userName', data.name || localStorage.getItem('userName') || "Candidate");
            localStorage.removeItem('is_guest');
            localStorage.removeItem('guestEmail');

            Toast.show("Account secured! Redirecting to your coach...", "success");
            setTimeout(() => {
                window.location.href = `/applications?open_report=${applicationId}`;
            }, 1500);
        } else {
            const errData = await resp.json();
            Toast.show(`Failed: ${errData.detail || 'Could not finalize account'}`, "error");
            btn.disabled = false;
            btn.innerText = 'Create Account & Proceed';
        }
    } catch (err) {
        console.error("Finalization Error:", err);
        Toast.show("Network error during account finalization", "error");
        btn.disabled = false;
        btn.innerText = 'Create Account & Proceed';
    }
});
