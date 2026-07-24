# Figure 6 Llama source checks

These CSVs are cold-cache Composite-LP results from the committed Llama N32
metadata. They are alternatives to the archived paper-era comparison tables
under `results/revalidation/figures_end_to_end/`.

- `july_1nic_latency.csv` and `july_1nic_bandwidth.csv` are from the July
  Alps rerun with `--node-map-mode rank-block --force-sequential
  --nic-per-rank` and the one-queue default.
- `final_1nic_bandwidth_repeat.csv` repeats that bandwidth configuration from
  a fresh cache on the final branch.
- `final_4nic_latency.csv` and `final_4nic_bandwidth.csv` use the same
  settings plus `--nics-per-node 4`, matching the physical Alps injection
  topology.

The July and final one-queue bandwidth runs differ mainly at 937.8 and
1224.9 Gbps, by 0.422% and 0.869% respectively, despite identical committed
code, inputs, and configuration.
Their maximum errors against the compact paper curve are 0.358% and 0.916%.
This is consistent with solver variation among nearly equivalent motif-LP
solutions. The final four-queue result has 0.571% maximum error. The full
workflow uses four queues for both panels because it matches the physical
topology and is the closer fresh final-branch result.

The one-queue files were copied from the July run rooted at
`reproduction_clariden-ln004_20260722T013845`. The four-queue files are from
final Slurm jobs 2892662 and 2892734. The repeated one-queue bandwidth job is
2892826. Their SHA-256 digests are:

```text
July one queue, latency:   bb31d743dc8aaf439d7d2f4e749293b89d7db45b69845e9634cfa073ab4ced68
July one queue, bandwidth: 84ba51716504ab16da292c5671b1e67ae29acd960b883de5ae7284bc7cca2db2
Final one-queue repeat:    954c80be160bcf3a624f1175b8c84a78188aba5eb482b77a51e80c69b91528e0
Final four queues, latency: d0d43075d3f15b0f8343bba39e7ac5965913f8fd9bcaadd8eeab49ab32748e08
Final four queues, bandwidth: d0356d9ec87c402b07c8af6e47059dfcf820fb88c720fef2cfd413b0c133536e
```

The final report and `results/reproduced/summary.json` record the pointwise
differences from the compact paper curves.
