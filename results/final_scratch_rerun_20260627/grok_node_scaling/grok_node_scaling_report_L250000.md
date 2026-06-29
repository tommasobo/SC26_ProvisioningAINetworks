# Grok Node-Scaling Revalidation

Target network latency: `250000 ns`.

## Runtime Summary

| node_count | HW ms | Composite-LP ms | LGS ms | Monolithic-LP ms |
| --- | --- | --- | --- | --- |
| 4 | 6202.184 | 6062.258 | 6128.688 |  |
| 8 | 5257.040 | 4921.690 | 5093.817 |  |
| 16 | 9961.441 | 9424.160 | 9630.504 |  |
| 32 | 9459.765 | 8504.525 | 9607.194 |  |
| 64 | 9562.007 | 8945.547 | 9950.388 |  |
| 128 | 8530.951 | 8794.723 | 9367.601 |  |
| 256 | 8809.187 | 8753.123 | 10053.471 |  |
| 512 | 8824.133 | 10218.188 | 10941.378 |  |

## Availability Matrix

| node_count | goal_available | sidecar_available | lgs_status | composite_lp_status | monolithic_lp_status | input_class |
| --- | --- | --- | --- | --- | --- | --- |
| 4 | True | True | ok | ok | target_outside_range_4000_4000 | scratch_real_grok |
| 8 | True | False | ok | ok | target_outside_range_4000_4000 | scratch_real_grok |
| 16 | True | False | ok | ok | target_outside_range_4000_4000 | scratch_real_grok |
| 32 | True | False | ok | ok | target_outside_range_4000_4000 | scratch_real_grok |
| 64 | True | True | ok | ok | target_outside_range_4000_4000 | scratch_real_grok |
| 128 | True | False | ok | ok | target_outside_range_4000_4000 | scratch_real_grok |
| 256 | True | False | ok | ok | missing | scratch_real_grok |
| 512 | True | False | ok | ok | missing | scratch_real_grok |

Rows in this report are assembled from local metadata, hardware logs, regenerated Composite-LP curves, and available LGS outputs; no packaged-large summary rows are included.
