# Grok Node-Scaling Revalidation

Target network latency: `0 ns`.

## Runtime Summary

| node_count | HW ms | Composite-LP ms | LGS ms | Monolithic-LP ms |
| --- | --- | --- | --- | --- |
| 4.000 | 6202.184 | 6077.368 | 6125.270 | 6057.369 |
| 8.000 | 5257.040 | 4911.806 | 5085.724 | 5126.012 |
| 16.000 | 9961.441 | 9383.579 | 9618.172 | 9413.176 |
| 32.000 | 9459.765 | 8391.006 | 9497.306 |  |
| 64.000 | 9562.007 | 8584.103 | 9717.271 |  |
| 128.000 | 8530.951 | 8136.229 |  |  |
| 512.000 | 8824.133 | 7554.102 |  |  |
| 1024.000 | 11661.604 | 10564.135 |  |  |

## Availability Matrix

| node_count | goal_available | sidecar_available | lgs_status | composite_lp_status | monolithic_lp_status | input_class |
| --- | --- | --- | --- | --- | --- | --- |
| 4 | True | True | ok | ok | ok | scratch_real_grok |
| 8 | True | True | ok | ok | ok | scratch_real_grok |
| 16 | True | True | ok | ok | ok | scratch_real_grok |
| 32 | True | True | ok | ok | target_outside_range_4000_4000 | scratch_real_grok |
| 64 | True | True | ok | ok | target_outside_range_4000_4000 | scratch_real_grok |
| 128 | True | False | nonpositive_curve | ok | missing | scratch_real_grok |
| 512 | False | False | missing | ok | missing | packaged_large_composite_only |
| 1024 | False | False | missing | ok | missing | packaged_large_composite_only |

Rows N512/N1024 use packaged Composite-LP summaries only; no GOAL/LGS/Monolithic inputs are bundled for those scales.
