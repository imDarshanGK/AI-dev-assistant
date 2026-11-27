import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const indexHtml = fs.readFileSync(path.resolve(__dirname, '..', 'index.html'), 'utf8');

const source = indexHtml.match(/function getDefaultApiBase\(location\) \{[\s\S]*?\n      \}/);
assert.ok(source, 'index.html should define getDefaultApiBase(location)');

const LOCAL = indexHtml.match(/const LOCAL_API_BASE = '([^']+)'/)[1];
const REMOTE = indexHtml.match(/const REMOTE_API_BASE = '([^']+)'/)[1];
const getDefaultApiBase = new Function(
  'LOCAL_API_BASE',
  'REMOTE_API_BASE',
  `${source[0]}; return getDefaultApiBase;`,
)(LOCAL, REMOTE);

const at = (url) => {
  const parsed = new URL(url);
  return { protocol: parsed.protocol, pathname: parsed.pathname, origin: parsed.origin };
};

// Served by the backend, which mounts the frontend at /app: use that backend.
assert.strictEqual(getDefaultApiBase(at('https://qyverixai.onrender.com/app/')), 'https://qyverixai.onrender.com');
assert.strictEqual(getDefaultApiBase(at('https://qyverixai.onrender.com/app')), 'https://qyverixai.onrender.com');
assert.strictEqual(getDefaultApiBase(at('https://code.example.org/app/index.html')), 'https://code.example.org');
assert.strictEqual(getDefaultApiBase(at('http://localhost:8000/app/')), 'http://localhost:8000');
assert.strictEqual(getDefaultApiBase(at('http://127.0.0.1:9000/app/')), 'http://127.0.0.1:9000');

// Opened from disk: there is no origin to call, so use the hosted API.
assert.strictEqual(getDefaultApiBase(at('file:///Users/dev/frontend/index.html')), REMOTE);

// Served by a separate dev server: the backend is expected on its usual port.
assert.strictEqual(getDefaultApiBase(at('http://localhost:5500/index.html')), LOCAL);
assert.strictEqual(getDefaultApiBase(at('http://localhost:5500/application/')), LOCAL);
assert.strictEqual(getDefaultApiBase(at('http://localhost:5500/frontend/app.html')), LOCAL);

assert.match(
  indexHtml,
  /return getDefaultApiBase\(window\.location\);/,
  'getApiBase should fall back to getDefaultApiBase when no API URL is configured',
);

console.log('api-base tests passed');
