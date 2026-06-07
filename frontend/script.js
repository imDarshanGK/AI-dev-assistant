/** Use security-utils.js when present (production index.html loads it first). */
const SEC = window.QyverixSecurity || {
  escHtml(s) {
    return String(s ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  },
  sanitizeClientCode(text) {
    return String(text).replace(/\x00/g, '').replace(/\x1b\[[0-9;]*[A-Za-z]/g, '');
  },
};
const { escHtml, sanitizeClientCode } = SEC;

const ALLOWED_MODES = new Set(['analyze', 'explanation', 'debugging', 'suggestions']);
function safeModeLabel(mode) {
  const key = String(mode || '').toLowerCase();
  return ALLOWED_MODES.has(key) ? key : 'analyze';
}

// ── State ──
let currentMode = 'analyze';
let isAnalyzing = false;
let history = JSON.parse(localStorage.getItem('qyverix_history') || '[]');
let favorites = JSON.parse(localStorage.getItem('qyverix_favorites') || '[]');
let lastResult = '';

// ── DOM refs ──
const codeInput = document.getElementById('codeInput');
const runBtn = document.getElementById('runBtn');
const runLabel = document.getElementById('runLabel');
const outputBox = document.getElementById('outputBox');
const apiUrlInput = document.getElementById('apiUrl');
const apiDocsLink = document.getElementById('apiDocsLink');
const engineBadge = document.getElementById('engineBadge');
const statusDot = document.getElementById('statusDot');
const lineCount = document.getElementById('lineCount');
const fileInput = document.getElementById('fileInput');
const historyContainer = document.getElementById('historyContainer');
const favContainer = document.getElementById('favContainer');
const themeToggle = document.getElementById('themeToggle');
const API_URL_STORAGE_KEY = 'qyverix_api_url';

const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
const savedTheme = localStorage.getItem('qyverix_theme') || (systemDark ? 'dark' : 'light');
document.documentElement.setAttribute('data-theme', savedTheme);

themeToggle.addEventListener('click', () => {
  const isLight = document.documentElement.getAttribute('data-theme') === 'light';
  document.documentElement.setAttribute('data-theme', isLight ? 'dark' : 'light');
  localStorage.setItem('qyverix_theme', isLight ? 'dark' : 'light');

  const themeToggleBtn = document.getElementById('themeToggle');
  if (themeToggleBtn) {
    themeToggleBtn.setAttribute('aria-label', isLight ? 'Toggle dark mode' : 'Toggle light mode');
    themeToggleBtn.setAttribute('aria-pressed', isLight ? 'false' : 'true');
  }
});

const initialTheme = document.documentElement.getAttribute('data-theme') || 'dark';
const themeToggleBtnInit = document.getElementById('themeToggle');
if (themeToggleBtnInit) {
  themeToggleBtnInit.setAttribute('aria-label', initialTheme === 'dark' ? 'Toggle light mode' : 'Toggle dark mode');
  themeToggleBtnInit.setAttribute('aria-pressed', initialTheme === 'dark' ? 'false' : 'true');
}

// ── Tabs ──
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => {
      t.classList.remove('active');
      t.setAttribute('aria-selected', 'false');
    });
    tab.classList.add('active');
    tab.setAttribute('aria-selected', 'true');
    currentMode = tab.dataset.mode;
  });
});

// ── Line count ──
codeInput.addEventListener('input', () => {
  const lines = codeInput.value.split('\n').length;
  lineCount.textContent = `${lines} line${lines !== 1 ? 's' : ''}`;
});

// ── Keyboard shortcut ──
codeInput.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    codeInput.blur();
    return;
  }
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault();
    if (isAnalyzing) {
        return;
    }
    runAnalysis();
  }
});

// ── File upload ──
document.getElementById('uploadBtn').addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (ev) => {
    codeInput.value = sanitizeClientCode(ev.target.result);
    codeInput.dispatchEvent(new Event('input'));
  };
  reader.readAsText(file);
});

// ── Clear ──
document.getElementById('clearBtn').addEventListener('click', () => {
  codeInput.value = '';
  lineCount.textContent = '0 lines';
  resetOutput();
});

// ── Copy ──
document.getElementById('copyBtn').addEventListener('click', () => {
  if (!lastResult) return;
  navigator.clipboard.writeText(lastResult);
  showToast('Copied to clipboard');
});

// ── Download ──
document.getElementById('downloadBtn').addEventListener('click', () => {
  if (!lastResult) return;
  const blob = new Blob([lastResult], { type: 'text/plain' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `qyverix-analysis-${Date.now()}.txt`;
  a.click();
});

// ── Save favorite ──
document.getElementById('saveBtn').addEventListener('click', () => {
  if (!lastResult) return;
  const entry = {
    id: Date.now(),
    code: codeInput.value.slice(0, 100),
    result: lastResult,
    mode: currentMode,
    time: new Date().toLocaleString()
  };
  favorites.unshift(entry);
  if (favorites.length > 20) favorites = favorites.slice(0, 20);
  localStorage.setItem('qyverix_favorites', JSON.stringify(favorites));
  renderFavorites();
  showToast('Saved to favorites ♡');
});

// ── Clear history ──
document.getElementById('clearHistoryBtn').addEventListener('click', () => {
  history = [];
  localStorage.setItem('qyverix_history', JSON.stringify(history));
  renderHistory();
});

// ── Download History JSON ──
document.getElementById('downloadJsonBtn').addEventListener('click', () => {

  if (history.length === 0) {
    showToast('No history to download');
    return;
  }

  const blob = new Blob(
    [JSON.stringify(history, null, 2)],
    { type: 'application/json' }
  );

  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'analysis-history.json';
  a.click();
  URL.revokeObjectURL(a.href);

});
// ── Download History CSV ──
document.getElementById('downloadCsvBtn').addEventListener('click', () => {

  if (history.length === 0) {
    showToast('No history to download');
    return;
  }

  const headers = ['id', 'preview', 'mode', 'time'];

  const rows = history.map(h =>
    [
      h.id,
      `"${(h.preview || '').replace(/"/g, '""')}"`,
      h.mode,
      h.time
    ].join(',')
  );

  const csvContent = [
    headers.join(','),
    ...rows
  ].join('\n');

  const blob = new Blob(
    [csvContent],
    { type: 'text/csv' }
  );

  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'analysis-history.csv';
  a.click();
URL.revokeObjectURL(a.href);
});

// ── Run Button ──
runBtn.addEventListener('click', runAnalysis);

function scrollToApp() {
  document.getElementById('app').scrollIntoView({ behavior: 'smooth' });
}
window.scrollToApp = scrollToApp;

// ── Connection check ──
async function checkConnection() {
  statusDot.className = 'status-dot checking';
  const currentApi = getApiUrl();
  const suggestedApi = normalizeApiUrl(getSuggestedApiUrl());
  try {
    const resp = await fetch(`${currentApi}/health`, { signal: AbortSignal.timeout(3000) });
    if (!resp.ok) {
      statusDot.className = 'status-dot offline';
      setEngineBadge('unknown');
      return;
    }

    const health = await resp.json().catch(() => ({}));
    statusDot.className = 'status-dot online';
    setEngineBadge(health.llm_enabled ? 'llm' : 'rule');
  } catch {
    if (suggestedApi && suggestedApi !== currentApi) {
      try {
        const fallbackResp = await fetch(`${suggestedApi}/health`, { signal: AbortSignal.timeout(3000) });
        if (fallbackResp.ok) {
          const fallbackHealth = await fallbackResp.json().catch(() => ({}));
          apiUrlInput.value = suggestedApi;
          localStorage.setItem(API_URL_STORAGE_KEY, suggestedApi);
          updateDocsLink();
          statusDot.className = 'status-dot online';
          setEngineBadge(fallbackHealth.llm_enabled ? 'llm' : 'rule');
          return;
        }
      } catch {
        // Keep offline state below if fallback fails.
      }
    }

    statusDot.className = 'status-dot offline';
    setEngineBadge('unknown');
  }
}

function normalizeApiUrl(url) {
  return (url || '').trim().replace(/\/$/, '');
}

function getHostname(url) {
  try {
    return new URL(url).hostname;
  } catch {
    return '';
  }
}

function isLocalHostName(hostname) {
  return hostname === 'localhost' || hostname === '127.0.0.1';
}

function getSuggestedApiUrl() {
  if (window.location.protocol === 'file:') {
    return 'http://localhost:8000';
  }
  return `${window.location.protocol}//${window.location.host}`;
}

function updateDocsLink() {
  if (!apiDocsLink) return;
  apiDocsLink.href = `${getApiUrl()}/docs`;
}

function setEngineBadge(mode) {
  if (!engineBadge) return;

  if (mode === 'llm') {
    engineBadge.className = 'engine-badge llm';
    engineBadge.textContent = 'Engine: LLM';
    engineBadge.title = 'LLM mode active';
    return;
  }

  if (mode === 'rule') {
    engineBadge.className = 'engine-badge rule';
    engineBadge.textContent = 'Engine: Rule-based';
    engineBadge.title = 'Rule-based mode active';
    return;
  }

  engineBadge.className = 'engine-badge unknown';
  engineBadge.textContent = 'Engine: Unknown';
  engineBadge.title = 'Engine status unavailable';
}

function initializeApiUrl() {
  const saved = normalizeApiUrl(localStorage.getItem(API_URL_STORAGE_KEY));
  const current = normalizeApiUrl(apiUrlInput.value);
  const suggested = normalizeApiUrl(getSuggestedApiUrl());
  const pageHost = window.location.hostname;

  let chosen = saved || current || suggested;

  if (
    saved &&
    window.location.protocol !== 'file:' &&
    !isLocalHostName(pageHost) &&
    isLocalHostName(getHostname(saved))
  ) {
    chosen = suggested;
  }

  apiUrlInput.value = chosen;
  localStorage.setItem(API_URL_STORAGE_KEY, chosen);
  updateDocsLink();
}

function getApiUrl() {
  return normalizeApiUrl(apiUrlInput.value) || normalizeApiUrl(getSuggestedApiUrl());
}

function getUserFriendlyError(err, responseStatus) {
  const raw = (err && err.message ? String(err.message) : '').toLowerCase();

  if (raw.includes('failed to fetch') || raw.includes('networkerror') || raw.includes('network request failed')) {
    return `Could not reach the backend at ${getApiUrl()}. Check the API URL and that the server is running.`;
  }

  if (responseStatus === 401) {
    return 'Unauthorized request. Check your API key or auth settings.';
  }

  if (responseStatus === 402 || responseStatus === 429 || raw.includes('insufficient_quota') || raw.includes('quota')) {
    return 'Provider quota/billing limit reached. Switch to rule-based mode or update billing.';
  }

  if (responseStatus >= 500) {
    return 'Server error while analyzing code. Try again in a moment.';
  }

  if (err && err.message) {
    return err.message;
  }

  return 'Could not reach the backend. Make sure it is running.';
}

initializeApiUrl();
apiUrlInput.addEventListener('change', () => {
  localStorage.setItem(API_URL_STORAGE_KEY, getApiUrl());
  updateDocsLink();
  checkConnection();
});
checkConnection();

// ── Main Analysis ──
async function runAnalysis() {

  if (isAnalyzing) {
    return;
  }

  const code = sanitizeClientCode(codeInput.value.trim());
  if (!code) {
    showError('Please paste some code first.');
    return;
  }

  isAnalyzing = true;

  runBtn.disabled = true;
  runBtn.classList.add('loading');
  runLabel.textContent = '⟳ Analyzing...';
  showLoading();

  const url = `${getApiUrl()}/${currentMode === 'analyze' ? 'analyze' : currentMode}/`;

  try {
    let responseStatus = 0;
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code })
    });
    responseStatus = resp.status;

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(getUserFriendlyError({ message: err.detail || `HTTP ${resp.status}` }, responseStatus));
    }

    const data = await resp.json();
    renderResult(data, currentMode);
    saveHistory(code, currentMode, data);
    statusDot.className = 'status-dot online';
  } catch (err) {
    showError(getUserFriendlyError(err, 0));
    statusDot.className = 'status-dot offline';
    setEngineBadge('unknown');
  } finally {
    isAnalyzing = false;
    runBtn.disabled = false;
    runBtn.classList.remove('loading');
    runLabel.textContent = '▶ Analyze Code';
  }
}

// ── Render Output ──
function renderResult(data, mode) {
  let html = '';
  let text = '';

  if (mode === 'analyze') {
    // Full analysis
    if (data.explanation) {
      const ex = data.explanation;
      text += `=== EXPLANATION ===\n`;
      html += `<div class="result-section">
        <h4>Explanation</h4>
        <div class="result-text">
          <p><strong>Language:</strong> ${escHtml(ex.language || 'Unknown')}</p>
          <p style="margin-top:8px">${escHtml(ex.summary || '')}</p>
          ${(ex.key_points || []).map(p => `<p>• ${escHtml(p)}</p>`).join('')}
        </div>
      </div>`;
      text += `Language: ${ex.language}\n${ex.summary}\n${(ex.key_points || []).join('\n')}\n\n`;
    }
    if (data.debugging) {
      const dg = data.debugging;
      text += `=== DEBUGGING ===\n`;
      const issues = dg.issues || [];
      html += `<div class="result-section">
        <h4>Debugging</h4>
        <div class="result-text">
          ${issues.length === 0
            ? '<span class="result-tag tag-ok">✓ No issues found</span>'
            : issues.map(i => `<div style="margin-bottom:10px">
                <span class="result-tag tag-error">${escHtml(i.type || 'Issue')}</span>
                <p style="margin-top:4px">${escHtml(i.description || '')}</p>
                ${i.suggestion ? `<p style="color:var(--accent-green);margin-top:4px">Fix: ${escHtml(i.suggestion)}</p>` : ''}
              </div>`).join('')}
        </div>
      </div>`;
      text += issues.map(i => `${i.type}: ${i.description}\nFix: ${i.suggestion}`).join('\n') + '\n\n';
    }
    if (data.suggestions) {
      const sg = data.suggestions;
      const cards = sg.suggestions || [];
      text += `=== SUGGESTIONS ===\n`;
      html += `<div class="result-section">
        <h4>Improvements</h4>
        <div class="result-text">
          ${cards.map(c => `<div style="margin-bottom:10px">
            <span class="result-tag tag-info">${escHtml(c.category || 'Tip')}</span>
            <p style="margin-top:4px">${escHtml(c.description || '')}</p>
          </div>`).join('')}
        </div>
      </div>`;
      text += cards.map(c => `[${c.category}] ${c.description}`).join('\n');
    }
  } else if (mode === 'explanation') {
    html += `<div class="result-section">
      <h4>Language</h4>
      <div class="result-text">${escHtml(data.language || 'Auto-detected')}</div>
    </div>
    <div class="result-section">
      <h4>Summary</h4>
      <div class="result-text">${escHtml(data.summary || '')}</div>
    </div>
    <div class="result-section">
      <h4>Key Points</h4>
      <div class="result-text">${(data.key_points || []).map(p => `<p>• ${escHtml(p)}</p>`).join('')}</div>
    </div>`;
    text = `Language: ${data.language}\n${data.summary}\n${(data.key_points || []).join('\n')}`;
  } else if (mode === 'debugging') {
    const issues = data.issues || [];
    html += `<div class="result-section">
      <h4>Issues Found (${issues.length})</h4>
      <div class="result-text">
        ${issues.length === 0
          ? '<span class="result-tag tag-ok">✓ No issues detected. Code looks clean!</span>'
          : issues.map(i => `<div style="margin-bottom:14px;padding:12px;background:var(--bg-2);border-radius:6px;border:1px solid var(--border)">
              <span class="result-tag tag-error">${escHtml(i.type || 'Issue')}</span>
              ${i.line ? `<span class="result-tag tag-info">Line ${i.line}</span>` : ''}
              <p style="margin-top:8px">${escHtml(i.description || '')}</p>
              ${i.suggestion ? `<p style="margin-top:6px;color:var(--accent-green)">→ ${escHtml(i.suggestion)}</p>` : ''}
            </div>`).join('')}
      </div>
    </div>`;
    text = issues.map(i => `[${i.type}] Line ${i.line}: ${i.description}\nFix: ${i.suggestion}`).join('\n');
  } else if (mode === 'suggestions') {
    const cards = data.suggestions || [];
    html += `<div class="result-section">
      <h4>Suggestions (${cards.length})</h4>
      <div class="result-text">
        ${cards.map(c => `<div style="margin-bottom:12px;padding:12px;background:var(--bg-2);border-radius:6px;border:1px solid var(--border)">
          <span class="result-tag tag-info">${escHtml(c.category || 'Tip')}</span>
          <p style="margin-top:8px">${escHtml(c.description || '')}</p>
          ${c.example ? `<pre style="margin-top:8px;font-size:12px;color:var(--text-3)">${escHtml(c.example)}</pre>` : ''}
        </div>`).join('')}
      </div>
    </div>`;
    text = cards.map(c => `[${c.category}] ${c.description}`).join('\n');
  }

  lastResult = text;
  outputBox.innerHTML = html || '<p style="color:var(--text-3)">No structured output returned.</p>';
}

function showLoading() {
  outputBox.innerHTML = `<div class="output-placeholder">
    <div class="placeholder-icon" style="animation:pulse 1s infinite">⬡</div>
    <p>Analyzing your code...</p>
  </div>`;
}

function resetOutput() {
  lastResult = '';
  outputBox.innerHTML = `<div class="output-placeholder">
    <div class="placeholder-icon">◇</div>
    <p>Your analysis will appear here.</p>
    <p class="placeholder-sub">Paste code → select mode → click Analyze.</p>
  </div>`;
}

function showError(msg) {
  outputBox.innerHTML = `<div class="result-section">
    <h4>Error</h4>
    <div class="result-text">
      <span class="result-tag tag-error">✕ ${msg}</span>
      <p style="margin-top:12px;color:var(--text-2)">Check that the backend is running at: <code>${getApiUrl()}</code></p>
    </div>
  </div>`;
}

// ── History ──
function saveHistory(code, mode, result) {
  history.unshift({
    id: Date.now(),
    preview: code.slice(0, 60).replace(/\n/g, ' ') + (code.length > 60 ? '...' : ''),
    mode,
    time: new Date().toLocaleTimeString()
  });
  if (history.length > 50) history = history.slice(0, 50);
  localStorage.setItem('qyverix_history', JSON.stringify(history));
  renderHistory();
}

function renderHistory() {
  if (history.length === 0) {
    historyContainer.innerHTML = '<p class="history-empty">No history yet. Run your first analysis above.</p>';
    return;
  }
  historyContainer.innerHTML = history.slice(0, 10).map(h => `
    <div class="history-item">
      <div>
        <div class="history-preview">${escHtml(h.preview)}</div>
        <div class="history-meta">${escHtml(safeModeLabel(h.mode))} · ${escHtml(h.time)}</div>
      </div>
    </div>
  `).join('');
}

function renderFavorites() {
  if (favorites.length === 0) {
    favContainer.innerHTML = '<p class="history-empty">No favorites saved yet.</p>';
    return;
  }
  favContainer.innerHTML = favorites.map(f => `
    <div class="history-item">
      <div>
        <div class="history-preview">${escHtml(f.code)}...</div>
        <div class="history-meta">${escHtml(safeModeLabel(f.mode))} · ${escHtml(f.time)}</div>
      </div>
    </div>
  `).join('');
}

// ── Toast ──
function showToast(msg) {
  const t = document.createElement('div');
  t.style.cssText = `
    position:fixed;bottom:24px;right:24px;z-index:9999;
    padding:10px 18px;background:var(--text);color:var(--bg);
    border-radius:8px;font-family:var(--font-mono);font-size:13px;
    animation:fadeIn 0.2s ease;pointer-events:none;
  `;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 2200);
}

// Fix #422 — Weekly Digest subscribe handler
const digestForm = document.getElementById('digestForm');
const digestEmail = document.getElementById('digestEmail');
const digestBtn = document.getElementById('digestBtn');

if (digestForm) {
  digestForm.addEventListener('submit', (e) => {
    e.preventDefault(); // stop page reload

    const email = digestEmail.value.trim();

    // Show loading state
    digestBtn.textContent = 'Subscribing...';
    digestBtn.disabled = true;

    // Simulate subscription (replace with real API call when backend is ready)
    setTimeout(() => {
      // Show success message
      digestForm.innerHTML = `<p style="font-size:0.8rem;color:#4caf50;margin:0;">✓ You have been subscribed!</p>`;
    }, 800);
  });
}

// ── Init ──
renderHistory();
renderFavorites();