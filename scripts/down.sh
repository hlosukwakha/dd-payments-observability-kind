#!/usr/bin/env bash
set -euo pipefail
export KUBECONFIG="${KUBECONFIG:-/workspace/.kube/config}"
set -a
[ -f /workspace/.env ] && source /workspace/.env
set +a
: "${KIND_CLUSTER_NAME:=dd-payments-kind}"
kind delete cluster --name "$KIND_CLUSTER_NAME" || true
