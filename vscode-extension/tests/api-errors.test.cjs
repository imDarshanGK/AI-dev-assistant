const assert = require('node:assert/strict');
const http = require('node:http');
const Module = require('node:module');
const { test } = require('node:test');

const commands = new Map();
const messages = [];
const panels = [];
const logs = [];
const originalWarn = console.warn;
console.warn = (...args) => logs.push(args.join(' '));
require('node:test').after(() => { console.warn = originalWarn; });
let apiUrl;
let timeout = 1;
const vscode = {
  workspace: { getConfiguration: () => ({ get: (key, fallback) => ({ apiUrl, timeout })[key] ?? fallback }) },
  window: {
    activeTextEditor: { document: { getText: () => 'print(1)', languageId: 'python', fileName: 'example.py', uri: 'test:example' } },
    createWebviewPanel: () => { const panel = { webview: { html: '' } }; panels.push(panel); return panel; },
    showErrorMessage: message => messages.push(message),
    showWarningMessage: () => {},
    showInformationMessage: () => {},
  },
  ViewColumn: { Beside: 2 },
  languages: { createDiagnosticCollection: () => ({ set() {}, dispose() {} }) },
  commands: { registerCommand: (name, callback) => { commands.set(name, callback); return { dispose() {} }; } },
};
const originalLoad = Module._load;
Module._load = function (id, ...args) {
  return id === 'vscode' ? vscode : originalLoad.call(this, id, ...args);
};
try {
  require('../extension.js').activate({ subscriptions: [] });
} finally {
  Module._load = originalLoad;
}

async function serve(t, handler) {
  const server = http.createServer(handler);
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  apiUrl = `http://127.0.0.1:${server.address().port}`;
  timeout = 1;
  t.after(() => new Promise(resolve => {
    server.close(resolve);
    server.closeAllConnections();
  }));
  return server;
}

const sentinel = 'PRIVATE_RESPONSE_SENTINEL';
for (const command of ['analyze', 'debug', 'explain', 'suggest']) {
  test(`${command} never displays server error bodies`, async t => {
    await serve(t, (_, res) => { res.writeHead(503); res.end(sentinel); });
    await commands.get(`qyverixai.${command}`)();
    assert.doesNotMatch(messages.at(-1), new RegExp(sentinel));
    assert.doesNotMatch(panels.at(-1).webview.html, new RegExp(sentinel));
    assert.match(messages.at(-1), /503/);
    assert.match(logs.at(-1), /http.*503/);
    assert.doesNotMatch(logs.at(-1), new RegExp(sentinel));
  });
}

test('invalid JSON does not expose response contents', async t => {
  await serve(t, (_, res) => res.end(sentinel));
  await commands.get('qyverixai.explain')();
  assert.doesNotMatch(messages.at(-1), new RegExp(sentinel));
  assert.match(messages.at(-1), /invalid response/i);
});

for (const status of [400, 401, 403, 404, 429, 500, 502]) {
  test(`HTTP ${status} reports only the status, not upstream details`, async t => {
    await serve(t, (_, res) => { res.writeHead(status); res.end(JSON.stringify({ detail: sentinel })); });
    await commands.get('qyverixai.explain')();
    assert.match(messages.at(-1), new RegExp(`HTTP ${status}`));
    assert.doesNotMatch(messages.at(-1), new RegExp(sentinel));
  });
}

for (const body of ['null', '[]', '42', '"unexpected"', '{}']) {
  test(`unexpected response shape ${body} has a stable error`, async t => {
    await serve(t, (_, res) => res.end(body));
    await commands.get('qyverixai.explain')();
    assert.match(messages.at(-1), /invalid response/i);
    assert.doesNotMatch(messages.at(-1), /TypeError|Cannot read/);
  });
}

test('connection reset has a stable error', async t => {
  await serve(t, req => req.socket.destroy());
  await commands.get('qyverixai.explain')();
  assert.match(messages.at(-1), /Could not connect/);
  assert.doesNotMatch(messages.at(-1), /ECONNRESET|socket hang up|127\.0\.0\.1/);
});

test('a truncated response rejects instead of leaving the command pending', { timeout: 2000 }, async t => {
  await serve(t, (_, res) => {
    res.writeHead(200, { 'Content-Length': 1000 });
    res.write('{');
    setTimeout(() => res.destroy(), 10);
  });
  await commands.get('qyverixai.explain')();
  assert.match(messages.at(-1), /Could not connect/);
});

test('a stalled request reaches its deadline', { timeout: 2000 }, async t => {
  await serve(t, () => {});
  timeout = 0.05;
  await commands.get('qyverixai.explain')();
  assert.match(messages.at(-1), /timed out/);
});

test('response activity cannot postpone the request deadline indefinitely', { timeout: 2000 }, async t => {
  await serve(t, (_, res) => {
    res.writeHead(200);
    res.write('{');
    const timer = setInterval(() => res.write(' '), 10);
    res.on('close', () => clearInterval(timer));
  });
  timeout = 0.05;
  await commands.get('qyverixai.explain')();
  assert.match(messages.at(-1), /timed out/);
});

for (const invalidUrl of ['not-a-url', 'ftp://localhost', `http://user:${sentinel}@localhost`]) {
  test('invalid URL configuration does not expose its value', async () => {
    apiUrl = invalidUrl;
    await commands.get('qyverixai.explain')();
    assert.match(messages.at(-1), /Settings/);
    assert.doesNotMatch(messages.at(-1), new RegExp(sentinel));
  });
}

for (const invalidTimeout of [0, -1, Infinity, NaN, 2147484]) {
  test(`invalid timeout ${invalidTimeout} is rejected`, async t => {
    await serve(t, (_, res) => res.end('{}'));
    timeout = invalidTimeout;
    await commands.get('qyverixai.explain')();
    assert.match(messages.at(-1), /Settings/);
  });
}

test('successful requests preserve payloads and split UTF-8 response characters', async t => {
  const explanation = {
    language: 'python', summary: 'Résumé: café', key_points: ['Prints a number'],
    complexity: 'O(1)', line_count: 1, function_count: 0, class_count: 0,
  };
  let received;
  await serve(t, (req, res) => {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      received = JSON.parse(body);
      const bytes = Buffer.from(JSON.stringify(explanation));
      const split = bytes.indexOf(Buffer.from('é')) + 1;
      res.write(bytes.subarray(0, split));
      setImmediate(() => res.end(bytes.subarray(split)));
    });
  });
  const errorCount = messages.length;
  await commands.get('qyverixai.explain')();
  assert.equal(messages.length, errorCount);
  assert.deepEqual(received, { code: 'print(1)', language: 'python' });
  assert.match(panels.at(-1).webview.html, /Résumé: café/);
});
