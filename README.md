# dd-payments-observability-kind

![Docker](https://img.shields.io/badge/Docker-Engine%20%2B%20Compose-2496ED?logo=docker&logoColor=white)
![Kubernetes](https://img.shields.io/badge/Kubernetes-kind%20(v1.31)-326CE5?logo=kubernetes&logoColor=white)
![Helm](https://img.shields.io/badge/Helm-3-0F1689?logo=helm&logoColor=white)
![Datadog](https://img.shields.io/badge/Datadog-Observability-632CA6?logo=datadog&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Services-009688?logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Uvicorn](https://img.shields.io/badge/Uvicorn-ASGI-111111)
![Jira](https://img.shields.io/badge/Atlassian-Jira-0052CC?logo=jira&logoColor=white)

A local, reproducible **payments microservices demo** running on **Kubernetes-in-Docker (kind)**, instrumented with **Datadog APM + Logs + Metrics + RUM**, and optionally integrated with **Jira** and **AI/LLM Observability**.

This repo is designed to be:
- a hands-on **observability playground** (SRE/Platform/Engineering Enablement),
- a demo for **trace context propagation** across services,
- a working template for **kind + Helm + Datadog** workflows,
- a minimal reference for **RUM ↔ backend tracing correlation** and **LLM service telemetry**.

---

## What the project does

This environment simulates a basic payments flow:

1. **web-frontend** (FastAPI serves UI + API gateway)
   - Serves `index.html`
   - Produces **RUM + Session Replay + Browser Logs**
   - Calls backend APIs and propagates tracing headers

2. **auth-service**
   - Authenticates users
   - Emits logs, metrics, traces
   - Provides authentication latency/outcome signals

3. **payment-service**
   - Creates payments, attempts settlement
   - Emits payment counters, failure reasons, settlement latency
   - Calls fraud detection and Jira workflows

4. **fraud-service**
   - Flags suspected fraud (based on configurable rates)
   - Optionally calls Jira to create a ticket for suspected fraud

5. **jira-poller**
   - Creates issues and adds comments via Jira REST API
   - Polls Jira and emits high-level metrics

6. **llm-service** (simulated)
   - Implements a `/llm/generate` endpoint
   - Can emit **AI/LLM observability** signals (requires correct ddtrace/LLMObs configuration and API key availability)

7. **Datadog Agent (Helm)**
   - Collects logs/metrics/traces from workloads
   - Enables Kubernetes/container metrics, pod restarts, CPU/memory/network, etc.

The goal is to make it easy to:
- run everything locally,
- observe service behavior end-to-end,
- build dashboards and investigations quickly,
- extend the stack with new services, checks, and workflows.

---

## Repository layout (project tree)

> The exact tree may differ slightly based on your workspace, but these are the core components referenced by the scripts and YAML.

```text
dd-payments-observability-kind/
├─ docker/
│  └─ services/
│     └─ Dockerfile
├─ k8s/
│  ├─ apps.yaml
│  ├─ namespace.yaml
│  ├─ kind-config.yaml
│  └─ secrets/
│     ├─ datadog-secret.dd-demo.yaml
│     └─ datadog-secret.datadog.yaml
├─ datadog/
│  └─ values.yaml
├─ scripts/
│  ├─ bootstrap.sh
│  ├─ logs.sh
│  ├─ status.sh
│  └─ port-forward.sh
├─ services/
│  ├─ __init__.py
│  ├─ obs.py
│  ├─ web_frontend.py
│  ├─ auth_service.py
│  ├─ payment_service.py
│  ├─ fraud_service.py
│  ├─ jira_poller.py
│  ├─ llm_service.py
│  └─ web/
│     └─ index.html
├─ Makefile
├─ .env.example
└─ README.md
```

---

## Tech stack (what each part does)

- **kind**: runs a full Kubernetes cluster inside Docker containers (fast, local, disposable).
- **kubectl**: applies manifests, inspects pods, logs, events, rollouts.
- **Helm**: installs/updates the Datadog Agent chart with your values.
- **Datadog Agent**: collects APM traces, infrastructure metrics, logs, and (optionally) orchestrator/process data.
- **FastAPI + Uvicorn**: lightweight services and a UI gateway.
- **ddtrace**: automatic and manual trace instrumentation.
- **DogStatsd**: emits custom app metrics (counts, gauges, timings).
- **Datadog Browser SDK (v6)**: RUM, session replay, browser logs, and correlation with backend traces.
- **Jira REST API**: issue creation and commenting for suspected fraud workflows.

---

## Prerequisites

Install locally:
- Docker + Docker Compose
- kind
- kubectl
- helm

Optional but recommended:
- `gettext` (for `envsubst`) if you use env-substitution for secrets/templates  
  - macOS: `brew install gettext` and ensure `envsubst` is on PATH  
  - Debian/Ubuntu: `sudo apt-get install gettext-base`

Datadog:
- A Datadog **EU** org if you’re using `datadoghq.eu` (`DD_SITE=datadoghq.eu`)
- A valid **Datadog API key**
- Optional: RUM application + client token

Jira (optional):
- Atlassian cloud base URL (e.g., `https://your-org.atlassian.net`)
- Email + API token
- Project key + issue type

---

## Configuration

### `.env` (required)
Copy and edit:

```bash
cp .env.example .env
```

Minimum required:
- `DATADOG_API_KEY=...`
- `DD_SITE=datadoghq.eu`

RUM (optional but recommended):
- `DD_RUM_APPLICATION_ID=...`
- `DD_RUM_CLIENT_TOKEN=...` (public token)
- `DD_RUM_SITE=datadoghq.eu`
- `DD_RUM_SERVICE=web-frontend`
- `DD_RUM_ENV=dev`
- `DD_RUM_VERSION=0.1.0`
- `DD_RUM_SESSION_REPLAY_SAMPLE_RATE=100`

Jira (optional):
- `JIRA_BASE_URL=https://<org>.atlassian.net`
- `JIRA_EMAIL=...`
- `JIRA_API_TOKEN=...`
- `JIRA_PROJECT_KEY=PER`
- `JIRA_ISSUE_TYPE=Task`

> Notes:
> - Secrets must exist **in the same namespace** as the workloads that reference them.
> - In this repo we intentionally create `datadog-secret` in both `datadog` (agent) and `dd-demo` (apps), because the LLM service uses `DD_API_KEY`.

---

## How to run (quick start)

### 1) Bootstrap everything
From the repo root:

```bash
make up
```

Typical flow:
1. Create kind cluster (3 nodes)
2. Install Datadog Agent via Helm (namespace `datadog`)
3. Build the services image (`demo-services:0.1.0`)
4. Load the image into kind
5. Create namespace/config/secrets in `dd-demo`
6. Apply `k8s/apps.yaml`
7. Wait for rollouts

### 2) Port-forward the web frontend
One of the following (depends on your Makefile):

```bash
make pf
```

or manually:

```bash
kubectl -n dd-demo port-forward svc/web-frontend 8080:8000
```

Then open:
- UI: `http://localhost:8080`

---

## How to access llm-service via browser

The service is `ClusterIP` by default, so you access it via port-forward:

```bash
kubectl -n dd-demo port-forward svc/llm-service 8000:8000
```

Open:
- Swagger UI: `http://localhost:8000/docs`

Test generate endpoint:
```bash
curl -sS -X POST "http://127.0.0.1:8000/llm/generate"   -H "Content-Type: application/json"   -d '{"prompt":"Write a one-line joke about Kubernetes."}' | jq .
```

---

## Testing and sanity checks

### Check deployments and pods
```bash
kubectl -n dd-demo get deploy,pods,svc
kubectl -n datadog get pods
```

### Rollout status
```bash
kubectl -n dd-demo rollout status deploy/web-frontend --timeout=300s
kubectl -n dd-demo rollout status deploy/payment-service --timeout=300s
```

### View logs
```bash
kubectl -n dd-demo logs deploy/web-frontend --tail=200
kubectl -n dd-demo logs deploy/payment-service --tail=200
kubectl -n dd-demo logs deploy/jira-poller --tail=200
kubectl -n dd-demo logs deploy/llm-service --tail=200
```

### Inspect crashes quickly
```bash
kubectl -n dd-demo get pods
kubectl -n dd-demo describe pod <pod-name>
kubectl -n dd-demo logs <pod-name> --previous --tail=200
kubectl -n dd-demo get events --sort-by=.lastTimestamp | tail -n 40
```

---

## Makefile usage

Your Makefile is the primary UX for the repo. Typical targets:

```bash
make up          # cluster + datadog + build/load image + deploy apps
make down        # tear down resources (and optionally delete kind cluster)
make pf          # port-forward web-frontend to localhost:8080
make logs SVC=web-frontend   # tail logs for a service (if implemented)
make status      # summary of pods/deployments/events
```

If your Makefile doesn’t implement a target yet, prefer shell scripts under `scripts/` (this repo expects them).

---

## Scripts overview

### `scripts/bootstrap.sh`
Bootstraps the full environment:
- reads `.env`
- creates/exports kind kubeconfig
- ensures namespaces exist
- creates `datadog-secret` (Datadog API key) in required namespaces
- installs Datadog Agent via Helm
- builds and loads the services image into kind
- creates `demo-config` ConfigMap and `demo-secrets` Secret
- applies `k8s/apps.yaml`
- waits for rollouts

### `scripts/port-forward.sh`
Convenience wrapper around:
```bash
kubectl -n dd-demo port-forward svc/web-frontend 8080:8000
```

### `scripts/logs.sh`
Utility to fetch logs for a named deployment/pod.

---

## Kubernetes YAML files

### `k8s/kind-config.yaml`
kind cluster definition (3 nodes). Useful to:
- ensure multiple workers for scheduling,
- reproduce issues across nodes,
- validate DaemonSets (Datadog Agent) on multiple nodes.

### `k8s/namespace.yaml`
Creates `dd-demo`.

### `k8s/apps.yaml`
Defines:
- Deployments + Services for each microservice
- Environment variables for Datadog tracing/log injection
- Service discovery URLs (e.g., `FRAUD_SERVICE_URL`, `JIRA_POLLER_URL`)

> Common pitfall: `env` vars must be under the container spec:
> `spec.template.spec.containers[].env[]`
> Not as a “fake container” entry (which triggers `unknown field ... containers[x].value`).

### `k8s/secrets/datadog-secret.*.yaml`
Defines `datadog-secret` in the relevant namespace.
- **Agent namespace** (`datadog`) uses it for agent configuration.
- **App namespace** (`dd-demo`) uses it for `DD_API_KEY` (needed for agentless AI observability / LLMObs).

---

## Troubleshooting (common issues)

### 1) `Error: secret "datadog-secret" not found`
Cause: the pod references a secret that does not exist **in its namespace**.

Fix:
```bash
kubectl -n dd-demo create secret generic datadog-secret   --from-literal api-key="$DATADOG_API_KEY"   --dry-run=client -o yaml | kubectl apply -f -
kubectl -n dd-demo rollout restart deploy/llm-service
```

Sanity check:
```bash
kubectl -n dd-demo get secret datadog-secret
```

### 2) Datadog Agent readiness probe failing (HTTP 500) + `API Key invalid (403 response)`
Cause: wrong/empty key or key not base64-encoded correctly when templated.

Fix (recreate secret in `datadog` namespace):
```bash
kubectl -n datadog create secret generic datadog-secret   --from-literal api-key="$DATADOG_API_KEY"   --dry-run=client -o yaml | kubectl apply -f -
helm -n datadog upgrade --install datadog datadog/datadog -f datadog/values.yaml --wait --timeout 30m
```

### 3) `envsubst: command not found`
Cause: `envsubst` isn’t installed in the environment running `bootstrap.sh`.

Fix options:
- Install gettext (`envsubst`), or
- Avoid templating and create secrets using `kubectl create secret ... --from-literal ...` (recommended for portability).

### 4) Pods CrashLoopBackOff but logs are empty, exit code 0, reason “Completed”
Cause: the Python module exits immediately (e.g., not running uvicorn, missing entrypoint, wrong command).

Fix:
- Ensure the container runs a server process (e.g., `uvicorn module:app`).
- Confirm module import and `app` exists.

Quick check inside image:
```bash
kubectl -n dd-demo run inspect --rm -it --image=demo-services:0.1.0 --restart=Never   --command -- python -c "import services.web_frontend as m; print(m.__file__)"
```

### 5) RUM SDK not loading
Cause: wrong script URL (404) or blocked network.

Fix:
- Use the official Datadog Browser SDK URL (EU1 example):
  - `https://www.datadoghq-browser-agent.com/eu1/v6/datadog-rum.js`
  - `https://www.datadoghq-browser-agent.com/eu1/v6/datadog-logs.js`

### 6) Jira API errors (405 / bad URL)
Common cause: malformed endpoint such as:
`.../rest/api/3/issue//comment` (missing issue key)

Fix:
- validate `issue_key` before building comment URL
- log request URL + response body on failure
- use `LOG.exception(...)` to include stack trace

---

## Useful commands (Docker / kind / Helm / Kubernetes)

### Docker
```bash
docker ps
docker images | grep demo-services
docker logs <container>
```

### kind
```bash
kind get clusters
kind export kubeconfig --name dd-payments-kind --kubeconfig ./kubeconfig-dd-payments-kind
kind load docker-image demo-services:0.1.0 --name dd-payments-kind
```

### Helm
```bash
helm repo add datadog https://helm.datadoghq.com
helm repo update
helm -n datadog list
helm -n datadog get values datadog
helm -n datadog upgrade --install datadog datadog/datadog -f datadog/values.yaml --wait --timeout 30m
```

### Kubernetes
```bash
kubectl get nodes -o wide
kubectl -n dd-demo get all
kubectl -n dd-demo get events --sort-by=.lastTimestamp | tail -n 50
kubectl -n dd-demo describe pod <pod>
kubectl -n dd-demo logs <pod> --previous --tail=200
kubectl -n dd-demo rollout restart deploy/<name>
```

---

## Extending the project

Common extensions:
- Add a new microservice and propagate trace headers across calls
- Add custom DogStatsD metrics (counts, latency histograms)
- Add a new dashboard or SLO set for the payments funnel
- Add feature flags (e.g., failure rates driven by config)
- Add synthetic load (k6 / locust) to generate steady telemetry
- Add OpenTelemetry exporter side-by-side (comparison exercise)

Guidance:
1. Add the service module in `services/`
2. Add a deployment/service stanza to `k8s/apps.yaml`
3. Ensure `envFrom` includes `demo-config` and `demo-secrets`
4. Include standard DD env vars (`DD_SERVICE`, `DD_ENV`, `DD_VERSION`, agent host/ports)
5. Rebuild and reload the image:
   ```bash
   docker build -t demo-services:0.1.0 -f docker/services/Dockerfile .
   kind load docker-image demo-services:0.1.0 --name dd-payments-kind
   kubectl -n dd-demo rollout restart deploy/<service>
   ```

---

## Signature

Created and maintained by **@hlosukwakha**.
