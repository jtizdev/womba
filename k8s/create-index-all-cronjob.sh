#!/bin/bash
# Script to create/update the womba-index-all CronJob in Kubernetes
# This CronJob runs index-all every Saturday morning at 3 AM UTC

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default namespace
NAMESPACE="${KUBERNETES_NAMESPACE:-womba}"
CRONJOB_FILE="k8s/cronjob-index-all.yaml"

echo -e "${GREEN}🚀 Creating/Updating Womba Index-All CronJob${NC}"
echo "=========================================="
echo "Namespace: ${NAMESPACE}"
echo "Schedule: Every Saturday at 3:00 AM UTC"
echo "=========================================="
echo ""

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}❌ kubectl not found. Please install kubectl first.${NC}"
    exit 1
fi

# Check if we can connect to cluster
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}❌ Cannot connect to Kubernetes cluster.${NC}"
    echo "Please check your kubeconfig: kubectl cluster-info"
    exit 1
fi

# Check if namespace exists
if ! kubectl get namespace "${NAMESPACE}" &> /dev/null; then
    echo -e "${YELLOW}⚠️  Namespace '${NAMESPACE}' does not exist.${NC}"
    read -p "Create namespace? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        kubectl create namespace "${NAMESPACE}"
        echo -e "${GREEN}✅ Created namespace: ${NAMESPACE}${NC}"
    else
        echo -e "${RED}❌ Aborted. Please create namespace first.${NC}"
        exit 1
    fi
fi

# Check if CronJob file exists
if [ ! -f "${CRONJOB_FILE}" ]; then
    echo -e "${RED}❌ CronJob file not found: ${CRONJOB_FILE}${NC}"
    exit 1
fi

# Check if PVC exists (required for RAG database)
echo "Checking required PersistentVolumeClaims..."
PVC_EXISTS=$(kubectl -n "${NAMESPACE}" get pvc womba-chroma-data 2>/dev/null || echo "")
if [ -z "$PVC_EXISTS" ]; then
    echo -e "${YELLOW}⚠️  PVC 'womba-chroma-data' not found in namespace '${NAMESPACE}'.${NC}"
    echo "The CronJob needs this PVC to access the RAG database."
    echo "Please ensure it exists or update the CronJob manifest."
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if secrets/configmaps exist
echo "Checking required secrets/configmaps..."
SECRET_EXISTS=$(kubectl -n "${NAMESPACE}" get secret womba-secrets 2>/dev/null || echo "")
CONFIG_EXISTS=$(kubectl -n "${NAMESPACE}" get configmap womba-config 2>/dev/null || echo "")

if [ -z "$SECRET_EXISTS" ]; then
    echo -e "${YELLOW}⚠️  Secret 'womba-secrets' not found.${NC}"
    echo "The CronJob needs this secret for credentials."
fi

if [ -z "$CONFIG_EXISTS" ]; then
    echo -e "${YELLOW}⚠️  ConfigMap 'womba-config' not found.${NC}"
    echo "The CronJob will work without it, but may need env vars."
fi

echo ""
echo -e "${GREEN}📋 Applying CronJob manifest...${NC}"

# Apply the CronJob
if kubectl -n "${NAMESPACE}" apply -f "${CRONJOB_FILE}"; then
    echo -e "${GREEN}✅ CronJob created/updated successfully!${NC}"
else
    echo -e "${RED}❌ Failed to apply CronJob${NC}"
    exit 1
fi

echo ""
echo "=========================================="
echo -e "${GREEN}✅ Setup Complete!${NC}"
echo "=========================================="
echo ""
echo "📊 CronJob Details:"
kubectl -n "${NAMESPACE}" get cronjob womba-index-all
echo ""
echo "📅 Schedule: Every Saturday at 3:00 AM UTC"
echo ""
echo "🔍 Useful commands:"
echo "  # View CronJob:"
echo "  kubectl -n ${NAMESPACE} get cronjob womba-index-all"
echo ""
echo "  # View job history:"
echo "  kubectl -n ${NAMESPACE} get jobs -l component=index-all"
echo ""
echo "  # View logs from latest run:"
echo "  LATEST_JOB=\$(kubectl -n ${NAMESPACE} get jobs -l component=index-all --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1].metadata.name}')"
echo "  kubectl -n ${NAMESPACE} logs job/\$LATEST_JOB"
echo ""
echo "  # Manually trigger a run:"
echo "  kubectl -n ${NAMESPACE} create job --from=cronjob/womba-index-all womba-index-all-manual-\$(date +%s)"
echo ""
echo "  # Suspend CronJob:"
echo "  kubectl -n ${NAMESPACE} patch cronjob womba-index-all -p '{\"spec\":{\"suspend\":true}}'"
echo ""
echo "  # Resume CronJob:"
echo "  kubectl -n ${NAMESPACE} patch cronjob womba-index-all -p '{\"spec\":{\"suspend\":false}}'"
echo ""
echo "  # Delete CronJob:"
echo "  kubectl -n ${NAMESPACE} delete cronjob womba-index-all"
echo ""

