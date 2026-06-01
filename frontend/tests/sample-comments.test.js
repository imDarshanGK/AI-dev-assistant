const assert = require('assert');
const fs = require('fs');
const path = require('path');

const indexHtml = fs.readFileSync(path.resolve(__dirname, '..', 'index.html'), 'utf8');

const expectedHeaders = {
  python: '# Python Sample',
  javascript: '// JavaScript Sample',
  typescript: '// TypeScript Sample',
  java: '// Java Sample',
  cpp: '// C++ Sample',
};

for (const [language, expectedHeader] of Object.entries(expectedHeaders)) {
  const match = indexHtml.match(new RegExp(`${language}: \`([^\\n]+)`));

  assert.ok(match, `Missing ${language} sample`);
  assert.strictEqual(match[1].trimEnd(), expectedHeader, `${language} sample should start with ${expectedHeader}`);
}

assert.ok(!indexHtml.includes('python: `// Python Sample'), 'Python sample must not use JavaScript comment syntax');
