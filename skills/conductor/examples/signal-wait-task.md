# Example: Signal a WAIT Task

> "Workflow `order-wf-789` is waiting for payment confirmation. Approve it."

## Steps

```bash
# 1. Find the blocking task
conductor workflow get-execution order-wf-789 -c
```

Look for a task with `type: WAIT` and `status: IN_PROGRESS`. That's the one to signal. In this example: `wait_for_payment`.

```bash
# 2. Signal it (use signal-sync to get the updated workflow back in one round-trip)
conductor task signal-sync \
  --workflow-id order-wf-789 \
  --task-ref wait_for_payment \
  --status COMPLETED \
  --output '{"paymentId": "pay-456", "amount": 149.99, "method": "credit_card"}'
```

## signal vs signal-sync

- `signal` — async, fire-and-forget. Returns immediately; workflow advances in the background.
- `signal-sync` — returns the updated workflow object in the same response. Use when you need to confirm the next task is now running, or to chain follow-up logic.

## Statuses you can signal

`COMPLETED`, `FAILED`, `FAILED_WITH_TERMINAL_ERROR`. Use `FAILED_WITH_TERMINAL_ERROR` to reject the WAIT permanently (no retry).

## Patterns demonstrated

- Reading execution state to find the blocking WAIT task.
- Passing structured `output` data with the signal — that data becomes `${wait_for_payment.output.x}` for downstream tasks.
- Sync signaling for human-in-the-loop confirmations.
