#!/usr/bin/env python3
"""List all indexed documents in the RAG database."""

from src.ai.rag_store import RAGVectorStore

store = RAGVectorStore()
collection = store.get_or_create_collection('external_docs')

# Get all documents
results = collection.get(limit=200, include=['metadatas', 'documents'])

print('='*80)
print(f'📚 All {len(results["ids"])} Indexed PlainID Documents')
print('='*80)
print()

# Extract and display
docs_info = []
for doc_id, meta, content in zip(results['ids'], results['metadatas'], results['documents']):
    title = meta.get('title', 'Unknown')
    has_json = meta.get('has_json_examples', False)
    
    # Extract URL from content (it's in the first line)
    url = 'N/A'
    if content.startswith('Source: '):
        url = content.split('\n')[0].replace('Source: ', '')
    
    docs_info.append({
        'title': title,
        'url': url,
        'has_json': has_json,
        'content_length': len(content)
    })

# Sort by title
docs_info.sort(key=lambda x: x['title'])

# Display
for i, doc in enumerate(docs_info, 1):
    emoji = '📋' if doc['has_json'] else '📄'
    print(f"{i:3d}. {emoji} {doc['title']}")
    if doc['url'] != 'N/A':
        print(f"      URL: {doc['url']}")
    if doc['has_json']:
        print(f"      ✨ Contains JSON examples")
    print()

# Summary
print('='*80)
print('📊 Summary:')
print(f"  Total documents: {len(docs_info)}")
print(f"  With JSON examples: {sum(1 for d in docs_info if d['has_json'])}")
print(f"  General documentation: {sum(1 for d in docs_info if not d['has_json'])}")
print('='*80)

