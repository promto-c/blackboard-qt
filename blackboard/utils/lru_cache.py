# Type Checking Imports
# ---------------------
from typing import Callable, Optional, Any, Tuple, FrozenSet, TYPE_CHECKING
if TYPE_CHECKING:
    from numbers import Number

# Standard Library Imports
# ------------------------
from collections import OrderedDict
from functools import wraps
import pickle
import psutil


# Class Definitions
# -----------------
class LRUCache:
    """Decorator implementing a simple memory-bounded LRU cache.
    """

    # Initialization
    # --------------
    def __init__(self, max_memory: Optional[int] = None, memory_pct: 'Number' = 10.0):
        """Initialize the cache.

        Args:
            max_memory: Maximum cache size in **bytes**. If `None`, it is
                computed as `memory_pct` percent of the available RAM.
            memory_pct: Fallback percentage when `max_memory` is `None`.
        """
        self.max_memory = max_memory or int(self._get_available_memory() * float(memory_pct) / 100)
        self.cache = OrderedDict()
        self.current_memory = 0

    def __call__(self, func: Callable) -> Callable:
        """Wrap *func* with LRU caching.
        """
        @wraps(func)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            key = self._make_key(args, kwargs)

            # Fast path: hit in cache
            if key in self.cache:
                self.cache.move_to_end(key)
                return self.cache[key]

            # Miss: compute result
            result = func(*args, **kwargs)
            result_size = self._get_size(result)

            # Skip caching objects that would never fit  ------------------- #
            if result_size > self.max_memory:                              # ⬅︎ changed
                return result

            # Insert into cache
            self.cache[key] = result
            self.current_memory += result_size

            # Evict until within budget
            while self.current_memory > self.max_memory and self.cache:     # ⬅︎ changed
                self._evict()

            return result

        # Expose cache helpers on the wrapped function
        wrapped.cache = self.cache
        wrapped.get_current_memory = self._get_current_memory
        wrapped.max_memory = self.max_memory
        wrapped.clear_cache = self.clear_cache
        return wrapped

    def _make_key(self, args: Tuple[Any, ...], kwargs: dict) -> Tuple[Any, FrozenSet[Tuple[str, Any]]]:
        """Return a hashable key built from *args* and *kwargs*.
        """
        return args, frozenset(kwargs.items())

    def _evict(self) -> None:
        """Remove the least-recently-used item, if any.
        """
        if not self.cache:
            self.current_memory = 0
            return
        _, oldest_result = self.cache.popitem(last=False)
        self.current_memory = max(0, self.current_memory - self._get_size(oldest_result))

    def clear_cache(self) -> None:
        """Clear the cache and reset memory counters.
        """
        self.cache.clear()
        self.current_memory = 0

    def _get_current_memory(self) -> int:
        return self.current_memory

    @staticmethod
    def _get_available_memory() -> int:
        """Return available system RAM in bytes.
        """
        return psutil.virtual_memory().available

    @staticmethod
    def _get_size(obj: Any) -> int:
        """Rough byte size of *obj* via pickle serialisation.
        """
        return len(pickle.dumps(obj))


# Example usage
# -------------
if __name__ == "__main__":
    @LRUCache(memory_pct=50)
    def expensive_computation(x: int, y: int) -> int:
        return x + y

    # Testing the LRUCache
    print("Testing with 50% of available memory...")

    # Create a lot of calls to test memory usage
    for i in range(1000):
        expensive_computation(i, i + 1)

    # Print cache size for verification
    print("Cache size (number of items):", len(expensive_computation.cache))
    print("Current memory used by cache (bytes):", expensive_computation.get_current_memory())
    print("Max memory allowed for cache (bytes):", expensive_computation.max_memory)
