"""Public package entry points for requirements automation."""

__all__ = ["main"]

# Lazy import to avoid double-import warning when running with python -m
def main(*args, **kwargs):
    from .cli import main as _main
    return _main(*args, **kwargs)
