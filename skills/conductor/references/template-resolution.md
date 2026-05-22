# Template / `${...}` Resolution

Conductor resolves `${...}` expressions when it builds each task's input. The resolver is forgiving — sometimes too forgiving — and a few of its behaviors produce silent data corruption rather than loud failures. This page documents the cases that have caused production bugs.

For the basic expression syntax (`${workflow.input.x}`, `${task.output.y}`, `${workflow.variables.z}`), see [workflow-definition.md](workflow-definition.md). For the JS scope rules (`$.varName` etc.), see [graaljs-gotchas.md](graaljs-gotchas.md).

## Pitfall 1: a missing intermediate field silently returns the parent

If you write `${task.output.a.b.c}` and `task.output.a.b` exists but `c` does not, the resolver does **not** evaluate to `null`. It returns the closest resolvable ancestor — typically the parent object — without raising.

Concrete example: an LLM emits

```json
{ "tool_call": { "name": "get_weather", "args": {} } }
```

and a downstream task tries to read `${chat.output.result.text}`. There is no `.text` field. The downstream field gets set to the whole `result` object (the parent), Java-toString'd into a string field — and silently flows on as the agent's "final answer."

**Mitigation:**

- Route on action **first** with a SWITCH, then access `.text` (or whatever path) only in the branch where you know it exists.
- Keep SWITCH `defaultCase` empty (or a `NOOP`) when you do not have a meaningful no-op handler. A `defaultCase` that calls `finalize` will overwrite `final_response` with garbage whenever the LLM emits something unrecognized.
- For paranoia, sanity-check field presence in an upstream INLINE task and emit a clean `null` or sentinel when missing.

## Pitfall 2: interpolating an object into a string field invokes Java `toString`

Conductor's string-typed input fields (e.g. `messages[].message`, HTTP request bodies as strings, an LLM `prompt`) accept `${...}` interpolation. If the resolved value is a **structured object** rather than a string, Conductor converts it via Java's `Map.toString()`:

```
{key1=value1, key2=value2}
```

Note the `=` separators — that is not JSON. Sending this into a `message` field results in `{k=v}` garbage entering the LLM's chat history, the provider almost always returns nonsense, and the downstream `output.result` route fails.

**Fix:** stringify upstream with `JSON_JQ_TRANSFORM` and `tojson`:

```json
{
  "name": "stringify_tool_result",
  "taskReferenceName": "stringify_tool_result",
  "type": "JSON_JQ_TRANSFORM",
  "inputParameters": {
    "data": "${call_tool.output.content}",
    "queryExpression": ". | tojson"
  }
}
```

Then interpolate `${stringify_tool_result.output.result}` into the string field.

You **cannot** do this in INLINE/graaljs — `JSON.stringify` on a Java-Map-backed proxy returns `"{}"`. See [graaljs-gotchas.md](graaljs-gotchas.md) Rule 3.

## Pitfall 3: DO_WHILE iteration counter — `${loop.output.iteration}`, not `${loop.iteration}`

The iteration counter lives **inside** the loop task's `outputData`, not as a top-level field on the task. The correct access paths are:

| Where | Expression |
|-------|------------|
| `workflow.outputParameters` | `${loop.output.iteration}` |
| Another task's `inputParameters` | `${loop.output.iteration}` |
| Inside the loop's own `loopCondition` (after wiring `loop: ${loop.output}`) | `$.loop['iteration']` |

`${loop.iteration}` resolves to nothing useful — the resolver returns the loop task object, not the iteration number. This is a frequent silent bug in `outputParameters`.

## Pitfall 4: per-iteration outputs are keyed by iteration number

Each iteration of a DO_WHILE writes its body tasks' outputs under a numeric key on the loop task:

```
${loop.output.1.<bodyTaskRef>.output...}
${loop.output.2.<bodyTaskRef>.output...}
...
```

To read the **latest** body output inside the loop, combine with `$.loop['iteration']`:

```javascript
var i = $.loop['iteration'];
return $.loop[i].think.output.result.answer;
```

(`$.loop` must be wired in via `inputParameters` — see Rule 6 in [graaljs-gotchas.md](graaljs-gotchas.md).)

## Pitfall 5: `${workflow.variables.X}` only resolves inside `${...}` interpolation, not inside JS

`${workflow.variables.X}` is a template-resolver feature, not a JavaScript binding. It works in `inputParameters` values, HTTP URIs, and other string fields. It does **not** work inside an INLINE / DO_WHILE / SWITCH-javascript script — there is no `$.workflow` object in scope.

```json
// works
"inputParameters": { "endpoint": "${workflow.variables.api_base}/users" }

// fails — throws "Cannot read property 'variables' from undefined"
"expression": "(function(){ return $.workflow.variables.api_base; })();"
```

If you need a workflow variable inside a script, plumb it through `inputParameters`:

```json
"inputParameters": {
  "evaluatorType": "graaljs",
  "expression": "(function(){ return $.api_base + '/users'; })();",
  "api_base": "${workflow.variables.api_base}"
}
```

## Quick-reference table

| Pattern | Result |
|---------|--------|
| `${task.output.field}` (field exists) | the field's value |
| `${task.output.missing}` | the parent object (silently — no error) |
| `${task.output.path.to.missing}` | closest resolvable ancestor |
| Object → string field | Java `Map.toString()` → `{k=v}` |
| Object → string field via JQ `tojson` | proper JSON string |
| `${loop_ref.iteration}` | the loop task object (wrong) |
| `${loop_ref.output.iteration}` | the iteration counter (correct) |
| `$.workflow.input.x` inside JS | TypeError (not in scope) |
| `${workflow.input.x}` inside a string field | resolves to the input value |
