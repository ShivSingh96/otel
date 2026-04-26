```markdown
# OTel Flask Improvements Guide (Post-Setup)
*Production-hardening and troubleshooting notes from our working session.*

## Context

After the base setup was working (`Flask -> OTel Collector -> Jaeger`), we improved reliability and operability in incremental steps:

1. Run app with Gunicorn (instead of Flask dev server)
2. Run Gunicorn under systemd (survives SSH logout/reboot)
3. Add log-trace correlation (`trace_id`, `span_id`) in application logs

This guide captures:
- what we changed,
- errors faced,
- how we diagnosed and fixed them,
- and final validation checks.

---

## Improvement 1: Move from Flask dev server to Gunicorn

## Why
Flask’s built-in server is for development/testing only.  
Gunicorn provides a production-ready WSGI runtime with better worker/process handling.

## What we did
- Installed `gunicorn` in virtual env
- Started app with:

```bash
gunicorn -w 2 -k gthread --threads 4 -b 0.0.0.0:5000 app:app
```

## Error faced
`/` worked but `/work` returned `404 Not Found`.

## Root cause
The process bound to `:5000` was not the expected app/module version (or wrong Gunicorn module target), so the `/work` route was not registered in the active process.

## Resolution
- Verified correct module target (`app:app`)
- Ensured only one server process was active on port `5000`
- Restarted Gunicorn from the correct project directory

## Verification
- `curl http://localhost:5000/` => 200
- `curl http://localhost:5000/work` => 200
- Collector `debug` exporter showed spans for both routes

---

## Improvement 2: Run Gunicorn with systemd

## Why
Manual shell runs die when SSH session closes.  
`systemd` gives restart policy, boot persistence, and centralized logs (`journalctl`).

## What we did
Created `otel-flask.service` with:
- `WorkingDirectory=/home/ec2-user/otel-python`
- Gunicorn `ExecStart`
- OTel environment variables
- `Restart=always`

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable otel-flask
sudo systemctl start otel-flask
```

## Error faced
Service started fine, but expected app-level telemetry-enriched logs were not visible at first.

## Root cause
At that stage we were mostly seeing Gunicorn lifecycle logs (master/worker start), not necessarily app-request logs.

## Resolution
- Verified service actually started cleanly
- Generated traffic (`curl /`, `curl /work`) after startup
- Continued with explicit logging instrumentation in next step

## Verification
`journalctl -u otel-flask -f` showed:
- service restart success,
- Gunicorn workers booted,
- app handling requests once traffic generated.

---

## Improvement 3: Log correlation (`trace_id`, `span_id` in logs)

## Why
This is high-value for operations: jump from logs -> exact distributed trace.

## What we aimed for
Log lines like:

`INFO [trace_id=... span_id=... ...] otel-app - Inside /work custom span`

## Errors faced and fixes

### Error A: No `trace_id` / `span_id` in logs
**Observed:** only basic logs or Gunicorn logs, no correlated IDs.

**Root causes:**
1. Incorrect import usage in app:
   - used `from opentelemetry.instrumentation.logging import logging`  
   - should use Python stdlib `import logging` + `LoggingInstrumentor`
2. `systemd` environment formatting issues for log format string (`%` handling)
3. Request logs not emitted from app code path

**Resolutions:**
- Use stdlib logging and instrument logging correctly:
  - `import logging`
  - `from opentelemetry.instrumentation.logging import LoggingInstrumentor`
  - `LoggingInstrumentor().instrument(set_logging_format=True)`
- Add explicit `logger.info(...)` inside endpoints (`/`, `/work`)
- In `systemd`, escape `%` in `OTEL_PYTHON_LOG_FORMAT` as `%%(...)` when inline in `Environment="..."`

### Error B: `.env` values not taking effect
**Observed:** vars set in `.env`, but behavior unchanged.

**Root cause:** systemd does not automatically consume `.env` unless configured with `EnvironmentFile=...` or explicit `Environment=` lines.

**Resolution:**
- Keep vars directly in unit with `Environment="..."`, or
- use `EnvironmentFile=/path/to/.env` properly.

## Verification (successful)
`journalctl` showed app logs including:
- `trace_id=...`
- `span_id=...`
for endpoint logs such as:
- `Handling hello endpoint`
- `Inside /work custom span`

This confirmed log-trace correlation is now working.

---

## Final working state after improvements

- App served by Gunicorn (not Flask dev server)
- App managed by systemd (auto-start/restart behavior)
- Traces flowing through collector and visible in Jaeger
- Logs include trace correlation IDs for easier troubleshooting

---

## Known non-blocking notes

- Collector warning seen:
  - `"otlp" alias is deprecated; use "otlp_grpc" instead`
- Impact:
  - non-fatal; pipeline still worked.
- Recommended cleanup:
  - replace OTLP exporter alias with `otlp_grpc` in Collector config.

---

## Operational runbook (quick commands)

## Service lifecycle
```bash
sudo systemctl status otel-flask
sudo systemctl restart otel-flask
sudo systemctl stop otel-flask
sudo journalctl -u otel-flask -f
```

## App health
```bash
curl http://localhost:5000/
curl http://localhost:5000/work
```

## Collector health
```bash
sudo docker ps --filter name=otel-collector
sudo docker logs otel-collector
```

## Trace validation
- Generate `/work` traffic
- Check collector `debug` exporter for spans
- Open Jaeger UI, find service `hello-flask-service`

## Log-trace correlation validation
- Read `journalctl -u otel-flask -f`
- Copy `trace_id` from log line
- Search same trace in Jaeger

---

## Lessons learned (for future readers)

1. Validate one hop at a time: `app -> collector -> jaeger`.
2. New Collector versions changed/deprecated some exporters; check startup logs first.
3. In systemd units, `%` in format strings must be escaped as `%%`.
4. `.env` files do nothing for systemd unless explicitly wired.
5. Seeing only Gunicorn startup logs is normal; generate app traffic to validate app logger output.
6. Correlated logs (`trace_id/span_id`) dramatically reduce incident debugging time.
```

If you want, I can also give you a **shorter “one-page” version** of this for onboarding docs (less narrative, more checklist).