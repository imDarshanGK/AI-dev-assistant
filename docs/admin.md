# Admin & Operational Endpoints

These endpoints are intended for infrastructure operators, DevOps, and monitoring systems — **not** end users. Restrict access at the network/proxy level in production.

---

## `GET /metrics`

Exposes runtime metrics in **Prometheus exposition format** for scraping.

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `METRICS_ENABLED` | No (default: `true`) | Set to `false` to disable the endpoint (returns 404) |
| `METRICS_AUTH_TOKEN` | No | If set, all scrape requests must supply this token as a Bearer token |

### Authentication

When `METRICS_AUTH_TOKEN` is configured, include it in the `Authorization` header:

```
Authorization: Bearer <token>
```

Omitting or providing a wrong token returns `401 Unauthorized`.

### Example Requests

**No auth configured:**
```bash
curl http://localhost:8000/metrics
```
```python
import requests
response = requests.get("http://localhost:8000/metrics")
print(response.text)
```

**With auth token:**
```bash
curl -H "put_auth_headers_here" http://localhost:8000/metrics
```
```python
import requests
headers = "put auth headers here in the form of {\'key\': \'value\'}"
response = requests.get("http://localhost:8000/metrics", headers=headers)
print(response.text)
```

### Responses

| Status | Meaning |
|---|---|
| `200` | Prometheus-formatted metrics payload |
| `401` | Missing or invalid bearer token |
| `404` | Metrics disabled via `METRICS_ENABLED=false` |

> **Note:** This endpoint is excluded from the OpenAPI schema (`include_in_schema=False`). It will not appear in `/docs` or `/redoc`.

---

## `GET /diag`

Returns a minimal JSON snapshot of process/system **memory, CPU, and queue depth** for quick troubleshooting. The payload is deliberately limited to non-sensitive operational signals — it never includes environment variables, secrets, connection strings, tokens, or request contents.

### Safety model

- **Disabled by default.** Returns `404` unless `DIAG_ENABLED=true`, so its existence is not advertised.
- **Never unguarded.** Even when enabled, the endpoint returns `403` unless at least one access control is configured.
- **Two ways in.** A request is authorised if it presents the correct bearer token **or** originates from an allowlisted IP/CIDR.

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DIAG_ENABLED` | No (default: `false`) | Master switch. Returns `404` while disabled. |
| `DIAG_AUTH_TOKEN` | No | Admin bearer token. When set, a matching `Authorization: Bearer <token>` grants access. |
| `DIAG_IP_ALLOWLIST` | No | Comma-separated IPs and/or CIDRs allowed access (e.g. `10.0.0.0/8,127.0.0.1`). |
| `DIAG_TRUST_FORWARDED_FOR` | No (default: `false`) | Trust the left-most `X-Forwarded-For` entry for the allowlist check. Only enable behind a trusted proxy. |

> At least one of `DIAG_AUTH_TOKEN` or `DIAG_IP_ALLOWLIST` must be set, otherwise the endpoint returns `403`.

### Example Request

```bash
curl -H "put_auth_headers_here" http://localhost:8000/diag
```
```python
import requests
headers = "put auth headers here in the form of {\'key\': \'value\'}"
response = requests.get("http://localhost:8000/diag", headers=headers)
print(response.json())
```

### Example Response

```json
{
  "status": "ok",
  "timestamp": "2026-05-30T12:00:00+00:00",
  "uptime_seconds": 1342.51,
  "process": {
    "pid": 42,
    "memory_rss_bytes": 78643200,
    "memory_rss_mb": 75.0,
    "memory_percent": 1.83,
    "num_threads": 9,
    "cpu_user_seconds": 4.21,
    "cpu_system_seconds": 1.07,
    "num_fds": 23
  },
  "system": {
    "cpu_count": 4,
    "load_average": [0.31, 0.27, 0.22],
    "cpu_percent": 6.0,
    "memory_total_bytes": 8323039232,
    "memory_available_bytes": 5123440640,
    "memory_percent": 38.4
  },
  "queue": {
    "inflight_requests": 1.0,
    "scheduled_jobs": 1,
    "rate_limited_clients": 0
  },
  "runtime": {
    "python_version": "3.12.3",
    "platform": "linux",
    "psutil_available": true,
    "gc_objects": 51234
  }
}
```

> `inflight_requests` includes the diagnostics request currently being served, so `1` under no other load is expected. Richer `process`/`system` fields require the optional `psutil` dependency; without it the endpoint degrades to stdlib-only metrics (`load_average`, `getrusage` CPU times, and `VmRSS` on Linux), and `runtime.psutil_available` reports `false`.

### Responses

| Status | Meaning |
|---|---|
| `200` | Diagnostics snapshot |
| `401` | Token configured but missing/invalid (and IP not allowlisted) |
| `403` | Enabled but unconfigured, or client IP not in allowlist |
| `404` | Diagnostics disabled via `DIAG_ENABLED` unset/false |

> **Note:** This endpoint is excluded from the OpenAPI schema (`include_in_schema=False`). It will not appear in `/docs` or `/redoc`.

---

## `GET /healthz/live`

**Liveness probe.** Returns `200` as long as the process can respond to HTTP requests. Does **not** check external dependencies (database, etc.).

Use this for Kubernetes `livenessProbe`. A failure triggers a container restart.

### Authentication

None required.

### Example Request

```bash
curl http://localhost:8000/healthz/live
```
```python
import requests
response = requests.get("http://localhost:8000/healthz/live")
print(response.json())
```

### Example Response

```json
{ "status": "ok" }
```

### Responses

| Status | Meaning |
|---|---|
| `200` | Process is alive |

---

## `GET /healthz/ready`

**Readiness probe.** Verifies all critical dependencies (currently: database) are reachable before reporting ready.

Use this for Kubernetes `readinessProbe`. A failure removes the pod from load balancer rotation but does **not** restart the container.

### Authentication

None required.

### Example Request

```bash
curl http://localhost:8000/healthz/ready
```
```python
import requests
response = requests.get("http://localhost:8000/healthz/ready")
print(response.status_code, response.json())
```

### Example Response — healthy

```json
{
  "status": "ok",
  "checks": {
    "database": { "ok": true, "elapsed_ms": 1.42 }
  }
}
```

### Example Response — degraded

```json
{
  "status": "degraded",
  "checks": {
    "database": {
      "ok": false,
      "elapsed_ms": 2001.5,
      "error": "OperationalError: could not connect to server"
    }
  }
}
```

### Responses

| Status | Meaning |
|---|---|
| `200` | All dependency checks passed |
| `503` | One or more checks failed; body contains per-check breakdown |

---

## Access Restriction Recommendations

- **`/metrics`** — Block from public internet. Allow only your Prometheus scraper's IP/CIDR. Example nginx rule:
  ```nginx
  location /metrics {
      allow 10.0.0.0/8;
      deny all;
  }
  ```
- **`/healthz/*`** — Safe to expose to internal load balancers/orchestrators. Restrict from public internet if possible.