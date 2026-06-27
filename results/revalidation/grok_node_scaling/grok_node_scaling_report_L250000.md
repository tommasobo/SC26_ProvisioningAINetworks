# Grok Node-Scaling Revalidation

Target network latency: `250000 ns`.

## Runtime Summary

| node_count | HW ms | Composite-LP ms | LGS ms | Monolithic-LP ms |
| --- | --- | --- | --- | --- |
| 4 | 6202.184 | 6062.264 |  |  |
| 8 | 5257.040 | 4921.701 | 5087.804 |  |
| 16 | 9961.441 | 9424.150 | 9623.090 |  |
| 32 | 9459.765 | 8504.538 | 9555.376 |  |
| 64 | 9562.007 | 8945.539 | 9787.489 |  |
| 128 | 8530.951 | 8794.723 | 9339.442 |  |
| 256 | 8809.187 | 8753.338 | 9783.941 |  |
| 512 | 8824.133 | 10217.985 | 10941.378 |  |

## Availability Matrix

| node_count | goal_available | sidecar_available | lgs_status | composite_lp_status | monolithic_lp_status | input_class |
| --- | --- | --- | --- | --- | --- | --- |
| 4 | True | True | target_outside_range_0_10000 | ok | missing | scratch_real_grok |
| 8 | True | True | ok | ok | missing | scratch_real_grok |
| 16 | True | True | ok | ok | missing | scratch_real_grok |
| 32 | True | True | ok | ok | missing | scratch_real_grok |
| 64 | True | True | ok | ok | missing | scratch_real_grok |
| 128 | True | False | ok | ok | missing | scratch_real_grok |
| 256 | True | False | ok | ok | missing | scratch_real_grok |
| 512 | True | False | ok | ok | missing | scratch_real_grok |

Rows in this report are assembled from local metadata, hardware logs, regenerated Composite-LP curves, and available LGS outputs; no packaged-large summary rows are included.
