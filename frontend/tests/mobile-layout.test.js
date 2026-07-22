/**
 * Static assertions that the mobile layout CSS improvements are present
 * in index.html.
 *
 * Run with: node tests/mobile-layout.test.js
 */
import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const html = fs.readFileSync(path.resolve(__dirname, '..', 'index.html'), 'utf8');

// ── Breakpoint existence ─────────────────────────────────────────────────────

assert.match(
  html,
  /@media\(max-width:600px\)/,
  '600px breakpoint should be present',
);
assert.match(
  html,
  /@media\(max-width:400px\)/,
  '400px breakpoint should be present',
);
assert.match(
  html,
  /@media\(max-width:900px\)/,
  '900px (tablet) breakpoint for workspace grid should be present',
);

// ── 44px touch target enforcement ────────────────────────────────────────────

assert.match(
  html,
  /min-height:44px/,
  'At least one element should enforce a 44px minimum touch target height',
);

// ── Mode buttons: min-height touch target ────────────────────────────────────

assert.match(
  html,
  /\.mode-btn\{[^}]*min-height:44px|mode-btn[^{]*\{[^}]*min-height:44px/,
  'mode-btn should have min-height:44px in mobile breakpoint',
);

// ── Shortcut hints hidden on small screens ───────────────────────────────────

assert.match(
  html,
  /\.shortcut-hints\{display:none\}|\.shortcut-hints\s*\{\s*display\s*:\s*none/,
  'shortcut-hints should be hidden (display:none) inside a mobile breakpoint',
);

// ── Panel header flex-wrap ────────────────────────────────────────────────────

assert.match(
  html,
  /\.panel-header\{[^}]*flex-wrap:wrap|panel-header[^{]*\{[^}]*flex-wrap\s*:\s*wrap/,
  'panel-header should use flex-wrap:wrap in mobile breakpoint',
);

// ── Horizontal scroll for lang-tabs and result-tabs on 400px ─────────────────

assert.match(
  html,
  /\.lang-tabs\{overflow-x:auto|lang-tabs[^{]*\{[^}]*overflow-x\s*:\s*auto/,
  'lang-tabs should allow horizontal scroll on 400px breakpoint',
);
assert.match(
  html,
  /\.result-tabs\{overflow-x:auto|result-tabs[^{]*\{[^}]*overflow-x\s*:\s*auto/,
  'result-tabs should allow horizontal scroll on 400px breakpoint',
);

// ── Editor height reduction on mobile ────────────────────────────────────────

assert.match(
  html,
  /#codeEditor\{[^}]*min-height:200px|#codeEditor[^{]*\{[^}]*min-height\s*:\s*200px/,
  'codeEditor should have reduced min-height on mobile',
);

// ── API URL input full-width on mobile ────────────────────────────────────────

assert.match(
  html,
  /#apiUrl\{[^}]*width:100%|#apiUrl[^{]*\{[^}]*width\s*:\s*100%/,
  'apiUrl input should be full-width on mobile',
);

// ── Result actions wrapping ───────────────────────────────────────────────────

assert.match(
  html,
  /\.result-actions\{[^}]*flex-wrap:wrap|result-actions[^{]*\{[^}]*flex-wrap\s*:\s*wrap/,
  'result-actions should wrap on mobile',
);

// ── Pagination touch targets ──────────────────────────────────────────────────

assert.match(
  html,
  /#btnPrevHistory,#btnNextHistory\{[^}]*min-height:44px|btnPrevHistory[^{]*\{[^}]*min-height\s*:\s*44px/,
  'history pagination buttons should have 44px touch target',
);

// ── Viewport meta tag ─────────────────────────────────────────────────────────

assert.match(
  html,
  /<meta[^>]+name="viewport"[^>]+content="[^"]*width=device-width/,
  'viewport meta tag with width=device-width should be present for proper mobile scaling',
);

console.log('All mobile layout assertions passed.');
