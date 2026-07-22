/**
 * Static assertions that all expected empty-state elements are present
 * in index.html with correct structure, roles, and i18n attributes.
 *
 * Run with: node tests/empty-states.test.js
 */
import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const html = fs.readFileSync(path.resolve(__dirname, '..', 'index.html'), 'utf8');

// ── Result-panel empty states ────────────────────────────────────────────────

assert.match(
  html,
  /id="emptyExplain"/,
  'explain pane should have an emptyExplain empty-state element',
);
assert.match(
  html,
  /id="emptyDebug"/,
  'debug pane should have an emptyDebug empty-state element',
);
assert.match(
  html,
  /id="emptySuggest"/,
  'suggest pane should have an emptySuggest empty-state element',
);

// Each result-pane empty state should use the .empty-state class
assert.match(
  html,
  /id="emptyExplain"[^>]*>[\s\S]*?class="empty-state"|class="empty-state"[^>]*>[\s\S]{0,200}id="emptyExplain"|id="emptyExplain"[\s\S]{0,50}empty-state/,
  'emptyExplain should use empty-state styling',
);

// Each result pane empty state should have a human-readable title
assert.match(
  html,
  /data-i18n="empty_explain_title"/,
  'explain empty state should have an i18n title',
);
assert.match(
  html,
  /data-i18n="empty_debug_title"/,
  'debug empty state should have an i18n title',
);
assert.match(
  html,
  /data-i18n="empty_suggest_title"/,
  'suggest empty state should have an i18n title',
);

// Each result pane empty state should have a description
assert.match(
  html,
  /data-i18n="empty_explain_desc"/,
  'explain empty state should have an i18n description',
);
assert.match(
  html,
  /data-i18n="empty_debug_desc"/,
  'debug empty state should have an i18n description',
);
assert.match(
  html,
  /data-i18n="empty_suggest_desc"/,
  'suggest empty state should have an i18n description',
);

// Icons in result pane empty states should be aria-hidden
assert.match(
  html,
  /class="empty-icon"[^>]*aria-hidden="true"|aria-hidden="true"[^>]*class="empty-icon"/,
  'result pane empty-state icons should be aria-hidden',
);

// ── History empty state ──────────────────────────────────────────────────────

assert.match(
  html,
  /id="emptyHistory"/,
  'history panel should have an emptyHistory empty-state element',
);
assert.match(
  html,
  /class="list-empty-state"[\s\S]{0,400}id="emptyHistory"|id="emptyHistory"[\s\S]{0,20}class="list-empty-state"|id="emptyHistory"/,
  'emptyHistory should use list-empty-state styling',
);
assert.match(
  html,
  /class="list-empty-title"/,
  'history and favorites empty states should have a list-empty-title element',
);
assert.match(
  html,
  /class="list-empty-desc"/,
  'history and favorites empty states should have a list-empty-desc element',
);
assert.match(
  html,
  /class="list-empty-icon"[^>]*aria-hidden="true"|aria-hidden="true"[^>]*class="list-empty-icon"/,
  'list empty-state icons should be aria-hidden',
);

// ── Favorites empty state ────────────────────────────────────────────────────

assert.match(
  html,
  /id="emptyFavorites"/,
  'favorites panel should have an emptyFavorites empty-state element',
);

// ── i18n keys exist in the translations object ───────────────────────────────

assert.match(
  html,
  /empty_history_title:/,
  'translations should include empty_history_title key',
);
assert.match(
  html,
  /empty_history_desc:/,
  'translations should include empty_history_desc key',
);
assert.match(
  html,
  /empty_favorites_title:/,
  'translations should include empty_favorites_title key',
);
assert.match(
  html,
  /empty_favorites_desc:/,
  'translations should include empty_favorites_desc key',
);

// ── CSS classes exist ────────────────────────────────────────────────────────

assert.match(
  html,
  /\.list-empty-state\s*\{/,
  'CSS should define .list-empty-state rule',
);
assert.match(
  html,
  /\.list-empty-icon\s*\{/,
  'CSS should define .list-empty-icon rule',
);
assert.match(
  html,
  /\.list-empty-title\s*\{/,
  'CSS should define .list-empty-title rule',
);
assert.match(
  html,
  /\.list-empty-desc\s*\{/,
  'CSS should define .list-empty-desc rule',
);

// ── aria-live regions ────────────────────────────────────────────────────────

assert.match(
  html,
  /id="historyList"[^>]*aria-live="polite"|aria-live="polite"[^>]*id="historyList"/,
  'history list should have aria-live="polite" for screen reader announcements',
);
assert.match(
  html,
  /id="favList"[^>]*aria-live="polite"|aria-live="polite"[^>]*id="favList"/,
  'favorites list should have aria-live="polite" for screen reader announcements',
);

console.log('All empty-state assertions passed.');
