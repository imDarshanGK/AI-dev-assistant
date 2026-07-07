import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

def setup_tracing(app_name: str = "qyverix-ai"):
    # Check if tracing is turned on in the environment
    if os.getenv("OTEL_ENABLED", "false").lower() != "true":
        return None

    # Set up the resource (tells us what app is sending the data)
    resource = Resource.create({"service.name": app_name})
    provider = TracerProvider(resource=resource)
    
    # Set up the exporter (this sends data to Jaeger)
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    
    # Process spans in batches for better performance
    span_processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(span_processor)
    
    # Make this the global tracer
    trace.set_tracer_provider(provider)
    return trace.get_tracer(__name__)