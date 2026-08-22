import { test, expect } from '@playwright/test';
import { sampleFixturePath } from '../helpers.js';

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

  await page.locator('.editor-wrap').dispatchEvent('drop', { dataTransfer });

  await expect(editor).toHaveValue('const answer: number = 42;\n');
  await expect(activeTab).toHaveAttribute('data-lang', 'typescript');
});
test('unsupported file type shows supported extensions guidance', async ({ page }) => {
  await page.goto('/app/');

  const fileInput = page.locator('#fileInput').first();

  await fileInput.setInputFiles({
    name: 'sample.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('%PDF-1.4'),
  });

  const toast = page.locator('#toastContainer .toast.error').last();

  await expect(toast).toBeVisible();
  await expect(toast).toContainText('Unsupported file type');
  await expect(toast).toContainText('.py');
  await expect(toast).toContainText('.js');
  const editor = page.locator('#codeEditor').first();
  await expect(editor).not.toHaveValue(/sample\.pdf/);
});
