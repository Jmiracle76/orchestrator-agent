#!/usr/bin/env python3
"""
Test that runner_v2.py (WorkflowRunner) is the sole workflow engine.

This test verifies that:
1. runner_v2.py exists and can be imported
2. The legacy runner.py has been removed
3. cli.py uses only WorkflowRunner from runner_v2.py
"""
import sys
from pathlib import Path

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

def test_runner_v2_exists():
    """Test that runner_v2.py exists and WorkflowRunner can be imported."""
    print("Test 1: Verify runner_v2.py exists and WorkflowRunner can be imported")
    print("-" * 70)
    
    try:
        from requirements_automation.runner_v2 import WorkflowRunner
        print("  ✓ WorkflowRunner successfully imported from runner_v2")
        return True
    except ImportError as e:
        print(f"  ✗ Failed to import WorkflowRunner: {e}")
        return False

def test_legacy_runner_removed():
    """Test that legacy runner.py has been removed."""
    print("\nTest 2: Verify legacy runner.py has been removed")
    print("-" * 70)
    
    legacy_runner_path = repo_root / "tools" / "requirements_automation" / "runner.py"
    
    if legacy_runner_path.exists():
        print(f"  ✗ Legacy runner.py still exists at {legacy_runner_path}")
        return False
    else:
        print(f"  ✓ Legacy runner.py has been removed")
        return True

def test_cli_uses_workflow_runner():
    """Test that cli.py uses only WorkflowRunner and not legacy runner functions."""
    print("\nTest 3: Verify cli.py uses only WorkflowRunner")
    print("-" * 70)
    
    cli_path = repo_root / "tools" / "requirements_automation" / "cli.py"
    cli_content = cli_path.read_text()
    
    # Check that WorkflowRunner is imported
    if "from .runner_v2 import WorkflowRunner" not in cli_content:
        print("  ✗ cli.py does not import WorkflowRunner from runner_v2")
        return False
    print("  ✓ cli.py imports WorkflowRunner from runner_v2")
    
    # Check that legacy runner is NOT imported
    if "from .runner import" in cli_content:
        print("  ✗ cli.py still imports from legacy runner")
        return False
    print("  ✓ cli.py does not import from legacy runner")
    
    # Check that WorkflowRunner is instantiated
    if "runner = WorkflowRunner(" not in cli_content:
        print("  ✗ cli.py does not instantiate WorkflowRunner")
        return False
    print("  ✓ cli.py instantiates WorkflowRunner")
    
    # Check that runner methods are called
    has_run_once = "runner.run_once(" in cli_content
    has_run_until_blocked = "runner.run_until_blocked(" in cli_content
    
    if not (has_run_once and has_run_until_blocked):
        print("  ✗ cli.py does not call expected WorkflowRunner methods")
        return False
    print("  ✓ cli.py calls WorkflowRunner.run_once() and run_until_blocked()")
    
    return True

def test_no_legacy_imports_in_codebase():
    """Test that no active code imports from legacy runner.py."""
    print("\nTest 4: Verify no active code imports from legacy runner")
    print("-" * 70)
    
    # Check all Python files in tools/requirements_automation
    tools_dir = repo_root / "tools" / "requirements_automation"
    legacy_imports_found = []
    
    for py_file in tools_dir.rglob("*.py"):
        # Skip __pycache__ and other generated files
        if "__pycache__" in str(py_file):
            continue
            
        content = py_file.read_text()
        if "from .runner import" in content or "from requirements_automation.runner import" in content:
            legacy_imports_found.append(py_file.name)
    
    if legacy_imports_found:
        print(f"  ✗ Found legacy runner imports in: {', '.join(legacy_imports_found)}")
        return False
    
    print("  ✓ No legacy runner imports found in active code")
    return True

def main():
    """Run all tests."""
    print("=" * 70)
    print("Test Suite: runner_v2.py as Sole Workflow Engine")
    print("=" * 70)
    print()
    
    results = []
    
    results.append(("runner_v2 exists", test_runner_v2_exists()))
    results.append(("legacy runner removed", test_legacy_runner_removed()))
    results.append(("cli uses WorkflowRunner", test_cli_uses_workflow_runner()))
    results.append(("no legacy imports", test_no_legacy_imports_in_codebase()))
    
    print("\n" + "=" * 70)
    print("Test Results")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print("-" * 70)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 70)
    
    if passed == total:
        print("\n✓ All tests passed! runner_v2.py is the sole workflow engine.")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
