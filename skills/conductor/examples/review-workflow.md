# Example: Review and Optimize a Workflow

> "Review my `order_processing` workflow and tell me what to fix."

## Steps

```bash
# 1. Load the definition
conductor workflow get order_processing > /tmp/wf.json

# 2. For each SIMPLE task, load the task definition
conductor taskDef get charge_card
conductor taskDef get send_email
conductor taskDef get update_inventory
```

Walk the checklist in [../references/optimization.md](../references/optimization.md). Group findings by severity.

## Sample report

```
Workflow: order_processing v3 (12 tasks)

CRITICAL (2)
  ✗ B1  SIMPLE task `charge_card` (taskDef): responseTimeoutSeconds=0, timeoutSeconds=0
        A hung payment worker hangs the workflow. Set responseTimeoutSeconds=30,
        pollTimeoutSeconds=60, timeoutSeconds=300 on the task definition.
  ✗ D1  Workflow input `stripeApiKey` is a secret being passed in plaintext.
        Move to ${workflow.secrets.STRIPE_KEY} or to the worker's environment.

WARN (3)
  ⚠ A1  description is empty
  ⚠ B2  No workflow timeoutSeconds — a stuck workflow can run forever.
        Suggest 1800s with timeoutPolicy=TIME_OUT_WF.
  ⚠ B3  SIMPLE task `send_email` has retryCount=0. Email is transient by nature —
        set retryCount=3, retryLogic=EXPONENTIAL_BACKOFF, retryDelaySeconds=30.

INFO
  • A4  12 tasks — well within the 100-task limit
  • B4  No failureWorkflow. This workflow mutates inventory and charges cards;
        consider a failureWorkflow that releases the inventory hold and notifies ops.

Recommended Changes (priority order)
  [ ] task_def_charge_card.json     set responseTimeoutSeconds=30, pollTimeoutSeconds=60, timeoutSeconds=300
  [ ] order_processing.json         move stripeApiKey to ${workflow.secrets.STRIPE_KEY}
  [ ] order_processing.json         add description, timeoutSeconds=1800, timeoutPolicy=TIME_OUT_WF
  [ ] task_def_send_email.json      set retryCount=3, retryLogic=EXPONENTIAL_BACKOFF, retryDelaySeconds=30
  [ ] order_processing.json         (discussion) add failureWorkflow for inventory rollback + ops alert
```

## Offer to fix

> Want me to apply any of these? I can:
> - update the `charge_card` and `send_email` task definitions and re-register them
> - rewrite the workflow to add `timeoutSeconds`, `timeoutPolicy`, `description`
> - move `stripeApiKey` out of inputs (need to know where you want it: secrets or worker env)
>
> The `failureWorkflow` and the inventory-rollback design are bigger calls — I'd want to know your retry/refund policy before scaffolding that.

Don't apply silently. Each fix gets confirmed.

## What this example demonstrates

- Loading definition + each SIMPLE task's taskDef before reporting (timeouts and retry config live on the task def, not the workflow task).
- Grading findings (CRITICAL / WARN / INFO) so the user knows what's urgent.
- Offering targeted fixes, not a wholesale rewrite.
- Drawing the line at design decisions that need user input (failureWorkflow design, retry semantics).
