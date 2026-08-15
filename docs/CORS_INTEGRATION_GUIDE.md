# CORS Integration Guide

## Overview

QyverixAI supports Cross-Origin Resource Sharing (CORS) for browser-based applications and external integrations.

Current CORS configuration:

| Setting         | Value   |
| --------------- | ------- |
| Allowed Origins | `*`     |
| Allowed Methods | `*`     |
| Allowed Headers | `*`     |
| Credentials     | Enabled |

 > **Note:** Credentials are enabled in the server configuration. Browser behavior may vary when credentials are used with wildcard origins (`*`).

## JavaScript Fetch Example

```javascript
const response = await fetch("http://localhost:8000/analyze/", {
  method: "POST",
  headers: {
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    code: "print('Hello World')",
    language: "python"
  })
});

const data = await response.json();
console.log(data);
```

## cURL Example

```bash
curl -X POST http://localhost:8000/analyze/ \
-H "Content-Type: application/json" \
-d "{\"code\":\"print('Hello World')\",\"language\":\"python\"}"
```

## Authentication

Authentication endpoints:

* `POST /auth/signup`
* `POST /auth/login`
* `GET /auth/me`

Successful signup and login requests return an access token.

Include the token in the Authorization header when accessing protected endpoints:

```http
Authorization: Bearer YOUR_TOKEN
```

## Proxy and Serverless Frontends

When deploying behind Nginx, Cloudflare, Vercel, Netlify, or other proxy/serverless platforms:

* Allow OPTIONS preflight requests.
* Forward Authorization headers.
* Preserve Access-Control-Allow-* headers.
* Ensure the API URL is reachable from the frontend.

