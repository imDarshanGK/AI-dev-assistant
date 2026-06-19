import { test, expect } from '@playwright/test';
import { sampleFixturePath } from '../helpers.js';

test('uploads a sample file and renders analysis results', async ({ page }) => {
  await page.goto('/app/');

  await page.route('**/analyze/', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        explanation: {
          language: 'Python',
          summary:
            'A short Python snippet (3 lines) that performs a focused task. Good starting point for learners.',
          key_points: [],
        },
        debugging: {
          issues: [],
        },
      }),
    });
  });

  const editor = page.locator('#codeEditor').first();
  const fileInput = page.locator('#fileInput').first();
  const analyzeButton = page.locator('#analyzeBtn').first();

  await fileInput.setInputFiles(sampleFixturePath());
  await expect(editor).toHaveValue(/def add\(a, b\):/);

  await analyzeButton.click();

  await expect(
    page.locator('.explain-summary')
  ).toContainText('A short Python snippet');  await expect(
    
    page.locator(
      'text=A short Python snippet (3 lines) that performs a focused task. Good starting point for learners.'
    )
  ).toBeVisible();
});


test.skip('drag-and-drop upload auto-selects the detected language tab', async ({ page }) => {
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

  await editor.dispatchEvent('drop', { dataTransfer });

await expect(editor).toHaveValue(/const answer/);
await expect(activeTab).toHaveAttribute('data-lang', 'typescript');
});
