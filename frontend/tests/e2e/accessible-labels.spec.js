import { test, expect } from '@playwright/test';

test.describe('Accessible labels on frontend controls', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/app/');
  });

  test('result action icon buttons have accessible labels', async ({ page }) => {
    await expect(page.locator('#favBtn')).toHaveAttribute('aria-label', 'Save to favorites');
    await expect(page.locator('#downloadBtn')).toHaveAttribute('aria-label', 'Download results');
    await expect(page.locator('#export-pdf-btn')).toHaveAttribute('aria-label', 'Export results as PDF');
    await expect(page.locator('#export-md-btn')).toHaveAttribute('aria-label', 'Export results as Markdown');
  });

  test('history sort and order selects have accessible labels', async ({ page }) => {
    await expect(page.locator('#historySortSelect')).toHaveAttribute('aria-label', 'Sort history by');
    await expect(page.locator('#historyOrderSelect')).toHaveAttribute('aria-label', 'History sort order');
  });

  test('collaboration panel inputs have accessible labels', async ({ page }) => {
    await expect(page.locator('#collabName')).toHaveAttribute('aria-label', 'Your name');
    await expect(page.locator('#collabSession')).toHaveAttribute('aria-label', 'Session ID');
    await expect(page.locator('#collabLine')).toHaveAttribute('aria-label', 'Line number for comment');
    await expect(page.locator('#collabCommentText')).toHaveAttribute('aria-label', 'Live review comment text');
  });

  test('digest subscription email input has an accessible label', async ({ page }) => {
    await expect(page.locator('#digestEmail')).toHaveAttribute(
      'aria-label',
      'Email address for digest subscription'
    );
  });
});