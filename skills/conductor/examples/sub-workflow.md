# Example: Composing Workflows with SUB_WORKFLOW

Run another registered workflow as a single task. The parent waits for the child to complete and reads its output. Useful for splitting large workflows into reusable units.

> If you want fire-and-forget instead — parent does not wait — use `START_WORKFLOW`.

## Pattern

Two registered workflows: `child_normalize` (reusable) and `parent_pipeline` (composes the child).

### Child — `child_normalize`

See [workflows/child-normalize.json](workflows/child-normalize.json). Takes a raw payload, returns a normalized object.

### Parent — `parent_pipeline`

See [workflows/parent-pipeline.json](workflows/parent-pipeline.json):

```json
{
  "name": "normalize",
  "taskReferenceName": "normalize",
  "type": "SUB_WORKFLOW",
  "subWorkflowParam": { "name": "child_normalize", "version": 1 },
  "inputParameters": {
    "payload": "${workflow.input.raw}"
  }
}
```

The child's `outputParameters` become the SUB_WORKFLOW task's output:

```
${normalize.output.normalized}
```

## Run

```bash
# Register both — child first
conductor workflow create examples/workflows/child-normalize.json
conductor workflow create examples/workflows/parent-pipeline.json

conductor workflow start -w parent_pipeline -i '{"raw": {"name": "ALICE", "email": "ALICE@EX.COM"}}'
```

## Notes

- The child must be registered before the parent runs (not before the parent is created — Conductor doesn't validate references at definition time).
- Pin `version` in `subWorkflowParam` for stability. Omitting it picks the latest, which can break parents silently when the child is updated.
- Child failure surfaces as a SUB_WORKFLOW task failure on the parent.
- For dynamic-named children, set `subWorkflowParam.name` from input or use `START_WORKFLOW`.
