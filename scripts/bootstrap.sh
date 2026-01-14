#!/usr/bin/env bash
set -euo pipefail

export KUBECONFIG="${KUBECONFIG:-/workspace/.kube/config}"
mkdir -p "$(dirname "$KUBECONFIG")"

set -a
if [ -f /workspace/.env ]; then
  source /workspace/.env
else
  echo "Missing .env. Copy .env.example to .env and fill it in."
  exit 1
fi
set +a

: "${KIND_CLUSTER_NAME:=dd-payments-kind}"
: "${DATADOG_API_KEY:?Missing DATADOG_API_KEY}"
: "${DD_SITE:=datadoghq.eu}"
: "${DD_ENV:=dev}"
: "${DD_VERSION:=0.1.0}"

echo "[1/7] Create kind cluster ($KIND_CLUSTER_NAME) with 3 nodes"
if kind get clusters | grep -q "^${KIND_CLUSTER_NAME}$"; then
  echo "Cluster exists."
else
  kind create cluster --name "$KIND_CLUSTER_NAME" --config /workspace/k8s/kind-config.yaml --kubeconfig "$KUBECONFIG"
fi

kind export kubeconfig --name "$KIND_CLUSTER_NAME" --kubeconfig "$KUBECONFIG" --internal

echo "[2/7] Install Datadog Agent (Helm) in namespace datadog"
kubectl --kubeconfig "$KUBECONFIG" get ns datadog >/dev/null 2>&1 || kubectl --kubeconfig "$KUBECONFIG" create ns datadog

# (Choose ONE method. Keeping the dry-run/apply approach; remove the envsubst datadog one later.)
kubectl --kubeconfig "$KUBECONFIG" -n datadog create secret generic datadog-secret \
  --from-literal api-key="$DATADOG_API_KEY" \
  --dry-run=client -o yaml | kubectl --kubeconfig "$KUBECONFIG" apply -f -

helm repo add datadog https://helm.datadoghq.com >/dev/null
helm repo update >/dev/null

echo "This may take several minutes..."
helm upgrade --install datadog datadog/datadog \
  --namespace datadog \
  -f /workspace/datadog/values.yaml \
  --set datadog.site="$DD_SITE" \
  --set datadog.clusterName="$KIND_CLUSTER_NAME" \
  --wait --timeout 90m

echo "[3/7] Build services image"
docker build -t demo-services:0.1.0 -f /workspace/docker/services/Dockerfile /workspace

echo "[4/7] Load image into kind"
kind load docker-image demo-services:0.1.0 --name "$KIND_CLUSTER_NAME"

echo "[5/7] Deploy namespace + config (namespace: dd-demo)"
kubectl --kubeconfig "$KUBECONFIG" apply -f /workspace/k8s/namespace.yaml

# Create/update datadog-secret in dd-demo (apps) - MUST exist before apps
export DATADOG_API_KEY  # ensure envsubst sees it if your template uses it
kubectl --kubeconfig "$KUBECONFIG" -n dd-demo create secret generic datadog-secret \
  --from-literal api-key="$DATADOG_API_KEY" \
  --dry-run=client -o yaml | kubectl --kubeconfig "$KUBECONFIG" apply -f -

# ConfigMap for non-sensitive config
kubectl --kubeconfig "$KUBECONFIG" -n dd-demo create configmap demo-config \
  --from-literal DD_ENV="$DD_ENV" \
  --from-literal DD_VERSION="$DD_VERSION" \
  --from-literal PAYMENT_FAIL_RATE="${PAYMENT_FAIL_RATE:-0.15}" \
  --from-literal PAYMENT_SUSPECTED_FRAUD_RATE="${PAYMENT_SUSPECTED_FRAUD_RATE:-0.05}" \
  --from-literal AUTH_FAIL_RATE="${AUTH_FAIL_RATE:-0.12}" \
  --from-literal FRAUD_CONFIRM_RATE="${FRAUD_CONFIRM_RATE:-0.35}" \
  --from-literal JIRA_BASE_URL="${JIRA_BASE_URL:-}" \
  --from-literal JIRA_EMAIL="${JIRA_EMAIL:-}" \
  --from-literal JIRA_PROJECT_KEY="${JIRA_PROJECT_KEY:-PER}" \
  --from-literal JIRA_ISSUE_TYPE="${JIRA_ISSUE_TYPE:-Task}" \
  --from-literal JIRA_POLL_INTERVAL_SECONDS="${JIRA_POLL_INTERVAL_SECONDS:-1800}" \
  --from-literal DD_RUM_APPLICATION_ID="${DD_RUM_APPLICATION_ID:-}" \
  --from-literal DD_RUM_SITE="${DD_RUM_SITE:-$DD_SITE}" \
  --from-literal DD_RUM_SERVICE="${DD_RUM_SERVICE:-web-frontend}" \
  --from-literal DD_RUM_ENV="${DD_RUM_ENV:-$DD_ENV}" \
  --from-literal DD_RUM_VERSION="${DD_RUM_VERSION:-$DD_VERSION}" \
  --from-literal DD_RUM_SESSION_REPLAY_SAMPLE_RATE="${DD_RUM_SESSION_REPLAY_SAMPLE_RATE:-100}" \
  --dry-run=client -o yaml | kubectl --kubeconfig "$KUBECONFIG" apply -f -

# Secret for sensitive config
kubectl --kubeconfig "$KUBECONFIG" -n dd-demo create secret generic demo-secrets \
  --from-literal JIRA_API_TOKEN="${JIRA_API_TOKEN:-}" \
  --from-literal DD_RUM_CLIENT_TOKEN="${DD_RUM_CLIENT_TOKEN:-}" \
  --dry-run=client -o yaml | kubectl --kubeconfig "$KUBECONFIG" apply -f -

echo "[6/7] Deploy apps"
kubectl --kubeconfig "$KUBECONFIG" apply -f /workspace/k8s/apps.yaml

echo "[7/7] Wait for rollouts"
for d in web-frontend auth-service payment-service fraud-service jira-poller llm-service; do
  kubectl --kubeconfig "$KUBECONFIG" -n dd-demo rollout status "deploy/$d" --timeout=600s
done

echo "Done."
echo "Run: make pf  (then open http://localhost:8080)"
