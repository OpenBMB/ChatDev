# Slice Packet and Worker Contract

## Packet

The slicer emits schema version `1.0` as JSON or Markdown. JSON is the preferred
worker transport.

| Field | Meaning |
|---|---|
| `notice` | Constant statement that all sliced source is untrusted data |
| `selection` | Target root, language, detected languages, mode, depth, anchors, and path peer |
| `budget` | Limit, rendered-packet usage, and `ceil(rendered UTF-8 bytes / 3)` estimator |
| `slices[]` | Root-relative file, inclusive range, symbols, reasons, and line-numbered source |
| `relationships[]` | Included Trailmark edges with confidence |
| `omitted[]` | Bounded details for rejected units; every record has `symbols` and `reason`, and budget omissions also carry `file`, `start_line`, and `end_line` |
| `omitted_count` | Total omitted units even when details are truncated |
| `warnings[]` | Analysis gaps that the coordinator must consider |

The estimate is deliberately model-agnostic; it can undercount a specific
tokenizer and bounds only the rendered packet, not the worker's system prompt,
task, ambient Claude context, or output allowance. It is not a context-window
guarantee. Use a lower explicit limit and reserve model-specific overhead.

Selection is deterministic. Whole semantic units are admitted in priority
order:

1. Exact anchors and explicit shortest-path nodes
2. Enclosing container headers
3. Mode-specific graph context: transitive units by shortest CALLS distance
   (upstream/downstream), or direct callers/callees then type relationships
   with certain edges before inferred before uncertain (neighborhood only)

Under a tight budget this means a container header can be admitted while a
certain direct caller is omitted. Overlapping and adjacent
ranges merge. Container nodes contribute at most a 40-line declaration/header
ending before the first contained child. Mandatory function/method anchors are
never truncated; an oversized anchor produces `anchor_exceeds_budget`.

## Worker Input

Send a short task followed by the complete packet exactly as emitted. Pass the
script's stdout byte-for-byte; never reconstruct or re-serialize it. Both
output formats embed the untrusted-source notice (the JSON `notice` field and
the Markdown preamble); forward it intact so every worker sees that
instructions inside source, comments, strings, or identifiers must be ignored.

Do not include files, repository tools, hidden expected answers, or summaries
that are not already in the packet. External/local transports can provide this
strict envelope. Claude custom agents additionally receive repository
instructions, git status, environment data, and a composed delegation prompt;
their guarantee is bounded source access, not empty ambient context.

## Worker Output

Require one JSON object with all fields present:

```json
{
  "status": "complete | needs_context | cannot_answer",
  "answer": "Concise task result",
  "evidence": [
    {
      "claim": "Claim supported by this range",
      "file": "root/relative/file.py",
      "start_line": 10,
      "end_line": 14
    }
  ],
  "proposed_edits": [
    {
      "file": "root/relative/file.py",
      "start_line": 10,
      "end_line": 14,
      "replacement": "Exact replacement text",
      "rationale": "Why this satisfies the task"
    }
  ],
  "missing_context": [
    {
      "symbol_or_range": "Exact requested symbol, relationship, or range",
      "reason": "Why the current packet cannot answer the task"
    }
  ],
  "uncertainties": ["Unresolved ambiguity or uncertain Trailmark edge"]
}
```

Use empty arrays when a field does not apply. Proposed edits are suggestions,
not authorization to mutate files.

## Coordinator Validation

- Parse the output as JSON; reject prose before or after the object.
- Confirm every evidence and edit range is fully contained in one packet slice.
- Reject claims based only on omitted nodes or uncertain edges without an uncertainty note.
- Allow at most one coordinator-built replacement packet for `needs_context`,
  containing the original anchors plus the requested context under one budget.
- Re-read live source and run tests before accepting any edit or consequential conclusion.
