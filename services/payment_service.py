import os, time, uuid, random, logging, requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datadog import DogStatsd
from ddtrace import tracer
from .obs import init_observability, current_dd_ids, base_fields
from .banks import BANKS

init_observability()
LOG = logging.getLogger("payment_service")

DD_SERVICE = os.getenv("DD_SERVICE","payment-service")
statsd = DogStatsd(host=os.getenv("DD_AGENT_HOST","127.0.0.1"), port=int(os.getenv("DD_DOGSTATSD_PORT","8125")),
                   constant_tags=[f"service:{DD_SERVICE}", f"env:{os.getenv('DD_ENV','dev')}", f"version:{os.getenv('DD_VERSION','0.1.0')}"])

FRAUD_SERVICE_URL = os.getenv("FRAUD_SERVICE_URL","http://fraud-service:8000")
JIRA_POLLER_URL = os.getenv("JIRA_POLLER_URL","http://jira-poller:8000")

PAYMENT_FAIL_RATE = float(os.getenv("PAYMENT_FAIL_RATE","0.15"))
PAYMENT_SUSPECTED_FRAUD_RATE = float(os.getenv("PAYMENT_SUSPECTED_FRAUD_RATE","0.05"))

FAIL_REASONS = ["Request timeout","Insufficient funds","Invalid recipient","incorrect card details"]
SUSPECTED_FRAUD_REASON = "Suspected Fraud"

app = FastAPI(title="Payment Service", version=os.getenv("DD_VERSION","0.1.0"))

class PayReq(BaseModel):
    customer_id: str
    bank_id: str
    amount: float

def bank_name(bank_id: str) -> str:
    for b in BANKS:
        if b["id"] == bank_id:
            return b["name"]
    return bank_id

@app.get("/banks")
def banks():
    return {"banks": BANKS}

@app.post("/pay")
def pay(req: PayReq):
    with tracer.trace("payment.pay", service=DD_SERVICE, resource="POST /pay"):
        payment_id = str(uuid.uuid4())
        statsd.increment("payment.created", tags=[f"bank:{req.bank_id}"])
        LOG.info("payment_created", extra={**base_fields(DD_SERVICE), **current_dd_ids(), "customer_id": req.customer_id, "payment_id": payment_id, "bank_id": req.bank_id, "amount": req.amount, "status":"created"})

        time.sleep(random.uniform(0.05, 0.25))

        # Suspected fraud flow
        if random.random() < PAYMENT_SUSPECTED_FRAUD_RATE:
            trace_id = current_dd_ids().get("dd.trace_id","0")
            issue_key = ""
            try:
                r = requests.post(f"{JIRA_POLLER_URL.rstrip('/')}/jira/create_suspected_fraud", json={
                    "trace_id": trace_id, "payment_id": payment_id, "customer_id": req.customer_id, "bank_id": req.bank_id, "amount": req.amount, "reason": SUSPECTED_FRAUD_REASON
                }, timeout=10)
                r.raise_for_status()
                issue_key = r.json().get("issue_key","")
            except Exception as e:
                LOG.error("jira_create_error", extra={**base_fields(DD_SERVICE), **current_dd_ids(), "customer_id": req.customer_id, "payment_id": payment_id, "bank_id": req.bank_id, "amount": req.amount, "status":"jira_create_error", "reason": str(e)})

            fraud = None
            try:
                fr = requests.post(f"{FRAUD_SERVICE_URL.rstrip('/')}/check", json={
                    "trace_id": trace_id, "payment_id": payment_id, "customer_id": req.customer_id, "bank_id": req.bank_id, "amount": req.amount, "issue_key": issue_key
                }, timeout=10)
                fr.raise_for_status()
                fraud = fr.json()
            except Exception as e:
                LOG.error("fraud_call_error", extra={**base_fields(DD_SERVICE), **current_dd_ids(), "customer_id": req.customer_id, "payment_id": payment_id, "bank_id": req.bank_id, "amount": req.amount, "status":"fraud_call_error", "reason": str(e)})

            if fraud and fraud.get("fraudulent") is False:
                statsd.increment("payment.settled", tags=[f"bank:{req.bank_id}"])
                LOG.info("payment_settled", extra={**base_fields(DD_SERVICE), **current_dd_ids(), "customer_id": req.customer_id, "payment_id": payment_id, "bank_id": req.bank_id, "amount": req.amount, "status":"settled"})
                return {"ok": True, "payment_id": payment_id, "status": "settled", "bank_id": req.bank_id, "bank_name": bank_name(req.bank_id)}

            statsd.increment("payment.failed", tags=[f"reason:{SUSPECTED_FRAUD_REASON}", f"bank:{req.bank_id}"])
            LOG.error("payment_failed", extra={**base_fields(DD_SERVICE), **current_dd_ids(), "customer_id": req.customer_id, "payment_id": payment_id, "bank_id": req.bank_id, "amount": req.amount, "status":"failed", "reason": SUSPECTED_FRAUD_REASON})
            raise HTTPException(status_code=502, detail={"error":"payment_failed","reason":SUSPECTED_FRAUD_REASON,"payment_id":payment_id})

        # Normal failures
        if random.random() < PAYMENT_FAIL_RATE:
            reason = random.choice(FAIL_REASONS)
            statsd.increment("payment.failed", tags=[f"reason:{reason}", f"bank:{req.bank_id}"])
            LOG.error("payment_failed", extra={**base_fields(DD_SERVICE), **current_dd_ids(), "customer_id": req.customer_id, "payment_id": payment_id, "bank_id": req.bank_id, "amount": req.amount, "status":"failed", "reason": reason})
            raise HTTPException(status_code=502, detail={"error":"payment_failed","reason":reason,"payment_id":payment_id})

        statsd.increment("payment.settled", tags=[f"bank:{req.bank_id}"])
        LOG.info("payment_settled", extra={**base_fields(DD_SERVICE), **current_dd_ids(), "customer_id": req.customer_id, "payment_id": payment_id, "bank_id": req.bank_id, "amount": req.amount, "status":"settled"})
        return {"ok": True, "payment_id": payment_id, "status":"settled", "bank_id": req.bank_id, "bank_name": bank_name(req.bank_id)}
