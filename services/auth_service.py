import os, random, hashlib, logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datadog import DogStatsd
from ddtrace import tracer
from .obs import init_observability, current_dd_ids, base_fields

init_observability()
LOG = logging.getLogger("auth_service")

DD_SERVICE = os.getenv("DD_SERVICE", "auth-service")
statsd = DogStatsd(
    host=os.getenv("DD_AGENT_HOST", "127.0.0.1"),
    port=int(os.getenv("DD_DOGSTATSD_PORT", "8125")),
    constant_tags=[f"service:{DD_SERVICE}", f"env:{os.getenv('DD_ENV','dev')}", f"version:{os.getenv('DD_VERSION','0.1.0')}"],
)

AUTH_FAIL_RATE = float(os.getenv("AUTH_FAIL_RATE", "0.12"))
FAIL_REASONS = ["Incorrect password", "incorrect username", "account not found", "Unknown device"]

app = FastAPI(title="Auth Service", version=os.getenv("DD_VERSION","0.1.0"))

class LoginReq(BaseModel):
    username: str
    password: str

def customer_id(username: str) -> str:
    return "cust_" + hashlib.sha256(username.encode()).hexdigest()[:10]

@app.post("/auth/login")
def login(req: LoginReq):
    with tracer.trace("auth.login", service=DD_SERVICE, resource="POST /auth/login"):
        cid = customer_id(req.username)

        if random.random() < AUTH_FAIL_RATE:
            reason = random.choice(FAIL_REASONS)
            statsd.increment("auth.failed", tags=[f"reason:{reason}"])
            LOG.warning("auth_error", extra={**base_fields(DD_SERVICE), **current_dd_ids(), "customer_id": cid, "status": "auth_error", "reason": reason})
            raise HTTPException(status_code=401, detail={"error":"auth_error","reason":reason,"customer_id":cid})

        statsd.increment("auth.ok")
        LOG.info("auth_ok", extra={**base_fields(DD_SERVICE), **current_dd_ids(), "customer_id": cid, "status": "auth_ok"})
        return {"ok": True, "customer_id": cid}
