import logging
import time
from flask import Flask
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# for P95 latency
from opentelemetry.sdk.metrics.view import View
from opentelemetry.sdk.metrics.aggregation import ExplicitBucketHistogramAggregation

# Inject trace/span context into Python logging records
LoggingInstrumentor().instrument(set_logging_format=True)

resource = Resource.create(
    {
        "service.name": "hello-flask-service",
        "service.version": "1.0.0",
        "deployment.environment": "dev",
    }
)

# ---- Traces (to Collector host port 4319) ----
trace_provider = TracerProvider(resource=resource)
trace.set_tracer_provider(trace_provider)

span_exporter = OTLPSpanExporter(
    endpoint="http://localhost:4319",
    insecure=True,
)
trace_provider.add_span_processor(BatchSpanProcessor(span_exporter))

# ---- Metrics (to Collector host port 4319) ----
metric_reader = PeriodicExportingMetricReader(
    OTLPMetricExporter(endpoint="http://localhost:4319", insecure=True)
)
meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
metrics.set_meter_provider(meter_provider)
meter = metrics.get_meter("otel-app-meter")

request_counter = meter.create_counter(
    "http_requests_total",
    unit="1",
    description="Total HTTP requests handled by Flask app",
)

request_duration_ms = meter.create_histogram(
    "http_request_duration_ms",
    unit="ms",
    description="Request duration in milliseconds",
)

app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)

logger = logging.getLogger("otel-app")
logger.setLevel(logging.INFO)


@app.route("/")
def hello():
    start = time.perf_counter()
    try:
        request_counter.add(1, {"route": "/", "method": "GET"})
        logger.info("Handling hello endpoint")
        return "Hello, World from Flask + OpenTelemetry!"
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        request_duration_ms.record(elapsed_ms, {"route": "/", "method": "GET"})


@app.route("/work")
def work():
    start = time.perf_counter()
    try:
        request_counter.add(1, {"route": "/work", "method": "GET"})
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("manual-work-span"):
            logger.info("Inside /work custom span")
            return "Did some work inside a custom span."
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        request_duration_ms.record(elapsed_ms, {"route": "/work", "method": "GET"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)