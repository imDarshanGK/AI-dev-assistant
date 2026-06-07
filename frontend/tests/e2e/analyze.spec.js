const { test, expect } = require('@playwright/test');
const { sampleFixturePath } = require('../helpers');

test('uploads a sample file and renders analysis results', async ({ page }) => {
  await page.goto('/app/');

  const editor = page.locator('#codeEditor').first();
  const fileInput = page.locator('#fileInput').first();
  const analyzeButton = page.locator('#analyzeBtn').first();

  await fileInput.setInputFiles(sampleFixturePath());
  await expect(editor).toHaveValue(/def add\(a, b\):/);

  await analyzeButton.click();

  const summary = page.locator('#explainResult .explain-summary');
  await expect(summary).toBeVisible();
  await expect(summary).toHaveText(
    'A short Python snippet (3 lines) that performs a focused task. Good starting point for learners.'
  );
});

test('drag-and-drop upload auto-selects the detected language tab', async ({ page }) => {
  await page.goto('/app/');

  const editor = page.locator('#codeEditor').first();
  const javaTab = page.locator('.lang-tab[data-lang="java"]').first();
  const activeTab = page.locator('.lang-tab.active').first();

  await javaTab.click();
  await expect(activeTab).toHaveAttribute('data-lang', 'java');

  const dataTransfer = await page.evaluateHandle(() => {
    const transfer = new DataTransfer();
    transfer.items.add(
      new File(['const answer: number = 42;\n'], 'sample.ts', {
        type: 'text/typescript',
      })
    );
    return transfer;
  });

  await page.locator('body').dispatchEvent('drop', { dataTransfer });

  await expect(editor).toHaveValue('const answer: number = 42;\n');
  await expect(activeTab).toHaveAttribute('data-lang', 'typescript');
});
