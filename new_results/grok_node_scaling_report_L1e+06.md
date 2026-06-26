# Grok Node-Scaling Revalidation

Target network latency: `1e+06 ns`.

## Runtime Summary

| node_count | HW ms | Composite-LP ms | LGS ms | Monolithic-LP ms |
| --- | --- | --- | --- | --- |
| 4 | 6202.184 | 6075.742 | 6199.406 |  |
| 8 | 5257.040 | 4963.701 | 5093.742 |  |
| 16 | 9961.441 | 9559.150 | 9669.394 |  |
| 32 | 9459.765 | 9016.038 | 9819.073 |  |
| 64 | 9562.007 | 9985.039 | 10547.836 |  |
| 128 | 8530.951 | 10890.223 |  |  |
| 256 | 8809.187 | 12960.838 | 13810.054 |  |
| 512 | 8824.133 | 18649.485 | 19319.758 |  |

## Availability Matrix

| node_count | goal_available | sidecar_available | lgs_status | composite_lp_status | monolithic_lp_status | input_class |
| --- | --- | --- | --- | --- | --- | --- |
| 4 | True | True | ok | ok | missing | scratch_real_grok |
| 8 | True | True | ok | ok | missing | scratch_real_grok |
| 16 | True | True | ok | ok | missing | scratch_real_grok |
| 32 | True | True | ok | ok | missing | scratch_real_grok |
| 64 | True | True | ok | ok | missing | scratch_real_grok |
| 128 | True | False | nonpositive_curve | ok | missing | scratch_real_grok |
| 256 | True | False | ok | ok | missing | scratch_real_grok |
| 512 | True | False | ok | ok | missing | scratch_real_grok |

Rows in this report are assembled from local metadata, hardware logs, regenerated Composite-LP curves, and available LGS outputs; no packaged-large summary rows are included.
