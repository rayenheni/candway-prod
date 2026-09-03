// skill-tree-modal.js – handles the multi‑step creation modal for recruiters
// ---------------------------------------------------------------
// This script provides the UI logic for the "Create Skill Tree" workflow
// described in the redesigned skill‑tree page.
// It does NOT contain any server‑side business logic – all data is fetched
// from the existing REST endpoints.

(() => {
  const modal = document.getElementById('skill-tree-modal');
  const stepContainer = document.getElementById('modal-step-container');
  const prevBtn = document.getElementById('prev-step-btn');
  const nextBtn = document.getElementById('next-step-btn');

  if (!modal || !stepContainer || !prevBtn || !nextBtn) return;

  // State shared across steps
  const state = {
    jobId: null,
    selectedCategories: [],
    jobTitle: '',
    jobDescription: '',
    templateId: null,
    rubric: null, // full rubric JSON (categories, skills, etc.)
  };

  // Helper – load HTML for each step (lazy‑loaded to keep the file small)
  const stepTemplates = {
    1: `
      <h3 class="text-lg font-bold mb-3">Select a Job</h3>
      <select id="modal-job" class="w-full border rounded p-2">
        <option value="">Loading jobs…</option>
      </select>`,
    2: `
      <h3 class="text-lg font-bold mb-3">Select Categories</h3>
      <div id="category-grid" class="grid grid-cols-2 gap-2"></div>`,
    3: `
      <h3 class="text-lg font-bold mb-3">Job Details</h3>
      <label class="block mb-2">Job Title</label>
      <input id="job-title" type="text" class="w-full border rounded p-2 mb-4"/>
      <label class="block mb-2">Job Description</label>
      <textarea id="job-desc" rows="4" class="w-full border rounded p-2"></textarea>`,
    4: `
      <h3 class="text-lg font-bold mb-3">Choose a Template</h3>
      <button id="browse-templates" class="px-4 py-2 bg-indigo-600 text-white rounded mr-2">Browse Templates</button>
      <button id="generate-ai" class="px-4 py-2 bg-emerald-600 text-white rounded">Generate with AI</button>
      <div id="templates-list" class="mt-4 grid grid-cols-1 md:grid-cols-2 gap-2"></div>`,
    5: `
      <h3 class="text-lg font-bold mb-3">Customize Rubric</h3>
      <div id="rubric-editor" class="overflow-auto max-h-96 border rounded p-2"></div>`,
    6: `
      <h3 class="text-lg font-bold mb-3">Publish Skill Tree</h3>
      <p class="mb-4">Review your rubric below and click Publish.</p>
      <pre id="final-rubric" class="bg-gray-100 p-2 rounded overflow-auto"></pre>`,
  };

  let currentStep = 1;
  const totalSteps = Object.keys(stepTemplates).length;

  function renderStep() {
    stepContainer.innerHTML = stepTemplates[currentStep];
    prevBtn.disabled = currentStep === 1;
    nextBtn.textContent = currentStep === totalSteps ? 'Finish' : 'Next';
    // Populate step‑specific data
    switch (currentStep) {
      case 1:
        loadJobs();
        break;
      case 2:
        loadCategories();
        break;
      case 3:
        // pre‑fill if we already have data (e.g., coming back)
        document.getElementById('job-title').value = state.jobTitle;
        document.getElementById('job-desc').value = state.jobDescription;
        break;
      case 4:
        document.getElementById('browse-templates').onclick = browseTemplates;
        document.getElementById('generate-ai').onclick = generateWithAI;
        break;
      case 5:
        renderRubricEditor();
        break;
      case 6:
        document.getElementById('final-rubric').textContent = JSON.stringify(state.rubric, null, 2);
        break;
    }
  }

  // ---------- Step 1 – Jobs ----------
  async function loadJobs() {
    const select = document.getElementById('modal-job');
    try {
      const res = await fetch('/api/v1/recruiter/jobs/my');
      if (!res.ok) throw new Error('Failed to fetch')
      const data = await res.json();
      select.innerHTML = '<option value="">Select job…</option>';
      data.jobs.forEach(j => {
        const opt = document.createElement('option');
        opt.value = j.id;
        opt.textContent = `${j.title} – ${j.company}`;
        select.appendChild(opt);
      });
      select.onchange = () => {
        state.jobId = select.value;
        // grab title & description for later steps (optional)
        const chosen = data.jobs.find(j => j.id == state.jobId);
        if (chosen) {
          state.jobTitle = chosen.title;
          state.jobDescription = chosen.description || '';
        }
      };
    } catch (e) {
      select.innerHTML = '<option value="">Error loading jobs</option>';
    }
  }

  // ---------- Step 2 – Categories ----------
  async function loadCategories() {
    const container = document.getElementById('category-grid');
    container.innerHTML = 'Loading categories…';
    try {
      const res = await fetch('/api/v1/categories/job');
      const data = await res.json();
      container.innerHTML = '';
      data.categories.forEach(cat => {
        const btn = document.createElement('button');
        btn.className = 'p-2 border rounded hover:bg-indigo-50';
        btn.textContent = cat.name;
        btn.onclick = () => {
          const idx = state.selectedCategories.indexOf(cat.id);
          if (idx > -1) {
            state.selectedCategories.splice(idx, 1);
            btn.classList.remove('bg-indigo-200');
          } else {
            state.selectedCategories.push(cat.id);
            btn.classList.add('bg-indigo-200');
          }
        };
        container.appendChild(btn);
      });
    } catch (e) {
      container.textContent = 'Error loading categories';
    }
  }

  // ---------- Step 4 – Templates ----------
  async function browseTemplates() {
    const list = document.getElementById('templates-list');
    list.innerHTML = 'Loading templates…';
    try {
      const res = await fetch('/api/v1/rubric/templates');
      const data = await res.json();
      list.innerHTML = '';
      data.templates.forEach(tpl => {
        const card = document.createElement('div');
        card.className = 'p-3 border rounded cursor-pointer hover:bg-gray-50';
        card.textContent = tpl.title;
        card.onclick = () => {
          state.templateId = tpl.id;
          // fetch full rubric for editing later
          fetch(`/api/v1/rubric/template-detail/${tpl.id}`).then(r => r.json()).then(d => {
            state.rubric = d.rubric; // assume {rubric: {...}}
          });
          // highlight selection
          Array.from(list.children).forEach(c => c.classList.remove('bg-indigo-100'));
          card.classList.add('bg-indigo-100');
        };
        list.appendChild(card);
      });
    } catch (e) {
      list.textContent = 'Error loading templates';
    }
  }

  async function generateWithAI() {
    if (!state.jobDescription) {
      alert('Provide a job description first (Step 3)');
      return;
    }
    const loading = document.createElement('div');
    loading.textContent = 'Generating…';
    const list = document.getElementById('templates-list');
    list.innerHTML = '';
    list.appendChild(loading);
    try {
      const res = await fetch('/api/v1/rubric/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ description: state.jobDescription, job_id: state.jobId })
      });
      const data = await res.json();
      state.rubric = data.rubric; // assume the endpoint returns {rubric: {...}}
      state.templateId = null;
      list.innerHTML = '<div class="text-green-600">AI rubric generated – proceed to Customize.</div>';
    } catch (e) {
      list.textContent = 'AI generation failed';
    }
  }

  // ---------- Step 5 – Rubric editor (very simple UI) ----------
  function renderRubricEditor() {
    const container = document.getElementById('rubric-editor');
    if (!state.rubric) {
      container.textContent = 'No rubric loaded. Choose a template or generate with AI.';
      return;
    }
    // Render categories & skills as simple lists with add/remove buttons for skills only
    container.innerHTML = '';
    Object.entries(state.rubric.categories || {}).forEach(([catId, cat]) => {
      const catDiv = document.createElement('div');
      catDiv.className = 'mb-3 p-2 border-b';
      const title = document.createElement('h4');
      title.textContent = cat.name;
      catDiv.appendChild(title);
      const skillList = document.createElement('ul');
      skillList.className = 'list-disc pl-5';
      (cat.skills || []).forEach((skill, idx) => {
        const li = document.createElement('li');
        li.textContent = skill.name;
        const rm = document.createElement('button');
        rm.className = 'ml-2 text-red-500';
        rm.textContent = '✕';
        rm.onclick = () => {
          cat.skills.splice(idx, 1);
          renderRubricEditor();
        };
        li.appendChild(rm);
        skillList.appendChild(li);
      });
      // add new skill input
      const addInput = document.createElement('input');
      addInput.type = 'text';
      addInput.placeholder = 'New skill name';
      addInput.className = 'border rounded p-1 mr-2';
      const addBtn = document.createElement('button');
      addBtn.textContent = 'Add Skill';
      addBtn.className = 'bg-indigo-600 text-white px-2 py-1 rounded';
      addBtn.onclick = () => {
        const name = addInput.value.trim();
        if (!name) return;
        cat.skills = cat.skills || [];
        cat.skills.push({ name });
        addInput.value = '';
        renderRubricEditor();
      };
      catDiv.appendChild(skillList);
      catDiv.appendChild(addInput);
      catDiv.appendChild(addBtn);
      container.appendChild(catDiv);
    });
  }

  // ---------- Navigation ----------
  prevBtn.onclick = () => {
    if (currentStep > 1) {
      currentStep--;
      renderStep();
    }
  };

  nextBtn.onclick = async () => {
    // Validation before moving forward
    if (currentStep === 1 && !state.jobId) { alert('Select a job first'); return; }
    if (currentStep === 2 && state.selectedCategories.length === 0) { alert('Pick at least one category'); return; }
    if (currentStep === 3) {
      state.jobTitle = document.getElementById('job-title').value.trim();
      state.jobDescription = document.getElementById('job-desc').value.trim();
      if (!state.jobTitle) { alert('Job title required'); return; }
    }
    if (currentStep === 4 && !state.rubric) { alert('Select a template or generate a rubric'); return; }
    if (currentStep === 5) {
      // nothing extra – rubric already edited in place
    }
    if (currentStep === totalSteps) {
      // Final publish step
      try {
        const payload = {
          job_id: Number(state.jobId),
          title: state.jobTitle,
          description: state.jobDescription,
          categories: state.selectedCategories,
          rubric: state.rubric,
        };
        const res = await fetch('/api/v1/recruiter/skill-trees', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        if (!res.ok) throw new Error('Publish failed');
        const result = await res.json();
        alert('Skill tree published!');
        // close modal & refresh table
        close();
        if (window.loadSkillTrees) window.loadSkillTrees();
      } catch (e) {
        alert(e.message);
      }
      return;
    }
    currentStep++;
    renderStep();
  };

  // ---------- Open / Close ----------
  window.SkillTreeModal = {
    open() {
      modal.classList.remove('hidden');
      currentStep = 1;
      renderStep();
    },
    close() {
      modal.classList.add('hidden');
    },
    edit(id) {
      // For brevity, edit functionality re‑uses the create flow – you could fetch the existing tree and populate state here.
      this.open();
    },
    delete(id) {
      if (!confirm('Delete this skill tree?')) return;
      fetch(`/api/v1/recruiter/skill-trees/${id}`, { method: 'DELETE' })
        .then(r => r.ok ? window.loadSkillTrees() : alert('Delete failed'));
    },
  };

  // Close button inside modal (if exists)
  const closeBtn = document.getElementById('ste-modal-close');
  if (closeBtn) closeBtn.onclick = () => modal.classList.add('hidden');
})();
