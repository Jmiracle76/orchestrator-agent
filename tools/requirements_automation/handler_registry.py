"""Handler Registry for Section Processing Configuration.

This module provides the HandlerRegistry class that loads and manages
section handler configurations from YAML files. The registry maps
(doc_type, section_id) pairs to handler configurations, enabling
flexible, configuration-driven section processing.
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import yaml
from .models import HandlerConfig


class HandlerRegistryError(Exception):
    """Base exception for handler registry errors."""
    pass


class HandlerRegistry:
    """
    Registry that maps (doc_type, section_id) -> handler configuration.
    
    This decouples section processing logic from code, allowing new document
    types and section behaviors to be defined via YAML configuration files
    without engine changes.
    
    Example YAML structure:
        requirements:
          problem_statement:
            mode: integrate_then_questions
            output_format: prose
            subsections: false
            dedupe: false
            preserve_headers: []
            sanitize_remove: []
            llm_profile: requirements
            auto_apply_patches: false
            scope: current_section
    """
    
    # Valid handler modes
    VALID_MODES = {
        "integrate_then_questions",  # Default: integrate answers, then generate questions if needed
        "questions_then_integrate",  # Alternative: generate questions first, then integrate
        "review_gate",               # Special: review specified scope, return pass/fail + patches
    }
    
    # Valid output formats
    VALID_OUTPUT_FORMATS = {
        "prose",        # Paragraph format
        "bullets",      # Bullet list format
        "subsections",  # Preserve subsection headers
    }
    
    # Valid scope values
    VALID_SCOPES = {
        "current_section",    # Review only current section
        "all_prior_sections", # Review all sections before this gate
        "entire_document",    # Review all sections in document
    }
    
    @staticmethod
    def _is_valid_scope(scope: str) -> bool:
        """Check if scope value is valid (handles dynamic scope formats)."""
        if scope in HandlerRegistry.VALID_SCOPES:
            return True
        # Support "sections:X,Y,Z" format
        if scope.startswith("sections:"):
            return True
        return False
    
    # Required keys in handler config
    REQUIRED_KEYS = {
        "mode",
        "output_format",
        "subsections",
        "dedupe",
        "preserve_headers",
        "sanitize_remove",
        "llm_profile",
        "auto_apply_patches",
        "scope",
    }
    
    # Optional keys in handler config
    OPTIONAL_KEYS = {
        "validation_rules",  # for review_gate mode
    }
    
    def __init__(self, config_path: Path):
        """
        Initialize the handler registry from a YAML configuration file.
        
        Args:
            config_path: Path to handler_registry.yaml file
            
        Raises:
            HandlerRegistryError: If config file is missing or invalid
        """
        self.config_path = config_path
        self.config: Dict[str, Dict[str, Dict[str, Any]]] = {}
        
        if not config_path.exists():
            raise HandlerRegistryError(
                f"Handler registry config file not found: {config_path}\n"
                f"Please create tools/config/handler_registry.yaml in the repository root."
            )
        
        try:
            self.config = self._load_yaml(config_path)
        except yaml.YAMLError as e:
            raise HandlerRegistryError(
                f"Failed to parse handler registry YAML: {config_path}\n"
                f"YAML error: {e}"
            )
        except Exception as e:
            raise HandlerRegistryError(
                f"Failed to load handler registry: {config_path}\n"
                f"Error: {e}"
            )
        
        self._validate_schema()
    
    def _load_yaml(self, path: Path) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """Load and parse YAML configuration file."""
        with open(path, 'r') as f:
            content = yaml.safe_load(f)
        
        if not isinstance(content, dict):
            raise HandlerRegistryError(
                f"Handler registry YAML must be a dictionary at root level"
            )
        
        return content
    
    def _validate_schema(self) -> None:
        """
        Validate that the loaded configuration has the expected structure.
        
        Raises:
            HandlerRegistryError: If configuration is invalid
        """
        if not self.config:
            raise HandlerRegistryError(
                "Handler registry is empty. At least one doc_type must be defined."
            )
        
        # Validate each doc_type and its sections
        for doc_type, sections in self.config.items():
            if not isinstance(sections, dict):
                raise HandlerRegistryError(
                    f"Invalid config for doc_type '{doc_type}': "
                    f"expected dict of section configs, got {type(sections).__name__}"
                )
            
            # Validate each section's handler config
            for section_id, handler_config in sections.items():
                if not isinstance(handler_config, dict):
                    raise HandlerRegistryError(
                        f"Invalid config for section '{section_id}' in doc_type '{doc_type}': "
                        f"expected dict, got {type(handler_config).__name__}"
                    )
                
                # Check required keys
                missing_keys = self.REQUIRED_KEYS - handler_config.keys()
                if missing_keys:
                    raise HandlerRegistryError(
                        f"Missing required keys in handler config for "
                        f"section '{section_id}' in doc_type '{doc_type}': "
                        f"{', '.join(sorted(missing_keys))}"
                    )
                
                # Validate mode
                mode = handler_config.get("mode")
                if mode not in self.VALID_MODES:
                    raise HandlerRegistryError(
                        f"Invalid mode '{mode}' for section '{section_id}' in doc_type '{doc_type}'. "
                        f"Valid modes: {', '.join(sorted(self.VALID_MODES))}"
                    )
                
                # Validate output_format
                output_format = handler_config.get("output_format")
                if output_format not in self.VALID_OUTPUT_FORMATS:
                    raise HandlerRegistryError(
                        f"Invalid output_format '{output_format}' for section '{section_id}' "
                        f"in doc_type '{doc_type}'. "
                        f"Valid formats: {', '.join(sorted(self.VALID_OUTPUT_FORMATS))}"
                    )
                
                # Validate scope
                scope = handler_config.get("scope")
                if not self._is_valid_scope(scope):
                    raise HandlerRegistryError(
                        f"Invalid scope '{scope}' for section '{section_id}' "
                        f"in doc_type '{doc_type}'. "
                        f"Valid scopes: {', '.join(sorted(self.VALID_SCOPES))} or 'sections:X,Y,Z'"
                    )
    
    def get_handler_config(self, doc_type: str, section_id: str) -> HandlerConfig:
        """
        Get handler configuration for a specific (doc_type, section_id) pair.
        
        Args:
            doc_type: Document type (e.g., "requirements", "research")
            section_id: Section identifier (e.g., "problem_statement", "assumptions")
            
        Returns:
            HandlerConfig object with configuration for the section
            
        Raises:
            HandlerRegistryError: If doc_type not found and no default exists
        """
        # Try to find specific doc_type config
        doc_config = self.config.get(doc_type)
        
        if doc_config is None:
            # Try to use default config
            default_config = self.config.get("_default")
            if default_config is None:
                raise HandlerRegistryError(
                    f"Unknown doc_type '{doc_type}' and no _default handler defined. "
                    f"Available doc_types: {', '.join(sorted(k for k in self.config.keys() if k != '_default'))}"
                )
            doc_config = default_config
            logging.warning(
                f"Using default handler config for unknown doc_type '{doc_type}'"
            )
        
        # Try to find specific section config
        handler_data = doc_config.get(section_id)
        
        if handler_data is None:
            # Section not found in this doc_type, use generic default
            logging.warning(
                f"Section '{section_id}' not found in doc_type '{doc_type}', "
                f"using generic default handler"
            )
            # Create a generic default config
            handler_data = {
                "mode": "integrate_then_questions",
                "output_format": "prose",
                "subsections": False,
                "dedupe": False,
                "preserve_headers": [],
                "sanitize_remove": [],
                "llm_profile": "requirements",  # Default to requirements profile
                "auto_apply_patches": "never",
                "scope": "current_section",
                "validation_rules": [],
            }
        
        # Create HandlerConfig object
        return HandlerConfig(
            section_id=section_id,
            mode=handler_data["mode"],
            output_format=handler_data["output_format"],
            subsections=handler_data["subsections"],
            dedupe=handler_data["dedupe"],
            preserve_headers=handler_data.get("preserve_headers", []),
            sanitize_remove=handler_data.get("sanitize_remove", []),
            llm_profile=handler_data["llm_profile"],
            auto_apply_patches=handler_data["auto_apply_patches"],
            scope=handler_data["scope"],
            validation_rules=handler_data.get("validation_rules", []),
        )
    
    def supports_doc_type(self, doc_type: str) -> bool:
        """
        Check if a document type is supported by the registry.
        
        Args:
            doc_type: Document type to check
            
        Returns:
            True if doc_type is in registry or _default exists, False otherwise
        """
        return doc_type in self.config or "_default" in self.config
