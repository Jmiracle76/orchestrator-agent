"""LLM client - backward compatibility wrapper.

This module maintains backward compatibility by re-exporting classes
and functions from the refactored modules.
"""
from .llm_client import LLMClient
from .llm_parsing import extract_json_object

__all__ = ["LLMClient", "extract_json_object"]

