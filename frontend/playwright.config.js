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
  baseURL: 'http://localhost:3000',
  headless: true,
}
});