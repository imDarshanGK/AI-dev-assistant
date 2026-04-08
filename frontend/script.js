const form = document.getElementById('assistant-form');
const codeInput = document.getElementById('code-input');
const actionInput = document.getElementById('action');
const apiBaseInput = document.getElementById('api-base');
const resultBox = document.getElementById('result');
const statusBox = document.getElementById('status');
const clearBtn = document.getElementById('clear-btn');
const codeFileInput = document.getElementById('code-file');
const copyBtn = document.getElementById('copy-btn');
const historyList = document.getElementById('history-list');
const clearHistoryBtn = document.getElementById('clear-history-btn');
const themeToggleBtn = document.getElementById('theme-toggle');

const HISTORY_KEY = 'ai-assistant-history';
const THEME_KEY = 'ai-assistant-theme';
const HISTORY_LIMIT = 10;

const savedApiBase = window.localStorage.getItem('ai-assistant-api-base');
if (savedApiBase) {
    apiBaseInput.value = savedApiBase;
}

apiBaseInput.addEventListener('change', () => {
    window.localStorage.setItem('ai-assistant-api-base', apiBaseInput.value.trim());
});

function setStatus(message, isError = false) {
    statusBox.textContent = message;
    statusBox.classList.toggle('error', isError);
    statusBox.classList.remove('loading');
}

function setLoadingStatus(message) {
    statusBox.textContent = message;
    statusBox.classList.remove('error');
    statusBox.classList.add('loading');
}

function buildEndpoint(action) {
    if (action === 'explanation') return '/explanation/';
    if (action === 'debugging') return '/debugging/';
    if (action === 'analyze') return '/analyze/';
    return '/suggestions/';
}

function getHistoryItems() {
    const raw = window.localStorage.getItem(HISTORY_KEY);
    if (!raw) {
        return [];
    }

    try {
        return JSON.parse(raw);
    } catch (error) {
        return [];
    }
}

function saveHistoryItems(items) {
    window.localStorage.setItem(HISTORY_KEY, JSON.stringify(items));
}

function renderHistory() {
    const items = getHistoryItems();
    historyList.innerHTML = '';

    if (items.length === 0) {
        const empty = document.createElement('li');
        empty.textContent = 'No previous queries yet.';
        historyList.appendChild(empty);
        return;
    }

    items.forEach((item) => {
        const li = document.createElement('li');
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'history-item-btn';
        button.innerHTML = `${item.action.toUpperCase()}: ${item.preview}<small>${item.timestamp}</small>`;

        button.addEventListener('click', () => {
            codeInput.value = item.code;
            actionInput.value = item.action;
            setStatus('Loaded query from history.');
        });

        li.appendChild(button);
        historyList.appendChild(li);
    });
}

function pushHistoryEntry(code, action) {
    const now = new Date();
    const entry = {
        code,
        action,
        preview: code.slice(0, 80).replace(/\n/g, ' '),
        timestamp: now.toLocaleString(),
    };

    const items = getHistoryItems();
    items.unshift(entry);
    const boundedItems = items.slice(0, HISTORY_LIMIT);
    saveHistoryItems(boundedItems);
    renderHistory();
}

function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    themeToggleBtn.textContent = theme === 'dark' ? 'Light mode' : 'Dark mode';
    window.localStorage.setItem(THEME_KEY, theme);
}

function detectActionFromFilename(filename) {
    const lower = filename.toLowerCase();
    if (lower.endsWith('.py') || lower.endsWith('.java') || lower.endsWith('.js')) {
        return 'analyze';
    }

    return actionInput.value;
}

const savedTheme = window.localStorage.getItem(THEME_KEY) || 'light';
applyTheme(savedTheme);
renderHistory();

form.addEventListener('submit', async (event) => {
    event.preventDefault();

    const code = codeInput.value.trim();
    if (!code) {
        setStatus('Please enter code before submitting.', true);
        resultBox.textContent = 'No code submitted.';
        return;
    }

    const action = actionInput.value;
    const endpoint = buildEndpoint(action);
    const apiBase = apiBaseInput.value.trim().replace(/\/$/, '');

    window.localStorage.setItem('ai-assistant-api-base', apiBase);

    setLoadingStatus('Running request...');
    resultBox.textContent = 'Loading...';

    try {
        const response = await fetch(apiBase + endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code }),
        });

        const data = await response.json();
        if (!response.ok) {
            setStatus('Request failed. Check input or backend logs.', true);
            resultBox.textContent = JSON.stringify(data, null, 2);
            return;
        }

        setStatus('Success');
        resultBox.textContent = JSON.stringify(data, null, 2);
        pushHistoryEntry(code, action);
    } catch (error) {
        setStatus('Could not connect to backend API.', true);
        resultBox.textContent = String(error);
    }
});

clearBtn.addEventListener('click', () => {
    codeInput.value = '';
    resultBox.textContent = 'Your result will appear here.';
    setStatus('Ready');
});

copyBtn.addEventListener('click', async () => {
    const text = resultBox.textContent.trim();
    if (!text || text === 'Your result will appear here.') {
        setStatus('No result available to copy.', true);
        return;
    }

    try {
        await navigator.clipboard.writeText(text);
        setStatus('Result copied to clipboard.');
    } catch (error) {
        setStatus('Failed to copy result.', true);
    }
});

codeFileInput.addEventListener('change', async (event) => {
    const file = event.target.files && event.target.files[0];
    if (!file) {
        return;
    }

    try {
        const content = await file.text();
        codeInput.value = content;
        actionInput.value = detectActionFromFilename(file.name);
        setStatus(`Loaded file: ${file.name}`);
    } catch (error) {
        setStatus('Failed to read selected file.', true);
    }
});

clearHistoryBtn.addEventListener('click', () => {
    saveHistoryItems([]);
    renderHistory();
    setStatus('History cleared.');
});

themeToggleBtn.addEventListener('click', () => {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    applyTheme(current === 'light' ? 'dark' : 'light');
});