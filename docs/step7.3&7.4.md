Great — next is **Step 7.4: real notification channel**.

Fastest path is **Slack webhook**. (If you prefer email/PagerDuty, say so and I’ll switch.)

## Step 7.4: Slack alert notifications

### 1) Create Slack Incoming Webhook
- In Slack: **Apps -> Incoming Webhooks**
- Choose channel
- Copy webhook URL (looks like `https://hooks.slack.com/services/...`)

### 2) Update `alertmanager.yml`
Replace receiver section with:

```yaml
global:
  resolve_timeout: 5m

route:
  receiver: "slack-notifications"
  group_by: ["alertname", "job"]
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 2h

receivers:
  - name: "slack-notifications"
    slack_configs:
      - api_url: "https://hooks.slack.com/services/XXX/YYY/ZZZ"
        channel: "#alerts"
        send_resolved: true
        title: "[{{ .Status | toUpper }}] {{ .CommonLabels.alertname }}"
        text: >-
          {{ range .Alerts -}}
          *Alert:* {{ .Annotations.summary }}
          *Description:* {{ .Annotations.description }}
          *Severity:* {{ .Labels.severity }}
          *Instance:* {{ .Labels.instance }}
          {{ end }}
```

### 3) Restart Alertmanager
```bash
docker compose up -d alertmanager
```

### 4) Verify in UI
- Open `http://<EC2_PUBLIC_IP>:9093`
- Check **Status** for config load success (no errors)

### 5) Trigger a test alert
Use temporary rule in `alerts.yml`:

```yaml
- alert: AlwaysFiringTest
  expr: vector(1)
  for: 1m
  labels:
    severity: warning
  annotations:
    summary: "Always firing test alert"
    description: "Test alert for Slack integration"
```

Restart/reload Prometheus, wait ~1 minute, confirm message arrives in Slack.

### 6) Cleanup
- Remove `AlwaysFiringTest` rule after verification.

---

If you want, next step after this is **Step 8: dashboarding (Grafana)** with a starter dashboard for request rate, p95 latency, and alert status.