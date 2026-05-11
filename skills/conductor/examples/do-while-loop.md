# Example: DO_WHILE Loop with Iteration Counter

Loop a body of tasks until a JavaScript condition returns false. The body sees an auto-managed `iteration` counter on the loop task's output.

## The self-reference pattern

The `loopCondition` is JavaScript. Variables in the script are read from the task's `inputParameters` via `$.varName`. To read the iteration counter, you must wire the loop task's *own output* back into its inputs:

```json
"inputParameters": {
  "value": "${workflow.input.count}",
  "loop_ref": "${loop_ref.output}"
}
```

This looks like a typo — referencing the task before it has output — but it's the canonical pattern. Conductor resolves `${loop_ref.output}` lazily at each iteration, exposing the running counter as `$.loop_ref['iteration']` inside the script.

## Workflow

See [workflows/do-while-loop.json](workflows/do-while-loop.json):

```json
{
  "name": "loop",
  "taskReferenceName": "loop_ref",
  "type": "DO_WHILE",
  "loopCondition": "if ($.loop_ref['iteration'] < $.value) { true; } else { false; }",
  "loopOver": [
    {
      "name": "do_work",
      "taskReferenceName": "do_work",
      "type": "HTTP",
      "inputParameters": {
        "http_request": {
          "uri": "${workflow.input.endpoint}?page=${loop_ref.output.iteration}",
          "method": "GET"
        }
      }
    }
  ],
  "inputParameters": {
    "value": "${workflow.input.count}",
    "loop_ref": "${loop_ref.output}"
  }
}
```

## Run

```bash
conductor workflow create examples/workflows/do-while-loop.json
conductor workflow start -w paginated_fetch -i '{"endpoint": "https://api.example.com/items", "count": 5}'
```

## Reading per-iteration output

Each iteration's task output is keyed by iteration number under the loop task:

```
${loop_ref.output.1.do_work.response.body}
${loop_ref.output.2.do_work.response.body}
...
```

The total iteration count is at `${loop_ref.output.iteration}`.

## Notes

- `iteration` is 1-indexed.
- The condition uses semicolon-terminated JS — Conductor's evaluator is strict.
- Every variable referenced as `$.x` in the condition must appear as a key in `inputParameters`. Forgetting this gives a confusing "undefined" failure at runtime.
- For unbounded loops, guard with both an iteration cap and a result-driven condition (e.g. `iteration < 100 && !$.loop_ref[iteration].do_work.output.done`).
