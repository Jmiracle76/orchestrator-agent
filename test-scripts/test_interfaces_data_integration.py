#!/usr/bin/env python3
"""
Integration test for interfaces_integrations and data_considerations subsection preservation.

This test simulates the actual workflow to verify that subsections are preserved
during the drafting process using the handler registry configuration.
"""
import sys
from pathlib import Path

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.handler_registry import HandlerRegistry
from requirements_automation.runner_integration import _build_subsection_structure
from requirements_automation.parsing import (
    find_sections,
    find_subsections_within,
    get_section_span,
)
from requirements_automation.utils_io import split_lines


def test_interfaces_integrations_handler_config():
    """Test that interfaces_integrations handler is configured correctly."""
    print("\nTest 1: interfaces_integrations handler configuration")
    print("=" * 70)
    
    # Load handler registry
    config_path = repo_root / "tools" / "config" / "handler_registry.yaml"
    registry = HandlerRegistry(config_path)
    
    # Get handler config for interfaces_integrations
    config = registry.get_handler_config("requirements", "interfaces_integrations")
    
    print(f"  mode: {config.mode}")
    print(f"  output_format: {config.output_format}")
    print(f"  subsections: {config.subsections}")
    print(f"  questions_table: {config.questions_table}")
    print(f"  bootstrap_questions: {config.bootstrap_questions}")
    
    # Verify configuration
    if config.subsections:
        print("  ✓ subsections enabled")
    else:
        print("  ✗ FAILED: subsections should be enabled!")
        return False
    
    if config.questions_table == "interfaces_integrations_questions":
        print("  ✓ questions_table correctly configured")
    else:
        print(f"  ✗ FAILED: questions_table is '{config.questions_table}', expected 'interfaces_integrations_questions'")
        return False
    
    if config.bootstrap_questions:
        print("  ✓ bootstrap_questions enabled")
    else:
        print("  ✗ FAILED: bootstrap_questions should be enabled!")
        return False
    
    print("  ✓ TEST PASSED")
    return True


def test_data_considerations_handler_config():
    """Test that data_considerations handler is configured correctly."""
    print("\nTest 2: data_considerations handler configuration")
    print("=" * 70)
    
    # Load handler registry
    config_path = repo_root / "tools" / "config" / "handler_registry.yaml"
    registry = HandlerRegistry(config_path)
    
    # Get handler config for data_considerations
    config = registry.get_handler_config("requirements", "data_considerations")
    
    print(f"  mode: {config.mode}")
    print(f"  output_format: {config.output_format}")
    print(f"  subsections: {config.subsections}")
    print(f"  questions_table: {config.questions_table}")
    print(f"  bootstrap_questions: {config.bootstrap_questions}")
    
    # Verify configuration
    if config.subsections:
        print("  ✓ subsections enabled")
    else:
        print("  ✗ FAILED: subsections should be enabled!")
        return False
    
    if config.output_format == "bullets":
        print("  ✓ output_format is bullets (correct for bullet list subsections)")
    else:
        print(f"  ✗ FAILED: output_format is '{config.output_format}', expected 'bullets'")
        return False
    
    if config.questions_table == "data_considerations_questions":
        print("  ✓ questions_table correctly configured")
    else:
        print(f"  ✗ FAILED: questions_table is '{config.questions_table}', expected 'data_considerations_questions'")
        return False
    
    if config.bootstrap_questions:
        print("  ✓ bootstrap_questions enabled")
    else:
        print("  ✗ FAILED: bootstrap_questions should be enabled!")
        return False
    
    print("  ✓ TEST PASSED")
    return True


def test_interfaces_integrations_subsection_structure():
    """Test that _build_subsection_structure correctly identifies interfaces_integrations subsections."""
    print("\nTest 3: interfaces_integrations subsection structure building")
    print("=" * 70)
    
    # Load handler config
    config_path = repo_root / "tools" / "config" / "handler_registry.yaml"
    registry = HandlerRegistry(config_path)
    config = registry.get_handler_config("requirements", "interfaces_integrations")
    
    # Create test document
    test_doc = """<!-- section:interfaces_integrations -->
## 8. Interfaces and Integrations

<!-- subsection:external_systems -->
### External Systems

<!-- table:external_systems -->
| System | Purpose | Interface Type | Dependencies |
|--------|---------|----------------|--------------|

<!-- subsection:data_exchange -->
### Data Exchange

<!-- table:data_exchange -->
| Integration Point | Data Flow | Format | Frequency |
|-------------------|-----------|--------|-----------|

<!-- subsection:questions_issues -->
### Questions & Issues

<!-- table:interfaces_integrations_questions -->
| Question ID | Question | Date | Answer | Status |
|-------------|----------|------|--------|--------|
"""
    
    lines = split_lines(test_doc)
    spans = find_sections(lines)
    span = get_section_span(spans, "interfaces_integrations")
    
    if not span:
        print("  ✗ FAILED: Could not find section!")
        return False
    
    # Build subsection structure
    structure = _build_subsection_structure(lines, span, config)
    
    if structure is None:
        print("  ✗ FAILED: _build_subsection_structure returned None!")
        return False
    
    print(f"  Subsection structure: {structure}")
    
    # Verify structure contains external_systems and data_exchange
    subsection_ids = {sub["id"] for sub in structure}
    
    if "external_systems" in subsection_ids:
        print("  ✓ external_systems in structure")
    else:
        print("  ✗ FAILED: external_systems not in structure!")
        return False
    
    if "data_exchange" in subsection_ids:
        print("  ✓ data_exchange in structure")
    else:
        print("  ✗ FAILED: data_exchange not in structure!")
        return False
    
    # Verify questions_issues is excluded (it's metadata, not content)
    if "questions_issues" not in subsection_ids:
        print("  ✓ questions_issues correctly excluded from structure")
    else:
        print("  ✗ FAILED: questions_issues should not be in structure!")
        return False
    
    # Verify table types
    for sub in structure:
        if sub["id"] in ["external_systems", "data_exchange"]:
            if sub["type"] == "table":
                print(f"  ✓ {sub['id']} correctly identified as table type")
            else:
                print(f"  ✗ FAILED: {sub['id']} should be table type, got {sub['type']}")
                return False
    
    print("  ✓ TEST PASSED")
    return True


def test_data_considerations_subsection_structure():
    """Test that _build_subsection_structure correctly identifies data_considerations subsections."""
    print("\nTest 4: data_considerations subsection structure building")
    print("=" * 70)
    
    # Load handler config
    config_path = repo_root / "tools" / "config" / "handler_registry.yaml"
    registry = HandlerRegistry(config_path)
    config = registry.get_handler_config("requirements", "data_considerations")
    
    # Create test document
    test_doc = """<!-- section:data_considerations -->
## 9. Data Considerations

<!-- subsection:data_requirements -->
### Data Requirements
- [Data entity 1]

<!-- subsection:privacy_security -->
### Privacy & Security
- [Privacy consideration]

<!-- subsection:data_retention -->
### Data Retention
- [Retention policy 1]

<!-- subsection:questions_issues -->
### Questions & Issues

<!-- table:data_considerations_questions -->
| Question ID | Question | Date | Answer | Status |
|-------------|----------|------|--------|--------|
"""
    
    lines = split_lines(test_doc)
    spans = find_sections(lines)
    span = get_section_span(spans, "data_considerations")
    
    if not span:
        print("  ✗ FAILED: Could not find section!")
        return False
    
    # Build subsection structure
    structure = _build_subsection_structure(lines, span, config)
    
    if structure is None:
        print("  ✗ FAILED: _build_subsection_structure returned None!")
        return False
    
    print(f"  Subsection structure: {structure}")
    
    # Verify structure contains all three subsections
    subsection_ids = {sub["id"] for sub in structure}
    
    required_subs = ["data_requirements", "privacy_security", "data_retention"]
    for sub_id in required_subs:
        if sub_id in subsection_ids:
            print(f"  ✓ {sub_id} in structure")
        else:
            print(f"  ✗ FAILED: {sub_id} not in structure!")
            return False
    
    # Verify questions_issues is excluded
    if "questions_issues" not in subsection_ids:
        print("  ✓ questions_issues correctly excluded from structure")
    else:
        print("  ✗ FAILED: questions_issues should not be in structure!")
        return False
    
    # Verify bullet types (since output_format is "bullets")
    for sub in structure:
        if sub["id"] in required_subs:
            if sub["type"] == "bullets":
                print(f"  ✓ {sub['id']} correctly identified as bullets type")
            else:
                print(f"  ✗ FAILED: {sub['id']} should be bullets type, got {sub['type']}")
                return False
    
    print("  ✓ TEST PASSED")
    return True


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("INTEGRATION TEST: HANDLER REGISTRY & SUBSECTION STRUCTURE")
    print("=" * 70)
    
    results = []
    results.append(test_interfaces_integrations_handler_config())
    results.append(test_data_considerations_handler_config())
    results.append(test_interfaces_integrations_subsection_structure())
    results.append(test_data_considerations_subsection_structure())
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("✓ ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("✗ SOME TESTS FAILED")
        sys.exit(1)
