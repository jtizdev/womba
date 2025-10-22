# RAG (Retrieval-Augmented Generation) in Womba

## Overview

Womba uses RAG to ensure that test generation relies on **company-specific context** rather than generic AI knowledge. This produces more accurate, consistent, and domain-specific test plans.

## How It Works

### 1. **Context Indexing**
When you generate test plans, Womba automatically indexes:
- **Generated test plans** - Learn from past test patterns
- **Confluence documentation** - Use your company's terminology
- **Jira stories** - Understand your domain
- **Existing Zephyr tests** - Match your testing style

### 2. **Semantic Retrieval**
When generating a new test plan, Womba:
1. Creates an embedding of the new story
2. Searches the vector database for similar content
3. Retrieves the most relevant examples
4. Injects them into the AI prompt

### 3. **Grounded Generation**
The AI is instructed to:
- **Prioritize retrieved examples** over generic knowledge
- **Match the style** of your existing tests
- **Use exact terminology** from your documentation
- **Follow patterns** from similar past stories

## Configuration

### Enable/Disable RAG

```bash
# In interactive setup
womba configure
# Choose "Enable RAG? (y/n) [y]"

# Or in .env file
ENABLE_RAG=true
RAG_AUTO_INDEX=true
```

### Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `enable_rag` | `true` | Enable RAG retrieval |
| `rag_auto_index` | `true` | Auto-index after generation |
| `rag_collection_path` | `./data/chroma` | Storage path |
| `rag_top_k_tests` | `5` | Similar test plans to retrieve |
| `rag_top_k_docs` | `10` | Similar docs to retrieve |
| `rag_top_k_stories` | `10` | Similar stories to retrieve |
| `rag_top_k_existing` | `20` | Similar existing tests |

## CLI Commands

### Index a Story
```bash
womba index PLAT-12991
```
Indexes the story's context (Confluence docs, linked stories, etc.)

### Batch Index
```bash
womba index-all
```
Indexes all existing Zephyr tests for your project (one-time setup)

### View Statistics
```bash
womba rag-stats
```
Shows how many documents are indexed in each collection

### Clear Database
```bash
womba rag-clear
```
Deletes all RAG data (use with caution)

## API Endpoints

### Get Statistics
```bash
GET /api/v1/rag/stats
```

### Index a Story
```bash
POST /api/v1/rag/index
{
  "story_key": "PLAT-12991",
  "project_key": "PLAT"
}
```

### Batch Index Tests
```bash
POST /api/v1/rag/index/batch?project_key=PLAT&max_tests=1000
```

### Search RAG
```bash
POST /api/v1/rag/search
{
  "query": "authentication tests",
  "collection": "test_plans",
  "top_k": 10,
  "project_key": "PLAT"
}
```

### Clear Collections
```bash
DELETE /api/v1/rag/clear?collection=test_plans
DELETE /api/v1/rag/clear  # Clear all
```

## Best Practices

### 1. **Initial Setup**
Run batch indexing once to populate the database:
```bash
womba index-all
```

### 2. **Continuous Learning**
Keep RAG auto-indexing enabled so new test plans are automatically learned

### 3. **Quality Over Quantity**
RAG retrieves the **most similar** documents, not all documents. The top-k settings control this.

### 4. **Project Isolation**
RAG uses `project_key` to filter results, so each project learns from its own context

### 5. **Regular Maintenance**
- Monitor with `womba rag-stats`
- Clear stale data if needed with `womba rag-clear`

## Performance Impact

### Indexing
- **Time**: ~100ms per document (OpenAI embedding)
- **When**: Happens in background after test generation
- **Impact**: Minimal (non-blocking)

### Retrieval
- **Time**: ~200-500ms (semantic search)
- **When**: Before test generation
- **Impact**: Low (adds ~0.5s to generation time)

### Recommendation
**Keep RAG enabled** - the benefits far outweigh the minimal performance cost.

## Troubleshooting

### Common Errors and Solutions

#### Error: "OpenAI API key not configured"
**Problem**: RAG requires OpenAI embeddings but API key is missing.

**Solutions**:
1. Run `womba configure` and enter your OpenAI API key
2. Or add to `.env`: `OPENAI_API_KEY=your-key-here`
3. Or set environment variable: `export OPENAI_API_KEY=your-key-here`

**Verify**: Run `womba rag-stats` - should work without errors

#### Error: "UnboundLocalError: cannot access local variable"
**Problem**: Bug in story context collection (fixed in latest version).

**Solutions**:
1. Update to latest version
2. Error should now be handled gracefully with warning logs

#### Error: "Collection is empty"
**Problem**: Trying to retrieve from empty RAG database.

**Solutions**:
1. Run initial indexing: `womba index-all`
2. Or index specific stories: `womba index PLAT-123`
3. System will now work gracefully with empty collections (returns no context)

**Verify**: Check `womba rag-stats` for document counts

### RAG Not Retrieving Context?

**Symptoms**: Test generation works but doesn't use RAG context.

**Debugging Steps**:
1. Check if RAG is enabled: `womba rag-stats`
2. Verify database has content:
   ```bash
   womba rag-stats
   # Should show > 0 documents in collections
   ```
3. Check logs for "RAG context retrieved" messages
4. Verify project key matches between indexed and retrieved data

**Solutions**:
- If database empty: Run `womba index-all`
- If project mismatch: Ensure consistent project keys
- If still not working: Check logs for retrieval errors

### Empty Retrieval Results?

**Why**: Semantic search found no similar documents.

**Common Causes**:
- **Empty database**: Run `womba index-all` first
- **Project key mismatch**: Check that indexed data uses same project key
- **Very different stories**: RAG requires some similarity to match
- **Fresh installation**: Need to build up context over time

**Solutions**:
1. Index existing data: `womba index-all`
2. Verify project key: Check logs for project filtering
3. Allow time for context to build up (10+ test plans recommended)

### Slow Generation?

**Expected**: RAG adds ~0.5-1s to generation time.

**If slower than 5s**:
1. Check internet connection (OpenAI embeddings)
2. Check ChromaDB disk I/O (large databases)
3. Consider reducing top-k values in settings

**Options**:
- **Acceptable slowness**: Keep RAG enabled (worth the time)
- **Too slow**: Reduce `rag_top_k_*` values in settings
- **Must be fast**: Set `ENABLE_RAG=false` (not recommended)

### Indexing Failures

**Symptoms**: `womba index` or `womba index-all` fails.

**Common Errors**:

1. **"Configuration Error: OpenAI API key not configured"**
   - Run `womba configure` and add API key

2. **"Failed to fetch existing tests"**
   - Check Zephyr credentials
   - Verify project key exists
   - Check network connection

3. **"Failed to embed batch"**
   - OpenAI API error - check rate limits
   - Check API key validity
   - Verify internet connection

**Recovery**:
- Indexing is idempotent - safe to retry
- Clear and re-index if corrupted: `womba rag-clear && womba index-all`

### How to Verify RAG is Working

Run this checklist:

```bash
# 1. Check RAG status
womba rag-stats
# Should show > 0 documents

# 2. Index test data
womba index PLAT-123
# Should complete without errors

# 3. Generate with RAG
womba generate PLAT-124
# Check logs for "RAG context retrieved" message

# 4. Verify retrieval
# Look for "Retrieved: X test plans, Y docs..." in logs
```

### Manual Testing

For comprehensive validation, run:

```bash
python tests/manual/test_rag_manual.py
```

This will:
- Test OpenAI embeddings
- Test vector store operations
- Test indexing workflow
- Test retrieval workflow
- Show detailed results and errors

### Performance Expectations

| Operation | Expected Time | Acceptable Range |
|-----------|--------------|------------------|
| Index 1 story | 0.5-1s | Up to 3s |
| Index 100 tests | 30-60s | Up to 2min |
| Retrieve context | 0.3-0.8s | Up to 2s |
| Generate with RAG | +0.5-1s overhead | +Up to 3s |

**If outside acceptable range**: Check network, API limits, or disk I/O.

### Debug Mode

Enable detailed logging:

```python
# In your code or .env
LOG_LEVEL=DEBUG
```

Look for these log messages:
- `"Initialized RAG vector store"`
- `"Retrieving RAG context for story..."`
- `"Retrieved: X test plans, Y docs..."`
- `"RAG context retrieved: ..."`

### Getting Help

If issues persist:

1. **Check logs**: Look for ERROR or WARNING messages
2. **Run manual tests**: `python tests/manual/test_rag_manual.py`
3. **Verify configuration**: Ensure all API keys are set
4. **Test without RAG**: Set `ENABLE_RAG=false` to isolate issue
5. **Check versions**: Ensure ChromaDB and OpenAI client are up to date

## Architecture

```
┌─────────────────┐
│  User Request   │
└────────┬────────┘
         │
         v
┌─────────────────┐
│ Story Collector │  ← Fetches context
└────────┬────────┘
         │
         v
┌─────────────────┐
│  RAG Retriever  │  ← Searches vector DB
└────────┬────────┘
         │
         v
┌─────────────────┐
│ Test Generator  │  ← Generates with context
└────────┬────────┘
         │
         v
┌─────────────────┐
│ Context Indexer │  ← Stores for future
└─────────────────┘
```

## Technical Details

### Vector Database
- **ChromaDB** (local, persistent)
- **Embeddings**: OpenAI `text-embedding-3-small`
- **Similarity**: Cosine distance

### Collections
1. `test_plans` - Past generated test plans
2. `confluence_docs` - Company documentation
3. `jira_stories` - Historical stories
4. `existing_tests` - Zephyr test cases

### Metadata Filtering
Each document includes:
- `project_key` - For isolation
- `story_key` / `test_key` - For reference
- `components` - For relevance
- `timestamp` - For freshness

## FAQ

**Q: Does RAG require internet?**  
A: Yes, for OpenAI embeddings. ChromaDB is local.

**Q: Can I use without RAG?**  
A: Yes, set `ENABLE_RAG=false`. System works without RAG.

**Q: How much does RAG cost?**  
A: ~$0.0001 per document (OpenAI embedding cost). Very cheap.

**Q: Can I use other embedding models?**  
A: Currently OpenAI only. Can extend to support sentence-transformers (free).

**Q: Is RAG data shared between projects?**  
A: No, each project's data is isolated by `project_key`.

**Q: How do I migrate RAG data?**  
A: Copy the `./data/chroma` directory.

