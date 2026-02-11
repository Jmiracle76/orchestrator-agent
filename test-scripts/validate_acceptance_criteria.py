#!/usr/bin/env python3
"""
Acceptance Criteria Validation for Issue 4: Section Handler Registry

This script validates all acceptance criteria listed in the issue.
"""
import sys
from pathlib import Path
import tempfile

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.handler_registry import HandlerRegistry, HandlerRegistryError
from requirements_automation.models import HandlerConfig
from requirements_automation.parsing import extract_workflow_order
from requirements_automation.utils_io import read_text, split_lines

def validate_acceptance_criteria():
    """Validate all acceptance criteria from Issue 4."""
    print("=" * 70)
    print("Acceptance Criteria Validation - Issue 4: Section Handler Registry")
    print("=" * 70)
    
    results = []
    
    # ✅ tools/config/handler_registry.yaml exists with entries for all current requirements sections
    print("\n✅ AC1: tools/config/handler_registry.yaml exists with all requirements sections")
    config_path = repo_root / "tools" / "config" / "handler_registry.yaml"
    if not config_path.exists():
        print("  ✗ FAILED: handler_registry.yaml not found")
        results.append(False)
    else:
        registry = HandlerRegistry(config_path)
        required_sections = [
            "problem_statement",
            "goals_objectives",
            "stakeholders_users",
            "success_criteria",
            "assumptions",
            "constraints",
            "requirements",
            "interfaces_integrations",
            "data_considerations",
            "risks_open_issues",
            "approval_record",
        ]
        missing = []
        for section in required_sections:
            try:
                config = registry.get_handler_config("requirements", section)
            except Exception:
                missing.append(section)
        
        if missing:
            print(f"  ✗ FAILED: Missing sections: {', '.join(missing)}")
            results.append(False)
        else:
            print(f"  ✓ PASSED: All {len(required_sections)} required sections have handlers")
            results.append(True)
    
    # ✅ HandlerRegistry class loads and parses YAML correctly
    print("\n✅ AC2: HandlerRegistry class loads and parses YAML correctly")
    try:
        registry = HandlerRegistry(config_path)
        if not registry.config:
            print("  ✗ FAILED: Registry config is empty")
            results.append(False)
        else:
            print(f"  ✓ PASSED: Registry loaded with {len(registry.config)} doc types")
            results.append(True)
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        results.append(False)
    
    # ✅ HandlerConfig dataclass defined with all configuration fields
    print("\n✅ AC3: HandlerConfig dataclass defined with all fields")
    try:
        registry = HandlerRegistry(config_path)
        config = registry.get_handler_config("requirements", "problem_statement")
        
        required_fields = [
            "section_id", "mode", "output_format", "subsections", "dedupe",
            "preserve_headers", "sanitize_remove", "llm_profile",
            "auto_apply_patches", "scope"
        ]
        missing_fields = [f for f in required_fields if not hasattr(config, f)]
        
        if missing_fields:
            print(f"  ✗ FAILED: Missing fields: {', '.join(missing_fields)}")
            results.append(False)
        else:
            print(f"  ✓ PASSED: HandlerConfig has all {len(required_fields)} required fields")
            results.append(True)
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        results.append(False)
    
    # ✅ Registry maps (doc_type="requirements", section_id="assumptions") → handler config with dedupe=true
    print("\n✅ AC4: Registry maps assumptions → config with dedupe=True")
    try:
        registry = HandlerRegistry(config_path)
        config = registry.get_handler_config("requirements", "assumptions")
        
        if config.dedupe:
            print(f"  ✓ PASSED: assumptions has dedupe=True")
            results.append(True)
        else:
            print(f"  ✗ FAILED: assumptions has dedupe={config.dedupe}, expected True")
            results.append(False)
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        results.append(False)
    
    # ✅ Registry maps review_gate:coherence_check → review gate config
    print("\n✅ AC5: Registry maps review_gate:coherence_check → review gate config")
    try:
        registry = HandlerRegistry(config_path)
        config = registry.get_handler_config("requirements", "review_gate:coherence_check")
        
        if config.mode == "review_gate":
            print(f"  ✓ PASSED: review_gate:coherence_check has mode='review_gate'")
            results.append(True)
        else:
            print(f"  ✗ FAILED: review_gate:coherence_check has mode='{config.mode}'")
            results.append(False)
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        results.append(False)
    
    # ✅ Default handler exists for unknown sections (_default key)
    print("\n✅ AC6: Default handler exists (_default key)")
    try:
        registry = HandlerRegistry(config_path)
        
        if "_default" in registry.config:
            print(f"  ✓ PASSED: _default key exists in config")
            results.append(True)
        else:
            print(f"  ✗ FAILED: _default key not found")
            results.append(False)
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        results.append(False)
    
    # ✅ Unknown doc_type falls back to _default or produces clear error
    print("\n✅ AC7: Unknown doc_type falls back to _default")
    try:
        registry = HandlerRegistry(config_path)
        
        # Try an unknown doc_type
        config = registry.get_handler_config("unknown_doc_type", "some_section")
        print(f"  ✓ PASSED: Unknown doc_type falls back successfully")
        results.append(True)
    except HandlerRegistryError as e:
        # Error is also acceptable if no _default exists
        if "_default" not in registry.config:
            print(f"  ✓ PASSED: Clear error for unknown doc_type (no _default)")
            results.append(True)
        else:
            print(f"  ✗ FAILED: Error despite _default existing: {e}")
            results.append(False)
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        results.append(False)
    
    # ✅ Invalid YAML produces clear error with file/line info
    print("\n✅ AC8: Invalid YAML produces clear error")
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("invalid:\n  yaml:\n    - unclosed list\n  - item")
        temp_path = Path(f.name)
    
    try:
        try:
            registry = HandlerRegistry(temp_path)
            print(f"  ✗ FAILED: Should have raised HandlerRegistryError")
            results.append(False)
        except HandlerRegistryError as e:
            error_msg = str(e)
            if "YAML" in error_msg or "parse" in error_msg.lower():
                print(f"  ✓ PASSED: Clear error message for invalid YAML")
                results.append(True)
            else:
                print(f"  ✗ FAILED: Error message unclear: {error_msg}")
                results.append(False)
    finally:
        temp_path.unlink()
    
    # ✅ WorkflowRunner uses registry to get handler configs
    print("\n✅ AC9: WorkflowRunner uses registry")
    try:
        # Check that runner_v2.py has the integration
        runner_path = repo_root / "tools" / "requirements_automation" / "runner_v2.py"
        runner_code = runner_path.read_text()
        
        checks = [
            "handler_registry" in runner_code,
            "get_handler_config" in runner_code,
            "self.handler_registry" in runner_code,
        ]
        
        if all(checks):
            print(f"  ✓ PASSED: WorkflowRunner integrates with handler registry")
            results.append(True)
        else:
            print(f"  ✗ FAILED: WorkflowRunner missing handler registry integration")
            results.append(False)
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        results.append(False)
    
    # ✅ All handler modes documented
    print("\n✅ AC10: All handler modes documented")
    try:
        modes = ["integrate_then_questions", "questions_then_integrate", "review_gate"]
        config_text = config_path.read_text()
        
        documented_modes = [m for m in modes if m in config_text]
        
        if len(documented_modes) == len(modes):
            print(f"  ✓ PASSED: All {len(modes)} handler modes documented in YAML")
            results.append(True)
        else:
            missing = set(modes) - set(documented_modes)
            print(f"  ✗ FAILED: Missing modes in docs: {', '.join(missing)}")
            results.append(False)
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        results.append(False)
    
    # ✅ Handler config includes LLM profile reference
    print("\n✅ AC11: Handler config includes LLM profile reference")
    try:
        registry = HandlerRegistry(config_path)
        config = registry.get_handler_config("requirements", "problem_statement")
        
        if hasattr(config, "llm_profile") and config.llm_profile:
            print(f"  ✓ PASSED: llm_profile='{config.llm_profile}'")
            results.append(True)
        else:
            print(f"  ✗ FAILED: llm_profile missing or empty")
            results.append(False)
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        results.append(False)
    
    # Summary
    print("\n" + "=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"Acceptance Criteria: {passed}/{total} PASSED")
    
    if passed == total:
        print("✓ ALL ACCEPTANCE CRITERIA MET")
    else:
        failed_count = total - passed
        print(f"✗ {failed_count} ACCEPTANCE CRITERIA FAILED")
    
    print("=" * 70)
    
    return passed == total

def main():
    """Run acceptance criteria validation."""
    try:
        success = validate_acceptance_criteria()
        return 0 if success else 1
    except Exception as e:
        print(f"\n✗ Validation failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
