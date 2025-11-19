# GitLab MCP OAuth Setup - Step-by-Step Guide

## ✅ STEP 1: Docker Build
**Status:** IN PROGRESS (building now...)

Building Docker image with:
- Node.js 20.x ✅
- npm ✅
- mcp-remote support ✅
- OAuth cache directory ✅

---

## ⏳ STEP 2: Start Womba (will do after build completes)

```bash
docker compose up -d womba
```

Expected output:
```
✓ Container started
✓ API listening on http://localhost:8000
```

---

## ⏳ STEP 3: Test MCP Configuration (local first)

```bash
cd /Users/royregev/womba
python test_mcp_oauth.py
```

Expected output:
```
✓ PASS: Configuration
✓ PASS: MCP Client Initialization
✓ PASS: Fallback Extractor
✓ PASS: OAuth Flow

Total: 4/4 tests passed
```

---

## ⏳ STEP 4: Test MCP in Docker Container

```bash
docker compose exec womba python test_mcp_oauth.py
```

This will verify MCP works inside the Docker container.

---

## ⏳ STEP 5: Trigger First OAuth Login (browser will open)

**Option A - Local:**
```bash
python test_mcp_setup.py
# Browser will open → Click "Authorize"
# Credentials cached in ~/.mcp-auth/
```

**Option B - In Docker:**
```bash
docker compose exec womba python test_mcp_setup.py
# Browser will open on your machine
# Click "Authorize"
# Cache accessible to container
```

---

## ⏳ STEP 6: Generate Test Plan to Trigger MCP

1. Go to: http://localhost:3000 (womba-ui)
2. Enter story: `PLAT-13541`
3. Click "Generate Test Plan"
4. Watch logs for MCP activity:
   ```bash
   docker compose logs -f womba
   ```

Expected in logs:
```
INFO: Starting GitLab MCP fallback extraction for PLAT-13541
INFO: Using mcp-remote with OAuth authentication
INFO: Found N code search results
INFO: GitLab MCP fallback extracted N API specifications
```

---

## ⏳ STEP 7: Verify Test Plan Generated

Check the generated test plan includes:
- ✅ API tests from MCP search
- ✅ UI tests with navigation
- ✅ Proper test naming (not "Validate...")
- ✅ Temperature 0.2 (deterministic)

---

## 📋 Environment Check

Current setup:
```
GITLAB_FALLBACK_ENABLED=true
GITLAB_BASE_URL=https://gitlab.com
GITLAB_GROUP_PATH=plainid/srv
TEMPERATURE=0.2 ✅ (fixed)
```

OAuth credentials location: `~/.mcp-auth/`

---

## 🎯 Success Criteria

✅ Docker builds successfully
✅ Container starts without errors
✅ MCP client detects mpc-remote
✅ Browser opens for first OAuth login
✅ User clicks "Authorize"
✅ Credentials cached automatically
✅ Test plan generation triggers MCP fallback
✅ MCP finds endpoints from codebase
✅ Test plan includes found endpoints

---

## 🔄 Timeline

1. Docker build: ~2-3 minutes (IN PROGRESS)
2. Container start: ~10 seconds
3. Local MCP test: ~5 seconds
4. Docker MCP test: ~5 seconds
5. OAuth browser login: Manual (~1 minute)
6. Test plan generation: ~30 seconds
7. MCP search: ~10-20 seconds

**Total estimated time: ~5-7 minutes**

---

## ⚠️ Important Notes

1. **First OAuth**: Browser WILL open automatically - this is normal!
2. **Click "Authorize"**: Required to grant MCP access
3. **Cached for life**: After first OAuth, no more browser logins needed
4. **Docker mounts**: Cache dir persists across container restarts
5. **Temperature**: Now at 0.2 for deterministic test generation

Ready to continue? Answer when you see Docker build complete!

