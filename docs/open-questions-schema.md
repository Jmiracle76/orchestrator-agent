# Open Questions Section-Based Format Specification

## Overview

This document describes the Open Questions section-based format specification that ensures consistency across all requirements documents. Each question is represented as a first-class markdown subsection with explicit fields.

## Canonical Format

Each question in the Open Questions section MUST use this structure:

```markdown
### Open Questions

#### Q-XXX: [Question Title]

**Status:** [Open | Resolved | Deferred]  
**Asked by:** [Agent or Person name]  
**Date:** [YYYY-MM-DD]  

**Question:**  
[The question text]

**Answer:**  
[Human-authored answer, may be empty for new/unanswered questions]

**Integration Targets:**  
- [Target section 1]
- [Target section 2]

---
```

### Field Specifications

1. **Heading** - Must be level 4 (####) with format: `#### Q-XXX: [Title]`
   - Question ID (Q-XXX) must be unique and stable
   - Title should be brief and descriptive
   
2. **Status** - Exact text, one of: "Open", "Resolved", or "Deferred"
   - Open: Awaiting human answer
   - Resolved: Answer integrated into requirements
   - Deferred: Postponed for later consideration

3. **Asked by** - Name of the agent or person who raised the question

4. **Date** - Date raised in YYYY-MM-DD format

5. **Question** - The complete question text

6. **Answer** - Human-provided answer (may be empty for new/unanswered questions)

7. **Integration Targets** - Bulleted list of sections where answer should be integrated

## Format Constraints

### Mandatory Requirements
- Each question MUST be a level 4 heading (####) 
- Question IDs (Q-XXX) MUST be stable and unique
- All seven labeled fields MUST be present in order
- Status MUST be one of the approved values: "Open", "Resolved", or "Deferred"
- Answer field may be empty but MUST exist
- Integration Targets MUST be a bulleted list

### Agent Behavior
- The Requirements Agent MUST include all required fields when adding new questions
- The agent MUST NOT use table format for questions
- The agent MUST maintain question ID stability across edits
- Format corrections MUST be logged in Revision History

## Implementation

### Section Parsing (`tools/invoke_requirements_agent.py`)

The parsing functions:
- Locate the `### Open Questions` section
- Parse each `#### Q-XXX:` subsection
- Extract labeled fields using pattern matching
- Validate presence of all required fields
- Return structured question data

### Mode Detection

The invocation script:
1. Parses all question subsections
2. Identifies questions with non-empty Answer and Status != "Resolved"
3. Determines mode: integrate (if pending answers) or review (otherwise)

### Answer Integration

When integrating answers:
- Agent locates target sections specified in Integration Targets
- Integrates answer content with source traceability
- Updates question Status to "Resolved"
- Logs integration in Revision History

## Testing

### Format Validation Tests

Comprehensive test suite should cover:
- Valid format validation
- Missing field detection
- Incorrect field order detection
- Question ID uniqueness
- Status value validation
- Data preservation during edits
- Edge cases and error handling

## Usage

### Manual Parsing

```python
import re

def parse_open_questions(content):
    """Parse section-based Open Questions format."""
    questions = []
    # Find all Q-XXX subsections
    pattern = r'#### (Q-\d+): (.+?)\n\n\*\*Status:\*\* (.+?)\s+\n\*\*Asked by:\*\* (.+?)\s+\n\*\*Date:\*\* (.+?)\s+\n\n\*\*Question:\*\*\s+\n(.+?)\n\n\*\*Answer:\*\*\s+\n(.+?)\n\n\*\*Integration Targets:\*\*\s+\n((?:- .+?\n)+)'
    
    for match in re.finditer(pattern, content, re.DOTALL):
        q_id, title, status, asked_by, date, question, answer, targets = match.groups()
        questions.append({
            'id': q_id,
            'title': title.strip(),
            'status': status.strip(),
            'asked_by': asked_by.strip(),
            'date': date.strip(),
            'question': question.strip(),
            'answer': answer.strip(),
            'targets': [t.strip('- \n') for t in targets.strip().split('\n') if t.strip()]
        })
    
    return questions
```

### Automatic (via Invocation Script)

The invocation script automatically parses and processes the section-based format:

```bash
python3 tools/invoke_requirements_agent.py < input.txt
```

Output example:
```
[Format Validation] Parsing Open Questions sections...
✓ Found 11 questions
✓ All questions have required fields
✓ 11 questions with Status: Resolved
✓ 0 questions pending integration
Mode: review_only
```

## Acceptance Criteria

✅ No markdown tables remain in the Open Questions section  
✅ Each question is represented as a first-class markdown subsection  
✅ Status is explicit text, not inferred from formatting  
✅ IDs (Q-XXX) remain stable across edits  
✅ All required fields are present for each question  
✅ Integration workflow continues to function correctly

## Related Files

- `docs/requirements.md` - Contains canonical format documentation and examples
- `agent-profiles/requirements-agent.md` - Contains agent behavior constraints
- `tools/invoke_requirements_agent.py` - Invocation script with parsing logic

## Migration Notes

This format replaces the previous table-based schema. Key differences:
- **Before:** Questions stored in a markdown table with 6 columns
- **After:** Each question is a subsection (####) with labeled fields
- **Benefits:** 
  - Better readability for complex questions/answers
  - Natural markdown structure
  - Easier to edit and maintain
  - Clearer visual hierarchy
  - No table column alignment issues
