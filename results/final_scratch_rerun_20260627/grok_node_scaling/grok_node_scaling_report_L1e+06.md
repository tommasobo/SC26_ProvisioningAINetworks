# Grok Node-Scaling Revalidation

Target network latency: `1e+06 ns`.

## Runtime Summary

| node_count | HW ms | Composite-LP ms | LGS ms | Monolithic-LP ms |
| --- | --- | --- | --- | --- |
| 4 | 6202.184 | 6075.738 | 6338.119 |  |
| 8 | 5257.040 | 4963.690 | 5127.067 |  |
| 16 | 9961.441 | 9559.160 | 9711.746 |  |
| 32 | 9459.765 | 9016.025 | 9906.008 |  |
| 64 | 9562.007 | 9985.047 | 10687.425 |  |
| 128 | 8530.951 | 10890.223 | 11087.621 |  |
| 256 | 8809.187 | 12960.623 |  |  |
| 512 | 8824.133 | 18649.688 | 19319.758 |  |

## Availability Matrix

| node_count | goal_available | sidecar_available | lgs_status | composite_lp_status | monolithic_lp_status | input_class |
| --- | --- | --- | --- | --- | --- | --- |
| 4 | True | True | ok | ok | target_outside_range_4000_4000 | scratch_real_grok |
| 8 | True | False | ok | ok | target_outside_range_4000_4000 | scratch_real_grok |
| 16 | True | False | ok | ok | target_outside_range_4000_4000 | scratch_real_grok |
| 32 | True | False | ok | ok | target_outside_range_4000_4000 | scratch_real_grok |
| 64 | True | True | ok | ok | target_outside_range_4000_4000 | scratch_real_grok |
| 128 | True | False | ok | ok | target_outside_range_4000_4000 | scratch_real_grok |
| 256 | True | False | target_outside_range_0_500000 | ok | missing | scratch_real_grok |
| 512 | True | False | ok | ok | missing | scratch_real_grok |

Rows in this report are assembled from local metadata, hardware logs, regenerated Composite-LP curves, and available LGS outputs; no packaged-large summary rows are included.
