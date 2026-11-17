/**
 * OptiForge Desktop App — Client Application Supervisor
 * Warm Editorial Front-End Interaction Engine
 */

let appState = {
  currentScreen: 'home',
  analysisResult: null,
  promptMode: 'fix_safe',
  promptDetail: 'detailed',
  activeFindingId: null,
  latestProposals: [],
  latestSnapshotId: null,
  theme: 'light'
};

/* ==========================================================================
   Initialization & Theme Supervisor
   ========================================================================== */
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  setupDragAndDrop();
  setupKeyboardShortcuts();
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
   Screen Transitions
   ========================================================================== */
function showHomeScreen() {
  appState.currentScreen = 'home';
  document.getElementById('screen-home').style.display = 'flex';
  document.getElementById('screen-analyzing').style.display = 'none';
  document.getElementById('screen-results').style.display = 'none';
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

  // Simulate calm step progression
  resetSteps();
  setTimeout(() => setStepActive(2), 500);
  setTimeout(() => setStepActive(3), 1100);
  setTimeout(() => setStepActive(4), 1700);
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
    if (el) {
      el.className = i === 1 ? 'step-item active' : 'step-item';
    }
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

/* ==========================================================================
   Drag & Drop and Input Handlers
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
      // Pick first file/folder path if available or fallback to name
      const file = dt.files[0];
      const targetPath = file.path || file.name;
      startAnalysis(targetPath);
    }
  }, false);
}

function triggerFolderSelect() {
  const input = document.getElementById('file-input-folder');
  if (input) input.click();
}

function triggerFileSelect() {
  const input = document.getElementById('file-input-files');
  if (input) input.click();
}

function triggerImageSelect() {
  const input = document.getElementById('file-input-images');
  if (input) input.click();
}

function handleFileChosen(e) {
  if (e.target.files && e.target.files.length > 0) {
    const file = e.target.files[0];
    const path = file.path || file.name;
    startAnalysis(path);
  }
}

function startAnalysisFromInput() {
  const textInput = document.getElementById('target-input-text');
  const val = textInput ? textInput.value.trim() : '';
  if (!val) {
    showToast('Please enter a folder path, website URL, or code snippet.');
    return;
  }
  startAnalysis(val);
}

function analyzeSampleProject() {
  startAnalysis('sample_bloated_project');
}

/* ==========================================================================
   Core Analysis Execution
   ========================================================================== */
async function startAnalysis(rawInput) {
  showAnalyzingScreen(rawInput);

  try {
    const response = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ raw_input: rawInput })
    });

    const data = await response.json();
    if (!data.success) {
      showHomeScreen();
      showToast(data.error || 'Analysis failed. Please check the target path.');
      return;
    }

    appState.analysisResult = data.result;
    renderResults(data.result);
    showResultsScreen();
  } catch (err) {
    showHomeScreen();
    showToast(`Network or server error: ${err.message}`);
  }
}

/* ==========================================================================
   Results Rendering (Hero, Accounting, Grouped Cards)
   ========================================================================== */
function renderResults(result) {
  // 1. Headline & Metadata
  document.getElementById('res-summary-headline').textContent = result.one_line_summary;
  document.getElementById('res-target-name').textContent = result.detected_input ? result.detected_input.friendly_label : 'Target';
  
  const totalFindings = (result.quick_wins ? result.quick_wins.length : 0) +
                        (result.worth_doing ? result.worth_doing.length : 0) +
                        (result.optional ? result.optional.length : 0);
  document.getElementById('res-findings-count').textContent = totalFindings;

  // 2. Score
  const score = Math.round(result.health_score || 0);
  document.getElementById('res-health-score').innerHTML = `${score}<span class="score-denom">/100</span>`;
  document.getElementById('res-health-ring').textContent = `${score}%`;

  // 3. Accounting Metrics
  document.getElementById('res-savings-mb').textContent = `${result.total_savings_mb} MB`;
  document.getElementById('res-speed-gain').textContent = result.estimated_speed_gain || '~350 ms';

  const safeCount = (result.quick_wins ? result.quick_wins.filter(f => f.safety_badge === 'Safe').length : 0) +
                    (result.worth_doing ? result.worth_doing.filter(f => f.safety_badge === 'Safe').length : 0);
  document.getElementById('res-safe-fixes').textContent = `${safeCount} items`;
  document.getElementById('res-btn-fix-count').textContent = safeCount;

  // Hide or show fix button if safeCount is 0
  const btnFix = document.getElementById('btn-fix-safe');
  if (btnFix) {
    btnFix.style.display = safeCount > 0 ? 'inline-flex' : 'none';
  }

  // 4. Render Grouped Findings
  const container = document.getElementById('findings-container');
  container.innerHTML = '';

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
          </div>
          <div class="finding-metric-item">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/></svg>
            <span>${escapeHtml(finding.file_path || 'Entire project')}</span>
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
        <span class="tech-key">Category:</span>
        <span class="tech-val">${escapeHtml(finding.category || 'Efficiency')}</span>
        <span class="tech-key">Impact / Effort:</span>
        <span class="tech-val">${escapeHtml(finding.impact || 'High')} / ${escapeHtml(finding.effort || 'Low')}</span>
        <span class="tech-key">Identifier:</span>
        <span class="tech-val">${escapeHtml(finding.id)}</span>
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

      data.proposals.forEach((p, idx) => {
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
          <button class="btn-primary" onclick="closeFixPreviewModal(); startAnalysis('${appState.analysisResult ? appState.analysisResult.detected_input.friendly_label : ''}');">
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
