import os, time, threading, logging, requests
from requests.auth import HTTPBasicAuth
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datadog import DogStatsd
from ddtrace import tracer
from .obs import init_observability, current_dd_ids, base_fields

init_observability()
LOG = logging.getLogger("jira_poller")

DD_SERVICE = os.getenv("DD_SERVICE", "jira-poller")
statsd = DogStatsd(
    host=os.getenv("DD_AGENT_HOST", "127.0.0.1"),
    port=int(os.getenv("DD_DOGSTATSD_PORT", "8125")),
    constant_tags=[
        f"service:{DD_SERVICE}",
        f"env:{os.getenv('DD_ENV', 'dev')}",
        f"version:{os.getenv('DD_VERSION', '0.1.0')}",
    ],
)

JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "").strip()
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "").strip()
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "").strip()
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "PER").strip()
JIRA_ISSUE_TYPE = os.getenv("JIRA_ISSUE_TYPE", "Task").strip()
POLL_INTERVAL = int(os.getenv("JIRA_POLL_INTERVAL_SECONDS", "1800"))

# Optional: allow disabling poller thread in some environments/tests
POLL_ENABLED = os.getenv("JIRA_POLL_ENABLED", "true").lower() in ("1", "true", "yes", "y")

app = FastAPI(title="Jira Poller", version=os.getenv("DD_VERSION", "0.1.0"))


class CreateReq(BaseModel):
    trace_id: str
    payment_id: str
    customer_id: str
    bank_id: str
    amount: float
    reason: str


class CommentReq(BaseModel):
    issue_key: str
    comment: str


def _auth() -> HTTPBasicAuth:
    if not (JIRA_EMAIL and JIRA_API_TOKEN):
        raise RuntimeError("Missing Jira credentials (JIRA_EMAIL/JIRA_API_TOKEN)")
    return HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)


def _require_jira_config() -> None:
    missing = []
    if not JIRA_BASE_URL:
        missing.append("JIRA_BASE_URL")
    if not JIRA_PROJECT_KEY:
        missing.append("JIRA_PROJECT_KEY")
    if not JIRA_EMAIL:
        missing.append("JIRA_EMAIL")
    if not JIRA_API_TOKEN:
        missing.append("JIRA_API_TOKEN")
    if missing:
        raise RuntimeError(f"Missing Jira config: {', '.join(missing)}")


def _headers() -> dict:
    return {"Accept": "application/json", "Content-Type": "application/json"}


@app.post("/jira/create_suspected_fraud")
def create(req: CreateReq):
    with tracer.trace(
        "jira.create_issue", service=DD_SERVICE, resource="POST /jira/create_suspected_fraud"
    ):
        try:
            _require_jira_config()
        except Exception as e:
            statsd.increment("jira.create.error", tags=["reason:missing_config"])
            LOG.error(
                "jira_create_error_missing_config",
                extra={**base_fields(DD_SERVICE), **current_dd_ids(), "status": "jira_create_error", "reason": str(e)},
            )
            raise HTTPException(status_code=500, detail=str(e))

        summary = f"Suspected Fraud {req.trace_id}"
        payload = {
            "fields": {
                "project": {"key": JIRA_PROJECT_KEY},
                "summary": summary,
                "issuetype": {"name": JIRA_ISSUE_TYPE},
                # Atlassian Document Format (ADF) for Cloud description
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {"type": "paragraph", "content": [{"type": "text", "text": f"Trace ID: {req.trace_id}"}]},
                        {"type": "paragraph", "content": [{"type": "text", "text": f"Payment ID: {req.payment_id}"}]},
                        {"type": "paragraph", "content": [{"type": "text", "text": f"Customer ID: {req.customer_id}"}]},
                        {"type": "paragraph", "content": [{"type": "text", "text": f"Bank: {req.bank_id}"}]},
                        {"type": "paragraph", "content": [{"type": "text", "text": f"Amount: {req.amount}"}]},
                        {"type": "paragraph", "content": [{"type": "text", "text": f"Reason: {req.reason}"}]},
                    ],
                },
            }
        }

        url = f"{JIRA_BASE_URL.rstrip('/')}/rest/api/3/issue"
        try:
            r = requests.post(url, auth=_auth(), headers=_headers(), json=payload, timeout=15)
            # If Jira returns a helpful JSON error, surface it in logs
            if not r.ok:
                try:
                    jira_err = r.json()
                except Exception:
                    jira_err = {"text": r.text}
                LOG.error(
                    "jira_create_failed",
                    extra={
                        **base_fields(DD_SERVICE),
                        **current_dd_ids(),
                        "status": "jira_create_failed",
                        "reason": f"HTTP {r.status_code}",
                        "jira_error": jira_err,
                    },
                )
                r.raise_for_status()

            issue_key = (r.json() or {}).get("key", "")
            statsd.increment("jira.create.ok")
            LOG.info(
                "jira_create_ok",
                extra={
                    **base_fields(DD_SERVICE),
                    **current_dd_ids(),
                    "status": "jira_create_ok",
                    "customer_id": req.customer_id,
                    "payment_id": req.payment_id,
                    "bank_id": req.bank_id,
                },
            )
            return {"issue_key": issue_key}
        except requests.HTTPError as e:
            statsd.increment("jira.create.error", tags=["reason:http_error"])
            LOG.exception("jira_create_http_error")
            raise HTTPException(status_code=502, detail=str(e))
        except Exception as e:
            statsd.increment("jira.create.error", tags=["reason:exception"])
            LOG.exception("jira_create_error")
            raise HTTPException(status_code=502, detail=str(e))


@app.post("/jira/comment")
def comment(req: CommentReq):
    with tracer.trace("jira.comment", service=DD_SERVICE, resource="POST /jira/comment"):
        try:
            _require_jira_config()
        except Exception as e:
            statsd.increment("jira.comment.error", tags=["reason:missing_config"])
            LOG.error(
                "jira_comment_error_missing_config",
                extra={**base_fields(DD_SERVICE), **current_dd_ids(), "status": "jira_comment_error", "reason": str(e)},
            )
            raise HTTPException(status_code=500, detail=str(e))

        payload = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": req.comment}]}],
            }
        }

        url = f"{JIRA_BASE_URL.rstrip('/')}/rest/api/3/issue/{req.issue_key}/comment"
        try:
            r = requests.post(url, auth=_auth(), headers=_headers(), json=payload, timeout=15)
            if not r.ok:
                try:
                    jira_err = r.json()
                except Exception:
                    jira_err = {"text": r.text}
                LOG.error(
                    "jira_comment_failed",
                    extra={
                        **base_fields(DD_SERVICE),
                        **current_dd_ids(),
                        "status": "jira_comment_failed",
                        "reason": f"HTTP {r.status_code}",
                        "jira_error": jira_err,
                        "issue_key": req.issue_key,
                    },
                )
                r.raise_for_status()

            statsd.increment("jira.comment.ok")
            LOG.info(
                "jira_comment_ok",
                extra={**base_fields(DD_SERVICE), **current_dd_ids(), "status": "jira_comment_ok", "issue_key": req.issue_key},
            )
            return {"ok": True}
        except requests.HTTPError as e:
            statsd.increment("jira.comment.error", tags=["reason:http_error"])
            LOG.exception("jira_comment_http_error")
            raise HTTPException(status_code=502, detail=str(e))
        except Exception as e:
            statsd.increment("jira.comment.error", tags=["reason:exception"])
            LOG.exception("jira_comment_error")
            raise HTTPException(status_code=502, detail=str(e))


def poll_loop():
    # Do not crash the app if Jira isn't configured; just disable polling.
    try:
        _require_jira_config()
    except Exception as e:
        LOG.warning(
            "poll_disabled_missing_jira_config",
            extra={**base_fields(DD_SERVICE), **current_dd_ids(), "status": "poll_disabled", "reason": str(e)},
        )
        return

    url = f"{JIRA_BASE_URL.rstrip('/')}/rest/api/3/search"
    jql = f'project = "{JIRA_PROJECT_KEY}" AND summary ~ "Suspected Fraud" ORDER BY created DESC'

    while True:
        try:
            with tracer.trace("jira.poll", service=DD_SERVICE, resource="jira.search"):
                r = requests.get(
                    url,
                    auth=_auth(),
                    headers={"Accept": "application/json"},
                    params={"jql": jql, "maxResults": 5},
                    timeout=15,
                )
                if not r.ok:
                    try:
                        jira_err = r.json()
                    except Exception:
                        jira_err = {"text": r.text}
                    LOG.error(
                        "jira_poll_failed",
                        extra={
                            **base_fields(DD_SERVICE),
                            **current_dd_ids(),
                            "status": "jira_poll_failed",
                            "reason": f"HTTP {r.status_code}",
                            "jira_error": jira_err,
                        },
                    )
                    r.raise_for_status()

                issues = (r.json() or {}).get("issues", []) or []
                statsd.gauge("jira.suspected_fraud.open", len(issues))
                statsd.increment("jira.poll.success")
                LOG.info(
                    "jira_poll_ok",
                    extra={**base_fields(DD_SERVICE), **current_dd_ids(), "status": "jira_poll_ok", "count": len(issues)},
                )
        except Exception as e:
            statsd.increment("jira.poll.error")
            LOG.error(
                "jira_poll_error",
                extra={**base_fields(DD_SERVICE), **current_dd_ids(), "status": "jira_poll_error", "reason": str(e)},
            )
        time.sleep(POLL_INTERVAL)


@app.on_event("startup")
def startup():
    if POLL_ENABLED:
        threading.Thread(target=poll_loop, daemon=True).start()
    else:
        LOG.info(
            "poll_disabled",
            extra={**base_fields(DD_SERVICE), **current_dd_ids(), "status": "poll_disabled", "reason": "JIRA_POLL_ENABLED=false"},
        )
