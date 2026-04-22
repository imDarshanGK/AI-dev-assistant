const chatForm = document.getElementById('chat-form');
const chatThread = document.getElementById('chat-thread');
const messageInput = document.getElementById('message-input');
const codeInput = document.getElementById('code-input');
const sendBtn = document.getElementById('send-btn');
const statusBox = document.getElementById('status');
const apiBaseInput = document.getElementById('api-base');
const themeToggle = document.getElementById('theme-toggle');
const clearChatBtn = document.getElementById('clear-chat');

const API_BASE_KEY = 'ai-assistant-api-base';
const THEME_KEY = 'ai-assistant-theme';
const LEGACY_RENDER_API_BASE = 'https://qyverixai.onrender.com';
const DEFAULT_API_BASE = window.location.origin && window.location.origin !== 'null'
    ? window.location.origin
    : LEGACY_RENDER_API_BASE;

let history = [];
let pendingMessageNode = null;
let requestInFlight = false;
const REQUEST_TIMEOUT_MS = 25000;

const CODE_SAMPLES = {
    'python-function': `def calculate_discount(price, percent):\n    if percent < 0 or percent > 100:\n        raise ValueError("percent must be between 0 and 100")\n    return round(price * (1 - percent / 100), 2)\n\nprint(calculate_discount(199.99, 15))`,
    'javascript-async': `async function fetchUserProfile(userId) {\n  const response = await fetch(\`/api/users/\${userId}\`);\n  if (!response.ok) {\n    throw new Error('Failed to load user profile');\n  }\n  return response.json();\n}\n\nfetchUserProfile(42).then(console.log).catch(console.error);`,
    'sql-query': `SELECT\n    customer_id,\n    COUNT(*) AS total_orders,\n    ROUND(AVG(order_total), 2) AS avg_order_value\nFROM orders\nWHERE created_at >= CURRENT_DATE - INTERVAL '30 days'\nGROUP BY customer_id\nORDER BY total_orders DESC\nLIMIT 10;`,
};

function setStatus(message, isError = false) {
    statusBox.textContent = message;
    statusBox.classList.toggle('error', isError);
}

function setLoading(isLoading) {
    sendBtn.disabled = isLoading;
    sendBtn.textContent = isLoading ? 'Thinking...' : 'Send Message';
}

function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    themeToggle.textContent = theme === 'dark' ? 'Light' : 'Dark';
    window.localStorage.setItem(THEME_KEY, theme);
}

function initApiBase() {
    const saved = window.localStorage.getItem(API_BASE_KEY);
    const currentOrigin = window.location.origin && window.location.origin !== 'null' ? window.location.origin : '';

    if (saved) {
        if (saved === LEGACY_RENDER_API_BASE && currentOrigin) {
            apiBaseInput.value = currentOrigin;
            window.localStorage.setItem(API_BASE_KEY, currentOrigin);
        } else {
            apiBaseInput.value = saved;
        }
    } else {
        apiBaseInput.value = DEFAULT_API_BASE;
    }
}

function getApiBase() {
    const raw = apiBaseInput.value.trim();
    if (!raw) {
        return DEFAULT_API_BASE;
    }

    const normalized = raw
        .replace(/\/$/, '')
        .replace(/\/app$/, '');

    return normalized || DEFAULT_API_BASE;
}

function parseMessageBody(text) {
    const content = String(text || '');
    const nodes = [];
    const codeFencePattern = /```([a-zA-Z0-9_-]+)?\n?([\s\S]*?)```/g;

    let cursor = 0;
    let match;

    while ((match = codeFencePattern.exec(content)) !== null) {
        const before = content.slice(cursor, match.index).trim();
        if (before) {
            before
                .split(/\n{2,}/)
                .map((part) => part.trim())
                .filter(Boolean)
                .forEach((paragraph) => {
                    nodes.push({ type: 'paragraph', text: paragraph });
                });
        }

        nodes.push({ type: 'code', language: (match[1] || '').toLowerCase(), text: match[2].trim() });
        cursor = match.index + match[0].length;
    }

    const trailing = content.slice(cursor).trim();
    if (trailing) {
        trailing
            .split(/\n{2,}/)
            .map((part) => part.trim())
            .filter(Boolean)
            .forEach((paragraph) => {
                nodes.push({ type: 'paragraph', text: paragraph });
            });
    }

    if (nodes.length === 0) {
        nodes.push({ type: 'paragraph', text: content });
    }

    return nodes;
}

function appendMessage(role, text) {
    const article = document.createElement('article');
    article.className = `message ${role}`;

    const header = document.createElement('div');
    header.className = 'message-header';

    const author = document.createElement('span');
    author.textContent = role === 'user' ? 'You' : 'QyverixAI';
    header.appendChild(author);

    if (role === 'assistant') {
        const copyBtn = document.createElement('button');
        copyBtn.type = 'button';
        copyBtn.className = 'copy-btn';
        copyBtn.textContent = 'Copy';
        copyBtn.addEventListener('click', async () => {
            try {
                await navigator.clipboard.writeText(text);
                setStatus('Copied response.');
            } catch (error) {
                setStatus('Failed to copy response.', true);
            }
        });
        header.appendChild(copyBtn);
    }

    article.appendChild(header);

    const body = document.createElement('div');
    body.className = 'message-body';

    parseMessageBody(text).forEach((block) => {
        if (block.type === 'code') {
            const pre = document.createElement('pre');
            const code = document.createElement('code');
            code.textContent = block.text;
            if (block.language) {
                code.className = `language-${block.language}`;
            }
            pre.appendChild(code);
            body.appendChild(pre);
            if (window.hljs) {
                window.hljs.highlightElement(code);
            }
            return;
        }

        const p = document.createElement('p');
        p.textContent = block.text;
        body.appendChild(p);
    });

    article.appendChild(body);
    chatThread.appendChild(article);
    chatThread.scrollTop = chatThread.scrollHeight;

    return article;
}

function showThinkingMessage() {
    pendingMessageNode = appendMessage('assistant', 'Thinking through your request...');
    pendingMessageNode.classList.add('thinking');
}

function clearThinkingMessage() {
    if (pendingMessageNode && pendingMessageNode.parentNode) {
        pendingMessageNode.parentNode.removeChild(pendingMessageNode);
    }
    pendingMessageNode = null;
}

async function updateQuickPrompt(promptText, autoSend = false) {
    messageInput.value = promptText;
    messageInput.focus();
    if (autoSend) {
        if (!codeInput.value.trim()) {
            setStatus('Paste code first, then tap the action again.', true);
            return;
        }
        await sendMessage();
        return;
    }
    setStatus('Prompt inserted.');
}

function resetChat() {
    const initialMessage = `
        <article class="message assistant">
            <div class="message-header">
                <span>QyverixAI</span>
            </div>
            <div class="message-body">
                <p>Welcome to your code intelligence workspace. Paste code, ask for fixes, optimizations, tests, or architecture decisions.</p>
            </div>
        </article>
    `;
    chatThread.innerHTML = initialMessage;
    history = [];
    setStatus('Conversation cleared.');
}

async function sendMessage() {
    if (requestInFlight) {
        setStatus('Please wait for the current response.', true);
        return;
    }

    const message = messageInput.value.trim();
    const code = codeInput.value.trim();

    if (!message) {
        setStatus('Enter a message first.', true);
        return;
    }

    appendMessage('user', code ? `${message}\n\nCode:\n\n\`\`\`\n${code}\n\`\`\`` : message);
    messageInput.value = '';
    setStatus('Sending...');
    requestInFlight = true;
    setLoading(true);
    showThinkingMessage();
    let timeoutId = null;

    try {
        const apiBase = getApiBase();
        window.localStorage.setItem(API_BASE_KEY, apiBase);

        const abortController = new AbortController();
        timeoutId = window.setTimeout(() => abortController.abort(), REQUEST_TIMEOUT_MS);

        const response = await fetch(`${apiBase}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message,
                code: code || null,
                history: history.slice(-12),
            }),
            signal: abortController.signal,
        });
        const data = await response.json();
        if (!response.ok) {
            clearThinkingMessage();
            const errorText = data.detail || data.error || 'Request failed.';
            appendMessage('assistant', `Request failed: ${errorText}`);
            setStatus('Request failed.', true);
            return;
        }

        clearThinkingMessage();
        const assistantText = String(data.response || '').trim() || 'No response returned.';
        appendMessage('assistant', assistantText);
        history.push(`User: ${message}`);
        history.push(`Assistant: ${assistantText}`);
        setStatus('Ready');
    } catch (error) {
        clearThinkingMessage();
        if (error instanceof DOMException && error.name === 'AbortError') {
            appendMessage('assistant', 'Request timed out. Please retry or verify API endpoint.');
            setStatus('Request timed out.', true);
        } else {
            appendMessage('assistant', 'Cannot connect to backend. Check API URL and server status.');
            setStatus('Connection error.', true);
        }
    } finally {
        if (timeoutId !== null) {
            window.clearTimeout(timeoutId);
        }
        requestInFlight = false;
        setLoading(false);
    }
}

chatForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    await sendMessage();
});

messageInput.addEventListener('keydown', async (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        await sendMessage();
    }
});

codeInput.addEventListener('keydown', async (event) => {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        await sendMessage();
    }
});

codeInput.addEventListener('input', () => {
    if (codeInput.value.length > 0) {
        setStatus('Code context ready.');
    }
});

themeToggle.addEventListener('click', () => {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    applyTheme(current === 'light' ? 'dark' : 'light');
});

apiBaseInput.addEventListener('change', () => {
    window.localStorage.setItem(API_BASE_KEY, getApiBase());
    setStatus('API endpoint updated.');
});

const savedTheme = window.localStorage.getItem(THEME_KEY);
applyTheme(savedTheme === 'dark' ? 'dark' : 'light');
initApiBase();
setStatus('Ready');

document.querySelectorAll('.prompt-chip').forEach((btn) => {
    btn.addEventListener('click', async (event) => {
        event.preventDefault();
        await updateQuickPrompt(String(btn.dataset.prompt || '').trim(), true);
    });
});

document.querySelectorAll('.sample-chip').forEach((btn) => {
    btn.addEventListener('click', (event) => {
        event.preventDefault();
        const sampleKey = String(btn.dataset.sample || '').trim();
        const snippet = CODE_SAMPLES[sampleKey];
        if (!snippet) {
            return;
        }
        codeInput.value = snippet;
        codeInput.focus();
        setStatus('Sample code loaded.');
    });
});

if (clearChatBtn) {
    clearChatBtn.addEventListener('click', (event) => {
        event.preventDefault();
        resetChat();
    });
}
