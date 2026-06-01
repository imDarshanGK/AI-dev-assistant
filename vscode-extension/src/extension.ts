import * as vscode from 'vscode';

// ---------------------------------------------------------------------------
// Types mirroring the QyverixAI API response schemas
// ---------------------------------------------------------------------------

interface ExplanationResponse {
  language: string;
  summary: string;
  key_points: string[];
  complexity: string;
  line_count: number;
  function_count: number;
  class_count: number;
}

interface DebugIssue {
  type: string;
  line: number | null;
  description: string;
  suggestion: string;
  severity: 'error' | 'warning' | 'info';
  code_snippet: string | null;
  code_context: string | null;
}

interface DebuggingResponse {
  issues: DebugIssue[];
  summary: string;
  clean: boolean;
  error_count: number;
  warning_count: number;
  info_count: number;
}

interface Suggestion {
  category: string;
  description: string;
  line_number: number | null;
  line_range: [number, number] | null;
  code_context: string | null;
  example: string | null;
  priority: 'high' | 'medium' | 'low';
}

interface SuggestionsResponse {
  suggestions: Suggestion[];
  overall_score: number;
  grade: string;
  next_step: string;
}

interface AnalyzeResponse {
  provider: string;
  model: string;
  explanation: ExplanationResponse;
  debugging: DebuggingResponse;
  suggestions: SuggestionsResponse;
  analysis_time_ms: number | null;
}

// ---------------------------------------------------------------------------
// Diagnostics collection shared across commands
// ---------------------------------------------------------------------------

let diagnosticCollection: vscode.DiagnosticCollection;

// ---------------------------------------------------------------------------
// HTTP helper
// ---------------------------------------------------------------------------

function postToApi<T>(endpoint: string, body: object, timeoutS: number): Promise<T> {
  const cfg = vscode.workspace.getConfiguration('qyverixai');
  const baseUrl = cfg.get<string>('apiUrl', 'https://qyverixai.onrender.com').replace(/\/+$/, '');
  const url = `${baseUrl}${endpoint}`;

  return new Promise<T>((resolve, reject) => {
    const isHttps = url.startsWith('https');
    const mod = isHttps ? require('https') : require('http');

    const payload = JSON.stringify(body);
    const parsed = new URL(url);

    const opts = {
      hostname: parsed.hostname,
      port: parsed.port || (isHttps ? 443 : 80),
      path: parsed.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(payload),
      },
      timeout: timeoutS * 1000,
    };

    const req = mod.request(opts, (res: any) => {
      let data = '';
      res.on('data', (chunk: string) => (data += chunk));
      res.on('end', () => {
        if (res.statusCode && res.statusCode >= 200 && res.statusCode < 300) {
          try {
            resolve(JSON.parse(data) as T);
          } catch {
            reject(new Error(`Invalid JSON response: ${data.slice(0, 200)}`));
          }
        } else {
          reject(new Error(`API error ${res.statusCode}: ${data.slice(0, 500)}`));
        }
      });
    });

    req.on('error', (err: Error) => reject(new Error(`Request failed: ${err.message}`)));
    req.on('timeout', () => { req.destroy(); reject(new Error('Request timed out')); });

    req.write(payload);
    req.end();
  });
}

// ---------------------------------------------------------------------------
// WebView helpers
// ---------------------------------------------------------------------------

function getNonce(): string {
  let text = '';
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  for (let i = 0; i < 64; i++) text += chars.charAt(Math.floor(Math.random() * chars.length));
  return text;
}

function severityColor(severity: string): string {
  switch (severity) {
    case 'error':   return '#f14c4c';
    case 'warning': return '#cca700';
    default:        return '#3794ff';
  }
}

function priorityBadge(priority: string): string {
  switch (priority) {
    case 'high':   return '<span class="badge badge-high">high</span>';
    case 'medium': return '<span class="badge badge-med">medium</span>';
    default:       return '<span class="badge badge-low">low</span>';
  }
}

function renderAnalyzeHtml(res: AnalyzeResponse): string {
  const issues = res.debugging.issues.map(i => `
    <div class="issue">
      <span class="severity" style="color:${severityColor(i.severity)}">●</span>
      <strong>${escapeHtml(i.type)}</strong> ${i.line !== null ? `(line ${i.line})` : ''}
      <p>${escapeHtml(i.description)}</p>
      ${i.suggestion ? `<p class="suggestion">Suggestion: ${escapeHtml(i.suggestion)}</p>` : ''}
      ${i.code_context ? `<pre><code>${escapeHtml(i.code_context)}</code></pre>` : ''}
    </div>
  `).join('');

  const suggestions = res.suggestions.suggestions.map(s => `
    <div class="suggestion-item">
      ${priorityBadge(s.priority)}
      <strong>${escapeHtml(s.category)}</strong>
      <p>${escapeHtml(s.description)}</p>
      ${s.example ? `<pre><code>${escapeHtml(s.example)}</code></pre>` : ''}
    </div>
  `).join('');

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline';">
<title>QyverixAI Analysis</title>
<style>
  body { font-family: var(--vscode-font-family); padding: 16px; color: var(--vscode-editor-foreground); }
  h1 { font-size: 1.4em; margin-bottom: 4px; }
  h2 { font-size: 1.15em; margin-top: 24px; margin-bottom: 8px; border-bottom: 1px solid var(--vscode-panel-border); padding-bottom: 4px; }
  .meta { font-size: 0.85em; color: var(--vscode-descriptionForeground); margin-bottom: 16px; }
  .summary { background: var(--vscode-textBlockQuote-background); padding: 12px; border-radius: 4px; margin-bottom: 16px; }
  .summary p { margin: 4px 0; }
  .issue { margin-bottom: 12px; padding: 8px; background: var(--vscode-textBlockQuote-background); border-radius: 4px; }
  .issue p { margin: 4px 0; }
  .suggestion { color: var(--vscode-textLink-foreground); }
  .suggestion-item { margin-bottom: 10px; padding: 8px; background: var(--vscode-textBlockQuote-background); border-radius: 4px; }
  .badge { display: inline-block; font-size: 0.75em; padding: 1px 6px; border-radius: 3px; margin-right: 6px; }
  .badge-high { background: #f14c4c33; color: #f14c4c; }
  .badge-med  { background: #cca70033; color: #cca700; }
  .badge-low  { background: #3794ff33; color: #3794ff; }
  .stats { display: flex; gap: 16px; margin: 8px 0; }
  .stat { text-align: center; padding: 8px 16px; background: var(--vscode-textBlockQuote-background); border-radius: 4px; }
  .stat-num { font-size: 1.5em; font-weight: bold; }
  .stat-label { font-size: 0.8em; color: var(--vscode-descriptionForeground); }
  pre { background: var(--vscode-textPreformat-background); padding: 8px; border-radius: 4px; overflow-x: auto; }
  code { font-family: var(--vscode-editor-font-family); font-size: 0.9em; }
  .key-points { list-style: disc; padding-left: 20px; }
  .score { font-size: 2em; font-weight: bold; text-align: center; padding: 16px; }
</style>
</head>
<body>
  <h1>QyverixAI Analysis</h1>
  <div class="meta">
    ${escapeHtml(res.provider)} &middot; ${escapeHtml(res.model)} &middot;
    ${res.analysis_time_ms !== null ? `${(res.analysis_time_ms / 1000).toFixed(2)}s` : ''}
  </div>

  <h2>Summary</h2>
  <div class="summary">
    <p><strong>Language:</strong> ${escapeHtml(res.explanation.language)}</p>
    <p><strong>Complexity:</strong> ${escapeHtml(res.explanation.complexity)}</p>
    <p><strong>${res.explanation.line_count}</strong> lines &middot;
       <strong>${res.explanation.function_count}</strong> functions &middot;
       <strong>${res.explanation.class_count}</strong> classes
    </p>
    <p>${escapeHtml(res.explanation.summary)}</p>
  </div>

  ${res.explanation.key_points.length ? `
  <h2>Key Points</h2>
  <ul class="key-points">
    ${res.explanation.key_points.map(kp => `<li>${escapeHtml(kp)}</li>`).join('')}
  </ul>` : ''}

  <h2>Code Quality Score</h2>
  <div class="score" style="color: ${gradeColor(res.suggestions.grade)}">
    ${escapeHtml(res.suggestions.grade)} (${res.suggestions.overall_score}/100)
  </div>

  <h2>Debugging Results</h2>
  <div class="stats">
    <div class="stat"><div class="stat-num" style="color:#f14c4c">${res.debugging.error_count}</div><div class="stat-label">Errors</div></div>
    <div class="stat"><div class="stat-num" style="color:#cca700">${res.debugging.warning_count}</div><div class="stat-label">Warnings</div></div>
    <div class="stat"><div class="stat-num" style="color:#3794ff">${res.debugging.info_count}</div><div class="stat-label">Info</div></div>
  </div>
  ${res.debugging.clean ? '<p>No issues detected.</p>' : issues}

  ${res.suggestions.suggestions.length ? `
  <h2>Suggestions (${escapeHtml(res.suggestions.next_step)})</h2>
  ${suggestions}` : ''}
</body>
</html>`;
}

function renderExplainHtml(res: ExplanationResponse): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline';">
<title>QyverixAI Explanation</title>
<style>
  body { font-family: var(--vscode-font-family); padding: 16px; color: var(--vscode-editor-foreground); }
  h1 { font-size: 1.4em; margin-bottom: 4px; }
  h2 { font-size: 1.15em; margin-top: 24px; border-bottom: 1px solid var(--vscode-panel-border); padding-bottom: 4px; }
  .meta { font-size: 0.85em; color: var(--vscode-descriptionForeground); margin-bottom: 16px; }
  .summary { background: var(--vscode-textBlockQuote-background); padding: 12px; border-radius: 4px; }
  ul { padding-left: 20px; }
  li { margin-bottom: 4px; }
</style>
</head>
<body>
  <h1>Code Explanation</h1>
  <div class="meta">${escapeHtml(res.language)} &middot; ${escapeHtml(res.complexity)}</div>
  <div class="summary">
    <p>${escapeHtml(res.summary)}</p>
    <p style="margin-top:8px;font-size:0.85em;color:var(--vscode-descriptionForeground)">
      ${res.line_count} lines &middot; ${res.function_count} functions &middot; ${res.class_count} classes
    </p>
  </div>
  ${res.key_points.length ? `
  <h2>Key Points</h2>
  <ul>${res.key_points.map(kp => `<li>${escapeHtml(kp)}</li>`).join('')}</ul>` : ''}
</body>
</html>`;
}

function escapeHtml(str: string): string {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function gradeColor(grade: string): string {
  switch (grade) {
    case 'A':
    case 'B':
      return '#4ec948';
    case 'C':
      return '#cca700';
    default:
      return '#f14c4c';
  }
}

// ---------------------------------------------------------------------------
// Diagnostics helpers
// ---------------------------------------------------------------------------

function severityToVsCode(sev: string): vscode.DiagnosticSeverity {
  switch (sev) {
    case 'error':   return vscode.DiagnosticSeverity.Error;
    case 'warning': return vscode.DiagnosticSeverity.Warning;
    default:        return vscode.DiagnosticSeverity.Information;
  }
}

function setDiagnostics(uri: vscode.Uri, issues: DebugIssue[]): void {
  const diagnostics: vscode.Diagnostic[] = [];
  for (const issue of issues) {
    if (issue.line === null) continue;
    const line = Math.max(0, issue.line - 1);
    const range = new vscode.Range(line, 0, line, 65536);
    const diag = new vscode.Diagnostic(
      range,
      `${issue.type}: ${issue.description}`,
      severityToVsCode(issue.severity),
    );
    diag.source = 'QyverixAI';
    diag.code = issue.type;
    diagnostics.push(diag);
  }
  diagnosticCollection.set(uri, diagnostics);
}

// ---------------------------------------------------------------------------
// Command handlers
// ---------------------------------------------------------------------------

async function handleAnalyze(): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  if (!editor) { vscode.window.showWarningMessage('No active editor'); return; }

  const code = editor.document.getText();
  if (!code.trim()) { vscode.window.showWarningMessage('Active file is empty'); return; }

  const panel = vscode.window.createWebviewPanel(
    'qyverixai.analyze',
    `QyverixAI: ${editor.document.fileName.split(/[/\\]/).pop()}`,
    vscode.ViewColumn.Beside,
    { enableScripts: false },
  );

  panel.webview.html = loadingHtml('Analyzing code...');

  const lang = editor.document.languageId;
  const timeout = vscode.workspace.getConfiguration('qyverixai').get<number>('timeout', 30);

  try {
    const res = await postToApi<AnalyzeResponse>('/analyze/', { code, language: lang }, timeout);
    panel.webview.html = renderAnalyzeHtml(res);

    setDiagnostics(editor.document.uri, res.debugging.issues);
    vscode.window.showInformationMessage(
      `QyverixAI: ${res.debugging.error_count} errors, ${res.debugging.warning_count} warnings — grade ${res.suggestions.grade}`,
    );
  } catch (err: any) {
    panel.webview.html = errorHtml(err.message);
    vscode.window.showErrorMessage(`QyverixAI analysis failed: ${err.message}`);
  }
}

async function handleDebug(): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  if (!editor) { vscode.window.showWarningMessage('No active editor'); return; }

  const code = editor.document.getText();
  if (!code.trim()) { vscode.window.showWarningMessage('Active file is empty'); return; }

  const panel = vscode.window.createWebviewPanel(
    'qyverixai.debug',
    `QyverixAI Debug: ${editor.document.fileName.split(/[/\\]/).pop()}`,
    vscode.ViewColumn.Beside,
    { enableScripts: false },
  );

  panel.webview.html = loadingHtml('Debugging code...');

  const lang = editor.document.languageId;
  const timeout = vscode.workspace.getConfiguration('qyverixai').get<number>('timeout', 30);

  try {
    const res = await postToApi<DebuggingResponse>('/debugging/', { code, language: lang }, timeout);
    panel.webview.html = renderDebugHtml(res);
    setDiagnostics(editor.document.uri, res.issues);

    if (res.clean) {
      vscode.window.showInformationMessage('QyverixAI: No issues detected!');
    } else {
      vscode.window.showWarningMessage(
        `QyverixAI: ${res.error_count} errors, ${res.warning_count} warnings found`,
      );
    }
  } catch (err: any) {
    panel.webview.html = errorHtml(err.message);
    vscode.window.showErrorMessage(`QyverixAI debug failed: ${err.message}`);
  }
}

async function handleExplain(): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  if (!editor) { vscode.window.showWarningMessage('No active editor'); return; }

  const code = editor.document.getText();
  if (!code.trim()) { vscode.window.showWarningMessage('Active file is empty'); return; }

  const panel = vscode.window.createWebviewPanel(
    'qyverixai.explain',
    `QyverixAI Explain: ${editor.document.fileName.split(/[/\\]/).pop()}`,
    vscode.ViewColumn.Beside,
    { enableScripts: false },
  );

  panel.webview.html = loadingHtml('Generating explanation...');

  const lang = editor.document.languageId;
  const timeout = vscode.workspace.getConfiguration('qyverixai').get<number>('timeout', 30);

  try {
    const res = await postToApi<ExplanationResponse>('/explanation/', { code, language: lang }, timeout);
    panel.webview.html = renderExplainHtml(res);
  } catch (err: any) {
    panel.webview.html = errorHtml(err.message);
    vscode.window.showErrorMessage(`QyverixAI explanation failed: ${err.message}`);
  }
}

// ---------------------------------------------------------------------------
// HTML fragments
// ---------------------------------------------------------------------------

function loadingHtml(text: string): string {
  return `<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline';"></head>
<body style="display:flex;align-items:center;justify-content:center;height:100vh;font-family:var(--vscode-font-family);color:var(--vscode-descriptionForeground);">
  <p>${escapeHtml(text)}</p>
</body>
</html>`;
}

function errorHtml(msg: string): string {
  return `<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline';"></head>
<body style="padding:24px;font-family:var(--vscode-font-family);">
  <h2 style="color:#f14c4c;">Error</h2>
  <p>${escapeHtml(msg)}</p>
</body>
</html>`;
}

function renderDebugHtml(res: DebuggingResponse): string {
  const issues = res.issues.map(i => `
    <div class="issue">
      <span class="severity" style="color:${severityColor(i.severity)}">●</span>
      <strong>${escapeHtml(i.type)}</strong> ${i.line !== null ? `(line ${i.line})` : ''}
      <p>${escapeHtml(i.description)}</p>
      ${i.suggestion ? `<p class="suggestion">Suggestion: ${escapeHtml(i.suggestion)}</p>` : ''}
      ${i.code_context ? `<pre><code>${escapeHtml(i.code_context)}</code></pre>` : ''}
    </div>
  `).join('');

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline';">
<title>QyverixAI Debug</title>
<style>
  body { font-family: var(--vscode-font-family); padding: 16px; color: var(--vscode-editor-foreground); }
  h1 { font-size: 1.4em; }
  .stats { display: flex; gap: 16px; margin: 12px 0; }
  .stat { text-align: center; padding: 8px 16px; background: var(--vscode-textBlockQuote-background); border-radius: 4px; }
  .stat-num { font-size: 1.5em; font-weight: bold; }
  .stat-label { font-size: 0.8em; color: var(--vscode-descriptionForeground); }
  .issue { margin-bottom: 12px; padding: 8px; background: var(--vscode-textBlockQuote-background); border-radius: 4px; }
  .issue p { margin: 4px 0; }
  .suggestion { color: var(--vscode-textLink-foreground); }
  pre { background: var(--vscode-textPreformat-background); padding: 8px; border-radius: 4px; overflow-x: auto; }
  code { font-family: var(--vscode-editor-font-family); font-size: 0.9em; }
</style>
</head>
<body>
  <h1>Debug Results</h1>
  <p style="color:var(--vscode-descriptionForeground);">${escapeHtml(res.summary)}</p>
  <div class="stats">
    <div class="stat"><div class="stat-num" style="color:#f14c4c">${res.error_count}</div><div class="stat-label">Errors</div></div>
    <div class="stat"><div class="stat-num" style="color:#cca700">${res.warning_count}</div><div class="stat-label">Warnings</div></div>
    <div class="stat"><div class="stat-num" style="color:#3794ff">${res.info_count}</div><div class="stat-label">Info</div></div>
  </div>
  ${res.clean ? '<p>No issues detected. Clean code!</p>' : issues}
</body>
</html>`;
}

// ---------------------------------------------------------------------------
// Activation
// ---------------------------------------------------------------------------

export function activate(context: vscode.ExtensionContext) {
  diagnosticCollection = vscode.languages.createDiagnosticCollection('qyverixai');
  context.subscriptions.push(diagnosticCollection);

  context.subscriptions.push(
    vscode.commands.registerCommand('qyverixai.analyze', handleAnalyze),
    vscode.commands.registerCommand('qyverixai.debug', handleDebug),
    vscode.commands.registerCommand('qyverixai.explain', handleExplain),
  );
}

export function deactivate() {
  if (diagnosticCollection) diagnosticCollection.dispose();
}
