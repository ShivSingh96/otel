```markdown
# Step 4 Guide: Adding Metrics to Flask + OpenTelemetry + Collector (and Troubleshooting)

## Objective

Extend the existing working trace pipeline to also collect **metrics** from the Flask app and expose them through the OpenTelemetry Collector at:

- `http://<host>:9464/metrics`

This step keeps traces working while adding metric telemetry.

---

## Initial Architecture (Before Step 4)

Working already:

- Flask app -> OTLP traces -> OTel Collector -> Jaeger
- Log correlation in app logs (`trace_id`, `span_id`) was already enabled
- Gunicorn + systemd were already in place

Step 4 added metrics path:

- Flask app -> OTLP metrics -> OTel Collector -> Prometheus exporter (`:9464`)

---

## What We Implemented

## 1) Collector metrics pipeline

We updated collector config to include:

- `otlp` receiver (already used by traces)
- `metrics` pipeline
- `prometheus` exporter on `0.0.0.0:9464`
- optional `debug` exporter for metric visibility in collector logs

Example structure:

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:

exporters:
  prometheus:
    endpoint: 0.0.0.0:9464
  otlp_grpc/jaeger:
    endpoint: jaeger:4317
    tls:
      insecure: true
  debug:
    verbosity: detailed

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [debug, otlp_grpc/jaeger]

    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [debug, prometheus]
```

---

## 2) App metrics instrumentation

In `app.py`, we added metrics SDK setup:

- `MeterProvider` with `PeriodicExportingMetricReader`
- `OTLPMetricExporter(...)`
- Counter:
  - `http_requests_total`
- Histogram:
  - `http_request_duration_ms`

We also instrumented route handlers:

- increment counter in `/` and `/work`
- measure and record request duration in ms

This gave us custom app-level metrics instead of relying only on traces/logs.

---

## 3) Systemd env configuration for metrics

In `otel-flask.service`, we added:

- `OTEL_METRICS_EXPORTER=otlp`
- `OTEL_EXPORTER_OTLP_METRICS_PROTOCOL=grpc`
- `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT=...`
- `OTEL_EXPORTER_OTLP_METRICS_INSECURE=true`

Then restarted service:

```bash
sudo systemctl daemon-reload
sudo systemctl restart otel-flask
```

---

## Problems We Faced During Step 4

## Problem A: No metric output from `/metrics`

### Symptom
`curl http://localhost:9464/metrics | grep ...` returned nothing.

### What we observed
- Collector was up and healthy
- Metrics endpoint responded, but no expected custom metric names appeared

### Root cause
**Endpoint mismatch (split-brain config):**

- `docker-compose.yml` mapped collector OTLP gRPC as:
  - host `4319 -> collector 4317`
- app/export config had mixed signal endpoints:
  - some places used `localhost:4317`
  - some used `localhost:4319`

As a result:
- app signals were not consistently sent to collector OTLP receiver

---

## Problem B: Confusion around using different endpoints for traces and metrics

### Clarification
Yes, technically possible.
But in our topology it caused ambiguity and accidental routing errors.

### Best-practice resolution
Use **Pattern A**: send both traces and metrics to collector on the same app endpoint (`4319` in this setup), and let collector fan out to Jaeger/Prometheus.

---

## Final Working Pattern (Pattern A)

## Endpoint alignment used to fix issue

Because compose maps collector OTLP gRPC to host `4319`, we set:

- app traces exporter -> `http://localhost:4319`
- app metrics exporter -> `http://localhost:4319`
- systemd OTLP env vars -> `http://localhost:4319`

This removed ambiguity and fixed metric flow.

---

## Final Verification Steps

## 1) Generate load

```bash
for i in {1..20}; do curl -s http://localhost:5000/work > /dev/null; done
```

## 2) Check collector logs

```bash
sudo docker logs otel-collector
```

Look for metrics/debug pipeline activity (if debug exporter enabled).

## 3) Inspect metrics endpoint

Start broad first (don’t over-filter too early):

```bash
curl -s http://localhost:9464/metrics
```

Then filter:

```bash
curl -s http://localhost:9464/metrics | rg "http_request|duration|route|otel"
```

Important: Prometheus-normalized names may differ from exact SDK names, so broad search is safer initially.

---

## Key Lessons from Step 4

1. **Signal routing consistency is critical**: traces/metrics must target the actual collector receiver endpoint.
2. **Host vs container port mapping matters**: app on host must use published host port (`4319`), not internal container port (`4317`) unless directly reachable.
3. **Avoid mixed endpoint sources**: hardcoded app exporter endpoints + conflicting systemd env vars create hidden drift.
4. **Use broad metric queries first**: exact grep patterns can miss normalized metric names.
5. **Pattern A is easiest to reason about**: app -> collector (single endpoint) -> backend-specific exporters.

---

## Final State Achieved for Step 4

- Metrics export enabled in Flask app
- Collector receives metrics through OTLP
- Collector exposes Prometheus scrape endpoint at `:9464`
- Traffic generation now produces visible metric series
- Trace + log + metric telemetry are all flowing through a coherent pipeline

---

## Optional Next Improvements

- Add Prometheus server scrape config for collector `:9464`
- Add Grafana dashboards for request count/latency
- Add labels (env, version, endpoint) consistently across metrics
- Add SLO-style alerts (error rate, p95 latency) once Prometheus is in place
```

If you want, I can also generate a **compact runbook version** of this Step 4 guide (copy/paste commands only, no explanations).