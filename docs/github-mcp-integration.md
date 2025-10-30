# GitHub MCP Integration

This project now includes a light-weight helper (`src/integrations/github_mcp.py`) that turns GitHub repository content into an MCP-accessible source. The goal is to let the agent cross-reference implementation details directly from source without bloating prompts or hitting rate limits.

## Configuration

1. **Set a GitHub token**
   - Create a fine-grained PAT with `repo` read permissions.
   - Add it to the environment or `.env`:

     ```env
     GITHUB_TOKEN=ghp_your_token_here
     ```

2. **List PlainID docs (optional)**
   - If you need remote PlainID pages pulled automatically, add URLs to:

     ```env
     PLAINID_DOC_URLS="https://docs.plainid.io/component/authorization-apis/overview"
     ```

## Using the Connector

```python
from src.integrations.github_mcp import GitHubMCPConnector

connector = GitHubMCPConnector()
if connector.is_available():
    file = connector.fetch_file("plainid", "platform", "src/pdp/handler.py")
    print(file.content[:400])
```

- `fetch_file` returns decoded file contents ready for RAG or prompt assembly.
- `list_tree` can be used by MCP clients to expose repository navigation.
- `create_mcp_tool_spec` returns a JSON schema snippet you can register in MCP tool definitions.

## Recommended Workflow

1. **Index docs** – run `womba index-all` to populate Confluence, Jira, Zephyr, _and_ PlainID docs.
2. **Connect MCP** – mount the GitHub connector so the agent can pull implementation snippets automatically when RAG indicates an endpoint.
3. **Generate tests** – `womba generate STORY-KEY --upload` now includes PlainID endpoint notes plus any repository snippets MCP fetched.

This keeps prompts grounded in both documentation and real code paths, reducing hallucinations while staying inside GPT-4o token ceilings.

