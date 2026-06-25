import assert from 'assert';
import fs from 'fs';
import path from 'path';

const indexHtml = fs.readFileSync(new URL('../index.html', import.meta.url).pathname, 'utf8');
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
