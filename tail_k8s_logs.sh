#!/bin/bash
# Tail logs from womba-server pod in Kubernetes

NAMESPACE="womba"
POD_NAME="${1:-womba-server-bfb947f4c-979zc}"
TAIL_LINES="${2:-100}"

echo "📋 Tailing logs from: $POD_NAME"
echo "   Namespace: $NAMESPACE"
echo "   Lines: $TAIL_LINES"
echo "   (Press Ctrl+C to stop)"
echo ""

kubectl -n $NAMESPACE logs -f --tail=$TAIL_LINES --timestamps $POD_NAME

