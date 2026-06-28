# Grok Node-Scaling Revalidation

Target network latency: `10000 ns`.

## Runtime Summary

| node_count | HW ms | Composite-LP ms | LGS ms | Monolithic-LP ms |
| --- | --- | --- | --- | --- |
| 4 | 6202.184 | 6060.285 | 6125.367 |  |
| 8 | 5257.040 | 4911.885 | 5086.283 |  |
| 16 | 9961.441 | 9383.698 | 9613.957 |  |
| 32 | 9459.765 | 8341.345 | 9571.281 |  |
| 64 | 9562.007 | 8612.907 | 9797.521 |  |
| 128 | 8530.951 | 8124.163 | 8983.723 |  |
| 256 | 8809.187 | 7498.383 | 9215.187 |  |
| 512 | 8824.133 | 7554.133 | 9037.570 |  |

## Availability Matrix

| node_count | goal_available | sidecar_available | lgs_status | composite_lp_status | monolithic_lp_status | input_class |
| --- | --- | --- | --- | --- | --- | --- |
| 4 | True | True | ok | ok | target_outside_range_4000_4000 | scratch_real_grok |
| 8 | True | False | ok | ok | target_outside_range_4000_4000 | scratch_real_grok |
| 16 | True | False | ok | ok | target_outside_range_4000_4000 | scratch_real_grok |
| 32 | True | False | ok | ok | target_outside_range_4000_4000 | scratch_real_grok |
| 64 | True | True | ok | ok | target_outside_range_4000_4000 | scratch_real_grok |
| 128 | True | False | ok | ok | missing | scratch_real_grok |
| 256 | True | False | ok | ok | missing | scratch_real_grok |
| 512 | True | False | ok | ok | missing | scratch_real_grok |

Rows in this report are assembled from local metadata, hardware logs, regenerated Composite-LP curves, and available LGS outputs; no packaged-large summary rows are included.
