import os, random, logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datadog import DogStatsd
from ddtrace import tracer
from .obs import init_observability, current_dd_ids, base_fields
import os, random, logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datadog import DogStatsd
from ddtrace import tracer
from .obs import init_observability, current_dd_ids, base_fields

init_observability()
LOG = logging.getLogger("llm_service")

DD_SERVICE = os.getenv("DD_SERVICE","llm-service")
statsd = DogStatsd(host=os.getenv("DD_AGENT_HOST","127.0.0.1"), port=int(os.getenv("DD_DOGSTATSD_PORT","8125")),
                   constant_tags=[f"service:{DD_SERVICE}", f"env:{os.getenv('DD_ENV','dev')}", f"version:{os.getenv('DD_VERSION','0.1.0')}"])

# Datadog LLM Observability SDK (ddtrace>=2.11.0)
from ddtrace.llmobs import LLMObs
from ddtrace.llmobs.decorators import llm, workflow

LLMObs.enable(service=DD_SERVICE)

app = FastAPI(title="LLM Service (Simulated)", version=os.getenv("DD_VERSION","0.1.0"))

class PromptReq(BaseModel):
    prompt: str

@llm(model_name="local-rule-model", model_provider="local", name="generate_text")
def _simulate_llm(prompt: str) -> str:
    if random.random() < 0.08:
        raise RuntimeError("simulated_model_error")
    if "summarize" in prompt.lower():
        return "Summary: " + prompt[:160].strip()
    if "classify" in prompt.lower():
        return "Label: neutral"
    return "Response: " + prompt[::-1][:220]

@app.post("/llm/generate")
def generate(req: PromptReq):
    with workflow(name="llm_request"):
        with tracer.trace("llm.endpoint", service=DD_SERVICE, resource="POST /llm/generate"):
            try:
                out = _simulate_llm(req.prompt)
                statsd.increment("llm.request.ok")
                LOG.info("llm_ok", extra={**base_fields(DD_SERVICE), **current_dd_ids(), "status":"llm_ok"})
                return {"ok": True, "output": out}
            except Exception as e:
                statsd.increment("llm.request.error", tags=[f"error:{type(e).__name__}"])
                LOG.error("llm_error", extra={**base_fields(DD_SERVICE), **current_dd_ids(), "status":"llm_error", "reason": str(e)})
                raise HTTPException(status_code=502, detail={"error":"llm_error","reason":str(e)})


init_observability()
LOG = logging.getLogger("llm_service")

DD_SERVICE = os.getenv("DD_SERVICE","llm-service")
statsd = DogStatsd(host=os.getenv("DD_AGENT_HOST","127.0.0.1"), port=int(os.getenv("DD_DOGSTATSD_PORT","8125")),
                   constant_tags=[f"service:{DD_SERVICE}", f"env:{os.getenv('DD_ENV','dev')}", f"version:{os.getenv('DD_VERSION','0.1.0')}"])

# Datadog LLM Observability SDK (ddtrace>=2.11.0)
from ddtrace.llmobs import LLMObs
from ddtrace.llmobs.decorators import llm, workflow

LLMObs.enable(service=DD_SERVICE)

app = FastAPI(title="LLM Service (Simulated)", version=os.getenv("DD_VERSION","0.1.0"))

class PromptReq(BaseModel):
    prompt: str

@llm(model_name="local-rule-model", model_provider="local", name="generate_text")
def _simulate_llm(prompt: str) -> str:
    if random.random() < 0.08:
        raise RuntimeError("simulated_model_error")
    if "summarize" in prompt.lower():
        return "Summary: " + prompt[:160].strip()
    if "classify" in prompt.lower():
        return "Label: neutral"
    return "Response: " + prompt[::-1][:220]

@app.post("/llm/generate")
@workflow(name="llm_request")
def generate(req: PromptReq):
    with tracer.trace("llm.endpoint", service=DD_SERVICE, resource="POST /llm/generate"):
        try:
            out = _simulate_llm(req.prompt)
            statsd.increment("llm.request.ok")
            LOG.info("llm_ok", extra={**base_fields(DD_SERVICE), **current_dd_ids(), "status":"llm_ok"})
            return {"ok": True, "output": out}
        except Exception as e:
            statsd.increment("llm.request.error", tags=[f"error:{type(e).__name__}"])
            LOG.error("llm_error", extra={**base_fields(DD_SERVICE), **current_dd_ids(), "status":"llm_error", "reason": str(e)})
            raise HTTPException(status_code=502, detail={"error":"llm_error","reason":str(e)})
