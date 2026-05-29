# -*- coding: utf-8 -*-
import time


class TTLCache(object):
    """TTL cache decorator (drop-new when full) for best minimal overhead.

    Supports both:
        @TTLCache
        @TTLCache(ttl_seconds=..., maxsize=...)
    And works on instance methods via descriptor binding (__get__).
    """

    def __init__(self, fn=None, ttl_seconds=2.0, maxsize=1024):
        self._ttl = float(ttl_seconds)
        self._maxsize = int(maxsize)

        self._fn = None
        self._wrapper = None

        if fn is not None:
            # Case: @TTLCache
            self._wrap(fn)

    def __call__(self, *args, **kwargs):
        # Case: @TTLCache(...)
        if self._fn is None and len(args) == 1 and callable(args[0]) and not kwargs:
            return self._wrap(args[0])

        # Normal function call
        return self._wrapper(*args, **kwargs)

    def __get__(self, instance, owner):
        # Accessed on class: Database.fetch_user
        if instance is None:
            return self

        # Return a bound callable that injects instance as first arg
        def bound(*args, **kwargs):
            return self._wrapper(instance, *args, **kwargs)

        # Keep cache_clear available from instance access too
        bound.cache_clear = self._wrapper.cache_clear
        return bound

    def _wrap(self, fn):
        self._fn = fn
        data = {}  # key -> (expires_at, value)

        def make_key(args, kwargs):
            return args if not kwargs else (args, tuple(sorted(kwargs.items())))

        def wrapper(*args, **kwargs):
            now = time.time()
            key = make_key(args, kwargs)

            item = data.get(key)
            if item is not None:
                expires_at, value = item
                if expires_at > now:
                    return value
                data.pop(key, None)

            value = fn(*args, **kwargs)

            # Drop-new policy: if full, skip caching
            if len(data) < self._maxsize:
                data[key] = (now + self._ttl, value)

            return value

        wrapper.cache_clear = data.clear
        self._wrapper = wrapper
        return self


def example():

    class Database:

        def __init__(self):
            pass

        # Explicit TTL
        @TTLCache(ttl_seconds=2.0)
        def fetch_task(self, task_id):
            print("DB HIT: fetch_task(%s)" % task_id)
            return {"id": task_id, "name": "Task-%s" % task_id}

        # Default TTL (2.0s)
        @TTLCache
        def fetch_user(self, user_id):
            print("DB HIT: fetch_user(%s)" % user_id)
            return {"id": user_id, "name": "User-%s" % user_id}

    d = Database()
    print("=== First calls (DB hit) ===")
    print(d.fetch_task(1))
    print(d.fetch_user(10))

    print("\n=== Cached calls (no DB hit) ===")
    print(d.fetch_task(1))
    print(d.fetch_user(10))

    print("\n=== Sleep past TTL ===")
    time.sleep(2.1)
    print(d.fetch_task(1))   # DB hit again
    print(d.fetch_user(10))  # DB hit again

    print("\n=== Manual refresh ===")
    d.fetch_task.cache_clear()
    print(d.fetch_task(1))   # DB hit after clear


if __name__ == "__main__":
    example()
