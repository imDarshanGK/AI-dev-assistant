import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  ALL_PAYLOADS,
  ENCODED_PAYLOADS,
  STORED_HISTORY_ATTACK,
  TEMPLATE_INJECTION_PAYLOADS,
  XSS_PAYLOADS,
  assertEscapedPayload,
  assertPlainTextHtml,
  loadSecurityUtils,
} from './helpers.mjs';

const SEC = loadSecurityUtils();

describe('escHtml', () => {
  for (const payload of XSS_PAYLOADS) {
    it(`escapes script/img/svg payload: ${payload.slice(0, 40)}`, () => {
      const out = SEC.escHtml(payload);
      assertPlainTextHtml(out, 'escHtml output');
      assert.ok(!out.includes('<script'), 'script tag must not survive');
      if (payload.includes('<')) {
        assert.ok(out.includes('&lt;'), 'angle brackets must be escaped');
      }
    });
  }

  for (const payload of TEMPLATE_INJECTION_PAYLOADS) {
    it(`leaves template text escaped-safe: ${payload.slice(0, 40)}`, () => {
      const out = SEC.escHtml(payload);
      assertPlainTextHtml(out, 'escHtml template');
    });
  }

  for (const payload of ENCODED_PAYLOADS) {
    it(`handles encoded payload without decoding to HTML: ${payload.slice(0, 30)}`, () => {
      const out = SEC.escHtml(payload);
      assertPlainTextHtml(out, 'escHtml encoded');
    });
  }
});

describe('sanitizeClientCode', () => {
  it('strips null bytes and ANSI sequences', () => {
    const dirty = "a\x00b\x1b[31mc\x1b[0m";
    const clean = SEC.sanitizeClientCode(dirty);
    assert.equal(clean.includes('\x00'), false);
    assert.equal(clean.includes('\x1b'), false);
    assert.equal(clean, 'abc');
  });

  for (const payload of XSS_PAYLOADS) {
    it(`preserves code text for analysis: ${payload.slice(0, 30)}`, () => {
      const clean = SEC.sanitizeClientCode(payload);
      assert.ok(clean.includes('alert') || clean.includes('script') || clean.includes('svg'));
    });
  }
});

describe('safePriorityClass / safeSeverityClass / safeCssToken', () => {
  it('allowlists priority values', () => {
    assert.equal(SEC.safePriorityClass('high'), 'high');
    assert.equal(SEC.safePriorityClass('HIGH'), 'high');
    assert.equal(SEC.safePriorityClass('${alert(1)}'), 'medium');
    assert.equal(SEC.safePriorityClass('high" onmouseover="alert(1)'), 'medium');
  });

  it('allowlists severity values', () => {
    assert.equal(SEC.safeSeverityClass('error'), 'error');
    assert.equal(SEC.safeSeverityClass('<script>'), 'info');
  });

  it('allowlists CSS tokens', () => {
    assert.equal(SEC.safeCssToken('Moderate', 'simple'), 'Moderate');
    assert.equal(SEC.safeCssToken('<img onerror=alert(1)>', 'safe'), 'safe');
  });
});

describe('stored history normalization', () => {
  it('rejects string id injection payload', () => {
    const normalized = SEC.normalizeStoredEntry(STORED_HISTORY_ATTACK);
    assert.equal(normalized, null);
  });

  it('accepts valid numeric id entry', () => {
    const normalized = SEC.normalizeStoredEntry({
      id: Date.now(),
      code: 'def ok(): pass',
      preview: 'def ok',
      lang: 'Python',
      ts: '12:00',
    });
    assert.ok(normalized);
    assert.equal(typeof normalized.id, 'number');
  });

  it('loadStoredHistory drops poisoned entries from mock storage', () => {
    const storage = {
      data: {},
      getItem(key) {
        return this.data[key] ?? null;
      },
      setItem(key, value) {
        this.data[key] = value;
      },
    };
    storage.setItem(
      'qyx_history',
      JSON.stringify([STORED_HISTORY_ATTACK, { id: 42, code: 'x=1', preview: 'x=1', lang: 'Py', ts: 't' }]),
    );
    const list = SEC.loadStoredHistory('qyx_history', storage);
    assert.equal(list.length, 1);
    assert.equal(list[0].id, 42);
  });
});

describe('renderMarkdown', () => {
  for (const payload of XSS_PAYLOADS) {
    it(`does not emit executable HTML for: ${payload.slice(0, 35)}`, () => {
      const html = SEC.renderMarkdown(`**${payload}**`);
      assertPlainTextHtml(html, 'renderMarkdown');
    });
  }
});

describe('buildStoredListItemHtml', () => {
  it('renders stored attack preview as plain text only', () => {
    const entry = {
      id: 1001,
      lang: STORED_HISTORY_ATTACK.lang,
      ts: STORED_HISTORY_ATTACK.ts,
      preview: STORED_HISTORY_ATTACK.preview,
    };
    const html = SEC.buildStoredListItemHtml(entry);
    assertPlainTextHtml(html, 'history item');
    assert.ok(!html.includes('onclick='), 'no inline handlers');
    assert.ok(!html.includes("');alert"), 'no JS breakout in attributes');
    assertEscapedPayload(html, STORED_HISTORY_ATTACK.preview);
  });

  for (const payload of ALL_PAYLOADS) {
    it(`history HTML safe for payload in preview: ${payload.slice(0, 28)}`, () => {
      const html = SEC.buildStoredListItemHtml({
        id: 1,
        lang: 'Test',
        ts: 'now',
        preview: payload,
      });
      assertPlainTextHtml(html, 'history preview');
    });
  }
});

describe('buildIssueCardHtml / buildSuggestCardHtml', () => {
  it('escapes issue fields and safe severity class', () => {
    const html = SEC.buildIssueCardHtml({
      severity: 'error" onmouseover="alert(1)',
      type: '<script>alert(1)</script>',
      description: '<img src=x onerror=alert(1)>',
    });
    assertPlainTextHtml(html, 'issue card');
    assert.ok(html.includes('issue-card info') || html.includes('issue-card error'));
    assert.ok(!html.includes('onmouseover='));
  });

  it('escapes suggestion and safe priority class', () => {
    const html = SEC.buildSuggestCardHtml({
      priority: 'high"><script>alert(1)</script>',
      description: '${alert(1)}',
    });
    assertPlainTextHtml(html, 'suggest card');
    assert.ok(html.includes('priority-medium') || html.includes('priority-high'));
    assert.ok(!html.includes('<script>'));
  });
});

describe('normal code preserved', () => {
  const samples = [
    'def add(a, b):\n    return a + b\n',
    'if x < 10 and y > 0:\n    print("ok")\n',
    'const add = (a, b) => a + b;\n',
  ];

  for (const code of samples) {
    it(`sanitizeClientCode preserves: ${code.split('\n')[0]}`, () => {
      assert.equal(SEC.sanitizeClientCode(code), code);
    });
  }
});
