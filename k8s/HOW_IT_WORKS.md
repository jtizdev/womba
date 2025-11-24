# How the CronJob Works - Simple Explanation

## The Big Picture

You have Womba running in Kubernetes. Currently, you probably run `index-all` manually like this:

```bash
kubectl -n womba exec <pod-name> -- womba index-all
```

The CronJob **automates this** - it runs the same command automatically on a schedule.

## Visual Flow

```
┌─────────────────────────────────────────────────────────────┐
│  Kubernetes Cluster                                         │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  CronJob Controller (built into Kubernetes)          │  │
│  │  - Watches the schedule                              │  │
│  │  - "Is it Saturday 3 AM? Yes? Create a Job!"        │  │
│  └──────────────────────────────────────────────────────┘  │
│                        │                                     │
│                        ▼                                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Job (created by CronJob)                            │  │
│  │  - Runs once                                          │  │
│  │  - Creates a Pod                                      │  │
│  └──────────────────────────────────────────────────────┘  │
│                        │                                     │
│                        ▼                                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Pod (temporary container)                          │  │
│  │  ┌──────────────────────────────────────────────┐   │  │
│  │  │ Container: womba-index-all                   │   │  │
│  │  │ Command: womba index-all --force-refresh     │   │  │
│  │  │                                                │   │  │
│  │  │ Mounts:                                        │   │  │
│  │  │  - /app/data (RAG database) ◄──┐             │   │  │
│  │  │  - /app/.env (config)          │             │   │  │
│  │  │                                 │             │   │  │
│  │  │ Reads from:                     │             │   │  │
│  │  │  - womba-secrets (credentials)  │             │   │  │
│  │  │  - womba-config (settings)      │             │   │  │
│  │  └────────────────────────────────┘             │   │  │
│  └──────────────────────────────────────────────────────┘  │
│                        │                                     │
│                        ▼                                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  PersistentVolumeClaim: womba-chroma-data           │  │
│  │  (Shared storage - same as your main Womba pod)    │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Your Main Womba Pod (always running)             │  │
│  │  - API server on port 8000                          │  │
│  │  - Uses same PVC: womba-chroma-data                 │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Step-by-Step: What Happens

### 1. **You Deploy the CronJob** (one time)

```bash
kubectl -n womba apply -f k8s/cronjob-index-all.yaml
```

This tells Kubernetes: "Hey, I want you to run `womba index-all` every Saturday at 3 AM."

### 2. **Kubernetes Watches the Schedule**

Kubernetes has a built-in CronJob controller that:
- Checks every minute: "Is it time to run?"
- When Saturday 3 AM UTC arrives → Creates a Job

### 3. **Job Creates a Pod**

The Job creates a temporary Pod (container) that:
- Uses the same Docker image as your main Womba deployment
- Mounts the **same** PersistentVolumeClaim (`womba-chroma-data`)
- Has access to the **same** secrets/configmaps
- Runs the command: `womba index-all --force-refresh`

### 4. **The Pod Executes**

Inside the Pod:
```bash
# This happens automatically:
womba index-all --force-refresh

# Which does:
# 1. Fetches all Zephyr tests
# 2. Fetches all Jira stories
# 3. Fetches all Confluence docs
# 4. Fetches external docs
# 5. Fetches Swagger docs
# 6. Indexes everything into ChromaDB
# 7. Saves to /app/data (the PVC)
```

### 5. **Pod Completes and Deletes**

- Pod finishes (success or failure)
- Job keeps the Pod for history (you can see logs)
- After a while, Kubernetes deletes old Pods (keeps last 3)

### 6. **Your Main Womba Pod Benefits**

Your main Womba API pod uses the **same** PVC, so:
- It immediately sees the updated RAG database
- New test plan generations use the fresh indexed data
- No downtime, no restart needed

## Key Concepts

### **CronJob vs Job vs Pod**

- **CronJob**: The schedule definition ("run every Saturday")
- **Job**: An instance created by the CronJob ("run it now!")
- **Pod**: The actual container that runs ("doing the work")

### **Shared Storage (PVC)**

Both your main Womba pod and the CronJob pod use the **same** PersistentVolumeClaim:
- Main pod: Reads/writes RAG database
- CronJob pod: Writes updated RAG database
- They share the same data!

### **Why This Works**

1. **Same Image**: CronJob uses same Docker image → has `womba` CLI
2. **Same Storage**: CronJob mounts same PVC → updates same database
3. **Same Config**: CronJob uses same secrets → has same credentials
4. **Isolated**: CronJob runs in separate pod → doesn't affect main pod

## Real Example: What You'll See

### Before CronJob (Manual)

```bash
# You run this manually:
$ kubectl -n womba exec womba-pod-abc123 -- womba index-all
🚀 STARTING INDEX-ALL FOR PROJECT: PLAT
⏰ Start Time: 2025-01-20 10:30:00
...
🎉 INDEX-ALL COMPLETE!
```

### After CronJob (Automatic)

**Saturday 3:00 AM UTC arrives...**

```bash
# Kubernetes automatically creates:
$ kubectl -n womba get jobs
NAME                          COMPLETIONS   DURATION   AGE
womba-index-all-1737360000    1/1           8m         2m

# You can see the pod:
$ kubectl -n womba get pods -l component=index-all
NAME                              READY   STATUS      COMPLETED   AGE
womba-index-all-1737360000-xyz    0/1     Completed   0           8m

# View logs:
$ kubectl -n womba logs womba-index-all-1737360000-xyz
🚀 WOMBA INDEX-ALL SCHEDULED JOB
⏰ Started at: 2025-01-25 03:00:00 UTC
🔄 Running: womba index-all --force-refresh
🚀 STARTING INDEX-ALL FOR PROJECT: PLAT
...
🎉 INDEX-ALL COMPLETE!
```

## Common Questions

### Q: Does this affect my main Womba pod?

**A:** No! The CronJob creates a **separate temporary pod**. Your main pod keeps running normally.

### Q: What if the CronJob fails?

**A:** Kubernetes will retry (up to 2 times by default). You can see failures in:
```bash
kubectl -n womba get jobs -l component=index-all
kubectl -n womba describe job <job-name>
```

### Q: Can I run it manually?

**A:** Yes! Create a one-time job:
```bash
kubectl -n womba create job --from=cronjob/womba-index-all \
  womba-index-all-manual-$(date +%s)
```

### Q: How do I know it ran?

**A:** Check job history:
```bash
kubectl -n womba get jobs -l component=index-all
kubectl -n womba get cronjob womba-index-all
```

### Q: What if I want to change the schedule?

**A:** Edit the YAML and reapply:
```bash
vim k8s/cronjob-index-all.yaml  # Change schedule
kubectl -n womba apply -f k8s/cronjob-index-all.yaml
```

### Q: Does it need the same PVC as my main pod?

**A:** Yes! That's the whole point - they share the RAG database. Make sure:
- Main pod mounts: `womba-chroma-data` PVC
- CronJob mounts: `womba-chroma-data` PVC (same name!)

## Troubleshooting

### CronJob not running?

```bash
# Check if CronJob exists
kubectl -n womba get cronjob womba-index-all

# Check if it's suspended
kubectl -n womba get cronjob womba-index-all -o jsonpath='{.spec.suspend}'
# Should be: false

# Check last schedule time
kubectl -n womba get cronjob womba-index-all -o jsonpath='{.status.lastScheduleTime}'
```

### Job failing?

```bash
# Get latest job
LATEST_JOB=$(kubectl -n womba get jobs -l component=index-all \
  --sort-by=.metadata.creationTimestamp \
  -o jsonpath='{.items[-1].metadata.name}')

# Check status
kubectl -n womba describe job $LATEST_JOB

# View logs
kubectl -n womba logs job/$LATEST_JOB
```

### PVC not found?

```bash
# Check if PVC exists
kubectl -n womba get pvc womba-chroma-data

# If not, you need to create it (or update CronJob to use different PVC)
```

## Summary

**The CronJob is like having a robot that:**
1. Wakes up every Saturday at 3 AM
2. Runs `womba index-all` for you
3. Updates your RAG database
4. Goes back to sleep
5. Your main Womba pod automatically benefits from the fresh data

**You don't need to do anything** - it just works automatically! 🎉

