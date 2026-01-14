import os, json, logging, secrets, pathlib, requests
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from datadog import DogStatsd
from ddtrace import tracer
from .obs import init_observability, current_dd_ids, base_fields
from .banks import BANKS

init_observability()
LOG = logging.getLogger("web_frontend")

DD_SERVICE = os.getenv("DD_SERVICE","web-frontend")
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL","http://auth-service:8000")
PAYMENT_SERVICE_URL = os.getenv("PAYMENT_SERVICE_URL","http://payment-service:8000")

RUM = {
  "applicationId": os.getenv("DD_RUM_APPLICATION_ID",""),
  "clientToken": os.getenv("DD_RUM_CLIENT_TOKEN",""),
  "site": os.getenv("DD_RUM_SITE","datadoghq.eu"),
  "service": os.getenv("DD_RUM_SERVICE","web-frontend"),
  "env": os.getenv("DD_RUM_ENV","dev"),
  "version": os.getenv("DD_RUM_VERSION","0.1.0"),
  "sessionReplaySampleRate": int(os.getenv("DD_RUM_SESSION_REPLAY_SAMPLE_RATE","100")),
}

statsd = DogStatsd(host=os.getenv("DD_AGENT_HOST","127.0.0.1"), port=int(os.getenv("DD_DOGSTATSD_PORT","8125")),
                   constant_tags=[f"service:{DD_SERVICE}", f"env:{os.getenv('DD_ENV','dev')}", f"version:{os.getenv('DD_VERSION','0.1.0')}"])

app = FastAPI(title="Web Frontend", version=os.getenv("DD_VERSION","0.1.0"))
SESSIONS = {}

class LoginReq(BaseModel):
    username: str
    password: str

class PayReq(BaseModel):
    bank_id: str
    amount: float

def _index_html() -> str:
    html_path = pathlib.Path(__file__).parent / "web" / "index.html"
    return html_path.read_text(encoding="utf-8")

@app.get("/", response_class=HTMLResponse)
def index():
    html = _index_html().replace("__RUM_CONFIG__", json.dumps(RUM))
    return HTMLResponse(html)

@app.get("/api/banks")
def banks():
    return {"banks": BANKS}

@app.post("/api/login")
def login(req: LoginReq, response: Response):
    with tracer.trace("web.login", service=DD_SERVICE, resource="POST /api/login"):
        try:
            r = requests.post(f"{AUTH_SERVICE_URL.rstrip('/')}/auth/login", json=req.dict(), timeout=10)
        except Exception as e:
            LOG.error("auth_upstream_error", extra={**base_fields(DD_SERVICE), **current_dd_ids(), "status":"auth_upstream_error", "reason": str(e)})
            raise HTTPException(status_code=502, detail="auth_upstream_error")

        if r.status_code != 200:
            statsd.increment("web.auth.failed")
            return JSONResponse(status_code=401, content=r.json())

        cid = r.json()["customer_id"]
        sid = secrets.token_urlsafe(16)
        SESSIONS[sid] = cid
        response.set_cookie("session_id", sid, httponly=False)
        statsd.increment("web.auth.ok")
        LOG.info("auth_ok", extra={**base_fields(DD_SERVICE), **current_dd_ids(), "customer_id": cid, "status":"auth_ok"})
        return {"ok": True, "customer_id": cid}

def _require_session(request: Request) -> str:
    sid = request.cookies.get("session_id")
    if not sid or sid not in SESSIONS:
        raise HTTPException(status_code=401, detail="not_authenticated")
    return SESSIONS[sid]

@app.post("/api/pay")
def pay(req: PayReq, request: Request):
    with tracer.trace("web.pay", service=DD_SERVICE, resource="POST /api/pay"):
        cid = _require_session(request)
        try:
            r = requests.post(f"{PAYMENT_SERVICE_URL.rstrip('/')}/pay", json={"customer_id": cid, "bank_id": req.bank_id, "amount": req.amount}, timeout=15)
        except Exception as e:
            LOG.error("payment_upstream_error", extra={**base_fields(DD_SERVICE), **current_dd_ids(), "customer_id": cid, "bank_id": req.bank_id, "amount": req.amount, "status":"payment_upstream_error", "reason": str(e)})
            raise HTTPException(status_code=502, detail="payment_upstream_error")

        if r.status_code != 200:
            statsd.increment("web.payment.error", tags=[f"bank:{req.bank_id}"])
            return JSONResponse(status_code=r.status_code, content=r.json())

        statsd.increment("web.payment.ok", tags=[f"bank:{req.bank_id}"])
        LOG.info("payment_ok", extra={**base_fields(DD_SERVICE), **current_dd_ids(), "customer_id": cid, "bank_id": req.bank_id, "amount": req.amount, "status":"payment_ok"})
        return r.json()
