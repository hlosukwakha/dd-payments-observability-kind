import os, random, logging, requests
from fastapi import FastAPI
from pydantic import BaseModel
from datadog import DogStatsd
from ddtrace import tracer
from .obs import init_observability, current_dd_ids, base_fields

init_observability()
LOG = logging.getLogger("fraud_service")

DD_SERVICE = os.getenv("DD_SERVICE","fraud-service")
statsd = DogStatsd(host=os.getenv("DD_AGENT_HOST","127.0.0.1"), port=int(os.getenv("DD_DOGSTATSD_PORT","8125")),
                   constant_tags=[f"service:{DD_SERVICE}", f"env:{os.getenv('DD_ENV','dev')}", f"version:{os.getenv('DD_VERSION','0.1.0')}"])

JIRA_POLLER_URL = os.getenv("JIRA_POLLER_URL","http://jira-poller:8000")
FRAUD_CONFIRM_RATE = float(os.getenv("FRAUD_CONFIRM_RATE","0.35"))
FRAUD_REASONS = ["incorrect credit card","incorrect PIN number","transaction above limit","duplicate transaction","suspicious transaction"]

app = FastAPI(title="Fraud Service", version=os.getenv("DD_VERSION","0.1.0"))

class Req(BaseModel):
    trace_id: str
    payment_id: str
    customer_id: str
    bank_id: str
    amount: float
    issue_key: str

@app.post("/check")
def check(req: Req):
    with tracer.trace("fraud.check", service=DD_SERVICE, resource="POST /check"):
        fraudulent = random.random() < FRAUD_CONFIRM_RATE
        reason = random.choice(FRAUD_REASONS)
        if fraudulent:
            statsd.increment("fraud.check.rejected", tags=[f"fraud_reason:{reason}", f"bank:{req.bank_id}"])
            comment = "Confirmed fraudulent activity. Please escalate to Product Team"
            LOG.warning("fraud_rejected", extra={**base_fields(DD_SERVICE), **current_dd_ids(), "payment_id": req.payment_id, "customer_id": req.customer_id, "bank_id": req.bank_id, "amount": req.amount, "status":"fraud_rejected", "reason": reason})
        else:
            statsd.increment("fraud.check.approved", tags=[f"bank:{req.bank_id}"])
            comment = "Transaction not fraudulent, please complete it"
            LOG.info("fraud_approved", extra={**base_fields(DD_SERVICE), **current_dd_ids(), "payment_id": req.payment_id, "customer_id": req.customer_id, "bank_id": req.bank_id, "amount": req.amount, "status":"fraud_approved"})

        try:
            requests.post(f"{JIRA_POLLER_URL.rstrip('/')}/jira/comment", json={"issue_key": req.issue_key, "comment": comment}, timeout=10).raise_for_status()
        except Exception as e:
            LOG.error("jira_comment_error", extra={**base_fields(DD_SERVICE), **current_dd_ids(), "status":"jira_comment_error", "reason": str(e)})
        return {"fraudulent": fraudulent, "reason": reason, "comment": comment}
