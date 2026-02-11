#!/usr/bin/env python3
"""
Manual test script for ProfileLoader functionality.

This script validates the profile loader implementation by testing:
1. Loading base_policy.md
2. Loading task style profiles
3. Building full profiles (base + task)
4. Error handling for missing profiles
5. Profile caching functionality
"""
import sys
from pathlib import Path
import tempfile
import os

# Add the tools directory to the path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from requirements_automation.profile_loader import ProfileLoader, ProfileLoaderError


def test_load_base_policy():
    """Test loading base policy profile."""
    print("Test 1: Load base policy profile...")
    
    try:
        loader = ProfileLoader()
        base_policy = loader.get_base_policy()
        
        if not base_policy:
            print("  ✗ Base policy is empty")
            return False
        
        # Verify key content exists
        if "Core Rules" not in base_policy:
            print("  ✗ Base policy missing 'Core Rules' section")
            return False
        
        if "Forbidden Actions" not in base_policy:
            print("  ✗ Base policy missing 'Forbidden Actions' section")
            return False
        
        print(f"  ✓ Successfully loaded base policy ({len(base_policy)} chars)")
        return True
    except Exception as e:
        print(f"  ✗ Failed to load base policy: {e}")
        return False


def test_load_requirements_profile():
    """Test loading requirements task style profile."""
    print("\nTest 2: Load requirements profile...")
    
    try:
        loader = ProfileLoader()
        requirements = loader.load_profile("requirements")
        
        if not requirements:
            print("  ✗ Requirements profile is empty")
            return False
        
        # Verify key content exists
        if "Document Purpose" not in requirements:
            print("  ✗ Requirements profile missing 'Document Purpose' section")
            return False
        
        if "Language Guidelines" not in requirements:
            print("  ✗ Requirements profile missing 'Language Guidelines' section")
            return False
        
        print(f"  ✓ Successfully loaded requirements profile ({len(requirements)} chars)")
        return True
    except Exception as e:
        print(f"  ✗ Failed to load requirements profile: {e}")
        return False


def test_load_requirements_review_profile():
    """Test loading requirements_review profile."""
    print("\nTest 3: Load requirements_review profile...")
    
    try:
        loader = ProfileLoader()
        review = loader.load_profile("requirements_review")
        
        if not review:
            print("  ✗ Requirements review profile is empty")
            return False
        
        # Verify key content exists
        if "Review Objective" not in review:
            print("  ✗ Review profile missing 'Review Objective' section")
            return False
        
        if "Review Criteria" not in review:
            print("  ✗ Review profile missing 'Review Criteria' section")
            return False
        
        print(f"  ✓ Successfully loaded requirements_review profile ({len(review)} chars)")
        return True
    except Exception as e:
        print(f"  ✗ Failed to load requirements_review profile: {e}")
        return False


def test_build_full_profile():
    """Test building full profile (base + task style)."""
    print("\nTest 4: Build full profile (base + task)...")
    
    try:
        loader = ProfileLoader()
        full_profile = loader.build_full_profile("requirements")
        
        if not full_profile:
            print("  ✗ Full profile is empty")
            return False
        
        # Verify both base and task content exists
        if "Core Rules" not in full_profile:
            print("  ✗ Full profile missing base policy content")
            return False
        
        if "Document Purpose" not in full_profile:
            print("  ✗ Full profile missing requirements profile content")
            return False
        
        # Verify separator exists
        if "---" not in full_profile:
            print("  ✗ Full profile missing separator")
            return False
        
        print(f"  ✓ Successfully built full profile ({len(full_profile)} chars)")
        return True
    except Exception as e:
        print(f"  ✗ Failed to build full profile: {e}")
        return False


def test_profile_caching():
    """Test that profiles are cached after first load."""
    print("\nTest 5: Test profile caching...")
    
    try:
        loader = ProfileLoader()
        
        # Load profile first time
        profile1 = loader.load_profile("requirements")
        
        # Check cache
        if "requirements" not in loader._cache:
            print("  ✗ Profile not cached after first load")
            return False
        
        # Load profile second time (should use cache)
        profile2 = loader.load_profile("requirements")
        
        if profile1 != profile2:
            print("  ✗ Cached profile differs from original")
            return False
        
        # Verify they're the same object (cached)
        if id(profile1) != id(profile2):
            print("  ✗ Second load returned different object (not using cache)")
            return False
        
        print("  ✓ Profile caching works correctly")
        return True
    except Exception as e:
        print(f"  ✗ Failed profile caching test: {e}")
        return False


def test_clear_cache():
    """Test clearing the profile cache."""
    print("\nTest 6: Test cache clearing...")
    
    try:
        loader = ProfileLoader()
        
        # Load and cache a profile
        loader.load_profile("requirements")
        
        if "requirements" not in loader._cache:
            print("  ✗ Profile not in cache")
            return False
        
        # Clear cache
        loader.clear_cache()
        
        if loader._cache:
            print("  ✗ Cache not empty after clear")
            return False
        
        print("  ✓ Cache clearing works correctly")
        return True
    except Exception as e:
        print(f"  ✗ Failed cache clearing test: {e}")
        return False


def test_missing_profile_error():
    """Test error handling for missing profile file."""
    print("\nTest 7: Test error handling for missing profile...")
    
    try:
        loader = ProfileLoader()
        
        # Try to load non-existent profile
        try:
            loader.load_profile("nonexistent_profile")
            print("  ✗ Should have raised ProfileLoaderError")
            return False
        except ProfileLoaderError as e:
            if "not found" in str(e).lower():
                print("  ✓ Correctly raised ProfileLoaderError for missing profile")
                return True
            else:
                print(f"  ✗ Wrong error message: {e}")
                return False
    except Exception as e:
        print(f"  ✗ Unexpected error: {e}")
        return False


def test_missing_profiles_directory():
    """Test error handling for missing profiles directory."""
    print("\nTest 8: Test error handling for missing profiles directory...")
    
    # Create a temporary directory without profiles
    with tempfile.TemporaryDirectory() as tmpdir:
        nonexistent_profiles_dir = Path(tmpdir) / "nonexistent_profiles"
        
        try:
            loader = ProfileLoader(profiles_dir=nonexistent_profiles_dir)
            print("  ✗ Should have raised ProfileLoaderError")
            return False
        except ProfileLoaderError as e:
            if "not found" in str(e).lower():
                print("  ✓ Correctly raised ProfileLoaderError for missing directory")
                return True
            else:
                print(f"  ✗ Wrong error message: {e}")
                return False


def test_missing_base_policy():
    """Test error handling for missing base_policy.md."""
    print("\nTest 9: Test error handling for missing base_policy.md...")
    
    # Create a temporary profiles directory without base_policy.md
    with tempfile.TemporaryDirectory() as tmpdir:
        profiles_dir = Path(tmpdir) / "profiles"
        profiles_dir.mkdir()
        
        # Create a different profile but not base_policy.md
        (profiles_dir / "other.md").write_text("# Other Profile")
        
        try:
            loader = ProfileLoader(profiles_dir=profiles_dir)
            print("  ✗ Should have raised ProfileLoaderError for missing base_policy.md")
            return False
        except ProfileLoaderError as e:
            if "base policy" in str(e).lower():
                print("  ✓ Correctly raised ProfileLoaderError for missing base_policy.md")
                return True
            else:
                print(f"  ✗ Wrong error message: {e}")
                return False


def main():
    """Run all tests."""
    print("=" * 70)
    print("ProfileLoader Test Suite")
    print("=" * 70)
    
    tests = [
        test_load_base_policy,
        test_load_requirements_profile,
        test_load_requirements_review_profile,
        test_build_full_profile,
        test_profile_caching,
        test_clear_cache,
        test_missing_profile_error,
        test_missing_profiles_directory,
        test_missing_base_policy,
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
