from __future__ import annotations
from copy import deepcopy
from typing import Any


class UpdatableMixin:
    def copy_with(
        self,
        *,
        skip_none: bool = True,
        strict_types: bool = False,
        **kwargs: Any
    ) -> None:
        """Update attributes of the instance with the given keyword arguments."""
        for key, value in kwargs.items():
            if not hasattr(self, key):
                raise AttributeError(f"[{self.__class__.__name__}] No attribute named '{key}'")

            if skip_none and value is None:
                continue

            current_value = getattr(self, key)

            if strict_types and value is not None and current_value is not None:
                if not isinstance(value, type(current_value)):
                    raise TypeError(
                        f"[{self.__class__.__name__}] Field '{key}' must be of type "
                        f"{type(current_value).__name__}, got {type(value).__name__}"
                    )

            safe_value = deepcopy(value) if isinstance(value, (dict, list)) else value
            setattr(self, key, safe_value)
