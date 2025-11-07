# Womba - AI-Powered Test Generation Platform

## Overview

Womba is an AI-powered test generation platform that automatically generates comprehensive test cases from Jira stories. It integrates with Jira, Confluence, and Zephyr Scale to create context-aware test plans using RAG (Retrieval-Augmented Generation) technology.

## Core Functionality

### Main Workflow
1. **Story Collection**: Fetches Jira stories with full context (subtasks, linked issues, comments, Confluence docs)
2. **Context Enrichment**: Uses RAG to retrieve similar test plans and patterns from ChromaDB
3. **AI Generation**: Uses GPT-4 to generate comprehensive test cases based on story complexity
4. **Zephyr Integration**: Optionally uploads generated tests directly to Zephyr Scale
5. **History Tracking**: Tracks all test generation activities for analytics

### Key Features
- **Smart Complexity Scoring**: Automatically determines test count (4-15 tests) based on story complexity
- **RAG-Powered**: Learns from existing test plans using ChromaDB vector database
- **Deep Context Analysis**: Uses subtasks, linked issues, Confluence docs, and comments
- **Atlassian Connect Integration**: Works as a Jira app with UI panels
- **Automation Support**: Can generate test code and create PRs (optional)
- **Indexing Support**: **CRITICAL** - The UI must support indexing operations to populate the RAG database

## UI Requirements - Indexing Support

**IMPORTANT**: The UI must provide full support for RAG indexing functionality. This is essential for the platform to learn from existing tests and improve test generation quality. The UI needs to allow users to:

1. **Index Individual Stories**: Users should be able to index a specific Jira story into RAG
2. **Batch Index Tests**: Users should be able to batch index existing tests from Zephyr Scale
3. **View Indexing Statistics**: Display how many documents are indexed in each collection
4. **Search Indexed Content**: Allow users to search the RAG database to see what's been indexed
5. **Clear Indexed Data**: Provide ability to clear collections (with confirmation)

Indexing is a critical feature because:
- It enables the RAG system to learn from past test plans
- It improves test generation quality by providing context from similar stories
- It allows the system to maintain project-specific knowledge
- Without indexing, the RAG system cannot retrieve relevant context

## API Endpoints

### Base URL
- **Development**: `http://localhost:8000`
- **Production**: `https://api.womba.ai`

### Health & Status

#### GET `/health`
Check API health status.

**Response:**
```json
{
  "status": "healthy",
  "environment": "development"
}
```

#### GET `/`
Root endpoint with API information.

**Response:**
```json
{
  "name": "Womba API",
  "version": "0.1.0",
  "status": "operational",
  "docs": "/docs",
  "connect_descriptor": "/atlassian-connect.json"
}
```

### Story Management

#### GET `/api/v1/stories/{issue_key}`
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

#### GET `/api/v1/stories/{issue_key}/context`
Fetch comprehensive context for a story including linked issues, subtasks, and related bugs.

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

### Test Plan Generation

#### POST `/api/v1/test-plans/generate`
Generate a comprehensive test plan for a Jira story. This is the main endpoint.

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
    "test_case_ids": ["TEST-101", "TEST-102"],
    "uploaded_count": 15
  }
}
```

#### POST `/api/v1/test-plans/{issue_key}/generate`
Simplified endpoint for test plan generation.

**Parameters:**
- `issue_key` (path): Jira issue key
- `upload_to_zephyr` (query, optional): Upload to Zephyr
- `project_key` (query, optional): Project key for Zephyr

**Example:**
```
POST /api/v1/test-plans/PROJ-123/generate?upload_to_zephyr=true&project_key=PROJ
```

### RAG (Retrieval-Augmented Generation) Management

**NOTE**: These endpoints are CRITICAL for the UI to support. The UI must provide interfaces for all of these operations.

#### GET `/api/v1/rag/stats`
Get RAG database statistics showing how many documents are indexed in each collection.

**UI Requirement**: Display these statistics prominently, showing:
- Total documents indexed per collection
- Project-specific counts
- Last indexing date/time

**Response:**
```json
{
  "test_plans": {
    "count": 150,
    "collections": ["test_plans"]
  },
  "stories": {
    "count": 200,
    "collections": ["stories"]
  }
}
```

#### POST `/api/v1/rag/index`
Index a story's context into RAG for future retrieval.

**UI Requirement**: Provide a form or button to index individual stories. Should show:
- Input field for story key
- Optional project key field
- Progress indicator during indexing
- Success/error feedback

**Request Body:**
```json
{
  "story_key": "PROJ-123",
  "project_key": "PROJ"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Successfully indexed PROJ-123",
  "story_key": "PROJ-123",
  "project_key": "PROJ"
}
```

#### POST `/api/v1/rag/index/batch`
Batch index existing tests from Zephyr into RAG.

**UI Requirement**: Provide a batch indexing interface with:
- Project key selector
- Max tests input (default: 1000)
- Progress bar for batch operations
- Ability to cancel long-running operations
- Summary of results (how many tests indexed)

**Parameters:**
- `project_key` (query, required): Project key to index tests for
- `max_tests` (query, optional): Maximum number of tests to index (default: 1000)

**Example:**
```
POST /api/v1/rag/index/batch?project_key=PROJ&max_tests=1000
```

**Response:**
```json
{
  "status": "success",
  "message": "Successfully indexed 150 tests",
  "project_key": "PROJ",
  "tests_indexed": 150
}
```

#### POST `/api/v1/rag/search`
Search RAG database for similar documents.

**UI Requirement**: Provide a search interface allowing users to:
- Enter search queries
- Select collection to search
- Set number of results (top_k)
- Filter by project key
- Display results with relevance scores

**Request Body:**
```json
{
  "query": "authentication tests",
  "collection": "test_plans",
  "top_k": 10,
  "project_key": "PROJ"
}
```

**Parameters:**
- `query` (required): Search query text
- `collection` (optional): Collection to search (default: "test_plans")
- `top_k` (optional): Number of results to return (default: 10)
- `project_key` (optional): Filter by project key

**Response:**
```json
{
  "status": "success",
  "collection": "test_plans",
  "results_count": 10,
  "results": [
    {
      "document": "...",
      "metadata": { ... },
      "score": 0.95
    }
  ]
}
```

#### DELETE `/api/v1/rag/clear`
Clear RAG database (all collections or specific collection).

**UI Requirement**: Provide clear functionality with:
- Warning confirmation dialog
- Option to clear specific collection or all collections
- Clear indication of what will be deleted
- Confirmation of successful deletion

**Parameters:**
- `collection` (query, optional): Collection name to clear (clears all if not specified)

**Example:**
```
DELETE /api/v1/rag/clear?collection=test_plans
```

**Response:**
```json
{
  "status": "success",
  "message": "Cleared collection: test_plans"
}
```

### UI & Statistics

#### GET `/api/v1/health`
Health check for UI.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00"
}
```

#### GET `/api/v1/stats`
Get statistics about test generation activity.

**Response:**
```json
{
  "total_tests": 500,
  "total_stories": 50,
  "time_saved": 100,
  "success_rate": 95.5,
  "tests_this_week": 25,
  "stories_this_week": 3
}
```

#### GET `/api/v1/history`
Get test generation history.

**Parameters:**
- `limit` (query, optional): Number of items to return (default: 50)
- `offset` (query, optional): Pagination offset (default: 0)

**Response:**
```json
[
  {
    "id": "hist_1",
    "story_key": "PROJ-123",
    "created_at": "2024-01-01T12:00:00",
    "test_count": 15,
    "status": "success",
    "duration": 45,
    "zephyr_ids": ["TEST-101", "TEST-102"]
  }
]
```

#### GET `/api/v1/history/{history_id}`
Get details for a specific history item.

#### GET `/api/v1/config`
Get current configuration.

**Response:**
```json
{
  "atlassian_url": "https://example.atlassian.net",
  "atlassian_email": "user@example.com",
  "project_key": "PROJ",
  "ai_model": "gpt-4o",
  "repo_path": "/path/to/repo",
  "git_provider": "auto",
  "default_branch": "master",
  "auto_upload": false,
  "auto_create_pr": true,
  "ai_tool": "aider"
}
```

#### POST `/api/v1/config`
Save configuration.

**Request Body:**
```json
{
  "atlassian_url": "https://example.atlassian.net",
  "atlassian_email": "user@example.com",
  "atlassian_api_token": "...",
  "zephyr_api_token": "...",
  "openai_api_key": "...",
  "project_key": "PROJ",
  "ai_model": "gpt-4o",
  "repo_path": "/path/to/repo",
  "git_provider": "auto",
  "default_branch": "master",
  "auto_upload": false,
  "auto_create_pr": true,
  "ai_tool": "aider"
}
```

#### POST `/api/v1/config/validate`
Validate specific configuration settings.

**Request Body:**
```json
{
  "service": "jira",
  "atlassian_url": "https://example.atlassian.net",
  "atlassian_api_token": "..."
}
```

**Response:**
```json
{
  "valid": true,
  "message": "Jira connection successful"
}
```

### Atlassian Connect Integration

#### POST `/connect/installed`
Called when the app is installed in a Jira instance. Stores installation credentials.

**Request Body:**
```json
{
  "key": "...",
  "clientKey": "...",
  "sharedSecret": "...",
  "baseUrl": "https://example.atlassian.net",
  "productType": "jira",
  "eventType": "installed"
}
```

#### POST `/connect/uninstalled`
Called when the app is uninstalled from a Jira instance.

#### POST `/connect/enabled`
Called when the app is enabled in a Jira instance.

#### POST `/connect/disabled`
Called when the app is disabled in a Jira instance.

#### GET `/connect/issue-glance`
Returns data for the issue glance (badge showing test count on Jira issues).

**Parameters:**
- `issueKey` (query, required): Jira issue key

**Response:**
```json
{
  "label": {
    "value": "15 Tests"
  },
  "status": {
    "type": "default"
  }
}
```

#### GET `/connect/issue-panel`
Returns HTML for the issue panel that appears on Jira issue view. Allows users to generate tests directly from the issue.

**Parameters:**
- `issueKey` (query, required): Jira issue key
- `projectKey` (query, optional): Project key

#### GET `/connect/test-manager`
Returns HTML for the test manager full page (general page accessible from Jira's top navigation).

**Parameters:**
- `projectKey` (query, optional): Project key

#### GET `/connect/admin`
Returns HTML for the admin configuration page (only accessible to Jira administrators).

## How It Works

### Test Generation Process

1. **Story Collection** (`StoryCollector`):
   - Fetches main story from Jira
   - Collects all subtasks
   - Finds linked stories and related bugs
   - Retrieves Confluence documentation if linked
   - Builds context graph

2. **Context Enrichment** (`StoryEnricher`):
   - Uses RAG to retrieve similar test plans from ChromaDB
   - Scores story complexity
   - Enriches with related context
   - **Note**: RAG retrieval only works if content has been indexed first!

3. **Test Plan Generation** (`TestPlanGenerator`):
   - Uses GPT-4 with enriched context
   - Generates test cases based on complexity:
     - Simple (score < 5): 4-6 tests
     - Medium (5-12): 6-10 tests
     - Complex (12+): 10-15 tests
   - Creates test steps with actions and expected results
   - Tags tests with categories and priorities

4. **Zephyr Upload** (`ZephyrIntegration`):
   - Uploads test cases to Zephyr Scale
   - Organizes in folders
   - Links back to Jira story
   - Returns Zephyr test case IDs

5. **RAG Indexing** (`ContextIndexer`):
   - Automatically indexes generated test plans
   - Stores in ChromaDB for future retrieval
   - Enables learning from past tests
   - **This is why indexing support in the UI is critical!**

### RAG System

- **Collections**: 
  - `test_plans`: Generated test plans
  - `stories`: Story contexts
- **Storage**: ChromaDB vector database
- **Embeddings**: OpenAI embeddings
- **Retrieval**: Semantic search with project filtering
- **Indexing**: Must be done before retrieval can work effectively

### Authentication

- **JWT Authentication**: For Atlassian Connect endpoints (validates JWT tokens from Jira)
- **API Keys**: For direct API access (configured in environment variables)
- **Installation Store**: Stores per-installation credentials for multi-tenant support

## Usage Examples

### Generate Test Plan (Basic)
```bash
curl -X POST "http://localhost:8000/api/v1/test-plans/generate" \
  -H "Content-Type: application/json" \
  -d '{"issue_key": "PROJ-123"}'
```

### Generate and Upload to Zephyr
```bash
curl -X POST "http://localhost:8000/api/v1/test-plans/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "issue_key": "PROJ-123",
    "upload_to_zephyr": true,
    "project_key": "PROJ",
    "folder_id": "folder-123"
  }'
```

### Get Story Context
```bash
curl -X GET "http://localhost:8000/api/v1/stories/PROJ-123/context"
```

### Index Story into RAG (CRITICAL FOR UI)
```bash
curl -X POST "http://localhost:8000/api/v1/rag/index" \
  -H "Content-Type: application/json" \
  -d '{
    "story_key": "PROJ-123",
    "project_key": "PROJ"
  }'
```

### Batch Index Tests from Zephyr (CRITICAL FOR UI)
```bash
curl -X POST "http://localhost:8000/api/v1/rag/index/batch?project_key=PROJ&max_tests=1000"
```

### Search RAG
```bash
curl -X POST "http://localhost:8000/api/v1/rag/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "authentication login tests",
    "collection": "test_plans",
    "top_k": 5,
    "project_key": "PROJ"
  }'
```

### Get RAG Statistics (CRITICAL FOR UI)
```bash
curl -X GET "http://localhost:8000/api/v1/rag/stats"
```

### Clear RAG Collection (CRITICAL FOR UI)
```bash
curl -X DELETE "http://localhost:8000/api/v1/rag/clear?collection=test_plans"
```

### Get Statistics
```bash
curl -X GET "http://localhost:8000/api/v1/stats"
```

### Get History
```bash
curl -X GET "http://localhost:8000/api/v1/history?limit=10&offset=0"
```

## Important Notes

1. **Indexing is Critical**: The RAG system requires indexing before it can effectively retrieve context. The UI MUST support indexing operations.

2. **Project Key**: Most endpoints support `project_key` parameter for project isolation

3. **RAG Auto-Indexing**: Test plans are automatically indexed after generation, but users may want to manually index existing stories/tests

4. **Initial Setup**: Users typically need to run batch indexing once to populate the RAG database with existing tests

5. **Complexity Scoring**: Test count is automatically determined based on story complexity

6. **Zephyr Integration**: Requires `project_key` when `upload_to_zephyr=true`

7. **History Tracking**: All test generations are tracked for analytics

8. **Error Handling**: All endpoints return appropriate HTTP status codes (400, 404, 500)

9. **CORS**: API supports CORS for web UI access

10. **Static Files**: UI static files are served from `/static` and `/ui` paths

## UI Integration Requirements

The platform includes a web UI that can be accessed via:
- Static files: `/static/*` and `/ui/*`
- Issue panel: `/connect/issue-panel` (for Jira integration)
- Test manager: `/connect/test-manager` (full page)
- Admin config: `/connect/admin` (admin only)

### Required UI Features

The UI must provide interfaces for:

1. **Test Plan Generation**:
   - Form to enter issue key
   - Option to upload to Zephyr
   - Progress indicator
   - Display generated test plan
   - Show Zephyr upload results

2. **Indexing Management** (CRITICAL):
   - **Index Individual Story**: Form with story key input
   - **Batch Index**: Interface with project selector and max tests input
   - **View Statistics**: Dashboard showing indexed document counts
   - **Search RAG**: Search interface to query indexed content
   - **Clear Collections**: Confirmation dialog for clearing data

3. **History & Statistics**:
   - View test generation history
   - Display statistics dashboard
   - Filter by date, project, status

4. **Configuration**:
   - Settings form for API keys and credentials
   - Validation for each service
   - Save/load configuration

5. **Story Context**:
   - View story details
   - Display linked stories and context graph

The UI uses the API endpoints above to:
- Generate test plans
- **Index stories and tests into RAG** (MUST HAVE)
- View history and statistics
- Manage configuration
- Search and manage RAG data
- View test generation results

