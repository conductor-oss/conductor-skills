# GraalJS Gotchas

Conductor evaluates JavaScript in **INLINE**, **DO_WHILE** (`loopCondition`), and **SWITCH** (`evaluatorType: "javascript"` or `"graaljs"`) tasks through the GraalVM JavaScript engine. The engine runs on the JVM and is fed Java objects, which behave subtly differently from plain JS objects. Most "the script ran but the data is garbage" failures trace back to one of the rules below.

If you are writing any `expression` or `loopCondition` script, read this page first.

## Rule 0: the `$.varName` rule (applies to every JS-evaluated task)

**Every `$.x` referenced in a script MUST appear as a key in `inputParameters` on the same task.** The `$` object inside the script is the task's resolved `inputParameters` map (minus `evaluatorType` and `expression`).

Forgetting an entry produces a confusing `undefined`/`null` failure at runtime, not a clean validation error.

```json
{
  "type": "INLINE",
  "inputParameters": {
    "evaluatorType": "graaljs",
    "expression": "(function(){ return $.name + ' is ' + $.age; })();",
    "name": "${workflow.input.name}",
    "age": "${workflow.input.age}"
  }
}
```

This is **the single most important rule** for every JS-evaluated task. If a `$.foo` is in your script and `foo` is not in `inputParameters`, the task will fail.

## Rule 1: prefer `evaluatorType: "graaljs"` — and set it explicitly on DO_WHILE

For **INLINE** tasks, the platform aliases `"javascript"` and `"graaljs"` to the same GraalJS engine (per `Inline.java`); either string works. For **DO_WHILE** `loopCondition` evaluation, that aliasing has been reported to fail on some cluster versions — set `evaluatorType: "graaljs"` explicitly at the top level of the DO_WHILE task. The older docs that omit `evaluatorType` on DO_WHILE are the most common source of "loop condition fails at runtime."

```json
{
  "type": "DO_WHILE",
  "evaluatorType": "graaljs",
  "loopCondition": "(function(){ return $.loop_ref['iteration'] < $.max; })();",
  "inputParameters": { "loop_ref": "${loop_ref.output}", "max": "${workflow.input.max}" },
  "loopOver": []
}
```

Same goes for **SWITCH** with a JavaScript expression — explicit `"graaljs"` is the safer default.

## Rule 2: task outputs are already parsed objects — do not `String()` then `JSON.parse`

HTTP, LLM_CHAT_COMPLETE, CALL_MCP_TOOL, JSON_JQ_TRANSFORM, and most other tasks already return **parsed object** outputs. They are Java-Map-backed JavaScript proxies, not JSON strings.

The single most expensive mistake in agentic-loop work is "defensively" wrapping these in a parse step:

```javascript
// WRONG — produces garbage
var s = String($.http_resp);          // → "{key1=value1, key2=value2}" (Java Map.toString syntax)
var parsed = JSON.parse(s);            // → SyntaxError, caught, returns garbage
```

`String()` on a Java-Map-backed proxy calls Java's `Map.toString()`, which produces `{key1=value1, key2=value2}` with `=` separators. That is not JSON, `JSON.parse` throws, the `catch` returns garbage, and the garbage propagates downstream as the agent's "answer."

**Fix:** trust the output. Access fields directly:

```javascript
return $.http_resp.body.someField;
```

## Rule 3: `JSON.stringify` and `Object.keys` do not work on Java-Map-backed proxies

The own-properties of a Java-Map-backed proxy are not enumerable to JavaScript's reflective APIs:

```javascript
JSON.stringify($.http_resp)   // → "{}"
Object.keys($.http_resp)      // → []
```

The obvious "deep-copy then stringify" workaround therefore also fails. If you need to **serialize a structured task output into a string field** (e.g. to embed a tool result in the next LLM message), do not try to do it in INLINE.

**Fix:** use `JSON_JQ_TRANSFORM` with `tojson`. JQ operates on JSON natively — no JS/Java-proxy translation in the middle.

```json
{
  "type": "JSON_JQ_TRANSFORM",
  "inputParameters": {
    "data": "${call_tool.output}",
    "queryExpression": ".data | tojson"
  }
}
```

The output (`${stringify.output.result}`) is a JSON string you can safely interpolate into a `message` field, a downstream HTTP body, etc.

## Rule 4: what is in scope inside a script

Only these are accessible:

- `$.<key>` for every key declared in the task's `inputParameters` (after `${...}` resolution).

These are **NOT** accessible:

- `$.workflow.input.*` — throws `TypeError: Cannot read property "input" from undefined`.
- `$.workflow.variables.*` — throws `TypeError: Cannot read property "variables" from undefined`.
- Any other task's output that you didn't wire into `inputParameters`.

If you need a workflow input or variable, plumb it in:

```json
"inputParameters": {
  "evaluatorType": "graaljs",
  "expression": "(function(){ return $.iter < $.cap; })();",
  "iter": "${loop_ref.output.iteration}",
  "cap": "${workflow.input.max_iterations}"
}
```

## Rule 5: avoid `input` and `messages` as INLINE input-parameter names

Empirically, naming an INLINE input parameter `input` or `messages` produces obscure failures (`Cannot read property ... from undefined`, value missing at runtime). Whether these names collide with a reserved binding or with another scope, the safe move is to rename:

```json
// avoid
"inputParameters": { "input": "${prev.output}" }

// prefer
"inputParameters": { "inputMessages": "${prev.output}" }
```

## Rule 6: DO_WHILE `loopCondition` shape

Use an IIFE returning a boolean. Conductor's parser tolerates other shapes, but an IIFE is the only form that reliably returns a boolean across cluster versions:

```javascript
// CORRECT
(function(){ return $.loop_ref['iteration'] < $.max; })();

// AVOID — encourages writing complex conditions as awkward statements
if ($.loop_ref['iteration'] < $.max) { true; } else { false; }

// WRONG — Conductor reads the script's value, not a return from a named function
function check(){ return $.loop_ref['iteration'] < $.max; }
check();    // value of statement is the IIFE result, but the named-function form is fragile

// REDUNDANT — the comparison is already a boolean
if ($.loop_ref['iteration'] < $.max) return true; return false;
```

Always include the `evaluatorType: "graaljs"` field on the DO_WHILE task itself, and wire the loop task's own `taskReferenceName` back via `inputParameters` so the iteration counter is visible inside the script:

```json
{
  "name": "agent_loop",
  "taskReferenceName": "agent_loop",
  "type": "DO_WHILE",
  "evaluatorType": "graaljs",
  "loopCondition": "(function(){ return $.agent_loop['iteration'] < $.max_iterations; })();",
  "inputParameters": {
    "agent_loop": "${agent_loop.output}",
    "max_iterations": "${workflow.input.max_iterations}"
  },
  "loopOver": []
}
```

See [../examples/do-while-loop.md](../examples/do-while-loop.md) for a runnable workflow.

## Rule 7: the escape hatch — when in doubt, use JQ

Most "I'm writing JS to massage task output" tasks should be `JSON_JQ_TRANSFORM` instead. JQ operates on JSON natively and avoids every Java-Map-backed-proxy hazard above. Use INLINE for control flow that JQ can't express; use JQ for shape transforms, field extraction, and stringification.

| Need | Tool |
|------|------|
| Pick a field from a task output | `${task.output.path}` (no task needed) |
| Reshape, filter, aggregate task output | `JSON_JQ_TRANSFORM` |
| Serialize structured data → string | `JSON_JQ_TRANSFORM` with `\| tojson` |
| Boolean condition for SWITCH / DO_WHILE | INLINE / inline JS expression |
| Multi-step transform with side effects | SIMPLE worker |

## Summary checklist

Before submitting a workflow with any JS-evaluated task:

- [ ] `evaluatorType` is set. For DO_WHILE, set `"graaljs"` explicitly. For INLINE either `"javascript"` or `"graaljs"` works (they're aliased), but `"graaljs"` is the safer default.
- [ ] Every `$.x` in the script has a matching key in `inputParameters`.
- [ ] No `String($.someTaskOutput)` followed by `JSON.parse`.
- [ ] No `JSON.stringify($.someTaskOutput)` — use JQ `tojson`.
- [ ] No `Object.keys($.someTaskOutput)` — the keys are not enumerable.
- [ ] No `$.workflow.*` inside the script — plumb in via `inputParameters`.
- [ ] If it's a DO_WHILE: `evaluatorType` at the top, loop task ref in `inputParameters`, IIFE condition, iteration cap.
- [ ] INLINE input parameter is not named `input` or `messages`.
