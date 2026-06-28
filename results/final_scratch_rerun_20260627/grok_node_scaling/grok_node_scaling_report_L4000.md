# Grok Node-Scaling Revalidation

Target network latency: `4000 ns`.

## Runtime Summary

| node_count | HW ms | Composite-LP ms | LGS ms | Monolithic-LP ms |
| --- | --- | --- | --- | --- |
| 4.000 | 6202.184 | 6060.249 | 6125.301 | 6057.441 |
| 8.000 | 5257.040 | 4911.837 | 5086.191 | 4984.083 |
| 16.000 | 9961.441 | 9383.626 | 9613.792 | 8236.869 |
| 32.000 | 9459.765 | 8338.154 | 9551.556 | 8095.967 |
| 64.000 | 9562.007 | 8604.782 | 9788.116 | 8072.785 |
| 128.000 | 8530.951 | 8107.423 | 8973.763 |  |
| 256.000 | 8809.187 | 7498.383 | 9174.943 |  |
| 512.000 | 8824.133 | 7554.133 | 8989.975 |  |

## Availability Matrix

| node_count | goal_available | sidecar_available | lgs_status | composite_lp_status | monolithic_lp_status | input_class |
| --- | --- | --- | --- | --- | --- | --- |
| 4 | True | True | ok | ok | ok | scratch_real_grok |
| 8 | True | False | ok | ok | ok | scratch_real_grok |
| 16 | True | False | ok | ok | ok | scratch_real_grok |
| 32 | True | False | ok | ok | ok | scratch_real_grok |
| 64 | True | True | ok | ok | ok | scratch_real_grok |
| 128 | True | False | ok | ok | missing | scratch_real_grok |
| 256 | True | False | ok | ok | missing | scratch_real_grok |
| 512 | True | False | ok | ok | missing | scratch_real_grok |

Rows in this report are assembled from local metadata, hardware logs, regenerated Composite-LP curves, and available LGS outputs; no packaged-large summary rows are included.
