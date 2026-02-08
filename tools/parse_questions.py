#!/usr/bin/env python3
"""
Parsing utilities for section-based Open Questions format.
"""

import re
from typing import Dict, List, Tuple, Optional


def parse_open_questions_section(content: str) -> List[Dict[str, str]]:
    """
    Parse section-based Open Questions format.
    
    Returns a list of question dictionaries with fields:
    - id: Question ID (e.g., "Q-001")
    - title: Question title
    - status: Status value (Open, Resolved, Deferred)
    - asked_by: Who asked the question
    - date: Date in YYYY-MM-DD format
    - question: The question text
    - answer: The answer text (may be empty)
    - targets: List of integration target strings
    """
    questions = []
    
    # Find the Open Questions section
    open_q_match = re.search(r'### Open Questions\n', content)
    if not open_q_match:
        return questions
    
    start_pos = open_q_match.end()
    
    # Find the end of the Open Questions section (comment block, not separator lines)
    rest = content[start_pos:]
    end_pattern = r'\n<!--\s*ANSWER INTEGRATION WORKFLOW'
    
    end_match = re.search(end_pattern, rest)
    if end_match:
        end_pos = end_match.start()
    else:
        # Fallback: next major section
        next_section = re.search(r'\n---\n\n## \d+\.', rest)
        end_pos = next_section.start() if next_section else len(rest)
    
    section_content = rest[:end_pos]
    
    # Find all question blocks using a simple approach
    # Each question starts with #### Q-XXX: and ends before the next #### or ---
    question_starts = [(m.start(), m.group()) for m in re.finditer(r'####\s+(Q-\d+):\s+(.+)', section_content)]
    
    for i, (start, heading_text) in enumerate(question_starts):
        # Find end of this question block
        if i + 1 < len(question_starts):
            end = question_starts[i + 1][0]
        else:
            end = len(section_content)
        
        # Extract the block
        block = section_content[start:end]
        
        # Parse heading
        heading_match = re.match(r'####\s+(Q-\d+):\s+(.+)', heading_text)
        if not heading_match:
            continue
        
        q_id = heading_match.group(1).strip()
        title = heading_match.group(2).strip()
        
        # Parse fields from block
        status_match = re.search(r'\*\*Status:\*\*\s+(.+?)\s*\n', block)
        asked_by_match = re.search(r'\*\*Asked by:\*\*\s+(.+?)\s*\n', block)
        date_match = re.search(r'\*\*Date:\*\*\s+(.+?)\s*\n', block)
        
        question_match = re.search(r'\*\*Question:\*\*\s*\n(.+?)\s*\n\*\*Answer:\*\*', block, re.DOTALL)
        answer_match = re.search(r'\*\*Answer:\*\*\s*\n(.+?)\s*\n\*\*Integration Targets:\*\*', block, re.DOTALL)
        targets_match = re.search(r'\*\*Integration Targets:\*\*\s*\n((?:- .+\n?)+)', block)
        
        if not all([status_match, asked_by_match, date_match, question_match, targets_match]):
            continue
        
        status = status_match.group(1).strip()
        asked_by = asked_by_match.group(1).strip()
        date = date_match.group(1).strip()
        question = question_match.group(1).strip()
        answer = answer_match.group(1).strip() if answer_match else ""
        targets_text = targets_match.group(1).strip()
        
        # Parse targets list
        targets = []
        for line in targets_text.split('\n'):
            line = line.strip()
            if line.startswith('- '):
                target = line[2:].strip()
                if target:  # Only add non-empty targets
                    targets.append(target)
        
        questions.append({
            'id': q_id,
            'title': title,
            'status': status,
            'asked_by': asked_by,
            'date': date,
            'question': question,
            'answer': answer,
            'targets': targets
        })
    
    return questions


def has_pending_answers_section_based(content: str) -> bool:
    """
    Check if there are answered questions pending integration.
    
    Returns True if any question has:
    - Non-empty Answer field
    - Status is not "Resolved"
    """
    questions = parse_open_questions_section(content)
    
    for q in questions:
        answer = q['answer'].strip()
        status = q['status'].strip()
        
        # Has answer and not resolved
        if answer and not status.lower().startswith('resolved'):
            return True
    
    return False


def update_question_status(content: str, question_id: str, new_status: str) -> str:
    """
    Update the status of a specific question.
    
    Args:
        content: Full document content
        question_id: Question ID (e.g., "Q-001")
        new_status: New status value
        
    Returns:
        Updated document content
    """
    # Find the question heading
    pattern = rf'(#### {re.escape(question_id)}:.+?\n\n\*\*Status:\*\*\s+)(.+?)(\s*\n)'
    
    def replace_status(match):
        return match.group(1) + new_status + match.group(3)
    
    return re.sub(pattern, replace_status, content)


def format_new_question(
    q_id: str,
    title: str,
    asked_by: str,
    date: str,
    question: str,
    status: str = "Open",
    answer: str = "",
    targets: Optional[List[str]] = None
) -> str:
    """
    Format a new question in section-based format.
    
    Returns the formatted question string ready to insert.
    """
    if targets is None:
        targets = ["TBD"]
    
    lines = [
        f"#### {q_id}: {title}\n",
        "\n",
        f"**Status:** {status}  \n",
        f"**Asked by:** {asked_by}  \n",
        f"**Date:** {date}  \n",
        "\n",
        "**Question:**  \n",
        f"{question}\n",
        "\n",
        "**Answer:**  \n",
        f"{answer}\n",
        "\n",
        "**Integration Targets:**  \n",
    ]
    
    for target in targets:
        lines.append(f"- {target}\n")
    
    return ''.join(lines)


if __name__ == '__main__':
    # Test parsing
    import sys
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r', encoding='utf-8') as f:
            content = f.read()
        
        questions = parse_open_questions_section(content)
        print(f"Found {len(questions)} questions:")
        for q in questions:
            print(f"  {q['id']}: {q['title']} - Status: {q['status']}")
            print(f"    Answer: {'Yes' if q['answer'] else 'No'}")
        
        has_pending = has_pending_answers_section_based(content)
        print(f"\nHas pending answers: {has_pending}")
