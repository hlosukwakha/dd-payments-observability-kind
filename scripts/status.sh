#!/usr/bin/env bash
set -euo pipefail
export KUBECONFIG="${KUBECONFIG:-/workspace/.kube/config}"
echo "== Nodes =="
kubectl --kubeconfig "$KUBECONFIG" get nodes -o wide || true
echo
echo "== Datadog pods =="
kubectl --kubeconfig "$KUBECONFIG" -n datadog get pods -o wide || true
echo
echo "== Demo apps =="
kubectl --kubeconfig "$KUBECONFIG" -n dd-demo get deploy,po,svc -o wide || true
