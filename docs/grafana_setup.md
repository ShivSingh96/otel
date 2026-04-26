What you’ve built so far isn’t just “Grafana setup.”
It’s the first piece of **operational memory** — the kind teams rely on when things go wrong at 2 AM and no one remembers what was done.

Let’s write this like engineers who expect failure — and prepare for it.

---

# 📘 Grafana + Prometheus + EC2 Metrics

### (Setup, Lessons, and Failures)

---

# 🧭 Objective

To build a **baseline observability dashboard** that answers three fundamental questions:

* Is the system receiving traffic?
* Is the system responding fast enough?
* Is the infrastructure healthy?

This was achieved using:

* Prometheus (metrics collection)
* Alertmanager (alerting)
* Grafana (visualization)
* Node Exporter (EC2 host metrics)

---

# 🏗️ Architecture Overview

```
App → OTel → Prometheus → Alertmanager → Slack
                          ↓
                       Grafana
                          ↓
                    Node Exporter (EC2)
```

This flow matters.
If you don’t understand the flow, debugging becomes guessing.

---

# ⚙️ Step 1 — Grafana Setup

Added Grafana service in `docker-compose.yml`:

```yaml
grafana:
  image: grafana/grafana:latest
  container_name: grafana
  ports:
    - "3000:3000"
  environment:
    - GF_SECURITY_ADMIN_USER=admin
    - GF_SECURITY_ADMIN_PASSWORD=admin
  volumes:
    - grafana-storage:/var/lib/grafana

volumes:
  grafana-storage:
```

Started service:

```bash
docker-compose up -d grafana
```

Access:

```
http://<EC2-IP>:3000
```

---

# 🔗 Step 2 — Prometheus as Data Source

Configured in Grafana:

```
URL: http://prometheus:9090
```

✔️ This works only if:

* Grafana and Prometheus are on same Docker network
* Service name `prometheus` is resolvable

---

# 📊 Step 3 — Dashboard Panels

## 1. Request Rate

```promql
sum(rate(http_requests_total[1m]))
```

Purpose:

* Detect traffic drop or surge

---

## 2. p95 Latency

```promql
histogram_quantile(
  0.95,
  sum(rate(http_request_duration_ms_bucket[5m])) by (le)
)
```

Purpose:

* Detect performance degradation early

---

## 3. Alert Status

```promql
ALERTS{alertstate="firing"}
```

Purpose:

* Surface active incidents

---

# 🖥️ Step 4 — EC2 Metrics via Node Exporter

Node Exporter exposes system-level metrics:

### Installed & started Node Exporter

```bash
./node_exporter &
```

Or via systemd (recommended for production)

---

## Prometheus scrape config

```yaml
- job_name: "node-exporter"
  static_configs:
    - targets: ["<EC2-IP>:9100"]
```

---

## Useful EC2 Metrics

### CPU Usage

```promql
100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[1m])) * 100)
```

---

### Memory Usage

```promql
(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes)
/
node_memory_MemTotal_bytes * 100
```

---

### Disk Usage

```promql
(node_filesystem_size_bytes - node_filesystem_free_bytes)
/
node_filesystem_size_bytes * 100
```

---

# 🚨 Errors We Faced (and what they really meant)

This is the most important section.
Failures teach more than success ever will.

---

## ❌ 1. Alerts visible but NOT sent to Slack

### Symptom:

* Alert visible in Alertmanager UI
* No Slack notification

### Root Cause:

* Alertmanager running **old config**
* Receiver = `default-receiver`
* Slack config never applied

### Proof:

```bash
curl /api/v2/status
```

Showed wrong config.

### Fix:

* Restarted docker-compose
* Ensured correct config mounted

---

## ❌ 2. Webhook DNS failure

### Error:

```
lookup example-webhook.local: no such host
```

### Meaning:

* Alertmanager trying to hit dummy webhook
* Slack not even involved

### Lesson:

> Always verify which receiver is active before debugging integrations

---

## ❌ 3. Config drift (silent killer)

### Reality:

* Local config ≠ running config

### Fix:

* Verified using:

```bash
curl http://alertmanager:9093/api/v2/status
```

### Lesson:

> Never trust your files. Trust the running system.

---

## ❌ 4. Docker networking confusion

### Risk:

* Grafana couldn’t reach Prometheus if wrong URL used

### Fix:

* Use service name (`prometheus:9090`)
* Not localhost

---

## ❌ 5. Metrics disappeared (earlier issue)

### Symptom:

* `http_requests_total` stopped showing

### Likely Cause:

* Misconfigured OTel pipeline
* Exporter or instrumentation broken

### Lesson:

> Observability pipelines fail silently — always validate metrics after changes

---

# 🧠 Key Learnings

### 1. Observability is a chain

Break one link → everything looks fine but isn’t

---

### 2. Restart ≠ fix

Restart only hides the real issue:
👉 **state inconsistency**

---

### 3. Dashboards are not decoration

Each panel must answer a question

---

### 4. Alerts without visualization are blind

Visualization without alerts is lazy

You need both.

---

# 🔮 What This Enables (Future Steps)

Now you have:

* Metrics ✅
* Alerts ✅
* Visualization ✅

Next evolution:

### 🔹 Add Logs (Loki / ELK)

→ Understand “what happened”

### 🔹 Add Traces (Tempo / Jaeger)

→ Understand “where it broke”

### 🔹 Add AI Layer

→ Understand “why it happened”

---

# 🧭 Final Reflection

You didn’t just “set up Grafana.”

You built:

* A feedback loop
* A debugging surface
* A foundation for intelligent systems

Most teams stop here.

You won’t.

---

If you want next:
👉 I can give you a **production-grade Grafana dashboard JSON (import-ready)**
👉 Or we move to **logs correlation (Loki setup)** — where things get truly powerful
