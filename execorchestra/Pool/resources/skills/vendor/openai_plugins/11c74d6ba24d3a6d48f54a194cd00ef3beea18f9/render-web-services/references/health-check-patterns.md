# Health check patterns for Render Web Services

Render uses an HTTP **GET** to your configured **`healthCheckPath`**. The response must be **`2xx` or `3xx`**. Anything else (including **`4xx`**, **`5xx`**, timeouts, or connection failures) counts as **unhealthy** and can **block a deploy from going live** or trigger rollback behavior.

## Endpoint design

- Prefer a **dedicated** path such as **`/health`** or **`/healthz`**.
- Return **`200 OK`** with a small body or empty body; avoid heavy work on every request.
- The path must be served by the **same process and port** that handles production traffic (i.e. whatever listens on **`PORT`**).

### What to verify (in order of usefulness)

1. **Application has finished starting** — routes registered, server accepting connections.
2. **Optional: critical dependencies** — e.g. can open a **database** connection or run a trivial query *if* you accept that DB blips mark the whole service unhealthy (often desirable for strict readiness).
3. Avoid equating “process alive” with “ready for traffic” if initialization is slow (migrations, cache warm-up, etc.).

Do **not** use health checks that always return 200 before the server is actually listening on **`PORT`**.

## Framework examples

These are minimal illustrations; adapt paths and ports to your app.

### Express.js (Node)

```js
app.get("/health", (_req, res) => {
  res.status(200).send("ok");
});
```

### Flask (Python)

```python
@app.get("/health")
def health():
    return "", 200
```

### Django (Python)

```python
# urls.py
path("health", lambda r: HttpResponse(status=200)),
```

### Go (net/http)

```go
http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
    w.WriteHeader(http.StatusOK)
})
```

### Rust (Actix-web)

```rust
#[get("/health")]
async fn health() -> impl Responder {
    HttpResponse::Ok().finish()
}
```

## Timeouts and tuning

- If the app **starts listening after** the health check window expects readiness, deploys may **fail or roll back**.
- **Slow-starting** apps (large JVM warmup, many workers): ensure the **listen** happens as early as possible, or **increase** health check **timeout** / **interval** in settings if the platform allows—so the first successful check occurs after the server is truly up.
- A failing dependency check (DB down) will keep the service **unhealthy**; that is often correct for **readiness** but harsh if you only wanted **liveness**. Prefer **readiness** semantics for Render’s path unless you have a reason not to.

## Common issues

| Symptom | Likely cause |
|--------|----------------|
| Deploy never goes live | Health path returns **4xx/5xx**, wrong path, or server not up yet |
| Connection refused | App bound to **127.0.0.1** only, or wrong **port** vs **`PORT`** |
| Intermittent failures | Timeouts too aggressive vs cold start; DB check flapping |
| Wrong service | Health path hits a different process or static file only in old deploy |

Always confirm **`healthCheckPath`** matches a **GET** route on the service that listens on **`0.0.0.0:$PORT`**.
