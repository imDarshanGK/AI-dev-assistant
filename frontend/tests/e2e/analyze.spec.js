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