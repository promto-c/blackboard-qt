"""Runtime-checked descriptor for type-enforced attributes.

Example
-------
Basic usage validates assignments against annotations and populates defaults:

>>> class Person:
...     age: int = TypedProp()
...     nickname: str | None = TypedProp(default=None)
...
>>> alice = Person()
>>> alice.age = 32
>>> alice.age
32
>>> alice.nickname is None
True
>>> alice.age = "old"
Traceback (most recent call last):
...
TypeError: age must be int, got str

`validator` allows additional custom checks to run after the type check:

>>> class Positive:
...     value: int = TypedProp(validator=lambda v: v >= 0)
...
>>> pos = Positive()
>>> pos.value = 10
>>> pos.value
10
>>> pos.value = -1
Traceback (most recent call last):
...
ValueError: invalid value for value: -1
"""

import sys
import types
from typing import Any, Callable, Generic, Optional, TypeVar, Union, get_args, get_origin, get_type_hints

T = TypeVar("T")


def _make_checker(annotation: Any) -> Callable[[Any], bool]:
    """Return a predicate that enforces runtime compatibility with an annotation."""
    origin = get_origin(annotation)

    # Plain annotations (no origin)
    if origin is None:
        if annotation is Any:
            return lambda v: True
        if isinstance(annotation, type):
            return lambda v: isinstance(v, annotation)
        # Unknown typing form -> accept (safe fallback)
        return lambda v: True

    # Union / Optional (typing.Union or types.UnionType for PEP 604)
    if origin in (Union, types.UnionType):
        args = get_args(annotation)
        allow_none = any(a is type(None) for a in args)  # noqa: E721

        # Build predicates for non-None members
        preds = [_make_checker(a) for a in args if a is not type(None)]  # noqa: E721
        if not preds:
            return lambda v: v is None
        return lambda v: (v is None and allow_none) or any(p(v) for p in preds)

    # Loose container: just check the outer type
    if isinstance(origin, type):
        return lambda v: isinstance(v, origin)

    # Unknown origin -> accept
    return lambda v: True


class TypedProp(Generic[T]):
    """Descriptor that validates assignments against type hints (and optional validator)."""

    def __init__(
        self,
        type_: Any | None = None,
        default: Optional[T] = None,
        *,
        name: str | None = None,
        validator: Optional[Callable[[T], bool]] = None,
    ):
        self._type = type_
        self._default = default
        self._name_hint = name
        self._validator = validator

        self._type_resolved: Any = None
        self._check: Callable[[Any], bool] = lambda v: True
        self._on_set_hook: Optional[Callable[[object, T], T]] = None

    def on_set(self, func: Callable[[object, T], T]):
        """Decorator to register a pre-set hook."""
        self._on_set_hook = func
        return self

    def __set_name__(self, owner, public_name: str):
        self._public_name = public_name
        self._private_name = f"_{public_name}"

        # Resolve typing from owner annotations if not explicitly given
        ann = self._type if self._type is not None else getattr(owner, "__annotations__", {}).get(public_name, None)

        # Resolve forward refs / postponed annotations
        mod_globals = sys.modules[owner.__module__].__dict__
        try:
            hints = get_type_hints(owner, globalns=mod_globals, localns=owner.__dict__)
            resolved = hints.get(public_name, ann)
        except Exception:
            resolved = ann

        self._type_resolved = resolved
        self._check = _make_checker(self._type_resolved)

    def __get__(self, obj, owner=None) -> T:
        if obj is None:
            return self
        if not hasattr(obj, self._private_name):
            setattr(obj, self._private_name, self._default)
        return getattr(obj, self._private_name)

    def __set__(self, obj, value: T) -> None:
        if self._on_set_hook is not None:
            value = self._on_set_hook(obj, value)

        if not self._check(value):
            want = getattr(self._type_resolved, "__name__", str(self._type_resolved))
            got = type(value).__name__
            raise TypeError(f"{self._public_name} must be {want}, got {got}")

        if self._validator and not self._validator(value):
            raise ValueError(f"invalid value for {self._public_name}: {value}")

        setattr(obj, self._private_name, value)


__all__ = ["TypedProp"]
