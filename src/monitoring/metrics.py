"""
Performance monitoring and metrics tracking for Womba.
Tracks timing, cache performance, and system metrics.
"""

import time
from contextlib import asynccontextmanager
from typing import Any, Callable, Dict, List, Optional

from loguru import logger


class PerformanceMetrics:
    """
    Tracks performance metrics for various operations.
    """
    
    def __init__(self):
        """Initialize metrics tracker."""
        self.timings: Dict[str, List[float]] = {}
        self.operation_counts: Dict[str, int] = {}
        self.errors: Dict[str, int] = {}
        self.start_time = time.time()
    
    def record_timing(self, operation: str, duration: float):
        """
        Record timing for an operation.
        
        Args:
            operation: Operation name
            duration: Duration in seconds
        """
        if operation not in self.timings:
            self.timings[operation] = []
            self.operation_counts[operation] = 0
        
        self.timings[operation].append(duration)
        self.operation_counts[operation] += 1
    
    def record_error(self, operation: str):
        """
        Record an error for an operation.
        
        Args:
            operation: Operation name
        """
        if operation not in self.errors:
            self.errors[operation] = 0
        self.errors[operation] += 1
    
    @asynccontextmanager
    async def track(self, operation: str):
        """
        Context manager to track operation timing.
        
        Usage:
            async with metrics.track('fetch_jira'):
                data = await jira_client.get_issue(key)
        
        Args:
            operation: Operation name
        """
        start = time.time()
        try:
            yield
        except Exception as e:
            self.record_error(operation)
            raise
        finally:
            duration = time.time() - start
            self.record_timing(operation, duration)
    
    async def track_async(self, operation: str, func: Callable) -> Any:
        """
        Track an async function call.
        
        Args:
            operation: Operation name
            func: Async function to track
            
        Returns:
            Function result
        """
        start = time.time()
        try:
            result = await func()
            return result
        except Exception as e:
            self.record_error(operation)
            raise
        finally:
            duration = time.time() - start
            self.record_timing(operation, duration)
    
    def get_stats(self, operation: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics for operations.
        
        Args:
            operation: Specific operation (None for all)
            
        Returns:
            Statistics dictionary
        """
        if operation:
            return self._get_operation_stats(operation)
        
        # Return stats for all operations
        all_stats = {}
        for op in self.timings.keys():
            all_stats[op] = self._get_operation_stats(op)
        
        return all_stats
    
    def _get_operation_stats(self, operation: str) -> Dict[str, Any]:
        """Get stats for a specific operation."""
        if operation not in self.timings or not self.timings[operation]:
            return {
                'count': 0,
                'total_time': 0,
                'avg_time': 0,
                'min_time': 0,
                'max_time': 0,
                'errors': self.errors.get(operation, 0)
            }
        
        timings = self.timings[operation]
        total_time = sum(timings)
        
        return {
            'count': len(timings),
            'total_time': round(total_time, 3),
            'avg_time': round(total_time / len(timings), 3),
            'min_time': round(min(timings), 3),
            'max_time': round(max(timings), 3),
            'errors': self.errors.get(operation, 0)
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get overall performance summary.
        
        Returns:
            Summary dictionary
        """
        total_operations = sum(self.operation_counts.values())
        total_time = time.time() - self.start_time
        total_errors = sum(self.errors.values())
        
        # Find slowest operations
        slowest_ops = []
        for op, timings in self.timings.items():
            if timings:
                avg_time = sum(timings) / len(timings)
                slowest_ops.append((op, avg_time))
        
        slowest_ops.sort(key=lambda x: x[1], reverse=True)
        
        return {
            'total_operations': total_operations,
            'total_elapsed_time': round(total_time, 3),
            'total_errors': total_errors,
            'slowest_operations': slowest_ops[:5],  # Top 5 slowest
            'operations': list(self.timings.keys())
        }
    
    def print_summary(self):
        """Print performance summary to console."""
        summary = self.get_summary()
        stats = self.get_stats()
        
        logger.info("=" * 60)
        logger.info("PERFORMANCE SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Operations: {summary['total_operations']}")
        logger.info(f"Total Elapsed Time: {summary['total_elapsed_time']}s")
        logger.info(f"Total Errors: {summary['total_errors']}")
        logger.info("")
        
        if summary['slowest_operations']:
            logger.info("Slowest Operations:")
            for op, avg_time in summary['slowest_operations']:
                logger.info(f"  - {op}: {avg_time:.3f}s avg")
        
        logger.info("")
        logger.info("Detailed Statistics:")
        for operation, op_stats in stats.items():
            logger.info(f"  {operation}:")
            logger.info(f"    Count: {op_stats['count']}")
            logger.info(f"    Avg: {op_stats['avg_time']}s")
            logger.info(f"    Min: {op_stats['min_time']}s")
            logger.info(f"    Max: {op_stats['max_time']}s")
            if op_stats['errors'] > 0:
                logger.info(f"    Errors: {op_stats['errors']}")
        
        logger.info("=" * 60)
    
    def reset(self):
        """Reset all metrics."""
        self.timings.clear()
        self.operation_counts.clear()
        self.errors.clear()
        self.start_time = time.time()


# Global metrics instance
_metrics_instance: Optional[PerformanceMetrics] = None


def get_metrics() -> PerformanceMetrics:
    """
    Get global metrics instance (singleton).
    
    Returns:
        PerformanceMetrics instance
    """
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = PerformanceMetrics()
    return _metrics_instance


def tracked(operation: str):
    """
    Decorator to track async function performance.
    
    Usage:
        @tracked('fetch_story')
        async def fetch_story(key):
            return await jira.get_issue(key)
    
    Args:
        operation: Operation name
        
    Returns:
        Decorated function
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            metrics = get_metrics()
            return await metrics.track_async(operation, lambda: func(*args, **kwargs))
        return wrapper
    return decorator

