import fs from 'fs';
import path from 'path';
import assert from 'assert';

const filePath = path.resolve(
  process.cwd(),
  'tests/sample-comments.test.js'
);
import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const indexHtml = fs.readFileSync(path.resolve(__dirname, '..', 'index.html'), 'utf8');

assert.ok(fs.existsSync(filePath), 'Test file exists');

console.log('Static test passed ✔');