# Template Library Format

This document describes the JSON format used by the MovieDev template import/export flow.

## Exported file shape

```json
{
  "version": 1,
  "exported_at": "2026-04-03T12:34:56.000Z",
  "workflow_name": "example_workflow",
  "source": "moviedev-template-export",
  "tags": ["moviedev", "agent-team", "workflow-template"],
  "snapshot": {
    "graph": {
      "description": "Optional workflow description",
      "initial_instruction": "Optional initial instruction",
      "organization": "Optional grouping label",
      "team_mode": "human_governed",
      "start": ["Planner"],
      "nodes": [],
      "edges": []
    },
    "vars": {}
  }
}
```

## Required fields

- `snapshot.graph`
- `snapshot.graph.start`
- `snapshot.graph.nodes`

If any of those fields are missing, the template import preview will mark the file as invalid.

## Optional metadata

- `version`: Current export format version.
- `exported_at`: ISO timestamp for the export moment.
- `workflow_name`: Human-readable workflow/template name.
- `source`: Export source identifier.
- `tags`: Free-form tags used for search and template organization.

## Notes

- Imported templates are stored locally in browser storage and appear under the `Imported` category in the template modal.
- Imported templates preserve `title`, `description`, `tags`, and the full `snapshot`.
- The runtime currently applies imported templates by replacing the current workflow graph with the imported snapshot.
