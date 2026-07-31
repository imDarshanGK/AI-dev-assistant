import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const indexHtml = fs.readFileSync(path.resolve(__dirname, '..', 'index.html'), 'utf8');

const resultEmptyStates = [
  {
    id: 'emptyExplain',
    titleKey: 'empty_explain_title',
    title: 'No analysis yet',
    descKey: 'empty_explain_desc',
    desc: 'Paste your code and click Analyze to see results',
  },
  {
    id: 'emptyDebug',
    titleKey: 'empty_debug_title',
    title: 'No bugs scanned',
    descKey: 'empty_debug_desc',
    desc: 'Run analysis to detect issues in your code',
  },
  {
    id: 'emptySuggest',
    titleKey: 'empty_suggest_title',
    title: 'No suggestions yet',
    descKey: 'empty_suggest_desc',
    desc: 'Run analysis to get improvement ideas',
  },
];

for (const state of resultEmptyStates) {
  const block = indexHtml.match(
    new RegExp(`<div class="empty-state" id="${state.id}">([\\s\\S]*?)</div>\\s*<div id=`)
  );
  assert.ok(block, `Missing empty-state markup for #${state.id}`);
  assert.match(
    block[1],
    new RegExp(`data-i18n="${state.titleKey}">${state.title}<`),
    `#${state.id} should surface title "${state.title}"`
  );
  assert.match(
    block[1],
    new RegExp(`data-i18n="${state.descKey}">${state.desc}<`),
    `#${state.id} should surface description "${state.desc}"`
  );
  assert.match(block[1], /class="empty-icon"/, `#${state.id} should include an empty-icon`);
}

assert.match(
  indexHtml,
  /id="historyList"[\s\S]*?<div class="list-empty" data-i18n="empty_history">No history yet\. Run your first analysis\.<\/div>/,
  'History panel should surface its empty state'
);

assert.match(
  indexHtml,
  /id="favList"[\s\S]*?<div class="list-empty" data-i18n="empty_favorites">No favorites saved yet\.<\/div>/,
  'Favorites panel should surface its empty state'
);
