# Checking RAG Stats in Kubernetes

## Quick Commands

### 1. Get Pod Name
```bash
kubectl -n womba get pods
```

### 2. Check RAG Stats via CLI
```bash
# Get pod name first
POD_NAME=$(kubectl -n womba get pods -o jsonpath='{.items[0].metadata.name}')

# Run RAG stats command
kubectl -n womba exec $POD_NAME -- womba rag-stats
```

### 3. Check RAG Stats via API
```bash
# Get pod name
POD_NAME=$(kubectl -n womba get pods -o jsonpath='{.items[0].metadata.name}')

# Port forward to access API
kubectl -n womba port-forward $POD_NAME 8000:8000 &

# Then in another terminal:
curl http://localhost:8000/api/v1/rag/stats | jq .

# Or if you have a service/ingress:
curl http://your-womba-service/api/v1/rag/stats | jq .
```

### 4. One-liner (if pod name is known)
```bash
kubectl -n womba exec <pod-name> -- womba rag-stats
```

## What RAG Stats Shows

The stats include:
- **Total Documents**: Total across all collections
- **Storage Path**: Where RAG data is stored
- **Collections**:
  - `test_plans`: Generated test plans
  - `confluence_docs`: Confluence documentation
  - `jira_issues`: Jira stories/issues
  - `existing_tests`: Existing test cases
  - `external_docs`: External documentation
  - `swagger_docs`: API documentation (Swagger/OpenAPI)

## Example Output

```
================================================================
📊 RAG Database Statistics
================================================================

📁 Storage Path: /app/data/chroma
📈 Total Documents: 1234

Collections:
  ✓ test_plans: 45 documents
  ✓ confluence_docs: 234 documents
  ✓ jira_issues: 567 documents
  ✓ existing_tests: 123 documents
  ✓ external_docs: 234 documents
  ✓ swagger_docs: 31 documents
================================================================
```

## Troubleshooting

**If command not found:**
- Ensure the pod has the `womba` CLI installed
- Check if you need to use `python -m womba_cli` instead

**If API endpoint not accessible:**
- Check if port 8000 is exposed in the service
- Verify the pod is running: `kubectl -n womba get pods`
- Check pod logs: `kubectl -n womba logs <pod-name>`

