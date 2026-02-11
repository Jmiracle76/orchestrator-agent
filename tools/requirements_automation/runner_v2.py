"""Workflow runner - backward compatibility wrapper.

This module maintains backward compatibility by re-exporting the WorkflowRunner
class from the refactored runner_core module.
"""
from .runner_core import WorkflowRunner

__all__ = ["WorkflowRunner"]
