# dd-payments-observability-kind

A reproducible local lab: **Kind (3 nodes)** + **Datadog Agent** + **FastAPI microservices** + **Datadog RUM Session Replay** + **Jira fraud workflow**.

## Services
- web-frontend (UI + RUM + browser logs; proxies downstream calls)
- auth-service
- payment-service (random failures + suspected fraud path)
- fraud-service (random confirm/clear; comments on Jira ticket)
- jira-poller (creates + comments + periodic poll)
- llm-service (simulated model, instrumented for Datadog LLM Observability)

## Prereqs
- Docker + Docker Compose
- Datadog API key
- Datadog RUM Application ID + Client Token with Session Replay enabled citeturn0search1turn3search13
- Jira Cloud base URL + email + API token + project key

## Run
```bash
cp .env.example .env
# edit .env
make up
make pf   # open http://localhost:8080
```

## Useful commands
```bash
make status
make logs-payment
make logs-fraud
make logs-jira
make logs-auth
make logs-web
make logs-llm
make down
```

## Trace correlation model
Browser → web-frontend → auth-service/payment-service → fraud-service/jira-poller.

All services (except llm-service) share a single trace via HTTP propagation and automatic instrumentation. citeturn0search2turn0search6
