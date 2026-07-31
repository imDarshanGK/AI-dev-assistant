import { test, expect } from '@playwright/test';

test('shows pagination controls and allows navigating history pages', async ({ page }) => {
  // Intercept history API calls to force fallback to local storage
  await page.route('**/history/**', route => route.abort());

  await page.goto('/app/');

  // Inject 7 mock history items into localStorage
  await page.evaluate(() => {
    const mockHistory = [];
    for (let i = 1; i <= 7; i++) {
      mockHistory.push({
        id: 1000 + i,
        code: `console.log("Mock item ${i}");`,
        result: {
          explanation: { language: 'JavaScript', summary: `Mock item summary ${i}` },
          debugging: { issues: [] },
          suggestions: { overall_score: 95 }
        },
        lang: 'JavaScript',
        ts: `10:00:0${i}`,
        preview: `console.log("Mock item ${i}");`
      });
    }
    localStorage.setItem('qyx_history', JSON.stringify(mockHistory));
  });

  // Reload page to pick up the injected history
  await page.reload();

  // Verify pagination block is visible
  const pagination = page.locator('#historyPagination');
  await expect(pagination).toBeVisible();

  // Verify there are 5 items shown on page 1
  const items = page.locator('#historyList .history-item');
  await expect(items).toHaveCount(5);

  // Verify page number text is "Page 1 of 2"
  const pageNum = page.locator('#historyPageNum');
  await expect(pageNum).toHaveText('Page 1 of 2');

  // Verify "Previous" is disabled and "Next" is enabled
  const prevBtn = page.locator('#btnPrevHistory');
  const nextBtn = page.locator('#btnNextHistory');
  await expect(prevBtn).toBeDisabled();
  await expect(nextBtn).toBeEnabled();

  // Click Next Page
  await nextBtn.click();

  // Verify we are on page 2
  await expect(pageNum).toHaveText('Page 2 of 2');
  await expect(items).toHaveCount(2); // Remaining 2 items
  await expect(prevBtn).toBeEnabled();
  await expect(nextBtn).toBeDisabled();

  // Click Previous Page
  await prevBtn.click();
  await expect(pageNum).toHaveText('Page 1 of 2');
  await expect(items).toHaveCount(5);
  await expect(prevBtn).toBeDisabled();
  await expect(nextBtn).toBeEnabled();
});
