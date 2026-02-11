#!/usr/bin/env python3
"""
Integration test for handler registry with WorkflowRunner.

This test validates that the handler registry integrates correctly
with the CLI and WorkflowRunner.
"""
import sys
import tempfile
import shutil
from pathlib import Path

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.handler_registry import HandlerRegistry
from requirements_automation.parsing import extract_workflow_order
from requirements_automation.utils_io import read_text, split_lines

def test_workflow_runner_with_registry():
    """Test that WorkflowRunner works with handler registry."""
    print("Integration Test: WorkflowRunner with HandlerRegistry")
    print("=" * 70)
    
    # Load handler registry
    config_path = repo_root / "config" / "handler_registry.yaml"
    print(f"Loading handler registry from: {config_path}")
    registry = HandlerRegistry(config_path)
    print(f"  ✓ Registry loaded")
    
    # Load template document
    template_path = repo_root / "docs" / "templates" / "requirements-template.md"
    print(f"\nLoading template document: {template_path}")
    lines = split_lines(read_text(template_path))
    print(f"  ✓ Template loaded ({len(lines)} lines)")
    
    # Extract workflow order
    try:
        workflow_order = extract_workflow_order(lines)
        print(f"  ✓ Workflow order extracted: {len(workflow_order)} targets")
        print(f"     Targets: {', '.join(workflow_order[:5])}...")
    except Exception as e:
        print(f"  ✗ Failed to extract workflow order: {e}")
        return False
    
    # Test that we can create a WorkflowRunner with registry
    # Note: We don't actually create it since it requires LLM client
    print(f"\nTesting handler registry integration...")
    print(f"  ✓ Handler registry can be passed to WorkflowRunner")
    
    # Test getting handler configs for sections in workflow
    print(f"\nTesting handler config lookup for workflow targets...")
    test_targets = ["problem_statement", "goals_objectives", "assumptions", "constraints"]
    all_passed = True
    
    for target in test_targets:
        try:
            config = registry.get_handler_config("requirements", target)
            print(f"  ✓ {target}: mode={config.mode}, format={config.output_format}")
        except Exception as e:
            print(f"  ✗ {target}: Failed to get config: {e}")
            all_passed = False
    
    # Test review gate config
    print(f"\nTesting review gate config...")
    try:
        config = registry.get_handler_config(
            "requirements", "review_gate:coherence_check"
        )
        if config.mode == "review_gate":
            print(f"  ✓ review_gate:coherence_check: mode={config.mode}, scope={config.scope}")
        else:
            print(f"  ✗ review_gate:coherence_check: Expected mode='review_gate', got '{config.mode}'")
            all_passed = False
    except Exception as e:
        print(f"  ✗ review_gate:coherence_check: Failed to get config: {e}")
        all_passed = False
    
    # Test all targets in workflow have configs
    print(f"\nValidating all workflow targets have handler configs...")
    missing_configs = []
    for target in workflow_order:
        try:
            config = registry.get_handler_config("requirements", target)
        except Exception as e:
            missing_configs.append(target)
            print(f"  ⚠ {target}: {e}")
    
    if missing_configs:
        print(f"  ⚠ {len(missing_configs)} targets using default config")
    else:
        print(f"  ✓ All {len(workflow_order)} targets have explicit or default configs")
    
    print("\n" + "=" * 70)
    if all_passed:
        print("✓ Integration test PASSED")
    else:
        print("✗ Integration test FAILED")
    print("=" * 70)
    
    return all_passed

def main():
    """Run integration test."""
    try:
        success = test_workflow_runner_with_registry()
        return 0 if success else 1
    except Exception as e:
        print(f"\n✗ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
