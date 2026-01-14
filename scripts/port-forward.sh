#!/usr/bin/env bash
set -euo pipefail
export KUBECONFIG="${KUBECONFIG:-/workspace/.kube/config}"
kubectl --kubeconfig "$KUBECONFIG" -n dd-demo port-forward svc/web-frontend 8080:8000
