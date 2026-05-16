# Example: Parallel Branches with FORK_JOIN

Run independent tasks in parallel, then converge before continuing. Always pair `FORK_JOIN` with a `JOIN` that lists every parallel branch's terminal `taskReferenceName`.

## Pattern

```
       ┌─→ branch_a_task ─┐
fork ──┤                  ├─→ join ─→ next
       └─→ branch_b_task ─┘
```

## Workflow

See [workflows/fork-join.json](workflows/fork-join.json). Key tasks:

```json
{
  "name": "fork", "taskReferenceName": "fork", "type": "FORK_JOIN",
  "forkTasks": [
    [{"name": "fetch_inventory", "taskReferenceName": "inventory", "type": "HTTP", "inputParameters": {"http_request": {"uri": "${workflow.input.inventoryUrl}", "method": "GET"}}}],
    [{"name": "fetch_pricing",   "taskReferenceName": "pricing",   "type": "HTTP", "inputParameters": {"http_request": {"uri": "${workflow.input.pricingUrl}",   "method": "GET"}}}]
  ]
},
{
  "name": "join", "taskReferenceName": "join", "type": "JOIN",
  "joinOn": ["inventory", "pricing"]
}
```

## Run

```bash
conductor workflow create examples/workflows/fork-join.json
conductor workflow start -w parallel_fetch -i '{"inventoryUrl": "https://...", "pricingUrl": "https://..."}'
```

## Reading the output

Each branch's output is available as `${branchRef.output...}` in tasks after the JOIN. The JOIN task's own output aggregates branch outputs by reference name:

```
${join.output.inventory.response.body}
${join.output.pricing.response.body}
```

## Notes

- Branches in `forkTasks` are arrays of arrays — one inner array per parallel branch. Each inner array can itself be a sequence of tasks.
- `joinOn` must list the **last** task's `taskReferenceName` from each branch.
- Failure in any branch fails the JOIN unless every task in that branch is `optional: true`.
- For dynamic branch counts, use `FORK_JOIN_DYNAMIC` (see workflow-definition.md).
