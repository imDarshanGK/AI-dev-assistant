import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const indexHtml = fs.readFileSync(path.resolve(__dirname, '..', 'index.html'), 'utf8');

assert.match(indexHtml, /class="shortcut-hints"/, 'shortcut hints should be visible in the frontend');
assert.match(indexHtml, /<kbd>Ctrl\/⌘ \+ Enter<\/kbd>/, 'analyze shortcut should be displayed');
assert.match(indexHtml, /<kbd>\/<\/kbd>/, 'editor focus shortcut should be displayed');
assert.match(indexHtml, /<kbd>Esc<\/kbd>/, 'editor escape shortcut should be displayed');
assert.match(
  indexHtml,
  /aria-keyshortcuts="Control\+Enter Meta\+Enter"/,
  'analyze shortcut should be exposed to assistive technology',
);
