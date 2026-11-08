import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const A11Y_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];

// The hero and panel sections play one-shot CSS entrance animations (fade/scale-in) on
// load. Scanning mid-animation makes axe see transiently-blended, low-opacity colors and
// report false-positive contrast violations, so let finite animations settle first.
async function waitForEntranceAnimations(page) {
  await page.evaluate(() =>
    Promise.all(
      document
        .getAnimations()
        .filter((a) => a.effect?.getTiming().iterations !== Infinity)
        .map((a) => a.finished.catch(() => {}))
    )
  );
}

test.describe('accessibility', () => {
  test('main editor view has no detectable a11y violations', async ({ page }) => {
    await page.goto('/app/');
    await waitForEntranceAnimations(page);

    const results = await new AxeBuilder({ page }).withTags(A11Y_TAGS).analyze();

    expect(results.violations, formatViolations(results.violations)).toEqual([]);
  });

  test('debug and suggest result tabs have no detectable a11y violations', async ({ page }) => {
    await page.goto('/app/');
    await waitForEntranceAnimations(page);

    for (const tabId of ['tab-debug', 'tab-suggest']) {
      await page.locator(`#${tabId}`).click();

      const results = await new AxeBuilder({ page }).withTags(A11Y_TAGS).analyze();

      expect(results.violations, formatViolations(results.violations)).toEqual([]);
    }
  });

  test('history panel has no detectable a11y violations', async ({ page }) => {
    await page.route('**/history/**', (route) => route.abort());
    await page.goto('/app/');
    await waitForEntranceAnimations(page);

    const results = await new AxeBuilder({ page })
      .include('#historyList')
      .include('#favList')
      .withTags(A11Y_TAGS)
      .analyze();

    expect(results.violations, formatViolations(results.violations)).toEqual([]);
  });

  test('interactive controls are reachable via keyboard tab order', async ({ page }) => {
    await page.goto('/app/');

    const languageSelect = page.locator('#langSelect');
    await page.locator('body').click();
    await languageSelect.focus();
    await expect(languageSelect).toBeFocused();

    const editor = page.locator('#codeEditor');
    await editor.focus();
    await expect(editor).toBeFocused();

    const analyzeButton = page.locator('#analyzeBtn');
    await analyzeButton.focus();
    await expect(analyzeButton).toBeFocused();
  });
});

function formatViolations(violations) {
  if (violations.length === 0) return '';

  return violations
    .map((violation) => {
      const nodes = violation.nodes.map((node) => `    - ${node.target.join(' ')}`).join('\n');
      return `[${violation.impact}] ${violation.id}: ${violation.help}\n${nodes}`;
    })
    .join('\n');
}
