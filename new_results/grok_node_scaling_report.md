# Grok Node-Scaling Revalidation

Target network latency: `4000 ns`.

## Runtime Summary

| node_count | HW ms | Composite-LP ms | LGS ms | Monolithic-LP ms |
| --- | --- | --- | --- | --- |
| 4.000 | 6202.184 | 6077.392 | 6125.290 | 6057.441 |
| 8.000 | 5257.040 | 4911.838 | 5085.758 | 5128.127 |
| 16.000 | 9961.441 | 9383.627 | 9618.225 | 9413.344 |
| 32.000 | 9459.765 | 8391.481 | 9499.005 | 8675.907 |
| 64.000 | 9562.007 | 8584.191 | 9716.899 | 8957.498 |
| 128.000 | 8530.951 | 8137.504 |  |  |
| 512.000 | 8824.133 | 7554.102 |  |  |
| 1024.000 | 11661.604 | 10564.135 |  |  |

## Availability Matrix

| node_count | goal_available | sidecar_available | lgs_status | composite_lp_status | monolithic_lp_status | input_class |
| --- | --- | --- | --- | --- | --- | --- |
| 4 | True | True | ok | ok | ok | scratch_real_grok |
| 8 | True | True | ok | ok | ok | scratch_real_grok |
| 16 | True | True | ok | ok | ok | scratch_real_grok |
| 32 | True | True | ok | ok | ok | scratch_real_grok |
| 64 | True | True | ok | ok | ok | scratch_real_grok |
| 128 | True | False | nonpositive_curve | ok | missing | scratch_real_grok |
| 512 | False | False | missing | ok | missing | packaged_large_composite_only |
| 1024 | False | False | missing | ok | missing | packaged_large_composite_only |

Rows N512/N1024 use packaged Composite-LP summaries only; no GOAL/LGS/Monolithic inputs are bundled for those scales.
