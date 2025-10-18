# Womba API Documentation

## Overview

Womba is an AI-powered test generation platform that analyzes product stories and generates comprehensive test plans with automated test code implementation.

## Base URL

```
Development: http://localhost:8000
Production: https://api.womba.ai
```

## Authentication

Currently, the API uses API keys configured in environment variables. Future versions will support:
- JWT authentication
- OAuth2
- API key per user

## Endpoints

### Health Check

#### GET /health

Check API health status.

**Response:**
```json
{
  "status": "healthy",
  "environment": "development"
}
```

### Stories

#### GET /api/v1/stories/{issue_key}

Fetch a Jira story by key.

**Parameters:**
- `issue_key` (path): Jira issue key (e.g., PROJ-123)

**Response:**
```json
{
  "key": "PROJ-123",
  "summary": "Add user authentication feature",
  "description": "Implement OAuth2 authentication...",
  "issue_type": "Story",
  "status": "In Progress",
  "priority": "High",
  "labels": ["authentication", "security"],
  "components": ["Backend"]
}
```

#### GET /api/v1/stories/{issue_key}/context

Fetch comprehensive context for a story including linked issues.

**Parameters:**
- `issue_key` (path): Jira issue key

**Response:**
```json
{
  "main_story": { ... },
  "linked_stories": [ ... ],
  "related_bugs": [ ... ],
  "context_graph": { ... }
}
```

### Test Plans

#### POST /api/v1/test-plans/generate

Generate a comprehensive test plan for a story.

**Request Body:**
```json
{
  "issue_key": "PROJ-123",
  "upload_to_zephyr": false,
  "project_key": "PROJ",
  "folder_id": "optional-folder-id"
}
```

**Parameters:**
- `issue_key` (required): Jira issue key
- `upload_to_zephyr` (optional): Whether to upload to Zephyr Scale (default: false)
- `project_key` (required if upload_to_zephyr=true): Jira project key for Zephyr
- `folder_id` (optional): Zephyr folder ID for organizing tests

**Response:**
```json
{
  "test_plan": {
    "story": { ... },
    "test_cases": [
      {
        "title": "Verify user login with valid credentials",
        "description": "...",
        "steps": [
          {
            "step_number": 1,
            "action": "Navigate to login page",
            "expected_result": "Login form displayed"
          }
        ],
        "priority": "high",
        "test_type": "functional",
        "tags": ["authentication"],
        "automation_candidate": true
      }
    ],
    "metadata": {
      "total_test_cases": 15,
      "edge_case_count": 5,
      "integration_test_count": 3
    },
    "summary": "Comprehensive test plan for user authentication"
  },
  "zephyr_results": {
    "Test case 1": "TEST-101",
    "Test case 2": "TEST-102"
  }
}
```

#### POST /api/v1/test-plans/{issue_key}/generate

Simplified endpoint for test plan generation.

**Parameters:**
- `issue_key` (path): Jira issue key
- `upload_to_zephyr` (query, optional): Upload to Zephyr
- `project_key` (query, optional): Project key for Zephyr

**Example:**
```
POST /api/v1/test-plans/PROJ-123/generate?upload_to_zephyr=true&project_key=PROJ
```

## Response Codes

- `200`: Success
- `400`: Bad Request (invalid parameters)
- `401`: Unauthorized
- `404`: Resource Not Found
- `500`: Internal Server Error

## Rate Limiting

- Development: No limits
- Production: 60 requests per minute per API key

## Error Responses

```json
{
  "detail": "Error message here"
}
```

## Examples

### Python

```python
import httpx

async def generate_test_plan(issue_key: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/test-plans/generate",
            json={"issue_key": issue_key},
            timeout=60.0
        )
        return response.json()
```

### cURL

```bash
# Fetch story
curl -X GET "http://localhost:8000/api/v1/stories/PROJ-123"

# Generate test plan
curl -X POST "http://localhost:8000/api/v1/test-plans/generate" \
  -H "Content-Type: application/json" \
  -d '{"issue_key": "PROJ-123", "upload_to_zephyr": false}'
```

### JavaScript

```javascript
async function generateTestPlan(issueKey) {
  const response = await fetch('http://localhost:8000/api/v1/test-plans/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ issue_key: issueKey })
  });
  return await response.json();
}
```

## Webhooks (Coming Soon)

Future versions will support webhooks for:
- Test plan generation completion
- Zephyr upload status
- PR creation notifications

## SDK (Coming Soon)

Official SDKs will be available for:
- Python
- JavaScript/TypeScript
- Java
- C#

