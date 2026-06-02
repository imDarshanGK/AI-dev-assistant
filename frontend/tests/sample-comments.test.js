import fs from 'fs';
import path from 'path';
import assert from 'assert';

const filePath = path.resolve(
  process.cwd(),
  'tests/sample-comments.test.js'
);

assert.ok(fs.existsSync(filePath), 'Test file exists');

console.log('Static test passed ✔');