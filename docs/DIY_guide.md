```markdown
# Flask + OpenTelemetry + Collector + Jaeger on EC2  
*A complete walkthrough of what we did, issues faced, and how we fixed them.*

## Goal

Build a basic Flask "Hello World" app on EC2, instrument it with OpenTelemetry (Python), send traces to an OpenTelemetry Collector, and export those traces to Jaeger for visualization.

---

## Architecture We Set Up

- **Flask app** (Python) generates traces
- **OpenTelemetry Python SDK** exports traces via OTLP gRPC
- **OpenTelemetry Collector** receives OTLP and exports onward
- **Jaeger** receives traces from Collector and shows them in UI

Flow:

`Flask App -> OTel Collector (4317) -> Jaeger -> Jaeger UI (16686)`

---

## Step-by-Step Setup We Performed

## 1) Flask app creation on EC2

- Created Python virtual environment
- Installed Flask
- Built basic endpoints:
  - `/` -> Hello World
  - `/work` -> test endpoint with manual custom span

---

## 2) OpenTelemetry instrumentation in Flask

Installed:

- `opentelemetry-api`
- `opentelemetry-sdk`
- `opentelemetry-exporter-otlp`
- `opentelemetry-instrumentation-flask`
- `opentelemetry-instrumentation-requests`

Configured app with:

- `TracerProvider` + `Resource(service.name=hello-flask-service)`
- `BatchSpanProcessor`
- `OTLPSpanExporter(endpoint="http://localhost:4317", insecure=True)`
- `FlaskInstrumentor().instrument_app(app)`

---

## 3) Collector + Jaeger deployment in Docker

- Started Jaeger all-in-one container
- Created Collector config with:
  - `otlp` receiver
  - `batch` processor
  - `debug` exporter
  - exporter to Jaeger (eventually via OTLP gRPC alias path)
- Started Collector with ports:
  - `4317`, `4318`, `13133`

---

## 4) Networking and access checks

- Flask bound to `0.0.0.0:5000`
- Learned EC2 private IP (`172.31.x.x`) is not accessible from local browser over public internet
- Used EC2 public IP / Security Group rules / optional SSH tunneling guidance

---

## Errors We Faced and Resolutions

## Error 1: Could not open Flask app in browser

### Symptom
App showed running on:
- `127.0.0.1:5000`
- `172.31.x.x:5000`

But browser from laptop could not load it.

### Root Cause
Used EC2 **private IP** (`172.31.x.x`) in browser.

### Resolution
- Use **EC2 Public IPv4** in browser: `http://<public-ip>:5000`
- Ensure Security Group allows inbound TCP `5000` from your IP (or use SSH tunnel)

---

## Error 2: Collector failed to start with logging exporter deprecation

### Symptom
Collector logs showed:

`'exporters' the logging exporter has been deprecated, use the debug exporter instead`

### Root Cause
Newer Collector version removed/deprecated `logging` exporter config.

### Resolution
Replaced:
```yaml
exporters:
  logging:
    loglevel: debug
```

With:
```yaml
exporters:
  debug:
    verbosity: detailed
```

And updated pipeline exporter reference from `logging` -> `debug`.

---

## Error 3: Collector failed with unknown `jaeger` exporter type

### Symptom
Collector logs:

`unknown type: "jaeger" for id: "jaeger"`

### Root Cause
Current Collector image no longer includes legacy `jaeger` exporter type in this build.

### Resolution
Switched to supported exporter path:
- OTLP exporter towards Jaeger (`otlp` alias / later `otlp_grpc` recommended), or Zipkin exporter alternative.

---

## Error 4: App could not export traces (`DEADLINE_EXCEEDED`, `UNAVAILABLE`) to Collector

### Symptom
Flask logs:
- `Failed to export traces ... DEADLINE_EXCEEDED`
- `StatusCode.UNAVAILABLE`

### Root Cause
Collector receiver inside container was bound to:
- `127.0.0.1:4317`
- `127.0.0.1:4318`
which made it unreachable from host process path expected by exporter in this setup.

### Resolution
Explicitly bound receiver endpoints to all interfaces:

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318
```

After restart, logs showed:
- `Starting GRPC server ... endpoint: [::]:4317`
- `Everything is ready. Begin running and processing data.`

This confirmed healthy receiver startup.

---

## Error 5 (Warning only): OTLP alias deprecation

### Symptom
Collector warning:

`"otlp" alias is deprecated; use "otlp_grpc" instead`

### Root Cause
Collector version `0.150.1` deprecates alias naming.

### Resolution
No immediate breakage; pipeline still works. Recommended cleanup:
- replace `otlp` exporter type alias with `otlp_grpc`.

---

## Security Group / Port Decisions We Clarified

Do **not** open everything publicly.

- `4317`: only needed publicly if external systems must push OTLP directly.
- `4318`: optional (OTLP HTTP), same principle.
- `16686`: Jaeger UI, restrict to your IP (`/32`) if opening.
- `13133`: health check, usually keep private.

For single-host demo:
- Open only `22` and optionally `16686`/`5000` to your IP, or prefer SSH tunnel.

---

## Final Working State

- Flask app runs on EC2 and generates spans
- App exports OTLP gRPC to Collector at `localhost:4317`
- Collector starts successfully and receives OTLP
- Collector pipeline exports onward to Jaeger
- Jaeger UI can be used to query service traces

---

## Recommended Final Collector Config (clean version)

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
  debug:
    verbosity: detailed
  otlp_grpc/jaeger:
    endpoint: jaeger:4317
    tls:
      insecure: true

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [debug, otlp_grpc/jaeger]
```

---

## Validation Checklist (Quick)

- [ ] Flask app responds on `/` and `/work`
- [ ] No `UNAVAILABLE` in Flask exporter logs
- [ ] Collector logs show receiver started and ready
- [ ] Collector debug exporter shows trace/span output
- [ ] Jaeger UI shows `hello-flask-service` traces

---

## Optional Next Improvements

- Move app config to env vars (`OTEL_*`)
- Add metrics + logs via Collector
- Use Docker Compose for one-command startup
- Replace Flask dev server with Gunicorn for production-like behavior
- Add sampling config and resource attributes for better observability
```

If you want, I can also provide a second, shorter version of this doc as a **runbook** (copy/paste commands only).