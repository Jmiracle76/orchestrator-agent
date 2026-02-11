"""Configuration setup for CLI operations."""
from __future__ import annotations
import logging
from pathlib import Path
from .handler_registry import HandlerRegistry, HandlerRegistryError


def load_handler_registry(handler_config_path: Path | None, repo_root: Path) -> tuple[HandlerRegistry | None, int]:
    """
    Load and initialize the handler registry.
    
    Args:
        handler_config_path: Optional path to handler registry YAML
        repo_root: Repository root path for default config location
        
    Returns:
        Tuple of (HandlerRegistry instance or None, exit_code)
        If successful, returns (registry, 0)
        If failed, returns (None, error_code)
    """
    if handler_config_path:
        config_path = Path(handler_config_path).resolve()
    else:
        config_path = repo_root / "tools" / "config" / "handler_registry.yaml"
    
    try:
        handler_registry = HandlerRegistry(config_path)
        logging.info("Loaded handler registry from: %s", config_path)
        return handler_registry, 0
    except HandlerRegistryError as e:
        print(f"ERROR: {e}")
        return None, 2
