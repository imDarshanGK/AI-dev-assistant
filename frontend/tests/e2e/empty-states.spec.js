import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.clear();
  });
});

test('surfaces result empty states before any analysis', async ({ page }) => {
  await page.goto('/app/');

  const emptyExplain = page.locator('#emptyExplain');
  await expect(emptyExplain).toBeVisible();
  await expect(emptyExplain.locator('.empty-title')).toHaveText('No analysis yet');
  await expect(page.locator('#explainResult')).toBeHidden();

  await page.locator('#tab-debug').click();
  const emptyDebug = page.locator('#emptyDebug');
  await expect(emptyDebug).toBeVisible();
  await expect(emptyDebug.locator('.empty-title')).toHaveText('No bugs scanned');
  await expect(page.locator('#debugResult')).toBeHidden();

  await page.locator('#tab-suggest').click();
  const emptySuggest = page.locator('#emptySuggest');
  await expect(emptySuggest).toBeVisible();
  await expect(emptySuggest.locator('.empty-title')).toHaveText('No suggestions yet');
  await expect(page.locator('#suggestResult')).toBeHidden();
});

test('surfaces history and favorites empty states with no saved data', async ({ page }) => {
  await page.route('**/history/**', (route) => route.abort());
  await page.goto('/app/');

  await expect(page.locator('#historyList .list-empty')).toBeVisible();
  await expect(page.locator('#historyList .list-empty')).toHaveText(
    'No history yet. Run your first analysis.'
  );

  await expect(page.locator('#favList .list-empty')).toBeVisible();
  await expect(page.locator('#favList .list-empty')).toHaveText('No favorites saved yet.');
});
