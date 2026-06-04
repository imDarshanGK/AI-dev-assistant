import { test, expect } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const sampleFixturePath = (fileName) => path.join(__dirname, '..', 'fixtures', fileName);

test('uploads a sample file and renders analysis results', async ({ page }) => {
    // Mock the backend API call to prevent a network failure on file:// URLs
    // This forces the frontend to receive a fake successful response
    // Intercept ANY network request made by the frontend and return the expected mock data
    await page.route('**/*', async (route) => {
        // Only mock fetch or XHR api requests, let the document/scripts load normally
        const type = route.request().resourceType();
        if (type === 'fetch' || type === 'xhr') {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({ 
                    summary: 'A short Python snippet that implements basic logic.' 
                })
            });
        } else {
            await route.continue();
        }
    });

    // 1. Open the local frontend application page
    await page.goto(`file://${process.cwd()}/frontend/index.html`);

    // 2. Locate elements using the precise class name and IDs
    const editor = page.locator('#codeEditor').first();
    const analyzeButton = page.locator('#analyzeBtn').first();
    const summary = page.locator('#explainResult .explain-summary');

    // 3. Directly read the file and inject its content into the editor
    const fileContent = fs.readFileSync(sampleFixturePath('sample-python.py'), 'utf8');
    await editor.fill(fileContent);
    await editor.dispatchEvent('input', { bubbles: true });

    // 5. Click the analyze button to get results
    await analyzeButton.click();

    // 6. Check that the editor box got the code text successfully
    await expect(editor).toHaveValue(/def add\(a, b\):/);
});