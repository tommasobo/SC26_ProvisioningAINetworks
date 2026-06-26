# vLLM Llama70B N2 Online NSYS Revalidation

Input source: `http://storage2.spcl.ethz.ch/traces/ai/vllm/Llama_3.1_70B_Instruct_N2_GPU8_TP8_Short_Prompts/nsys_reports/`.

The two online `.nsys-rep` files were downloaded, exported to SQLite, converted to GOAL plus NCCL metadata, replayed with LogGOPSim, used to emit a non-empty LP `comm_dep.csv`, and solved with GOAL-level Composite-LP.

Key results:

- NSYS export: 42s wall time, 43,264 KiB max RSS.
- NSYS SQLite to GOAL/metadata: 4m09.42s wall time, 1,660,932 KiB max RSS.
- Generated GOAL: 193,457,472 bytes, 6,789,473 lines.
- Generated metadata: 81,992 `collective_instances.csv` rows and 81,992 `goal_label_ranges.csv` rows.
- LogGOPSim sweep: 7m40.00s wall time, 516,612 KiB max RSS.
- `comm_dep.csv`: 523,768 rows, emitted by patched LogGOPSim in 2m26.68s.
- Composite-LP: 4m00.25s wall time, 3,300,036 KiB max RSS, 3,136,432 vertices, 4,176,792 edges.
- Composite-LP vs LGS on nearest sampled points: max relative difference 0.189220%.

This validates the online Llama70B N2 path. It does not reproduce the packaged vLLM8B paper curve under `data/output/vllm_llama8b_128tok/`; the regenerated online trace gives about 30.0s runtime, the public prebuilt Llama70B GOAL gives 261.198ms, and the packaged vLLM8B curve is about 3.03s at `L=0`.
