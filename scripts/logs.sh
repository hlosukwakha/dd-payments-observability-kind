#!/usr/bin/env bash
set -euo pipefail
export KUBECONFIG="${KUBECONFIG:-/workspace/.kube/config}"
NS="dd-demo"
APP="${1:-}"
if [ -z "$APP" ]; then
  echo "Usage: ./scripts/logs.sh <app>"
  exit 1
fi
kubectl --kubeconfig "$KUBECONFIG" -n "$NS" logs -l app="$APP" --tail=200 -f
