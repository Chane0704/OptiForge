/**
 * OptiForge Desktop App — Client Application Supervisor
 * Warm Editorial Front-End Interaction Engine
 */

let appState = {
  currentScreen: 'home',
  currentTargetPath: '',         // Full resolved absolute path or URL
  currentTargetDisplayName: '',  // Short human-readable display label
  analysisResult: null,
  promptMode: 'fix_safe',
  promptDetail: 'detailed',
  activeFindingId: null,
  latestProposals: [],
  latestSnapshotId: null,
  theme: 'light'
};

const RECENT_PROJECTS_KEY = 'optiforge_recent_projects';
const LAST_RESULT_KEY = 'optiforge_last_result';

/* ==========================================================================
   Initialization & Lifecycle Supervisor
   ========================================================================== */
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  setupDragAndDrop();
  setupKeyboardShortcuts();
  renderRecentProjects();

  // Handle URL query parameters (e.g. launched via CLI: OptiForgeApp.exe <folder>)
  const params = new URLSearchParams(window.location.search);
  const targetParam = params.get('target');
  const isNew = params.get('new') === '1';

  if (targetParam) {
    // Auto-start analysis for folder passed on command line or context menu
    startAnalysis(decodeURIComponent(targetParam));
  } else if (!isNew) {
    // Check if we have a persisted previous analysis result
    restoreLastResult();
  }
});

function initTheme() {
  const saved = localStorage.getItem('optiforge-theme');
  if (saved) {
    appState.theme = saved;
  } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    appState.theme = 'dark';
  } else {
    appState.theme = 'light';
  }
  applyTheme(appState.theme);
}

function applyTheme(theme) {
  appState.theme = theme;
  document.body.classList.toggle('dark', theme === 'dark');
  localStorage.setItem('optiforge-theme', theme);

  const themeIcon = document.getElementById('theme-icon');
  const themeText = document.getElementById('theme-text');
  if (themeIcon && themeText) {
    if (theme === 'dark') {
      themeIcon.innerHTML = '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>';
      themeText.textContent = 'Dark';
    } else {
      themeIcon.innerHTML = '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>';
      themeText.textContent = 'Light';
    }
  }
}

function toggleAppTheme() {
  applyTheme(appState.theme === 'dark' ? 'light' : 'dark');
}

function setAppTheme(theme) {
  applyTheme(theme);
}

/* ==========================================================================
   Screen Transitions & State Restoration
   ========================================================================== */
function showHomeScreen(userInitiated = false) {
  appState.currentScreen = 'home';
  document.getElementById('screen-home').style.display = 'flex';
  document.getElementById('screen-analyzing').style.display = 'none';
  document.getElementById('screen-results').style.display = 'none';
  renderRecentProjects();
  if (userInitiated) {
    // When user explicitly clicks "Analyze another project", clear last result cache
    localStorage.removeItem(LAST_RESULT_KEY);
  }
}

function showAnalyzingScreen(targetName = '') {
  appState.currentScreen = 'analyzing';
  document.getElementById('screen-home').style.display = 'none';
  document.getElementById('screen-analyzing').style.display = 'flex';
  document.getElementById('screen-results').style.display = 'none';

  const statusText = document.getElementById('analyzing-status-text');
  if (statusText) {
    statusText.textContent = targetName ? `Auditing "${targetName}"...` : 'Inspecting dependencies, code structure, assets, and runtime performance.';
  }

  resetSteps();
  setTimeout(() => setStepActive(2), 400);
  setTimeout(() => setStepActive(3), 900);
  setTimeout(() => setStepActive(4), 1400);
}

function showResultsScreen() {
  appState.currentScreen = 'results';
  document.getElementById('screen-home').style.display = 'none';
  document.getElementById('screen-analyzing').style.display = 'none';
  document.getElementById('screen-results').style.display = 'block';
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function cancelAnalysis() {
  showHomeScreen();
  showToast('Analysis cancelled');
}

function resetSteps() {
  for (let i = 1; i <= 4; i++) {
    const el = document.getElementById(`step-${i}`);
    if (el) el.className = i === 1 ? 'step-item active' : 'step-item';
  }
}

function setStepActive(stepNum) {
  for (let i = 1; i < stepNum; i++) {
    const el = document.getElementById(`step-${i}`);
    if (el) el.className = 'step-item done';
  }
  const curr = document.getElementById(`step-${stepNum}`);
  if (curr) curr.className = 'step-item active';
}

function restoreLastResult() {
  try {
    const cached = localStorage.getItem(LAST_RESULT_KEY);
    if (cached) {
      const result = JSON.parse(cached);
      if (result && result.target_name) {
        appState.analysisResult = result;
        appState.currentTargetPath = result.target_path || '';
        renderResults(result);
        showResultsScreen();
      }
    }
  } catch (e) {
    console.warn('Could not restore last analysis:', e);
  }
}

/* ==========================================================================
   Native Windows Dialogs (Zero Chromium Upload Popups)
   ========================================================================== */
async function browseNative(dialogType) {
  const lastFolder = localStorage.getItem('optiforge_last_folder') || '';
  try {
    const resp = await fetch('/api/dialog/pick', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        dialog_type: dialogType,
        initial_dir: lastFolder
      })
    });
    const data = await resp.json();
    if (data.cancelled) return;

    const chosen = data.path || data.selected;
    const pickedPath = Array.isArray(chosen) ? chosen[0] : chosen;
    if (data.success && pickedPath) {
      // Save last directory for future pickers
      let dir = pickedPath;
      if (dialogType !== 'folder') {
        const lastSlash = Math.max(dir.lastIndexOf('\\'), dir.lastIndexOf('/'));
        if (lastSlash > 0) dir = dir.substring(0, lastSlash);
      }
      localStorage.setItem('optiforge_last_folder', dir);

      const displayName = pickedPath.split(/[\\/]/).filter(Boolean).pop() || pickedPath;
      startAnalysis(pickedPath, displayName);
    }
  } catch (err) {
    showToast(`Dialog error: ${err.message}`);
  }
}

function triggerFolderSelect() {
  browseNative('folder');
}

function triggerFileSelect() {
  browseNative('file');
}

function triggerImageSelect() {
  browseNative('image');
}

/* ==========================================================================
   Drag & Drop Handlers
   ========================================================================== */
function setupDragAndDrop() {
  const dropArea = document.getElementById('drop-area');
  if (!dropArea) return;

  ['dragenter', 'dragover'].forEach(eventName => {
    dropArea.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropArea.classList.add('drag-active');
    }, false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropArea.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropArea.classList.remove('drag-active');
    }, false);
  });

  dropArea.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    if (dt && dt.files && dt.files.length > 0) {
      const file = dt.files[0];
      // On desktop webview, file.path contains full local filesystem path when available
      const targetPath = file.path || file.name;
      const displayName = file.name || targetPath.split(/[\\/]/).filter(Boolean).pop() || 'Project';
      startAnalysis(targetPath, displayName);
    }
  }, false);
}

function startAnalysisFromInput() {
  const textInput = document.getElementById('target-input-text');
  let val = textInput ? textInput.value.trim() : '';
  if (!val) {
    showToast('Please enter a folder path, website URL, or code snippet.');
    return;
  }
  // Strip surrounding quotes (e.g. from Windows "Copy as path")
  val = val.replace(/^["']+|["']+$/g, '').trim();
  const displayName = val.split(/[\\/]/).filter(Boolean).pop() || val;
  startAnalysis(val, displayName);
}

function analyzeSampleProject() {
  startAnalysis('sample_bloated_project', 'sample_bloated_project');
}

/* ==========================================================================
   Recent Projects Manager (Local Persistence)
   ========================================================================== */
function getRecentProjects() {
  try {
    const raw = localStorage.getItem(RECENT_PROJECTS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    return [];
  }
}

function saveRecentProject(result) {
  if (!result || !result.target_path) return;
  let recents = getRecentProjects();
  // Filter out existing by path
  recents = recents.filter(r => r.path !== result.target_path);
  // Add newest to front
  recents.unshift({
    name: result.target_name || 'Project',
    path: result.target_path,
    score: Math.round(result.health_score || 0),
    tech_stack: result.tech_stack || 'General',
    analyzed_at: result.analyzed_at || new Date().toLocaleDateString()
  });
  // Cap at 8 recent projects
  recents = recents.slice(0, 8);
  localStorage.setItem(RECENT_PROJECTS_KEY, JSON.stringify(recents));
  renderRecentProjects();
}

function removeRecentProject(targetPath, event) {
  if (event) event.stopPropagation();
  let recents = getRecentProjects();
  recents = recents.filter(r => r.path !== targetPath);
  localStorage.setItem(RECENT_PROJECTS_KEY, JSON.stringify(recents));
  renderRecentProjects();
}

function clearRecentProjects() {
  localStorage.removeItem(RECENT_PROJECTS_KEY);
  renderRecentProjects();
  showToast('Recent projects history cleared.');
}

function renderRecentProjects() {
  const container = document.getElementById('recent-projects-container');
  const list = document.getElementById('recent-projects-list');
  if (!container || !list) return;

  const recents = getRecentProjects();
  if (recents.length === 0) {
    container.style.display = 'none';
    list.innerHTML = '';
    return;
  }

  container.style.display = 'block';
  list.innerHTML = '';

  recents.forEach(p => {
    const card = document.createElement('div');
    card.className = 'recent-project-card';
    card.onclick = () => startAnalysis(p.path, p.name);
    card.innerHTML = `
      <div class="recent-project-left">
        <div class="recent-project-name">${escapeHtml(p.name)}</div>
        <div class="recent-project-path">${escapeHtml(p.path)}</div>
      </div>
      <div class="recent-project-right">
        <span class="recent-score-pill">${p.score}/100</span>
        <button class="btn-ghost btn-sm" onclick="event.stopPropagation(); startAnalysis('${escapeHtml(p.path)}', '${escapeHtml(p.name)}')" title="Re-analyze this project">
          Re-analyze
        </button>
        <button class="btn-ghost btn-sm" style="color:var(--text-muted); padding:4px 6px;" onclick="removeRecentProject('${escapeHtml(p.path)}', event)" title="Remove from recent list">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="12" height="12"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>
    `;
    list.appendChild(card);
  });
}

/* ==========================================================================
   Core Analysis Execution & Target Override
   ========================================================================== */
async function startAnalysis(rawInput, displayName = '') {
  if (!rawInput) return;
  const shortName = displayName || rawInput.split(/[\\/]/).filter(Boolean).pop() || 'Project';
  appState.currentTargetPath = rawInput;
  appState.currentTargetDisplayName = shortName;

  showAnalyzingScreen(shortName);

  try {
    const response = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ raw_input: rawInput })
    });

    const data = await response.json();
    if (!data.success) {
      showHomeScreen();
      showToast(data.error || 'Analysis failed. Please verify the target path.');
      return;
    }

    appState.analysisResult = data.result;
    appState.currentTargetPath = data.result.target_path || rawInput;
    appState.currentTargetDisplayName = data.result.target_name || shortName;

    // Persist to localStorage
    saveRecentProject(data.result);
    try {
      localStorage.setItem(LAST_RESULT_KEY, JSON.stringify(data.result));
    } catch (e) {
      // quota or private mode
    }

    renderResults(data.result);
    showResultsScreen();
  } catch (err) {
    showHomeScreen();
    showToast(`Analysis request error: ${err.message}`);
  }
}

function reanalyzeCurrentTarget() {
  if (appState.currentTargetPath) {
    startAnalysis(appState.currentTargetPath, appState.currentTargetDisplayName);
  } else if (appState.analysisResult && appState.analysisResult.target_path) {
    startAnalysis(appState.analysisResult.target_path, appState.analysisResult.target_name);
  } else {
    showHomeScreen();
  }
}

async function overrideTarget(forcedKind) {
  if (!appState.currentTargetPath) return;
  showAnalyzingScreen(`Forcing target type: ${forcedKind}`);

  try {
    const resp = await fetch('/api/override-target', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        path: appState.currentTargetPath,
        kind: forcedKind
      })
    });
    const data = await resp.json();
    if (data.success && data.result) {
      appState.analysisResult = data.result;
      saveRecentProject(data.result);
      localStorage.setItem(LAST_RESULT_KEY, JSON.stringify(data.result));
      renderResults(data.result);
      showResultsScreen();
      showToast(`Target re-evaluated as ${forcedKind}.`);
    } else {
      showToast(`Could not override: ${data.error || 'Unknown error'}`);
      showResultsScreen();
    }
  } catch (err) {
    showToast(`Override error: ${err.message}`);
    showResultsScreen();
  }
}

/* ==========================================================================
   Results Rendering (Real Metrics, Measured vs Estimated, Verified Identity)
   ========================================================================== */
function renderResults(result) {
  // 1. Identity & Metadata
  document.getElementById('res-target-name').textContent = result.target_name || (result.detected_input ? result.detected_input.friendly_label : 'Project');
  
  const pathEl = document.getElementById('res-target-path');
  if (pathEl) {
    pathEl.textContent = result.target_path || 'Target';
  }

  const techEl = document.getElementById('res-tech-stack');
  if (techEl) {
    techEl.textContent = result.tech_stack || 'General';
  }

  const analyzedEl = document.getElementById('res-analyzed-at');
  if (analyzedEl) {
    analyzedEl.textContent = result.analyzed_at || 'Just now';
  }

  const itemsEl = document.getElementById('res-item-count');
  if (itemsEl) {
    itemsEl.textContent = `${result.item_count || 0} items`;
  }

  const sizeEl = document.getElementById('res-current-size');
  if (sizeEl) {
    sizeEl.textContent = `${result.target_size_mb || '0.00'} MB`;
  }

  const detectedTypeEl = document.getElementById('res-detected-type');
  if (detectedTypeEl) {
    const kind = result.detected_input ? result.detected_input.kind : 'codebase';
    detectedTypeEl.textContent = kind.charAt(0).toUpperCase() + kind.slice(1);
  }

  const totalFindings = (result.quick_wins ? result.quick_wins.length : 0) +
                        (result.worth_doing ? result.worth_doing.length : 0) +
                        (result.optional ? result.optional.length : 0);
  document.getElementById('res-findings-count').textContent = totalFindings;

  // 2. Health Score
  const score = Math.round(result.health_score || 0);
  document.getElementById('res-health-score').innerHTML = `${score}<span class="score-denom">/100</span>`;
  document.getElementById('res-health-ring').textContent = `${score}%`;

  // 3. Accounting Metrics (Properly Labeled Measured vs Estimated)
  document.getElementById('res-savings-mb').textContent = `${result.total_savings_mb} MB`;

  const speedEl = document.getElementById('res-speed-gain');
  const speedTag = document.getElementById('res-speed-tag');
  if (speedEl) {
    speedEl.textContent = result.estimated_speed_gain || 'Optimal';
  }
  if (speedTag) {
    if (result.speed_gain_source === 'measured') {
      speedTag.textContent = '[Measured]';
    } else if (result.speed_gain_source === 'varies') {
      speedTag.textContent = '[Varies]';
    } else {
      speedTag.textContent = '[Estimated]';
    }
  }

  const safeCount = result.safe_fixes_count !== undefined ? result.safe_fixes_count :
                    ((result.quick_wins ? result.quick_wins.filter(f => f.safety_badge === 'Safe').length : 0) +
                     (result.worth_doing ? result.worth_doing.filter(f => f.safety_badge === 'Safe').length : 0));
  document.getElementById('res-safe-fixes').textContent = `${safeCount} items`;
  document.getElementById('res-btn-fix-count').textContent = safeCount;

  const btnFix = document.getElementById('btn-fix-safe');
  if (btnFix) {
    btnFix.style.display = safeCount > 0 ? 'inline-flex' : 'none';
  }

  // 4. Render Grouped Findings or Friendly Empty State
  const container = document.getElementById('findings-container');
  container.innerHTML = '';

  if (totalFindings === 0) {
    container.innerHTML = `
      <div class="empty-findings-box">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75">
          <circle cx="12" cy="12" r="10"/>
          <polyline points="9 12 11 14 15 10"/>
        </svg>
        <h4 class="empty-findings-title">Clean Bill of Health</h4>
        <p class="empty-findings-desc">
          OptiForge scanned <strong>${result.item_count || 0} items</strong> across "${escapeHtml(result.target_name || 'Project')}". No memory leaks, dead libraries, redundant assets, or performance bottlenecks were detected. Everything is operating efficiently.
        </p>
      </div>
    `;
    return;
  }

  renderGroup(container, 'Quick wins (high gain, low effort)', result.quick_wins || [], 'safe');
  renderGroup(container, 'Worth doing (substantial impact)', result.worth_doing || [], 'warn');
  renderGroup(container, 'Optional optimizations', result.optional || [], 'info');
}

function renderGroup(container, groupTitle, items, dotClass) {
  if (!items || items.length === 0) return;

  const section = document.createElement('div');
  section.className = 'findings-group';

  section.innerHTML = `
    <div class="group-header">
      <span class="group-dot ${dotClass}"></span>
      <h3 class="group-title">${groupTitle}</h3>
      <span class="group-count">&bull; ${items.length} ${items.length === 1 ? 'item' : 'items'}</span>
    </div>
    <div class="group-cards-list"></div>
  `;

  const list = section.querySelector('.group-cards-list');
  items.forEach(finding => {
    const card = createFindingCard(finding);
    list.appendChild(card);
  });

  container.appendChild(section);
}

function createFindingCard(finding) {
  const card = document.createElement('div');
  card.className = 'finding-card';
  card.id = `card-${finding.id}`;

  let badgeClass = 'badge-safe';
  let badgeLabel = 'Safe to fix';
  if (finding.safety_badge === 'Probably safe') {
    badgeClass = 'badge-warn';
    badgeLabel = 'Probably safe';
  } else if (finding.safety_badge === 'Be careful') {
    badgeClass = 'badge-alert';
    badgeLabel = 'Be careful';
  }

  // Display exact file path and line number if available
  const filePathStr = finding.file_path 
    ? `${finding.file_path}${finding.line_number ? ':' + finding.line_number : ''}` 
    : 'Entire project';

  // Gain tag (Measured vs Estimated)
  const isGainMeasured = finding.gain_type === 'measured' || (finding.estimated_savings_bytes && finding.estimated_savings_bytes > 0);
  const gainTag = isGainMeasured ? '<span class="metric-tag">[Measured]</span>' : '<span class="metric-tag">[Estimated]</span>';

  card.innerHTML = `
    <div class="finding-card-top">
      <div class="finding-main-content">
        <div class="finding-title-row">
          <span class="badge ${badgeClass}">${badgeLabel}</span>
          <h4 class="finding-title">${escapeHtml(finding.plain_title)}</h4>
        </div>
        <p class="finding-desc">${escapeHtml(finding.why_it_matters)}</p>
        <div class="finding-metrics-row">
          <div class="finding-metric-item">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
            <span class="tabular font-medium text-main">${escapeHtml(finding.estimated_gain)}</span>
            ${gainTag}
          </div>
          <div class="finding-metric-item" title="${escapeHtml(filePathStr)}">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/></svg>
            <span style="font-family:var(--font-mono); font-size:11.5px; max-width:280px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${escapeHtml(filePathStr)}</span>
          </div>
        </div>
      </div>

      <div class="finding-card-actions">
        <button class="icon-btn btn-sm" onclick="openPromptModal('${finding.id}')" title="Copy prompt for an AI assistant to fix this issue">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="13" height="13"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>
          AI Prompt
        </button>
        <button class="btn-ghost btn-sm" onclick="toggleAdvanced('${finding.id}')" title="Toggle technical details">
          <svg id="chevron-${finding.id}" viewBox="0 0 24 24" fill="none" stroke="currentColor" width="14" height="14"><path d="m6 9 6 6 6-6"/></svg>
        </button>
      </div>
    </div>

    <div class="finding-advanced" id="advanced-${finding.id}">
      <div style="font-weight:600; color:var(--text-main); margin-bottom:4px;">Technical Diagnosis</div>
      <div>${escapeHtml(finding.what_to_do)}</div>
      <div class="tech-details-grid">
        <span class="tech-key">Target File:</span>
        <span class="tech-val font-mono" style="word-break:break-all;">${escapeHtml(filePathStr)}</span>
        <span class="tech-key">Category:</span>
        <span class="tech-val">${escapeHtml(finding.category || 'Efficiency')}</span>
        <span class="tech-key">Impact / Effort:</span>
        <span class="tech-val">${escapeHtml(finding.impact || 'High')} / ${escapeHtml(finding.effort || 'Low')}</span>
        <span class="tech-key">Identifier:</span>
        <span class="tech-val font-mono">${escapeHtml(finding.id)}</span>
      </div>
    </div>
  `;

  return card;
}

function toggleAdvanced(id) {
  const el = document.getElementById(`advanced-${id}`);
  const chevron = document.getElementById(`chevron-${id}`);
  if (el) {
    el.classList.toggle('open');
    if (chevron) {
      chevron.style.transform = el.classList.contains('open') ? 'rotate(180deg)' : 'rotate(0deg)';
      chevron.style.transition = 'transform 150ms ease';
    }
  }
}

/* ==========================================================================
   Health Score Formula Explanation Modal
   ========================================================================== */
function openFormulaModal() {
  const modal = document.getElementById('modal-formula');
  const details = document.getElementById('formula-breakdown-details');
  if (!modal) return;

  if (details && appState.analysisResult) {
    const r = appState.analysisResult;
    const formula = r.health_score_formula || 'Health Score = 100 - penalties (min floor 10)';
    details.innerHTML = `
      <div style="margin-top:8px;">
        <strong>Active Project Calculation:</strong>
        <div style="font-family:var(--font-mono); font-size:11.5px; margin-top:4px; padding:8px; background:var(--surface); border:1px solid var(--border); border-radius:4px;">
          ${escapeHtml(formula)}
        </div>
      </div>
    `;
  }
  modal.classList.add('open');
}

function closeFormulaModal() {
  const modal = document.getElementById('modal-formula');
  if (modal) modal.classList.remove('open');
}

/* ==========================================================================
   AI Prompt Hand-Off Modal Logic
   ========================================================================== */
function openPromptModal(findingId = null) {
  appState.activeFindingId = findingId;
  const modal = document.getElementById('modal-prompt');
  if (modal) modal.classList.add('open');
  loadPrompt();
}

function closePromptModal() {
  const modal = document.getElementById('modal-prompt');
  if (modal) modal.classList.remove('open');
}

function setPromptMode(mode) {
  appState.promptMode = mode;
  ['fix_safe', 'fix_all', 'explain'].forEach(m => {
    const btn = document.getElementById(`mode-tab-${m}`);
    if (btn) btn.classList.toggle('active', m === mode);
  });
  loadPrompt();
}

function setPromptDetail(detail) {
  appState.promptDetail = detail;
  const btnDetailed = document.getElementById('btn-detail-detailed');
  const btnConcise = document.getElementById('btn-detail-concise');
  if (btnDetailed && btnConcise) {
    btnDetailed.style.fontWeight = detail === 'detailed' ? '600' : '400';
    btnConcise.style.fontWeight = detail === 'concise' ? '600' : '400';
  }
  loadPrompt();
}

async function loadPrompt() {
  const textarea = document.getElementById('prompt-output');
  if (!textarea) return;

  textarea.value = 'Preparing ready-to-paste AI agent prompt...';

  try {
    const response = await fetch('/api/generate-prompt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        mode: appState.promptMode,
        detail_level: appState.promptDetail,
        finding_id: appState.activeFindingId
      })
    });

    const data = await response.json();
    if (data.success) {
      textarea.value = data.prompt_text;

      const notice = document.getElementById('redaction-notice');
      if (notice) {
        if (data.secrets_redacted_count > 0) {
          notice.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="15" height="15"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><circle cx="12" cy="11" r="2"/></svg>
            <span><strong>${data.secrets_redacted_count} secret(s) automatically redacted</strong> from prompt to protect your security.</span>
          `;
        } else {
          notice.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="15" height="15"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><circle cx="12" cy="11" r="2"/></svg>
            <span>Redacted by default: Passwords, API keys, and environment secrets are safely excluded.</span>
          `;
        }
      }
    } else {
      textarea.value = `Unable to generate prompt: ${data.error}`;
    }
  } catch (err) {
    textarea.value = `Error generating prompt: ${err.message}`;
  }
}

function copyPromptToClipboard() {
  const textarea = document.getElementById('prompt-output');
  if (!textarea) return;

  navigator.clipboard.writeText(textarea.value).then(() => {
    showToast('Prompt copied to clipboard! Paste it into your AI assistant.');
  }).catch(() => {
    textarea.select();
    document.execCommand('copy');
    showToast('Prompt copied to clipboard!');
  });
}

function savePromptAsMarkdown() {
  const textarea = document.getElementById('prompt-output');
  if (!textarea || !textarea.value) return;

  const blob = new Blob([textarea.value], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `optiforge_prompt_${appState.promptMode}.md`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  showToast('Saved prompt as .md file');
}

/* ==========================================================================
   Fix Preview, Apply & Rollback Modal Logic
   ========================================================================== */
async function openFixPreviewModal() {
  const modal = document.getElementById('modal-fix-preview');
  const list = document.getElementById('fix-preview-list');
  const footer = document.getElementById('fix-modal-footer');
  if (!modal || !list) return;

  list.innerHTML = '<div style="padding:20px; text-align:center;">Loading proposed fixes...</div>';
  modal.classList.add('open');

  try {
    const response = await fetch('/api/fix/preview');
    const data = await response.json();
    if (data.success && data.proposals) {
      appState.latestProposals = data.proposals;

      if (data.proposals.length === 0) {
        list.innerHTML = '<div style="padding:16px; text-align:center; color:var(--text-muted);">No fixes available for the active target.</div>';
        if (footer) footer.style.display = 'none';
        return;
      }

      let html = `
        <div style="font-size:12.5px; margin-bottom:12px; color:var(--text-main);">
          <strong>${data.count} safe optimizations</strong> prepared. Estimated space reclamation: <strong>${data.total_savings_mb} MB</strong>.
        </div>
        <div style="display:flex; flex-direction:column; gap:8px; max-height:260px; overflow-y:auto;">
      `;

      data.proposals.forEach((p) => {
        const mb = (p.estimated_savings_bytes / (1024 * 1024)).toFixed(2);
        html += `
          <div style="background-color:var(--surface-subtle); border:1px solid var(--border); border-radius:var(--radius-control); padding:10px 14px; display:flex; justify-content:space-between; align-items:center;">
            <div>
              <div style="font-weight:600; font-size:12.5px; color:var(--text-main);">${escapeHtml(p.description)}</div>
              <div style="font-size:11.5px; color:var(--text-muted); font-family:var(--font-mono);">${escapeHtml(p.target_path)}</div>
            </div>
            <div style="font-size:12px; font-weight:600; color:var(--badge-safe-text); text-align:right;">
              +${mb > 0.01 ? mb + ' MB' : (p.estimated_savings_bytes / 1024).toFixed(1) + ' KB'}
            </div>
          </div>
        `;
      });

      html += '</div>';
      list.innerHTML = html;
      if (footer) {
        footer.style.display = 'flex';
        footer.innerHTML = `
          <button class="btn-ghost" onclick="closeFixPreviewModal()">Cancel</button>
          <button class="btn-primary" onclick="applySafeFixes()">Apply Safe Fixes</button>
        `;
      }
    }
  } catch (err) {
    list.innerHTML = `<div style="color:var(--badge-alert-text);">Error loading preview: ${err.message}</div>`;
  }
}

function closeFixPreviewModal() {
  const modal = document.getElementById('modal-fix-preview');
  if (modal) modal.classList.remove('open');
}

async function applySafeFixes() {
  const list = document.getElementById('fix-preview-list');
  const footer = document.getElementById('fix-modal-footer');
  if (list) list.innerHTML = '<div style="padding:24px; text-align:center;">Applying safe optimizations & creating atomic backup snapshot...</div>';
  if (footer) footer.style.display = 'none';

  try {
    const response = await fetch('/api/fix/apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: 'safe_only' })
    });

    const data = await response.json();
    if (data.success) {
      appState.latestSnapshotId = data.snapshot_id;
      const savedMb = (data.saved_bytes / (1024 * 1024)).toFixed(2);

      list.innerHTML = `
        <div style="text-align:center; padding:16px 8px;">
          <div style="width:40px; height:40px; border-radius:50%; background-color:var(--badge-safe-bg); color:var(--badge-safe-text); display:flex; align-items:center; justify-content:center; margin:0 auto 12px auto;">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="22" height="22" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
          </div>
          <h4 style="font-family:var(--font-display); font-size:20px; font-weight:500; color:var(--text-main); margin-bottom:4px;">
            Optimizations Applied Successfully
          </h4>
          <p style="font-size:13px; color:var(--text-muted); margin-bottom:14px;">
            Saved <strong>${savedMb} MB</strong>. ${data.modified_count} files modified, ${data.quarantined_count} files moved to quarantine.
          </p>
          <div style="font-size:11.5px; color:var(--text-subtle); font-family:var(--font-mono);">
            Snapshot: ${data.snapshot_id}
          </div>
        </div>
      `;

      if (footer) {
        footer.style.display = 'flex';
        footer.innerHTML = `
          <button class="btn-secondary" onclick="rollbackAppliedFixes('${data.snapshot_id}')">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="14" height="14"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>
            Undo All Changes (Rollback)
          </button>
          <button class="btn-primary" onclick="closeFixPreviewModal(); reanalyzeCurrentTarget();">
            Refresh Report
          </button>
        `;
      }
      showToast('Optimizations applied successfully!');
    } else {
      list.innerHTML = `<div style="color:var(--badge-alert-text); padding:16px;">Error applying fixes: ${data.error}</div>`;
      if (footer) {
        footer.style.display = 'flex';
        footer.innerHTML = '<button class="btn-ghost" onclick="closeFixPreviewModal()">Close</button>';
      }
    }
  } catch (err) {
    list.innerHTML = `<div style="color:var(--badge-alert-text); padding:16px;">Failed: ${err.message}</div>`;
  }
}

async function rollbackAppliedFixes(snapshotId) {
  const list = document.getElementById('fix-preview-list');
  const footer = document.getElementById('fix-modal-footer');
  if (list) list.innerHTML = '<div style="padding:24px; text-align:center;">Restoring files bit-for-bit from quarantine...</div>';
  if (footer) footer.style.display = 'none';

  try {
    const response = await fetch('/api/rollback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ snapshot_id: snapshotId })
    });

    const data = await response.json();
    if (data.success) {
      list.innerHTML = `
        <div style="text-align:center; padding:16px 8px;">
          <div style="width:40px; height:40px; border-radius:50%; background-color:var(--surface-subtle); color:var(--text-main); display:flex; align-items:center; justify-content:center; margin:0 auto 12px auto;">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="20" height="20" stroke-width="2"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg>
          </div>
          <h4 style="font-family:var(--font-display); font-size:18px; font-weight:500; color:var(--text-main); margin-bottom:4px;">
            Rollback Complete
          </h4>
          <p style="font-size:12.5px; color:var(--text-muted);">
            All files restored bit-for-bit to their exact pre-fix state with verified SHA-256 integrity.
          </p>
        </div>
      `;

      if (footer) {
        footer.style.display = 'flex';
        footer.innerHTML = '<button class="btn-primary" onclick="closeFixPreviewModal()">Done</button>';
      }
      showToast('Rollback completed. Original state restored.');
    } else {
      list.innerHTML = `<div style="color:var(--badge-alert-text); padding:16px;">Rollback error: ${data.error}</div>`;
    }
  } catch (err) {
    list.innerHTML = `<div style="color:var(--badge-alert-text); padding:16px;">Failed: ${err.message}</div>`;
  }
}

/* ==========================================================================
   Settings, Walkthrough & Utility Modals
   ========================================================================== */
function openSettingsModal() {
  const modal = document.getElementById('modal-settings');
  if (modal) modal.classList.add('open');
}

function closeSettingsModal() {
  const modal = document.getElementById('modal-settings');
  if (modal) modal.classList.remove('open');
}

function openWalkthroughModal() {
  const modal = document.getElementById('modal-walkthrough');
  if (modal) modal.classList.add('open');
}

function closeWalkthroughModal() {
  const modal = document.getElementById('modal-walkthrough');
  if (modal) modal.classList.remove('open');
}

function closeAllModals(e) {
  if (e && e.target && e.target.classList.contains('modal-backdrop')) {
    e.target.classList.remove('open');
  }
}

function setupKeyboardShortcuts() {
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal-backdrop.open').forEach(m => m.classList.remove('open'));
    }
  });
}

function showToast(message) {
  const toast = document.getElementById('app-toast');
  const msgEl = document.getElementById('toast-message');
  if (!toast || !msgEl) return;

  msgEl.textContent = message;
  toast.classList.add('visible');
  setTimeout(() => {
    toast.classList.remove('visible');
  }, 3200);
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
