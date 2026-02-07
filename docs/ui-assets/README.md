# UI Assets Directory

## Purpose

This directory contains all UI/UX design assets created by the UI/UX Agent during the design phase of each issue. Assets include wireframes, mockups, prototypes, and other visual materials that document the intended user experience.

## Naming Convention

Assets should be organized by issue and follow this naming convention:

```
/docs/ui-assets/
  ├── [issue-id]/
  │   ├── [issue-id]-wireframe-[screen-name].png
  │   ├── [issue-id]-mockup-[screen-name].png
  │   ├── [issue-id]-flow-diagram.png
  │   └── [issue-id]-prototype-[version].html
```

**Examples:**
- `M1-I1/M1-I1-wireframe-login-screen.png`
- `M1-I1/M1-I1-mockup-dashboard.png`
- `M2-I3/M2-I3-flow-diagram.png`

**File Naming Rules:**
- Use issue ID as prefix (e.g., `M1-I1-`)
- Use lowercase with hyphens for multi-word names
- Include asset type in name (wireframe, mockup, prototype, flow, etc.)
- Include screen/component name when applicable
- Use standard image formats: PNG for static images, HTML/PDF for interactive prototypes

## Asset Inventory

<!-- Maintained by UI/UX Agent -->

| File Name | Issue | Screen/Flow | Type | Description | Last Updated |
|-----------|-------|-------------|------|-------------|--------------|
| [filename.png] | [M1-I1] | [Screen Name] | [Wireframe \| Mockup \| Prototype \| Flow Diagram \| etc.] | [Brief description of what this shows] | [YYYY-MM-DD] |
| [filename.png] | [M1-I2] | [Screen Name] | [Type] | [Description] | [YYYY-MM-DD] |

## Asset Types

### Wireframes
Low-fidelity sketches showing layout and structure without visual design details. Use for early-stage design validation.

### Mockups
High-fidelity designs showing visual appearance, colors, typography, and spacing. Use for visual design approval.

### Prototypes
Interactive demonstrations of user flows and interactions. Use for usability testing and flow validation.

### Flow Diagrams
Visual representations of user journeys and navigation paths. Use for understanding complex workflows.

### Component Specs
Detailed specifications for reusable UI components. Use for design system documentation.

## Usage Guidelines

1. **Create assets early:** Generate wireframes before coding begins
2. **Version control:** Keep old versions when making significant changes (use v1, v2 suffixes)
3. **Reference in ui-intent.md:** All assets must be referenced in the corresponding ui-intent.md document
4. **Clean up:** Archive or remove obsolete assets when issues are completed
5. **Access control:** All team members should have read access, UI/UX Agent has write access

## Cross-References

- **UI Intent Documentation:** `/docs/ui-intent.md` - References and describes these assets
- **Project Plan:** `/docs/project-plan.md` - Links issues to their design assets
- **Implementation Notes:** `/docs/implementation-notes.md` - May reference assets for implementation context
