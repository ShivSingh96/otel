```markdown
# Step 7.1 & 7.2 Guide: Prometheus Monitoring + Alert Rules
*What we implemented, issues we hit, and how we resolved them.*

## Objective

After enabling traces, logs, and metrics, we moved to operational monitoring:

- **Step 7.1:** Prometheus scraping validation
- **Step 7.2:** Alert rule creation and validation

Goal: make telemetry health visible and actionable, not just manually inspectable.

---

## Step 7.1 — Prometheus Scraping Setup

## What we did

1. Added Prometheus service in `docker-compose.yml`
2. Exposed Prometheus UI on port `9090`
3. Created Prometheus config (`prometheus.yml`) with scrape targets:
   - `otel-collector:9464` (collector Prometheus exporter)
   - initially also `otel-collector:13133` (collector health endpoint)
4. Started stack with compose and validated target status from:
   - `http://<EC2_PUBLIC_IP>:9090/targets`

---

## Issues faced in Step 7.1 and resolutions

## Issue 1: Prometheus UI not reachable (`:9090` timeout)

### Symptom
Browser showed timeout when opening:
- `http://<EC2_PUBLIC_IP>:9090/targets`

### Root cause
EC2 Security Group did not allow inbound traffic on `9090`.

### Resolution
Added inbound rule:
- TCP `9090`
- Source: your IP `/32`

After that, UI became reachable.

---

## Issue 2: `otel-collector` marked unhealthy in Docker Compose

### Symptom
Compose showed:
- `dependency failed to start: container otel-collector is unhealthy`
- Collector container was `Up` but health status `unhealthy`.

### Root cause
Collector healthcheck used `wget` command inside collector container image; this image may not contain `wget`, causing healthcheck command failure despite collector running.

### Resolution
Switched to a safer healthcheck command available in container context (or relaxed dependency logic), then collector health state stabilized.

---

## Issue 3: Collector health target showing DOWN in Prometheus

### Symptom
In `/targets`:
- `otel-collector-prom-exporter` was `UP`
- `otel-collector-health` was `DOWN` with parse error (`INVALID`)

### Root cause
`13133` is a collector **health endpoint**, not a Prometheus metrics endpoint.
Prometheus attempted to parse health response as metrics and failed.

### Resolution
Kept/used `otel-collector:9464` as the valid metrics scrape target.
Stopped treating `13133` as metrics scrape target (health can be checked separately by probes).

---

## Issue 4: Prometheus rule pages (`/rules`, `/alerts`) were empty

### Symptom
No rule groups visible even after creating `alerts.yml`.

### Root causes
1. `alerts.yml` was not mounted in Prometheus container.
2. `volumes` block was accidentally put inside `prometheus.yml` (Prometheus config file), which is invalid syntax for Prometheus config.

### Resolution
- Keep `prometheus.yml` strictly Prometheus config only.
- Mount `alerts.yml` in `docker-compose.yml` under Prometheus service:
  - `./alerts.yml:/etc/prometheus/alerts.yml:ro`
- Ensure `prometheus.yml` includes:
  - `rule_files: ["/etc/prometheus/alerts.yml"]`
- Restart Prometheus container.

After fix, `/rules` and `/alerts` displayed correctly.

---

## Step 7.2 — Alert Rule Setup

## What we added

Created baseline rules in `alerts.yml` group `otel-baseline-alerts`:

1. **OTelCollectorPromExporterDown**
   - triggers when `up{job="otel-collector-prom-exporter"} == 0` for 2m

2. **NoAppTraffic**
   - triggers when `increase(http_requests_total[5m]) == 0` for 10m

3. **HighP95Latency**
   - triggers when p95 histogram latency exceeds threshold (`> 500ms`) for 5m

(5xx ratio alert left optional for future once status_code labeling is standardized.)

---

## Step 7.2 validation performed

1. Opened:
   - `/rules` -> confirmed `otel-baseline-alerts` loaded
   - `/alerts` -> confirmed state transitions visible

2. Confirmed observed behavior:
   - `NoAppTraffic` moved to `PENDING` when request traffic dropped
   - Other rules evaluated with `OK` state

This validated both rule loading and expression execution.

---

## Final status after Step 7.1 + 7.2

- Prometheus UI reachable on `:9090`
- Valid target `otel-collector:9464` is scraped successfully
- Alert rules loaded and evaluated
- Alert lifecycle (`inactive -> pending -> firing`) working as expected

---

## Current known-good files

- `docker-compose.yml`
  - includes Prometheus service and correct file mounts
- `prometheus.yml`
  - includes scrape target(s) and `rule_files`
- `alerts.yml`
  - includes baseline alert rules under `otel-baseline-alerts`

---

## Lessons learned

1. Security group rules are part of observability setup (not just app networking).
2. Container healthcheck command availability matters (`wget` may not exist).
3. Health endpoints and metrics endpoints are not interchangeable.
4. Prometheus config and Docker Compose config must stay separate in syntax and responsibility.
5. Rule pages being empty usually means either:
   - rule file not mounted,
   - rule file not referenced,
   - or Prometheus not restarted/reloaded.

---

## Suggested pre-check before Step 7.3 (Alertmanager)

- `/targets`: collector metrics target is `UP`
- `/rules`: baseline rule group present
- `/alerts`: at least one rule can become `PENDING` under expected conditions
- `docker compose ps`: all services healthy/up
```

