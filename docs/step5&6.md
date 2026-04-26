```markdown
# Step 5 & 6 Guide: Tuning + Docker Compose Hardening
*What we changed, what broke, and how we fixed it.*

## Context

At this point in the project, we already had:

- Flask app instrumented with OpenTelemetry
- Traces flowing to Collector and Jaeger
- Logs correlated with `trace_id` and `span_id`
- Metrics path introduced in Step 4

Step 5 and Step 6 focused on making this stack more production-friendly and stable.

---

## Step 5: Telemetry Tuning (quality, cost, resilience)

## Goals
- Control trace volume/cost with sampling
- Improve exporter efficiency with batching
- Protect collector from memory spikes
- Standardize resource metadata

## What we implemented

### 1) Sampling controls (app side)
Added environment variables in `otel-flask.service`:

- `OTEL_TRACES_SAMPLER=parentbased_traceidratio`
- `OTEL_TRACES_SAMPLER_ARG=0.2`

This targets ~20% head-based sampling while preserving parent-based decisions.

### 2) Batch span processor tuning (app side)
Added:

- `OTEL_BSP_MAX_QUEUE_SIZE=2048`
- `OTEL_BSP_MAX_EXPORT_BATCH_SIZE=512`
- `OTEL_BSP_SCHEDULE_DELAY=5000`
- `OTEL_BSP_EXPORT_TIMEOUT=30000`

This improves export behavior under load and reduces per-span overhead.

### 3) Resource attributes consistency
Expanded resource metadata for better filtering/grouping, including region and environment tags.

### 4) Collector-side protection
Added processors in `otel-collector-config.yaml`:

- `memory_limiter`
- tuned `batch` processor (`send_batch_size`, `timeout`)

Applied in both traces and metrics pipelines.

---

## Step 5 issues we encountered

## Issue A: Metrics not visible at `/metrics`
### Symptom
`curl http://localhost:9464/metrics` with targeted grep showed no expected app metrics.

### Root cause
Endpoint mismatch between host/container mapping and app exporter settings:

- Collector OTLP gRPC exposed on host `4319` (from compose)
- Some app/systemd settings still pointed to `4317`
- Hardcoded exporter endpoints in `app.py` caused drift from service env vars

### Resolution
Adopted one consistent routing rule (Pattern A):

- app traces -> `http://localhost:4319`
- app metrics -> `http://localhost:4319`

Then restarted services and validated with load generation + collector logs.

---

## Issue B: Traces and metrics split across different endpoints caused confusion
### Symptom
Telemetry partially worked but behavior was hard to reason about.

### Root cause
Using different endpoints for different signals is valid, but in this setup it accidentally routed traces/metrics to different backends.

### Resolution
Chose Pattern A for simplicity and reliability:
single app egress endpoint -> Collector -> backend fanout.

---

## Step 5 validation checklist we used

1. Generate traffic:
```bash
for i in {1..50}; do curl -s http://localhost:5000/work > /dev/null; done
```

2. Confirm app still serves:
```bash
curl http://localhost:5000/
```

3. Confirm collector receives telemetry:
```bash
docker logs otel-collector
```

4. Confirm metrics endpoint:
```bash
curl -s http://localhost:9464/metrics
```
(Use broad match first; exact names can be normalized.)

---

## Step 6: Docker Compose Hardening

## Goals
- Make startup deterministic
- Reduce unexpected breakage from image drift
- Add health checks and dependency gating
- Persist Jaeger data
- Improve operational safety

## What we implemented

### 1) Pinned image versions
Replaced `latest` tags with explicit versions:
- Jaeger: `jaegertracing/all-in-one:1.57`
- Collector: `otel/opentelemetry-collector-contrib:0.150.1`

This avoids sudden behavior changes from upstream updates.

### 2) Added health checks
In `docker-compose.yml`:
- Jaeger health check (`http://localhost:16686`)
- Collector health check (`http://localhost:13133`)

### 3) Added startup gating
Collector depends on healthy Jaeger:

```yaml
depends_on:
  jaeger:
    condition: service_healthy
```

### 4) Kept explicit host port mapping
- Collector OTLP gRPC on host `4319`
- Collector OTLP HTTP on host `4320`
- Collector metrics exporter on `9464`
- Collector health endpoint on `13133`

### 5) Persistent Jaeger storage
Added volume:
- `jaeger-data:/badger`

Prevents easy data loss on restarts.

---

## Step 6 issues we encountered

## Issue A: Collector config syntax typo
### Symptom
Config had a malformed processors list.

### Example
`processors: [memory_limiter, batch]]`  (extra `]`)

### Resolution
Fixed to:
`processors: [memory_limiter, batch]`

---

## Issue B: Health extension configured but not enabled in service
### Symptom
`extensions.health_check` was declared but not referenced in `service`.

### Root cause
Collector only activates declared extensions when listed in:
`service.extensions: [...]`

### Resolution
Added:
```yaml
service:
  extensions: [health_check]
  pipelines:
    ...
```

This aligns with compose healthcheck on port `13133`.

---

## Final Step 6 status

### `docker-compose.yml`
- Healthy and aligned with hardening goals.

### `otel-collector-config.yaml`
- Good after:
  - fixing processor bracket typo
  - adding `service.extensions: [health_check]`

---

## Key lessons from Step 5 & 6

1. **Port mapping discipline is non-negotiable**  
   Host and container ports must be consistently reflected in app exporters and service env.

2. **Avoid config drift**  
   Hardcoded `app.py` endpoints + different systemd env endpoints create hidden failures.

3. **Use one routing strategy unless truly needed**  
   Pattern A (all app signals -> collector) is easier to operate and troubleshoot.

4. **Pin versions early**  
   Prevents surprises like deprecated/removed components between runs.

5. **Health checks should test real readiness**  
   Defining an extension is not enough; it must be enabled under `service.extensions`.

---

## Current architecture after Step 5 & 6

`Flask (Gunicorn/systemd)`  
-> OTLP gRPC to `localhost:4319`  
-> `OpenTelemetry Collector` (batch + memory_limiter + healthcheck)  
-> traces to Jaeger, metrics to Prometheus exporter (`:9464`)  
-> correlated app logs available in journal

---

## Suggested next step (Step 7)

Monitoring and alerting:
- collector exporter failures
- dropped spans/metrics
- memory limiter activation
- app latency (p95/p99)
- request error rate

This completes the transition from “working observability” to “operational observability”.
```

