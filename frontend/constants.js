/**
 * Shared constants for QyverixAI frontend.
 * Loaded by index.html before script.js and security-utils.js.
 */

// ── Analysis Modes ─────────────────────────────────────────────
const ALLOWED_MODES = new Set(['analyze', 'explanation', 'debugging', 'suggestions']);

// ── localStorage Keys ──────────────────────────────────────────
const STORAGE_KEYS = {
  API_URL:   'qyverix_api_url',
  HISTORY:   'qyverix_history',
  FAVORITES: 'qyverix_favorites',
  THEME:     'qyverix_theme',
};

// ── Validation Sets ────────────────────────────────────────────
const ALLOWED_PRIORITIES = new Set(['high', 'medium', 'low']);
const ALLOWED_SEVERITIES = new Set(['error', 'warning', 'info']);

// ── Stored Entry Limits ────────────────────────────────────────
const STORED_ENTRY_LIMITS = { lang: 64, ts: 64, preview: 120 };
