const chatForm = document.getElementById('chat-form');
const chatThread = document.getElementById('chat-thread');
const messageInput = document.getElementById('message-input');
const codeInput = document.getElementById('code-input');
const sendBtn = document.getElementById('send-btn');
const statusBox = document.getElementById('status');
const apiBaseInput = document.getElementById('api-base');
const themeToggle = document.getElementById('theme-toggle');

const API_BASE_KEY = 'ai-assistant-api-base';
const THEME_KEY = 'ai-assistant-theme';
const LEGACY_RENDER_API_BASE = 'https://qyverixai.onrender.com';
const DEFAULT_API_BASE = window.location.origin && window.location.origin !== 'null'
    ? window.location.origin
    : LEGACY_RENDER_API_BASE;

let history = [];

function setStatus(message, isError = false) {
    statusBox.textContent = message;
    statusBox.classList.toggle('error', isError);
}

function setLoading(isLoading) {
    sendBtn.disabled = isLoading;
    sendBtn.textContent = isLoading ? 'Thinking...' : 'Send';
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
    return apiBaseInput.value.trim().replace(/\/$/, '');
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
}

async function sendMessage() {
    const message = messageInput.value.trim();
    const code = codeInput.value.trim();

    if (!message) {
        setStatus('Enter a message first.', true);
        return;
    }

    appendMessage('user', code ? `${message}\n\nCode:\n\n\`\`\`\n${code}\n\`\`\`` : message);
    messageInput.value = '';
    setStatus('Sending...');
    setLoading(true);

    try {
        const apiBase = getApiBase();
        window.localStorage.setItem(API_BASE_KEY, apiBase);

        const response = await fetch(`${apiBase}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message,
                code: code || null,
                history: history.slice(-12),
            }),
        });

        const data = await response.json();
        if (!response.ok) {
            const errorText = data.detail || data.error || 'Request failed.';
            appendMessage('assistant', `Request failed: ${errorText}`);
            setStatus('Request failed.', true);
            return;
        }

        const assistantText = String(data.response || '').trim() || 'No response returned.';
        appendMessage('assistant', assistantText);
        history.push(`User: ${message}`);
        history.push(`Assistant: ${assistantText}`);
        setStatus('Ready');
    } catch (error) {
        appendMessage('assistant', 'Cannot connect to backend. Check API URL and server status.');
        setStatus('Connection error.', true);
    } finally {
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

themeToggle.addEventListener('click', () => {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    applyTheme(current === 'light' ? 'dark' : 'light');
});

apiBaseInput.addEventListener('change', () => {
    window.localStorage.setItem(API_BASE_KEY, getApiBase());
});

const savedTheme = window.localStorage.getItem(THEME_KEY);
applyTheme(savedTheme === 'dark' ? 'dark' : 'light');
initApiBase();
setStatus('Ready');

// Wire quick-action buttons
document.querySelectorAll('.quick-btn').forEach((btn) => {
    btn.addEventListener('click', (e) => {
        e.preventDefault();
        if (codeInput.value.trim()) {
            messageInput.value = btn.dataset.prompt;
            messageInput.focus();
        }
    });
});
