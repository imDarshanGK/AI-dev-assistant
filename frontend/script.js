const form = document.getElementById('assistant-form');
const codeInput = document.getElementById('code-input');
const actionInput = document.getElementById('action');
const apiBaseInput = document.getElementById('api-base');
const resultBox = document.getElementById('result');
const statusBox = document.getElementById('status');
const clearBtn = document.getElementById('clear-btn');

function setStatus(message, isError = false) {
    statusBox.textContent = message;
    statusBox.classList.toggle('error', isError);
}

function buildEndpoint(action) {
    if (action === 'explanation') return '/explanation/';
    if (action === 'debugging') return '/debugging/';
    return '/suggestions/';
}

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

    setStatus('Running request...');
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