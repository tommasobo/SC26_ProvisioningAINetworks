# Grok Node-Scaling Revalidation

Target network latency: `4000 ns`.

## Runtime Summary

| node_count | HW ms | Composite-LP ms | LGS ms | Monolithic-LP ms |
| --- | --- | --- | --- | --- |
| 4 | 6202.184 | 6060.250 | 6125.290 |  |
| 8 | 5257.040 | 4911.840 | 5085.758 |  |
| 16 | 9961.441 | 9383.628 | 9618.225 |  |
| 32 | 9459.765 | 8338.166 | 9499.005 |  |
| 64 | 9562.007 | 8604.774 | 9716.899 |  |
| 128 | 8530.951 | 8107.423 |  |  |
| 256 | 8809.187 | 7498.399 | 8909.015 |  |
| 512 | 8824.133 | 7554.102 | 8989.975 |  |

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

Rows N512/N1024 use packaged Composite-LP summaries only; no GOAL/LGS/Monolithic inputs are bundled for those scales.
