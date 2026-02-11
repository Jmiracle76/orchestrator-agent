"""Public package entry points for requirements automation."""

from typing import Any

__all__ = ["main"]


# Lazy import to avoid double-import warning when running with python -m
def main(*args: Any, **kwargs: Any) -> Any:
    from .cli import main as _main

    return _main(*args, **kwargs)
