const form = document.getElementById('assistant-form');
const codeInput = document.getElementById('code-input');
const actionInput = document.getElementById('action');
const apiBaseInput = document.getElementById('api-base');
const authEmailInput = document.getElementById('auth-email');
const authPasswordInput = document.getElementById('auth-password');
const signupBtn = document.getElementById('signup-btn');
const loginBtn = document.getElementById('login-btn');
const logoutBtn = document.getElementById('logout-btn');
const authStatus = document.getElementById('auth-status');
const resultBox = document.getElementById('result');
const statusBox = document.getElementById('status');
const clearBtn = document.getElementById('clear-btn');
const codeFileInput = document.getElementById('code-file');
const favoriteBtn = document.getElementById('favorite-btn');
const shareBtn = document.getElementById('share-btn');
const downloadBtn = document.getElementById('download-btn');
const copyBtn = document.getElementById('copy-btn');
const historyList = document.getElementById('history-list');
const favoritesList = document.getElementById('favorites-list');
const clearHistoryBtn = document.getElementById('clear-history-btn');
const clearFavoritesBtn = document.getElementById('clear-favorites-btn');
const themeToggleBtn = document.getElementById('theme-toggle');
const languageSelect = document.getElementById('language-select');
const detectedLanguageText = document.getElementById('detected-language');
const dropzone = document.getElementById('code-dropzone');
const historyCount = document.getElementById('history-count');
const favoritesCount = document.getElementById('favorites-count');
const apiModeLabel = document.getElementById('api-mode-label');

const HISTORY_KEY = 'ai-assistant-history';
const FAVORITES_KEY = 'ai-assistant-favorites';
const THEME_KEY = 'ai-assistant-theme';
const TOKEN_KEY = 'ai-assistant-access-token';
const USER_EMAIL_KEY = 'ai-assistant-user-email';
const HISTORY_LIMIT = 10;

const savedApiBase = window.localStorage.getItem('ai-assistant-api-base');
if (savedApiBase) {
    apiBaseInput.value = savedApiBase;
} else {
    apiBaseInput.value = window.location.origin;
}

apiBaseInput.addEventListener('change', () => {
    window.localStorage.setItem('ai-assistant-api-base', apiBaseInput.value.trim());
});

function setStatus(message, isError = false) {
    statusBox.textContent = message;
    statusBox.classList.toggle('error', isError);
    statusBox.classList.remove('loading');
}

function getApiBase() {
    return apiBaseInput.value.trim().replace(/\/$/, '');
}

function getAuthToken() {
    return window.localStorage.getItem(TOKEN_KEY) || '';
}

function getCurrentUserEmail() {
    return window.localStorage.getItem(USER_EMAIL_KEY) || '';
}

function updateAuthStatus() {
    const email = getCurrentUserEmail();
    authStatus.textContent = email ? `Logged in as ${email}` : 'Not logged in';
}

function clearAuthSession() {
    window.localStorage.removeItem(TOKEN_KEY);
    window.localStorage.removeItem(USER_EMAIL_KEY);
    updateAuthStatus();
}

function buildAuthHeaders() {
    const token = getAuthToken();
    if (!token) {
        return {};
    }

    return { Authorization: `Bearer ${token}` };
}

async function fetchWithAuth(path, options = {}) {
    const response = await fetch(getApiBase() + path, {
        ...options,
        headers: {
            ...(options.headers || {}),
            ...buildAuthHeaders(),
        },
    });

    if (response.status === 401) {
        clearAuthSession();
        setStatus('Session expired. Please log in again.', true);
    }

    return response;
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

async function loadServerHistory() {
    const token = getAuthToken();
    if (!token) {
        return false;
    }

    const response = await fetchWithAuth('/user/history');

    if (!response.ok) {
        return false;
    }

    const items = await response.json();
    saveHistoryItems(
        items.map((item) => ({
            id: item.id,
            code: item.code,
            action: item.action,
            preview: item.code.slice(0, 80).replace(/\n/g, ' '),
            timestamp: new Date(item.created_at).toLocaleString(),
        }))
    );
    renderHistory();
    return true;
}

function getFavoriteItems() {
    const raw = window.localStorage.getItem(FAVORITES_KEY);
    if (!raw) {
        return [];
    }

    try {
        return JSON.parse(raw);
    } catch (error) {
        return [];
    }
}

function saveFavoriteItems(items) {
    window.localStorage.setItem(FAVORITES_KEY, JSON.stringify(items));
}

async function loadServerFavorites() {
    const token = getAuthToken();
    if (!token) {
        return false;
    }

    const response = await fetchWithAuth('/user/favorites');

    if (!response.ok) {
        return false;
    }

    const items = await response.json();
    saveFavoriteItems(
        items.map((item) => ({
            id: item.id,
            fingerprint: `${item.action}:${item.code.slice(0, 120)}:${item.result_json.slice(0, 120)}`,
            code: item.code,
            action: item.action,
            result: item.result_json,
            title: item.title,
            timestamp: new Date(item.created_at).toLocaleString(),
        }))
    );
    renderFavorites();
    return true;
}

function renderHistory() {
    const items = getHistoryItems();
    historyList.innerHTML = '';

    if (items.length === 0) {
        const empty = document.createElement('li');
        empty.textContent = 'No previous queries yet.';
        historyList.appendChild(empty);
        historyCount.textContent = '0';
        return;
    }

    items.forEach((item, index) => {
        const li = document.createElement('li');
        const row = document.createElement('div');
        row.className = 'history-item-row';
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'history-item-btn';
        button.innerHTML = `${item.action.toUpperCase()}: ${item.preview}<small>${item.timestamp}</small>`;

        button.addEventListener('click', () => {
            codeInput.value = item.code;
            actionInput.value = item.action;
            setStatus('Loaded query from history.');
        });

        const deleteBtn = document.createElement('button');
        deleteBtn.type = 'button';
        deleteBtn.className = 'item-danger-btn';
        deleteBtn.textContent = 'Delete';
        deleteBtn.addEventListener('click', async () => {
            await deleteHistoryEntry(index);
        });

        row.appendChild(button);
        row.appendChild(deleteBtn);
        li.appendChild(row);
        historyList.appendChild(li);
    });

    historyCount.textContent = String(items.length);
}

function renderFavorites() {
    const items = getFavoriteItems();
    favoritesList.innerHTML = '';

    if (items.length === 0) {
        const empty = document.createElement('li');
        empty.textContent = 'No saved favorite results yet.';
        favoritesList.appendChild(empty);
        favoritesCount.textContent = '0';
        return;
    }

    items.forEach((item, index) => {
        const li = document.createElement('li');
        const row = document.createElement('div');
        row.className = 'history-item-row';
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'history-item-btn';
        button.innerHTML = `${item.title}<small>${item.timestamp}</small>`;

        button.addEventListener('click', () => {
            codeInput.value = item.code;
            actionInput.value = item.action;
            resultBox.textContent = item.result;
            setStatus('Loaded favorite result.');
            updateDetectedLanguage();
        });

        const deleteBtn = document.createElement('button');
        deleteBtn.type = 'button';
        deleteBtn.className = 'item-danger-btn';
        deleteBtn.textContent = 'Delete';
        deleteBtn.addEventListener('click', async () => {
            await deleteFavoriteEntry(index);
        });

        row.appendChild(button);
        row.appendChild(deleteBtn);
        li.appendChild(row);
        favoritesList.appendChild(li);
    });

    favoritesCount.textContent = String(items.length);
}

async function pushHistoryEntry(code, action) {
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

    const token = getAuthToken();
    if (token) {
        const response = await fetchWithAuth('/user/history', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                action,
                code,
                result_json: resultBox.textContent,
            }),
        });

        if (response.ok) {
            const created = await response.json();
            const updatedItems = getHistoryItems();
            if (updatedItems[0] && !updatedItems[0].id) {
                updatedItems[0].id = created.id;
                saveHistoryItems(updatedItems);
                renderHistory();
            }
        }
    }
}

async function pushFavoriteEntry(code, action, resultText) {
    const items = getFavoriteItems();
    const fingerprint = `${action}:${code.slice(0, 120)}:${resultText.slice(0, 120)}`;

    const existingIndex = items.findIndex((item) => item.fingerprint === fingerprint);
    const entry = {
        fingerprint,
        code,
        action,
        result: resultText,
        title: `${action.toUpperCase()} favorite from ${new Date().toLocaleString()}`,
        timestamp: new Date().toLocaleString(),
    };

    if (existingIndex >= 0) {
        items[existingIndex] = entry;
    } else {
        items.unshift(entry);
    }

    saveFavoriteItems(items.slice(0, HISTORY_LIMIT));
    renderFavorites();

    const token = getAuthToken();
    if (token) {
        const response = await fetchWithAuth('/user/favorites', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                title: entry.title,
                action,
                code,
                result_json: resultText,
            }),
        });

        if (response.ok) {
            const created = await response.json();
            const updatedItems = getFavoriteItems();
            if (updatedItems[0] && !updatedItems[0].id) {
                updatedItems[0].id = created.id;
                saveFavoriteItems(updatedItems);
                renderFavorites();
            }
        }
    }
}

async function deleteHistoryEntry(index) {
    const items = getHistoryItems();
    const [removed] = items.splice(index, 1);
    saveHistoryItems(items);
    renderHistory();

    if (!removed) {
        return;
    }

    if (removed.id && getAuthToken()) {
        const response = await fetchWithAuth(`/user/history/${removed.id}`, { method: 'DELETE' });
        if (!response.ok && response.status !== 401) {
            setStatus('Failed to delete history item from server.', true);
            return;
        }
    }

    setStatus('History item deleted.');
}

async function deleteFavoriteEntry(index) {
    const items = getFavoriteItems();
    const [removed] = items.splice(index, 1);
    saveFavoriteItems(items);
    renderFavorites();

    if (!removed) {
        return;
    }

    if (removed.id && getAuthToken()) {
        const response = await fetchWithAuth(`/user/favorites/${removed.id}`, { method: 'DELETE' });
        if (!response.ok && response.status !== 401) {
            setStatus('Failed to delete favorite from server.', true);
            return;
        }
    }

    setStatus('Favorite deleted.');
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

function guessLanguage(code) {
    const normalized = code.toLowerCase();
    if (normalized.includes('def ') || normalized.includes('import ')) {
        return 'Python';
    }
    if (normalized.includes('function ') || normalized.includes('console.log(')) {
        return 'JavaScript';
    }
    if (normalized.includes('public static void main') || normalized.includes('class ')) {
        return 'Java';
    }
    return 'Unknown';
}

function updateDetectedLanguage() {
    if (languageSelect.value !== 'auto') {
        detectedLanguageText.textContent = `Selected language: ${languageSelect.options[languageSelect.selectedIndex].text}`;
        return;
    }

    const guessed = guessLanguage(codeInput.value);
    detectedLanguageText.textContent = `Detected language: ${guessed}`;
}

async function loadFile(file) {
    try {
        const content = await file.text();
        codeInput.value = content;
        actionInput.value = detectActionFromFilename(file.name);
        setStatus(`Loaded file: ${file.name}`);
        updateDetectedLanguage();
    } catch (error) {
        setStatus('Failed to read selected file.', true);
    }
}

async function loadSharedSnippetFromUrl() {
    const params = new URLSearchParams(window.location.search);
    const token = params.get('share');
    if (!token) {
        return;
    }

    try {
        const response = await fetch(getApiBase() + `/share/${encodeURIComponent(token)}`);
        if (!response.ok) {
            setStatus('Shared result not found.', true);
            return;
        }

        const payload = await response.json();
        codeInput.value = payload.code;
        actionInput.value = payload.action;
        resultBox.textContent = payload.result_json;
        updateDetectedLanguage();
        setStatus('Loaded shared result.');
    } catch (error) {
        setStatus('Failed to load shared result.', true);
    }
}

const savedTheme = window.localStorage.getItem(THEME_KEY) || 'light';
applyTheme(savedTheme);
renderHistory();
renderFavorites();
updateDetectedLanguage();
updateAuthStatus();
apiModeLabel.textContent = window.location.pathname.startsWith('/app') ? 'Frontend' : 'API';

async function bootstrapSession() {
    if (!getAuthToken()) {
        return;
    }

    const response = await fetchWithAuth('/auth/me');
    if (!response.ok) {
        return;
    }

    const profile = await response.json();
    if (profile.email) {
        window.localStorage.setItem(USER_EMAIL_KEY, profile.email);
        updateAuthStatus();
    }

    await loadServerHistory();
    await loadServerFavorites();
}

bootstrapSession().catch(() => {});
loadSharedSnippetFromUrl().catch(() => {});

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
    const apiBase = getApiBase();

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
        await pushHistoryEntry(code, action);
        updateDetectedLanguage();
        apiModeLabel.textContent = 'Ready';
    } catch (error) {
        setStatus('Could not connect to backend API.', true);
        resultBox.textContent = String(error);
        apiModeLabel.textContent = 'Offline';
    }
});

clearBtn.addEventListener('click', () => {
    codeInput.value = '';
    resultBox.textContent = 'Your result will appear here.';
    setStatus('Ready');
});

favoriteBtn.addEventListener('click', async () => {
    const code = codeInput.value.trim();
    const resultText = resultBox.textContent.trim();
    if (!code || !resultText || resultText === 'Your result will appear here.') {
        setStatus('Run an analysis before saving a favorite.', true);
        return;
    }

    await pushFavoriteEntry(code, actionInput.value, resultText);
    setStatus(getAuthToken() ? 'Favorite saved and synced.' : 'Favorite saved locally.');
});

shareBtn.addEventListener('click', async () => {
    const code = codeInput.value.trim();
    const resultText = resultBox.textContent.trim();
    const action = actionInput.value;

    if (!code || !resultText || resultText === 'Your result will appear here.') {
        setStatus('Run an analysis before creating a share link.', true);
        return;
    }

    try {
        const response = await fetch(getApiBase() + '/share/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                action,
                code,
                result_json: resultText,
            }),
        });

        const data = await response.json();
        if (!response.ok) {
            setStatus(data.detail || 'Failed to create share link.', true);
            return;
        }

        const shareUrl = `${window.location.origin}${window.location.pathname}?share=${encodeURIComponent(data.token)}`;
        await navigator.clipboard.writeText(shareUrl);
        setStatus('Share link copied to clipboard.');
    } catch (error) {
        setStatus('Failed to create share link.', true);
    }
});

downloadBtn.addEventListener('click', () => {
    const text = resultBox.textContent.trim();
    if (!text || text === 'Your result will appear here.') {
        setStatus('No result available to download.', true);
        return;
    }

    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');

    anchor.href = url;
    anchor.download = `ai-developer-assistant-result-${timestamp}.txt`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);

    setStatus('Result downloaded as TXT.');
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

    await loadFile(file);
});

clearHistoryBtn.addEventListener('click', async () => {
    saveHistoryItems([]);
    renderHistory();

    if (getAuthToken()) {
        const response = await fetchWithAuth('/user/history', { method: 'DELETE' });
        if (!response.ok && response.status !== 401) {
            setStatus('Failed to clear server history.', true);
            return;
        }
    }

    setStatus('History cleared.');
});

clearFavoritesBtn.addEventListener('click', async () => {
    saveFavoriteItems([]);
    renderFavorites();

    if (getAuthToken()) {
        const response = await fetchWithAuth('/user/favorites', { method: 'DELETE' });
        if (!response.ok && response.status !== 401) {
            setStatus('Failed to clear server favorites.', true);
            return;
        }
    }

    setStatus('Favorites cleared.');
});

async function authenticate(endpoint) {
    const email = authEmailInput.value.trim().toLowerCase();
    const password = authPasswordInput.value;

    if (!email || !password) {
        setStatus('Enter email and password first.', true);
        return;
    }

    const response = await fetch(getApiBase() + endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
    });

    const data = await response.json();
    if (!response.ok) {
        setStatus(data.detail || 'Authentication failed.', true);
        return;
    }

    window.localStorage.setItem(TOKEN_KEY, data.access_token);
    window.localStorage.setItem(USER_EMAIL_KEY, data.email);
    updateAuthStatus();
    await loadServerHistory();
    await loadServerFavorites();
    setStatus('Authentication successful.');
}

signupBtn.addEventListener('click', async () => {
    try {
        await authenticate('/auth/signup');
    } catch (error) {
        setStatus('Signup request failed.', true);
    }
});

loginBtn.addEventListener('click', async () => {
    try {
        await authenticate('/auth/login');
    } catch (error) {
        setStatus('Login request failed.', true);
    }
});

logoutBtn.addEventListener('click', () => {
    clearAuthSession();
    setStatus('Logged out. Local dashboard data remains in your browser.');
});

themeToggleBtn.addEventListener('click', () => {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    applyTheme(current === 'light' ? 'dark' : 'light');
});

languageSelect.addEventListener('change', updateDetectedLanguage);
codeInput.addEventListener('input', updateDetectedLanguage);

document.addEventListener('keydown', async (event) => {
    if (event.ctrlKey && event.key === 'Enter') {
        event.preventDefault();
        form.requestSubmit();
    }

    if (event.ctrlKey && event.shiftKey && (event.key === 'C' || event.key === 'c')) {
        event.preventDefault();
        await copyBtn.click();
    }
});

['dragenter', 'dragover'].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
        event.preventDefault();
        event.stopPropagation();
        dropzone.classList.add('dragover');
    });
});

['dragleave', 'drop'].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
        event.preventDefault();
        event.stopPropagation();
        dropzone.classList.remove('dragover');
    });
});

dropzone.addEventListener('drop', async (event) => {
    const file = event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0];
    if (!file) {
        return;
    }

    const supported = ['.py', '.js', '.java'];
    const isSupported = supported.some((ext) => file.name.toLowerCase().endsWith(ext));
    if (!isSupported) {
        setStatus('Unsupported file type. Use .py, .js, or .java.', true);
        return;
    }

    await loadFile(file);
});