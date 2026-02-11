"""Profile Loader for LLM Policy and Style Profiles.

This module provides the ProfileLoader class that loads and manages
markdown-based LLM policy and style profiles. Profiles define rules-based
guidance for LLM reasoning style, output constraints, and content quality
standards.
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Dict


class ProfileLoaderError(Exception):
    """Base exception for profile loader errors."""
    pass


class ProfileLoader:
    """
    Loader for LLM policy and style profile markdown files.
    
    Profiles are markdown files that define:
    - Base policy: Universal rules injected into every LLM call
    - Task styles: Document-type-specific guidance for reasoning and output
    
    Profiles are cached in memory to avoid repeated disk reads.
    
    Example usage:
        loader = ProfileLoader()
        full_profile = loader.build_full_profile("requirements")
        # Returns: base_policy.md + requirements.md combined
    """
    
    def __init__(self, profiles_dir: Path = None):
        """
        Initialize the profile loader.
        
        Args:
            profiles_dir: Path to profiles directory. Defaults to 'profiles'
                         relative to repository root.
        """
        if profiles_dir is None:
            # Default to profiles/ in repository root
            # Assume this module is in tools/requirements_automation/
            repo_root = Path(__file__).parent.parent.parent
            profiles_dir = repo_root / "profiles"
        
        self.profiles_dir = Path(profiles_dir)
        self._cache: Dict[str, str] = {}
        
        # Validate profiles directory exists
        if not self.profiles_dir.exists():
            raise ProfileLoaderError(
                f"Profiles directory not found: {self.profiles_dir}\n"
                f"Please create profiles/ directory in the repository root."
            )
        
        # Validate base_policy.md exists (critical dependency)
        base_policy_path = self.profiles_dir / "base_policy.md"
        if not base_policy_path.exists():
            raise ProfileLoaderError(
                f"Base policy file not found: {base_policy_path}\n"
                f"Please create profiles/base_policy.md (required for all LLM calls)."
            )
    
    def load_profile(self, profile_name: str) -> str:
        """
        Load and cache a profile markdown file as a string.
        
        Args:
            profile_name: Profile name (without .md extension)
        
        Returns:
            Profile content as string
            
        Raises:
            ProfileLoaderError: If profile file not found or cannot be read
        """
        if profile_name in self._cache:
            logging.debug("Using cached profile: %s", profile_name)
            return self._cache[profile_name]
        
        profile_path = self.profiles_dir / f"{profile_name}.md"
        
        if not profile_path.exists():
            raise ProfileLoaderError(
                f"Profile not found: {profile_path}\n"
                f"Available profiles: {self._list_available_profiles()}"
            )
        
        try:
            content = profile_path.read_text(encoding="utf-8")
            self._cache[profile_name] = content
            logging.debug("Loaded profile: %s (%d chars)", profile_name, len(content))
            return content
        except Exception as e:
            raise ProfileLoaderError(
                f"Failed to read profile file: {profile_path}\n"
                f"Error: {e}"
            )
    
    def get_base_policy(self) -> str:
        """
        Load base policy (injected into every LLM call).
        
        Returns:
            Base policy content as string
            
        Raises:
            ProfileLoaderError: If base_policy.md not found
        """
        return self.load_profile("base_policy")
    
    def build_full_profile(self, task_style: str) -> str:
        """
        Combine base policy + task style into full profile.
        
        Args:
            task_style: Task style profile name (e.g., "requirements", "requirements_review")
        
        Returns:
            Combined profile as string (base + separator + task style)
            
        Raises:
            ProfileLoaderError: If base_policy.md or task style profile not found
        """
        base = self.get_base_policy()
        task = self.load_profile(task_style)
        return f"{base}\n\n---\n\n{task}"
    
    def _list_available_profiles(self) -> str:
        """
        List available profile files for error messages.
        
        Returns:
            Comma-separated list of profile names (without .md extension)
        """
        try:
            md_files = list(self.profiles_dir.glob("*.md"))
            # Exclude README.md from profile list
            profile_names = [
                f.stem for f in md_files 
                if f.stem.lower() != "readme"
            ]
            return ", ".join(sorted(profile_names))
        except Exception:
            return "(unable to list profiles)"
    
    def clear_cache(self):
        """Clear the profile cache (useful for testing or hot-reloading)."""
        self._cache.clear()
        logging.debug("Profile cache cleared")
