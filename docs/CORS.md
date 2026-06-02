# Cross-Origin Resource Sharing (CORS)

## Overview

QyverixAI enables Cross-Origin Resource Sharing (CORS) to allow web applications hosted on different domains to interact with the API.

Current CORS configuration:

```python
allow_origins=["*"]
allow_credentials=True
allow_methods=["*"]
allow_headers=["*"]
```

This configuration permits requests from any origin and supports all HTTP methods and headers.

---

## Authentication

Authenticated endpoints require a Bearer token in the Authorization header.

Example:

```http
Authorization: Bearer <access_token>
```

Authentication endpoints:

* `/auth/signup`
* `/auth/login`
* `/auth/me`

---

## Example: cURL Request

```bash
curl -X POST http://localhost:8000/explanation/ \
-H "Content-Type: application/json" \
-d '{
  "code":"print(\"Hello World\")",
  "language":"python"
}'
```

---

## Example: JavaScript Fetch

```javascript
fetch("http://localhost:8000/explanation/", {
  method: "POST",
  headers: {
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    code: "print('Hello World')",
    language: "python"
  })
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error(error));
```

---

## Example: Authenticated Fetch

```javascript
fetch("http://localhost:8000/auth/me", {
  headers: {
    "Authorization": `Bearer ${token}`
  }
})
.then(response => response.json())
.then(data => console.log(data));
```

---

## Using Reverse Proxies

When deploying behind a reverse proxy such as Nginx, ensure that:

* Authorization headers are forwarded.
* OPTIONS requests are not blocked.
* Required CORS headers are preserved.

Example Nginx configuration:

```nginx
proxy_set_header Authorization $http_authorization;
```

---

## Serverless Frontends

QyverixAI can be consumed from:

* Vercel
* Netlify
* Cloudflare Pages
* AWS Amplify

Ensure API URLs point to the deployed backend instance and HTTPS is used in production.

---

## Common CORS Issues

### CORS Error in Browser Console

Possible causes:

* Backend server is unavailable.
* Incorrect API URL.
* Proxy configuration strips headers.

### Authorization Header Not Sent

Verify the request includes:

```http
Authorization: Bearer <token>
```

### Preflight Request Fails

Ensure OPTIONS requests are allowed by any proxy or gateway between the frontend and backend.
