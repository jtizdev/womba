# Atlassian Connect Integration - Technical Documentation

## Architecture Overview

Womba implements the Atlassian Connect framework to integrate directly with Jira Cloud. This document explains the technical implementation.

## Components

### 1. App Descriptor (`src/web/atlassian-connect.json`)

The descriptor tells Jira:
- What the app is called and what it does
- What permissions it needs (scopes)
- What UI modules it provides (panels, glances, pages)
- Where to send lifecycle events (installed, uninstalled)
- Where to send webhooks (issue created, updated, deleted)

**Key Sections:**
```json
{
  "key": "com.womba.jira",
  "baseUrl": "https://womba.onrender.com",
  "authentication": {"type": "jwt"},
  "scopes": ["READ", "WRITE", "DELETE", "ACT_AS_USER"],
  "lifecycle": {...},
  "modules": {...}
}
```

### 2. JWT Authentication

**Implementation**: `src/api/middleware/jwt_auth.py`

Atlassian Connect uses JWT (JSON Web Tokens) for authentication:

1. **Installation**: When installed, Jira sends `clientKey` and `sharedSecret`
2. **Storage**: We store these in `data/installations.json`
3. **Request Validation**: Every request from Jira includes a JWT token
4. **Verification**: We verify the JWT using the stored `sharedSecret`

**JWT Flow:**
```
Jira → [JWT Token] → Womba
                ↓
        Verify signature with sharedSecret
                ↓
        Extract context (clientKey, userKey, issueKey, etc.)
                ↓
        Proceed with request
```

**Key Components:**
- `JWTAuthMiddleware`: FastAPI middleware that validates all `/connect/*` requests
- `require_jwt`: Dependency injection for route handlers
- `JiraContext`: Object containing Jira instance context

### 3. Installation Storage

**Files:**
- `src/models/installation.py`: Pydantic model for installation data
- `src/storage/installation_store.py`: JSON file-based storage

**Stored Data:**
```python
{
  "client_key": "unique-jira-instance-id",
  "shared_secret": "secret-for-jwt-signing",
  "base_url": "https://customer.atlassian.net",
  "product_type": "jira",
  "installed_at": "2025-01-15T10:30:00",
  "enabled": true
}
```

**Operations:**
- `save_installation()`: Store new installation
- `get_installation()`: Retrieve by clientKey
- `delete_installation()`: Remove on uninstall
- `update_enabled_status()`: Toggle enabled/disabled

### 4. Lifecycle Endpoints

**File**: `src/api/routes/connect.py`

| Endpoint | Event | Purpose |
|----------|-------|---------|
| `POST /connect/installed` | App installed | Store clientKey, sharedSecret |
| `POST /connect/uninstalled` | App uninstalled | Delete installation data |
| `POST /connect/enabled` | App enabled | Update enabled status |
| `POST /connect/disabled` | App disabled | Update enabled status |

**Request Payload:**
```json
{
  "key": "com.womba.jira",
  "clientKey": "...",
  "sharedSecret": "...",
  "serverVersion": "...",
  "baseUrl": "https://customer.atlassian.net",
  "productType": "jira",
  "description": "Customer Name",
  "eventType": "installed"
}
```

### 5. UI Modules

#### A. Issue Glance

**Location**: Badge on every Jira issue  
**Endpoint**: `GET /connect/issue-glance?issueKey={issue.key}`  
**Returns**: JSON with label and status

```json
{
  "label": {"value": "5 Tests"},
  "status": {"type": "default"}
}
```

#### B. Issue Panel

**Location**: Right sidebar on issue view page  
**Endpoint**: `GET /connect/issue-panel?issueKey={issue.key}&projectKey={project.key}`  
**Returns**: HTML content (iframe)

**Features:**
- Shows existing tests for the issue
- "Generate Tests" button
- Progress indicator
- Test results display

#### C. General Page

**Location**: Top navigation bar  
**Endpoint**: `GET /connect/test-manager?projectKey={project.key}`  
**Returns**: HTML content (full page)

**Features:**
- Bulk test generation
- RAG data management
- Test generation history
- Search and filters

#### D. Admin Page

**Location**: Jira Settings → Apps  
**Endpoint**: `GET /connect/admin`  
**Returns**: HTML configuration form

**Features:**
- API key configuration
- Data source toggles
- RAG settings
- Auto-generation rules

### 6. Context Extraction

**File**: `src/api/utils/jira_context.py`

Every iframe request from Jira includes context via query parameters:
- `jwt`: JWT token
- `iss`: Issuer (clientKey)
- `xdm_e`: Jira base URL
- `issueKey`: Current issue (for issue-specific modules)
- `projectKey`: Current project
- `userKey`: Current user

**JiraContext Object:**
```python
{
  "client_key": "...",
  "base_url": "https://customer.atlassian.net",
  "user_account_id": "...",
  "issue_key": "PROJ-123",
  "project_key": "PROJ"
}
```

### 7. Webhooks (Future)

**File**: `src/api/routes/webhooks.py` (TODO)

| Event | Webhook URL | Purpose |
|-------|-------------|---------|
| `jira:issue_created` | `/connect/webhooks/issue-created` | Auto-generate tests |
| `jira:issue_updated` | `/connect/webhooks/issue-updated` | Re-generate if needed |
| `jira:issue_deleted` | `/connect/webhooks/issue-deleted` | Clean up data |

## Security

### JWT Validation

All requests are validated:
1. Extract JWT from query string or Authorization header
2. Decode to get `iss` (clientKey)
3. Load `sharedSecret` from storage
4. Verify JWT signature using `sharedSecret`
5. Check expiry time
6. Validate issuer and audience

### Shared Secret Storage

- Stored in `data/installations.json` (file-based)
- Should be moved to secure storage (e.g., environment variables, secrets manager) in production
- Never exposed to client-side code
- Unique per Jira instance

### HTTPS Requirement

- Jira Cloud ONLY communicates over HTTPS
- Render provides HTTPS by default
- Certificate must be valid (no self-signed)

### Scopes

Womba requests these permissions:
- `READ`: Read issues, projects, users
- `WRITE`: Create/update issues (for linking tests)
- `DELETE`: Delete test data (cleanup)
- `ACT_AS_USER`: Act on behalf of the user

## Testing

### Local Development

1. **Use ngrok for HTTPS:**
   ```bash
   ngrok http 8000
   ```

2. **Update descriptor baseUrl:**
   ```json
   "baseUrl": "https://abc123.ngrok.io"
   ```

3. **Install in Jira dev instance**

### Render Deployment

1. Deploy to Render
2. Set environment variable:
   ```
   WOMBA_BASE_URL=https://womba.onrender.com
   ```
3. Install in Jira using: `https://womba.onrender.com/atlassian-connect.json`

## File Structure

```
womba/
├── src/
│   ├── api/
│   │   ├── middleware/
│   │   │   └── jwt_auth.py        # JWT validation middleware
│   │   ├── routes/
│   │   │   ├── connect.py         # Lifecycle + UI modules
│   │   │   └── webhooks.py        # Jira webhooks (TODO)
│   │   ├── utils/
│   │   │   └── jira_context.py    # Context extraction
│   │   └── main.py                # Add Connect routes
│   ├── models/
│   │   └── installation.py        # Installation model
│   ├── storage/
│   │   └── installation_store.py  # Installation storage
│   └── web/
│       ├── atlassian-connect.json # App descriptor
│       └── static/
│           ├── issue-panel.html   # Issue panel UI
│           ├── test-manager.html  # Test manager UI
│           └── admin-config.html  # Admin config UI
├── data/
│   └── installations.json         # Stored installations
└── requirements-minimal.txt       # Added PyJWT, cryptography
```

## API Endpoints

### Public (No Auth)
- `GET /` - Root endpoint
- `GET /health` - Health check
- `GET /atlassian-connect.json` - App descriptor

### Lifecycle (JWT in body)
- `POST /connect/installed` - Installation callback
- `POST /connect/uninstalled` - Uninstallation callback
- `POST /connect/enabled` - Enabled callback
- `POST /connect/disabled` - Disabled callback

### UI Modules (JWT in query)
- `GET /connect/issue-glance` - Issue badge
- `GET /connect/issue-panel` - Issue panel HTML
- `GET /connect/test-manager` - Test manager HTML
- `GET /connect/admin` - Admin config HTML

### Webhooks (JWT in header) - TODO
- `POST /connect/webhooks/issue-created` - Issue created
- `POST /connect/webhooks/issue-updated` - Issue updated
- `POST /connect/webhooks/issue-deleted` - Issue deleted

## Dependencies

Added to `requirements-minimal.txt`:
```
PyJWT==2.8.0          # JWT encoding/decoding
cryptography==41.0.7  # Cryptographic primitives
```

## Environment Variables

```bash
# Required for dynamic baseUrl
WOMBA_BASE_URL=https://womba.onrender.com

# Existing (unchanged)
OPENAI_API_KEY=...
ATLASSIAN_BASE_URL=...
ATLASSIAN_EMAIL=...
ATLASSIAN_API_TOKEN=...
ZEPHYR_API_TOKEN=...
```

## Next Steps

### Phase 2: Enhanced UI (TODO)
- [ ] Build rich issue panel with React/Vue
- [ ] Add real-time progress indicators
- [ ] Implement test result visualization
- [ ] Add inline editing of generated tests

### Phase 3: Webhooks (TODO)
- [ ] Implement webhook handlers
- [ ] Add auto-generation on issue creation
- [ ] Add re-generation on issue updates
- [ ] Add cleanup on issue deletion

### Phase 4: Advanced Features (TODO)
- [ ] Bulk test generation
- [ ] Test templates
- [ ] Custom test frameworks
- [ ] Integration with CI/CD
- [ ] Analytics dashboard

### Phase 5: Production Hardening (TODO)
- [ ] Move to database storage (PostgreSQL)
- [ ] Add rate limiting
- [ ] Implement caching
- [ ] Add monitoring/alerting
- [ ] Performance optimization
- [ ] Error tracking (Sentry)

## Troubleshooting

### Installation fails
- Check Render logs for errors
- Verify descriptor is valid JSON
- Ensure baseUrl is correct and accessible

### JWT validation fails
- Check that installation exists in storage
- Verify sharedSecret matches
- Check JWT expiry time
- Ensure clock sync between servers

### UI modules don't load
- Check browser console for errors
- Verify JWT is in query parameters
- Check Content-Security-Policy headers
- Test outside Jira (direct URL access)

## Resources

- [Atlassian Connect Documentation](https://developer.atlassian.com/cloud/jira/platform/getting-started-with-connect/)
- [JWT Specification](https://jwt.io/)
- [FastAPI Middleware Guide](https://fastapi.tiangolo.com/advanced/middleware/)
- [Render Deployment Guide](https://render.com/docs)

---

**Status**: ✅ Phase 1 Complete  
**Next**: Phase 2 - Enhanced UI Development

