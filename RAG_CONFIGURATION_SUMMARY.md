# RAG Configuration Summary

## Current Status

### ✅ What's Working
- PlainID documentation indexing is **enabled**
- Base URL configured: `https://docs.plainid.io/v1-api`
- Crawler generates 12 URLs to fetch
- **3 external docs successfully indexed:**
  1. Policy Resolution (`/apidocs/policy-resolution`)
  2. Policy Resolution 1 (`/apidocs/policy-resolution-1`)
  3. Authentication (`/apidocs/authentication`)

### ⚠️ Issues Found

#### 1. Limited PlainID Docs (Only 3/12 URLs Successful)
**Problem:** Crawler attempts to fetch 12 URLs but only 3 return valid content.

**URLs that likely failed (404 or network errors):**
- `/v1-api/apidocs/policy-resolution` (duplicate path)
- `/v1-api/apidocs/policy-resolution-1` (duplicate path)
- `/apidocs/authorization`
- `/apidocs/users`
- `/apidocs/groups`
- `/apidocs/policies`
- `/apidocs/attributes`
- `/apidocs/audit`
- `/apidocs/configuration`

**Solution:** Add actual PlainID API documentation URLs to your `.env`:
```bash
# Option 1: Set explicit URLs (recommended)
PLAINID_DOC_URLS='["https://docs.plainid.io/v1-api/actual-endpoint-1", "https://docs.plainid.io/v1-api/actual-endpoint-2"]'

# Option 2: Update base URL if structure is different
PLAINID_DOC_BASE_URL=https://docs.plainid.io/correct-path
```

#### 2. Embedding Token Limit Errors
**Problem:** Some documents still exceed 8192 tokens even after chunking.

**Errors seen:**
```
Error code: 400 - This model's maximum context length is 8192 tokens, 
however you requested 8480 tokens
```

**Solution:** The chunking safety margin needs adjustment. Documents are being chunked at 85% of limit (6963 tokens), but when sent in batches, the total can exceed limits.

#### 3. No Visibility Into Retrieved Context
**Problem:** You can't see what RAG retrieved for a specific test generation.

**Solution:** Use the new `check_external_docs.py` script or add logging.

## How to View What Was Retrieved

### View All External Docs
```bash
python check_external_docs.py
```

### View RAG Stats
```bash
python womba_cli.py rag-stats
```

### View Specific Collection
```python
from src.ai.rag_store import RAGVectorStore

store = RAGVectorStore()
collection = store.get_or_create_collection('external_docs')
results = collection.get(limit=20)

for doc_id, meta in zip(results['ids'], results['metadatas']):
    print(f"- {meta.get('title')}: {meta.get('url')}")
```

## Configuration Options

### Current Settings (from `.env`)
```bash
# PlainID Documentation Indexing
PLAINID_DOC_INDEX_ENABLED=true
PLAINID_DOC_BASE_URL=https://docs.plainid.io/v1-api
PLAINID_DOC_MAX_PAGES=100
PLAINID_DOC_MAX_DEPTH=3
PLAINID_DOC_REQUEST_DELAY=0.5
PLAINID_DOC_PROJECT_KEY=PLAT
```

### Recommended Additions
```bash
# Add explicit URLs for known PlainID endpoints
PLAINID_DOC_URLS='[
  "https://docs.plainid.io/v1-api/apidocs/policy-resolution",
  "https://docs.plainid.io/v1-api/apidocs/authentication",
  "https://docs.plainid.io/v1-api/apidocs/authorization",
  "https://docs.plainid.io/v1-api/apidocs/users",
  "https://docs.plainid.io/v1-api/apidocs/policies"
]'
```

## Next Steps

1. **Find Correct PlainID URLs:**
   - Visit https://docs.plainid.io/v1-api in your browser
   - Identify the actual API documentation pages
   - Add them to `PLAINID_DOC_URLS` in `.env`

2. **Re-index:**
   ```bash
   python womba_cli.py rag-clear -y
   python womba_cli.py index-all PLAT
   ```

3. **Verify:**
   ```bash
   python check_external_docs.py
   python womba_cli.py rag-stats
   ```

4. **Test Generation:**
   ```bash
   python womba_cli.py generate PLAT-XXXX --upload
   ```
   
   Check logs for "Retrieved context" to see what was used.

## Adding Retrieval Visibility

To see what RAG retrieved during test generation, check the logs for:
- "Retrieved X similar test plans"
- "Retrieved X similar docs"
- "Retrieved X similar stories"
- "Retrieved X similar existing tests"
- "Retrieved X similar external docs"

Or add this to your test generation command to see full context:
```python
# In src/ai/test_plan_generator.py, after retrieval:
logger.info(f"Retrieved context summary: {context.get_summary()}")
for doc in context.similar_external_docs:
    logger.info(f"  - External doc: {doc.get('metadata', {}).get('title', 'Unknown')}")
```

