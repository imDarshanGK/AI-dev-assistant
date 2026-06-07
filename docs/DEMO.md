# Demo Account & Rate Limiting

QyverixAI supports a shared demo account with a lower API quota so visitors can try the product without signing up for a full account.

## Create the Demo Account

From the repository root, set a password and run the creation script:

```bash
export DEMO_PASSWORD="your-secure-demo-password"
python backend/scripts/create_demo_user.py
```

On Windows (PowerShell):

```powershell
$env:DEMO_PASSWORD = "your-secure-demo-password"
python backend/scripts/create_demo_user.py
```

The script creates (or updates) a user with:

- **Email:** `demo@qyverixai.com`
- **Password:** value of `DEMO_PASSWORD`
- **`is_demo`:** `true`

Credentials are printed to stdout when the script finishes.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEMO_PASSWORD` | *(required for script)* | Password for the demo account |
| `DEMO_RATE_LIMIT_PER_MINUTE` | `5` | Max analysis requests per minute for demo users |
| `RATE_LIMIT_PER_MINUTE` | `30` | Max analysis requests per minute for regular users |

Add these to your `.env` (see `.env.example`):

```env
DEMO_RATE_LIMIT_PER_MINUTE=5
DEMO_PASSWORD=your-secure-demo-password
```

## How Demo Rate Limiting Works

Rate limiting applies to these endpoints only:

- `/explanation/`
- `/debugging/`
- `/suggestions/`
- `/analyze/`

**Regular users** are limited by `RATE_LIMIT_PER_MINUTE` (default 30) per client IP.

**Demo users** are limited by `DEMO_RATE_LIMIT_PER_MINUTE` (default 5) per client IP when the client sends:

```http
X-Demo-User: true
```

The middleware keeps separate in-memory counters for demo and regular traffic. Every response includes:

- `X-RateLimit-Limit` — the active limit (5 for demo, 30 for regular)
- `X-RateLimit-Remaining` — requests left in the current 60-second window

When the limit is exceeded, the API returns `429 Too Many Requests` with a `Retry-After` header.

### Authenticating as Demo

1. Log in via `POST /auth/login` with the demo email and password.
2. Call `GET /auth/me` with the bearer token — the response includes `"is_demo": true`.
3. Send `X-Demo-User: true` on analysis requests so the lower demo quota applies.

## Displaying Quota in the Frontend

The web UI reads rate-limit headers after each analysis request and shows a banner when demo mode is active.

### Enable demo mode

Set `localStorage` before or after login:

```javascript
localStorage.setItem('qyx_is_demo', 'true');
```

Or open the app with `?demo=1` in the URL (the UI persists this flag).

### Send the demo header

Include `X-Demo-User: true` on requests to analysis endpoints:

```javascript
const headers = { 'Content-Type': 'application/json' };
if (localStorage.getItem('qyx_is_demo') === 'true') {
  headers['X-Demo-User'] = 'true';
}

const response = await fetch(`${apiBase}/analyze/`, {
  method: 'POST',
  headers,
  body: JSON.stringify({ code, language }),
});
```

### Show remaining quota

Parse the response headers and update the banner:

```javascript
const remaining = parseInt(response.headers.get('X-RateLimit-Remaining') || '0', 10);
const limit = parseInt(response.headers.get('X-RateLimit-Limit') || '5', 10);

// Example banner text
banner.textContent = `Demo Mode: ${remaining} of ${limit} requests remaining`;
```

The built-in frontend banner turns amber when remaining requests are low (≤ 2) and shows `Demo Mode: X requests remaining`.
