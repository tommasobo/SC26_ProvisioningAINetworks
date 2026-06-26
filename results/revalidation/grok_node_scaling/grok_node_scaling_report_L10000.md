# Grok Node-Scaling Revalidation

Target network latency: `10000 ns`.

## Runtime Summary

| node_count | HW ms | Composite-LP ms | LGS ms | Monolithic-LP ms |
| --- | --- | --- | --- | --- |
| 4 | 6202.184 | 6060.286 | 6125.320 |  |
| 8 | 5257.040 | 4911.888 | 5085.809 |  |
| 16 | 9961.441 | 9383.700 | 9618.306 |  |
| 32 | 9459.765 | 8341.363 | 9501.553 |  |
| 64 | 9562.007 | 8612.899 | 9716.341 |  |
| 128 | 8530.951 | 8124.163 |  |  |
| 256 | 8809.187 | 7498.399 | 8930.355 |  |
| 512 | 8824.133 | 7554.210 | 9037.570 |  |

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
