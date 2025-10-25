"""
Telemetry collection for sending metrics to analytics backend.
"""
import httpx
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from loguru import logger
from src.config.settings import settings


class TelemetryCollector:
    """Collects and sends telemetry data to analytics backend."""
    
    def __init__(self, analytics_url: str = None):
        self.analytics_url = analytics_url or getattr(settings, 'analytics_api_url', 'http://localhost:8000')
        self.enabled = getattr(settings, 'enable_telemetry', True)
        self.current_run_id = None
        self.run_data = {}
        self.run_start_time = None
        
        if self.enabled:
            logger.info(f"Telemetry enabled, sending to: {self.analytics_url}")
        else:
            logger.info("Telemetry disabled")
    
    async def start_run(self, story_key: str) -> str:
        """Start tracking a new execution run"""
        import uuid
        self.current_run_id = str(uuid.uuid4())
        self.run_start_time = datetime.utcnow()
        self.run_data = {
            "id": self.current_run_id,
            "story_key": story_key,
            "started_at": self.run_start_time.isoformat(),
            "status": "running",
            "num_subtasks": 0,
            "num_linked_issues": 0,
            "num_confluence_docs": 0,
            "num_test_cases_generated": 0,
            "num_test_cases_uploaded": 0
        }
        
        logger.info(f"Started telemetry tracking for run {self.current_run_id} (story: {story_key})")
        return self.current_run_id
    
    def update_context_stats(self, subtasks: int = 0, linked_issues: int = 0, confluence_docs: int = 0):
        """Update context collection statistics"""
        if self.run_data:
            self.run_data.update({
                "num_subtasks": subtasks,
                "num_linked_issues": linked_issues,
                "num_confluence_docs": confluence_docs
            })
    
    def update_test_case_stats(self, generated: int = 0, uploaded: int = 0):
        """Update test case statistics"""
        if self.run_data:
            self.run_data.update({
                "num_test_cases_generated": generated,
                "num_test_cases_uploaded": uploaded
            })
    
    async def end_run(self, status: str, error: str = None):
        """Complete and send run data"""
        if not self.enabled or not self.current_run_id:
            return
        
        completed_at = datetime.utcnow()
        duration = (completed_at - self.run_start_time).total_seconds() if self.run_start_time else 0
        
        self.run_data.update({
            "completed_at": completed_at.isoformat(),
            "duration_seconds": duration,
            "status": status,
            "error_message": error
        })
        
        logger.info(f"Ending telemetry run {self.current_run_id}: {status} ({duration:.2f}s)")
        await self._send_to_backend("/api/analytics/runs", self.run_data)
    
    async def track_operation(self, operation: str, duration: float, status: str):
        """Track individual operation metrics"""
        if not self.enabled or not self.current_run_id:
            return
        
        data = {
            "run_id": self.current_run_id,
            "operation_name": operation,
            "duration_seconds": duration,
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.debug(f"Tracking operation: {operation} ({duration:.2f}s, {status})")
        await self._send_to_backend("/api/analytics/operations", data)
    
    async def track_cost(self, provider: str, model: str, tokens_in: int, tokens_out: int, cost: float = None):
        """Track API costs"""
        if not self.enabled or not self.current_run_id:
            return
        
        # Calculate cost if not provided
        if cost is None:
            cost = self._calculate_cost(provider, model, tokens_in, tokens_out)
        
        data = {
            "run_id": self.current_run_id,
            "provider": provider,
            "model": model,
            "tokens_input": tokens_in,
            "tokens_output": tokens_out,
            "cost_usd": cost,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.debug(f"Tracking cost: {provider}/{model} - ${cost:.4f} ({tokens_in}+{tokens_out} tokens)")
        await self._send_to_backend("/api/analytics/costs", data)
    
    async def track_cache_stats(self, cache_type: str, hits: int, misses: int):
        """Track cache performance"""
        if not self.enabled or not self.current_run_id:
            return
        
        hit_rate = hits / (hits + misses) if (hits + misses) > 0 else 0
        
        data = {
            "run_id": self.current_run_id,
            "cache_type": cache_type,
            "hits": hits,
            "misses": misses,
            "hit_rate": hit_rate,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.debug(f"Tracking cache: {cache_type} - {hits} hits, {misses} misses ({hit_rate:.1%})")
        await self._send_to_backend("/api/analytics/cache", data)
    
    async def track_rag_retrieval(self, collection: str, num_results: int, duration_ms: float, avg_score: float):
        """Track RAG retrieval statistics"""
        if not self.enabled or not self.current_run_id:
            return
        
        data = {
            "run_id": self.current_run_id,
            "collection_name": collection,
            "num_results": num_results,
            "query_duration_ms": duration_ms,
            "avg_similarity_score": avg_score,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.debug(f"Tracking RAG: {collection} - {num_results} results in {duration_ms:.2f}ms")
        await self._send_to_backend("/api/analytics/rag", data)
    
    def _calculate_cost(self, provider: str, model: str, tokens_in: int, tokens_out: int) -> float:
        """Calculate cost based on provider and model pricing"""
        # OpenAI pricing (as of 2024)
        pricing = {
            "openai": {
                "gpt-4o": {"input": 0.005 / 1000, "output": 0.015 / 1000},  # $5/$15 per 1M tokens
                "gpt-4o-mini": {"input": 0.00015 / 1000, "output": 0.0006 / 1000},  # $0.15/$0.60 per 1M
                "gpt-4-turbo": {"input": 0.01 / 1000, "output": 0.03 / 1000},
                "gpt-3.5-turbo": {"input": 0.0005 / 1000, "output": 0.0015 / 1000},
                "text-embedding-3-small": {"input": 0.00002 / 1000, "output": 0},
                "text-embedding-3-large": {"input": 0.00013 / 1000, "output": 0},
            }
        }
        
        model_pricing = pricing.get(provider, {}).get(model, {"input": 0, "output": 0})
        cost = (tokens_in * model_pricing["input"]) + (tokens_out * model_pricing["output"])
        return round(cost, 6)
    
    async def _send_to_backend(self, endpoint: str, data: Dict[str, Any]):
        """Send data to analytics backend"""
        if not self.enabled:
            return
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                url = f"{self.analytics_url}{endpoint}"
                response = await client.post(url, json=data)
                
                if response.status_code >= 400:
                    logger.warning(f"Failed to send telemetry to {url}: {response.status_code}")
                else:
                    logger.debug(f"Sent telemetry to {endpoint}")
                    
        except httpx.TimeoutException:
            logger.debug(f"Telemetry request timed out for {endpoint}")
        except httpx.ConnectError:
            logger.debug(f"Could not connect to analytics backend at {self.analytics_url}")
        except Exception as e:
            logger.debug(f"Failed to send telemetry: {e}")


# Global instance
_telemetry = None


def get_telemetry() -> TelemetryCollector:
    """Get the global telemetry collector instance"""
    global _telemetry
    if _telemetry is None:
        _telemetry = TelemetryCollector()
    return _telemetry


def reset_telemetry():
    """Reset the global telemetry instance (useful for testing)"""
    global _telemetry
    _telemetry = None

