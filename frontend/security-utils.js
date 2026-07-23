/**
 * Shared XSS/injection helpers for QyverixAI frontend.
 * Loaded by index.html; tested via frontend/tests/*.test.mjs
 */
(function (global) {
  const ALLOWED_PRIORITIES = new Set(['high', 'medium', 'low']);
  const ALLOWED_SEVERITIES = new Set(['error', 'warning', 'info']);
  const STORED_ENTRY_LIMITS = { lang: 64, ts: 64, preview: 120 };

  const FAV_HEART_SVG =
    '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">' +
    '<path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>';

  function escHtml(s) {
    return String(s ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function sanitizeClientCode(text) {
    return String(text)
      .replace(/\x00/g, '')
      .replace(/\x1b\[[0-9;]*[A-Za-z]/g, '');
  }

  function safePriorityClass(priority) {
    const key = String(priority || '').toLowerCase();
    return ALLOWED_PRIORITIES.has(key) ? key : 'medium';
  }

  function safeSeverityClass(severity) {
    const key = String(severity || '').toLowerCase();
    return ALLOWED_SEVERITIES.has(key) ? key : 'info';
  }

  function safeCssToken(value, fallback) {
    const token = String(value || '').trim().replace(/\s+/g, '-');
    return /^[a-z0-9_-]+$/i.test(token) ? token : fallback;
  }

  function safeHistoryId(id) {
    const n = Number(id);
    return Number.isFinite(n) && n > 0 ? n : null;
  }

  function normalizeStoredEntry(entry) {
    if (!entry || typeof entry !== 'object') return null;
    const id = safeHistoryId(entry.id);
    if (id === null) return null;
    return {
      id,
      code: typeof entry.code === 'string' ? entry.code : '',
      result: entry.result ?? null,
      lang: typeof entry.lang === 'string' ? entry.lang.slice(0, STORED_ENTRY_LIMITS.lang) : '?',
      ts: typeof entry.ts === 'string' ? entry.ts.slice(0, STORED_ENTRY_LIMITS.ts) : '',
      preview: typeof entry.preview === 'string' ? entry.preview.slice(0, STORED_ENTRY_LIMITS.preview) : '',
    };
  }

  function loadStoredHistory(storageKey, storage) {
    const store = storage ?? (typeof localStorage !== 'undefined' ? localStorage : null);
    if (!store) return [];
    try {
      const raw = JSON.parse(store.getItem(storageKey) || '[]');
      if (!Array.isArray(raw)) return [];
      return raw.map(normalizeStoredEntry).filter(Boolean);
    } catch {
      return [];
    }
  }

  function saveStoredHistory(storageKey, entries, storage) {
    const store = storage ?? (typeof localStorage !== 'undefined' ? localStorage : null);
    if (!store) return;
    store.setItem(storageKey, JSON.stringify(entries));
  }

  function createStoredEntry({ code, result, lang, ts, preview }) {
    return {
      id: Date.now(),
      code: sanitizeClientCode(code),
      result: result ?? null,
      lang: String(lang || '?').slice(0, STORED_ENTRY_LIMITS.lang),
      ts: String(ts || '').slice(0, STORED_ENTRY_LIMITS.ts),
      preview: String(preview || '')
        .slice(0, STORED_ENTRY_LIMITS.preview)
        .replace(/\n/g, ' '),
    };
  }

  function renderMarkdown(s) {
    const safe = escHtml(s);
    return safe
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(
        /`(.+?)`/g,
        '<code style="font-family:var(--font-mono);font-size:0.85em;background:var(--bg);padding:1px 5px;border-radius:4px;border:1px solid var(--border)">$1</code>',
      );
  }

  function buildStoredListItemHtml(entry, { favorite = false } = {}) {
    const itemClass = favorite ? 'fav-item' : 'history-item';
    const labelKind = favorite ? 'favorite' : 'history';
    const metaHtml = favorite
      ? `<span class="history-meta" style="opacity:0.5">${FAV_HEART_SVG}</span>`
      : `<span class="history-meta">${escHtml(entry.ts)}</span>`;

    return (
      `<div class="${itemClass}" data-entry-id="${entry.id}" tabindex="0" role="button"` +
      ` aria-label="Load ${labelKind} entry for ${escHtml(entry.lang)} at ${escHtml(entry.ts)}">` +
      `<span class="history-lang">${escHtml(entry.lang || '?')}</span>` +
      `<span class="history-thumb">${escHtml(entry.preview)}…</span>` +
      metaHtml +
      `</div>`
    );
  }

  /** @deprecated Use buildStoredListItemHtml — kept for tests */
  const buildHistoryItemHtml = (entry) => buildStoredListItemHtml(entry);

  function bindStoredListNavigation(listEl, loaderFn) {
    if (!listEl || typeof loaderFn !== 'function') return;

    listEl.addEventListener('click', (e) => {
      const item = e.target.closest('[data-entry-id]');
      if (!item || !listEl.contains(item)) return;
      const id = safeHistoryId(item.dataset.entryId);
      if (id !== null) loaderFn(id);
    });

    listEl.addEventListener('keydown', (e) => {
      if (e.key !== 'Enter' && e.key !== ' ') return;
      const item = e.target.closest('[data-entry-id]');
      if (!item || !listEl.contains(item)) return;
      e.preventDefault();
      const id = safeHistoryId(item.dataset.entryId);
      if (id !== null) loaderFn(id);
    });
  }

  function isEditableShortcutTarget(target) {
    if (!target || typeof target !== 'object') return false;
    const tagName = String(target.tagName || '').toLowerCase();
    return (
      tagName === 'input' ||
      tagName === 'textarea' ||
      tagName === 'select' ||
      target.isContentEditable === true
    );
  }

  function matchesKeyboardShortcut(event, shortcut) {
    if (!event || !shortcut || typeof shortcut.key !== 'string') return false;

    const eventKey = String(event.key || '').toLowerCase();
    const shortcutKey = shortcut.key.toLowerCase();
    if (eventKey !== shortcutKey) return false;

    if (shortcut.mod) {
      if (!event.ctrlKey && !event.metaKey) return false;
    } else if (
      Boolean(event.ctrlKey) !== Boolean(shortcut.ctrl) ||
      Boolean(event.metaKey) !== Boolean(shortcut.meta)
    ) {
      return false;
    }

    return (
      Boolean(event.altKey) === Boolean(shortcut.alt) &&
      Boolean(event.shiftKey) === Boolean(shortcut.shift)
    );
  }

  /**
   * Bind declarative keyboard shortcuts and return a function that removes them.
   * Plain-key shortcuts ignore form fields by default; set allowInEditable when a
   * shortcut is intentionally available while the user is typing.
   */
  function bindKeyboardShortcuts(target, shortcuts) {
    if (!target || typeof target.addEventListener !== 'function') {
      throw new TypeError('A valid keyboard event target is required');
    }

    const bindings = Array.isArray(shortcuts) ? shortcuts : [];
    const onKeydown = (event) => {
      if (event.defaultPrevented || event.repeat || event.isComposing) return;

      for (const shortcut of bindings) {
        if (!shortcut || typeof shortcut.handler !== 'function') continue;
        if (
          !shortcut.allowInEditable &&
          isEditableShortcutTarget(event.target)
        ) {
          continue;
        }
        if (
          typeof shortcut.when === 'function' &&
          !shortcut.when(event)
        ) {
          continue;
        }
        if (!matchesKeyboardShortcut(event, shortcut)) continue;

        if (shortcut.preventDefault !== false) event.preventDefault();
        if (shortcut.stopPropagation) event.stopPropagation();
        shortcut.handler(event);
        break;
      }
    };

    target.addEventListener('keydown', onKeydown);
    return () => target.removeEventListener('keydown', onKeydown);
  }

  /** Minimal card builders used by security tests (mirror panel class rules). */
  function buildIssueCardHtml(issue) {
    return (
      `<div class="issue-card ${safeSeverityClass(issue.severity)}">` +
      `<span class="issue-type">${escHtml(issue.type)}</span>` +
      `<div class="issue-desc">${escHtml(issue.description)}</div>` +
      `</div>`
    );
  }

  function buildSuggestCardHtml(suggestion) {
    return (
      `<div class="suggest-card priority-${safePriorityClass(suggestion.priority)}">` +
      `<div class="suggest-desc">${escHtml(suggestion.description)}</div>` +
      `</div>`
    );
  }

  /** Shared empty-state renderer — consistent messaging across all result lists. */
  function buildEmptyStateHtml(message, { tag = 'ok' } = {}) {
    return `<span class="result-tag tag-${safeCssToken(tag, 'ok')}">${escHtml(message)}</span>`;
  }

  /** Renders a list of issue cards, or a consistent empty state if none exist. */
  function buildIssuesListHtml(issues, { emptyMessage = '✓ No issues found. Code looks clean!' } = {}) {
    if (!Array.isArray(issues) || issues.length === 0) {
      return buildEmptyStateHtml(emptyMessage);
    }
    return issues.map(buildIssueCardHtml).join('');
  }

  /** Renders a list of suggestion cards, or a consistent empty state if none exist. */
  function buildSuggestionsListHtml(suggestions, { emptyMessage = 'No suggestions available.' } = {}) {
    if (!Array.isArray(suggestions) || suggestions.length === 0) {
      return buildEmptyStateHtml(emptyMessage);
    }
    return suggestions.map(buildSuggestCardHtml).join('');
  }

  /** Renders a stored history/favorites list, or a consistent empty state if none exist. */
  function buildStoredListHtml(entries, loaderOpts, { emptyMessage = 'No entries yet.' } = {}) {
    if (!Array.isArray(entries) || entries.length === 0) {
      return `<p class="history-empty">${escHtml(emptyMessage)}</p>`;
    }
    return entries.map((e) => buildStoredListItemHtml(e, loaderOpts)).join('');
  }

  global.QyverixSecurity = {
    ALLOWED_PRIORITIES,
    ALLOWED_SEVERITIES,
    STORED_ENTRY_LIMITS,
    escHtml,
    sanitizeClientCode,
    safePriorityClass,
    safeSeverityClass,
    safeCssToken,
    safeHistoryId,
    normalizeStoredEntry,
    loadStoredHistory,
    saveStoredHistory,
    createStoredEntry,
    renderMarkdown,
    buildStoredListItemHtml,
    buildHistoryItemHtml,
    bindStoredListNavigation,
    isEditableShortcutTarget,
    matchesKeyboardShortcut,
    bindKeyboardShortcuts,
    buildIssueCardHtml,
    buildSuggestCardHtml,
    buildEmptyStateHtml,
    buildIssuesListHtml,
    buildSuggestionsListHtml,
    buildStoredListHtml,
  };
})(typeof window !== 'undefined' ? window : globalThis);
