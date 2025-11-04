#!/usr/bin/env python3
"""
View what's actually indexed in the RAG vector database.
"""

from src.ai.rag_store import RAGVectorStore

def view_collection(collection_name: str, limit: int = 20):
    """View documents in a specific collection."""
    store = RAGVectorStore()
    collection = store.get_or_create_collection(collection_name)
    
    # Get documents with metadata
    results = collection.get(limit=limit, include=['documents', 'metadatas'])
    
    print(f"\n{'='*80}")
    print(f"📂 Collection: {collection_name}")
    print(f"{'='*80}")
    print(f"Total documents: {len(results['ids'])}")
    print()
    
    if not results['ids']:
        print("❌ No documents in this collection")
        return
    
    for i, (doc_id, meta, doc) in enumerate(zip(results['ids'], results['metadatas'], results['documents']), 1):
        print(f"{i}. ID: {doc_id}")
        print(f"   Title: {meta.get('title', 'N/A')}")
        print(f"   URL: {meta.get('url', 'N/A')}")
        print(f"   Source: {meta.get('source', 'N/A')}")
        print(f"   Has JSON examples: {meta.get('has_json_examples', False)}")
        print(f"   Content length: {len(doc)} chars")
        print(f"   Preview: {doc[:150]}...")
        print()

def search_collection(collection_name: str, query: str, top_k: int = 5):
    """Search for documents similar to a query."""
    store = RAGVectorStore()
    
    print(f"\n{'='*80}")
    print(f"🔍 Searching '{collection_name}' for: {query}")
    print(f"{'='*80}")
    
    import asyncio
    results = asyncio.run(store.retrieve_similar(collection_name, query, top_k=top_k))
    
    if not results:
        print("❌ No results found")
        return
    
    for i, result in enumerate(results, 1):
        print(f"\n{i}. Match (distance: {result.get('distance', 'N/A'):.3f})")
        print(f"   ID: {result.get('id', 'N/A')}")
        meta = result.get('metadata', {})
        print(f"   Title: {meta.get('title', 'N/A')}")
        print(f"   URL: {meta.get('url', 'N/A')}")
        doc = result.get('document', '')
        print(f"   Preview: {doc[:200]}...")

if __name__ == "__main__":
    import sys
    
    store = RAGVectorStore()
    
    print("\n" + "="*80)
    print("📊 RAG Vector Database Viewer")
    print("="*80)
    
    # Get all stats
    stats = store.get_all_stats()
    print(f"\n📁 Storage Path: {stats['storage_path']}")
    print(f"📈 Total Documents: {stats['total_documents']}")
    print("\nCollections:")
    for name in ['test_plans', 'confluence_docs', 'jira_stories', 'existing_tests', 'external_docs']:
        count = stats.get(name, {}).get('count', 0)
        print(f"  ✓ {name}: {count} documents")
    
    # If argument provided, view that collection
    if len(sys.argv) > 1:
        collection = sys.argv[1]
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        
        if collection == "search":
            # Search mode: python view_indexed_docs.py search "query text"
            query = sys.argv[2] if len(sys.argv) > 2 else "policy resolution"
            coll = sys.argv[3] if len(sys.argv) > 3 else "external_docs"
            search_collection(coll, query, top_k=5)
        else:
            view_collection(collection, limit)
    else:
        # Default: show external docs
        print("\n💡 Usage:")
        print("  python view_indexed_docs.py [collection] [limit]")
        print("  python view_indexed_docs.py search \"query\" [collection]")
        print("\nCollections: external_docs, jira_stories, confluence_docs, existing_tests, test_plans")
        print("\nShowing external_docs by default...\n")
        view_collection("external_docs", limit=10)

