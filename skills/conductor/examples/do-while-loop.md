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
  "evaluatorType": "graaljs",
  "loopCondition": "(function(){ return $.loop_ref['iteration'] < $.value; })();",
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

Three details that are easy to miss:

1. **`evaluatorType: "graaljs"` at the top of the DO_WHILE task.** Older docs omit it, and without it the condition fails at runtime on recent clusters.
2. **IIFE form for `loopCondition`.** `(function(){ return <expr>; })()` returns a clean boolean. The older `if (...) { true; } else { false; }` statement form is fragile, and named functions or `return true; return false;` are red flags.
3. **`loop_ref` wired through `inputParameters`.** This is what makes `$.loop_ref['iteration']` accessible inside the condition. Forgetting it is the #1 cause of `Cannot read property ... from undefined` failures.

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

The total iteration count is at `${loop_ref.output.iteration}` — **not** `${loop_ref.iteration}`. See [../references/template-resolution.md](../references/template-resolution.md) Pitfall 3.

## Scope inside `loopCondition`

Only these are accessible:

- `$.<key>` for every key declared in `inputParameters` (after `${...}` resolution).

These are **not** in scope and will throw `TypeError`:

- `$.workflow.input.*`
- `$.workflow.variables.*`
- Any other task's output you didn't plumb in via `inputParameters`.

If you need a workflow input or variable inside the condition, declare it as an input parameter on the DO_WHILE task:

```json
"inputParameters": {
  "loop_ref": "${loop_ref.output}",
  "max_iterations": "${workflow.input.max_iterations}",
  "stop_flag": "${workflow.variables.stop_flag}"
}
```

then reference `$.max_iterations`, `$.stop_flag` in the condition.

## Notes

- `iteration` is 1-indexed.
- Every variable referenced as `$.x` in the condition must appear as a key in `inputParameters`. Forgetting this gives a confusing `undefined` failure at runtime.
- For unbounded loops, **always** include an iteration cap in addition to any result-driven exit (`(function(){ return $.loop_ref['iteration'] < 100 && !$.loop_ref[$.loop_ref['iteration']].do_work.output.done; })();`). The optimization checklist flags unbounded loops as CRITICAL.
- See [../references/graaljs-gotchas.md](../references/graaljs-gotchas.md) for the full set of GraalJS pitfalls (Java-Map-backed proxies, `JSON.stringify` behavior, reserved-ish input names, etc.).
