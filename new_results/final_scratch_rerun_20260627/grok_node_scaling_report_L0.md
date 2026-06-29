# Grok Node-Scaling Revalidation

Target network latency: `0 ns`.

## Runtime Summary

| node_count | HW ms | Composite-LP ms | LGS ms | Monolithic-LP ms |
| --- | --- | --- | --- | --- |
| 4.000 | 6202.184 | 6060.225 | 6125.226 | 6057.369 |
| 8.000 | 5257.040 | 4911.805 | 5086.301 | 4983.863 |
| 16.000 | 9961.441 | 9383.578 | 9602.123 | 8236.857 |
| 32.000 | 9459.765 | 8337.438 | 9556.816 | 8095.931 |
| 64.000 | 9562.007 | 8600.001 | 9801.121 | 8072.669 |
| 128.000 | 8530.951 | 8096.343 | 8973.542 |  |
| 256.000 | 8809.187 | 7498.383 | 9168.341 |  |
| 512.000 | 8824.133 | 7554.133 | 8958.244 |  |

## Availability Matrix

| node_count | goal_available | sidecar_available | lgs_status | composite_lp_status | monolithic_lp_status | input_class |
| --- | --- | --- | --- | --- | --- | --- |
| 4 | True | True | ok | ok | ok | scratch_real_grok |
| 8 | True | False | ok | ok | ok | scratch_real_grok |
| 16 | True | False | ok | ok | ok | scratch_real_grok |
| 32 | True | False | ok | ok | ok | scratch_real_grok |
| 64 | True | True | ok | ok | ok | scratch_real_grok |
| 128 | True | False | ok | ok | target_outside_range_4000_4000 | scratch_real_grok |
| 256 | True | False | ok | ok | missing | scratch_real_grok |
| 512 | True | False | ok | ok | missing | scratch_real_grok |

Rows in this report are assembled from local metadata, hardware logs, regenerated Composite-LP curves, and available LGS outputs; no packaged-large summary rows are included.
