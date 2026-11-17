"""Query Optimization - Query analysis and optimization utilities."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Any, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class OptimizationHint(str, Enum):
    USE_INDEX = "USE_INDEX"
    AVOID_SEQUENTIAL_SCAN = "AVOID_SEQUENTIAL_SCAN"
    USE_HASH_JOIN = "USE_HASH_JOIN"
    USE_MERGE_JOIN = "USE_MERGE_JOIN"
    LIMIT_RESULT = "LIMIT_RESULT"
    PARTITION_PRUNING = "PARTITION_PRUNING"
    MATERIALIZE = "MATERIALIZE"
    PUSH_DOWN_PREDICATE = "PUSH_DOWN_PREDICATE"


@dataclass
class QueryPlan:
    """Query execution plan."""
    query_hash: str
    estimated_cost: float
    estimated_rows: int
    operations: List[Dict]
    indexes_used: List[str]
    tables_scanned: List[str]
    estimated_time_ms: float
    warnings: List[str] = field(default_factory=list)


@dataclass
class OptimizationResult:
    """Result of query optimization."""
    original_query: str
    optimized_query: str
    hints_applied: List[OptimizationHint]
    estimated_improvement_pct: float
    plan_before: QueryPlan
    plan_after: QueryPlan
    confidence: float


class OptimizationStrategy(str, Enum):
    RULE_BASED = "RULE_BASED"
    COST_BASED = "COST_BASED"
    HEURISTIC = "HEURISTIC"
    ML_ASSISTED = "ML_ASSISTED"
    HYBRID = "HYBRID"


@dataclass
class OptimizationConfig:
    """Configuration for query optimization."""
    max_execution_time_ms: int = 30000
    max_rows: int = 100000
    enable_parallel: bool = True
    max_parallelism: int = 4
    use_partition_pruning: bool = True
    enable_predicate_pushdown: bool = True
    enable_index_hints: bool = True
    cost_model: str = "POSTGRESQL"
    stats_update_threshold: float = 0.1


class QueryOptimizer:
    """Query optimizer for analytical workloads."""
    
    def __init__(self, db_connection=None):
        self.db = db_connection
        self._rule_cache: Dict[str, List[OptimizationHint]] = {}
    
    def analyze_query(self, query: str) -> Dict:
        """Analyze query structure and identify optimization opportunities."""
        # Simplified analysis
        issues = []
        hints = []
        
        query_lower = query.lower()
        
        # Check for SELECT *
        if "select *" in query_lower:
            issues.append("SELECT * retrieves all columns")
            hints.append(OptimizationHint.LIMIT_RESULT)
        
        # Check for missing WHERE clause on large tables
        if "where" not in query_lower and ("join" in query_lower or "from" in query_lower):
            issues.append("Query may scan entire table")
            hints.append(OptimizationHint.USE_INDEX)
        
        # Check for OR conditions
        if " or " in query_lower:
            issues.append("OR conditions may prevent index usage")
            hints.append(OptimizationHint.AVOID_SEQUENTIAL_SCAN)
        
        # Check for leading wildcards
        if "like '%" in query_lower:
            issues.append("Leading wildcard prevents index usage")
            hints.append(OptimizationHint.AVOID_SEQUENTIAL_SCAN)
        
        # Check for functions on indexed columns
        import re
        if re.search(r'\w+\([^)]*\)\s*[=<>]', query):
            issues.append("Functions on columns prevent index usage")
            hints.append(OptimizationHint.AVOID_SEQUENTIAL_SCAN)
        
        return {
            "query": query,
            "issues": issues,
            "recommended_hints": hints,
            "complexity": self._estimate_complexity(query)
        }
    
    def _estimate_complexity(self, query: str) -> str:
        """Estimate query complexity."""
        joins = query.lower().count("join")
        subqueries = query.lower().count("select") - 1
        if joins > 3 or subqueries > 2:
            return "HIGH"
        elif joins > 1 or subqueries > 0:
            return "MEDIUM"
        return "LOW"
    
    def optimize(self, query: str, context: Dict = None) -> OptimizationResult:
        """Optimize a query."""
        analysis = self.analyze_query(query)
        
        # Apply optimizations (simplified)
        optimized = query
        applied_hints = []
        
        # Add LIMIT if missing and not aggregate
        if "limit" not in query.lower() and "count(" not in query.lower():
            if not optimized.rstrip().endswith(";"):
                optimized += " LIMIT 1000"
            else:
                optimized = optimized[:-1] + " LIMIT 1000;"
            applied_hints.append(OptimizationHint.LIMIT_RESULT)
        
        # Suggest indexes for WHERE columns
        # (In practice, would analyze schema and suggest CREATE INDEX)
        
        return OptimizationResult(
            original_query=query,
            optimized_query=optimized,
            hints_applied=applied_hints,
            estimated_improvement_pct=15.0,  # Estimated
            plan_before=QueryPlan(
                query_hash="",
                estimated_cost=100.0,
                estimated_rows=10000,
                operations=[],
                indexes_used=[],
                tables_scanned=[],
                estimated_time_ms=50.0
            ),
            plan_after=QueryPlan(
                query_hash="",
                estimated_cost=85.0,
                estimated_rows=1000,
                operations=[],
                indexes_used=["idx_optimized"],
                tables_scanned=[],
                estimated_time_ms=15.0
            ),
            confidence=0.7
        )
    
    def suggest_indexes(self, query: str, schema: Dict) -> List[Dict]:
        """Suggest indexes for query."""
        # Simplified index suggestion
        suggestions = []
        
        # Extract WHERE columns
        import re
        where_match = re.search(r'where\s+(.+?)(\s+order\s+by|\s+group\s+by|\s+limit|$)', query, re.IGNORECASE)
        if where_match:
            where_clause = where_match.group(1)
            # Extract column names
            columns = re.findall(r'(\w+)\s*[=<>]', where_clause)
            for col in columns:
                suggestions.append({
                    "table": "inferred",
                    "column": col,
                    "type": "BTREE",
                    "reason": f"Column {col} used in WHERE clause"
                })
        
        return suggestions
    
    def get_statistics(self) -> Dict:
        """Get optimizer statistics."""
        return {
            "queries_analyzed": len(self._rule_cache),
            "cache_size": len(self._rule_cache)
        }


class IndexAdvisor:
    """Advises on index creation based on query patterns."""
    
    def __init__(self):
        self._query_patterns: List[Dict] = []
    
    def record_query(self, query: str, execution_time_ms: float, rows_returned: int):
        """Record query for analysis."""
        self._query_patterns.append({
            "query": query,
            "execution_time_ms": execution_time_ms,
            "rows_returned": rows_returned,
            "timestamp": datetime.utcnow()
        })
        
        # Keep last 10000 queries
        if len(self._query_patterns) > 10000:
            self._query_patterns = self._query_patterns[-10000:]
    
    def recommend_indexes(self, min_frequency: int = 5) -> List[Dict]:
        """Recommend indexes based on query patterns."""
        # Analyze patterns and recommend
        recommendations = []
        
        # Group by table and columns
        # Simplified implementation
        return recommendations
    
    def get_workload_stats(self) -> Dict:
        """Get workload statistics."""
        if not self._query_patterns:
            return {}
        
        total = len(self._query_patterns)
        avg_time = sum(q["execution_time_ms"] for q in self._query_patterns) / total
        slow_queries = [q for q in self._query_patterns if q["execution_time_ms"] > avg_time * 3]
        
        return {
            "total_queries": total,
            "avg_execution_time_ms": avg_time,
            "slow_query_count": len(slow_queries),
            "slow_query_pct": len(slow_queries) / total * 100
        }


class ConnectionPoolOptimizer:
    """Optimizes database connection pool settings."""
    
    def __init__(self, pool_size: int = 10, max_overflow: int = 20):
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self._usage_stats: List[Dict] = []
    
    def record_usage(self, active: int, idle: int, wait_time_ms: float):
        """Record pool usage statistics."""
        self._usage_stats.append({
            "timestamp": datetime.utcnow(),
            "active": active,
            "idle": idle,
            "wait_time_ms": wait_time_ms,
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
        })
        
        # Keep last 10000 records
        if len(self._usage_stats) > 10000:
            self._usage_stats = self._usage_stats[-10000:]
    
    def get_optimal_pool_size(self) -> Dict[str, int]:
        """Calculate optimal pool size based on usage patterns."""
        if not self._usage_stats:
            return {"pool_size": self.pool_size, "max_overflow": self.max_overflow}
        
        avg_active = sum(s["active"] for s in self._usage_stats) / len(self._usage_stats)
        max_active = max(s["active"] for s in self._usage_stats)
        avg_wait = sum(s["wait_time_ms"] for s in self._usage_stats) / len(self._usage_stats)
        
        # Calculate recommended pool size
        recommended_pool = int(max_active * 1.2)
        recommended_overflow = int(max(0, max_active - recommended_pool) * 1.5)
        
        return {
            "pool_size": max(self.pool_size, recommended_pool),
            "max_overflow": max(self.max_overflow, recommended_overflow),
            "avg_active": int(avg_active),
            "max_active": max_active,
            "avg_wait_ms": avg_wait,
        }
    
    def get_stats(self) -> Dict:
        """Get pool optimization statistics."""
        if not self._usage_stats:
            return {}
        
        total = len(self._usage_stats)
        avg_wait = sum(s["wait_time_ms"] for s in self._usage_stats) / total
        max_wait = max(s["wait_time_ms"] for s in self._usage_stats)
        peak_active = max(s["active"] for s in self._usage_stats)
        
        return {
            "total_samples": total,
            "avg_wait_ms": avg_wait,
            "max_wait_ms": max_wait,
            "peak_active": peak_active,
            "current_pool_size": self.pool_size,
            "current_max_overflow": self.max_overflow,
        }


class CacheOptimizer:
    """Optimizes cache configuration and usage."""
    
    def __init__(self, cache_manager=None):
        self.cache_manager = cache_manager
        self._hit_rates: List[Dict] = []
    
    def record_hit_rate(self, cache_name: str, hit_rate: float, size_mb: float, evictions: int):
        """Record cache hit rate statistics."""
        self._hit_rates.append({
            "timestamp": datetime.utcnow(),
            "cache_name": cache_name,
            "hit_rate": hit_rate,
            "size_mb": size_mb,
            "evictions": evictions,
        })
        
        # Keep last 10000 records
        if len(self._hit_rates) > 10000:
            self._hit_rates = self._hit_rates[-10000:]
    
    def get_optimal_cache_size(self, cache_name: str) -> Dict:
        """Calculate optimal cache size based on hit rate patterns."""
        cache_stats = [s for s in self._hit_rates if s["cache_name"] == cache_name]
        if not cache_stats:
            return {"recommended_size_mb": 512, "target_hit_rate": 0.85}
        
        avg_hit_rate = sum(s["hit_rate"] for s in cache_stats) / len(cache_stats)
        avg_size = sum(s["size_mb"] for s in cache_stats) / len(cache_stats)
        avg_evictions = sum(s["evictions"] for s in cache_stats) / len(cache_stats)
        
        # Recommend larger cache if hit rate is low
        if avg_hit_rate < 0.7:
            recommended_size = int(avg_size * 1.5)
        elif avg_hit_rate < 0.85:
            recommended_size = int(avg_size * 1.2)
        else:
            recommended_size = int(avg_size)
        
        return {
            "recommended_size_mb": max(64, recommended_size),
            "target_hit_rate": 0.9,
            "current_avg_hit_rate": avg_hit_rate,
            "current_avg_size_mb": avg_size,
            "avg_evictions": avg_evictions,
        }
    
    def get_recommendations(self) -> List[Dict]:
        """Get cache optimization recommendations."""
        recommendations = []
        
        if not self._hit_rates:
            return [{"cache": "all", "action": "monitor", "reason": "No data yet"}]
        
        # Group by cache name
        from collections import defaultdict
        by_cache = defaultdict(list)
        for s in self._hit_rates:
            by_cache[s["cache_name"]].append(s)
        
        for cache_name, stats in by_cache.items():
            avg_hit = sum(s["hit_rate"] for s in stats) / len(stats)
            if avg_hit < 0.7:
                recommendations.append({
                    "cache": cache_name,
                    "action": "increase_size",
                    "reason": f"Low hit rate: {avg_hit:.1%}",
                    "priority": "high"
                })
            elif avg_hit < 0.85:
                recommendations.append({
                    "cache": cache_name,
                    "action": "tune_ttl",
                    "reason": f"Moderate hit rate: {avg_hit:.1%}",
                    "priority": "medium"
                })
        
        return recommendations
    
    def get_stats(self) -> Dict:
        """Get cache optimization statistics."""
        if not self._hit_rates:
            return {}
        
        total = len(self._hit_rates)
        avg_hit_rate = sum(s["hit_rate"] for s in self._hit_rates) / total
        total_evictions = sum(s["evictions"] for s in self._hit_rates)
        
        return {
            "total_samples": total,
            "avg_hit_rate": avg_hit_rate,
            "total_evictions": total_evictions,
            "caches_monitored": len(set(s["cache_name"] for s in self._hit_rates)),
        }


class OptimizationEngine:
    """Optimization engine for performance tuning."""
    
    def __init__(self, config: OptimizationConfig = None):
        self.config = config or OptimizationConfig()
        self.query_optimizer = QueryOptimizer()
        self.pool_optimizer = ConnectionPoolOptimizer()
        self.cache_optimizer = CacheOptimizer()
    
    def optimize_system(self, workload_profile: Dict = None) -> Dict:
        """Run full system optimization."""
        results = {
            "query_optimization": self.query_optimizer.optimize("SELECT * FROM test"),
            "pool_optimization": self.pool_optimizer.get_optimal_pool_size(),
            "cache_optimization": self.cache_optimizer.get_recommendations(),
        }
        return results
    
    def get_performance_report(self) -> Dict:
        """Get comprehensive performance report."""
        return {
            "query_optimizer": self.query_optimizer.get_statistics(),
            "pool_optimizer": self.pool_optimizer.get_stats(),
            "cache_optimizer": self.cache_optimizer.get_stats(),
        }


def create_optimization_engine(config: OptimizationConfig = None) -> OptimizationEngine:
    return OptimizationEngine(config)


def create_optimization_config(**kwargs) -> OptimizationConfig:
    return OptimizationConfig(**kwargs)


def create_query_optimizer(db_connection=None) -> QueryOptimizer:
    return QueryOptimizer(db_connection)



def create_index_advisor() -> IndexAdvisor:
    return IndexAdvisor()