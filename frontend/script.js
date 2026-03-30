document.getElementById('assistant-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    const code = document.getElementById('code-input').value;
    const action = document.getElementById('action').value;
    let endpoint = '';
    if (action === 'explanation') endpoint = '/explanation/';
    else if (action === 'debugging') endpoint = '/debugging/';
    else if (action === 'suggestions') endpoint = '/suggestions/';
    document.getElementById('result').textContent = 'Loading...';
    try {
        const res = await fetch('http://localhost:8000' + endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code })
        });
        const data = await res.json();
        document.getElementById('result').textContent = JSON.stringify(data, null, 2);
    } catch (err) {
        document.getElementById('result').textContent = 'Error: ' + err;
    }
});