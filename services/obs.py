import os
import logging
from pythonjsonlogger import jsonlogger
from ddtrace import tracer, patch_all

def init_observability():
    patch_all()

    root = logging.getLogger()
    root.handlers = []
    root.setLevel(os.getenv("LOG_LEVEL", "INFO"))

    handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s "
        "%(dd.trace_id)s %(dd.span_id)s %(dd.service)s %(dd.env)s %(dd.version)s "
        "%(service)s %(env)s %(version)s %(bank_id)s %(customer_id)s %(payment_id)s %(amount)s %(status)s %(reason)s"
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)

def current_dd_ids():
    span = tracer.current_span()
    if not span:
        return {"dd.trace_id": "0", "dd.span_id": "0"}
    ctx = span.context
    return {"dd.trace_id": str(ctx.trace_id), "dd.span_id": str(ctx.span_id)}

def base_fields(service: str):
    return {"service": service, "env": os.getenv("DD_ENV","dev"), "version": os.getenv("DD_VERSION","0.1.0")}
