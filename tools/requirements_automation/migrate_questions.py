#!/usr/bin/env python3
"""Migration tool to convert documents from global to per-section question tables."""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Ensure we can import from the tools package
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools.requirements_automation.models import OpenQuestion
from tools.requirements_automation.open_questions import open_questions_parse
from tools.requirements_automation.parsing import find_sections, get_section_span
from tools.requirements_automation.section_questions import (
    get_section_questions_table_name,
    insert_section_questions_batch,
)
from tools.requirements_automation.utils_io import (
    join_lines,
    read_text,
    split_lines,
    write_text,
)

# Mapping of sections to their expected question table
SECTION_TO_TABLE = {
    "problem_statement": "problem_statement_questions",
    "goals_objectives": "goals_objectives_questions",
    "stakeholders_users": "stakeholders_users_questions",
    "success_criteria": "success_criteria_questions",
    "assumptions": "assumptions_questions",
    "constraints": "constraints_questions",
}


def distribute_questions_to_sections(
    lines: List[str], questions: List[OpenQuestion]
) -> Tuple[Dict[str, List[Tuple[str, str]]], List[OpenQuestion]]:
    """Distribute global questions to section-specific lists.

    Args:
        lines: Document content
        questions: List of questions from global table

    Returns:
        Tuple of (section_questions_dict, unmapped_questions)
    """
    section_questions: Dict[str, List[Tuple[str, str]]] = {
        section: [] for section in SECTION_TO_TABLE.keys()
    }

    unmapped_questions = []

    for q in questions:
        # Map section_target to actual section
        target = q.section_target.strip()

        # Handle various aliases and formats
        if target in SECTION_TO_TABLE:
            section_id = target
        elif target.replace("-", "_") in SECTION_TO_TABLE:
            section_id = target.replace("-", "_")
        elif target.replace(" ", "_").lower() in SECTION_TO_TABLE:
            section_id = target.replace(" ", "_").lower()
        else:
            # Try to find by partial match
            section_id = None
            for s in SECTION_TO_TABLE.keys():
                if target.lower() in s or s in target.lower():
                    section_id = s
                    break

        if section_id:
            # Add to section-specific list
            section_questions[section_id].append((q.question, q.date))
        else:
            # Keep in unmapped list
            unmapped_questions.append(q)
            logging.warning(
                f"Could not map question '{q.question_id}' with target '{target}' to a section"
            )

    return section_questions, unmapped_questions


def check_section_has_questions_table(lines: List[str], section_id: str) -> bool:
    """Check if section already has a questions table.

    Args:
        lines: Document content
        section_id: Section identifier

    Returns:
        True if section has questions table, False otherwise
    """
    table_name = get_section_questions_table_name(section_id)
    table_marker = f"<!-- table:{table_name} -->"

    return any(table_marker in line for line in lines)


def migrate_document(doc_path: Path, backup: bool = True) -> int:
    """Migrate a document from global to per-section question tables.

    Args:
        doc_path: Path to requirements document
        backup: Whether to create a backup before migrating

    Returns:
        Exit code (0 for success)
    """
    print(f"Migrating document: {doc_path}")

    # Read document
    try:
        content = read_text(doc_path)
        lines = split_lines(content)
    except Exception as e:
        print(f"Error reading document: {e}")
        return 1

    # Create backup if requested
    if backup:
        backup_path = doc_path.with_suffix(doc_path.suffix + ".backup")
        shutil.copy2(doc_path, backup_path)
        print(f"Created backup: {backup_path}")

    # Parse global questions
    try:
        questions, table_span, _ = open_questions_parse(lines)
        print(f"Found {len(questions)} questions in global table")
    except Exception as e:
        print(f"Error parsing global questions table: {e}")
        print("Document may already be migrated or have no global questions table")
        return 0

    if not questions:
        print("No questions to migrate")
        return 0

    # Distribute questions to sections
    section_questions, unmapped = distribute_questions_to_sections(lines, questions)

    # Count total questions to be migrated
    total_to_migrate = sum(len(qs) for qs in section_questions.values())
    print(f"\nDistribution:")
    for section_id, qs in section_questions.items():
        if qs:
            print(f"  {section_id}: {len(qs)} questions")

    if unmapped:
        print(f"\nWarning: {len(unmapped)} questions could not be mapped to sections:")
        for q in unmapped:
            print(f"  - {q.question_id}: {q.section_target}")

    # Insert questions into section tables
    modified_lines = lines.copy()
    inserted_total = 0

    for section_id, qs in section_questions.items():
        if not qs:
            continue

        # Check if section has questions table
        if not check_section_has_questions_table(modified_lines, section_id):
            print(f"\nWarning: Section '{section_id}' does not have a questions table")
            print(
                f"  Please update the template to include <!-- table:{get_section_questions_table_name(section_id)} -->"
            )
            continue

        try:
            modified_lines, inserted = insert_section_questions_batch(
                modified_lines, section_id, qs
            )
            inserted_total += inserted
            print(f"  Inserted {inserted} questions into {section_id}")
        except Exception as e:
            print(f"  Error inserting questions into {section_id}: {e}")
            continue

    print(f"\nTotal questions migrated: {inserted_total}/{total_to_migrate}")

    # Remove global questions table (optional - commented out for safety)
    # We'll keep the global table for now to maintain backward compatibility
    # Users can manually remove it after verifying the migration
    print("\nNote: Global Open Questions table has been preserved for backward compatibility")
    print("You may manually remove it after verifying the migration")

    # Write updated document
    try:
        content = join_lines(modified_lines)
        write_text(doc_path, content)
        print(f"\nMigration complete! Updated document: {doc_path}")
        return 0
    except Exception as e:
        print(f"Error writing document: {e}")
        return 1


def main(argv: List[str] | None = None) -> int:
    """Run the migration tool."""
    parser = argparse.ArgumentParser(
        description="Migrate requirements document from global to per-section question tables"
    )
    parser.add_argument("--doc", required=True, help="Path to requirements document to migrate")
    parser.add_argument("--no-backup", action="store_true", help="Skip creating backup file")
    parser.add_argument(
        "--log-level", default="INFO", help="Logging level (DEBUG, INFO, WARNING, ERROR)"
    )

    args = parser.parse_args(argv)

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(levelname)s: %(message)s",
    )

    # Validate document path
    doc_path = Path(args.doc).resolve()
    if not doc_path.exists():
        print(f"Error: Document not found: {doc_path}")
        return 1

    # Run migration
    return migrate_document(doc_path, backup=not args.no_backup)


if __name__ == "__main__":
    sys.exit(main())
