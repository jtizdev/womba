#!/bin/bash
# Quick script to check RAG stats in Kubernetes

NAMESPACE="womba"

echo "🔍 Connecting to Kubernetes cluster..."
echo ""

# Get pod name (prefer womba-server, fallback to first pod)
POD_NAME=$(kubectl -n $NAMESPACE get pods -l app=womba-server -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
if [ -z "$POD_NAME" ]; then
    POD_NAME=$(kubectl -n $NAMESPACE get pods -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
fi

if [ -z "$POD_NAME" ]; then
    echo "❌ No pods found in namespace $NAMESPACE"
    echo ""
    echo "Available namespaces:"
    kubectl get namespaces | grep -E "NAME|womba"
    exit 1
fi

echo "✅ Found pod: $POD_NAME"
echo ""

# Check RAG stats (filter out telemetry errors)
echo "📊 RAG Statistics:"
echo "=================="
kubectl -n $NAMESPACE exec $POD_NAME -- womba rag-stats 2>&1 | grep -v "Failed to send telemetry"

