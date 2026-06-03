import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

const __dirname = dirname(fileURLToPath(import.meta.url));
const UTILS_PATH = join(__dirname, '..', 'security-utils.js');

/** Load security-utils.js the same way the browser does (IIFE on global). */
export function loadSecurityUtils() {
  const code = readFileSync(UTILS_PATH, 'utf8');
  const context = vm.createContext({
    window: {},
    globalThis: {},
  });
  context.window = context;
  context.globalThis = context;
  vm.runInContext(code, context);
  return context.QyverixSecurity;
}

export const SCRIPT_TAG = "<script>alert('xss')</script>";

export const XSS_PAYLOADS = [
  SCRIPT_TAG,
  "<script>alert(String.fromCharCode(88,83,83))</script>",
  '<img src=x onerror="alert(1)">',
  "<img src=x onerror=alert('xss')>",
  '<svg/onload=alert(1)>',
  '<svg><script>alert(1)</script></svg>',
  "<body onload=alert('xss')>",
];

export const TEMPLATE_INJECTION_PAYLOADS = [
  '${alert(1)}',
  "{{constructor.constructor('alert(1)')()}}",
  '#{7*7}',
  'priority-high" onmouseover="alert(1)',
];

export const ENCODED_PAYLOADS = [
  "&lt;script&gt;alert('xss')&lt;/script&gt;",
  '&#60;script&#62;alert(1)&#60;/script&#62;',
  '<scr\x00ipt>alert(1)</scr\x00ipt>',
];

export const ALL_PAYLOADS = [
  ...XSS_PAYLOADS,
  ...TEMPLATE_INJECTION_PAYLOADS,
  ...ENCODED_PAYLOADS,
];

export const STORED_HISTORY_ATTACK = {
  id: "1');alert(1);//",
  code: "<script>alert('xss')</script>",
  preview: '<img src=x onerror="alert(1)">',
  lang: '<svg/onload=alert(1)>',
  ts: '${alert(1)}',
};

/**
 * Assert output is safe HTML: escaped payloads may contain the words
 * "onerror" / "onload" as text, but must not form active tags or handlers.
 */
export function assertPlainTextHtml(html, label = 'html') {
  if (html.includes('<script')) {
    throw new Error(`${label}: raw <script tag in HTML output`);
  }
  if (/<img\s/i.test(html)) {
    throw new Error(`${label}: raw <img tag in HTML output`);
  }
  if (/<svg[\s>/]/i.test(html)) {
    throw new Error(`${label}: raw <svg tag in HTML output`);
  }
  if (/<iframe/i.test(html)) {
    throw new Error(`${label}: raw <iframe tag in HTML output`);
  }
  if (/javascript:/i.test(html)) {
    throw new Error(`${label}: javascript: URI in HTML output`);
  }
  if (/<[a-z][\w-]*[^>]*\s+on\w+\s*=/i.test(html)) {
    throw new Error(`${label}: inline event handler on active HTML element`);
  }
}

export function assertEscapedPayload(html, payload) {
  const escaped = payload
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  if (payload.includes('<') && !html.includes('&lt;') && html.includes('<')) {
    throw new Error('Expected escaped angle brackets in HTML output');
  }
  if (payload.includes('<script') && html.toLowerCase().includes('<script')) {
    throw new Error('Raw <script> found in HTML — payload must be escaped');
  }
}
