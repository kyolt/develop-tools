# vlm-inference-server-specific Review Rules

## Stack Context
- Python ML/VLM serving. Multiple server backends: `vila_server/`, `nvvila_server/`, `nim_server/`, `gpt_server/`, vLLM deploys under `deploy/vllm/`.
- `linker-middleware/` (request adaptation, e.g. linker chat), `vlm-evaluations/`, `vlm-metrics/`, `tools/locust/` (load testing), `monitoring/`, `helm/`.
- Mixed Python + shell entrypoints + Dockerfiles + Makefiles + Helm + CI.

## Documentation Readability & Consistency [must / should — primary focus]
- **Docs must match the change**: when code/config/flags change, the README, docstrings, `docs/`, and inline comments describing them must be updated in the same PR. Flag any doc/comment that now describes old behavior — stale docs here mislead operators deploying models.
- **Description vs implementation consistency**: a flag's help text, a config key's comment, or a function docstring must accurately describe what the code actually does. Flag mismatches (e.g. help says "default 4096" but code defaults to 8192).
- **Readability**: docs and comments should be clear to an operator who didn't write the code — flag ambiguous instructions, undocumented required env vars, or setup steps that assume hidden context.
- **Cross-file consistency**: the same value/flag documented in multiple places (README + Makefile + Helm values + entrypoint script) must agree. Flag drift.

## Inference / Serving [must / should]
- **Precision / numerics flags** are correctness-critical: `--quantization fp8`, `--kv-cache-dtype fp8`, `--dtype bfloat16`. A wrapper that silently drops or renames these starts the server with wrong numerics. Flag any flag-matcher that can drop a critical flag with only a warning — prefer hard-fail on an allowlist, or record the resolved `CMD` + dropped flags for post-mortem.
- GPU memory: batch size / `max-model-len` / `gpu-memory-utilization` changes that risk OOM; unbounded request batching.
- Blocking CPU/GPU work on an async path without `run_in_executor`.
- Model load / weights path handling: local path vs HF repo id confusion; missing existence check before load.
- Streaming responses: backpressure, partial-failure handling, client disconnect cleanup.

## Shell Entrypoints & Makefiles [must — recurring here]
- **Makefile recipes must be TAB-indented**, not spaces → space indentation causes `*** target pattern contains no '%'` fatal parse error that breaks the whole Makefile. Check `make -n <targets>` parses.
- Stray/corrupted recipe fragments merged onto another line.
- **Dead guards**: `[ -z "$(VAR)" ]` where `VAR` has a hardcoded non-empty default (e.g. `DOCKER_REGISTRY=192.168.x.x:port`) → guard is unreachable. Use `?=` with no default, or drop the guard.
- Duplicated `VLLM_SERVE_HELP` / `arg_is_valid` / `add_flag` blocks across `entrypoints/4/run_vllm*.sh` → mark as `🔧 Future refactor` (extract to a sourced lib), non-blocking.

## CI / Containers / Helm [should]
- Multi-stage Dockerfile hygiene; correct image tag/digest pushed matches what Helm/K8s pulls.
- ECR `cache-to` / `cache-from` consistency; `timeout-minutes` on long GPU jobs.
- Helm values: resource requests/limits, GPU resource declarations.

## Tests & Tools [should]
- Duplicated skip guards (e.g. a `middleware_version < 4.1` skip repeated in the same test) — remove the duplicate.
- Load-test (locust) changes: required dataset present, results JSON schema stable.

## Typos [nit]
- Misspelled identifiers (e.g. `lagacy` → `legacy`) reduce searchability — flag with the all call sites.
