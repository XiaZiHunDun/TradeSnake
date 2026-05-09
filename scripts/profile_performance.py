"""性能 profiling 脚本 — 量化关键路径耗时"""
import time
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def profile_robust_normalize():
    """Profile CPEngine._robust_normalize"""
    import numpy as np

    # Mock a minimal CPEngine to test normalize
    class MockEngine:
        def _robust_normalize(self, data):
            """Same implementation as CPEngine._robust_normalize"""
            import numpy as np
            arr = np.array(data, dtype=float)
            p5 = np.percentile(arr, 5)
            p95 = np.percentile(arr, 95)
            clipped = np.clip(arr, p5, p95)
            if clipped.max() > clipped.min():
                return (clipped - clipped.min()) / (clipped.max() - clipped.min()) * 100
            return np.zeros_like(arr)

    engine = MockEngine()
    data = list(np.random.uniform(0, 100, 200))

    # Warm up
    for _ in range(10):
        engine._robust_normalize(data)

    # Benchmark
    iterations = 1000
    start = time.perf_counter()
    for _ in range(iterations):
        engine._robust_normalize(data)
    elapsed = (time.perf_counter() - start) / iterations
    print(f"_robust_normalize (200 values): {elapsed * 1000:.3f}ms avg ({iterations} iterations)")


def profile_numpy_operations():
    """Profile numpy percentile vs alternative"""
    import numpy as np

    data = np.random.uniform(0, 100, 200)

    # Method 1: np.percentile (2x)
    start = time.perf_counter()
    for _ in range(500):
        p5 = np.percentile(data, 5)
        p95 = np.percentile(data, 95)
    elapsed1 = (time.perf_counter() - start) / 500

    # Method 2: np.nanpercentile
    start = time.perf_counter()
    for _ in range(500):
        p5 = np.nanpercentile(data, 5)
        p95 = np.nanpercentile(data, 95)
    elapsed2 = (time.perf_counter() - start) / 500

    print(f"np.percentile (200 values): {elapsed1 * 1000:.3f}ms avg")
    print(f"np.nanpercentile (200 values): {elapsed2 * 1000:.3f}ms avg")


def profile_stock_computation():
    """Profile stock score computation loop"""
    import numpy as np

    n_stocks = 200
    n_scores = 4  # growth, value, momentum, quality

    # Generate mock data
    scores = np.random.uniform(0, 100, (n_stocks, n_scores))
    weights = np.array([0.3, 0.3, 0.2, 0.2])
    risk_penalties = np.random.uniform(0, 20, n_stocks)

    # Method 1: Python loop
    def compute_loop(scores, weights, risk_penalties):
        results = []
        for i in range(len(scores)):
            weighted = np.dot(scores[i], weights)
            adjusted = weighted - risk_penalties[i]
            results.append(max(0, min(100, adjusted)))
        return results

    # Method 2: numpy vectorized
    def compute_vectorized(scores, weights, risk_penalties):
        weighted = np.dot(scores, weights)
        adjusted = weighted - risk_penalties
        return np.clip(adjusted, 0, 100)

    # Benchmark loop
    start = time.perf_counter()
    for _ in range(100):
        compute_loop(scores, weights, risk_penalties)
    loop_time = (time.perf_counter() - start) / 100 * 1000

    # Benchmark vectorized
    start = time.perf_counter()
    for _ in range(100):
        compute_vectorized(scores, weights, risk_penalties)
    vec_time = (time.perf_counter() - start) / 100 * 1000

    print(f"Stock computation (200 stocks, 4 scores):")
    print(f"  Python loop: {loop_time:.2f}ms avg")
    print(f"  Vectorized: {vec_time:.2f}ms avg")
    print(f"  Speedup: {loop_time / vec_time:.1f}x")


def profile_duckdb_connection():
    """Profile DuckDB connection acquisition"""
    from backend.data_manager.duckdb_store import get_duckdb_store

    store = get_duckdb_store()

    # Warm up
    try:
        store.get_stock('600519')
    except:
        pass

    # Benchmark connection
    iterations = 50
    start = time.perf_counter()
    for _ in range(iterations):
        conn = store._get_conn()
        conn.close()
    elapsed = (time.perf_counter() - start) / iterations
    print(f"DuckDB connection acquire+release: {elapsed * 1000:.2f}ms avg ({iterations} iterations)")

    # Benchmark get_stock
    start = time.perf_counter()
    for _ in range(20):
        try:
            store.get_stock('600519')
        except:
            pass
    elapsed = (time.perf_counter() - start) / 20
    print(f"DuckDB get_stock: {elapsed * 1000:.2f}ms avg (20 iterations)")


def profile_duckdb_bulk_query():
    """Profile DuckDB bulk kline query"""
    from backend.data_manager.duckdb_store import get_duckdb_store

    store = get_duckdb_store()

    # Get 50 random codes from DuckDB
    try:
        conn = store._get_conn()
        result = conn.execute("SELECT DISTINCT code FROM daily_kline LIMIT 50").fetchall()
        conn.close()
        codes = [r[0] for r in result]
    except Exception as e:
        print(f"Could not fetch codes: {e}")
        return

    # Benchmark bulk query
    iterations = 5
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        try:
            result = store.get_klines_bulk(codes, days=60)
        except Exception as e:
            print(f"get_klines_bulk error: {e}")
            return
        elapsed = time.perf_counter() - start
        times.append(elapsed)

    avg_time = sum(times) / len(times) * 1000
    print(f"DuckDB get_klines_bulk ({len(codes)} codes, 60 days): {avg_time:.1f}ms avg ({len(times)} iterations)")
    if len(times) > 1:
        print(f"  Min: {min(times)*1000:.1f}ms, Max: {max(times)*1000:.1f}ms")


def profile_duckdb_single_query():
    """Profile single stock kline query"""
    from backend.data_manager.duckdb_store import get_duckdb_store

    store = get_duckdb_store()

    # Benchmark single query
    iterations = 20
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        try:
            result = store.get_klines('600519', days=30)
        except Exception as e:
            pass
        elapsed = time.perf_counter() - start
        times.append(elapsed * 1000)

    avg_time = sum(times) / len(times)
    print(f"DuckDB get_klines (1 code, 30 days): {avg_time:.2f}ms avg ({len(times)} iterations)")


def profile_cp_engine_init():
    """Profile CPEngine initialization"""
    from backend.engine.cp_engine import CPEngine

    start = time.perf_counter()
    for _ in range(5):
        engine = CPEngine()
    elapsed = (time.perf_counter() - start) / 5
    print(f"CPEngine() init: {elapsed * 1000:.2f}ms avg (5 iterations)")


def profile_normalize_cached():
    """Profile normalize with dirty flag caching"""
    import numpy as np

    class MockEngineWithCache:
        def __init__(self):
            self._normalize_cache = None
            self._normalize_stocks_version = None

        def _robust_normalize(self, data, stocks_version=None):
            # Check if we can use cache
            if stocks_version is not None and self._normalize_stocks_version == stocks_version:
                return self._normalize_cache

            arr = np.array(data, dtype=float)
            p5 = np.percentile(arr, 5)
            p95 = np.percentile(arr, 95)
            clipped = np.clip(arr, p5, p95)
            result = (clipped - clipped.min()) / (clipped.max() - clipped.min()) * 100 if clipped.max() > clipped.min() else np.zeros_like(arr)

            # Cache result
            if stocks_version is not None:
                self._normalize_cache = result
                self._normalize_stocks_version = stocks_version
            return result

    engine = MockEngineWithCache()
    data = list(np.random.uniform(0, 100, 200))

    # First call - no cache
    start = time.perf_counter()
    for _ in range(100):
        engine._normalize_stocks_version = None  # Force no cache
        engine._robust_normalize(data, stocks_version=1)
    first_time = (time.perf_counter() - start) / 100 * 1000

    # Cached calls
    start = time.perf_counter()
    for _ in range(100):
        engine._robust_normalize(data, stocks_version=1)
    cached_time = (time.perf_counter() - start) / 100 * 1000

    print(f"Normalize (200 values):")
    print(f"  First call (no cache): {first_time:.3f}ms avg")
    print(f"  Cached call: {cached_time:.3f}ms avg")
    print(f"  Cache speedup: {first_time / cached_time:.1f}x")


if __name__ == '__main__':
    print("=" * 60)
    print("TradeSnake Performance Profiling")
    print("=" * 60)

    print("\n1. Robust Normalize Profile:")
    profile_robust_normalize()

    print("\n2. Numpy Operations:")
    profile_numpy_operations()

    print("\n3. Stock Computation Loop vs Vectorized:")
    profile_stock_computation()

    print("\n4. DuckDB Connection:")
    try:
        profile_duckdb_connection()
    except Exception as e:
        print(f"  Connection profile failed: {e}")

    print("\n4b. DuckDB Bulk Query:")
    try:
        profile_duckdb_bulk_query()
    except Exception as e:
        print(f"  Bulk query profile failed: {e}")

    print("\n4c. DuckDB Single Query:")
    try:
        profile_duckdb_single_query()
    except Exception as e:
        print(f"  Single query profile failed: {e}")

    print("\n5. CPEngine Initialization:")
    profile_cp_engine_init()

    print("\n6. Normalize with Cache:")
    profile_normalize_cached()

    print("\n" + "=" * 60)
    print("Profiling complete")
    print("=" * 60)