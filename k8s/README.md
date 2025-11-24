# Kubernetes CronJob for Index-All

This directory contains Kubernetes manifests and scripts for running `womba index-all` on a scheduled basis.

## Quick Start

### 1. Prerequisites

- Kubernetes cluster access (`kubectl` configured)
- Namespace `womba` exists (or set `KUBERNETES_NAMESPACE` env var)
- Required PVCs exist:
  - `womba-chroma-data` (for RAG database)
  - `womba-mcp-auth` (optional, for MCP OAuth cache)
- Required secrets/configmaps:
  - `womba-secrets` (with credentials)
  - `womba-config` (optional, with config)

### 2. Create the CronJob

```bash
# Make script executable
chmod +x k8s/create-index-all-cronjob.sh

# Run the script
./k8s/create-index-all-cronjob.sh
```

Or manually apply:

```bash
kubectl -n womba apply -f k8s/cronjob-index-all.yaml
```

## Schedule

The CronJob runs **every Saturday at 3:00 AM UTC** by default.

Cron format: `0 3 * * 6`
- `0` = minute 0
- `3` = hour 3 (3 AM)
- `*` = any day of month
- `*` = any month
- `6` = Saturday (0=Sunday, 6=Saturday)

### Changing the Schedule

Edit `cronjob-index-all.yaml` and modify the `schedule` field:

```yaml
spec:
  schedule: "0 3 * * 6"  # Saturday 3 AM UTC
```

Common schedules:
- `"0 2 * * *"` - Daily at 2 AM UTC
- `"0 */12 * * *"` - Every 12 hours
- `"0 3 * * 1"` - Every Monday at 3 AM UTC
- `"0 2,14 * * *"` - Twice daily (2 AM and 2 PM UTC)
- `"0 4 * * 0"` - Every Sunday at 4 AM UTC

## Verification

### Check CronJob Status

```bash
kubectl -n womba get cronjob womba-index-all
```

### View Job History

```bash
kubectl -n womba get jobs -l component=index-all
```

### View Logs from Latest Run

```bash
# Get latest job name
LATEST_JOB=$(kubectl -n womba get jobs -l component=index-all \
  --sort-by=.metadata.creationTimestamp \
  -o jsonpath='{.items[-1].metadata.name}')

# View logs
kubectl -n womba logs job/$LATEST_JOB
```

### Check Job Status

```bash
kubectl -n womba get jobs -l component=index-all -o wide
```

## Manual Execution

### Trigger a Manual Run

```bash
kubectl -n womba create job --from=cronjob/womba-index-all \
  womba-index-all-manual-$(date +%s)
```

### Watch Manual Run

```bash
# Get job name
JOB_NAME=$(kubectl -n womba get jobs -l component=index-all \
  --sort-by=.metadata.creationTimestamp \
  -o jsonpath='{.items[-1].metadata.name}')

# Watch job
kubectl -n womba get job $JOB_NAME -w

# View logs
kubectl -n womba logs job/$JOB_NAME -f
```

## Management

### Suspend CronJob

```bash
kubectl -n womba patch cronjob womba-index-all \
  -p '{"spec":{"suspend":true}}'
```

### Resume CronJob

```bash
kubectl -n womba patch cronjob womba-index-all \
  -p '{"spec":{"suspend":false}}'
```

### Delete CronJob

```bash
kubectl -n womba delete cronjob womba-index-all
```

### Update CronJob

```bash
# Edit the manifest
vim k8s/cronjob-index-all.yaml

# Apply changes
kubectl -n womba apply -f k8s/cronjob-index-all.yaml
```

## Configuration

### Required Volumes

The CronJob needs access to:

1. **RAG Database** (`womba-chroma-data` PVC)
   - Stores indexed documents
   - Must match main deployment PVC

2. **Configuration** (`womba-secrets` secret)
   - Contains credentials (Jira, Zephyr, AI keys, etc.)
   - Must match main deployment secrets

3. **MCP Auth** (`womba-mcp-auth` PVC, optional)
   - Stores MCP OAuth tokens
   - Only needed if using GitLab MCP

### Environment Variables

The CronJob inherits environment variables from:
- `womba-secrets` secret (via `envFrom.secretRef`)
- `womba-config` configmap (via `envFrom.configMapRef`)

Required environment variables:
- `ATLASSIAN_BASE_URL`
- `ATLASSIAN_EMAIL`
- `ATLASSIAN_API_TOKEN`
- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`
- `ZEPHYR_API_TOKEN`
- `ZEPHYR_BASE_URL`
- `PROJECT_KEY` (or configured in `~/.womba/config.yml`)

### Resource Limits

Default resource limits:
- Requests: 512Mi memory, 200m CPU
- Limits: 2Gi memory, 1000m CPU

Adjust in `cronjob-index-all.yaml` if needed:

```yaml
resources:
  requests:
    memory: "1Gi"
    cpu: "500m"
  limits:
    memory: "4Gi"
    cpu: "2000m"
```

## Troubleshooting

### CronJob Not Running

1. Check CronJob status:
   ```bash
   kubectl -n womba describe cronjob womba-index-all
   ```

2. Check for suspend flag:
   ```bash
   kubectl -n womba get cronjob womba-index-all -o jsonpath='{.spec.suspend}'
   ```

3. Check last schedule time:
   ```bash
   kubectl -n womba get cronjob womba-index-all -o jsonpath='{.status.lastScheduleTime}'
   ```

### Job Failing

1. Check job status:
   ```bash
   kubectl -n womba get jobs -l component=index-all
   ```

2. View job events:
   ```bash
   JOB_NAME=$(kubectl -n womba get jobs -l component=index-all \
     --sort-by=.metadata.creationTimestamp \
     -o jsonpath='{.items[-1].metadata.name}')
   kubectl -n womba describe job $JOB_NAME
   ```

3. View pod logs:
   ```bash
   POD_NAME=$(kubectl -n womba get pods -l component=index-all \
     --sort-by=.metadata.creationTimestamp \
     -o jsonpath='{.items[-1].metadata.name}')
   kubectl -n womba logs $POD_NAME
   ```

### Common Issues

**PVC Not Found**
- Ensure `womba-chroma-data` PVC exists in namespace
- Check PVC is bound: `kubectl -n womba get pvc`

**Secrets Not Found**
- Ensure `womba-secrets` secret exists
- Verify secret has required keys: `kubectl -n womba get secret womba-secrets -o yaml`

**Image Pull Errors**
- Check image name in manifest matches your registry
- Verify image pull secrets if using private registry

**Permission Denied**
- Check service account permissions
- May need to create RBAC rules for service account

## Monitoring

### Set Up Alerts

You can monitor CronJob execution using:

1. **Kubernetes Events**:
   ```bash
   kubectl -n womba get events --field-selector involvedObject.name=womba-index-all
   ```

2. **Prometheus Metrics** (if Prometheus operator installed):
   - CronJob metrics available via `kube-state-metrics`
   - Job success/failure metrics

3. **Log Aggregation**:
   - Forward logs to your logging system (ELK, Loki, etc.)
   - Set up alerts on job failures

## Security Considerations

1. **Service Account**: Uses `default` service account. Consider creating a dedicated service account with minimal permissions.

2. **Secrets**: Secrets are mounted read-only. Ensure secrets are properly encrypted at rest.

3. **Network Policies**: Consider restricting pod network access if needed.

4. **Resource Limits**: Set appropriate limits to prevent resource exhaustion.

## Example: Custom Service Account

Create a dedicated service account:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: womba-index-all
  namespace: womba
```

Then update CronJob to use it:

```yaml
spec:
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: womba-index-all
```

