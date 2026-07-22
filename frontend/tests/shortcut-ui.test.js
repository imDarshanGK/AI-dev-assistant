import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const indexHtml = fs.readFileSync(path.resolve(__dirname, '..', 'index.html'), 'utf8');

// ── Original shortcuts ──────────────────────────────────────────────────────
assert.match(indexHtml, /class="shortcut-hints"/, 'shortcut hints should be visible in the frontend');
assert.match(indexHtml, /<kbd>Ctrl\/⌘ \+ Enter<\/kbd>/, 'analyze shortcut should be displayed');
assert.match(indexHtml, /<kbd>\/<\/kbd>/, 'editor focus shortcut should be displayed');
assert.match(indexHtml, /<kbd>Esc<\/kbd>/, 'editor escape shortcut should be displayed');
assert.match(
  indexHtml,
  /aria-keyshortcuts="Control\+Enter Meta\+Enter"/,
  'analyze shortcut should be exposed to assistive technology',
);

// ── New shortcuts ───────────────────────────────────────────────────────────
assert.match(indexHtml, /<kbd>Ctrl\/⌘ \+ K<\/kbd>/, 'clear shortcut should be displayed');
assert.match(indexHtml, /<kbd>Ctrl\/⌘ \+ Shift \+ T<\/kbd>/, 'theme toggle shortcut should be displayed');
assert.match(indexHtml, /<kbd>Alt \+ 1–4<\/kbd>/, 'mode switch shortcut should be displayed');

assert.match(
  indexHtml,
  /aria-keyshortcuts="Control\+K Meta\+K"/,
  'clear shortcut should be exposed to assistive technology on clearBtn',
);
assert.match(
  indexHtml,
  /aria-keyshortcuts="Control\+Shift\+T Meta\+Shift\+T"/,
  'theme toggle shortcut should be exposed to assistive technology on themeToggle',
);
assert.match(
  indexHtml,
  /aria-keyshortcuts="Alt\+1"/,
  'analyze mode shortcut should be exposed to assistive technology',
);
assert.match(
  indexHtml,
  /aria-keyshortcuts="Alt\+2"/,
  'explain mode shortcut should be exposed to assistive technology',
);
assert.match(
  indexHtml,
  /aria-keyshortcuts="Alt\+3"/,
  'debug mode shortcut should be exposed to assistive technology',
);
assert.match(
  indexHtml,
  /aria-keyshortcuts="Alt\+4"/,
  'suggest mode shortcut should be exposed to assistive technology',
);
