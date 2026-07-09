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
curl -H "Authorization: Bearer mysecrettoken" http://localhost:8000/metrics
```
```python
import requests
headers = {"Authorization": "Bearer mysecrettoken"}
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
