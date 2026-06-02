import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  ALL_PAYLOADS,
  SCRIPT_TAG,
  XSS_PAYLOADS,
  assertPlainTextHtml,
  loadSecurityUtils,
} from './helpers.mjs';
// SCRIPT_TAG: canonical <script>alert('xss')</script> payload for stored-history tests

const SEC = loadSecurityUtils();

/**
 * Simulates index.html renderExplain / renderDebug output assembly.
 */
function simulateAnalysisPanelHtml(apiResult) {
  const exp = apiResult.explanation;
  const dbg = apiResult.debugging;
  let html = '';

  if (exp) {
    html += `<div class="explain-summary">${SEC.escHtml(exp.summary)}</div>`;
    html += `<div class="meta-chip complexity-${SEC.safeCssToken(exp.complexity, 'unknown')}">`;
    html += `${SEC.escHtml(exp.complexity)}</div>`;
    html += '<ul>';
    for (const point of exp.key_points || []) {
      html += `<li>${SEC.renderMarkdown(point)}</li>`;
    }
    html += '</ul>';
  }

  if (dbg) {
    for (const issue of dbg.issues || []) {
      html += SEC.buildIssueCardHtml(issue);
    }
  }

  return html;
}

describe('simulated analysis panel rendering', () => {
  for (const payload of XSS_PAYLOADS) {
    it(`renders API-shaped xss payload as plain text: ${payload.slice(0, 32)}`, () => {
      const fakeApi = {
        explanation: {
          summary: payload,
          complexity: payload,
          key_points: [`**${payload}**`, `code: \`${payload}\``],
        },
        debugging: {
          issues: [
            {
              severity: 'error',
              type: payload,
              description: payload,
            },
          ],
        },
      };

      const html = simulateAnalysisPanelHtml(fakeApi);
      assertPlainTextHtml(html, 'analysis panel');
      assert.ok(!html.includes('<script>'), 'no raw script tags in DOM HTML');
    });
  }

  it('renders stored-execution-style history result without executable markup', () => {
    const poisonedResult = {
      explanation: {
        summary: "<script>alert('stored')</script>",
        complexity: 'high" onclick="alert(1)',
        key_points: ['<img src=x onerror=alert(1)>'],
      },
      debugging: {
        issues: [
          {
            severity: 'warning',
            type: '<svg/onload=alert(1)>',
            description: '${alert(1)}',
          },
        ],
      },
    };

    const panelHtml = simulateAnalysisPanelHtml(poisonedResult);
    assertPlainTextHtml(panelHtml, 'stored result panel');

    const historyHtml = SEC.buildHistoryItemHtml({
      id: 9001,
      lang: 'JavaScript',
      ts: '10:00:00',
      preview: SCRIPT_TAG,
    });
    assertPlainTextHtml(historyHtml, 'stored history');
  });
});

describe('innerHTML assignment safety (unit simulation)', () => {
  it('escaped HTML string does not match dangerous patterns when assigned', () => {
    const payload = "<script>alert('xss')</script>";
    const boxContent = `<div class="result-text">${SEC.escHtml(payload)}</div>`;
    assertPlainTextHtml(boxContent, 'outputBox simulation');
    assert.equal(boxContent.includes("<script>alert"), false);
    assert.ok(boxContent.includes('&lt;script'));
  });

  for (const payload of ALL_PAYLOADS) {
    it(`outputBox template safe: ${payload.slice(0, 25)}`, () => {
      const html = `<div>${SEC.escHtml(payload)}</div>`;
      assertPlainTextHtml(html, 'outputBox');
    });
  }
});
