# Fig. 5 NSYS-to-LP Revalidation

Input: local Llama7B N4/GPU16 one-iteration NSYS/SQLite workspace matching the online trace directory `http://storage2.spcl.ethz.ch/traces/ai/llama/Llama7B_N4_GPU16_TP1_PP1_DP16_BS32_1iter/raw_nsys/`.

Commands:

```bash
timeout 7200 bash pipeline/reproduce_fig5_from_nsys.sh \
  --skip-download \
  --work /mnt/scratch/SC_Tracing_revalidation/fig5_llama_n4_1iter_local \
  --run-lp

python3 pipeline/run_nccl_composite.py \
  --analysis-dir /mnt/scratch/SC_Tracing_revalidation/fig5_llama_n4_1iter_local/analysis \
  --out /mnt/scratch/SC_Tracing_revalidation/fig5_llama_n4_1iter_local/composite_default/composed_runtime.csv \
  --cache-dir /mnt/scratch/SC_Tracing_revalidation/fig5_llama_n4_1iter_local/composite_default/cache \
  --clear-cache --parallel-solve --max-workers 8 \
  --l-min 0 --l-max 1000000 --step 5000
```

Results:

| Path | Runtime | Max RSS | Comparison |
| --- | ---: | ---: | --- |
| NSYS SQLite -> GOAL/metadata | 59.1s | included in helper run | generated 244 MiB `output.goal` and NCCL metadata sidecars |
| GOAL -> `comm_dep.csv` via patched LogGOPSim | 133.42s | included in helper run | generated 16 MiB LP sidecar |
| Monolithic-LP full sweep | 376.5s | 5,123,260 KiB | vs packaged `partial_100pct/full_runtime.csv`: max rel 120.638%, mean rel 74.217% |
| Composite-LP default | 16.30s | 351,440 KiB | vs packaged `comp_100pct/composed_runtime.csv`: max rel 23.787%, mean rel 20.620% |
| Composite-LP force-sequential | 2.27s warm cache | 89,712 KiB | vs packaged Composite: max rel 22.565%, mean rel 19.707% |

Interpretation: the Fig. 5 raw/SQLite path is runnable end-to-end on a moderate N4 trace, including LP sidecar emission and Gurobi solve. It does not numerically reproduce the shipped Fig. 5 curves. The mismatch is present in both Monolithic-LP and NCCL metadata Composite-LP, so this is not only a `comm_dep` issue; it likely reflects historical generator/model assumptions or a different exact input bundle.
