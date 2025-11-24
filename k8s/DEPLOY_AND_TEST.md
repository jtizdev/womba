# Deploy and Test CronJob

## How It Works

1. **CronJob** = Schedule definition ("run every Saturday at 3 AM")
2. **Job** = Instance created by CronJob ("run it now!")
3. **Pod** = Container that actually runs the command

When the schedule triggers:
- Kubernetes creates a Job
- Job creates a Pod
- Pod runs `womba index-all --force-refresh`
- Pod updates the RAG database (shared PVC)
- Pod completes and gets cleaned up

## Deploy Production CronJob

```bash
# Deploy the CronJob (runs every Saturday at 3 AM UTC)
kubectl -n womba apply -f k8s/cronjob-index-all.yaml

# Verify it's created
kubectl -n womba get cronjob womba-index-all

# Check the schedule
kubectl -n womba get cronjob womba-index-all -o jsonpath='{.spec.schedule}'
# Should show: 0 3 * * 6
```

## Test Immediately (3 Ways)

### Option 1: Create Manual Job from CronJob (Recommended)

```bash
# Create a one-time job from the CronJob
kubectl -n womba create job --from=cronjob/womba-index-all \
  womba-index-all-manual-$(date +%s)

# Watch it run
kubectl -n womba get jobs -l component=index-all -w

# View logs
JOB_NAME=$(kubectl -n womba get jobs -l component=index-all \
  --sort-by=.metadata.creationTimestamp \
  -o jsonpath='{.items[-1].metadata.name}')

kubectl -n womba logs job/$JOB_NAME -f
```

### Option 2: Deploy Test CronJob (Runs Every Minute)

```bash
# Deploy test version that runs every minute
kubectl -n womba apply -f k8s/test-cronjob-1min.yaml

# Watch it create jobs
kubectl -n womba get jobs -l component=index-all -w

# After it runs, delete the test CronJob
kubectl -n womba delete cronjob womba-index-all-test
```

### Option 3: Temporarily Change Schedule

```bash
# Patch the CronJob to run in 1 minute
# First, get current time + 1 minute
# Then patch: kubectl -n womba patch cronjob womba-index-all -p '{"spec":{"schedule":"X X * * *"}}'

# Or just create manual job (easier)
```

## Monitor Execution

```bash
# Watch jobs being created
kubectl -n womba get jobs -l component=index-all -w

# Check job status
kubectl -n womba get jobs -l component=index-all

# View pod logs
POD_NAME=$(kubectl -n womba get pods -l component=index-all \
  --sort-by=.metadata.creationTimestamp \
  -o jsonpath='{.items[-1].metadata.name}')

kubectl -n womba logs $POD_NAME -f

# Or view job logs directly
JOB_NAME=$(kubectl -n womba get jobs -l component=index-all \
  --sort-by=.metadata.creationTimestamp \
  -o jsonpath='{.items[-1].metadata.name}')

kubectl -n womba logs job/$JOB_NAME -f
```

## Check Results

```bash
# Verify RAG database was updated
kubectl -n womba exec deployment/womba-server -- womba rag-stats

# Or via API
kubectl -n womba port-forward deployment/womba-server 8000:8000 &
curl http://localhost:8000/api/v1/rag/stats | jq .
```

## Cleanup

```bash
# Delete test CronJob
kubectl -n womba delete cronjob womba-index-all-test

# Delete manual job
kubectl -n womba delete job womba-index-all-manual-<timestamp>

# Suspend production CronJob (if needed)
kubectl -n womba patch cronjob womba-index-all \
  -p '{"spec":{"suspend":true}}'

# Resume production CronJob
kubectl -n womba patch cronjob womba-index-all \
  -p '{"spec":{"suspend":false}}'
```

