"""Public package entry points for requirements automation."""

__all__ = ["main"]

# Re-export the CLI entry point for consumers importing this package.
from .cli import main
