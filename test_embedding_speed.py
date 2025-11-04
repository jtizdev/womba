"""
Quick performance test for the new embedding service.
"""
import asyncio
import time
from src.ai.embedding_service import EmbeddingService

async def main():
    service = EmbeddingService()
    
    # Test 1: Small batch (100 texts)
    print("=" * 70)
    print("TEST 1: 100 texts")
    print("=" * 70)
    texts_100 = [f'Test document {i} for performance testing' for i in range(100)]
    start = time.time()
    embeddings = await service.embed_texts(texts_100)
    duration = time.time() - start
    print(f"✓ Completed in {duration:.2f}s ({len(embeddings)/duration:.1f} embeddings/sec)")
    
    # Test 2: Medium batch (1000 texts)
    print("\n" + "=" * 70)
    print("TEST 2: 1000 texts")
    print("=" * 70)
    texts_1000 = [f'Test document {i} with more content for testing' for i in range(1000)]
    start = time.time()
    embeddings = await service.embed_texts(texts_1000)
    duration = time.time() - start
    print(f"✓ Completed in {duration:.2f}s ({len(embeddings)/duration:.1f} embeddings/sec)")
    
    # Projections
    print("\n" + "=" * 70)
    print("PERFORMANCE PROJECTIONS")
    print("=" * 70)
    speed = len(embeddings) / duration
    print(f"Current speed: {speed:.1f} embeddings/second")
    print(f"  → 10,000 texts would take: ~{10000/speed/60:.1f} minutes")
    print(f"  → 50,000 texts would take: ~{50000/speed/60:.1f} minutes")
    print(f"  → 100,000 texts would take: ~{100000/speed/60:.1f} minutes")
    
    print("\n✅ All tests PASSED!")

if __name__ == "__main__":
    asyncio.run(main())

