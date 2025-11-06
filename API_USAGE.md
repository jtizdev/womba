# Womba API for Frontend Integration

## Running Womba as API Service

Womba includes a **FastAPI server** that can be called from any frontend.

### Start the API Server

**Docker (Recommended)**:
```bash
docker run -d \
  -p 8000:8000 \
  -e ATLASSIAN_BASE_URL=https://your-instance.atlassian.net \
  -e ATLASSIAN_EMAIL=your-email@company.com \
  -e ATLASSIAN_API_TOKEN=your_atlassian_token \
  -e ZEPHYR_API_TOKEN=your_zephyr_token \
  -e OPENAI_API_KEY=your_openai_key \
  -v $(pwd)/data:/app/data \
  --name womba-server \
  womba:latest
```

**Local (Development)**:
```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

---

## API Endpoints

### Base URL
```
http://localhost:8000
```

### API Documentation
```
http://localhost:8000/docs          # Swagger UI
http://localhost:8000/redoc         # ReDoc
```

---

## Key Endpoints for Frontend

### 1. Generate Test Plan

**Endpoint**: `POST /api/v1/test-plans/generate`

**Request**:
```json
{
  "issue_key": "PLAT-15596",
  "upload_to_zephyr": false,
  "project_key": "PLAT",
  "folder_id": null
}
```

**Response**:
```json
{
  "test_plan": {
    "story": {...},
    "test_cases": [
      {
        "title": "Verify vendor policies display correctly...",
        "description": "...",
        "steps": [...],
        "priority": "critical",
        "test_type": "functional",
        "tags": ["UI", "Vendor Compare"]
      }
    ],
    "metadata": {
      "total_test_cases": 8,
      "ai_model": "gpt-4o-mini",
      "ai_reasoning": "..."
    },
    "suggested_folder": "Vendor Compare Tests"
  },
  "zephyr_results": null
}
```

**Features**:
- Story enrichment with zero truncations
- API endpoint extraction from subtasks
- UI tests with navigation (no API endpoints)
- Intelligent folder suggestion
- 51.8% context usage (full details)

### 2. Upload Test Plan to Zephyr

**Included in generate** (set `upload_to_zephyr: true`)

Or separately:

**Endpoint**: `POST /api/v1/test-plans/upload`

**Request**:
```json
{
  "test_plan": {...},
  "project_key": "PLAT",
  "folder_path": "Vendor Compare Tests"
}
```

**Response**:
```json
{
  "test_case_ids": [
    "PLAT-T1234",
    "PLAT-T1235",
    "PLAT-T1236"
  ],
  "folder_id": "12345",
  "folder_path": "Vendor Compare Tests"
}
```

**Features**:
- Intelligent folder matching (reuses existing)
- Creates nested folders if needed
- Links tests to story automatically

### 3. Get Story Context

**Endpoint**: `GET /api/v1/stories/{issue_key}`

**Response**:
```json
{
  "story": {
    "key": "PLAT-15596",
    "summary": "...",
    "description": "...",
    "acceptance_criteria": "...",
    "subtasks": [...]
  },
  "linked_stories": [...],
  "confluence_docs": [...]
}
```

### 4. RAG Management

**Endpoint**: `POST /api/v1/rag/index`

Index story context to RAG:
```json
{
  "issue_key": "PLAT-15596"
}
```

**Endpoint**: `GET /api/v1/rag/stats`

Get RAG database statistics:
```json
{
  "total_documents": 628,
  "collections": {
    "test_plans": 2,
    "confluence_docs": 486,
    "jira_stories": 10,
    "external_docs": 142
  }
}
```

---

## Frontend Integration Example

### React/TypeScript Example

```typescript
// API client
const WOMBA_API = 'http://localhost:8000';

async function generateTestPlan(issueKey: string) {
  const response = await fetch(`${WOMBA_API}/api/v1/test-plans/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      issue_key: issueKey,
      upload_to_zephyr: false
    })
  });
  
  const data = await response.json();
  return data.test_plan;
}

// Usage
const testPlan = await generateTestPlan('PLAT-15596');
console.log(`Generated ${testPlan.test_cases.length} tests`);
console.log(`Suggested folder: ${testPlan.suggested_folder}`);

// Display tests
testPlan.test_cases.forEach(test => {
  console.log(`- ${test.title} (${test.priority})`);
  console.log(`  Type: ${test.test_type}`);
  console.log(`  Tags: ${test.tags.join(', ')}`);
});
```

### Upload to Zephyr

```typescript
async function generateAndUpload(issueKey: string) {
  const response = await fetch(`${WOMBA_API}/api/v1/test-plans/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      issue_key: issueKey,
      upload_to_zephyr: true,
      project_key: 'PLAT'
      // folder_id: optional, uses smart matching
    })
  });
  
  const data = await response.json();
  return {
    testPlan: data.test_plan,
    zephyrIds: data.zephyr_results?.test_case_ids || []
  };
}
```

---

## WebSocket Support (Future)

For real-time progress updates during generation:
```typescript
const ws = new WebSocket('ws://localhost:8000/ws/generate/PLAT-15596');

ws.onmessage = (event) => {
  const progress = JSON.parse(event.data);
  console.log(`Step: ${progress.step}, Status: ${progress.status}`);
  // Update UI with progress
};
```

---

## CORS Configuration

By default, CORS allows all origins (`allow_origins=["*"]`).

**For production**, update in `src/api/main.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

---

## Authentication

Womba supports **Atlassian Connect JWT** for integration with Jira/Confluence apps.

**Middleware**: `src/api/middleware/jwt_auth.py`

For custom auth, add your middleware:
```python
from fastapi import Request, HTTPException

async def custom_auth(request: Request, call_next):
    token = request.headers.get("Authorization")
    if not token or not validate_token(token):
        raise HTTPException(401, "Unauthorized")
    return await call_next(request)

app.middleware("http")(custom_auth)
```

---

## Environment Variables

Required for API mode:
```bash
ATLASSIAN_BASE_URL=https://your-instance.atlassian.net
ATLASSIAN_EMAIL=your-email@company.com
ATLASSIAN_API_TOKEN=your_atlassian_token
ZEPHYR_API_TOKEN=your_zephyr_token
OPENAI_API_KEY=sk-...

# Optional
ANTHROPIC_API_KEY=sk-ant-...  # For Claude models
GITLAB_TOKEN=glpat-...  # For Swagger docs
```

---

## Health Check

**Endpoint**: `GET /health`

**Response**:
```json
{
  "status": "healthy",
  "environment": "production"
}
```

Use for monitoring and load balancer health checks.

---

## 🎯 Summary

Womba provides a **production-ready FastAPI server** for frontend integration:

- ✅ RESTful API endpoints
- ✅ OpenAPI/Swagger documentation
- ✅ Docker deployment
- ✅ CORS support
- ✅ Health checks
- ✅ JWT authentication ready
- ✅ All enrichment features available
- ✅ Zero truncations
- ✅ Smart folder matching

**Deploy and integrate with any frontend!** 🚀
