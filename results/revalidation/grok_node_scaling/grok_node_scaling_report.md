# Grok Node-Scaling Revalidation

Target network latency: `0 ns`.

## Runtime Summary

| node_count | HW ms | Composite-LP ms | LGS ms | Monolithic-LP ms |
| --- | --- | --- | --- | --- |
| 4 | 6202.184 | 6060.226 | 6125.270 |  |
| 8 | 5257.040 | 4911.808 | 5085.724 |  |
| 16 | 9961.441 | 9383.580 | 9618.172 |  |
| 32 | 9459.765 | 8337.437 | 9497.306 |  |
| 64 | 9562.007 | 8600.014 | 9717.271 |  |
| 128 | 8530.951 | 8096.343 |  |  |
| 256 | 8809.187 | 7498.399 | 8894.789 |  |
| 512 | 8824.133 | 7554.102 | 8958.244 |  |

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
