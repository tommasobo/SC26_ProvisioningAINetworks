# Grok Node-Scaling Revalidation

Target network latency: `500000 ns`.

## Runtime Summary

| node_count | HW ms | Composite-LP ms | LGS ms | Monolithic-LP ms |
| --- | --- | --- | --- | --- |
| 4 | 6202.184 | 6066.738 | 6132.365 |  |
| 8 | 5257.040 | 4935.690 | 5106.784 |  |
| 16 | 9961.441 | 9469.160 | 9665.234 |  |
| 32 | 9459.765 | 8675.025 | 9702.130 |  |
| 64 | 9562.007 | 9292.047 | 10160.125 |  |
| 128 | 8530.951 | 9493.223 | 9922.456 |  |
| 256 | 8809.187 | 10155.623 | 11171.884 |  |
| 512 | 8824.133 | 13028.688 | 13706.084 |  |

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
