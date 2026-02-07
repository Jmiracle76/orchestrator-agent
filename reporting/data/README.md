# Data Directory - Aggregated Metrics and Reporting Data

## Purpose

This directory contains machine-readable aggregated data files used by the Reporting Agent to generate milestone summaries, dashboards, and trend analysis. All files are in standard formats (JSON, CSV) for easy consumption by reporting tools and scripts.

## File Descriptions

### test-results-aggregate.json

**Purpose:** Aggregated test results across all test runs for the project

**Schema:**
```json
{
  "project": "Project Name",
  "last_updated": "YYYY-MM-DDTHH:MM:SSZ",
  "milestones": [
    {
      "milestone_id": "M1",
      "milestone_name": "Milestone Name",
      "test_runs": [
        {
          "test_run_id": "TR-YYYY-MM-DD-NNN",
          "issue_id": "M1-I1",
          "execution_date": "YYYY-MM-DDTHH:MM:SSZ",
          "status": "pass|fail|blocked",
          "test_summary": {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "blocked": 0,
            "pass_rate": 0.0
          },
          "test_types": {
            "unit": {"total": 0, "passed": 0, "failed": 0},
            "integration": {"total": 0, "passed": 0, "failed": 0},
            "e2e": {"total": 0, "passed": 0, "failed": 0},
            "performance": {"total": 0, "passed": 0, "failed": 0},
            "security": {"total": 0, "passed": 0, "failed": 0},
            "accessibility": {"total": 0, "passed": 0, "failed": 0}
          },
          "defects": [
            {
              "defect_id": "DEF-001",
              "severity": "critical|high|medium|low",
              "status": "open|resolved|closed",
              "resolution_time_hours": 0
            }
          ]
        }
      ]
    }
  ]
}
```

**Updated By:** Reporting Agent  
**Update Frequency:** After each test run completion

---

### issue-status.csv

**Purpose:** Current status of all issues across all milestones

**Columns:**
- `issue_id` - Issue identifier (e.g., "M1-I1")
- `milestone_id` - Parent milestone (e.g., "M1")
- `title` - Issue title
- `assigned_agent` - Agent responsible for this issue
- `status` - Current status (open, in_progress, testing, blocked, resolved, closed)
- `priority` - Priority level (high, medium, low)
- `effort_estimate_hours` - Estimated effort in hours
- `effort_actual_hours` - Actual effort spent in hours
- `created_date` - When issue was created (YYYY-MM-DD)
- `started_date` - When work started (YYYY-MM-DD or null)
- `completed_date` - When work completed (YYYY-MM-DD or null)
- `last_updated` - Last status update (YYYY-MM-DDTHH:MM:SSZ)

**Example:**
```csv
issue_id,milestone_id,title,assigned_agent,status,priority,effort_estimate_hours,effort_actual_hours,created_date,started_date,completed_date,last_updated
M1-I1,M1,Create Login Screen,ui-ux-agent,resolved,high,16,18,2026-02-01,2026-02-02,2026-02-05,2026-02-05T14:30:00Z
M1-I2,M1,Implement Authentication,coding-agent,in_progress,high,24,12,2026-02-01,2026-02-06,,2026-02-08T10:00:00Z
```

**Updated By:** Reporting Agent  
**Update Frequency:** Daily or after significant status changes

---

### acceptance-criteria-status.json

**Purpose:** Detailed status of all acceptance criteria across all requirements

**Schema:**
```json
{
  "project": "Project Name",
  "last_updated": "YYYY-MM-DDTHH:MM:SSZ",
  "requirements": [
    {
      "requirement_id": "FR-001",
      "requirement_title": "Requirement Title",
      "acceptance_criteria": [
        {
          "criterion_id": "FR-001-AC1",
          "criterion_text": "Specific testable criterion",
          "status": "pending|met|failed|partial",
          "verified_by": "Agent Name or null",
          "verification_date": "YYYY-MM-DDTHH:MM:SSZ or null",
          "test_cases": ["UT-001", "INT-001", "E2E-001"],
          "issues": ["M1-I1", "M1-I2"],
          "notes": "Additional context"
        }
      ],
      "coverage_percentage": 0.0
    }
  ]
}
```

**Updated By:** Reporting Agent  
**Update Frequency:** After each test run completion

---

### execution-traces.json

**Purpose:** Audit trail of all significant project events

**Schema:**
```json
{
  "project": "Project Name",
  "traces": [
    {
      "timestamp": "YYYY-MM-DDTHH:MM:SSZ",
      "event_type": "requirements_approved|planning_approved|issue_assigned|issue_completed|milestone_completed|governance_violation|escalation|test_executed|defect_raised",
      "actor": "Agent or Person Name",
      "target": "What was affected (issue ID, document, etc.)",
      "details": "Description of event",
      "artifact_ref": "Path to related artifact or null",
      "metadata": {
        "key": "value"
      }
    }
  ]
}
```

**Updated By:** Orchestration Agent, Reporting Agent  
**Update Frequency:** Real-time as events occur

---

### milestone-metrics.json

**Purpose:** Aggregated metrics for each milestone

**Schema:**
```json
{
  "project": "Project Name",
  "last_updated": "YYYY-MM-DDTHH:MM:SSZ",
  "milestones": [
    {
      "milestone_id": "M1",
      "milestone_name": "Milestone Name",
      "status": "planned|in_progress|testing|complete|blocked",
      "target_end_date": "YYYY-MM-DD",
      "actual_end_date": "YYYY-MM-DD or null",
      "metrics": {
        "planned_issues": 0,
        "completed_issues": 0,
        "completion_percentage": 0.0,
        "planned_effort_hours": 0,
        "actual_effort_hours": 0,
        "effort_variance_hours": 0,
        "test_pass_rate": 0.0,
        "defects_total": 0,
        "defects_critical": 0,
        "defects_resolved": 0,
        "requirements_changes": 0,
        "rework_cycles": 0
      },
      "velocity": {
        "story_points_completed": 0,
        "average_cycle_time_days": 0.0,
        "throughput_issues_per_week": 0.0
      }
    }
  ]
}
```

**Updated By:** Reporting Agent  
**Update Frequency:** Daily during active milestones

---

### trend-data.csv

**Purpose:** Time-series data for trend analysis and charting

**Columns:**
- `date` - Date of measurement (YYYY-MM-DD)
- `milestone_id` - Which milestone this data is for
- `metric_name` - Name of metric (e.g., "test_pass_rate", "velocity", "defect_density")
- `metric_value` - Numeric value of metric
- `metric_unit` - Unit of measurement (percentage, hours, count, etc.)
- `baseline_value` - Baseline or target value for comparison
- `variance` - Difference from baseline (positive or negative)

**Example:**
```csv
date,milestone_id,metric_name,metric_value,metric_unit,baseline_value,variance
2026-02-01,M1,test_pass_rate,85.0,percentage,90.0,-5.0
2026-02-02,M1,test_pass_rate,92.0,percentage,90.0,2.0
2026-02-03,M1,test_pass_rate,95.0,percentage,90.0,5.0
2026-02-01,M1,velocity,12.0,story_points_per_week,10.0,2.0
```

**Updated By:** Reporting Agent  
**Update Frequency:** Daily

---

## Usage Guidelines

1. **Automated updates:** All files should be updated automatically by agents, not manually edited
2. **Consistent formats:** Maintain schema consistency across updates
3. **Timestamps:** Use ISO 8601 format for all timestamps (YYYY-MM-DDTHH:MM:SSZ)
4. **Validation:** Validate data before writing to ensure schema compliance
5. **Backup:** Consider backing up data files before major updates
6. **Access control:** Read access for all agents, write access for Reporting and Orchestration Agents only

## Cross-References

- **Milestone Summary:** `/reporting/milestone-execution-summary.md` - Generated from these data files
- **Test Results:** `/reporting/test-results.md` - Source of test data
- **Planning State:** `/docs/planning-state.yaml` - Source of issue and workflow data
- **Project Plan:** `/docs/project-plan.md` - Source of planning and requirement data
