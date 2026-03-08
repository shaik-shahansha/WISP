"""
WISP capability decorator and registry.

Capabilities are the actions a WispDevice can perform.
They are discovered automatically from decorated methods and exposed to the AI.
"""

from __future__ import annotations

import functools
import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class CapabilitySpec:
    """Metadata about a single device capability."""

    name: str
    description: str
    fn: Callable
    parameters: List[CapabilityParam] = field(default_factory=list)

    def to_ai_schema(self) -> Dict[str, Any]:
        """Return a JSON-serialisable description for the AI system prompt."""
        schema: Dict[str, Any] = {"name": self.name, "description": self.description}
        if self.parameters:
            schema["parameters"] = [p.to_dict() for p in self.parameters]
        return schema

    def __call__(self, device_instance: Any, **kwargs: Any) -> Any:
        return self.fn(device_instance, **kwargs)


@dataclass
class CapabilityParam:
    """A single parameter of a capability."""

    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None

    def to_dict(self) -> Dict[str, Any]:
        d = {"name": self.name, "type": self.type, "description": self.description, "required": self.required}
        if self.default is not None:
            d["default"] = self.default
        return d


class CapabilityRegistry:
    """Holds all capabilities registered on a WispDevice class."""

    def __init__(self) -> None:
        self._caps: Dict[str, CapabilitySpec] = {}

    def register(self, spec: CapabilitySpec) -> None:
        self._caps[spec.name] = spec

    def get(self, name: str) -> Optional[CapabilitySpec]:
        return self._caps.get(name)

    def all(self) -> List[CapabilitySpec]:
        return list(self._caps.values())

    def names(self) -> List[str]:
        return list(self._caps.keys())

    def to_ai_schema(self) -> List[Dict[str, Any]]:
        return [c.to_ai_schema() for c in self._caps.values()]


def _infer_params(fn: Callable) -> List[CapabilityParam]:
    """Infer capability parameters from function signature and type hints."""
    sig = inspect.signature(fn)
    hints = fn.__annotations__
    params: List[CapabilityParam] = []
    for pname, param in sig.parameters.items():
        if pname == "self":
            continue
        ptype = hints.get(pname, Any)
        type_str = getattr(ptype, "__name__", str(ptype)).lower()
        required = param.default is inspect.Parameter.empty
        default = None if required else param.default
        params.append(
            CapabilityParam(
                name=pname,
                type=type_str,
                description=f"The {pname.replace('_', ' ')}",
                required=required,
                default=default,
            )
        )
    return params


def capability(
    fn: Optional[Callable] = None,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> Callable:
    """
    Decorator that registers a method as a WISP device capability.

    Usage — bare decorator::

        @capability
        def read_temperature(self) -> dict:
            \"\"\"Read the current temperature from the sensor.\"\"\"
            ...

    Usage — with arguments::

        @capability(name="toggle_relay", description="Turn a GPIO relay on or off")
        def set_relay(self, relay_name: str, state: str) -> dict:
            ...

    The docstring is used as the capability description when no ``description``
    is provided explicitly.
    """

    def decorator(func: Callable) -> Callable:
        cap_name = name or func.__name__
        cap_desc = description or (inspect.getdoc(func) or func.__name__.replace("_", " "))
        params = _infer_params(func)

        spec = CapabilitySpec(
            name=cap_name,
            description=cap_desc,
            fn=func,
            parameters=params,
        )

        # Attach spec to the function so WispDeviceMeta can find it
        func._wisp_capability = spec  # type: ignore[attr-defined]

        @functools.wraps(func)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            return func(self, *args, **kwargs)

        wrapper._wisp_capability = spec  # type: ignore[attr-defined]
        return wrapper

    # Allow both @capability and @capability(...)
    if fn is not None:
        return decorator(fn)
    return decorator
