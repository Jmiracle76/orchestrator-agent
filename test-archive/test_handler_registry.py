#!/usr/bin/env python3
"""
Manual test script for HandlerRegistry functionality.

This script validates the handler registry implementation by testing:
1. Loading valid YAML configuration
2. Looking up handler configs for known sections
3. Testing default fallback for unknown sections
4. Validating error handling for malformed YAML
"""
import sys
import tempfile
from pathlib import Path

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.handler_registry import HandlerRegistry, HandlerRegistryError


def test_load_valid_config():
    """Test loading valid handler registry YAML."""
    print("Test 1: Load valid handler registry config...")
    config_path = repo_root / "config" / "handler_registry.yaml"

    try:
        registry = HandlerRegistry(config_path)
        print("  ✓ Successfully loaded handler registry")
        print(
            f"  ✓ Found doc types: {', '.join([k for k in registry.config.keys() if k != '_default'])}"
        )
        return True
    except Exception as e:
        print(f"  ✗ Failed to load registry: {e}")
        return False


def test_get_handler_config():
    """Test retrieving handler config for known sections."""
    print("\nTest 2: Get handler config for known sections...")
    config_path = repo_root / "config" / "handler_registry.yaml"
    registry = HandlerRegistry(config_path)

    test_cases = [
        ("requirements", "problem_statement", "integrate_then_questions", "prose"),
        ("requirements", "goals_objectives", "integrate_then_questions", "bullets"),
        ("requirements", "assumptions", "integrate_then_questions", "bullets"),
        ("requirements", "constraints", "integrate_then_questions", "subsections"),
        ("requirements", "review_gate:coherence_check", "review_gate", "prose"),
    ]

    all_passed = True
    for doc_type, section_id, expected_mode, expected_format in test_cases:
        try:
            config = registry.get_handler_config(doc_type, section_id)
            if config.mode != expected_mode:
                print(f"  ✗ {section_id}: Expected mode '{expected_mode}', got '{config.mode}'")
                all_passed = False
            elif config.output_format != expected_format:
                print(
                    f"  ✗ {section_id}: Expected format '{expected_format}', got '{config.output_format}'"
                )
                all_passed = False
            else:
                print(f"  ✓ {section_id}: mode={config.mode}, format={config.output_format}")
        except Exception as e:
            print(f"  ✗ {section_id}: Failed to get config: {e}")
            all_passed = False

    return all_passed


def test_assumptions_dedupe():
    """Test that assumptions section has dedupe=True."""
    print("\nTest 3: Verify assumptions section has dedupe=True...")
    config_path = repo_root / "config" / "handler_registry.yaml"
    registry = HandlerRegistry(config_path)

    try:
        config = registry.get_handler_config("requirements", "assumptions")
        if config.dedupe:
            print(f"  ✓ assumptions: dedupe=True")
            return True
        else:
            print(f"  ✗ assumptions: dedupe={config.dedupe} (expected True)")
            return False
    except Exception as e:
        print(f"  ✗ Failed to get assumptions config: {e}")
        return False


def test_constraints_preserve_headers():
    """Test that constraints section has preserve_headers."""
    print("\nTest 4: Verify constraints section has preserve_headers...")
    config_path = repo_root / "config" / "handler_registry.yaml"
    registry = HandlerRegistry(config_path)

    try:
        config = registry.get_handler_config("requirements", "constraints")
        expected_headers = [
            "### Technical Constraints",
            "### Operational Constraints",
            "### Resource Constraints",
        ]
        if config.preserve_headers == expected_headers:
            print(f"  ✓ constraints: preserve_headers={config.preserve_headers}")
            return True
        else:
            print(f"  ✗ constraints: preserve_headers={config.preserve_headers}")
            print(f"     Expected: {expected_headers}")
            return False
    except Exception as e:
        print(f"  ✗ Failed to get constraints config: {e}")
        return False


def test_default_fallback():
    """Test that unknown sections fall back to default."""
    print("\nTest 5: Test default fallback for unknown sections...")
    config_path = repo_root / "config" / "handler_registry.yaml"
    registry = HandlerRegistry(config_path)

    try:
        # Try to get config for an unknown section
        config = registry.get_handler_config("requirements", "unknown_section_xyz")
        print(f"  ✓ Unknown section returned config with mode={config.mode}")
        return True
    except Exception as e:
        print(f"  ✗ Failed to get default config: {e}")
        return False


def test_supports_doc_type():
    """Test the supports_doc_type method."""
    print("\nTest 6: Test supports_doc_type method...")
    config_path = repo_root / "config" / "handler_registry.yaml"
    registry = HandlerRegistry(config_path)

    test_cases = [
        ("requirements", True),
        ("research", True),  # Should return True if _default exists
        ("unknown_type", True),  # Should return True if _default exists
    ]

    all_passed = True
    for doc_type, expected in test_cases:
        result = registry.supports_doc_type(doc_type)
        if result == expected:
            print(f"  ✓ supports_doc_type('{doc_type}') = {result}")
        else:
            print(f"  ✗ supports_doc_type('{doc_type}') = {result}, expected {expected}")
            all_passed = False

    return all_passed


def test_malformed_yaml():
    """Test error handling for malformed YAML."""
    print("\nTest 7: Test error handling for malformed YAML...")

    # Create a temporary malformed YAML file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("invalid:\n  yaml:\n    - unclosed list\n  - item")
        temp_path = Path(f.name)

    try:
        try:
            registry = HandlerRegistry(temp_path)
            print(f"  ✗ Should have raised HandlerRegistryError for malformed YAML")
            return False
        except HandlerRegistryError as e:
            print(f"  ✓ Correctly raised HandlerRegistryError: {str(e)[:80]}...")
            return True
    finally:
        temp_path.unlink()


def test_missing_config_file():
    """Test error handling for missing config file."""
    print("\nTest 8: Test error handling for missing config file...")

    missing_path = Path("/tmp/nonexistent_config.yaml")

    try:
        registry = HandlerRegistry(missing_path)
        print(f"  ✗ Should have raised HandlerRegistryError for missing file")
        return False
    except HandlerRegistryError as e:
        if "not found" in str(e):
            print(f"  ✓ Correctly raised HandlerRegistryError for missing file")
            return True
        else:
            print(f"  ✗ Wrong error message: {e}")
            return False


def main():
    """Run all tests."""
    print("=" * 70)
    print("Handler Registry Test Suite")
    print("=" * 70)

    tests = [
        test_load_valid_config,
        test_get_handler_config,
        test_assumptions_dedupe,
        test_constraints_preserve_headers,
        test_default_fallback,
        test_supports_doc_type,
        test_malformed_yaml,
        test_missing_config_file,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"  ✗ Test failed with exception: {e}")
            import traceback

            traceback.print_exc()
            results.append(False)

    print("\n" + "=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 70)

    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
