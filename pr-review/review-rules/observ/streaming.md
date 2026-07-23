# observ / streaming — Streaming & GPU Rules

Applies to PRs touching `streaming/`. This handles streaming pipelines and GPU operations. **Weight findings toward performance and correctness of the logic implementation** — this is a hot path.

## Performance [must — primary focus here]
- **Per-frame / per-message hot path**: flag any allocation, copy, serialization, or logging that runs every frame and could be hoisted out of the loop.
- **GPU ↔ CPU transfers**: minimize `.cpu()` / `.numpy()` / host-device copies inside loops; batch where possible. Flag redundant transfers.
- **Blocking work on the stream path**: CPU-bound or sync I/O blocking the async/event loop → needs `run_in_executor` or a worker.
- **Unbounded buffers / queues**: frame queues without a max size → memory growth / OOM under backpressure.
- **GPU memory**: tensors retained across iterations (no release), growing batch without limit, missing `torch.no_grad()` in inference paths.

## Logic Implementation Correctness [must]
- Frame ordering / dropped-frame handling under load — verify the intended drop vs block behavior.
- Backpressure: what happens when the consumer is slower than the producer?
- Resource cleanup on stream teardown / client disconnect (GPU handles, sockets, background tasks).
- Concurrency: shared mutable state across stream workers without synchronization; race conditions.
- This repo has migrated `mp` primitives toward `asyncio` — flag leftover blocking multiprocessing calls mixed into async paths.

## Be Honest About Uncertainty
- GPU/runtime behavior is hard to verify from a diff. When you can't confirm a performance claim locally, say so explicitly rather than asserting.

(Performance, error handling, security baseline from `_base.md` always apply.)
