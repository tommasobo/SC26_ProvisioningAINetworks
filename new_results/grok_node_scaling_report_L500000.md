# Grok Node-Scaling Revalidation

Target network latency: `500000 ns`.

## Runtime Summary

| node_count | HW ms | Composite-LP ms | LGS ms | Monolithic-LP ms |
| --- | --- | --- | --- | --- |
| 4 | 6202.184 | 6066.742 |  |  |
| 8 | 5257.040 | 4935.701 | 5089.742 |  |
| 16 | 9961.441 | 9469.150 | 9627.926 |  |
| 32 | 9459.765 | 8675.038 | 9644.011 |  |
| 64 | 9562.007 | 9292.039 | 10017.495 |  |
| 128 | 8530.951 | 9493.223 | 9913.840 |  |
| 256 | 8809.187 | 10155.838 | 11018.048 |  |
| 512 | 8824.133 | 13028.485 | 13706.084 |  |

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
