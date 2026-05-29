const { test, expect } = require('@playwright/test');

test('keeps editor viewport stable for long uploaded files', async ({ page }) => {
  await page.goto('/app/');

  const fileInput = page.locator('#fileInput').first();
  const editor = page.locator('#codeEditor').first();

  const longCode = Array.from(
    { length: 1200 },
    (_, i) => `print("line ${i + 1}")`
  ).join('\n');

  await fileInput.setInputFiles({
    name: 'long-upload.py',
    mimeType: 'text/x-python',
    buffer: Buffer.from(longCode, 'utf-8'),
  });

  await expect(editor).toHaveValue(/line 1200/);

  const before = await page.evaluate(() => {
    const editorEl = document.getElementById('codeEditor');
    const lineNumbersEl = document.getElementById('lineNumbers');
    const wrapEl = document.querySelector('.editor-wrap');
    const wrapRect = wrapEl.getBoundingClientRect();
    const editorRect = editorEl.getBoundingClientRect();
    return {
      wrapHeight: wrapRect.height,
      editorHeight: editorRect.height,
      lineNumbersHeight: lineNumbersEl.clientHeight,
      lineNumbersScrollHeight: lineNumbersEl.scrollHeight,
      lineNumbersText: lineNumbersEl.textContent || '',
    };
  });

  expect(Math.abs(before.wrapHeight - before.editorHeight)).toBeLessThan(4);
  expect(Math.abs(before.lineNumbersHeight - before.editorHeight)).toBeLessThan(4);
  expect(before.lineNumbersScrollHeight).toBeGreaterThan(before.lineNumbersHeight);
  expect(before.lineNumbersText).toContain('1200');

  await editor.evaluate((el) => {
    el.scrollTop = el.scrollHeight;
    el.dispatchEvent(new Event('scroll'));
  });

  const afterScrollTop = await page.evaluate(() => {
    const lineNumbersEl = document.getElementById('lineNumbers');
    return lineNumbersEl.scrollTop;
  });

  expect(afterScrollTop).toBeGreaterThan(0);
});
