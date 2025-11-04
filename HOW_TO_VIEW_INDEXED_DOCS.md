# How to View What's Indexed in RAG

## Quick Commands

### 1. View RAG Statistics
```bash
python womba_cli.py rag-stats
```
Shows counts for each collection (test_plans, jira_stories, confluence_docs, existing_tests, external_docs)

### 2. List All External Docs
```bash
python list_all_indexed_docs.py
```
Shows all 138 PlainID docs with titles, URLs, and whether they have JSON examples

### 3. View Specific Collection
```bash
python view_indexed_docs.py external_docs 10
```
Shows first 10 documents from external_docs with full metadata and content preview

### 4. Search for Specific Content
```python
from src.ai.rag_store import RAGVectorStore
import asyncio

async def search():
    store = RAGVectorStore()
    results = await store.retrieve_similar(
        collection_name='external_docs',
        query_text='policy resolution API',
        top_k=5
    )
    
    for i, result in enumerate(results, 1):
        print(f"{i}. {result['metadata']['title']}")
        print(f"   Distance: {result['distance']:.3f}")
        print(f"   Preview: {result['document'][:200]}...")
        print()

asyncio.run(search())
```

## What's Currently Indexed

### External Docs (138 documents)

**PlainID API Documentation includes:**

- **Authorization APIs**
  - Policy Resolution
  - Permit/Deny
  - User Access Token
  - User List
  - Policy List

- **Policy Management APIs**
  - Import/Export/Validate/Delete Policy
  - Building Blocks CRUD
  - Asset Template operations
  - Application management
  - PAA Groups
  - API Mappers
  - Identity Templates
  - Source management

- **Authentication APIs**
  - Token Exchange
  - Client Credentials
  - OAuth flows
  - IDP integration
  - Auth0/Azure AD setup

- **General Documentation**
  - About Assets, Conditions, Scopes
  - PAAs and PIPs
  - Tenant settings
  - Environment management
  - Authorizers (Access File, API, etc.)
  - SDK documentation
  - And much more...

### Query the Vector DB Directly

```python
from src.ai.rag_store import RAGVectorStore

# Initialize
store = RAGVectorStore()

# Get specific collection
collection = store.get_or_create_collection('external_docs')

# Get all documents (up to limit)
results = collection.get(
    limit=200,
    include=['documents', 'metadatas']
)

# Access the data
for doc_id, meta, content in zip(results['ids'], results['metadatas'], results['documents']):
    print(f"Title: {meta.get('title')}")
    print(f"URL: {meta.get('url')}")
    print(f"Has JSON: {meta.get('has_json_examples')}")
    print(f"Content: {content[:200]}...")
    print()
```

### Check What's Retrieved During Test Generation

When you run test generation, look for these log lines:

```bash
python womba_cli.py generate PLAT-XXXXX --upload
```

In the logs, you'll see:
```
Retrieved X similar test plans
Retrieved X similar docs
Retrieved X similar stories
Retrieved X similar existing tests
Retrieved X similar external docs  ← This shows PlainID docs retrieved
```

### View Specific Document by ID

```python
from src.ai.rag_store import RAGVectorStore

store = RAGVectorStore()
collection = store.get_or_create_collection('external_docs')

# Get by ID
results = collection.get(
    ids=['plainid_01f10cee79fd3cb5_20251103'],
    include=['documents', 'metadatas']
)

print(results)
```

## Available Collections

1. **test_plans** - Previously generated test plans
2. **jira_stories** - Jira stories and tasks
3. **confluence_docs** - Confluence documentation
4. **existing_tests** - Existing Zephyr test cases
5. **external_docs** - PlainID API documentation (138 docs)

## Tools Provided

- **`list_all_indexed_docs.py`** - Lists all 138 PlainID docs with details
- **`view_indexed_docs.py`** - Interactive viewer with search capability
- **`womba_cli.py rag-stats`** - Quick stats overview

## Verify Indexing Worked

```bash
# Should show 138 external_docs
python womba_cli.py rag-stats

# Should list all 138 docs
python list_all_indexed_docs.py | grep "Total documents"

# Should show: Total documents: 138
```

## Next Steps

1. **Run full index-all** to also get Jira/Confluence/Tests:
   ```bash
   python womba_cli.py index-all PLAT
   ```

2. **Generate a test** and check logs to see what was retrieved:
   ```bash
   python womba_cli.py generate PLAT-XXXXX --upload
   ```

3. **Check the test plan** - It should now reference actual PlainID API endpoints with correct JSON payloads!

