const { defineConfig } = require('@playwright/test');
const path = require('path');

const BASE_URL = 'http://127.0.0.1:8000';

module.exports = defineConfig({
  testDir: './tests/e2e',
  timeout: 60000,
  expect: {
    timeout: 10000,
  },
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI
    ? [['list'], ['html', { open: 'never' }]]
    : [['list']],
  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    viewport: { width: 1440, height: 1080 },
  },
  webServer: {
    command: 'python -m uvicorn app.main:app --host 127.0.0.1 --port 8000',
    cwd: path.resolve(__dirname, '..', 'backend'),
    url: `${BASE_URL}/health`,
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
    env: {
      RATE_LIMIT_PER_MINUTE: '1000',
    },
  },
});